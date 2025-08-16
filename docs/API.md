# API Documentation

This document provides detailed API documentation for the Text2SQL RAG system components.

## Core Classes

### Config

Configuration management for the Text2SQL RAG system.

```python
from text2sql_rag.config import Config

# Load from YAML file
config = Config.from_yaml("config.yaml")

# Load from environment variables
config = Config.from_env()

# Access configuration
print(config.notebook_source)
print(config.glue_catalog.account_id)
print(config.opensearch.endpoint)
```

#### Configuration Parameters

**notebook_source** (str): Path to notebooks (S3 or local)
- S3 format: `"s3://bucket/path/"`
- Local format: `"/absolute/path/to/notebooks"`

**glue_catalog** (GlueCatalogConfig):
- `account_id` (str): AWS account ID
- `region` (str): AWS region (default: "us-east-1")
- `databases` (List[str], optional): List of databases to include
- `tables` (List[str], optional): List of specific tables ("db.table")
- `cross_account_role_arn` (str, optional): Cross-account role ARN

**opensearch** (OpenSearchConfig):
- `endpoint` (str): OpenSearch cluster endpoint
- `region` (str): AWS region (default: "us-east-1")
- `index_name` (str): Index name (default: "text2sql-knowledge")
- `use_ssl` (bool): Use SSL (default: True)
- `verify_certs` (bool): Verify certificates (default: True)

**models** (ModelsConfig):
- `offline_model` (str): Model for parsing/analysis
- `online_model` (str): Model for SQL generation
- `embedding_model` (str): Model for embeddings
- `region` (str): Bedrock region

### KnowledgeBaseBuilder

Builds and manages the RAG knowledge base.

```python
from text2sql_rag.knowledge_base import KnowledgeBaseBuilder
from text2sql_rag.config import Config

config = Config.from_yaml("config.yaml")
kb_builder = KnowledgeBaseBuilder(config)

# Build knowledge base
success = kb_builder.build_knowledge_base()

# Force rebuild
success = kb_builder.build_knowledge_base(force_rebuild=True)

# Get statistics
stats = kb_builder.get_knowledge_base_stats()
print(f"Documents: {stats['document_count']}")
print(f"Index size: {stats['index_size']} bytes")
```

#### Methods

**build_knowledge_base(force_rebuild: bool = False) -> bool**

Builds the complete knowledge base from notebooks and Glue catalog.

- `force_rebuild`: Whether to rebuild from scratch
- Returns: True if successful

**get_knowledge_base_stats() -> Dict**

Returns statistics about the knowledge base.

- Returns: Dictionary with stats including document count, index size, etc.

### QueryEngine

Converts natural language to SQL using RAG.

```python
from text2sql_rag.query_engine import QueryEngine
from text2sql_rag.config import Config

config = Config.from_yaml("config.yaml")
engine = QueryEngine(config)

# Generate SQL
result = engine.generate_sql(
    user_question="Show me total revenue by month",
    max_similar=5,
    hybrid_search=True
)

print(f"SQL: {result.sql_query}")
print(f"Confidence: {result.confidence}")
print(f"Similar queries: {len(result.similar_queries)}")
```

#### Methods

**generate_sql(user_question: str, max_similar: int = 5, hybrid_search: bool = True) -> SQLResult**

Generates SQL from natural language question.

- `user_question`: Natural language question
- `max_similar`: Maximum similar queries to retrieve
- `hybrid_search`: Use both text and vector search
- Returns: SQLResult object

**validate_sql(sql_query: str) -> Tuple[bool, str]**

Validates generated SQL query.

- `sql_query`: SQL query to validate
- Returns: (is_valid, error_message)

### SQLResult

Result from text-to-SQL generation.

```python
# SQLResult attributes
result.sql_query          # Generated SQL query (str)
result.confidence         # Confidence score 0-1 (float)
result.explanation        # Explanation of the query (str)
result.similar_queries    # List of similar queries with citations
result.schema_context     # Schema context used (str)
result.execution_time     # Generation time in seconds (float)
```

## Notebook Processing

### NotebookParser

Parses Jupyter and Zeppelin notebooks to extract SQL queries.

```python
from text2sql_rag.notebook_parser import NotebookParser

parser = NotebookParser("s3://bucket/notebooks/")

# Discover notebooks
notebook_paths = parser.discover_notebooks()

# Parse single notebook
parsed = parser.parse_notebook("path/to/notebook.ipynb")

# Parse all notebooks in parallel
parsed_notebooks = parser.parse_notebooks_parallel(max_workers=10)

# Extract SQL with context
sql_extracts = parser.extract_sql_with_context(parsed_notebooks)
```

