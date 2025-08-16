"""Notebook parsing for Jupyter and Zeppelin notebooks."""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class NotebookCell:
    """Represents a cell in a notebook."""
    cell_type: str  # 'code', 'markdown', 'text'
    source: str
    metadata: Dict
    execution_count: Optional[int] = None
    outputs: Optional[List] = None


@dataclass
class ParsedNotebook:
    """Represents a parsed notebook with metadata."""
    notebook_path: str
    notebook_type: str  # 'jupyter' or 'zeppelin'
    cells: List[NotebookCell]
    metadata: Dict
    sql_cells: List[NotebookCell]
    markdown_cells: List[NotebookCell]


class NotebookParser:
    """Parser for Jupyter and Zeppelin notebooks."""
    
    def __init__(self, notebook_source: str):
        """Initialize the notebook parser.
        
        Args:
            notebook_source: S3 path or local directory containing notebooks
        """
        self.notebook_source = notebook_source
        self.is_s3 = notebook_source.startswith('s3://')
        
        if self.is_s3:
            self.s3_client = boto3.client('s3')
            self.bucket, self.prefix = self._parse_s3_path(notebook_source)
        
        # SQL detection patterns
        self.sql_patterns = [
            re.compile(r'^\s*SELECT\s+', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*WITH\s+', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*INSERT\s+', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*UPDATE\s+', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*DELETE\s+', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*CREATE\s+', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*ALTER\s+', re.IGNORECASE | re.MULTILINE),
            re.compile(r'^\s*DROP\s+', re.IGNORECASE | re.MULTILINE),
            re.compile(r'%sql\s+', re.IGNORECASE),  # Jupyter magic
            re.compile(r'%%sql', re.IGNORECASE),    # Jupyter cell magic
        ]
    
    def _parse_s3_path(self, s3_path: str) -> Tuple[str, str]:
        """Parse S3 path into bucket and prefix.
        
        Args:
            s3_path: S3 path in format s3://bucket/prefix
            
        Returns:
            Tuple of (bucket, prefix)
        """
        path = s3_path.replace('s3://', '')
        parts = path.split('/', 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''
        return bucket, prefix
    
    def discover_notebooks(self) -> List[str]:
        """Discover all notebook files in the source location.
        
        Returns:
            List of notebook file paths
        """
        if self.is_s3:
            return self._discover_s3_notebooks()
        else:
            return self._discover_local_notebooks()
    
    def _discover_local_notebooks(self) -> List[str]:
        """Discover notebooks in local filesystem."""
        notebooks = []
        source_path = Path(self.notebook_source)
        
        if not source_path.exists():
            logger.error(f"Local path does not exist: {self.notebook_source}")
            return notebooks
        
        # Find Jupyter notebooks (.ipynb)
        jupyter_notebooks = list(source_path.rglob('*.ipynb'))
        notebooks.extend([str(p) for p in jupyter_notebooks])
        
        # Find Zeppelin notebooks (.json)
        zeppelin_notebooks = list(source_path.rglob('*.json'))
        # Filter for actual Zeppelin notebooks (basic heuristic)
        for notebook in zeppelin_notebooks:
            if self._is_zeppelin_notebook(notebook):
                notebooks.append(str(notebook))
        
        logger.info(f"Discovered {len(notebooks)} notebooks in {self.notebook_source}")
        return notebooks
    
    def _discover_s3_notebooks(self) -> List[str]:
        """Discover notebooks in S3."""
        notebooks = []
        paginator = self.s3_client.get_paginator('list_objects_v2')
        
        try:
            for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if key.endswith('.ipynb') or key.endswith('.json'):
                        notebooks.append(f"s3://{self.bucket}/{key}")
            
            logger.info(f"Discovered {len(notebooks)} notebooks in {self.notebook_source}")
            return notebooks
            
        except ClientError as e:
            logger.error(f"Failed to list S3 objects: {e}")
            return []
    
    def _is_zeppelin_notebook(self, file_path: Path) -> bool:
        """Check if a JSON file is a Zeppelin notebook.
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            True if it's a Zeppelin notebook
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Zeppelin notebooks have 'paragraphs' field
                return 'paragraphs' in data
        except (json.JSONDecodeError, IOError):
            return False
    
    def parse_notebook(self, notebook_path: str) -> Optional[ParsedNotebook]:
        """Parse a single notebook file.
        
        Args:
            notebook_path: Path to the notebook file
            
        Returns:
            Parsed notebook or None if parsing failed
        """
        try:
            content = self._read_notebook_content(notebook_path)
            if not content:
                return None
            
            data = json.loads(content)
            
            if notebook_path.endswith('.ipynb'):
                return self._parse_jupyter_notebook(notebook_path, data)
            else:
                return self._parse_zeppelin_notebook(notebook_path, data)
                
        except Exception as e:
            logger.error(f"Failed to parse notebook {notebook_path}: {e}")
            return None
    
    def _read_notebook_content(self, notebook_path: str) -> Optional[str]:
        """Read notebook content from file or S3.
        
        Args:
            notebook_path: Path to the notebook
            
        Returns:
            Notebook content as string
        """
        try:
            if notebook_path.startswith('s3://'):
                bucket, key = self._parse_s3_path(notebook_path)
                response = self.s3_client.get_object(Bucket=bucket, Key=key)
                return response['Body'].read().decode('utf-8')
            else:
                with open(notebook_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to read notebook {notebook_path}: {e}")
            return None
    
    def _parse_jupyter_notebook(self, notebook_path: str, data: Dict) -> ParsedNotebook:
        """Parse a Jupyter notebook.
        
        Args:
            notebook_path: Path to the notebook
            data: Notebook JSON data
            
        Returns:
            Parsed notebook
        """
        cells = []
        sql_cells = []
        markdown_cells = []
        
        for cell_data in data.get('cells', []):
            cell = NotebookCell(
                cell_type=cell_data.get('cell_type', 'code'),
                source=self._extract_source(cell_data.get('source', [])),
                metadata=cell_data.get('metadata', {}),
                execution_count=cell_data.get('execution_count'),
                outputs=cell_data.get('outputs', [])
            )
            
            cells.append(cell)
            
            # Categorize cells
            if cell.cell_type == 'code' and self._contains_sql(cell.source):
                sql_cells.append(cell)
            elif cell.cell_type == 'markdown':
                markdown_cells.append(cell)
        
        return ParsedNotebook(
            notebook_path=notebook_path,
            notebook_type='jupyter',
            cells=cells,
            metadata=data.get('metadata', {}),
            sql_cells=sql_cells,
            markdown_cells=markdown_cells
        )
    
    def _parse_zeppelin_notebook(self, notebook_path: str, data: Dict) -> ParsedNotebook:
        """Parse a Zeppelin notebook.
        
        Args:
            notebook_path: Path to the notebook
            data: Notebook JSON data
            
        Returns:
            Parsed notebook
        """
        cells = []
        sql_cells = []
        markdown_cells = []
        
        for paragraph in data.get('paragraphs', []):
            # Zeppelin paragraphs can have different interpreters
            text = paragraph.get('text', '')
            config = paragraph.get('config', {})
            
            # Determine cell type based on interpreter
            cell_type = 'code'
            if text.startswith('%md'):
                cell_type = 'markdown'
                text = text[3:].strip()  # Remove %md prefix
            
            cell = NotebookCell(
                cell_type=cell_type,
                source=text,
                metadata={
                    'config': config,
                    'settings': paragraph.get('settings', {}),
                    'title': paragraph.get('title', '')
                }
            )
            
            cells.append(cell)
            
            # Categorize cells
            if cell_type == 'code' and self._contains_sql(cell.source):
                sql_cells.append(cell)
            elif cell_type == 'markdown':
                markdown_cells.append(cell)
        
        return ParsedNotebook(
            notebook_path=notebook_path,
            notebook_type='zeppelin',
            cells=cells,
            metadata=data.get('info', {}),
            sql_cells=sql_cells,
            markdown_cells=markdown_cells
        )
    
    def _extract_source(self, source: Union[str, List[str]]) -> str:
        """Extract source code from Jupyter cell source format.
        
        Args:
            source: Source code as string or list of strings
            
        Returns:
            Combined source code as string
        """
        if isinstance(source, list):
            return ''.join(source)
        return source
    
    def _contains_sql(self, text: str) -> bool:
        """Check if text contains SQL code.
        
        Args:
            text: Text to check
            
        Returns:
            True if text contains SQL
        """
        if not text or not text.strip():
            return False
        
        # Remove comments
        text_no_comments = re.sub(r'--.*$', '', text, flags=re.MULTILINE)
        text_no_comments = re.sub(r'/\*.*?\*/', '', text_no_comments, flags=re.DOTALL)
        
        return any(pattern.search(text_no_comments) for pattern in self.sql_patterns)
    
    def parse_notebooks_parallel(self, max_workers: int = 10) -> List[ParsedNotebook]:
        """Parse all notebooks in parallel.
        
        Args:
            max_workers: Maximum number of parallel workers
            
        Returns:
            List of parsed notebooks
        """
        notebook_paths = self.discover_notebooks()
        if not notebook_paths:
            logger.warning("No notebooks found to parse")
            return []
        
        parsed_notebooks = []
        
        logger.info(f"Parsing {len(notebook_paths)} notebooks using {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {
                executor.submit(self.parse_notebook, path): path
                for path in notebook_paths
            }
            
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    parsed_notebook = future.result()
                    if parsed_notebook:
                        parsed_notebooks.append(parsed_notebook)
                        logger.debug(f"Parsed notebook: {path}")
                except Exception as e:
                    logger.error(f"Failed to parse notebook {path}: {e}")
        
        # Filter notebooks with SQL content
        sql_notebooks = [nb for nb in parsed_notebooks if nb.sql_cells]
        
        logger.info(f"Parsed {len(parsed_notebooks)} notebooks, {len(sql_notebooks)} contain SQL")
        return sql_notebooks
    
    def extract_sql_with_context(self, parsed_notebooks: List[ParsedNotebook]) -> List[Dict]:
        """Extract SQL queries with surrounding context.
        
        Args:
            parsed_notebooks: List of parsed notebooks
            
        Returns:
            List of SQL extracts with context
        """
        sql_extracts = []
        
        for notebook in parsed_notebooks:
            for i, sql_cell in enumerate(notebook.sql_cells):
                # Get surrounding context (markdown cells before/after)
                context_before = []
                context_after = []
                
                # Find position of SQL cell in all cells
                sql_cell_index = -1
                for j, cell in enumerate(notebook.cells):
                    if cell == sql_cell:
                        sql_cell_index = j
                        break
                
                if sql_cell_index >= 0:
                    # Get markdown context before
                    for j in range(max(0, sql_cell_index - 3), sql_cell_index):
                        if notebook.cells[j].cell_type == 'markdown':
                            context_before.append(notebook.cells[j].source)
                    
                    # Get markdown context after
                    for j in range(sql_cell_index + 1, min(len(notebook.cells), sql_cell_index + 4)):
                        if notebook.cells[j].cell_type == 'markdown':
                            context_after.append(notebook.cells[j].source)
                
                sql_extract = {
                    'notebook_path': notebook.notebook_path,
                    'notebook_type': notebook.notebook_type,
                    'sql_query': sql_cell.source,
                    'context_before': ' '.join(context_before),
                    'context_after': ' '.join(context_after),
                    'cell_metadata': sql_cell.metadata,
                    'execution_count': sql_cell.execution_count
                }
                
                sql_extracts.append(sql_extract)
        
        logger.info(f"Extracted {len(sql_extracts)} SQL queries with context")
        return sql_extracts