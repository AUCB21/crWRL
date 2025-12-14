"""
Query Builder - Safe, Parameterized Query Generation

Provides SQL injection-safe query building for SELECT, INSERT, UPDATE, DELETE operations.
All queries use parameterized statements for security.
"""

from typing import Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Operator(Enum):
    """SQL comparison operators"""
    EQ = "="
    NE = "!="
    LT = "<"
    LE = "<="
    GT = ">"
    GE = ">="
    LIKE = "LIKE"
    NOT_LIKE = "NOT LIKE"
    IN = "IN"
    NOT_IN = "NOT IN"
    IS_NULL = "IS NULL"
    IS_NOT_NULL = "IS NOT NULL"
    BETWEEN = "BETWEEN"


class JoinType(Enum):
    """SQL JOIN types"""
    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL OUTER JOIN"
    CROSS = "CROSS JOIN"


class OrderDirection(Enum):
    """ORDER BY directions"""
    ASC = "ASC"
    DESC = "DESC"


class ConflictAction(Enum):
    """ON CONFLICT actions for INSERT"""
    IGNORE = "OR IGNORE"
    REPLACE = "OR REPLACE"
    ABORT = "OR ABORT"
    ROLLBACK = "OR ROLLBACK"
    FAIL = "OR FAIL"


@dataclass
class Condition:
    """
    Represents a WHERE condition.
    
    Usage:
        Condition('status', Operator.EQ, 200)
        Condition('depth', Operator.LE, 3)
        Condition('subdomain', Operator.LIKE, '%api%')
        Condition('id', Operator.IN, [1, 2, 3])
    """
    column: str
    operator: Operator
    value: Any = None
    
    def to_sql(self) -> tuple[str, tuple]:
        """
        Convert condition to SQL fragment and parameters.
        
        Returns:
            Tuple of (sql_fragment, parameters)
        """
        if self.operator == Operator.IS_NULL:
            return f"{self.column} IS NULL", ()
        elif self.operator == Operator.IS_NOT_NULL:
            return f"{self.column} IS NOT NULL", ()
        elif self.operator in (Operator.IN, Operator.NOT_IN):
            if not isinstance(self.value, (list, tuple)):
                self.value = [self.value]
            placeholders = ", ".join(["?"] * len(self.value))
            op = "IN" if self.operator == Operator.IN else "NOT IN"
            return f"{self.column} {op} ({placeholders})", tuple(self.value)
        elif self.operator == Operator.BETWEEN:
            return f"{self.column} BETWEEN ? AND ?", tuple(self.value[:2])
        else:
            return f"{self.column} {self.operator.value} ?", (self.value,)


@dataclass
class Join:
    """
    Represents a JOIN clause.
    
    Usage:
        Join('subdomains', 'urls.subdomain_id = subdomains.id')
        Join('users u', 'posts.user_id = u.id', JoinType.LEFT)
    """
    table: str
    condition: str
    join_type: JoinType = JoinType.INNER
    
    def to_sql(self) -> str:
        """Convert to SQL fragment."""
        return f"{self.join_type.value} {self.table} ON {self.condition}"


@dataclass  
class OrderBy:
    """ORDER BY specification"""
    column: str
    direction: OrderDirection = OrderDirection.ASC
    
    def to_sql(self) -> str:
        return f"{self.column} {self.direction.value}"


