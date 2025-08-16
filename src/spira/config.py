"""Configuration management for Text2SQL RAG system."""

import os
from pathlib import Path
from typing import Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, validator


class GlueCatalogConfig(BaseModel):
    """Configuration for AWS Glue Catalog access."""
    
    account_id: str = Field(..., description="AWS account ID containing the Glue catalog")
    region: str = Field(default="us-east-1", description="AWS region")
    databases: Optional[List[str]] = Field(default=None, description="List of databases to include")
    tables: Optional[List[str]] = Field(default=None, description="List of specific tables (format: db.table)")
    cross_account_role_arn: Optional[str] = Field(default=None, description="Cross-account role ARN if needed")
    
    @validator('databases', 'tables')
    def at_least_one_source(cls, v, values):
        """Ensure either databases or tables is specified."""
        if not v and not values.get('databases') and not values.get('tables'):
            raise ValueError("Must specify either databases or tables")
        return v


class OpenSearchConfig(BaseModel):
    """Configuration for AWS OpenSearch cluster."""
    
    endpoint: str = Field(..., description="OpenSearch cluster endpoint")
    region: str = Field(default="us-east-1", description="AWS region")
    index_name: str = Field(default="text2sql-knowledge", description="Index name for storing knowledge")
    use_ssl: bool = Field(default=True, description="Use SSL for connections")
    verify_certs: bool = Field(default=True, description="Verify SSL certificates")


class ModelsConfig(BaseModel):
    """Configuration for AWS Bedrock models."""
    
    offline_model: str = Field(
        default="anthropic.claude-3-haiku-20240307-v1:0",
        description="Model for offline processing (parsing, analysis)"
    )
    online_model: str = Field(
        default="anthropic.claude-3-5-sonnet-20241022-v2:0",
        description="Model for online SQL generation"
    )
    embedding_model: str = Field(
        default="amazon.titan-embed-text-v2:0",
        description="Model for generating embeddings"
    )
    region: str = Field(default="us-east-1", description="AWS region for Bedrock")


class ProcessingConfig(BaseModel):
    """Configuration for data processing."""
    
    max_workers: int = Field(default=10, description="Maximum number of parallel workers")
    batch_size: int = Field(default=100, description="Batch size for processing")
    chunk_size: int = Field(default=1000, description="Text chunk size for embeddings")
    similarity_threshold: float = Field(default=0.7, description="Similarity threshold for citations")


class Config(BaseModel):
    """Main configuration class for Text2SQL RAG system."""
    
    notebook_source: str = Field(..., description="S3 path or local folder containing notebooks")
    glue_catalog: GlueCatalogConfig
    opensearch: OpenSearchConfig
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    
    @validator('notebook_source')
    def validate_notebook_source(cls, v):
        """Validate notebook source path."""
        if v.startswith('s3://'):
            return v
        else:
            path = Path(v)
            if not path.exists():
                raise ValueError(f"Local path does not exist: {v}")
            return str(path.absolute())
    
    @classmethod
    def from_yaml(cls, config_path: Union[str, Path]) -> "Config":
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        return cls(**config_data)
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        config_data = {
            "notebook_source": os.getenv("NOTEBOOK_SOURCE", ""),
            "glue_catalog": {
                "account_id": os.getenv("GLUE_ACCOUNT_ID", ""),
                "region": os.getenv("GLUE_REGION", "us-east-1"),
                "databases": os.getenv("GLUE_DATABASES", "").split(",") if os.getenv("GLUE_DATABASES") else None,
                "tables": os.getenv("GLUE_TABLES", "").split(",") if os.getenv("GLUE_TABLES") else None,
                "cross_account_role_arn": os.getenv("GLUE_CROSS_ACCOUNT_ROLE_ARN"),
            },
            "opensearch": {
                "endpoint": os.getenv("OPENSEARCH_ENDPOINT", ""),
                "region": os.getenv("OPENSEARCH_REGION", "us-east-1"),
                "index_name": os.getenv("OPENSEARCH_INDEX", "text2sql-knowledge"),
            },
            "models": {
                "offline_model": os.getenv("OFFLINE_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"),
                "online_model": os.getenv("ONLINE_MODEL", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
                "embedding_model": os.getenv("EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0"),
                "region": os.getenv("BEDROCK_REGION", "us-east-1"),
            }
        }
        return cls(**config_data)
    
    def to_yaml(self, output_path: Union[str, Path]) -> None:
        """Save configuration to YAML file."""
        with open(output_path, 'w') as f:
            yaml.dump(self.dict(), f, default_flow_style=False, indent=2)