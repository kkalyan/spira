"""Main CLI coordinator for Spira - Intelligent SQL generation system."""

import argparse
import sys


def main():
    """Main CLI entry point that coordinates all Spira commands."""
    parser = argparse.ArgumentParser(
        description="🌟 Spira - Intelligent SQL Generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Commands:
  spira-build     Build knowledge base from notebooks
  spira-app       Run Spira web application
  spira           Interactive query interface

Examples:
  # Build knowledge base
  spira-build --config config.yaml

  # Run web application
  spira-app --port 8080

  # Interactive querying
  spira --config config.yaml

For help with specific commands, use command --help
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to configuration YAML file'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n🌟 Welcome to Spira!")
        print("\nQuick start:")
        print("1. spira-build --config config.yaml  # Build knowledge base")
        print("2. spira-app                         # Run web application")
        sys.exit(0)
    
    args = parser.parse_args()
    
    # If config provided, run interactive query interface
    if args.config:
        from spira_backend.cli import query_interactive
        # Set up args for the interactive function
        sys.argv = ['spira', '--config', args.config]
        if args.verbose:
            sys.argv.append('--verbose')
        query_interactive()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()