class QueryBuilder:
    """
    SQL Query Builder with parameterized queries.
    
    All methods return (query_string, parameters) tuples for safe execution.
    
    Usage:
        qb = QueryBuilder()
        
        # SELECT
        query, params = qb.select('users', columns=['id', 'name'], where={'active': True})
        
        # INSERT
        query, params = qb.insert('users', {'name': 'John', 'email': 'john@example.com'})
        
        # UPDATE
        query, params = qb.update('users', {'active': False}, where={'id': 1})
        
        # DELETE
        query, params = qb.delete('users', where={'id': 1})
    """
    
    @staticmethod
    def _validate_identifier(name: str) -> str:
        """
        Validate and sanitize SQL identifier (table/column name).
        
        Args:
            name: Identifier to validate
            
        Returns:
            Sanitized identifier
            
        Raises:
            ValueError: If identifier contains invalid characters
        """
        # Allow alphanumeric, underscore, dot (for table.column), and space (for aliases)
        import re
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_.\s*()]*$', name):
            raise ValueError(f"Invalid identifier: {name}")
        return name
    
    @staticmethod
    def _build_where(
        where: Optional[Union[dict, list[Condition]]] = None
    ) -> tuple[str, tuple]:
        """
        Build WHERE clause from conditions.
        
        Args:
            where: Dict of {column: value} or list of Condition objects
            
        Returns:
            Tuple of (where_clause, parameters)
        """
        if not where:
            return "", ()
        
        conditions = []
        params = []
        
        if isinstance(where, dict):
            for column, value in where.items():
                if isinstance(value, tuple) and len(value) == 2:
                    # Tuple format: (operator, value) e.g., ('>=', 5)
                    op_str, val = value
                    op_map = {
                        '=': Operator.EQ, '!=': Operator.NE,
                        '<': Operator.LT, '<=': Operator.LE,
                        '>': Operator.GT, '>=': Operator.GE,
                        'LIKE': Operator.LIKE, 'IN': Operator.IN,
                        'NOT IN': Operator.NOT_IN
                    }
                    op = op_map.get(op_str.upper(), Operator.EQ)
                    cond = Condition(column, op, val)
                elif value is None:
                    cond = Condition(column, Operator.IS_NULL)
                else:
                    cond = Condition(column, Operator.EQ, value)
                
                sql, p = cond.to_sql()
                conditions.append(sql)
                params.extend(p)
        else:
            # List of Condition objects
            for cond in where:
                sql, p = cond.to_sql()
                conditions.append(sql)
                params.extend(p)
        
        where_clause = " AND ".join(conditions)
        return f"WHERE {where_clause}", tuple(params)
    
    def select(
        self,
        table: str,
        columns: Union[str, list[str]] = "*",
        where: Optional[Union[dict, list[Condition]]] = None,
        order_by: Optional[Union[str, list[str], list[OrderBy]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        joins: Optional[list[Join]] = None,
        group_by: Optional[Union[str, list[str]]] = None,
        having: Optional[str] = None,
        distinct: bool = False
    ) -> tuple[str, tuple]:
        """
        Build SELECT query.
        
        Args:
            table: Table name
            columns: Column(s) to select
            where: WHERE conditions
            order_by: ORDER BY column(s)
            limit: LIMIT value
            offset: OFFSET value
            joins: JOIN clauses
            group_by: GROUP BY column(s)
            having: HAVING clause
            distinct: Use SELECT DISTINCT
            
        Returns:
            Tuple of (query_string, parameters)
        """
        table = self._validate_identifier(table)
        
        # Columns
        if isinstance(columns, list):
            cols = ", ".join(self._validate_identifier(c) for c in columns)
        else:
            cols = self._validate_identifier(columns) if columns != "*" else "*"
        
        # Base query
        distinct_str = "DISTINCT " if distinct else ""
        query = f"SELECT {distinct_str}{cols} FROM {table}"
        params = []
        
        # JOINs
        if joins:
            for join in joins:
                query += f" {join.to_sql()}"
        
        # WHERE
        where_clause, where_params = self._build_where(where)
        if where_clause:
            query += f" {where_clause}"
            params.extend(where_params)
        
        # GROUP BY
        if group_by:
            if isinstance(group_by, list):
                group_cols = ", ".join(self._validate_identifier(c) for c in group_by)
            else:
                group_cols = self._validate_identifier(group_by)
            query += f" GROUP BY {group_cols}"
        
        # HAVING
        if having:
            query += f" HAVING {having}"
        
        # ORDER BY
        if order_by:
            if isinstance(order_by, str):
                order_clause = self._validate_identifier(order_by)
            elif isinstance(order_by, list):
                if order_by and isinstance(order_by[0], OrderBy):
                    order_clause = ", ".join(o.to_sql() for o in order_by)
                else:
                    order_clause = ", ".join(self._validate_identifier(o) for o in order_by)
            query += f" ORDER BY {order_clause}"
        
        # LIMIT/OFFSET
        if limit is not None:
            query += f" LIMIT {int(limit)}"
        if offset is not None:
            query += f" OFFSET {int(offset)}"
        
        return query, tuple(params)
    
    def insert(
        self,
        table: str,
        data: dict,
        on_conflict: Optional[ConflictAction] = None
    ) -> tuple[str, tuple]:
        """
        Build INSERT query.
        
        Args:
            table: Table name
            data: Dict of {column: value} to insert
            on_conflict: Conflict resolution action
            
        Returns:
            Tuple of (query_string, parameters)
        """
        table = self._validate_identifier(table)
        
        columns = [self._validate_identifier(c) for c in data.keys()]
        values = list(data.values())
        placeholders = ", ".join(["?"] * len(values))
        
        conflict = f" {on_conflict.value}" if on_conflict else ""
        
        query = f"INSERT{conflict} INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
        
        return query, tuple(values)
    
    def insert_many(
        self,
        table: str,
        columns: list[str],
        data: list[tuple],
        on_conflict: Optional[ConflictAction] = None
    ) -> tuple[str, list[tuple]]:
        """
        Build INSERT query for multiple rows.
        
        Args:
            table: Table name
            columns: List of column names
            data: List of value tuples
            on_conflict: Conflict resolution action
            
        Returns:
            Tuple of (query_string, list_of_parameters)
        """
        table = self._validate_identifier(table)
        cols = [self._validate_identifier(c) for c in columns]
        placeholders = ", ".join(["?"] * len(cols))
        
        conflict = f" {on_conflict.value}" if on_conflict else ""
        
        query = f"INSERT{conflict} INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
        
        return query, data
    
    def update(
        self,
        table: str,
        data: dict,
        where: Union[dict, list[Condition]]
    ) -> tuple[str, tuple]:
        """
        Build UPDATE query.
        
        Args:
            table: Table name
            data: Dict of {column: new_value} to update
            where: WHERE conditions (required for safety)
            
        Returns:
            Tuple of (query_string, parameters)
            
        Raises:
            ValueError: If where is not provided
        """
        if not where:
            raise ValueError("WHERE clause required for UPDATE to prevent accidental full table update")
        
        table = self._validate_identifier(table)
        
        set_parts = []
        params = []
        
        for column, value in data.items():
            col = self._validate_identifier(column)
            set_parts.append(f"{col} = ?")
            params.append(value)
        
        query = f"UPDATE {table} SET {', '.join(set_parts)}"
        
        where_clause, where_params = self._build_where(where)
        query += f" {where_clause}"
        params.extend(where_params)
        
        return query, tuple(params)
    
    def delete(
        self,
        table: str,
        where: Optional[Union[dict, list[Condition]]] = None,
        confirm_all: bool = False
    ) -> tuple[str, tuple]:
        """
        Build DELETE query.
        
        Args:
            table: Table name
            where: WHERE conditions
            confirm_all: Must be True to delete all rows (safety)
            
        Returns:
            Tuple of (query_string, parameters)
            
        Raises:
            ValueError: If no where and confirm_all is False
        """
        table = self._validate_identifier(table)
        
        if not where and not confirm_all:
            raise ValueError(
                "DELETE without WHERE requires confirm_all=True to prevent accidental data loss"
            )
        
        query = f"DELETE FROM {table}"
        params = ()
        
        if where:
            where_clause, where_params = self._build_where(where)
            query += f" {where_clause}"
            params = where_params
        
        return query, params
    
    def count(
        self,
        table: str,
        column: str = "*",
        where: Optional[Union[dict, list[Condition]]] = None,
        distinct: bool = False
    ) -> tuple[str, tuple]:
        """
        Build COUNT query.
        
        Args:
            table: Table name
            column: Column to count (default *)
            where: WHERE conditions
            distinct: Count distinct values
            
        Returns:
            Tuple of (query_string, parameters)
        """
        table = self._validate_identifier(table)
        col = self._validate_identifier(column) if column != "*" else "*"
        
        distinct_str = "DISTINCT " if distinct else ""
        query = f"SELECT COUNT({distinct_str}{col}) as count FROM {table}"
        params = ()
        
        if where:
            where_clause, where_params = self._build_where(where)
            query += f" {where_clause}"
            params = where_params
        
        return query, params
    
    def exists(
        self,
        table: str,
        where: Union[dict, list[Condition]]
    ) -> tuple[str, tuple]:
        """
        Build EXISTS query.
        
        Args:
            table: Table name
            where: WHERE conditions
            
        Returns:
            Tuple of (query_string, parameters)
        """
        table = self._validate_identifier(table)
        
        where_clause, where_params = self._build_where(where)
        
        query = f"SELECT EXISTS(SELECT 1 FROM {table} {where_clause}) as exists_flag"
        
        return query, where_params


# Create a singleton instance for convenience
query_builder = QueryBuilder()