#### Methods

**discover_notebooks() -> List[str]**

Discovers notebook files in the configured source.

- Returns: List of notebook file paths

**parse_notebook(notebook_path: str) -> Optional[ParsedNotebook]**

Parses a single notebook file.

- `notebook_path`: Path to notebook file
- Returns: ParsedNotebook object or None

**parse_notebooks_parallel(max_workers: int = 10) -> List[ParsedNotebook]**

Parses notebooks in parallel.

- `max_workers`: Maximum parallel workers
- Returns: List of ParsedNotebook objects

### ParsedNotebook

Represents a parsed notebook with extracted content.

```python
# ParsedNotebook attributes
notebook.notebook_path    # Path to source notebook
notebook.notebook_type    # "jupyter" or "zeppelin"
notebook.cells           # List of all cells
notebook.sql_cells       # List of cells containing SQL
notebook.markdown_cells  # List of markdown cells
notebook.metadata        # Notebook metadata
```

## SQL Analysis

### SQLAnalyzer

Analyzes SQL queries to extract patterns and business logic.

```python
from text2sql_rag.sql_analyzer import SQLAnalyzer

analyzer = SQLAnalyzer()

# Analyze single query
pattern = analyzer.analyze_query(sql_query, context="")

# Analyze business patterns across queries
business_patterns = analyzer.analyze_business_patterns(sql_extracts)

# Format patterns for LLM context
context = analyzer.format_patterns_for_context(business_patterns)
```

#### Methods

**analyze_query(sql_query: str, context: str = "") -> SQLPattern**

Analyzes a single SQL query to extract patterns.

- `sql_query`: SQL query string
- `context`: Additional context about the query
- Returns: SQLPattern object

**analyze_business_patterns(sql_extracts: List[Dict]) -> BusinessPattern**

Analyzes business patterns across multiple queries.

- `sql_extracts`: List of SQL extracts with context
- Returns: BusinessPattern object

### SQLPattern

Represents extracted patterns from a SQL query.

```python
# SQLPattern attributes
pattern.tables           # Set of table names used
pattern.columns          # Set of column names used
pattern.joins            # List of (left_table, right_table, join_type)
pattern.filters          # List of WHERE conditions
pattern.aggregations     # Set of aggregation functions (SUM, COUNT, etc.)
pattern.functions        # Set of functions used
pattern.subqueries       # List of subqueries
pattern.cte_names        # Set of CTE names
pattern.query_type       # Query type (SELECT, INSERT, etc.)
```

## Glue Catalog Integration

### GlueCatalogExtractor

Extracts metadata from AWS Glue Catalog.

```python
from text2sql_rag.glue_catalog import GlueCatalogExtractor
from text2sql_rag.config import GlueCatalogConfig

config = GlueCatalogConfig(
    account_id="123456789012",
    region="us-east-1",
    databases=["sales_db"]
)

extractor = GlueCatalogExtractor(config)

# Get databases
databases = extractor.get_databases()

# Get tables for database
tables = extractor.get_tables_for_database("sales_db")

# Get table metadata
metadata = extractor.get_table_metadata("sales_db", "transactions")

# Extract metadata for all configured tables
all_metadata = extractor.extract_metadata(max_workers=10)
```

#### Methods

**get_databases() -> List[str]**

Gets list of databases from Glue catalog.

- Returns: List of database names

**get_tables_for_database(database_name: str) -> List[str]**

Gets list of tables for a specific database.

- `database_name`: Name of the database
- Returns: List of table names

**get_table_metadata(database_name: str, table_name: str) -> Optional[TableMetadata]**

Gets detailed metadata for a specific table.

- `database_name`: Name of the database
- `table_name`: Name of the table
- Returns: TableMetadata object or None

### TableMetadata

Represents metadata for a Glue table.

```python
# TableMetadata attributes
table.database           # Database name
table.name              # Table name
table.description       # Table description
table.columns           # List of ColumnMetadata objects
table.partition_keys    # List of partition key columns
table.location          # S3 location
table.input_format      # Input format
table.output_format     # Output format
table.table_type        # Table type
table.parameters        # Table parameters dict
```

## OpenSearch Integration

### OpenSearchClient

Client for OpenSearch operations with AWS integration.

