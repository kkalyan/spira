"""Tests for configuration management."""

import pytest
from pathlib import Path
from pydantic import ValidationError

from text2sql_rag.config import Config, GlueCatalogConfig, OpenSearchConfig, ModelsConfig


class TestGlueCatalogConfig:
    """Test Glue catalog configuration."""
    
    def test_valid_config_with_databases(self):
        """Test valid configuration with databases."""
        config = GlueCatalogConfig(
            account_id="123456789012",
            region="us-east-1",
            databases=["db1", "db2"]
        )
        assert config.account_id == "123456789012"
        assert config.databases == ["db1", "db2"]
    
    def test_valid_config_with_tables(self):
        """Test valid configuration with specific tables."""
        config = GlueCatalogConfig(
            account_id="123456789012",
            region="us-east-1",
            tables=["db1.table1", "db2.table2"]
        )
        assert config.tables == ["db1.table1", "db2.table2"]
    
    def test_missing_databases_and_tables(self):
        """Test that either databases or tables must be specified."""
        with pytest.raises(ValidationError):
            GlueCatalogConfig(
                account_id="123456789012",
                region="us-east-1"
            )


class TestOpenSearchConfig:
    """Test OpenSearch configuration."""
    
    def test_valid_config(self):
        """Test valid OpenSearch configuration."""
        config = OpenSearchConfig(
            endpoint="test-domain.us-east-1.es.amazonaws.com",
            region="us-east-1"
        )
        assert config.endpoint == "test-domain.us-east-1.es.amazonaws.com"
        assert config.index_name == "text2sql-knowledge"  # default
        assert config.use_ssl is True  # default
    
    def test_custom_settings(self):
        """Test custom OpenSearch settings."""
        config = OpenSearchConfig(
            endpoint="localhost:9200",
            region="us-west-2",
            index_name="custom-index",
            use_ssl=False,
            verify_certs=False
        )
        assert config.use_ssl is False
        assert config.verify_certs is False
        assert config.index_name == "custom-index"


class TestModelsConfig:
    """Test models configuration."""
    
    def test_default_models(self):
        """Test default model configuration."""
        config = ModelsConfig()
        assert "claude-3-haiku" in config.offline_model
        assert "claude-3-5-sonnet" in config.online_model
        assert "titan-embed" in config.embedding_model
        assert config.region == "us-east-1"
    
    def test_custom_models(self):
        """Test custom model configuration."""
        config = ModelsConfig(
            offline_model="custom-offline",
            online_model="custom-online",
            embedding_model="custom-embed",
            region="us-west-2"
        )
        assert config.offline_model == "custom-offline"
        assert config.online_model == "custom-online"
        assert config.embedding_model == "custom-embed"
        assert config.region == "us-west-2"


class TestConfig:
    """Test main configuration class."""
    
    def test_valid_config_local_path(self, tmp_path):
        """Test valid configuration with local path."""
        # Create a temporary directory
        notebook_dir = tmp_path / "notebooks"
        notebook_dir.mkdir()
        
        config_data = {
            "notebook_source": str(notebook_dir),
            "glue_catalog": {
                "account_id": "123456789012",
                "region": "us-east-1",
                "databases": ["test_db"]
            },
            "opensearch": {
                "endpoint": "test-domain.us-east-1.es.amazonaws.com",
                "region": "us-east-1"
            }
        }
        
        config = Config(**config_data)
        assert Path(config.notebook_source).exists()
        assert config.glue_catalog.account_id == "123456789012"
    
    def test_valid_config_s3_path(self):
        """Test valid configuration with S3 path."""
        config_data = {
            "notebook_source": "s3://my-bucket/notebooks/",
            "glue_catalog": {
                "account_id": "123456789012",
                "region": "us-east-1",
                "databases": ["test_db"]
            },
            "opensearch": {
                "endpoint": "test-domain.us-east-1.es.amazonaws.com",
                "region": "us-east-1"
            }
        }
        
        config = Config(**config_data)
        assert config.notebook_source == "s3://my-bucket/notebooks/"
    
    def test_invalid_local_path(self):
        """Test invalid local path raises error."""
        config_data = {
            "notebook_source": "/nonexistent/path",
            "glue_catalog": {
                "account_id": "123456789012",
                "region": "us-east-1",
                "databases": ["test_db"]
            },
            "opensearch": {
                "endpoint": "test-domain.us-east-1.es.amazonaws.com",
                "region": "us-east-1"
            }
        }
        
        with pytest.raises(ValidationError):
            Config(**config_data)
    
    def test_yaml_roundtrip(self, tmp_path):
        """Test YAML save and load roundtrip."""
        notebook_dir = tmp_path / "notebooks"
        notebook_dir.mkdir()
        
        config_data = {
            "notebook_source": str(notebook_dir),
            "glue_catalog": {
                "account_id": "123456789012",
                "region": "us-east-1",
                "databases": ["test_db"]
            },
            "opensearch": {
                "endpoint": "test-domain.us-east-1.es.amazonaws.com",
                "region": "us-east-1"
            }
        }
        
        # Create and save config
        config1 = Config(**config_data)
        yaml_path = tmp_path / "test_config.yaml"
        config1.to_yaml(yaml_path)
        
        # Load config from YAML
        config2 = Config.from_yaml(yaml_path)
        
        # Compare key fields
        assert config1.notebook_source == config2.notebook_source
        assert config1.glue_catalog.account_id == config2.glue_catalog.account_id
        assert config1.opensearch.endpoint == config2.opensearch.endpoint