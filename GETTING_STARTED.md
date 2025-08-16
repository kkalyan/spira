# Getting Started with Spira

Welcome! This guide will get you up and running with Spira in 15 minutes.

## Quick Overview

Spira converts natural language questions into SQL queries by learning from your existing notebooks and database schemas. It uses:

- 🧠 **AWS Bedrock Claude 4** for intelligent SQL generation
- 📚 **Your Jupyter/Zeppelin notebooks** as knowledge base (11K+ notebooks supported)
- 🗃️ **AWS Glue Catalog** for 100K+ table metadata
- 🔍 **AWS OpenSearch** for fast similarity search
- 📊 **Streamlit** for an intuitive web interface

## 5-Minute Setup

### 1. Install

```bash
pip install -e .
```

### 2. Configure

Create `config.yaml`:

```yaml
notebook_source: "s3://my-bucket/notebooks/"
glue_catalog:
  account_id: "123456789012"
  region: "us-east-1"
  databases: ["sales_db", "customer_db"]
opensearch:
  endpoint: "my-domain.us-east-1.es.amazonaws.com"
  region: "us-east-1"
models:
  region: "us-east-1"
```

### 3. Build Knowledge Base

```bash
spira-build --config config.yaml
```

### 4. Start Querying

```bash
spira-app
```

Open http://localhost:8501 and ask: *"Show me total revenue by month for the last year"*

## What You Get

### Intelligent SQL Generation
```
Question: "Which customers have the highest lifetime value?"

Generated SQL:
SELECT 
    c.customer_id,
    c.customer_name,
    SUM(o.total_amount) as lifetime_value
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 2 YEAR)
GROUP BY c.customer_id, c.customer_name
ORDER BY lifetime_value DESC
LIMIT 10;

Confidence: 0.94
```

### Smart Citations
The system shows you similar queries from your notebooks that inspired the generated SQL, with similarity scores and source notebooks.

### Schema Awareness
Automatically uses your actual table schemas from Glue Catalog, ensuring generated queries reference real tables and columns.

## System Architecture

```
Your Question → Embedding → Vector Search → Similar Queries + Schema Context
                                    ↓
Claude 4 ← Context (Patterns + Business Logic + Table Schemas) ← Glue Catalog
    ↓
Generated SQL + Confidence + Citations
```

## Key Features

### 🚀 Fast & Scalable
- Parallel processing of 10K+ notebooks
- Optimized vector search with OpenSearch
- Rate-limited API calls with automatic retries

### 🎯 Domain-Aware
- Learns your business logic from existing SQL
- Understands table relationships and common patterns
- Extracts business terminology and calculations

### 📋 Production Ready
- Comprehensive error handling and logging
- Type hints and validation throughout
- Unit tests for all components
- Configurable for different environments

### 🔒 Secure
- Uses AWS IAM for all service access
- No storage of sensitive data
- Validates generated SQL for safety

## Examples

### Business Intelligence
```
"What's our monthly recurring revenue trend?"
"Show me customer churn rate by segment"
"Which products have the best profit margins?"
```

### Data Analysis
```
"Find anomalies in daily sales patterns"
"Compare this quarter's performance to last year"
"Show me the correlation between marketing spend and revenue"
```

### Operational Queries
```
"How many orders are pending shipment?"
"Which warehouses have low inventory?"
"Show me response time trends for customer support"
```

## Advanced Configuration

### Multiple Data Sources
```yaml
glue_catalog:
  account_id: "123456789012"
  databases: ["sales", "marketing", "product"]
  # Cross-account access
  cross_account_role_arn: "arn:aws:iam::OTHER:role/GlueAccess"
```

### Performance Tuning
```yaml
processing:
  max_workers: 20           # Parallel processing
  batch_size: 200          # Bulk operations
  similarity_threshold: 0.8 # Citation quality
```

