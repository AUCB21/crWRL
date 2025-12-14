"""
CRWLR Database Manager

High-level database integration for the CRWLR async crawler.
Handles session tracking, URL logging, and statistics.
"""

import time
from typing import Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import json

from .sqlite_toolkit import SQLiteConfig
from .table_manager import TableManager
from .query_builder import QueryBuilder, ConflictAction

logger = logging.getLogger(__name__)


@dataclass
class CrawlSessionConfig:
    """Configuration for a crawl session"""
    target_url: str
    max_depth: int = 3
    workers: int = 5
    rate_limit: float = 0.5
    timeout: int = 5
    user_agent: Optional[str] = None
    proxy: Optional[str] = None


@dataclass
class CrawlMetrics:
    """Metrics for a crawl session"""
    total_time_seconds: float = 0.0
    crawl_time_seconds: float = 0.0
    urls_visited: int = 0
    subdomains_found: int = 0
    paths_found: int = 0
    errors_count: int = 0
    crawl_speed: float = 0.0
    avg_time_per_url: float = 0.0
    discovery_rate: float = 0.0
    completed_normally: bool = True


class CrawlDatabaseManager:
    """
    Database manager for CRWLR crawler.
    
    Provides high-level operations for:
    - Session management
    - URL logging
    - Subdomain tracking
    - Statistics and metrics
    
    Usage:
        db_manager = CrawlDatabaseManager('crwlr.db')
        db_manager.initialize()
        
        # Start a new crawl session
        session_id = db_manager.start_session(CrawlSessionConfig(
            target_url='https://example.com',
            max_depth=3
        ))
        
        # Log discovered URLs and subdomains
        db_manager.log_url(session_id, 'https://example.com/page', depth=1)
        db_manager.log_subdomain(session_id, 'api.example.com')
        
        # Complete the session
        db_manager.complete_session(session_id, metrics)
    """
    
    SCHEMA_VERSION = 1
    
    def __init__(self, db_path: str = "crwlr.db"):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.db = SQLiteConfig(db_path)
        self.qb = QueryBuilder()
        self.tm: Optional[TableManager] = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize the database connection and schema.
        
        Returns:
            True if initialization successful
        """
        try:
            self.db.connect()
            self.tm = TableManager(self.db)
            self._create_schema()
            self._initialized = True
            logger.info(f"CRWLR database initialized: {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False
    
    def close(self) -> None:
        """Close the database connection."""
        if self.db:
            self.db.close()
            self._initialized = False
    
    def _create_schema(self) -> None:
        """Create the database schema if not exists."""
        
        # Crawl sessions table
        self.tm.create_table('crawl_sessions', {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'target_url': 'TEXT NOT NULL',
            'started_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'completed_at': 'TIMESTAMP',
            'max_depth': 'INTEGER DEFAULT 3',
            'workers': 'INTEGER DEFAULT 5',
            'rate_limit': 'REAL DEFAULT 0.5',
            'timeout': 'INTEGER DEFAULT 5',
            'user_agent': 'TEXT',
            'proxy': 'TEXT',
            'status': "TEXT DEFAULT 'running'",
            'error_message': 'TEXT'
        })
        
        # Crawled URLs table
        self.tm.create_table('crawled_urls', {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'session_id': 'INTEGER NOT NULL',
            'url': 'TEXT NOT NULL',
            'normalized_url': 'TEXT',
            'domain': 'TEXT',
            'path': 'TEXT',
            'depth': 'INTEGER DEFAULT 0',
            'status_code': 'INTEGER',
            'content_type': 'TEXT',
            'response_time_ms': 'REAL',
            'discovered_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'error_message': 'TEXT'
        }, unique_constraints=[['session_id', 'url']])
        
        # Subdomains table
        self.tm.create_table('subdomains', {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'session_id': 'INTEGER NOT NULL',
            'subdomain': 'TEXT NOT NULL',
            'base_domain': 'TEXT NOT NULL',
            'first_seen': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
            'url_count': 'INTEGER DEFAULT 0'
        })
        
        # Metrics table
        self.tm.create_table('crawl_metrics', {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'session_id': 'INTEGER NOT NULL UNIQUE',
            'total_time_seconds': 'REAL',
            'crawl_time_seconds': 'REAL',
            'urls_visited': 'INTEGER DEFAULT 0',
            'subdomains_found': 'INTEGER DEFAULT 0',
            'paths_found': 'INTEGER DEFAULT 0',
            'errors_count': 'INTEGER DEFAULT 0',
            'crawl_speed': 'REAL',
            'avg_time_per_url': 'REAL',
            'discovery_rate': 'REAL',
            'completed_normally': 'INTEGER DEFAULT 1'
        })
        
        # Create indexes for performance
        self.tm.create_index('crawled_urls', 'idx_urls_session', ['session_id'])
        self.tm.create_index('crawled_urls', 'idx_urls_domain', ['domain'])
        self.tm.create_index('crawled_urls', 'idx_urls_depth', ['depth'])
        self.tm.create_index('subdomains', 'idx_subdomains_session', ['session_id'])
        self.tm.create_index('subdomains', 'idx_subdomains_domain', ['base_domain'])
        
        logger.info("Database schema created/verified")
    
    def start_session(self, config: CrawlSessionConfig) -> int:
        """
        Start a new crawl session.
        
        Args:
            config: Session configuration
            
        Returns:
            Session ID
        """
        query, params = self.qb.insert('crawl_sessions', {
            'target_url': config.target_url,
            'max_depth': config.max_depth,
            'workers': config.workers,
            'rate_limit': config.rate_limit,
            'timeout': config.timeout,
            'user_agent': config.user_agent,
            'proxy': config.proxy,
            'status': 'running'
        })
        
        self.db.execute(query, params)
        self.db.commit()
        
        session_id = self.db.last_insert_id
        logger.info(f"Started crawl session {session_id} for {config.target_url}")
        
        return session_id
    
    def log_url(
        self,
        session_id: int,
        url: str,
        normalized_url: Optional[str] = None,
        domain: Optional[str] = None,
        path: Optional[str] = None,
        depth: int = 0,
        status_code: Optional[int] = None,
        content_type: Optional[str] = None,
        response_time_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> int:
        """
        Log a crawled URL.
        
        Args:
            session_id: Current session ID
            url: The URL that was crawled
            normalized_url: Normalized version of URL
            domain: Domain of the URL
            path: Path portion of URL
            depth: Crawl depth
            status_code: HTTP response code
            content_type: Content-Type header
            response_time_ms: Response time in milliseconds
            error_message: Error if request failed
            
        Returns:
            URL record ID
        """
        query, params = self.qb.insert('crawled_urls', {
            'session_id': session_id,
            'url': url,
            'normalized_url': normalized_url or url,
            'domain': domain,
            'path': path,
            'depth': depth,
            'status_code': status_code,
            'content_type': content_type,
            'response_time_ms': response_time_ms,
            'error_message': error_message
        }, on_conflict=ConflictAction.IGNORE)
        
        self.db.execute(query, params)
        self.db.commit()
        
        return self.db.last_insert_id
    
    def log_url_batch(self, session_id: int, urls: list[dict]) -> int:
        """
        Log multiple URLs in a batch.
        
        Args:
            session_id: Current session ID
            urls: List of URL data dicts
            
        Returns:
            Number of URLs inserted
        """
        if not urls:
            return 0
        
        columns = [
            'session_id', 'url', 'normalized_url', 'domain', 
            'path', 'depth', 'status_code', 'content_type',
            'response_time_ms', 'error_message'
        ]
        
        data = []
        for url_data in urls:
            data.append((
                session_id,
                url_data.get('url'),
                url_data.get('normalized_url', url_data.get('url')),
                url_data.get('domain'),
                url_data.get('path'),
                url_data.get('depth', 0),
                url_data.get('status_code'),
                url_data.get('content_type'),
                url_data.get('response_time_ms'),
                url_data.get('error_message')
            ))
        
        query, _ = self.qb.insert_many('crawled_urls', columns, data, ConflictAction.IGNORE)
        count = self.db.execute_many(query, data)
        self.db.commit()
        
        return count
    
    def log_subdomain(
        self,
        session_id: int,
        subdomain: str,
        base_domain: str
    ) -> int:
        """
        Log a discovered subdomain.
        
        Args:
            session_id: Current session ID
            subdomain: Full subdomain (e.g., 'api.example.com')
            base_domain: Base domain (e.g., 'example.com')
            
        Returns:
            Subdomain record ID
        """
        # Check if already exists
        query, params = self.qb.select(
            'subdomains',
            columns=['id', 'url_count'],
            where={'session_id': session_id, 'subdomain': subdomain}
        )
        existing = self.db.fetch_one(query, params)
        
        if existing:
            # Update count
            update_query, update_params = self.qb.update(
                'subdomains',
                {'url_count': existing['url_count'] + 1},
                {'id': existing['id']}
            )
            self.db.execute(update_query, update_params)
            self.db.commit()
            return existing['id']
        
        # Insert new
        insert_query, insert_params = self.qb.insert('subdomains', {
            'session_id': session_id,
            'subdomain': subdomain,
            'base_domain': base_domain,
            'url_count': 1
        })
        
        self.db.execute(insert_query, insert_params)
        self.db.commit()
        
        return self.db.last_insert_id
    
    def complete_session(
        self,
        session_id: int,
        metrics: CrawlMetrics,
        status: str = 'completed',
        error_message: Optional[str] = None
    ) -> bool:
        """
        Mark a session as complete and save metrics.
        
        Args:
            session_id: Session ID
            metrics: Crawl metrics
            status: Final status ('completed', 'interrupted', 'failed')
            error_message: Error message if failed
            
        Returns:
            True if successful
        """
        try:
            # Update session
            query, params = self.qb.update('crawl_sessions', {
                'completed_at': datetime.now().isoformat(),
                'status': status,
                'error_message': error_message
            }, {'id': session_id})
            self.db.execute(query, params)
            
            # Insert metrics
            metrics_query, metrics_params = self.qb.insert('crawl_metrics', {
                'session_id': session_id,
                'total_time_seconds': metrics.total_time_seconds,
                'crawl_time_seconds': metrics.crawl_time_seconds,
                'urls_visited': metrics.urls_visited,
                'subdomains_found': metrics.subdomains_found,
                'paths_found': metrics.paths_found,
                'errors_count': metrics.errors_count,
                'crawl_speed': metrics.crawl_speed,
                'avg_time_per_url': metrics.avg_time_per_url,
                'discovery_rate': metrics.discovery_rate,
                'completed_normally': 1 if metrics.completed_normally else 0
            }, on_conflict=ConflictAction.REPLACE)
            self.db.execute(metrics_query, metrics_params)
            
            self.db.commit()
            logger.info(f"Completed session {session_id} with status: {status}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete session: {e}")
            return False
    
    def get_session(self, session_id: int) -> Optional[dict]:
        """
        Get session details.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session data dict or None
        """
        query, params = self.qb.select('crawl_sessions', where={'id': session_id})
        result = self.db.fetch_one(query, params)
        
        if result:
            return dict(result)
        return None
    
    def get_session_metrics(self, session_id: int) -> Optional[dict]:
        """
        Get metrics for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Metrics dict or None
        """
        query, params = self.qb.select('crawl_metrics', where={'session_id': session_id})
        result = self.db.fetch_one(query, params)
        
        if result:
            return dict(result)
        return None
    
    def get_session_urls(
        self,
        session_id: int,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> list[dict]:
        """
        Get URLs for a session.
        
        Args:
            session_id: Session ID
            limit: Max results
            offset: Offset for pagination
            
        Returns:
            List of URL dicts
        """
        query, params = self.qb.select(
            'crawled_urls',
            where={'session_id': session_id},
            order_by='discovered_at',
            limit=limit,
            offset=offset
        )
        results = self.db.fetch_all(query, params)
        return [dict(r) for r in results]
    
    def get_session_subdomains(self, session_id: int) -> list[dict]:
        """
        Get subdomains for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of subdomain dicts
        """
        query, params = self.qb.select(
            'subdomains',
            where={'session_id': session_id},
            order_by='url_count DESC'
        )
        results = self.db.fetch_all(query, params)
        return [dict(r) for r in results]
    
    def get_recent_sessions(self, limit: int = 10) -> list[dict]:
        """
        Get recent crawl sessions.
        
        Args:
            limit: Max number of sessions
            
        Returns:
            List of session dicts
        """
        query, params = self.qb.select(
            'crawl_sessions',
            order_by='started_at DESC',
            limit=limit
        )
        results = self.db.fetch_all(query, params)
        return [dict(r) for r in results]
    
    def get_stats_summary(self) -> dict:
        """
        Get overall database statistics.
        
        Returns:
            Summary statistics dict
        """
        sessions_count = self.db.fetch_one("SELECT COUNT(*) as count FROM crawl_sessions")
        urls_count = self.db.fetch_one("SELECT COUNT(*) as count FROM crawled_urls")
        subdomains_count = self.db.fetch_one("SELECT COUNT(DISTINCT subdomain) as count FROM subdomains")
        
        return {
            'total_sessions': sessions_count['count'] if sessions_count else 0,
            'total_urls': urls_count['count'] if urls_count else 0,
            'unique_subdomains': subdomains_count['count'] if subdomains_count else 0
        }
    
    def export_session(self, session_id: int, format: str = 'json') -> str:
        """
        Export session data.
        
        Args:
            session_id: Session ID
            format: 'json' or 'csv'
            
        Returns:
            Formatted string
        """
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        metrics = self.get_session_metrics(session_id)
        urls = self.get_session_urls(session_id)
        subdomains = self.get_session_subdomains(session_id)
        
        data = {
            'session': session,
            'metrics': metrics,
            'urls': urls,
            'subdomains': subdomains
        }
        
        if format == 'json':
            return json.dumps(data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
