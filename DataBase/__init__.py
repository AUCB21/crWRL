"""
DataBase - SQLite Toolkit for CRWLR

A comprehensive database toolkit supporting SQLite and PostgreSQL
with full CRUD operations, table management, and query building.

Usage:
    from DataBase import SQLiteConfig, QueryBuilder, TableManager
    from DataBase import CrawlDatabaseManager, CrawlSessionConfig, CrawlMetrics
    
    # Direct database access
    db = SQLiteConfig('my_database.db')
    db.connect()
    
    # Query building
    qb = QueryBuilder()
    query, params = qb.select('users', where={'active': True})
    results = db.fetch_all(query, params)
    
    # Table management
    tm = TableManager(db)
    tm.create_table('users', {'id': 'INTEGER PRIMARY KEY', 'name': 'TEXT'})
    
    # CRWLR integration
    with CrawlDatabaseManager('crwlr.db') as db_manager:
        session_id = db_manager.start_session(CrawlSessionConfig(
            target_url='https://example.com'
        ))
        db_manager.log_url(session_id, 'https://example.com/page')
        db_manager.complete_session(session_id, metrics)
"""

# Base classes
from .base import (
    DatabaseConfig,
    DatabaseFactory,
    DatabaseType,
    ColumnInfo,
    ForeignKey,
    IndexInfo,
    TableMetadata
)

# SQLite implementation
from .sqlite_toolkit import SQLiteConfig

# Query building
from .query_builder import (
    QueryBuilder,
    query_builder,
    Condition,
    Operator,
    Join,
    JoinType,
    OrderBy,
    OrderDirection,
    ConflictAction
)

# Table management
from .table_manager import (
    TableManager,
    Column
)

# CRWLR database manager
from .database_manager import (
    CrawlDatabaseManager,
    CrawlSessionConfig,
    CrawlMetrics
)

# Legacy support - keep old imports working
from .config import DB_Config, Schema

__all__ = [
    # Base
    'DatabaseConfig',
    'DatabaseFactory', 
    'DatabaseType',
    'ColumnInfo',
    'ForeignKey',
    'IndexInfo',
    'TableMetadata',
    
    # SQLite
    'SQLiteConfig',
    
    # Query Builder
    'QueryBuilder',
    'query_builder',
    'Condition',
    'Operator',
    'Join',
    'JoinType',
    'OrderBy',
    'OrderDirection',
    'ConflictAction',
    
    # Table Manager
    'TableManager',
    'Column',
    
    # CRWLR Manager
    'CrawlDatabaseManager',
    'CrawlSessionConfig',
    'CrawlMetrics',
    
    # Legacy
    'DB_Config',
    'Schema',
]

__version__ = '1.0.0'
