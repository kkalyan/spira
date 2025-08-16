"""Tests for SQL analyzer."""

import pytest
from spira_backend.sql_analyzer import SQLAnalyzer, SQLPattern


class TestSQLAnalyzer:
    """Test SQL analyzer functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = SQLAnalyzer()
    
    def test_simple_select_query(self):
        """Test analysis of simple SELECT query."""
        sql = """
        SELECT customer_id, SUM(amount) as total_amount
        FROM sales_table
        WHERE date >= '2023-01-01'
        GROUP BY customer_id
        ORDER BY total_amount DESC
        """
        
        pattern = self.analyzer.analyze_query(sql)
        
        assert pattern.query_type == "SELECT"
        assert "sales_table" in pattern.tables
        assert "SUM" in pattern.aggregations
        assert len(pattern.filters) > 0
    
    def test_join_query(self):
        """Test analysis of query with JOINs."""
        sql = """
        SELECT c.customer_name, SUM(s.amount) as total
        FROM customers c
        INNER JOIN sales s ON c.customer_id = s.customer_id
        WHERE s.date >= '2023-01-01'
        GROUP BY c.customer_name
        """
        
        pattern = self.analyzer.analyze_query(sql)
        
        assert pattern.query_type == "SELECT"
        assert "customers" in pattern.tables or "sales" in pattern.tables
        assert len(pattern.joins) > 0
        assert "SUM" in pattern.aggregations
    
    def test_cte_query(self):
        """Test analysis of query with Common Table Expression."""
        sql = """
        WITH monthly_sales AS (
            SELECT 
                DATE_TRUNC('month', date) as month,
                SUM(amount) as monthly_total
            FROM sales
            GROUP BY DATE_TRUNC('month', date)
        )
        SELECT month, monthly_total
        FROM monthly_sales
        WHERE monthly_total > 10000
        """
        
        pattern = self.analyzer.analyze_query(sql)
        
        assert pattern.query_type == "WITH"
        assert "monthly_sales" in pattern.cte_names
        assert "sales" in pattern.tables
        assert "SUM" in pattern.aggregations
    
    def test_subquery_detection(self):
        """Test detection of subqueries."""
        sql = """
        SELECT customer_id, amount
        FROM sales
        WHERE amount > (
            SELECT AVG(amount) 
            FROM sales 
            WHERE date >= '2023-01-01'
        )
        """
        
        pattern = self.analyzer.analyze_query(sql)
        
        assert len(pattern.subqueries) > 0
        assert "AVG" in pattern.aggregations
    
    def test_notebook_magic_cleaning(self):
        """Test cleaning of notebook magic commands."""
        sql = """
        %sql
        SELECT * FROM table1
        WHERE id = 1
        """
        
        pattern = self.analyzer.analyze_query(sql)
        
        assert pattern.query_type == "SELECT"
        assert "table1" in pattern.tables
    
    def test_comment_removal(self):
        """Test removal of SQL comments."""
        sql = """
        -- This is a comment
        SELECT customer_id, /* inline comment */ amount
        FROM sales_table
        /* multi-line 
           comment */
        WHERE date >= '2023-01-01'
        """
        
        pattern = self.analyzer.analyze_query(sql)
        
        assert pattern.query_type == "SELECT"
        assert "sales_table" in pattern.tables
    
    def test_empty_query(self):
        """Test handling of empty or invalid queries."""
        pattern1 = self.analyzer.analyze_query("")
        pattern2 = self.analyzer.analyze_query("   ")
        pattern3 = self.analyzer.analyze_query("invalid sql syntax")
        
        assert pattern1.query_type == "UNKNOWN"
        assert pattern2.query_type == "UNKNOWN"
        # pattern3 might still extract some information depending on implementation
    
    def test_business_pattern_analysis(self):
        """Test business pattern analysis across multiple queries."""
        sql_extracts = [
            {
                'sql_query': """
                SELECT customer_id, SUM(revenue) as total_revenue
                FROM sales_fact
                WHERE date >= '2023-01-01'
                GROUP BY customer_id
                """,
                'context_before': 'Calculate customer lifetime value'
            },
            {
                'sql_query': """
                SELECT product_id, COUNT(*) as sales_count
                FROM sales_fact
                WHERE date >= '2023-01-01'
                GROUP BY product_id
                """,
                'context_before': 'Analyze product performance'
            },
            {
                'sql_query': """
                SELECT 
                    customer_id,
                    DATE_TRUNC('month', date) as month,
                    SUM(revenue) as monthly_revenue
                FROM sales_fact
                WHERE date >= '2023-01-01'
                GROUP BY customer_id, DATE_TRUNC('month', date)
                """,
                'context_before': 'Monthly revenue analysis'
            }
        ]
        
        business_patterns = self.analyzer.analyze_business_patterns(sql_extracts)
        
        # Check that patterns were extracted
        assert len(business_patterns.table_relationships) > 0 or len(business_patterns.common_filters) > 0
        
        # sales_fact should appear in common filters or aggregations
        if 'sales_fact' in business_patterns.common_filters:
            assert len(business_patterns.common_filters['sales_fact']) > 0
        
        if 'sales_fact' in business_patterns.aggregation_patterns:
            assert 'SUM' in business_patterns.aggregation_patterns['sales_fact']
    
    def test_date_pattern_extraction(self):
        """Test extraction of date-related patterns."""
        sql_extracts = [
            {
                'sql_query': """
                SELECT * FROM sales
                WHERE date >= DATE_SUB(CURRENT_DATE, INTERVAL 30 DAY)
                """,
                'context_before': 'Last 30 days sales'
            },
            {
                'sql_query': """
                SELECT * FROM orders
                WHERE created_at >= '2023-01-01'
                AND created_at < '2024-01-01'
                """,
                'context_before': 'Orders for 2023'
            }
        ]
        
        business_patterns = self.analyzer.analyze_business_patterns(sql_extracts)
        
        # Should extract some date patterns
        assert len(business_patterns.date_patterns) > 0
    
    def test_pattern_context_formatting(self):
        """Test formatting of patterns for LLM context."""
        # Create a mock business pattern
        from text2sql_rag.sql_analyzer import BusinessPattern
        
        business_pattern = BusinessPattern(
            table_relationships={'sales': {'customers', 'products'}},
            common_filters={'sales': ['date >= CURRENT_DATE - 30', 'status = "active"']},
            business_calculations=['SUM(revenue) as total_revenue'],
            date_patterns=['date >= CURRENT_DATE - 30'],
            aggregation_patterns={'sales': ['SUM', 'COUNT']}
        )
        
        formatted = self.analyzer.format_patterns_for_context(business_pattern)
        
        assert 'Common Table Relationships' in formatted
        assert 'sales' in formatted
        assert 'customers' in formatted
        assert 'SUM' in formatted