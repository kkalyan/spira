# Setup Guide

This guide walks you through setting up the Text2SQL RAG system from scratch.

## Prerequisites

### 1. Python Environment

- Python 3.9 or higher
- pip or conda for package management

```bash
# Check Python version
python --version

# Create virtual environment (recommended)
python -m venv text2sql-env
source text2sql-env/bin/activate  # On Windows: text2sql-env\Scripts\activate
```

### 2. AWS Account Setup

You'll need access to the following AWS services:

#### AWS Bedrock
- Enable access to Claude models (Haiku, Sonnet)
- Enable access to Titan Embeddings
- Ensure your region supports these models

```bash
# Check Bedrock model access
aws bedrock list-foundation-models --region us-east-1
```

#### AWS OpenSearch
- Create an OpenSearch cluster
- Configure IAM permissions for access
- Note the cluster endpoint

#### AWS Glue Catalog
- Ensure your tables are cataloged in Glue
- Set up cross-account access if needed
- Note the account ID and region

### 3. AWS Credentials

Configure AWS credentials using one of these methods:

```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1

# Option 3: IAM roles (for EC2/containers)
# No additional setup needed
```

## Installation

### From Source (Recommended for development)

```bash
# Clone the repository
git clone https://github.com/yourusername/text2sql-rag.git
cd text2sql-rag

# Install in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

### From PyPI (when available)

```bash
pip install text2sql-rag
```

## AWS Service Setup

### 1. OpenSearch Cluster

Create an OpenSearch cluster with these minimum specifications:

```yaml
# Minimum configuration
Instance Type: t3.small.search
Instance Count: 1
Storage: 20 GB EBS
Version: OpenSearch 2.3+

# Production configuration
Instance Type: m6g.large.search
Instance Count: 3
Storage: 100 GB EBS
Multi-AZ: Enabled
```

#### IAM Policy for OpenSearch

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "es:*"
            ],
            "Resource": "arn:aws:es:REGION:ACCOUNT:domain/DOMAIN-NAME/*"
        }
    ]
}
```

### 2. Bedrock Permissions

#### IAM Policy for Bedrock

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:ListFoundationModels"
            ],
            "Resource": [
                "arn:aws:bedrock:*::foundation-model/anthropic.claude*",
                "arn:aws:bedrock:*::foundation-model/amazon.titan*"
            ]
        }
    ]
}
```

### 3. Glue Catalog Permissions

#### IAM Policy for Glue

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "glue:GetDatabase",
                "glue:GetDatabases",
                "glue:GetTable",
                "glue:GetTables"
            ],
            "Resource": "*"
        }
    ]
}
```

#### Cross-Account Access (if needed)

If your Glue catalog is in a different AWS account:

1. **In the target account**, create a role with Glue permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::YOUR-ACCOUNT:root"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
```

2. **In your account**, add permission to assume the role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "sts:AssumeRole",
            "Resource": "arn:aws:iam::TARGET-ACCOUNT:role/CrossAccountGlueRole"
        }
    ]
}
```

### 4. S3 Permissions (if using S3 for notebooks)

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-notebook-bucket",
                "arn:aws:s3:::your-notebook-bucket/*"
            ]
        }
    ]
}
```

## Configuration

### 1. Create Configuration File

Create a `config.yaml` file:

```yaml
# Notebook source
notebook_source: "s3://your-bucket/notebooks/"  # or "/local/path"

# Glue Catalog
glue_catalog:
  account_id: "123456789012"
  region: "us-east-1"
  databases: ["sales_db", "customer_db"]
  # For cross-account access:
  # cross_account_role_arn: "arn:aws:iam::TARGET-ACCOUNT:role/CrossAccountRole"

# OpenSearch
opensearch:
  endpoint: "your-domain.us-east-1.es.amazonaws.com"
  region: "us-east-1"
  index_name: "text2sql-knowledge"

# Models
models:
  offline_model: "anthropic.claude-3-haiku-20240307-v1:0"
  online_model: "anthropic.claude-3-5-sonnet-20241022-v2:0"
  embedding_model: "amazon.titan-embed-text-v2:0"
  region: "us-east-1"
```

### 2. Test Configuration

```bash
# Test AWS connectivity
python -c "
from text2sql_rag.config import Config
from text2sql_rag.glue_catalog import GlueCatalogExtractor
from text2sql_rag.opensearch_client import OpenSearchClient

