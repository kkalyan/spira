# 🌟 Spira

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Intelligent SQL generation from natural language using RAG and AWS AI services**

Spira transforms how you interact with data by converting natural language questions into precise SQL queries. It learns from your existing Jupyter and Zeppelin notebooks to understand your data patterns, business logic, and domain-specific terminology.

## ✨ Features

- 🧠 **Smart SQL Generation**: Powered by AWS Bedrock Claude 4 for accurate text-to-SQL conversion
- 📚 **Domain Learning**: Learns from 10K+ Jupyter/Zeppelin notebooks to understand your patterns
- 🔍 **Semantic Search**: Uses AWS OpenSearch for fast vector similarity search
- 🗃️ **Schema Integration**: Connects with AWS Glue Catalog for 100K+ table metadata
- 📊 **Smart Citations**: Shows similar queries from your notebooks with similarity scores
- ⚡ **High Performance**: Parallel processing and optimized embeddings
- 🌐 **Beautiful Interface**: Clean Streamlit web app for intuitive querying
- 🛠️ **Developer Tools**: Complete CLI toolkit for building and managing the system

## Architecture

```
[User Question] → [Embedding] → [OpenSearch Vector Search] → [Retrieve Similar Queries + Schema]
                                         ↓
[Claude 4] ← [RAG Context: Similar Queries + Business Patterns + Table Schemas] ← [Glue Catalog]
    ↓
[Generated SQL + Confidence + Citations]
```

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/spira.git
cd spira

# Install Spira
pip install -e .
```

### 2. AWS Setup

Ensure you have:
- AWS credentials configured (`aws configure` or IAM roles)
- Access to AWS Bedrock Claude and Titan models
- An AWS OpenSearch cluster
- AWS Glue Catalog with your table metadata

### 3. Configuration

Create a `config.yaml` file:

```yaml
# Notebook source (S3 or local path)
notebook_source: "s3://my-bucket/notebooks/"  # or "/local/path/"

# AWS Glue Catalog configuration
glue_catalog:
  account_id: "123456789012"
  region: "us-east-1"
  databases: ["sales_db", "customer_db"]  # or specific tables
  # tables: ["sales_db.transactions", "customer_db.profiles"]
  # cross_account_role_arn: "arn:aws:iam::ACCOUNT:role/CrossAccountRole"

# OpenSearch configuration
opensearch:
  endpoint: "my-domain.us-east-1.es.amazonaws.com"
  region: "us-east-1"
  index_name: "text2sql-knowledge"

# Model configuration
models:
  offline_model: "anthropic.claude-3-haiku-20240307-v1:0"      # For parsing
  online_model: "anthropic.claude-3-5-sonnet-20241022-v2:0"    # For generation
  embedding_model: "amazon.titan-embed-text-v2:0"              # For embeddings
  region: "us-east-1"

# Processing configuration (optional)
processing:
  max_workers: 10
  batch_size: 100
  similarity_threshold: 0.7
```

### 4. Build Knowledge Base

```bash
# Build the knowledge base from your notebooks
spira-build --config config.yaml --verbose
```

### 5. Start Querying

```bash
# Launch the web application
spira-app

# Or use the interactive CLI
spira --config config.yaml
```

Open your browser to `http://localhost:8501` and start asking questions!

## Usage Examples

### Web Interface

1. Upload your configuration file
2. Wait for the system to initialize
3. Ask questions like:
   - "Show me total revenue by month for the last year"
   - "Which customers have the highest lifetime value?"
   - "What are the top 10 products by sales volume?"

### CLI Interface

```bash
# Interactive querying
spira --config config.yaml

# Example session:
❓ Enter your question: What are the top selling products?

✅ Generated SQL (Confidence: 0.92):
SELECT 
    product_name,
    SUM(quantity) as total_quantity,
    SUM(revenue) as total_revenue
FROM sales_fact s
JOIN product_dim p ON s.product_id = p.product_id
WHERE s.date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 YEAR)
GROUP BY product_name
ORDER BY total_revenue DESC
LIMIT 10;

💡 Explanation: This query joins sales facts with product dimensions to calculate...
📚 Found 3 similar queries
⏱️  Generation time: 1.2s
```

## Configuration Options

### Notebook Sources

```yaml
# S3 bucket
notebook_source: "s3://my-bucket/notebooks/"

# Local directory  
notebook_source: "/Users/me/notebooks/"

# Specific S3 prefix
notebook_source: "s3://my-bucket/analytics/notebooks/"
```

### Glue Catalog Options

```yaml
glue_catalog:
  account_id: "123456789012"
  region: "us-east-1"
  
  # Option 1: Specify databases
  databases: ["sales", "marketing", "product"]
  
  # Option 2: Specify specific tables
  tables: ["sales.transactions", "sales.customers"]
  
  # Option 3: Cross-account access
  cross_account_role_arn: "arn:aws:iam::OTHER-ACCOUNT:role/GlueAccess"
```

### Model Selection

