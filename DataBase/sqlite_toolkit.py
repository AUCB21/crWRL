"""
SQLite Database Implementation

Provides SQLite-specific database operations with full CRUD support.
"""

import sqlite3
from pathlib import Path
from typing import Any, Optional
import logging
import threading

from .base import DatabaseConfig, DatabaseFactory

logger = logging.getLogger(__name__)


class SQLiteConfig(DatabaseConfig):
    """
    SQLite database configuration and operations.
    
    Usage:
        db = SQLiteConfig('my_database.db')
        db.connect()
        results = db.fetch_all("SELECT * FROM users WHERE active = ?", (1,))
        db.close()
        
    Or with context manager:
        with SQLiteConfig('my_database.db') as db:
            results = db.fetch_all("SELECT * FROM users")
    """
    
    def __init__(
        self,
        db_path: str = ":memory:",
        timeout: float = 30.0,
        check_same_thread: bool = False,
        isolation_level: Optional[str] = None
    ):
        """
        Initialize SQLite configuration.
        
        Args:
            db_path: Path to SQLite database file or ':memory:' for in-memory
            timeout: How long to wait for locks (seconds)
            check_same_thread: If True, only creating thread can use connection
            isolation_level: Transaction isolation level (None for autocommit)
        """
        # Initialize _local BEFORE calling super().__init__() 
        # because parent will try to set self.connection = None
        self._local = threading.local()
        
        super().__init__()
        self.db_path = db_path
        self.timeout = timeout
        self.check_same_thread = check_same_thread
        self.isolation_level = isolation_level
    
    @property
    def connection(self):
        """Thread-local connection."""
        return getattr(self._local, 'connection', None)
    
    @connection.setter
    def connection(self, value):
        self._local.connection = value
    
    def connect(self) -> bool:
        """
        Establish connection to SQLite database.
        
        Returns:
            bool: True if connection successful
        """
        try:
            # Create directory if needed (for file-based db)
            if self.db_path != ":memory:":
                db_dir = Path(self.db_path).parent
                db_dir.mkdir(parents=True, exist_ok=True)
            
            self.connection = sqlite3.connect(
                self.db_path,
                timeout=self.timeout,
                check_same_thread=self.check_same_thread,
                isolation_level=self.isolation_level
            )
            
            # Enable foreign keys
            self.connection.execute("PRAGMA foreign_keys = ON")
            
            # Return rows as Row objects for dict-like access
            self.connection.row_factory = sqlite3.Row
            
            self._connected = True
            logger.info(f"Connected to SQLite database: {self.db_path}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            self._connected = False
            return False
    
    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            try:
                self.connection.close()
                self._connected = False
                logger.info(f"Closed SQLite connection: {self.db_path}")
            except sqlite3.Error as e:
                logger.error(f"Error closing SQLite connection: {e}")
            finally:
                self.connection = None
    
    def execute(self, query: str, params: Optional[tuple] = None) -> sqlite3.Cursor:
        """
        Execute a query with optional parameters.
        
        Args:
            query: SQL query with ? placeholders
            params: Optional tuple of parameters
            
        Returns:
            Cursor object
        """
        if not self.is_connected:
            raise ConnectionError("Database not connected. Call connect() first.")
        
        try:
            cursor = self.connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor
        except sqlite3.Error as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise
    
    def execute_many(self, query: str, params_list: list[tuple]) -> int:
        """
        Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query with ? placeholders
            params_list: List of parameter tuples
            
        Returns:
            Number of affected rows
        """
        if not self.is_connected:
            raise ConnectionError("Database not connected. Call connect() first.")
        
        try:
            cursor = self.connection.cursor()
            cursor.executemany(query, params_list)
            return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"Batch execution failed: {e}\nQuery: {query}")
            raise
    
    def fetch_all(self, query: str, params: Optional[tuple] = None) -> list[sqlite3.Row]:
        """
        Execute query and fetch all results.
        
        Args:
            query: SQL query
            params: Optional query parameters
            
        Returns:
            List of Row objects (dict-like access)
        """
        cursor = self.execute(query, params)
        return cursor.fetchall()
    
    def fetch_one(self, query: str, params: Optional[tuple] = None) -> Optional[sqlite3.Row]:
        """
        Execute query and fetch single result.
        
        Args:
            query: SQL query
            params: Optional query parameters
            
        Returns:
            Single Row object or None
        """
        cursor = self.execute(query, params)
        return cursor.fetchone()
    
    def begin_transaction(self) -> None:
        """Begin a transaction."""
        if self.is_connected:
            self.execute("BEGIN TRANSACTION")
    
    def commit(self) -> None:
        """Commit current transaction."""
        if self.connection:
            self.connection.commit()
    
    def rollback(self) -> None:
        """Rollback current transaction."""
        if self.connection:
            self.connection.rollback()
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists
        """
        query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """
        result = self.fetch_one(query, (table_name,))
        return result is not None
    
    def get_tables(self) -> list[str]:
        """
        Get list of all tables in the database.
        
        Returns:
            List of table names
        """
        query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """
        results = self.fetch_all(query)
        return [row['name'] for row in results]
    
    def get_table_info(self, table_name: str) -> list[dict]:
        """
        Get column information for a table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column info dictionaries
        """
        query = f"PRAGMA table_info({table_name})"
        results = self.fetch_all(query)
        return [
            {
                'cid': row['cid'],
                'name': row['name'],
                'type': row['type'],
                'notnull': bool(row['notnull']),
                'default': row['dflt_value'],
                'pk': bool(row['pk'])
            }
            for row in results
        ]
    
    def vacuum(self) -> None:
        """Optimize database by reclaiming unused space."""
        self.execute("VACUUM")
        self.commit()
    
    @property
    def last_insert_id(self) -> int:
        """Get the ID of the last inserted row."""
        if self.connection:
            return self.connection.execute("SELECT last_insert_rowid()").fetchone()[0]
        return 0


# Register SQLite with the factory
DatabaseFactory.register('sqlite', SQLiteConfig)
