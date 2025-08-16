"""OpenSearch client for vector storage and retrieval."""

import json
import logging
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import ConnectionError, RequestError

from .config import OpenSearchConfig

logger = logging.getLogger(__name__)


class AWSRequestsHttpConnection(RequestsHttpConnection):
    """Custom connection class for AWS IAM authentication."""
    
    def __init__(self, aws_region: str, **kwargs):
        super().__init__(**kwargs)
        self.aws_region = aws_region
        self.session = boto3.Session()
        self.credentials = self.session.get_credentials()
    
    def perform_request(self, method, url, params=None, body=None, timeout=None, ignore=(), headers=None):
        """Override to add AWS IAM signature."""
        if headers is None:
            headers = {}
        
        # Prepare AWS request
        request = AWSRequest(
            method=method,
            url=f"https://{self.host}:{self.port}{url}",
            data=body,
            params=params,
            headers=headers
        )
        
        # Sign the request
        SigV4Auth(self.credentials, 'es', self.aws_region).add_auth(request)
        
        # Update headers
        headers.update(dict(request.headers.items()))
        
        return super().perform_request(
            method, url, params, body, timeout, ignore, headers
        )


class OpenSearchClient:
    """Client for OpenSearch operations with AWS integration."""
    
    def __init__(self, config: OpenSearchConfig):
        """Initialize OpenSearch client.
        
        Args:
            config: OpenSearch configuration
        """
        self.config = config
        self.client = self._create_client()
        self.index_name = config.index_name
    
    def _create_client(self) -> OpenSearch:
        """Create OpenSearch client with AWS authentication.
        
        Returns:
            Configured OpenSearch client
        """
        # Parse endpoint
        endpoint = self.config.endpoint.replace('https://', '').replace('http://', '')
        
        try:
            client = OpenSearch(
                hosts=[{
                    'host': endpoint,
                    'port': 443 if self.config.use_ssl else 80
                }],
                http_auth=None,  # Using IAM auth
                use_ssl=self.config.use_ssl,
                verify_certs=self.config.verify_certs,
                connection_class=AWSRequestsHttpConnection,
                aws_region=self.config.region,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )
            
            # Test connection
            client.cluster.health()
            logger.info(f"Connected to OpenSearch cluster: {endpoint}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to connect to OpenSearch: {e}")
            raise
    
    def create_index(self, force_recreate: bool = False) -> bool:
        """Create the knowledge base index.
        
        Args:
            force_recreate: Whether to delete and recreate existing index
            
        Returns:
            True if index was created successfully
        """
        try:
            # Check if index exists
            if self.client.indices.exists(index=self.index_name):
                if force_recreate:
                    logger.info(f"Deleting existing index: {self.index_name}")
                    self.client.indices.delete(index=self.index_name)
                else:
                    logger.info(f"Index already exists: {self.index_name}")
                    return True
            
            # Define index mapping
            index_mapping = {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "index": {
                        "knn": True,
                        "knn.algo_param.ef_search": 512
                    }
                },
                "mappings": {
                    "properties": {
                        "sql_query": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "business_context": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "table_pattern": {
                            "type": "text",
                            "analyzer": "keyword"
                        },
                        "tables_used": {
                            "type": "keyword"
                        },
                        "query_type": {
                            "type": "keyword"
                        },
                        "notebook_path": {
                            "type": "keyword"
                        },
                        "notebook_type": {
                            "type": "keyword"
                        },
                        "context_before": {
                            "type": "text"
                        },
                        "context_after": {
                            "type": "text"
                        },
                        "joins": {
                            "type": "keyword"
                        },
                        "filters": {
                            "type": "text"
                        },
                        "aggregations": {
                            "type": "keyword"
                        },
                        "embedding": {
                            "type": "knn_vector",
                            "dimension": 1024,  # Titan v2 dimension
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib",
                                "parameters": {
                                    "ef_construction": 512,
                                    "m": 16
                                }
                            }
                        },
                        "timestamp": {
                            "type": "date"
                        }
                    }
                }
            }
            
            # Create index
            self.client.indices.create(
                index=self.index_name,
                body=index_mapping
            )
            
            logger.info(f"Created index: {self.index_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            return False
    
    def index_document(self, doc_id: str, document: Dict) -> bool:
        """Index a single document.
        
        Args:
            doc_id: Unique document ID
            document: Document to index
            
        Returns:
            True if indexing was successful
        """
        try:
            self.client.index(
                index=self.index_name,
                id=doc_id,
                body=document
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to index document {doc_id}: {e}")
            return False
    
    def bulk_index_documents(self, documents: List[Dict]) -> int:
        """Bulk index multiple documents.
        
        Args:
            documents: List of documents to index
            
        Returns:
            Number of successfully indexed documents
        """
        if not documents:
            return 0
        
        try:
            # Prepare bulk request
            bulk_body = []
            for i, doc in enumerate(documents):
                doc_id = doc.get('id', f"doc_{i}")
                
                # Add index action
                bulk_body.append({
                    "index": {
                        "_index": self.index_name,
                        "_id": doc_id
                    }
                })
                
                # Add document
                bulk_body.append(doc)
            
            # Execute bulk request
            response = self.client.bulk(body=bulk_body)
            
            # Count successful operations
            successful = 0
            for item in response['items']:
                if 'index' in item and item['index'].get('status') in [200, 201]:
                    successful += 1
                elif 'error' in item.get('index', {}):
                    logger.error(f"Bulk index error: {item['index']['error']}")
            
            logger.info(f"Bulk indexed {successful}/{len(documents)} documents")
            return successful
            
        except Exception as e:
            logger.error(f"Bulk indexing failed: {e}")
            return 0
    
    def search_similar(self, query_embedding: List[float], size: int = 10, 
                      filters: Optional[Dict] = None) -> List[Dict]:
        """Search for similar documents using vector similarity.
        
        Args:
            query_embedding: Query vector
            size: Number of results to return
            filters: Optional filters to apply
            
        Returns:
            List of similar documents with scores
        """
        try:
            # Build search query
            search_body = {
                "size": size,
                "query": {
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": size
                        }
                    }
                },
                "_source": {
                    "excludes": ["embedding"]  # Don't return the embedding
                }
            }
            
            # Add filters if provided
            if filters:
                search_body["query"] = {
                    "bool": {
                        "must": [search_body["query"]],
                        "filter": [{"terms": filters}]
                    }
                }
            
            # Execute search
            response = self.client.search(
                index=self.index_name,
                body=search_body
            )
            
            # Process results
            results = []
            for hit in response['hits']['hits']:
                result = {
                    'id': hit['_id'],
                    'score': hit['_score'],
                    'source': hit['_source']
                }
                results.append(result)
            
            logger.debug(f"Found {len(results)} similar documents")
            return results
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            return []
    
    def hybrid_search(self, query_text: str, query_embedding: List[float], 
                     size: int = 10, alpha: float = 0.7) -> List[Dict]:
        """Perform hybrid search combining text and vector similarity.
        
        Args:
            query_text: Text query for keyword search
            query_embedding: Query vector for semantic search
            size: Number of results to return
            alpha: Weight for vector search (0-1, higher = more semantic)
            
        Returns:
            List of search results with combined scores
        """
        try:
            search_body = {
                "size": size,
                "query": {
                    "bool": {
                        "should": [
                            {
                                "multi_match": {
                                    "query": query_text,
                                    "fields": [
                                        "sql_query^2", 
                                        "business_context^1.5",
                                        "context_before",
                                        "context_after"
                                    ],
                                    "type": "best_fields",
                                    "boost": 1 - alpha
                                }
                            },
                            {
                                "knn": {
                                    "embedding": {
                                        "vector": query_embedding,
                                        "k": size,
                                        "boost": alpha
                                    }
                                }
                            }
                        ]
                    }
                },
                "_source": {
                    "excludes": ["embedding"]
                }
            }
            
            response = self.client.search(
                index=self.index_name,
                body=search_body
            )
            
            results = []
            for hit in response['hits']['hits']:
                result = {
                    'id': hit['_id'],
                    'score': hit['_score'],
                    'source': hit['_source']
                }
                results.append(result)
            
            logger.debug(f"Hybrid search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    def get_document(self, doc_id: str) -> Optional[Dict]:
        """Get a document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document or None if not found
        """
        try:
            response = self.client.get(
                index=self.index_name,
                id=doc_id
            )
            return response['_source']
            
        except Exception as e:
            logger.debug(f"Document not found: {doc_id}")
            return None
    
    def delete_index(self) -> bool:
        """Delete the knowledge base index.
        
        Returns:
            True if deletion was successful
        """
        try:
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
                logger.info(f"Deleted index: {self.index_name}")
                return True
            else:
                logger.info(f"Index does not exist: {self.index_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete index: {e}")
            return False
    
    def get_index_stats(self) -> Dict:
        """Get statistics about the index.
        
        Returns:
            Index statistics
        """
        try:
            stats = self.client.indices.stats(index=self.index_name)
            return {
                'document_count': stats['indices'][self.index_name]['total']['docs']['count'],
                'index_size': stats['indices'][self.index_name]['total']['store']['size_in_bytes'],
                'status': 'healthy'
            }
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return {'status': 'error', 'error': str(e)}