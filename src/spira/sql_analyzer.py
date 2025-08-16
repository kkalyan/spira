"""SQL pattern analysis and knowledge extraction."""

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Function, Where, Statement
from sqlparse.tokens import Keyword, Name

logger = logging.getLogger(__name__)


@dataclass
class SQLPattern:
    """Represents extracted patterns from SQL query."""
    tables: Set[str]
    columns: Set[str]
    joins: List[Tuple[str, str, str]]  # (left_table, right_table, join_type)
    filters: List[str]  # WHERE conditions
    aggregations: Set[str]  # COUNT, SUM, etc.
    functions: Set[str]  # Built-in functions used
    subqueries: List[str]
    cte_names: Set[str]  # Common Table Expression names
    query_type: str  # SELECT, INSERT, UPDATE, etc.


@dataclass
class BusinessPattern:
    """Represents business logic patterns from SQL."""
    table_relationships: Dict[str, Set[str]]  # table -> related tables
    common_filters: Dict[str, List[str]]  # table -> common WHERE conditions
    business_calculations: List[str]  # Complex calculations or business logic
    date_patterns: List[str]  # Date filtering patterns
    aggregation_patterns: Dict[str, List[str]]  # table -> common aggregations


class SQLAnalyzer:
    """Analyzes SQL queries to extract patterns and business logic."""
    
    def __init__(self):
        """Initialize the SQL analyzer."""
        self.table_alias_map = {}
        
        # Common SQL functions and operators
        self.aggregation_functions = {
            'count', 'sum', 'avg', 'min', 'max', 'median', 'stddev',
            'first_value', 'last_value', 'row_number', 'rank', 'dense_rank'
        }
        
        self.date_functions = {
            'date_trunc', 'date_part', 'extract', 'dateadd', 'datediff',
            'current_date', 'current_timestamp', 'now', 'getdate'
        }
        
        # Common business logic patterns
        self.business_keywords = [
            'revenue', 'profit', 'loss', 'margin', 'conversion', 'retention',
            'churn', 'ltv', 'cac', 'arpu', 'mrr', 'arr', 'cohort'
        ]
    
    def analyze_query(self, sql_query: str, context: str = "") -> SQLPattern:
        """Analyze a single SQL query to extract patterns.
        
        Args:
            sql_query: SQL query string
            context: Additional context about the query
            
        Returns:
            Extracted SQL patterns
        """
        try:
            # Clean and parse the SQL
            cleaned_sql = self._clean_sql(sql_query)
            parsed = sqlparse.parse(cleaned_sql)[0]
            
            pattern = SQLPattern(
                tables=set(),
                columns=set(),
                joins=[],
                filters=[],
                aggregations=set(),
                functions=set(),
                subqueries=[],
                cte_names=set(),
                query_type=self._get_query_type(parsed)
            )
            
            # Extract patterns
            self._extract_tables_and_columns(parsed, pattern)
            self._extract_joins(parsed, pattern)
            self._extract_filters(parsed, pattern)
            self._extract_functions_and_aggregations(parsed, pattern)
            self._extract_subqueries(parsed, pattern)
            self._extract_ctes(parsed, pattern)
            
            return pattern
            
        except Exception as e:
            logger.error(f"Failed to analyze SQL query: {e}")
            logger.debug(f"Query: {sql_query[:200]}...")
            return SQLPattern(
                tables=set(), columns=set(), joins=[], filters=[],
                aggregations=set(), functions=set(), subqueries=[],
                cte_names=set(), query_type='UNKNOWN'
            )
    
    def _clean_sql(self, sql: str) -> str:
        """Clean SQL query for better parsing.
        
        Args:
            sql: Raw SQL query
            
        Returns:
            Cleaned SQL query
        """
        # Remove notebook magic commands
        sql = re.sub(r'^%sql\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        sql = re.sub(r'^%%sql\s*', '', sql, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove comments but preserve structure
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        
        # Normalize whitespace
        sql = re.sub(r'\s+', ' ', sql).strip()
        
        return sql
    
    def _get_query_type(self, parsed: Statement) -> str:
        """Get the type of SQL query.
        
        Args:
            parsed: Parsed SQL statement
            
        Returns:
            Query type (SELECT, INSERT, etc.)
        """
        for token in parsed.tokens:
            if token.ttype is Keyword and token.value.upper() in [
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'WITH'
            ]:
                return token.value.upper()
        return 'UNKNOWN'
    
    def _extract_tables_and_columns(self, parsed: Statement, pattern: SQLPattern) -> None:
        """Extract table and column names from parsed SQL.
        
        Args:
            parsed: Parsed SQL statement
            pattern: Pattern object to update
        """
        self.table_alias_map = {}
        
        for token in parsed.flatten():
            if token.ttype is Name:
                # Could be table, column, or alias
                self._process_name_token(token, pattern)
    
    def _process_name_token(self, token, pattern: SQLPattern) -> None:
        """Process a name token to extract table/column information.
        
        Args:
            token: SQL token
            pattern: Pattern object to update
        """
        # This is a simplified implementation
        # In practice, you'd need more sophisticated parsing
        value = token.value
        
        # Skip common SQL keywords
        if value.upper() in ['FROM', 'WHERE', 'SELECT', 'AS', 'ON', 'AND', 'OR']:
            return
        
        # Check if it looks like a table.column reference
        if '.' in value:
            parts = value.split('.')
            if len(parts) == 2:
                table_or_alias, column = parts
                pattern.columns.add(column)
                
                # Resolve alias to actual table name
                actual_table = self.table_alias_map.get(table_or_alias, table_or_alias)
                pattern.tables.add(actual_table)
        else:
            # Could be a table name or column name
            # Context-dependent determination would be needed
            if self._looks_like_table_name(value):
                pattern.tables.add(value)
            else:
                pattern.columns.add(value)
    
    def _looks_like_table_name(self, name: str) -> bool:
        """Heuristic to determine if a name looks like a table name.
        
        Args:
            name: Name to check
            
        Returns:
            True if it looks like a table name
        """
        # Simple heuristics - in practice, you'd use schema information
        table_suffixes = ['_table', '_tbl', '_fact', '_dim', '_stage', '_raw']
        return any(name.lower().endswith(suffix) for suffix in table_suffixes)
    
    def _extract_joins(self, parsed: Statement, pattern: SQLPattern) -> None:
        """Extract JOIN information from parsed SQL.
        
        Args:
            parsed: Parsed SQL statement
            pattern: Pattern object to update
        """
        sql_str = str(parsed).upper()
        
        # Find JOIN patterns
        join_patterns = [
            r'(\w+)\s+(?:INNER\s+)?JOIN\s+(\w+)',
            r'(\w+)\s+LEFT\s+(?:OUTER\s+)?JOIN\s+(\w+)',
            r'(\w+)\s+RIGHT\s+(?:OUTER\s+)?JOIN\s+(\w+)',
            r'(\w+)\s+FULL\s+(?:OUTER\s+)?JOIN\s+(\w+)',
        ]
        
        for pattern_regex in join_patterns:
            matches = re.finditer(pattern_regex, sql_str)
            for match in matches:
                left_table = match.group(1)
                right_table = match.group(2)
                join_type = 'INNER'  # Default
                
                if 'LEFT' in match.group(0):
                    join_type = 'LEFT'
                elif 'RIGHT' in match.group(0):
                    join_type = 'RIGHT'
                elif 'FULL' in match.group(0):
                    join_type = 'FULL'
                
                pattern.joins.append((left_table, right_table, join_type))
    
    def _extract_filters(self, parsed: Statement, pattern: SQLPattern) -> None:
        """Extract WHERE clause filters from parsed SQL.
        
        Args:
            parsed: Parsed SQL statement
            pattern: Pattern object to update
        """
        for token in parsed.tokens:
            if isinstance(token, Where):
                # Extract individual filter conditions
                where_str = str(token).replace('WHERE', '').strip()
                
                # Split on AND/OR but preserve the conditions
                conditions = re.split(r'\s+(?:AND|OR)\s+', where_str, flags=re.IGNORECASE)
                pattern.filters.extend([cond.strip() for cond in conditions if cond.strip()])
    
    def _extract_functions_and_aggregations(self, parsed: Statement, pattern: SQLPattern) -> None:
        """Extract functions and aggregations from parsed SQL.
        
        Args:
            parsed: Parsed SQL statement
            pattern: Pattern object to update
        """
        sql_upper = str(parsed).upper()
        
        # Extract aggregation functions
        for agg_func in self.aggregation_functions:
            if f'{agg_func.upper()}(' in sql_upper:
                pattern.aggregations.add(agg_func.upper())
        
        # Extract other functions
        for date_func in self.date_functions:
            if f'{date_func.upper()}(' in sql_upper:
                pattern.functions.add(date_func.upper())
        
        # Find function calls using regex
        func_pattern = r'(\w+)\s*\('
        functions = re.findall(func_pattern, sql_upper)
        pattern.functions.update(functions)
    
    def _extract_subqueries(self, parsed: Statement, pattern: SQLPattern) -> None:
        """Extract subqueries from parsed SQL.
        
        Args:
            parsed: Parsed SQL statement
            pattern: Pattern object to update
        """
        sql_str = str(parsed)
        
        # Find subqueries (simplified approach)
        subquery_pattern = r'\(\s*SELECT\s+.*?\)'
        subqueries = re.findall(subquery_pattern, sql_str, re.IGNORECASE | re.DOTALL)
        pattern.subqueries.extend(subqueries)
    
    def _extract_ctes(self, parsed: Statement, pattern: SQLPattern) -> None:
        """Extract Common Table Expressions (CTEs) from parsed SQL.
        
        Args:
            parsed: Parsed SQL statement
            pattern: Pattern object to update
        """
        sql_str = str(parsed)
        
        # Find CTE names
        cte_pattern = r'WITH\s+(\w+)\s+AS\s*\('
        cte_names = re.findall(cte_pattern, sql_str, re.IGNORECASE)
        pattern.cte_names.update(cte_names)
    
    def analyze_business_patterns(self, sql_extracts: List[Dict]) -> BusinessPattern:
        """Analyze business patterns across multiple SQL queries.
        
        Args:
            sql_extracts: List of SQL extracts with context
            
        Returns:
            Business patterns found across queries
        """
        business_pattern = BusinessPattern(
            table_relationships={},
            common_filters={},
            business_calculations=[],
            date_patterns=[],
            aggregation_patterns={}
        )
        
        table_join_counts = {}
        table_filter_counts = {}
        table_agg_counts = {}
        
        for extract in sql_extracts:
            sql_pattern = self.analyze_query(extract['sql_query'], extract.get('context_before', ''))
            
            # Track table relationships
            for join in sql_pattern.joins:
                left_table, right_table, join_type = join
                
                if left_table not in business_pattern.table_relationships:
                    business_pattern.table_relationships[left_table] = set()
                business_pattern.table_relationships[left_table].add(right_table)
                
                # Count relationships
                relationship_key = f"{left_table}-{right_table}"
                table_join_counts[relationship_key] = table_join_counts.get(relationship_key, 0) + 1
            
            # Track common filters per table
            for table in sql_pattern.tables:
                if table not in table_filter_counts:
                    table_filter_counts[table] = {}
                
                for filter_condition in sql_pattern.filters:
                    if table.lower() in filter_condition.lower():
                        table_filter_counts[table][filter_condition] = \
                            table_filter_counts[table].get(filter_condition, 0) + 1
            
            # Track aggregation patterns
            for table in sql_pattern.tables:
                if table not in table_agg_counts:
                    table_agg_counts[table] = {}
                
                for agg in sql_pattern.aggregations:
                    table_agg_counts[table][agg] = table_agg_counts[table].get(agg, 0) + 1
            
            # Extract business calculations
            if any(keyword in extract['sql_query'].lower() for keyword in self.business_keywords):
                business_pattern.business_calculations.append(extract['sql_query'])
            
            # Extract date patterns
            if any(func in sql_pattern.functions for func in self.date_functions):
                for filter_condition in sql_pattern.filters:
                    if any(date_word in filter_condition.lower() for date_word in ['date', 'time', 'day', 'month', 'year']):
                        business_pattern.date_patterns.append(filter_condition)
        
        # Convert counts to top patterns
        for table, filters in table_filter_counts.items():
            top_filters = sorted(filters.items(), key=lambda x: x[1], reverse=True)[:5]
            business_pattern.common_filters[table] = [f[0] for f in top_filters]
        
        for table, aggs in table_agg_counts.items():
            top_aggs = sorted(aggs.items(), key=lambda x: x[1], reverse=True)[:5]
            business_pattern.aggregation_patterns[table] = [a[0] for a in top_aggs]
        
        logger.info(f"Analyzed business patterns across {len(sql_extracts)} SQL queries")
        return business_pattern
    
    def format_patterns_for_context(self, business_pattern: BusinessPattern) -> str:
        """Format business patterns as context for LLM.
        
        Args:
            business_pattern: Business patterns to format
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        # Table relationships
        if business_pattern.table_relationships:
            context_parts.append("## Common Table Relationships")
            for table, related_tables in business_pattern.table_relationships.items():
                context_parts.append(f"- {table} commonly joined with: {', '.join(related_tables)}")
        
        # Common filters
        if business_pattern.common_filters:
            context_parts.append("\n## Common Filters by Table")
            for table, filters in business_pattern.common_filters.items():
                if filters:
                    context_parts.append(f"- {table}: {', '.join(filters[:3])}")
        
        # Aggregation patterns
        if business_pattern.aggregation_patterns:
            context_parts.append("\n## Common Aggregations by Table")
            for table, aggs in business_pattern.aggregation_patterns.items():
                if aggs:
                    context_parts.append(f"- {table}: {', '.join(aggs[:3])}")
        
        # Date patterns
        if business_pattern.date_patterns:
            context_parts.append("\n## Common Date Filters")
            unique_date_patterns = list(set(business_pattern.date_patterns[:5]))
            for pattern in unique_date_patterns:
                context_parts.append(f"- {pattern}")
        
        return "\n".join(context_parts)