```python
from text2sql_rag.opensearch_client import OpenSearchClient
from text2sql_rag.config import OpenSearchConfig

config = OpenSearchConfig(
    endpoint="domain.us-east-1.es.amazonaws.com",
    region="us-east-1"
)

client = OpenSearchClient(config)

# Create index
success = client.create_index(force_recreate=False)

# Index document
success = client.index_document("doc_id", document_dict)

# Bulk index documents
indexed_count = client.bulk_index_documents(documents_list)

# Search similar documents
results = client.search_similar(query_embedding, size=10)

# Hybrid search
results = client.hybrid_search(query_text, query_embedding, size=10)
```

#### Methods

**create_index(force_recreate: bool = False) -> bool**

Creates the knowledge base index.

- `force_recreate`: Whether to delete existing index
- Returns: True if successful

**search_similar(query_embedding: List[float], size: int = 10) -> List[Dict]**

Searches for similar documents using vector similarity.

- `query_embedding`: Query vector
- `size`: Number of results to return
- Returns: List of similar documents with scores

**hybrid_search(query_text: str, query_embedding: List[float], size: int = 10) -> List[Dict]**

Performs hybrid search combining text and vector similarity.

- `query_text`: Text query for keyword search
- `query_embedding`: Query vector for semantic search
- `size`: Number of results to return
- Returns: List of search results

## Embeddings

### BedrockEmbeddingClient

Client for generating embeddings using AWS Bedrock.

```python
from text2sql_rag.embeddings import BedrockEmbeddingClient
from text2sql_rag.config import ModelsConfig

config = ModelsConfig(
    embedding_model="amazon.titan-embed-text-v2:0",
    region="us-east-1"
)

client = BedrockEmbeddingClient(config)

# Generate single embedding
embedding = client.generate_embedding("text to embed")

# Generate embeddings in batch
embeddings = client.generate_embeddings_batch(texts_list, max_workers=5)
```

#### Methods

**generate_embedding(text: str) -> Optional[List[float]]**

Generates embedding for a single text.

- `text`: Input text to embed
- Returns: Embedding vector or None if failed

**generate_embeddings_batch(texts: List[str], max_workers: int = 5) -> List[Optional[List[float]]]**

Generates embeddings for multiple texts in parallel.

- `texts`: List of texts to embed
- `max_workers`: Maximum parallel workers
- Returns: List of embeddings (same order as input)

## Error Handling

### Common Exceptions

**ValidationError** (from pydantic)
- Raised when configuration validation fails
- Check configuration parameters and types

**ClientError** (from botocore)
- Raised for AWS API errors
- Check permissions, regions, and service availability

**ConnectionError** (from opensearchpy)
- Raised for OpenSearch connection issues
- Check endpoint, security groups, and IAM permissions

### Example Error Handling

```python
from botocore.exceptions import ClientError
from pydantic import ValidationError

try:
    config = Config.from_yaml("config.yaml")
    kb_builder = KnowledgeBaseBuilder(config)
    success = kb_builder.build_knowledge_base()
    
except ValidationError as e:
    print(f"Configuration error: {e}")
    
except ClientError as e:
    error_code = e.response['Error']['Code']
    if error_code == 'AccessDenied':
        print("AWS permissions error")
    elif error_code == 'ThrottlingException':
        print("Rate limiting - try again later")
    else:
        print(f"AWS error: {e}")
        
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Best Practices

### Configuration

1. **Use environment-specific configs**
   ```python
   # Development
   config = Config.from_yaml("config-dev.yaml")
   
   # Production
   config = Config.from_yaml("config-prod.yaml")
   ```

2. **Validate configuration early**
   ```python
   try:
       config = Config.from_yaml("config.yaml")
       print("✅ Configuration valid")
   except ValidationError as e:
       print(f"❌ Configuration error: {e}")
       exit(1)
   ```

### Performance

1. **Use appropriate batch sizes**
   ```python
   # For small datasets
   config.processing.batch_size = 50
   config.processing.max_workers = 5
   
   # For large datasets
   config.processing.batch_size = 200
   config.processing.max_workers = 20
   ```

2. **Monitor API rate limits**
   ```python
   # The system includes automatic rate limiting
   # Adjust if you encounter throttling
   embedding_client.requests_per_second = 5  # Reduce if needed
   ```

### Error Recovery

1. **Implement retry logic**
   ```python
   max_retries = 3
   for attempt in range(max_retries):
       try:
           result = engine.generate_sql(question)
           break
       except Exception as e:
           if attempt == max_retries - 1:
               raise
           time.sleep(2 ** attempt)  # Exponential backoff
   ```

2. **Handle partial failures gracefully**
   ```python
   # The system continues processing even if some notebooks fail
   # Check logs for details on failed items
   ```