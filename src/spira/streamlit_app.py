"""Streamlit web application for Spira - Intelligent SQL generation system."""

import logging
import traceback
from pathlib import Path
from typing import Optional

import streamlit as st
import pandas as pd
from streamlit.logger import get_logger

from .config import Config
from .knowledge_base import KnowledgeBaseBuilder
from .query_engine import QueryEngine, SQLResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = get_logger(__name__)


class StreamlitApp:
    """Streamlit application for Spira."""
    
    def __init__(self):
        """Initialize the Streamlit app."""
        self.config: Optional[Config] = None
        self.query_engine: Optional[QueryEngine] = None
        self.knowledge_base: Optional[KnowledgeBaseBuilder] = None
        
        # Initialize session state
        if 'query_history' not in st.session_state:
            st.session_state.query_history = []
        if 'config_loaded' not in st.session_state:
            st.session_state.config_loaded = False
    
    def run(self):
        """Run the Streamlit application."""
        st.set_page_config(
            page_title="Spira",
            page_icon="🌟",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("🌟 Spira")
        st.markdown("**Intelligent SQL generation from natural language**")
        st.markdown("Powered by AWS Bedrock Claude, OpenSearch, and your domain knowledge")
        
        # Sidebar for configuration and controls
        with st.sidebar:
            self._render_sidebar()
        
        # Main content area
        if not st.session_state.config_loaded:
            self._render_config_setup()
        else:
            self._render_main_interface()
    
    def _render_sidebar(self):
        """Render the sidebar with configuration and controls."""
        st.header("Configuration")
        
        # Configuration file upload
        config_file = st.file_uploader(
            "Upload Configuration (YAML)",
            type=['yaml', 'yml'],
            help="Upload your configuration file to connect to AWS services"
        )
        
        if config_file and not st.session_state.config_loaded:
            try:
                # Save uploaded file temporarily
                temp_config_path = Path("temp_config.yaml")
                with open(temp_config_path, "wb") as f:
                    f.write(config_file.getvalue())
                
                # Load configuration
                self.config = Config.from_yaml(temp_config_path)
                self.query_engine = QueryEngine(self.config)
                self.knowledge_base = KnowledgeBaseBuilder(self.config)
                
                st.session_state.config_loaded = True
                st.success("Configuration loaded successfully!")
                
                # Clean up temp file
                temp_config_path.unlink()
                
            except Exception as e:
                st.error(f"Failed to load configuration: {str(e)}")
                logger.error(f"Configuration error: {e}")
        
        # System status
        if st.session_state.config_loaded:
            st.header("System Status")
            self._render_system_status()
            
            # Knowledge base management
            st.header("Knowledge Base")
            self._render_knowledge_base_controls()
    
    def _render_config_setup(self):
        """Render configuration setup instructions."""
        st.info("🚀 Welcome to Spira! Please upload a configuration file to get started.")
        
        with st.expander("📋 Configuration Example", expanded=True):
            config_example = """
notebook_source: "s3://your-bucket/notebooks/"  # or "/local/path/to/notebooks"

glue_catalog:
  account_id: "123456789012"
  region: "us-east-1"
  databases: ["your_database"]
  # OR specific tables:
  # tables: ["db.table1", "db.table2"]

opensearch:
  endpoint: "your-opensearch-domain.region.es.amazonaws.com"
  region: "us-east-1"
  index_name: "text2sql-knowledge"

models:
  offline_model: "anthropic.claude-3-haiku-20240307-v1:0"
  online_model: "anthropic.claude-3-5-sonnet-20241022-v2:0"
  embedding_model: "amazon.titan-embed-text-v2:0"
  region: "us-east-1"
"""
            st.code(config_example, language='yaml')
        
        st.markdown("""
        ### Prerequisites:
        1. **AWS Credentials**: Ensure your AWS credentials are configured
        2. **OpenSearch Cluster**: Set up an AWS OpenSearch cluster
        3. **Bedrock Access**: Enable access to Claude and Titan models
        4. **Glue Catalog**: Configure cross-account access if needed
        5. **Notebooks**: Prepare your Jupyter/Zeppelin notebooks
        """)
    
    def _render_system_status(self):
        """Render system status information."""
        if not self.knowledge_base:
            return
        
        try:
            stats = self.knowledge_base.get_knowledge_base_stats()
            
            if stats.get('status') == 'healthy':
                st.success("🌟 Spira is Online")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Documents", stats.get('document_count', 0))
                
                with col2:
                    index_size_mb = stats.get('index_size', 0) / (1024 * 1024)
                    st.metric("Index Size", f"{index_size_mb:.1f} MB")
            else:
                st.error(f"System Error: {stats.get('error', 'Unknown')}")
                
        except Exception as e:
            st.error(f"Failed to get system status: {str(e)}")
    
    def _render_knowledge_base_controls(self):
        """Render knowledge base management controls."""
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Rebuild KB", help="Rebuild the entire knowledge base"):
                self._rebuild_knowledge_base()
        
        with col2:
            if st.button("📊 View Stats", help="View detailed knowledge base statistics"):
                self._show_detailed_stats()
    
    def _render_main_interface(self):
        """Render the main query interface."""
        # Query input
        st.header("Ask a Question")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            user_question = st.text_area(
                "Enter your question in natural language:",
                placeholder="e.g., Show me the total revenue by month for the last year",
                height=100
            )
        
        with col2:
            st.markdown("### Options")
            max_similar = st.slider("Similar queries", 1, 10, 5)
            hybrid_search = st.checkbox("Hybrid search", value=True, 
                                      help="Use both text and semantic search")
            show_context = st.checkbox("Show context", value=False,
                                     help="Display the context used for generation")
        
        # Generate SQL button
        if st.button("🔍 Generate SQL", type="primary", disabled=not user_question.strip()):
            self._generate_and_display_sql(user_question, max_similar, hybrid_search, show_context)
        
        # Query history
        if st.session_state.query_history:
            st.header("Query History")
            self._render_query_history()
    
    def _generate_and_display_sql(self, user_question: str, max_similar: int, 
                                 hybrid_search: bool, show_context: bool):
        """Generate and display SQL result."""
        if not self.query_engine:
            st.error("Query engine not initialized. Please check your configuration.")
            return
        
        with st.spinner("Generating SQL query..."):
            try:
                # Generate SQL
                result = self.query_engine.generate_sql(
                    user_question=user_question,
                    max_similar=max_similar,
                    hybrid_search=hybrid_search
                )
                
                # Add to history
                st.session_state.query_history.insert(0, {
                    'question': user_question,
                    'result': result,
                    'timestamp': pd.Timestamp.now()
                })
                
                # Keep only last 10 queries
                st.session_state.query_history = st.session_state.query_history[:10]
                
                # Display result
                self._display_sql_result(result, show_context)
                
            except Exception as e:
                st.error(f"Error generating SQL: {str(e)}")
                logger.error(f"SQL generation error: {e}")
                logger.error(traceback.format_exc())
    
    def _display_sql_result(self, result: SQLResult, show_context: bool):
        """Display SQL generation result."""
        if not result.sql_query:
            st.error(f"Failed to generate SQL: {result.explanation}")
            return
        
        # Main result
        st.success(f"SQL generated successfully! (Confidence: {result.confidence:.2f})")
        
        # SQL Query
        st.subheader("Generated SQL")
        st.code(result.sql_query, language='sql')
        
        # Copy button
        if st.button("📋 Copy SQL"):
            st.write("SQL copied to clipboard!")  # Note: Actual clipboard copy requires additional setup
        
        # Explanation
        if result.explanation:
            st.subheader("Explanation")
            st.write(result.explanation)
        
        # Performance info
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Confidence", f"{result.confidence:.2f}")
        with col2:
            st.metric("Generation Time", f"{result.execution_time:.2f}s")
        
        # Similar queries (citations)
        if result.similar_queries:
            st.subheader("Similar Queries (Citations)")
            self._display_similar_queries(result.similar_queries)
        
        # Context information
        if show_context and result.schema_context:
            with st.expander("Schema Context Used"):
                st.text(result.schema_context)
    
    def _display_similar_queries(self, similar_queries: list):
        """Display similar queries with citations."""
        for i, query in enumerate(similar_queries[:3], 1):  # Show top 3
            with st.expander(f"Similar Query {i} (Similarity: {query['similarity_score']:.3f})"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.code(query['sql_query'], language='sql')
                    
                    if query.get('context_before'):
                        st.write("**Context:**", query['context_before'])
                
                with col2:
                    st.write("**Source:**", query.get('notebook_path', 'Unknown'))
                    st.write("**Type:**", query.get('query_type', 'Unknown'))
                    
                    if query.get('tables_used'):
                        st.write("**Tables:**", ', '.join(query['tables_used']))
    
    def _render_query_history(self):
        """Render query history."""
        for i, entry in enumerate(st.session_state.query_history):
            with st.expander(f"{entry['timestamp'].strftime('%H:%M:%S')} - {entry['question'][:50]}..."):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.code(entry['result'].sql_query, language='sql')
                
                with col2:
                    st.metric("Confidence", f"{entry['result'].confidence:.2f}")
                    if st.button("🔄 Rerun", key=f"rerun_{i}"):
                        self._generate_and_display_sql(
                            entry['question'], 5, True, False
                        )
    
    def _rebuild_knowledge_base(self):
        """Rebuild the knowledge base."""
        if not self.knowledge_base:
            st.error("Knowledge base not initialized")
            return
        
        with st.spinner("Rebuilding knowledge base... This may take several minutes."):
            try:
                success = self.knowledge_base.rebuild_index()
                if success:
                    st.success("Knowledge base rebuilt successfully!")
                else:
                    st.error("Failed to rebuild knowledge base. Check logs for details.")
            except Exception as e:
                st.error(f"Error rebuilding knowledge base: {str(e)}")
                logger.error(f"KB rebuild error: {e}")
    
    def _show_detailed_stats(self):
        """Show detailed knowledge base statistics."""
        if not self.knowledge_base:
            return
        
        try:
            stats = self.knowledge_base.get_knowledge_base_stats()
            
            st.subheader("Knowledge Base Statistics")
            
            # Create metrics columns
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total Documents", stats.get('document_count', 0))
                st.metric("Glue Databases", stats.get('glue_databases', 0))
            
            with col2:
                index_size_mb = stats.get('index_size', 0) / (1024 * 1024)
                st.metric("Index Size (MB)", f"{index_size_mb:.1f}")
                st.metric("Glue Tables", stats.get('glue_tables', 0))
            
            with col3:
                st.metric("Status", stats.get('status', 'Unknown'))
                st.write("**Embedding Model:**", stats.get('embedding_model', 'Unknown'))
            
            # Configuration details
            with st.expander("Configuration Details"):
                st.json(stats)
                
        except Exception as e:
            st.error(f"Failed to get detailed stats: {str(e)}")


def main():
    """Main entry point for the Streamlit app."""
    app = StreamlitApp()
    app.run()


if __name__ == "__main__":
    main()