config = Config.from_yaml('config.yaml')
print('✅ Configuration loaded')

# Test Glue access
glue = GlueCatalogExtractor(config.glue_catalog)
dbs = glue.get_databases()
print(f'✅ Glue: Found {len(dbs)} databases')

# Test OpenSearch
os_client = OpenSearchClient(config.opensearch)
print('✅ OpenSearch: Connected')
"
```

## Build Knowledge Base

### 1. Initial Build

```bash
# Build the knowledge base
text2sql-build --config config.yaml --verbose

# Expected output:
# Loading configuration from config.yaml
# Configuration loaded successfully
# Initializing knowledge base builder...
# Starting knowledge base build process...
# Creating OpenSearch index...
# Extracting Glue catalog metadata...
# Parsing notebooks and extracting SQL...
# Analyzing SQL patterns and business logic...
# Generating embeddings for knowledge base documents...
# Indexing documents in OpenSearch...
# Knowledge base build completed successfully!
```

### 2. Verify Build

```bash
# Check knowledge base statistics
python -c "
from text2sql_rag.config import Config
from text2sql_rag.knowledge_base import KnowledgeBaseBuilder

config = Config.from_yaml('config.yaml')
kb = KnowledgeBaseBuilder(config)
stats = kb.get_knowledge_base_stats()

print('Knowledge Base Statistics:')
print(f'Documents: {stats.get(\"document_count\", 0)}')
print(f'Index size: {stats.get(\"index_size\", 0) / (1024*1024):.1f} MB')
print(f'Status: {stats.get(\"status\", \"Unknown\")}')
"
```

## Test the System

### 1. Start the Web App

```bash
# Start Streamlit app
text2sql-app

# Or specify custom port
text2sql-app --port 8080
```

### 2. Test a Query

```bash
# Interactive CLI
python -c "
from text2sql_rag.config import Config
from text2sql_rag.query_engine import QueryEngine

config = Config.from_yaml('config.yaml')
engine = QueryEngine(config)

result = engine.generate_sql('Show me total sales by month')
print(f'SQL: {result.sql_query}')
print(f'Confidence: {result.confidence}')
"
```

## Troubleshooting

### Common Issues

1. **Bedrock Access Denied**
   ```bash
   # Check model access
   aws bedrock list-foundation-models --region us-east-1
   
   # Enable model access in AWS Console
   # Bedrock > Model access > Request model access
   ```

2. **OpenSearch Connection Failed**
   ```bash
   # Check cluster health
   curl -X GET "https://your-domain.us-east-1.es.amazonaws.com/_cluster/health"
   
   # Verify IAM permissions
   # Check security groups and VPC settings
   ```

3. **Glue Catalog Access Denied**
   ```bash
   # Test Glue access
   aws glue get-databases --region us-east-1
   
   # Check cross-account role if applicable
   aws sts assume-role --role-arn arn:aws:iam::ACCOUNT:role/ROLE --role-session-name test
   ```

4. **No Notebooks Found**
   ```bash
   # For S3: Check bucket permissions
   aws s3 ls s3://your-bucket/notebooks/
   
   # For local: Check path exists
   ls /path/to/notebooks/
   ```

### Performance Issues

1. **Slow Knowledge Base Build**
   - Reduce `max_workers` in config
   - Process notebooks in smaller batches
   - Use larger OpenSearch instance

2. **Slow Query Generation**
   - Use faster embedding model (Titan v2)
   - Reduce `max_similar` queries
   - Optimize OpenSearch index settings

### Getting Help

1. **Enable Debug Logging**
   ```bash
   text2sql-build --config config.yaml --verbose
   ```

2. **Check AWS CloudTrail**
   - Review API calls for permissions issues
   - Check for rate limiting

3. **Monitor OpenSearch**
   - Check cluster performance metrics
   - Review slow query logs

## Next Steps

1. **Optimize Performance**
   - Tune OpenSearch index settings
   - Adjust embedding batch sizes
   - Configure model parameters

2. **Add Monitoring**
   - Set up CloudWatch dashboards
   - Configure alerts for errors
   - Monitor usage and costs

3. **Scale for Production**
   - Use larger OpenSearch cluster
   - Implement load balancing
   - Add backup and recovery

4. **Customize for Your Domain**
   - Add domain-specific SQL patterns
   - Tune similarity thresholds
   - Create custom prompt templates