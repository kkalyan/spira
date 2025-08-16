"""Knowledge base builder for Text2SQL RAG system."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from .config import Config
from .embeddings import BedrockEmbeddingClient, QueryEmbeddingPipeline
from .glue_catalog import GlueCatalogExtractor
from .notebook_parser import NotebookParser
from .opensearch_client import OpenSearchClient
from .sql_analyzer import SQLAnalyzer

logger = logging.getLogger(__name__)


class KnowledgeBaseBuilder:
    """Builds and manages the RAG knowledge base."""
    
    def __init__(self, config: Config):
        """Initialize the knowledge base builder.
        
        Args:
            config: System configuration
        """
        self.config = config
        
        # Initialize components
        self.glue_extractor = GlueCatalogExtractor(config.glue_catalog)
        self.notebook_parser = NotebookParser(config.notebook_source)
        self.sql_analyzer = SQLAnalyzer()
        self.opensearch_client = OpenSearchClient(config.opensearch)
        self.embedding_client = BedrockEmbeddingClient(config.models)
        self.embedding_pipeline = QueryEmbeddingPipeline(self.embedding_client)
        
        logger.info("Knowledge base builder initialized")
    
    def build_knowledge_base(self, force_rebuild: bool = False) -> bool:
        """Build the complete knowledge base.
        
        Args:
            force_rebuild: Whether to rebuild from scratch
            
        Returns:
            True if build was successful
        """
        try:
            logger.info("Starting knowledge base build process")
            
            # Step 1: Create OpenSearch index
            logger.info("Creating OpenSearch index...")
            if not self.opensearch_client.create_index(force_recreate=force_rebuild):
                logger.error("Failed to create OpenSearch index")
                return False
            
            # Step 2: Extract Glue catalog metadata
            logger.info("Extracting Glue catalog metadata...")
            schema_metadata = self.glue_extractor.extract_metadata(
                max_workers=self.config.processing.max_workers
            )
            
            if not schema_metadata:
                logger.warning("No schema metadata extracted from Glue catalog")
            else:
                logger.info(f"Extracted metadata for {len(schema_metadata)} tables")
            
            # Step 3: Parse notebooks and extract SQL
            logger.info("Parsing notebooks and extracting SQL...")
            parsed_notebooks = self.notebook_parser.parse_notebooks_parallel(
                max_workers=self.config.processing.max_workers
            )
            
            if not parsed_notebooks:
                logger.error("No notebooks with SQL content found")
                return False
            
            # Step 4: Extract SQL with context
            logger.info("Extracting SQL queries with context...")
            sql_extracts = self.notebook_parser.extract_sql_with_context(parsed_notebooks)
            
            if not sql_extracts:
                logger.error("No SQL extracts found")
                return False
            
            # Step 5: Analyze SQL patterns
            logger.info("Analyzing SQL patterns and business logic...")
            sql_patterns = []
            for extract in sql_extracts:
                pattern = self.sql_analyzer.analyze_query(
                    extract['sql_query'], 
                    extract.get('context_before', '')
                )
                sql_patterns.append(pattern)
            
            # Analyze business patterns across all queries
            business_patterns = self.sql_analyzer.analyze_business_patterns(sql_extracts)
            
            # Step 6: Enrich extracts with pattern information
            logger.info("Enriching SQL extracts with pattern analysis...")
            enriched_extracts = self._enrich_sql_extracts(
                sql_extracts, sql_patterns, business_patterns, schema_metadata
            )
            
            # Step 7: Generate embeddings
            logger.info("Generating embeddings for knowledge base documents...")
            documents_with_embeddings = self.embedding_pipeline.generate_embeddings_for_knowledge_base(
                enriched_extracts,
                max_workers=min(self.config.processing.max_workers, 5)  # Rate limiting
            )
            
            if not documents_with_embeddings:
                logger.error("No documents with embeddings generated")
                return False
            
            # Step 8: Index documents in OpenSearch
            logger.info("Indexing documents in OpenSearch...")
            indexed_count = self._index_documents_in_batches(documents_with_embeddings)
            
            if indexed_count == 0:
                logger.error("Failed to index any documents")
                return False
            
            # Step 9: Store metadata and patterns
            logger.info("Storing metadata and patterns...")
            self._store_metadata(schema_metadata, business_patterns)
            
            logger.info(f"Knowledge base build completed successfully!")
            logger.info(f"- Processed {len(parsed_notebooks)} notebooks")
            logger.info(f"- Extracted {len(sql_extracts)} SQL queries")
            logger.info(f"- Indexed {indexed_count} documents")
            logger.info(f"- Schema metadata for {len(schema_metadata)} tables")
            
            return True
            
        except Exception as e:
            logger.error(f"Knowledge base build failed: {e}")
            return False
    
    def _enrich_sql_extracts(self, sql_extracts: List[Dict], sql_patterns: List, 
                            business_patterns, schema_metadata: Dict) -> List[Dict]:
        """Enrich SQL extracts with pattern analysis and schema information.
        
        Args:
            sql_extracts: Original SQL extracts
            sql_patterns: Analyzed SQL patterns
            business_patterns: Business patterns
            schema_metadata: Glue catalog metadata
            
        Returns:
            Enriched SQL extracts
        """
        enriched = []
        
        for extract, pattern in zip(sql_extracts, sql_patterns):
            # Create enriched extract
            enriched_extract = extract.copy()
            
            # Add pattern information
            enriched_extract.update({
                'tables_used': list(pattern.tables),
                'query_type': pattern.query_type,
                'joins': [f"{j[0]}-{j[1]}" for j in pattern.joins],
                'filters': pattern.filters,
                'aggregations': list(pattern.aggregations),
                'functions': list(pattern.functions),
                'cte_names': list(pattern.cte_names),
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Create table pattern description
            table_pattern_parts = []
            if pattern.tables:
                table_pattern_parts.append(f"Tables: {', '.join(pattern.tables)}")
            if pattern.joins:
                join_desc = [f"{j[0]} {j[2]} JOIN {j[1]}" for j in pattern.joins]
                table_pattern_parts.append(f"Joins: {'; '.join(join_desc)}")
            if pattern.aggregations:
                table_pattern_parts.append(f"Aggregations: {', '.join(pattern.aggregations)}")
            
            enriched_extract['table_pattern'] = " | ".join(table_pattern_parts)
            
            # Add relevant schema context
            relevant_schemas = []
            for table_name in pattern.tables:
                # Try to find matching schema metadata
                for schema_key, table_meta in schema_metadata.items():
                    if table_name.lower() in schema_key.lower():
                        relevant_schemas.append(f"{schema_key}: {len(table_meta.columns)} columns")
                        break
            
            if relevant_schemas:
                enriched_extract['schema_context'] = "; ".join(relevant_schemas)
            
            enriched.append(enriched_extract)
        
        return enriched
    
    def _index_documents_in_batches(self, documents: List[Dict]) -> int:
        """Index documents in OpenSearch in batches.
        
        Args:
            documents: Documents to index
            
        Returns:
            Number of successfully indexed documents
        """
        batch_size = self.config.processing.batch_size
        total_indexed = 0
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            logger.debug(f"Indexing batch {i//batch_size + 1}: {len(batch)} documents")
            
            batch_indexed = self.opensearch_client.bulk_index_documents(batch)
            total_indexed += batch_indexed
            
            if batch_indexed < len(batch):
                logger.warning(f"Only {batch_indexed}/{len(batch)} documents indexed in batch")
        
        return total_indexed
    
    def _store_metadata(self, schema_metadata: Dict, business_patterns) -> None:
        """Store metadata and patterns in OpenSearch.
        
        Args:
            schema_metadata: Glue catalog metadata
            business_patterns: Analyzed business patterns
        """
        try:
            # Store schema metadata as a special document
            schema_doc = {
                'id': 'schema_metadata',
                'document_type': 'metadata',
                'content': self.glue_extractor.format_schema_context(schema_metadata),
                'tables': list(schema_metadata.keys()),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Store business patterns
            patterns_doc = {
                'id': 'business_patterns',
                'document_type': 'patterns',
                'content': self.sql_analyzer.format_patterns_for_context(business_patterns),
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Index metadata documents
            self.opensearch_client.index_document('schema_metadata', schema_doc)
            self.opensearch_client.index_document('business_patterns', patterns_doc)
            
            logger.info("Stored metadata and patterns in OpenSearch")
            
        except Exception as e:
            logger.error(f"Failed to store metadata: {e}")
    
    def get_knowledge_base_stats(self) -> Dict:
        """Get statistics about the knowledge base.
        
        Returns:
            Knowledge base statistics
        """
        try:
            stats = self.opensearch_client.get_index_stats()
            
            # Add component-specific stats
            stats.update({
                'notebook_source': self.config.notebook_source,
                'glue_databases': len(self.config.glue_catalog.databases or []),
                'glue_tables': len(self.config.glue_catalog.tables or []),
                'embedding_model': self.config.models.embedding_model,
                'index_name': self.config.opensearch.index_name
            })
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get knowledge base stats: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def rebuild_index(self) -> bool:
        """Rebuild the entire knowledge base index.
        
        Returns:
            True if rebuild was successful
        """
        logger.info("Rebuilding knowledge base index...")
        return self.build_knowledge_base(force_rebuild=True)
    
    def update_knowledge_base(self, new_notebooks: Optional[List[str]] = None) -> bool:
        """Update knowledge base with new or modified notebooks.
        
        Args:
            new_notebooks: List of specific notebook paths to process
            
        Returns:
            True if update was successful
        """
        # This is a simplified incremental update
        # In practice, you'd track modification times and only process changed files
        logger.info("Incremental update not yet implemented. Use rebuild_index() for now.")
        return False