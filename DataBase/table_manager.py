"""
Table Manager - Table DDL Operations

Provides CREATE, DROP, ALTER table operations with SQLite compatibility.
"""

from typing import Any, Optional, Union
from dataclasses import dataclass
import logging
import re

from .base import DatabaseConfig, ForeignKey, ColumnInfo, IndexInfo

logger = logging.getLogger(__name__)


@dataclass
class Column:
    """
    Column definition for CREATE TABLE.
    
    Usage:
        Column('id', 'INTEGER', primary_key=True, autoincrement=True)
        Column('url', 'TEXT', nullable=False, unique=True)
        Column('created_at', 'TIMESTAMP', default='CURRENT_TIMESTAMP')
    """
    name: str
    data_type: str
    primary_key: bool = False
    autoincrement: bool = False
    nullable: bool = True
    unique: bool = False
    default: Any = None
    check: Optional[str] = None
    
    def to_sql(self) -> str:
        """Convert column to SQL definition."""
        parts = [self.name, self.data_type]
        
        if self.primary_key:
            parts.append("PRIMARY KEY")
            if self.autoincrement:
                parts.append("AUTOINCREMENT")
        
        if not self.nullable and not self.primary_key:
            parts.append("NOT NULL")
        
        if self.unique and not self.primary_key:
            parts.append("UNIQUE")
        
        if self.default is not None:
            if isinstance(self.default, str) and not self.default.upper().startswith(('CURRENT_', '(')):
                parts.append(f"DEFAULT '{self.default}'")
            else:
                parts.append(f"DEFAULT {self.default}")
        
        if self.check:
            parts.append(f"CHECK ({self.check})")
        
        return " ".join(parts)


