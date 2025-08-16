"""Embedding generation using AWS Bedrock."""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from .config import ModelsConfig

logger = logging.getLogger(__name__)


class BedrockEmbeddingClient:
    """Client for generating embeddings using AWS Bedrock."""
    
    def __init__(self, config: ModelsConfig):
        """Initialize Bedrock embedding client.
        
        Args:
            config: Models configuration
        """
        self.config = config
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=config.region)
        self.embedding_model = config.embedding_model
        
        # Rate limiting configuration
        self.requests_per_second = 10  # Conservative rate limit
        self.last_request_time = 0
        self.min_request_interval = 1.0 / self.requests_per_second
        
        # Retry configuration
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 30.0
    
    def _rate_limit(self) -> None:
        """Apply rate limiting to avoid API throttling."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        
        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _exponential_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay.
        
        Args:
            attempt: Retry attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        return delay
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector or None if failed
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
        
        # Truncate text if too long (Titan v2 has input limits)
        max_length = 8000  # Conservative limit
        if len(text) > max_length:
            text = text[:max_length]
            logger.debug(f"Truncated text to {max_length} characters")
        
        for attempt in range(self.max_retries):
            try:
                self._rate_limit()
                
                # Prepare request based on model type
                if 'titan' in self.embedding_model.lower():
                    request_body = {
                        "inputText": text
                    }
                elif 'cohere' in self.embedding_model.lower():
                    request_body = {
                        "texts": [text],
                        "input_type": "search_document"
                    }
                else:
                    logger.error(f"Unsupported embedding model: {self.embedding_model}")
                    return None
                
                # Make API call
                response = self.bedrock_client.invoke_model(
                    modelId=self.embedding_model,
                    body=json.dumps(request_body),
                    contentType='application/json',
                    accept='application/json'
                )
                
                # Parse response
                response_body = json.loads(response['body'].read())
                
                if 'titan' in self.embedding_model.lower():
                    embedding = response_body.get('embedding')
                elif 'cohere' in self.embedding_model.lower():
                    embeddings = response_body.get('embeddings', [])
                    embedding = embeddings[0] if embeddings else None
                else:
                    embedding = None
                
                if embedding:
                    logger.debug(f"Generated embedding of dimension {len(embedding)}")
                    return embedding
                else:
                    logger.error("No embedding found in response")
                    return None
                    
            except ClientError as e:
                error_code = e.response['Error']['Code']
                
                if error_code == 'ThrottlingException':
                    if attempt < self.max_retries - 1:
                        delay = self._exponential_backoff(attempt)
                        logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error("Max retries reached for rate limiting")
                        return None
                else:
                    logger.error(f"Bedrock API error: {e}")
                    return None
                    
            except Exception as e:
                logger.error(f"Unexpected error generating embedding: {e}")
                if attempt < self.max_retries - 1:
                    delay = self._exponential_backoff(attempt)
                    logger.warning(f"Retrying in {delay}s (attempt {attempt + 1})")
                    time.sleep(delay)
                    continue
                else:
                    return None
        
        return None
    
    def generate_embeddings_batch(self, texts: List[str], max_workers: int = 5) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts in parallel.
        
        Args:
            texts: List of texts to embed
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of embeddings (same order as input texts)
        """
        if not texts:
            return []
        
        logger.info(f"Generating embeddings for {len(texts)} texts using {max_workers} workers")
        
        embeddings = [None] * len(texts)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all embedding tasks
            future_to_index = {
                executor.submit(self.generate_embedding, text): i
                for i, text in enumerate(texts)
            }
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    embedding = future.result()
                    embeddings[index] = embedding
                    if embedding:
                        logger.debug(f"Generated embedding {index + 1}/{len(texts)}")
                    else:
                        logger.warning(f"Failed to generate embedding for text {index + 1}")
                except Exception as e:
                    logger.error(f"Error generating embedding for text {index + 1}: {e}")
        
        successful = sum(1 for emb in embeddings if emb is not None)
        logger.info(f"Successfully generated {successful}/{len(texts)} embeddings")
        
        return embeddings


