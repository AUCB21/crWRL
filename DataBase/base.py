"""
Database Abstraction Layer - Base Classes

Provides abstract base class for database implementations.
Supports SQLite and PostgreSQL with a unified interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Union
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """Supported database types"""
    SQLITE = "sqlite"
    POSTGRES = "postgres"


@dataclass
class ColumnInfo:
    """Column metadata"""
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    default: Any = None
    unique: bool = False


@dataclass
class ForeignKey:
    """Foreign key constraint definition"""
    column: str
    reference_table: str
    reference_column: str
    on_delete: str = "CASCADE"
    on_update: str = "CASCADE"


@dataclass
class IndexInfo:
    """Index metadata"""
    name: str
    columns: list[str]
    unique: bool = False


@dataclass
class TableMetadata:
    """Complete table metadata"""
    name: str
    columns: list[ColumnInfo]
    primary_keys: list[str]
    foreign_keys: list[ForeignKey]
    indexes: list[IndexInfo]


class DatabaseConfig(ABC):
    """
    Abstract base class for database configuration and operations.
    
    All database implementations must inherit from this class
    and implement the abstract methods.
    """
    
    def __init__(self):
        self.connection = None
        self._connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the database.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass
    
    @abstractmethod
    def execute(self, query: str, params: Optional[tuple] = None) -> Any:
        """
        Execute a query with optional parameters.
        
        Args:
            query: SQL query string with placeholders
            params: Optional tuple of parameters for the query
            
        Returns:
            Query result or None
        """
        pass
    
    @abstractmethod
    def execute_many(self, query: str, params_list: list[tuple]) -> int:
        """
        Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query string with placeholders
            params_list: List of parameter tuples
            
        Returns:
            Number of affected rows
        """
        pass
    
    @abstractmethod
    def fetch_all(self, query: str, params: Optional[tuple] = None) -> list[tuple]:
        """
        Execute query and fetch all results.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            List of result tuples
        """
        pass
    
    @abstractmethod
    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[tuple]:
        """
        Execute query and fetch single result.
        
        Args:
            query: SQL query string
            params: Optional query parameters
            
        Returns:
            Single result tuple or None
        """
        pass
    
    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin a transaction."""
        pass
    
    @abstractmethod
    def commit(self) -> None:
        """Commit current transaction."""
        pass
    
    @abstractmethod
    def rollback(self) -> None:
        """Rollback current transaction."""
        pass
    
    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._connected
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is not None:
            self.rollback()
        self.close()
        return False


class DatabaseFactory:
    """
    Factory for creating database instances.
    
    Usage:
        db = DatabaseFactory.create('sqlite', db_path='my_database.db')
        db = DatabaseFactory.create('postgres', host='localhost', port=5432, ...)
    """
    
    _registry: dict[str, type] = {}
    
    @classmethod
    def register(cls, db_type: str, db_class: type) -> None:
        """Register a database implementation."""
        cls._registry[db_type.lower()] = db_class
    
    @classmethod
    def create(cls, db_type: str, **kwargs) -> DatabaseConfig:
        """
        Create a database instance.
        
        Args:
            db_type: Type of database ('sqlite', 'postgres')
            **kwargs: Database-specific configuration parameters
            
        Returns:
            DatabaseConfig instance
            
        Raises:
            ValueError: If db_type is not registered
        """
        db_type = db_type.lower()
        if db_type not in cls._registry:
            available = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unknown database type: '{db_type}'. "
                f"Available types: {available}"
            )
        return cls._registry[db_type](**kwargs)
    
    @classmethod
    def available_types(cls) -> list[str]:
        """Get list of available database types."""
        return list(cls._registry.keys())
