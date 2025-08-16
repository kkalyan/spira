#!/usr/bin/env python3
"""
Demo Streamlit app to showcase Spira branding.
This version works without AWS dependencies for UI demonstration.
"""

import streamlit as st

# Mock classes for demo
class MockConfig:
    def __init__(self):
        self.notebook_source = "s3://demo-bucket/notebooks/"
        self.opensearch = type('obj', (object,), {'endpoint': 'demo.us-east-1.es.amazonaws.com'})

class MockStats:
    def get_knowledge_base_stats(self):
        return {
            'status': 'healthy',
            'document_count': 15420,
            'index_size': 1024 * 1024 * 250,  # 250MB
            'notebook_source': 's3://demo-bucket/notebooks/',
            'glue_databases': 12,
            'glue_tables': 847
        }

def main():
    """Demo Spira Streamlit application."""
    
    # Page configuration
    st.set_page_config(
        page_title="Spira",
        page_icon="🌟",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Main title and description
    st.title("🌟 Spira")
    st.markdown("**Intelligent SQL generation from natural language**")
    st.markdown("Powered by AWS Bedrock Claude, OpenSearch, and your domain knowledge")
    
    # Sidebar
    with st.sidebar:
        st.header("Configuration")
        st.success("🌟 Demo Mode Active")
        
        st.header("System Status")
        st.success("🌟 Spira is Online")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Documents", "15,420")
        with col2:
            st.metric("Index Size", "250.0 MB")
        
        st.header("Knowledge Base")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Rebuild KB"):
                st.info("Demo mode - KB rebuild simulated")
        with col2:
            if st.button("📊 View Stats"):
                st.balloons()
    
    # Main interface
    if st.sidebar.button("📝 Show Demo Stats"):
        st.subheader("📊 Knowledge Base Statistics")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Documents", "15,420")
            st.metric("Glue Databases", "12")
        with col2:
            st.metric("Index Size (MB)", "250.0")
            st.metric("Glue Tables", "847")
        with col3:
            st.metric("Status", "🟢 Healthy")
            st.write("**Embedding Model:**")
            st.code("amazon.titan-embed-text-v2:0")
    
    # Query interface
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
        if user_question.strip():
            # Demo SQL generation
            st.success("SQL generated successfully! (Confidence: 0.94)")
            
            st.subheader("Generated SQL")
            demo_sql = f"""SELECT 
    c.customer_id,
    c.customer_name,
    SUM(o.total_amount) as total_amount
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_date >= DATE_SUB(CURRENT_DATE, INTERVAL 1 YEAR)
GROUP BY c.customer_id, c.customer_name
ORDER BY total_amount DESC
LIMIT 10;"""
            
            st.code(demo_sql, language='sql')
            
            if st.button("📋 Copy SQL"):
                st.success("SQL copied to clipboard! (Demo)")
            
            # Metrics
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Confidence", "0.94")
            with col2:
                st.metric("Generation Time", "1.2s")
            
            # Similar queries
            st.subheader("Similar Queries (Citations)")
            
            with st.expander("Similar Query 1 (Similarity: 0.892)"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.code("""SELECT customer_id, SUM(amount) as total 
FROM sales WHERE date >= '2023-01-01'
GROUP BY customer_id ORDER BY total DESC""", language='sql')
                    st.write("**Context:** Customer revenue analysis")
                with col2:
                    st.write("**Source:** notebook_analytics_2024.ipynb")
                    st.write("**Type:** SELECT")
                    st.write("**Tables:** sales, customers")
            
            with st.expander("Similar Query 2 (Similarity: 0.847)"):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.code("""SELECT c.name, SUM(s.revenue) as yearly_revenue
FROM customers c JOIN sales s ON c.id = s.customer_id
WHERE s.year = 2023 GROUP BY c.name""", language='sql')
                    st.write("**Context:** Annual customer performance")
                with col2:
                    st.write("**Source:** customer_analysis.ipynb")
                    st.write("**Type:** SELECT") 
                    st.write("**Tables:** customers, sales")
    
    # Query history section
    st.header("Recent Queries")
    
    # Demo history
    demo_history = [
        {"question": "Show me top selling products", "confidence": 0.91, "time": "14:32"},
        {"question": "What's our customer churn rate?", "confidence": 0.88, "time": "14:25"},
        {"question": "Monthly revenue trend analysis", "confidence": 0.95, "time": "14:18"}
    ]
    
    for i, entry in enumerate(demo_history):
        with st.expander(f"{entry['time']} - {entry['question']} (Confidence: {entry['confidence']})"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.code("SELECT * FROM demo_table WHERE condition = 'example';", language='sql')
            with col2:
                st.metric("Confidence", f"{entry['confidence']}")
                if st.button("🔄 Rerun", key=f"rerun_{i}"):
                    st.info("Demo mode - rerun simulated")
    
    # Footer
    st.markdown("---")
    st.markdown("**🌟 Spira Demo** - Transform your data interaction experience!")

if __name__ == "__main__":
    main()