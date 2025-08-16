#!/usr/bin/env python3
"""
Example script for querying the Spira system programmatically.

This script demonstrates how to use the QueryEngine directly in your code
to generate SQL from natural language questions.
"""

import logging
from pathlib import Path

from spira.config import Config
from spira.query_engine import QueryEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Example of programmatic SQL generation."""
    
    # Load configuration
    config_path = Path("config.yaml")
    if not config_path.exists():
        print("❌ Configuration file 'config.yaml' not found!")
        print("Please create a config.yaml file based on the example.")
        return
    
    try:
        # Initialize the query engine
        print("🔧 Loading configuration and initializing query engine...")
        config = Config.from_yaml(config_path)
        query_engine = QueryEngine(config)
        print("✅ Query engine ready!")
        
        # Example questions
        questions = [
            "Show me the total revenue by month for the last year",
            "Which customers have the highest lifetime value?",
            "What are the top 10 products by sales volume?",
            "How many new customers did we acquire each quarter?",
            "What is the average order value by customer segment?"
        ]
        
        print("\n🔍 Generating SQL for example questions...\n")
        
        for i, question in enumerate(questions, 1):
            print(f"{'='*60}")
            print(f"Question {i}: {question}")
            print(f"{'='*60}")
            
            # Generate SQL
            result = query_engine.generate_sql(
                user_question=question,
                max_similar=3,
                hybrid_search=True
            )
            
            if result.sql_query:
                print(f"✅ Generated SQL (Confidence: {result.confidence:.2f}):")
                print("-" * 40)
                print(result.sql_query)
                print("-" * 40)
                
                if result.explanation:
                    print(f"\n💡 Explanation:")
                    print(result.explanation)
                
                if result.similar_queries:
                    print(f"\n📚 Similar queries found ({len(result.similar_queries)}):")
                    for j, sq in enumerate(result.similar_queries[:2], 1):
                        print(f"  {j}. Similarity: {sq['similarity_score']:.3f}")
                        print(f"     Source: {sq.get('notebook_path', 'Unknown')}")
                        print(f"     Query: {sq['sql_query'][:100]}...")
                
                print(f"\n⏱️  Generation time: {result.execution_time:.2f}s")
                
                # Validate the generated SQL
                is_valid, validation_msg = query_engine.validate_sql(result.sql_query)
                if is_valid:
                    print("✅ SQL validation: PASSED")
                else:
                    print(f"⚠️  SQL validation: {validation_msg}")
                
            else:
                print(f"❌ Failed to generate SQL: {result.explanation}")
            
            print("\n")
        
        print("🎉 Example queries completed!")
        print("\nTips for better results:")
        print("- Be specific about time periods and filters")
        print("- Use business terms that appear in your notebooks")
        print("- Ask for common analysis patterns from your domain")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Query example failed: {e}")


if __name__ == "__main__":
    main()