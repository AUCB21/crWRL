"""
Buffer Handler Module

Manages crawl data buffering, JSON persistence, and database insertion.
Provides clean separation between crawling logic and data persistence.
"""

import json
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CrawlBufferHandler:
    """
    Handles buffering, flushing, and persistence of crawl data.
    
    Usage:
        handler = CrawlBufferHandler(session_id=1, db_manager=db_mgr)
        handler.add_url_record(url_data)
        handler.flush_if_needed()  # Auto-flushes at threshold
        handler.final_flush()      # Cleanup at end
    """
    
    def __init__(
        self,
        session_id: int,
        db_manager: Any,
        buffer_limit: int,
        output_dir: str
    ):
        """
        Initialize buffer handler.
        
        Args:
            session_id: Crawl session ID
            db_manager: Database manager instance
            buffer_limit: Number of records before auto-flush
            output_dir: Directory for JSON files
        """
        self.session_id = session_id
        self.db_manager = db_manager
        self.buffer_limit = buffer_limit
        self.output_dir = output_dir
        
        self.buffer: List[Dict[str, Any]] = []
        self.flush_count = 0
        self.total_flushed = 0
        
        # Setup session-specific logger
        self.logger = logging.getLogger(f"session_{session_id}")
        self.logger.setLevel(logging.DEBUG)
        
        # Create file handler for this session
        log_file = os.path.join(output_dir, f"{session_id}.log")
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter('[%(levelname)s] %(asctime)s: %(message)s')
        fh.setFormatter(formatter)
        
        # Add handler to logger
        if not self.logger.handlers:
            self.logger.addHandler(fh)
        
        # JSON file paths
        self.buffer_file = os.path.join(output_dir, f"crawl_session_{session_id}_buffer.json")
        self.final_file = os.path.join(output_dir, f"crawl_session_{session_id}.json")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        self.logger.info(f"Session {session_id} buffer handler initialized (limit: {buffer_limit})")
    
    def add_record(self, record: Dict[str, Any]) -> None:
        """
        Add a record to the buffer.
        Also writes to JSON file for crash recovery.
        
        Args:
            record: Dictionary with crawl data (must include 'type' key)
        """
        self.buffer.append(record)
        # Write buffer to JSON immediately for crash recovery
        self._write_buffer_to_json()
    
    def add_url_record(
        self,
        url: str,
        normalized_url: str,
        domain: str,
        path: str,
        depth: int,
        status_code: Optional[int] = None,
        content_type: Optional[str] = None,
        response_time_ms: Optional[float] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Add a URL record to the buffer.
        
        Args:
            url: Original URL
            normalized_url: Normalized URL
            domain: Domain name
            path: URL path
            depth: Crawl depth
            status_code: HTTP status code
            content_type: Content-Type header
            response_time_ms: Response time in milliseconds
            error_message: Error message if failed
        """
        record = {
            'type': 'url',
            'session_id': self.session_id,
            'url': url,
            'normalized_url': normalized_url,
            'domain': domain,
            'path': path,
            'depth': depth,
            'status_code': status_code,
            'content_type': content_type,
            'response_time_ms': response_time_ms,
            'error_message': error_message
        }
        self.add_record(record)
    
    def add_subdomain_record(
        self,
        subdomain: str,
        base_domain: str
    ) -> None:
        """
        Add a subdomain record to the buffer.
        
        Args:
            subdomain: Full subdomain (e.g., 'api.example.com')
            base_domain: Base domain (e.g., 'example.com')
        """
        record = {
            'type': 'subdomain',
            'session_id': self.session_id,
            'subdomain': subdomain,
            'base_domain': base_domain
        }
        self.add_record(record)
    
    def should_flush(self) -> bool:
        """Check if buffer has reached the flush threshold."""
        return len(self.buffer) >= self.buffer_limit
    
    def flush(self) -> int:
        """
        Flush buffer to database and wipe JSON.
        
        Returns:
            Number of records flushed
        """
        if not self.buffer:
            return 0
        
        try:
            # Copy buffer data
            data_to_flush = self.buffer.copy()
            
            # Insert to database
            self._insert_to_database(data_to_flush)
            
            # Clear buffer (memory)
            self.buffer.clear()
            
            # Delete JSON file after successful DB insert
            if os.path.exists(self.buffer_file):
                os.remove(self.buffer_file)
            
            # Update counters
            self.flush_count += 1
            self.total_flushed += len(data_to_flush)
            
            # Success log
            self.logger.info(f"Success: Data committed ({len(data_to_flush)} records), buffer wiped (flush #{self.flush_count})")
            return len(data_to_flush)
            
        except Exception as e:
            # Error log
            self.logger.error(f"Error: Data not committed, buffer error: {e}")
            # Re-add data back to buffer if flush failed
            self.buffer.extend(data_to_flush)
            return 0
    
    def flush_if_needed(self) -> int:
        """
        Flush buffer if threshold reached.
        
        Returns:
            Number of records flushed, or 0 if no flush needed
        """
        if self.should_flush():
            return self.flush()
        return 0
    
    def final_flush(self) -> int:
        """
        Flush remaining buffer and clean up.
        
        Returns:
            Number of records in final flush
        """
        # Flush any remaining records
        remaining = self.flush()
        
        # Clean up any leftover JSON file
        if os.path.exists(self.buffer_file):
            os.remove(self.buffer_file)
        
        # Wipe info log
        self.logger.info(f"Info: #{self.flush_count} wipe of session {self.session_id} - Total flushed: {self.total_flushed} records")
        
        return remaining
    
    def _write_buffer_to_json(self) -> None:
        """Write current buffer to JSON file (overwrites existing)."""
        try:
            with open(self.buffer_file, 'w', encoding='utf-8') as f:
                json.dump(self.buffer, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"Failed to write buffer to JSON: {e}")
    
    def _insert_to_database(self, data: List[Dict[str, Any]]) -> None:
        """Insert data to database."""
        # Bulk insert URLs
        url_records = [r for r in data if r.get('type') == 'url']
        if url_records:
            self.logger.info(f"Committing {len(url_records)} URLs to session {self.session_id}")
            self.db_manager.log_url_batch(self.session_id, url_records)
        
        # Insert subdomains
        subdomain_records = [r for r in data if r.get('type') == 'subdomain']
        if subdomain_records:
            self.logger.info(f"Committing {len(subdomain_records)} subdomains to session {self.session_id}")
            for record in subdomain_records:
                self.db_manager.log_subdomain(
                    record['session_id'],
                    record['subdomain'],
                    record['base_domain']
                )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get buffer statistics.
        
        Returns:
            Dictionary with buffer stats
        """
        return {
            'current_buffer_size': len(self.buffer),
            'buffer_limit': self.buffer_limit,
            'flush_count': self.flush_count,
            'total_flushed': self.total_flushed,
            'session_id': self.session_id
        }