### Model Selection
```yaml
models:
  offline_model: "anthropic.claude-3-haiku-20240307-v1:0"      # Fast parsing
  online_model: "anthropic.claude-3-5-sonnet-20241022-v2:0"   # Best generation
  embedding_model: "amazon.titan-embed-text-v2:0"             # Fast embeddings
```

## Deployment Options

### Local Development
```bash
# Use local notebooks and development OpenSearch
notebook_source: "/Users/me/notebooks"
opensearch:
  endpoint: "localhost:9200"
  use_ssl: false
```

### Production
```bash
# Use S3 notebooks and production OpenSearch cluster
notebook_source: "s3://prod-notebooks/"
opensearch:
  endpoint: "prod-domain.us-east-1.es.amazonaws.com"
processing:
  max_workers: 50
```

### Multi-Environment
```bash
# Development
text2sql-build --config config-dev.yaml

# Staging
text2sql-build --config config-staging.yaml

# Production
text2sql-build --config config-prod.yaml
```

## Integration Examples

### Python API
```python
from spira import Config, QueryEngine

config = Config.from_yaml("config.yaml")
engine = QueryEngine(config)

result = engine.generate_sql("Show me top customers")
print(result.sql_query)
```

### Jupyter Notebook
```python
%load_ext spira.jupyter_magic

%spira Show me revenue by product category
# Automatically generates and executes SQL
```

### REST API (Custom)
```python
from flask import Flask, request, jsonify
from spira import Config, QueryEngine

app = Flask(__name__)
engine = QueryEngine(Config.from_yaml("config.yaml"))

@app.route('/generate-sql', methods=['POST'])
def generate_sql():
    question = request.json['question']
    result = engine.generate_sql(question)
    return jsonify({
        'sql': result.sql_query,
        'confidence': result.confidence,
        'citations': result.similar_queries
    })
```

## Monitoring & Maintenance

### Health Checks
```python
from spira import KnowledgeBaseBuilder

kb = KnowledgeBaseBuilder(config)
stats = kb.get_knowledge_base_stats()

# Monitor key metrics
print(f"Documents: {stats['document_count']}")
print(f"Index health: {stats['status']}")
```

### Performance Monitoring
- Track query generation times
- Monitor OpenSearch cluster performance
- Watch AWS Bedrock usage and costs
- Set up CloudWatch alerts for errors

### Regular Updates
```bash
# Rebuild knowledge base monthly or when notebooks change
spira-build --config config.yaml --force-rebuild

# Incremental updates (when implemented)
spira-update --config config.yaml --changed-notebooks notebooks.json
```

## Troubleshooting

### Common Issues

**No SQL Generated**
- Check if similar patterns exist in your notebooks
- Verify table names exist in Glue Catalog
- Try more specific questions

**Low Confidence Scores**
- Add more diverse SQL examples to notebooks
- Include business context in markdown cells
- Verify schema metadata is complete

**Slow Performance**
- Increase OpenSearch instance size
- Reduce similarity threshold
- Use faster embedding model

### Debug Mode
```bash
# Enable verbose logging
spira-build --config config.yaml --verbose

# Check specific components
python -c "
from spira.config import Config
config = Config.from_yaml('config.yaml')
print('Config loaded successfully')
"
```

## Next Steps

1. **🔧 Customize**: Adjust configuration for your specific environment
2. **📊 Monitor**: Set up dashboards to track usage and performance  
3. **🚀 Scale**: Move to production with larger OpenSearch cluster
4. **🎯 Optimize**: Fine-tune similarity thresholds and model parameters
5. **🔄 Iterate**: Regularly update knowledge base as notebooks evolve

## Support & Community

- 📖 **Documentation**: `/docs` folder for detailed guides
- 🐛 **Issues**: GitHub Issues for bug reports
- 💬 **Discussions**: GitHub Discussions for questions
- 📧 **Contact**: Maintainers for enterprise support

---

**Ready to transform your data querying experience with Spira? Let's get started! 🌟**