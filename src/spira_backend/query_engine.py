"""Query engine for text-to-SQL generation using RAG."""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from .config import Config
from .embeddings import BedrockEmbeddingClient, QueryEmbeddingPipeline
from .opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)


@dataclass
class SQLResult:
    """Result from text-to-SQL generation."""
    sql_query: str
    confidence: float
    explanation: str
    similar_queries: List[Dict]
    schema_context: str
    execution_time: float


class QueryEngine:
    """Engine for converting natural language to SQL using RAG."""
    
    def __init__(self, config: Config):
        """Initialize the query engine.
        
        Args:
            config: System configuration
        """
        self.config = config
        self.opensearch_client = OpenSearchClient(config.opensearch)
        self.embedding_client = BedrockEmbeddingClient(config.models)
        self.embedding_pipeline = QueryEmbeddingPipeline(self.embedding_client)
        self.bedrock_client = boto3.client('bedrock-runtime', region_name=config.models.region)
        
        logger.info("Query engine initialized")
    
    def generate_sql(self, user_question: str, max_similar: int = 5, 
                    hybrid_search: bool = True) -> SQLResult:
        """Generate SQL from natural language question.
        
        Args:
            user_question: User's natural language question
            max_similar: Maximum number of similar queries to retrieve
            hybrid_search: Whether to use hybrid search (text + vector)
            
        Returns:
            SQL generation result
        """
        import time
        start_time = time.time()
        
        try:
            logger.info(f"Generating SQL for question: {user_question[:100]}...")
            
            # Step 1: Generate query embedding
            query_embedding = self.embedding_pipeline.generate_query_embedding(user_question)
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return self._create_error_result("Failed to generate query embedding", start_time)
            
            # Step 2: Retrieve similar queries from knowledge base
            if hybrid_search:
                similar_docs = self.opensearch_client.hybrid_search(
                    query_text=user_question,
                    query_embedding=query_embedding,
                    size=max_similar
                )
            else:
                similar_docs = self.opensearch_client.search_similar(
                    query_embedding=query_embedding,
                    size=max_similar
                )
            
            if not similar_docs:
                logger.warning("No similar queries found in knowledge base")
                return self._create_error_result("No similar queries found", start_time)
            
            # Step 3: Get schema context
            schema_context = self._get_schema_context()
            
            # Step 4: Get business patterns
            business_context = self._get_business_patterns()
            
            # Step 5: Prepare context for LLM
            rag_context = self._prepare_rag_context(
                user_question, similar_docs, schema_context, business_context
            )
            
            # Step 6: Generate SQL using Claude
            sql_query, confidence, explanation = self._generate_sql_with_claude(
                user_question, rag_context
            )
            
            if not sql_query:
                logger.error("Failed to generate SQL query")
                return self._create_error_result("Failed to generate SQL", start_time)
            
            # Step 7: Prepare similar queries for citations
            similar_queries = self._format_similar_queries(similar_docs)
            
            execution_time = time.time() - start_time
            
            result = SQLResult(
                sql_query=sql_query,
                confidence=confidence,
                explanation=explanation,
                similar_queries=similar_queries,
                schema_context=schema_context,
                execution_time=execution_time
            )
            
            logger.info(f"SQL generated successfully in {execution_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            return self._create_error_result(f"Error: {str(e)}", start_time)
    
    def _get_schema_context(self) -> str:
        """Get schema context from stored metadata.
        
        Returns:
            Formatted schema context
        """
        try:
            schema_doc = self.opensearch_client.get_document('schema_metadata')
            if schema_doc:
                return schema_doc.get('content', '')
            else:
                logger.warning("No schema metadata found")
                return ""
        except Exception as e:
            logger.error(f"Failed to get schema context: {e}")
            return ""
    
    def _get_business_patterns(self) -> str:
        """Get business patterns from stored metadata.
        
        Returns:
            Formatted business patterns
        """
        try:
            patterns_doc = self.opensearch_client.get_document('business_patterns')
            if patterns_doc:
                return patterns_doc.get('content', '')
            else:
                logger.warning("No business patterns found")
                return ""
        except Exception as e:
            logger.error(f"Failed to get business patterns: {e}")
            return ""
    
    def _prepare_rag_context(self, user_question: str, similar_docs: List[Dict], 
                           schema_context: str, business_context: str) -> str:
        """Prepare RAG context for LLM.
        
        Args:
            user_question: User's question
            similar_docs: Similar documents from search
            schema_context: Schema information
            business_context: Business patterns
            
        Returns:
            Formatted context for LLM
        """
        context_parts = []
        
        # Add schema context
        if schema_context:
            context_parts.append("## Available Tables and Schemas")
            context_parts.append(schema_context)
        
        # Add business patterns
        if business_context:
            context_parts.append("\n## Common Business Patterns")
            context_parts.append(business_context)
        
        # Add similar queries
        if similar_docs:
            context_parts.append("\n## Similar Queries from Past Analysis")
            for i, doc in enumerate(similar_docs[:3], 1):  # Top 3 for context
                source = doc['source']
                context_parts.append(f"\n### Example {i} (similarity: {doc['score']:.3f})")
                
                if source.get('context_before'):
                    context_parts.append(f"Context: {source['context_before']}")
                
                context_parts.append(f"SQL: {source['sql_query']}")
                
                if source.get('context_after'):
                    context_parts.append(f"Description: {source['context_after']}")
        
        return "\n".join(context_parts)
    
    def _generate_sql_with_claude(self, user_question: str, rag_context: str) -> Tuple[str, float, str]:
        """Generate SQL using Claude with RAG context.
        
        Args:
            user_question: User's question
            rag_context: RAG context
            
        Returns:
            Tuple of (sql_query, confidence, explanation)
        """
        try:
            # Prepare prompt for Claude
            system_prompt = """You are an expert SQL developer with deep knowledge of data analytics and business intelligence. Your task is to convert natural language questions into accurate, efficient SQL queries.

Given the user's question and the provided context (table schemas, business patterns, and similar queries), generate a SQL query that answers the question.

Guidelines:
1. Use only tables and columns that exist in the provided schema
2. Follow the business patterns and common practices shown in similar queries
3. Write clean, readable SQL with proper formatting
4. Include appropriate JOINs, WHERE clauses, and aggregations
5. Consider performance implications
6. If the question is ambiguous, make reasonable assumptions based on the context

Response format:
- SQL Query: [Your SQL query]
- Confidence: [0.0-1.0 confidence score]
- Explanation: [Brief explanation of the query logic and any assumptions made]"""
            
            user_prompt = f"""Context Information:
{rag_context}

User Question: {user_question}

Please generate a SQL query to answer this question."""
            
            # Call Claude via Bedrock
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                "temperature": 0.1
            }
            
            response = self.bedrock_client.invoke_model(
                modelId=self.config.models.online_model,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response['body'].read())
            claude_response = response_body['content'][0]['text']
            
            # Parse Claude's response
            sql_query, confidence, explanation = self._parse_claude_response(claude_response)
            
            return sql_query, confidence, explanation
            
        except Exception as e:
            logger.error(f"Failed to generate SQL with Claude: {e}")
            return "", 0.0, f"Error generating SQL: {str(e)}"
    
    def _parse_claude_response(self, response: str) -> Tuple[str, float, str]:
        """Parse Claude's response to extract SQL, confidence, and explanation.
        
        Args:
            response: Claude's response text
            
        Returns:
            Tuple of (sql_query, confidence, explanation)
        """
        import re
        
        try:
            # Extract SQL query
            sql_pattern = r'SQL Query:\s*```(?:sql)?\s*(.*?)\s*```'
            sql_match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
            
            if not sql_match:
                # Try alternative patterns
                sql_pattern = r'```sql\s*(.*?)\s*```'
                sql_match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
            
            if not sql_match:
                # Try simple SQL block
                sql_pattern = r'```\s*(SELECT.*?)\s*```'
                sql_match = re.search(sql_pattern, response, re.DOTALL | re.IGNORECASE)
            
            sql_query = sql_match.group(1).strip() if sql_match else ""
            
            # Extract confidence
            confidence_pattern = r'Confidence:\s*([0-9.]+)'
            confidence_match = re.search(confidence_pattern, response, re.IGNORECASE)
            confidence = float(confidence_match.group(1)) if confidence_match else 0.8
            
            # Extract explanation
            explanation_pattern = r'Explanation:\s*(.*?)(?=\n\n|\Z)'
            explanation_match = re.search(explanation_pattern, response, re.DOTALL | re.IGNORECASE)
            explanation = explanation_match.group(1).strip() if explanation_match else response
            
            # Clean up SQL query
            sql_query = self._clean_generated_sql(sql_query)
            
            return sql_query, confidence, explanation
            
        except Exception as e:
            logger.error(f"Failed to parse Claude response: {e}")
            return "", 0.0, response
    
    def _clean_generated_sql(self, sql: str) -> str:
        """Clean up generated SQL query.
        
        Args:
            sql: Raw SQL query
            
        Returns:
            Cleaned SQL query
        """
        if not sql:
            return ""
        
        # Remove any remaining markdown
        sql = sql.replace('```sql', '').replace('```', '')
        
        # Remove extra whitespace
        sql = ' '.join(sql.split())
        
        # Ensure it ends with semicolon
        sql = sql.rstrip(';') + ';'
        
        return sql
    
    def _format_similar_queries(self, similar_docs: List[Dict]) -> List[Dict]:
        """Format similar queries for citations.
        
        Args:
            similar_docs: Similar documents from search
            
        Returns:
            Formatted similar queries
        """
        formatted = []
        
        for doc in similar_docs:
            source = doc['source']
            formatted_query = {
                'sql_query': source.get('sql_query', ''),
                'similarity_score': doc['score'],
                'notebook_path': source.get('notebook_path', ''),
                'context_before': source.get('context_before', ''),
                'context_after': source.get('context_after', ''),
                'tables_used': source.get('tables_used', []),
                'query_type': source.get('query_type', '')
            }
            formatted.append(formatted_query)
        
        return formatted
    
    def _create_error_result(self, error_message: str, start_time: float) -> SQLResult:
        """Create an error result.
        
        Args:
            error_message: Error message
            start_time: Start time for execution time calculation
            
        Returns:
            Error SQL result
        """
        import time
        execution_time = time.time() - start_time
        
        return SQLResult(
            sql_query="",
            confidence=0.0,
            explanation=error_message,
            similar_queries=[],
            schema_context="",
            execution_time=execution_time
        )
    
    def validate_sql(self, sql_query: str) -> Tuple[bool, str]:
        """Validate generated SQL query.
        
        Args:
            sql_query: SQL query to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            import sqlparse
            
            # Basic SQL parsing validation
            parsed = sqlparse.parse(sql_query)
            if not parsed:
                return False, "Invalid SQL syntax"
            
            # Check for dangerous operations
            dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'INSERT', 'UPDATE']
            sql_upper = sql_query.upper()
            
            for keyword in dangerous_keywords:
                if keyword in sql_upper:
                    return False, f"Query contains potentially dangerous operation: {keyword}"
            
            return True, "Valid SQL query"
            
        except Exception as e:
            return False, f"SQL validation error: {str(e)}"