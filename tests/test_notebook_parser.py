"""Tests for notebook parser."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from text2sql_rag.notebook_parser import NotebookParser, NotebookCell, ParsedNotebook


class TestNotebookParser:
    """Test notebook parser functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = None
    
    def create_test_jupyter_notebook(self, notebook_path: Path):
        """Create a test Jupyter notebook."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# Data Analysis Notebook\n", "This notebook analyzes sales data."],
                    "metadata": {}
                },
                {
                    "cell_type": "code",
                    "source": [
                        "SELECT customer_id, SUM(amount) as total\n",
                        "FROM sales_table\n", 
                        "WHERE date >= '2023-01-01'\n",
                        "GROUP BY customer_id"
                    ],
                    "metadata": {},
                    "execution_count": 1,
                    "outputs": []
                },
                {
                    "cell_type": "markdown",
                    "source": ["## Results\n", "The query shows customer totals."],
                    "metadata": {}
                },
                {
                    "cell_type": "code",
                    "source": ["print('Analysis complete')"],
                    "metadata": {},
                    "execution_count": 2,
                    "outputs": []
                }
            ],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 4
        }
        
        with open(notebook_path, 'w') as f:
            json.dump(notebook_content, f)
    
    def create_test_zeppelin_notebook(self, notebook_path: Path):
        """Create a test Zeppelin notebook."""
        notebook_content = {
            "paragraphs": [
                {
                    "text": "%md\n# Sales Analysis\nThis analyzes our sales data.",
                    "config": {"enabled": True},
                    "settings": {}
                },
                {
                    "text": "SELECT product_id, COUNT(*) as sales_count\nFROM sales_fact\nWHERE date >= '2023-01-01'\nGROUP BY product_id\nORDER BY sales_count DESC",
                    "config": {"enabled": True},
                    "settings": {}
                },
                {
                    "text": "%md\n## Summary\nTop selling products identified.",
                    "config": {"enabled": True},
                    "settings": {}
                }
            ],
            "info": {
                "name": "Sales Analysis"
            }
        }
        
        with open(notebook_path, 'w') as f:
            json.dump(notebook_content, f)
    
    def test_local_notebook_discovery(self, tmp_path):
        """Test discovery of notebooks in local directory."""
        # Create test notebooks
        self.create_test_jupyter_notebook(tmp_path / "test1.ipynb")
        self.create_test_zeppelin_notebook(tmp_path / "test2.json")
        
        # Create non-notebook files that should be ignored
        (tmp_path / "data.csv").write_text("test,data\n1,2")
        (tmp_path / "readme.txt").write_text("This is a readme")
        
        parser = NotebookParser(str(tmp_path))
        notebooks = parser.discover_notebooks()
        
        assert len(notebooks) == 2
        assert any("test1.ipynb" in nb for nb in notebooks)
        assert any("test2.json" in nb for nb in notebooks)
    
    def test_jupyter_notebook_parsing(self, tmp_path):
        """Test parsing of Jupyter notebook."""
        notebook_path = tmp_path / "test.ipynb"
        self.create_test_jupyter_notebook(notebook_path)
        
        parser = NotebookParser(str(tmp_path))
        parsed = parser.parse_notebook(str(notebook_path))
        
        assert parsed is not None
        assert parsed.notebook_type == "jupyter"
        assert len(parsed.cells) == 4
        assert len(parsed.sql_cells) == 1  # Only one cell contains SQL
        assert len(parsed.markdown_cells) == 2
        
        # Check SQL cell content
        sql_cell = parsed.sql_cells[0]
        assert "SELECT" in sql_cell.source
        assert "sales_table" in sql_cell.source
    
    def test_zeppelin_notebook_parsing(self, tmp_path):
        """Test parsing of Zeppelin notebook."""
        notebook_path = tmp_path / "test.json"
        self.create_test_zeppelin_notebook(notebook_path)
        
        parser = NotebookParser(str(tmp_path))
        parsed = parser.parse_notebook(str(notebook_path))
        
        assert parsed is not None
        assert parsed.notebook_type == "zeppelin"
        assert len(parsed.cells) == 3
        assert len(parsed.sql_cells) == 1
        assert len(parsed.markdown_cells) == 2
        
        # Check SQL cell content
        sql_cell = parsed.sql_cells[0]
        assert "SELECT" in sql_cell.source
        assert "sales_fact" in sql_cell.source
    
    def test_sql_detection(self):
        """Test SQL detection in various text formats."""
        parser = NotebookParser("/dummy/path")
        
        # Test positive cases
        assert parser._contains_sql("SELECT * FROM table1")
        assert parser._contains_sql("select customer_id from customers")
        assert parser._contains_sql("WITH cte AS (SELECT...) SELECT * FROM cte")
        assert parser._contains_sql("%sql SELECT * FROM table")
        assert parser._contains_sql("%%sql\nSELECT * FROM table")
        assert parser._contains_sql("INSERT INTO table VALUES (1, 2)")
        
        # Test negative cases
        assert not parser._contains_sql("print('Hello world')")
        assert not parser._contains_sql("import pandas as pd")
        assert not parser._contains_sql("")
        assert not parser._contains_sql("This is just text")
    
    def test_sql_context_extraction(self, tmp_path):
        """Test extraction of SQL queries with surrounding context."""
        # Create notebook with SQL and context
        notebook_content = {
            "cells": [
                {
                    "cell_type": "markdown",
                    "source": ["# Customer Analysis\n", "Analyzing customer purchase patterns."],
                    "metadata": {}
                },
                {
                    "cell_type": "markdown", 
                    "source": ["## Get customer totals\n", "This query calculates total spent per customer."],
                    "metadata": {}
                },
                {
                    "cell_type": "code",
                    "source": [
                        "SELECT customer_id, SUM(amount) as total\n",
                        "FROM sales\n",
                        "GROUP BY customer_id"
                    ],
                    "metadata": {},
                    "execution_count": 1,
                    "outputs": []
                },
                {
                    "cell_type": "markdown",
                    "source": ["The results show the highest spending customers."],
                    "metadata": {}
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 4
        }
        
        notebook_path = tmp_path / "context_test.ipynb"
        with open(notebook_path, 'w') as f:
            json.dump(notebook_content, f)
        
        parser = NotebookParser(str(tmp_path))
        parsed = parser.parse_notebook(str(notebook_path))
        sql_extracts = parser.extract_sql_with_context([parsed])
        
        assert len(sql_extracts) == 1
        extract = sql_extracts[0]
        
        assert "SELECT" in extract['sql_query']
        assert "customer totals" in extract['context_before']
        assert "highest spending" in extract['context_after']
        assert extract['notebook_type'] == "jupyter"
    
    @patch('boto3.client')
    def test_s3_notebook_discovery(self, mock_boto_client):
        """Test discovery of notebooks in S3."""
        # Mock S3 client
        mock_s3 = Mock()
        mock_boto_client.return_value = mock_s3
        
        # Mock paginator
        mock_paginator = Mock()
        mock_s3.get_paginator.return_value = mock_paginator
        
        # Mock S3 response
        mock_paginator.paginate.return_value = [
            {
                'Contents': [
                    {'Key': 'notebooks/analysis1.ipynb'},
                    {'Key': 'notebooks/analysis2.json'},
                    {'Key': 'notebooks/data.csv'},  # Should be ignored
                    {'Key': 'notebooks/subfolder/analysis3.ipynb'}
                ]
            }
        ]
        
        parser = NotebookParser("s3://test-bucket/notebooks/")
        notebooks = parser.discover_notebooks()
        
        # Should find 3 notebook files (.ipynb and .json)
        assert len(notebooks) == 3
        assert "s3://test-bucket/notebooks/analysis1.ipynb" in notebooks
        assert "s3://test-bucket/notebooks/analysis2.json" in notebooks
        assert "s3://test-bucket/notebooks/subfolder/analysis3.ipynb" in notebooks
    
    def test_parallel_processing(self, tmp_path):
        """Test parallel processing of multiple notebooks."""
        # Create multiple test notebooks
        for i in range(5):
            self.create_test_jupyter_notebook(tmp_path / f"notebook_{i}.ipynb")
        
        parser = NotebookParser(str(tmp_path))
        parsed_notebooks = parser.parse_notebooks_parallel(max_workers=2)
        
        # Should have parsed all notebooks with SQL content
        assert len(parsed_notebooks) == 5
        
        # All should be Jupyter notebooks
        assert all(nb.notebook_type == "jupyter" for nb in parsed_notebooks)
        
        # All should have SQL cells
        assert all(len(nb.sql_cells) > 0 for nb in parsed_notebooks)
    
    def test_invalid_notebook_handling(self, tmp_path):
        """Test handling of invalid or corrupted notebook files."""
        # Create invalid JSON file
        invalid_notebook = tmp_path / "invalid.ipynb"
        invalid_notebook.write_text("{ invalid json content")
        
        # Create empty file
        empty_notebook = tmp_path / "empty.ipynb"
        empty_notebook.write_text("")
        
        parser = NotebookParser(str(tmp_path))
        
        # Should handle invalid files gracefully
        parsed_invalid = parser.parse_notebook(str(invalid_notebook))
        parsed_empty = parser.parse_notebook(str(empty_notebook))
        
        assert parsed_invalid is None
        assert parsed_empty is None
    
    def test_notebook_magic_command_handling(self, tmp_path):
        """Test handling of various notebook magic commands."""
        notebook_content = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["%sql SELECT * FROM table1"],
                    "metadata": {},
                    "execution_count": 1,
                    "outputs": []
                },
                {
                    "cell_type": "code", 
                    "source": ["%%sql\n", "SELECT customer_id\n", "FROM customers"],
                    "metadata": {},
                    "execution_count": 2,
                    "outputs": []
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 4
        }
        
        notebook_path = tmp_path / "magic_test.ipynb"
        with open(notebook_path, 'w') as f:
            json.dump(notebook_content, f)
        
        parser = NotebookParser(str(tmp_path))
        parsed = parser.parse_notebook(str(notebook_path))
        
        # Both cells should be detected as SQL
        assert len(parsed.sql_cells) == 2
        
        # Check that magic commands are properly handled
        for cell in parsed.sql_cells:
            assert "SELECT" in cell.source