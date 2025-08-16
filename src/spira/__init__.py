"""Spira: Intelligent SQL generation from natural language using RAG and AWS AI services."""

__version__ = "0.1.0"
__author__ = "Spira Contributors"
__email__ = ""

# Import from backend
from spira_backend import (
    Config, 
    KnowledgeBaseBuilder, 
    QueryEngine,
    GlueCatalogExtractor,
    NotebookParser,
    SQLAnalyzer,
    OpenSearchClient,
    BedrockEmbeddingClient
)

# Import from app
from spira_app import StreamlitApp

__all__ = [
    "Config", 
    "KnowledgeBaseBuilder", 
    "QueryEngine",
    "GlueCatalogExtractor",
    "NotebookParser", 
    "SQLAnalyzer",
    "OpenSearchClient",
    "BedrockEmbeddingClient",
    "StreamlitApp"
]