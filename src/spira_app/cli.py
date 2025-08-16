"""Command-line interface for Spira App - Streamlit web application."""

import argparse
import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_app():
    """CLI command to run the Spira Streamlit app."""
    parser = argparse.ArgumentParser(
        description="Run Spira web application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default settings
  spira-app

  # Run on specific port
  spira-app --port 8080

  # Run with custom host
  spira-app --host 0.0.0.0 --port 8080
        """
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
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        import streamlit.web.cli as stcli
        
        # Set Streamlit configuration
        os.environ['STREAMLIT_SERVER_PORT'] = str(args.port)
        os.environ['STREAMLIT_SERVER_ADDRESS'] = args.host
        
        # Path to the Streamlit app
        app_path = Path(__file__).parent / "app.py"
        
        logger.info(f"Starting Spira app on {args.host}:{args.port}")
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
        logger.info("Spira app stopped by user")
    except Exception as e:
        logger.error(f"Failed to start Spira app: {e}")
        if args.verbose:
            import traceback
            logger.error(traceback.format_exc())
        sys.exit(1)


def main():
    """Main CLI entry point for Spira app."""
    run_app()


if __name__ == "__main__":
    main()