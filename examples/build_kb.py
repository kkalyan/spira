#!/usr/bin/env python3
"""
Example script for building the Spira knowledge base.

This script demonstrates how to programmatically build the knowledge base
from your notebooks and Glue catalog metadata.
"""

import logging
import sys
from pathlib import Path

from spira_backend.config import Config
from spira_backend.knowledge_base import KnowledgeBaseBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to build the knowledge base."""
    
    # Load configuration
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error("Configuration file 'config.yaml' not found!")
        logger.info("Please create a config.yaml file based on the example in examples/config.yaml")
        sys.exit(1)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = Config.from_yaml(config_path)
        logger.info("✅ Configuration loaded successfully")
        
        # Initialize knowledge base builder
        logger.info("Initializing knowledge base builder...")
        kb_builder = KnowledgeBaseBuilder(config)
        logger.info("✅ Knowledge base builder initialized")
        
        # Build the knowledge base
        logger.info("🚀 Starting knowledge base build process...")
        logger.info("This may take several minutes depending on the number of notebooks...")
        
        success = kb_builder.build_knowledge_base()
        
        if success:
            logger.info("🎉 Knowledge base built successfully!")
            
            # Show statistics
            stats = kb_builder.get_knowledge_base_stats()
            logger.info("📊 Knowledge Base Statistics:")
            logger.info(f"  📝 Documents indexed: {stats.get('document_count', 0)}")
            logger.info(f"  💾 Index size: {stats.get('index_size', 0) / (1024*1024):.1f} MB")
            logger.info(f"  📚 Notebook source: {stats.get('notebook_source', 'Unknown')}")
            logger.info(f"  🗃️  Glue databases: {stats.get('glue_databases', 0)}")
            logger.info(f"  📋 Glue tables: {stats.get('glue_tables', 0)}")
            
            logger.info("\n✅ Knowledge base is ready for querying!")
            logger.info("You can now run the Spira app with: spira-app")
            
        else:
            logger.error("❌ Knowledge base build failed!")
            logger.error("Check the logs above for error details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("⚠️  Build process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Build process failed: {e}")
        logger.error("Check your configuration and AWS credentials.")
        sys.exit(1)


if __name__ == "__main__":
    main()