class QueryEmbeddingPipeline:
    """Pipeline for generating embeddings from SQL queries and context."""
    
    def __init__(self, embedding_client: BedrockEmbeddingClient):
        """Initialize the embedding pipeline.
        
        Args:
            embedding_client: Bedrock embedding client
        """
        self.embedding_client = embedding_client
    
    def prepare_text_for_embedding(self, sql_extract: Dict) -> str:
        """Prepare text from SQL extract for embedding.
        
        Args:
            sql_extract: SQL extract with context
            
        Returns:
            Prepared text for embedding
        """
        parts = []
        
        # Add context before (if available)
        context_before = sql_extract.get('context_before', '').strip()
        if context_before:
            parts.append(f"Context: {context_before}")
        
        # Add the SQL query
        sql_query = sql_extract.get('sql_query', '').strip()
        if sql_query:
            # Clean SQL for better embedding
            cleaned_sql = self._clean_sql_for_embedding(sql_query)
            parts.append(f"Query: {cleaned_sql}")
        
        # Add context after (if available)
        context_after = sql_extract.get('context_after', '').strip()
        if context_after:
            parts.append(f"Description: {context_after}")
        
        # Add notebook metadata
        notebook_path = sql_extract.get('notebook_path', '')
        if notebook_path:
            # Extract meaningful parts from path
            path_parts = notebook_path.split('/')
            if len(path_parts) > 1:
                parts.append(f"Source: {path_parts[-2]}/{path_parts[-1]}")
        
        return " | ".join(parts)
    
    def _clean_sql_for_embedding(self, sql: str) -> str:
        """Clean SQL query for better embedding representation.
        
        Args:
            sql: Raw SQL query
            
        Returns:
            Cleaned SQL query
        """
        import re
        
        # Remove notebook magic commands
        sql = re.sub(r'^%sql\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql = re.sub(r'^%%sql\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove comments but preserve structure
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # Normalize whitespace
        sql = re.sub(r'\s+', ' ', sql).strip()
        
        # Remove very long literal strings that might not be useful for similarity
        sql = re.sub(r"'[^']{100,}'", "'<LONG_STRING>'", sql)
        sql = re.sub(r'"[^"]{100,}"', '"<LONG_STRING>"', sql)
        
        return sql
    
    def prepare_search_query_text(self, user_question: str) -> str:
        """Prepare user question for embedding and search.
        
        Args:
            user_question: User's natural language question
            
        Returns:
            Prepared search text
        """
        # Convert natural language to search-friendly format
        question = user_question.strip()
        
        # Add context indicators for better matching
        search_parts = [f"Question: {question}"]
        
        # Add SQL-related keywords to improve matching
        sql_keywords = ['select', 'from', 'where', 'group by', 'order by', 'join']
        question_lower = question.lower()
        
        relevant_keywords = [kw for kw in sql_keywords if kw in question_lower]
        if relevant_keywords:
            search_parts.append(f"SQL concepts: {', '.join(relevant_keywords)}")
        
        return " | ".join(search_parts)
    
    def generate_embeddings_for_knowledge_base(self, sql_extracts: List[Dict], 
                                             max_workers: int = 5) -> List[Dict]:
        """Generate embeddings for knowledge base documents.
        
        Args:
            sql_extracts: List of SQL extracts
            max_workers: Maximum parallel workers
            
        Returns:
            List of documents with embeddings
        """
        logger.info(f"Generating embeddings for {len(sql_extracts)} SQL extracts")
        
        # Prepare texts for embedding
        texts = []
        for extract in sql_extracts:
            text = self.prepare_text_for_embedding(extract)
            texts.append(text)
        
        # Generate embeddings
        embeddings = self.embedding_client.generate_embeddings_batch(texts, max_workers)
        
        # Combine extracts with embeddings
        documents = []
        for i, (extract, embedding) in enumerate(zip(sql_extracts, embeddings)):
            if embedding is not None:
                document = {
                    'id': f"sql_{i}",
                    'sql_query': extract.get('sql_query', ''),
                    'business_context': self.prepare_text_for_embedding(extract),
                    'table_pattern': extract.get('table_pattern', ''),
                    'notebook_path': extract.get('notebook_path', ''),
                    'notebook_type': extract.get('notebook_type', ''),
                    'context_before': extract.get('context_before', ''),
                    'context_after': extract.get('context_after', ''),
                    'embedding': embedding,
                    'timestamp': extract.get('timestamp', ''),
                    'tables_used': extract.get('tables_used', []),
                    'query_type': extract.get('query_type', ''),
                    'joins': extract.get('joins', []),
                    'filters': extract.get('filters', []),
                    'aggregations': extract.get('aggregations', [])
                }
                documents.append(document)
            else:
                logger.warning(f"Skipping document {i} due to embedding failure")
        
        logger.info(f"Generated {len(documents)} documents with embeddings")
        return documents
    
    def generate_query_embedding(self, user_question: str) -> Optional[List[float]]:
        """Generate embedding for user query.
        
        Args:
            user_question: User's natural language question
            
        Returns:
            Query embedding vector
        """
        search_text = self.prepare_search_query_text(user_question)
        return self.embedding_client.generate_embedding(search_text)