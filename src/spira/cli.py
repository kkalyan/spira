"""Command-line interface for Spira - Intelligent SQL generation system."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from .config import Config
from .knowledge_base import KnowledgeBaseBuilder
from .query_engine import QueryEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Setup logging configuration.
    
    Args:
        verbose: Enable verbose logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)
    
    # Reduce noise from some libraries
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def build_knowledge_base():
    """CLI command to build the knowledge base."""
    parser = argparse.ArgumentParser(
        description="Build Spira knowledge base from notebooks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build from YAML config
  spira-build --config config.yaml

  # Build with verbose logging
  spira-build --config config.yaml --verbose

  # Force rebuild (delete existing index)
  spira-build --config config.yaml --force-rebuild
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        required=True,
        help='Path to configuration YAML file'
    )
    
    parser.add_argument(
        '--force-rebuild',
        action='store_true',
        help='Force rebuild of existing knowledge base'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        # Load configuration
        logger.info(f"Loading configuration from {args.config}")
        config_path = Path(args.config)
        
        if not config_path.exists():
            logger.error(f"Configuration file not found: {args.config}")
            sys.exit(1)
        
        config = Config.from_yaml(config_path)
        logger.info("Configuration loaded successfully")
        
        # Initialize knowledge base builder
        logger.info("Initializing knowledge base builder...")
        kb_builder = KnowledgeBaseBuilder(config)
        
        # Build knowledge base
        logger.info("Starting knowledge base build process...")
        success = kb_builder.build_knowledge_base(force_rebuild=args.force_rebuild)
        
        if success:
            logger.info("✅ Knowledge base built successfully!")
            
            # Show statistics
            stats = kb_builder.get_knowledge_base_stats()
            logger.info(f"📊 Statistics:")
            logger.info(f"  - Documents indexed: {stats.get('document_count', 0)}")
            logger.info(f"  - Index size: {stats.get('index_size', 0) / (1024*1024):.1f} MB")
            logger.info(f"  - Notebook source: {stats.get('notebook_source', 'Unknown')}")
            
        else:
            logger.error("❌ Knowledge base build failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Build process interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Build process failed: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)


def run_app():
    """CLI command to run the Streamlit app."""
    parser = argparse.ArgumentParser(
        description="Run Spira web application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  spira-app

  # Run on specific port
  spira-app --port 8080

  # Run with custom config (optional)
  spira-app --config config.yaml
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to configuration YAML file (optional, can be uploaded via UI)'
    )
    
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=8501,
        help='Port to run the Streamlit app on (default: 8501)'
    )
    
    parser.add_argument(
        '--host',
        type=str,
        default='localhost',
        help='Host to bind the app to (default: localhost)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        import streamlit.web.cli as stcli
        import os
        
        # Set Streamlit configuration
        os.environ['STREAMLIT_SERVER_PORT'] = str(args.port)
        os.environ['STREAMLIT_SERVER_ADDRESS'] = args.host
        
        # Path to the Streamlit app
        app_path = Path(__file__).parent / "streamlit_app.py"
        
        logger.info(f"Starting Streamlit app on {args.host}:{args.port}")
        logger.info(f"App module: {app_path}")
        
        # Launch Streamlit
        sys.argv = [
            "streamlit",
            "run",
            str(app_path),
            "--server.port", str(args.port),
            "--server.address", args.host,
        ]
        
        stcli.main()
        
    except ImportError:
        logger.error("Streamlit not installed. Install with: pip install streamlit")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)


def query_interactive():
    """CLI command for interactive querying."""
    parser = argparse.ArgumentParser(
        description="Interactive Spira query interface",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        required=True,
        help='Path to configuration YAML file'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        # Load configuration
        config_path = Path(args.config)
        if not config_path.exists():
            logger.error(f"Configuration file not found: {args.config}")
            sys.exit(1)
        
        config = Config.from_yaml(config_path)
        logger.info("Configuration loaded successfully")
        
        # Initialize query engine
        query_engine = QueryEngine(config)
        logger.info("Query engine initialized")
        
        print("\n🔍 Spira Interactive Query Interface")
        print("Type 'quit' or 'exit' to exit, 'help' for commands")
        print("-" * 50)
        
        while True:
            try:
                question = input("\n❓ Enter your question: ").strip()
                
                if question.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if question.lower() == 'help':
                    print("\nCommands:")
                    print("  help  - Show this help message")
                    print("  quit  - Exit the application")
                    print("  Otherwise, enter a natural language question about your data")
                    continue
                
                if not question:
                    continue
                
                print(f"\n🔄 Generating SQL for: {question}")
                
                # Generate SQL
                result = query_engine.generate_sql(question)
                
                if result.sql_query:
                    print(f"\n✅ Generated SQL (Confidence: {result.confidence:.2f}):")
                    print("-" * 40)
                    print(result.sql_query)
                    print("-" * 40)
                    
                    if result.explanation:
                        print(f"\n💡 Explanation: {result.explanation}")
                    
                    if result.similar_queries:
                        print(f"\n📚 Found {len(result.similar_queries)} similar queries")
                        for i, sq in enumerate(result.similar_queries[:2], 1):
                            print(f"  {i}. Similarity: {sq['similarity_score']:.3f} from {sq.get('notebook_path', 'Unknown')}")
                    
                    print(f"\n⏱️  Generation time: {result.execution_time:.2f}s")
                else:
                    print(f"\n❌ Failed to generate SQL: {result.explanation}")
                
            except KeyboardInterrupt:
                print("\nUse 'quit' to exit gracefully")
            except Exception as e:
                print(f"\n❌ Error: {e}")
                if args.verbose:
                    import traceback
                    print(traceback.format_exc())
    
    except Exception as e:
        logger.error(f"Interactive query failed: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("🌟 Spira - Intelligent SQL Generation")
        print("\nAvailable commands:")
        print("  spira-build  - Build knowledge base from notebooks")
        print("  spira-app    - Run Spira web application")
        print("  spira        - Interactive query interface")
        print("\nFor help with specific commands, use --help")
        print("\nExample usage:")
        print("  spira-build --config config.yaml")
        print("  spira-app --port 8080")
        sys.exit(1)


if __name__ == "__main__":
    main()