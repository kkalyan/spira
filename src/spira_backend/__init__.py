"""Spira Backend: Core logic for intelligent SQL generation."""

__version__ = "0.1.0"

from .config import Config
from .knowledge_base import KnowledgeBaseBuilder
from .query_engine import QueryEngine
from .glue_catalog import GlueCatalogExtractor, TableMetadata
from .notebook_parser import NotebookParser, ParsedNotebook
from .sql_analyzer import SQLAnalyzer, SQLPattern
from .opensearch_client import OpenSearchClient
from .embeddings import BedrockEmbeddingClient, QueryEmbeddingPipeline

__all__ = [
    "Config",
    "KnowledgeBaseBuilder", 
    "QueryEngine",
    "GlueCatalogExtractor",
    "TableMetadata",
    "NotebookParser",
    "ParsedNotebook", 
    "SQLAnalyzer",
    "SQLPattern",
    "OpenSearchClient",
    "BedrockEmbeddingClient",
    "QueryEmbeddingPipeline"
]