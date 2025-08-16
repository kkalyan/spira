"""AWS Glue Catalog metadata extraction."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from .config import GlueCatalogConfig

logger = logging.getLogger(__name__)


@dataclass
class ColumnMetadata:
    """Metadata for a table column."""
    name: str
    type: str
    comment: Optional[str] = None
    is_partition: bool = False


@dataclass
class TableMetadata:
    """Metadata for a Glue table."""
    database: str
    name: str
    description: Optional[str]
    columns: List[ColumnMetadata]
    partition_keys: List[ColumnMetadata]
    location: Optional[str]
    input_format: Optional[str]
    output_format: Optional[str]
    table_type: Optional[str]
    parameters: Dict[str, str]
    last_analyzed_time: Optional[str] = None
    last_access_time: Optional[str] = None


class GlueCatalogExtractor:
    """Extracts metadata from AWS Glue Catalog."""
    
    def __init__(self, config: GlueCatalogConfig):
        """Initialize the Glue catalog extractor.
        
        Args:
            config: Glue catalog configuration
        """
        self.config = config
        self.session = self._create_session()
        self.glue_client = self.session.client('glue', region_name=config.region)
    
    def _create_session(self) -> boto3.Session:
        """Create boto3 session with appropriate credentials."""
        session = boto3.Session()
        
        if self.config.cross_account_role_arn:
            # Assume cross-account role
            sts_client = session.client('sts')
            try:
                assumed_role = sts_client.assume_role(
                    RoleArn=self.config.cross_account_role_arn,
                    RoleSessionName='text2sql-rag-glue-access'
                )
                credentials = assumed_role['Credentials']
                session = boto3.Session(
                    aws_access_key_id=credentials['AccessKeyId'],
                    aws_secret_access_key=credentials['SecretAccessKey'],
                    aws_session_token=credentials['SessionToken']
                )
                logger.info(f"Assumed cross-account role: {self.config.cross_account_role_arn}")
            except ClientError as e:
                logger.error(f"Failed to assume cross-account role: {e}")
                raise
        
        return session
    
    def get_databases(self) -> List[str]:
        """Get list of databases from Glue catalog.
        
        Returns:
            List of database names
        """
        databases = []
        paginator = self.glue_client.get_paginator('get_databases')
        
        try:
            for page in paginator.paginate():
                for db in page['DatabaseList']:
                    databases.append(db['Name'])
            
            logger.info(f"Found {len(databases)} databases in Glue catalog")
            return databases
            
        except ClientError as e:
            logger.error(f"Failed to get databases: {e}")
            raise
    
    def get_tables_for_database(self, database_name: str) -> List[str]:
        """Get list of tables for a specific database.
        
        Args:
            database_name: Name of the database
            
        Returns:
            List of table names
        """
        tables = []
        paginator = self.glue_client.get_paginator('get_tables')
        
        try:
            for page in paginator.paginate(DatabaseName=database_name):
                for table in page['TableList']:
                    tables.append(table['Name'])
            
            logger.info(f"Found {len(tables)} tables in database {database_name}")
            return tables
            
        except ClientError as e:
            logger.error(f"Failed to get tables for database {database_name}: {e}")
            raise
    
    def get_table_metadata(self, database_name: str, table_name: str) -> Optional[TableMetadata]:
        """Get detailed metadata for a specific table.
        
        Args:
            database_name: Name of the database
            table_name: Name of the table
            
        Returns:
            Table metadata or None if not found
        """
        try:
            response = self.glue_client.get_table(
                DatabaseName=database_name,
                Name=table_name
            )
            
            table = response['Table']
            storage_descriptor = table.get('StorageDescriptor', {})
            
            # Extract column metadata
            columns = []
            for col in storage_descriptor.get('Columns', []):
                columns.append(ColumnMetadata(
                    name=col['Name'],
                    type=col['Type'],
                    comment=col.get('Comment')
                ))
            
            # Extract partition keys
            partition_keys = []
            for key in table.get('PartitionKeys', []):
                partition_key = ColumnMetadata(
                    name=key['Name'],
                    type=key['Type'],
                    comment=key.get('Comment'),
                    is_partition=True
                )
                partition_keys.append(partition_key)
            
            return TableMetadata(
                database=database_name,
                name=table_name,
                description=table.get('Description'),
                columns=columns,
                partition_keys=partition_keys,
                location=storage_descriptor.get('Location'),
                input_format=storage_descriptor.get('InputFormat'),
                output_format=storage_descriptor.get('OutputFormat'),
                table_type=table.get('TableType'),
                parameters=table.get('Parameters', {}),
                last_analyzed_time=table.get('LastAnalyzedTime'),
                last_access_time=table.get('LastAccessTime')
            )
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityNotFoundException':
                logger.warning(f"Table not found: {database_name}.{table_name}")
                return None
            else:
                logger.error(f"Failed to get table metadata for {database_name}.{table_name}: {e}")
                raise
    
    def extract_metadata(self, max_workers: int = 10) -> Dict[str, TableMetadata]:
        """Extract metadata for all configured tables and databases.
        
        Args:
            max_workers: Maximum number of parallel workers
            
        Returns:
            Dictionary mapping table names to metadata
        """
        table_list = self._get_target_tables()
        metadata = {}
        
        logger.info(f"Extracting metadata for {len(table_list)} tables using {max_workers} workers")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all table metadata extraction tasks
            future_to_table = {
                executor.submit(self.get_table_metadata, db, table): (db, table)
                for db, table in table_list
            }
            
            for future in as_completed(future_to_table):
                db, table = future_to_table[future]
                try:
                    table_metadata = future.result()
                    if table_metadata:
                        key = f"{db}.{table}"
                        metadata[key] = table_metadata
                        logger.debug(f"Extracted metadata for {key}")
                except Exception as e:
                    logger.error(f"Failed to extract metadata for {db}.{table}: {e}")
        
        logger.info(f"Successfully extracted metadata for {len(metadata)} tables")
        return metadata
    
    def _get_target_tables(self) -> List[tuple[str, str]]:
        """Get list of target tables to extract metadata for.
        
        Returns:
            List of (database, table) tuples
        """
        table_list = []
        
        # Handle specific tables
        if self.config.tables:
            for table_spec in self.config.tables:
                if '.' in table_spec:
                    db, table = table_spec.split('.', 1)
                    table_list.append((db, table))
                else:
                    logger.warning(f"Invalid table specification: {table_spec}. Expected format: database.table")
        
        # Handle databases
        if self.config.databases:
            for database in self.config.databases:
                try:
                    tables = self.get_tables_for_database(database)
                    for table in tables:
                        table_list.append((database, table))
                except Exception as e:
                    logger.error(f"Failed to get tables for database {database}: {e}")
        
        # Remove duplicates
        table_list = list(set(table_list))
        logger.info(f"Target tables identified: {len(table_list)}")
        
        return table_list
    
    def format_schema_context(self, metadata: Dict[str, TableMetadata]) -> str:
        """Format table metadata as context for LLM.
        
        Args:
            metadata: Dictionary of table metadata
            
        Returns:
            Formatted schema context string
        """
        context_parts = []
        
        for table_key, table_meta in metadata.items():
            context_parts.append(f"\n## Table: {table_key}")
            
            if table_meta.description:
                context_parts.append(f"Description: {table_meta.description}")
            
            # Format columns
            context_parts.append("Columns:")
            for col in table_meta.columns:
                col_info = f"  - {col.name} ({col.type})"
                if col.comment:
                    col_info += f" - {col.comment}"
                context_parts.append(col_info)
            
            # Format partition keys
            if table_meta.partition_keys:
                context_parts.append("Partition Keys:")
                for key in table_meta.partition_keys:
                    key_info = f"  - {key.name} ({key.type})"
                    if key.comment:
                        key_info += f" - {key.comment}"
                    context_parts.append(key_info)
        
        return "\n".join(context_parts)