class TableManager:
    """
    Table management operations (CREATE, DROP, ALTER).
    
    Usage:
        db = SQLiteConfig('database.db')
        db.connect()
        tm = TableManager(db)
        
        # Create table
        tm.create_table('users', {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'name': 'TEXT NOT NULL',
            'email': 'TEXT UNIQUE'
        })
        
        # Drop table
        tm.drop_table('users')
        
        # Add column
        tm.add_column('users', 'phone', 'TEXT')
    """
    
    def __init__(self, db: DatabaseConfig):
        """
        Initialize TableManager with a database connection.
        
        Args:
            db: Database configuration instance (must be connected)
        """
        self.db = db
    
    @staticmethod
    def _validate_name(name: str) -> str:
        """Validate SQL identifier name."""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
            raise ValueError(f"Invalid identifier name: {name}")
        return name
    
    def create_table(
        self,
        table_name: str,
        columns: Union[dict[str, str], list[Column]],
        primary_key: Optional[Union[str, list[str]]] = None,
        foreign_keys: Optional[list[ForeignKey]] = None,
        unique_constraints: Optional[list[Union[str, list[str]]]] = None,
        indexes: Optional[list[IndexInfo]] = None,
        if_not_exists: bool = True,
        strict: bool = False
    ) -> bool:
        """
        Create a new table.
        
        Args:
            table_name: Name of the table
            columns: Dict of {name: type} or list of Column objects
            primary_key: Column(s) for composite primary key
            foreign_keys: List of foreign key constraints
            unique_constraints: Columns with unique constraints
            indexes: Indexes to create
            if_not_exists: Add IF NOT EXISTS clause
            strict: Use STRICT table mode (SQLite 3.37+)
            
        Returns:
            True if successful
        """
        table_name = self._validate_name(table_name)
        
        # Build column definitions
        col_defs = []
        if isinstance(columns, dict):
            for name, definition in columns.items():
                name = self._validate_name(name)
                col_defs.append(f"{name} {definition}")
        else:
            for col in columns:
                col_defs.append(col.to_sql())
        
        # Composite primary key
        if primary_key:
            if isinstance(primary_key, str):
                primary_key = [primary_key]
            pk_cols = ", ".join(self._validate_name(c) for c in primary_key)
            col_defs.append(f"PRIMARY KEY ({pk_cols})")
        
        # Foreign keys
        if foreign_keys:
            for fk in foreign_keys:
                fk_sql = (
                    f"FOREIGN KEY ({self._validate_name(fk.column)}) "
                    f"REFERENCES {self._validate_name(fk.reference_table)}"
                    f"({self._validate_name(fk.reference_column)}) "
                    f"ON DELETE {fk.on_delete} ON UPDATE {fk.on_update}"
                )
                col_defs.append(fk_sql)
        
        # Unique constraints
        if unique_constraints:
            for uc in unique_constraints:
                if isinstance(uc, str):
                    uc = [uc]
                uc_cols = ", ".join(self._validate_name(c) for c in uc)
                col_defs.append(f"UNIQUE ({uc_cols})")
        
        # Build CREATE TABLE statement
        exists_clause = "IF NOT EXISTS " if if_not_exists else ""
        strict_clause = " STRICT" if strict else ""
        
        query = f"CREATE TABLE {exists_clause}{table_name} ({', '.join(col_defs)}){strict_clause}"
        
        try:
            self.db.execute(query)
            self.db.commit()
            logger.info(f"Created table: {table_name}")
            
            # Create indexes
            if indexes:
                for idx in indexes:
                    self.create_index(table_name, idx.name, idx.columns, idx.unique)
            
            return True
        except Exception as e:
            logger.error(f"Failed to create table {table_name}: {e}")
            raise
    
    def drop_table(
        self,
        table_name: str,
        if_exists: bool = True,
        cascade: bool = False
    ) -> bool:
        """
        Drop a table.
        
        Args:
            table_name: Name of the table to drop
            if_exists: Add IF EXISTS clause
            cascade: Note: SQLite doesn't support CASCADE, included for compatibility
            
        Returns:
            True if successful
        """
        table_name = self._validate_name(table_name)
        exists_clause = "IF EXISTS " if if_exists else ""
        
        query = f"DROP TABLE {exists_clause}{table_name}"
        
        try:
            self.db.execute(query)
            self.db.commit()
            logger.info(f"Dropped table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop table {table_name}: {e}")
            raise
    
    def add_column(
        self,
        table_name: str,
        column_name: str,
        data_type: str,
        default: Any = None,
        nullable: bool = True
    ) -> bool:
        """
        Add a column to an existing table.
        
        Args:
            table_name: Table to modify
            column_name: New column name
            data_type: Column data type
            default: Default value
            nullable: Allow NULL values
            
        Returns:
            True if successful
        """
        table_name = self._validate_name(table_name)
        column_name = self._validate_name(column_name)
        
        parts = [f"ALTER TABLE {table_name} ADD COLUMN {column_name} {data_type}"]
        
        if not nullable:
            parts.append("NOT NULL")
        
        if default is not None:
            if isinstance(default, str) and not default.upper().startswith(('CURRENT_', '(')):
                parts.append(f"DEFAULT '{default}'")
            else:
                parts.append(f"DEFAULT {default}")
        
        query = " ".join(parts)
        
        try:
            self.db.execute(query)
            self.db.commit()
            logger.info(f"Added column {column_name} to {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add column: {e}")
            raise
    
    def drop_column(self, table_name: str, column_name: str) -> bool:
        """
        Drop a column from a table.
        
        Note: SQLite 3.35+ supports ALTER TABLE DROP COLUMN.
        For older versions, this requires table recreation.
        
        Args:
            table_name: Table to modify
            column_name: Column to drop
            
        Returns:
            True if successful
        """
        table_name = self._validate_name(table_name)
        column_name = self._validate_name(column_name)
        
        query = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
        
        try:
            self.db.execute(query)
            self.db.commit()
            logger.info(f"Dropped column {column_name} from {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop column (may require SQLite 3.35+): {e}")
            raise
    
    def rename_table(self, old_name: str, new_name: str) -> bool:
        """
        Rename a table.
        
        Args:
            old_name: Current table name
            new_name: New table name
            
        Returns:
            True if successful
        """
        old_name = self._validate_name(old_name)
        new_name = self._validate_name(new_name)
        
        query = f"ALTER TABLE {old_name} RENAME TO {new_name}"
        
        try:
            self.db.execute(query)
            self.db.commit()
            logger.info(f"Renamed table {old_name} to {new_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename table: {e}")
            raise
    
    def rename_column(
        self,
        table_name: str,
        old_column: str,
        new_column: str
    ) -> bool:
        """
        Rename a column.
        
        Note: Requires SQLite 3.25+
        
        Args:
            table_name: Table containing the column
            old_column: Current column name
            new_column: New column name
            
        Returns:
            True if successful
        """
        table_name = self._validate_name(table_name)
        old_column = self._validate_name(old_column)
        new_column = self._validate_name(new_column)
        
        query = f"ALTER TABLE {table_name} RENAME COLUMN {old_column} TO {new_column}"
        
        try:
            self.db.execute(query)
            self.db.commit()
            logger.info(f"Renamed column {old_column} to {new_column} in {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to rename column (requires SQLite 3.25+): {e}")
            raise
    
    def truncate_table(self, table_name: str, vacuum: bool = True) -> bool:
        """
        Delete all rows from a table.
        
        SQLite doesn't have TRUNCATE, so this uses DELETE FROM.
        
        Args:
            table_name: Table to truncate
            vacuum: Run VACUUM after deletion
            
        Returns:
            True if successful
        """
        table_name = self._validate_name(table_name)
        
        try:
            self.db.execute(f"DELETE FROM {table_name}")
            self.db.commit()
            
            if vacuum:
                self.db.execute("VACUUM")
                self.db.commit()
            
            logger.info(f"Truncated table: {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to truncate table: {e}")
            raise
    
    def create_index(
        self,
        table_name: str,
        index_name: str,
        columns: list[str],
        unique: bool = False,
        if_not_exists: bool = True
    ) -> bool:
        """
        Create an index on a table.
        
        Args:
            table_name: Table to index
            index_name: Name for the index
            columns: Columns to include in the index
            unique: Create unique index
            if_not_exists: Add IF NOT EXISTS clause
            
        Returns:
            True if successful
        """
        table_name = self._validate_name(table_name)
        index_name = self._validate_name(index_name)
        cols = ", ".join(self._validate_name(c) for c in columns)
        
        unique_str = "UNIQUE " if unique else ""
        exists_str = "IF NOT EXISTS " if if_not_exists else ""
        
        query = f"CREATE {unique_str}INDEX {exists_str}{index_name} ON {table_name} ({cols})"
        
        try:
            self.db.execute(query)
            self.db.commit()
            logger.info(f"Created index {index_name} on {table_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create index: {e}")
            raise
    
    def drop_index(self, index_name: str, if_exists: bool = True) -> bool:
        """
        Drop an index.
        
        Args:
            index_name: Index to drop
            if_exists: Add IF EXISTS clause
            
        Returns:
            True if successful
        """
        index_name = self._validate_name(index_name)
        exists_str = "IF EXISTS " if if_exists else ""
        
        query = f"DROP INDEX {exists_str}{index_name}"
        
        try:
            self.db.execute(query)
            self.db.commit()
            logger.info(f"Dropped index: {index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to drop index: {e}")
            raise
    
    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        table_name = self._validate_name(table_name)
        
        query = """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """
        result = self.db.fetch_one(query, (table_name,))
        return result is not None
    
    def get_columns(self, table_name: str) -> list[ColumnInfo]:
        """
        Get column information for a table.
        
        Args:
            table_name: Table to inspect
            
        Returns:
            List of ColumnInfo objects
        """
        table_name = self._validate_name(table_name)
        
        query = f"PRAGMA table_info({table_name})"
        results = self.db.fetch_all(query)
        
        return [
            ColumnInfo(
                name=row['name'],
                data_type=row['type'],
                nullable=not bool(row['notnull']),
                primary_key=bool(row['pk']),
                default=row['dflt_value']
            )
            for row in results
        ]
    
    def get_indexes(self, table_name: str) -> list[IndexInfo]:
        """
        Get index information for a table.
        
        Args:
            table_name: Table to inspect
            
        Returns:
            List of IndexInfo objects
        """
        table_name = self._validate_name(table_name)
        
        query = f"PRAGMA index_list({table_name})"
        indexes = self.db.fetch_all(query)
        
        result = []
        for idx in indexes:
            # Get columns in this index
            cols_query = f"PRAGMA index_info({idx['name']})"
            cols = self.db.fetch_all(cols_query)
            
            result.append(IndexInfo(
                name=idx['name'],
                columns=[c['name'] for c in cols],
                unique=bool(idx['unique'])
            ))
        
        return result