```yaml
models:
  # Fast model for notebook parsing and analysis
  offline_model: "anthropic.claude-3-haiku-20240307-v1:0"
  
  # Best model for SQL generation
  online_model: "anthropic.claude-3-5-sonnet-20241022-v2:0"  # or claude-4
  
  # Embedding model (choose based on performance needs)
  embedding_model: "amazon.titan-embed-text-v2:0"  # Fast, good quality
  # embedding_model: "cohere.embed-english-v3"     # Alternative
```

## Advanced Usage

### Custom Processing Configuration

```yaml
processing:
  max_workers: 20           # Parallel workers for processing
  batch_size: 200          # Batch size for OpenSearch indexing
  chunk_size: 1500         # Text chunk size for embeddings
  similarity_threshold: 0.8 # Minimum similarity for citations
```

### Environment Variables

You can also configure using environment variables:

```bash
export NOTEBOOK_SOURCE="s3://my-bucket/notebooks/"
export GLUE_ACCOUNT_ID="123456789012"
export OPENSEARCH_ENDPOINT="my-domain.us-east-1.es.amazonaws.com"
export BEDROCK_REGION="us-east-1"
```

## Development

### Setting up Development Environment

```bash
# Clone and install in development mode
git clone https://github.com/yourusername/text2sql-rag.git
cd text2sql-rag
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/text2sql_rag --cov-report=html

# Run specific test file
pytest tests/test_config.py -v
```

### Code Quality

```bash
# Format code
black src/ tests/

# Lint code  
ruff src/ tests/

# Type checking
mypy src/
```

## Architecture Deep Dive

### Components

1. **Configuration Management** (`config.py`)
   - YAML-based configuration with validation
   - Support for environment variables
   - Cross-account AWS access configuration

2. **Notebook Parser** (`notebook_parser.py`)
   - Parallel processing of Jupyter/Zeppelin notebooks
   - SQL extraction with context
   - Support for S3 and local file systems

3. **SQL Analyzer** (`sql_analyzer.py`)
   - Pattern extraction from SQL queries
   - Business logic analysis
   - Table relationship mapping

4. **Glue Catalog Integration** (`glue_catalog.py`)
   - Cross-account metadata extraction
   - Schema context generation
   - Parallel table metadata retrieval

5. **Embedding Pipeline** (`embeddings.py`)
   - AWS Bedrock integration
   - Rate limiting and retry logic
   - Batch processing for efficiency

6. **OpenSearch Client** (`opensearch_client.py`)
   - Vector similarity search
   - Hybrid search (text + semantic)
   - Index management and optimization

7. **Query Engine** (`query_engine.py`)
   - RAG context preparation
   - Claude 4 integration for SQL generation
   - Result validation and formatting

8. **Knowledge Base Builder** (`knowledge_base.py`)
   - End-to-end pipeline orchestration
   - Incremental updates
   - Statistics and monitoring

### Data Flow

1. **Offline Processing**:
   ```
   Notebooks → Parse SQL → Analyze Patterns → Generate Embeddings → Index in OpenSearch
   ```

2. **Online Querying**:
   ```
   User Question → Generate Embedding → Search Similar → Get Schema → Generate SQL
   ```

## Troubleshooting

### Common Issues

**1. AWS Permissions**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Test Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

**2. OpenSearch Connection**
```python
# Test OpenSearch connectivity
from opensearchpy import OpenSearch
client = OpenSearch([{'host': 'your-domain.us-east-1.es.amazonaws.com', 'port': 443}])
print(client.cluster.health())
```

**3. Glue Catalog Access**
```bash
# Test Glue access
aws glue get-databases --region us-east-1
```

### Performance Tuning

**For Large Datasets (100K+ notebooks)**:
- Increase `max_workers` in processing config
- Use larger OpenSearch instance types
- Consider batch processing in smaller chunks
- Monitor AWS API rate limits

**For Faster Queries**:
- Use `amazon.titan-embed-text-v2:0` for embeddings (fastest)
- Enable OpenSearch index caching
- Reduce `similarity_threshold` for fewer results
- Pre-warm frequently used schemas

### Logging

Enable verbose logging for debugging:

```bash
# CLI
text2sql-build --config config.yaml --verbose

# Python
import logging
logging.getLogger('text2sql_rag').setLevel(logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Run code quality checks (`black`, `ruff`, `mypy`)
7. Commit your changes (`git commit -m 'Add amazing feature'`)
8. Push to the branch (`git push origin feature/amazing-feature`)
9. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- AWS Bedrock team for Claude and Titan models
- OpenSearch community for vector search capabilities
- Streamlit team for the excellent web framework
- All contributors who helped test and improve this system

## Support

- 📖 [Documentation](https://github.com/yourusername/text2sql-rag/wiki)
- 🐛 [Issues](https://github.com/yourusername/text2sql-rag/issues)
- 💬 [Discussions](https://github.com/yourusername/text2sql-rag/discussions)

---

**Built with ❤️ for the data community**