"""
Database management for Keymaster using SQLite3.
Uses Python's built-in sqlite3 module from the standard library.
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Tuple
import structlog

log = structlog.get_logger()

class KeyDatabase:
    """Manages SQLite database for key metadata."""
    
    def __init__(self):
        self.db_path = self._get_db_path()
        self._init_db()
        # Run service name normalization on startup
        self.normalize_service_names()
        
    def _get_db_path(self) -> str:
        """Get the path to the SQLite database file."""
        home_dir = os.path.expanduser("~")
        db_dir = os.path.join(home_dir, ".keymaster", "db")
        os.makedirs(db_dir, exist_ok=True)
        return os.path.join(db_dir, "keymaster.db")
        
    def _init_db(self) -> None:
        """Initialize the database schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS key_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    keychain_service_name TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    created_by TEXT NOT NULL,
                    last_updated_by TEXT NOT NULL,
                    UNIQUE(service_name, environment)
                )
            """)
            conn.commit()
            
    def add_key(self, 
                service_name: str, 
                environment: str, 
                keychain_service_name: str,
                user: str) -> None:
        """Add or update a key's metadata."""
        now = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            try:
                # Try to insert new record
                conn.execute("""
                    INSERT INTO key_metadata 
                    (service_name, environment, keychain_service_name, 
                     created_at, updated_at, created_by, last_updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (service_name, environment.lower(), keychain_service_name,
                     now, now, user, user))
            except sqlite3.IntegrityError:
                # Update existing record
                conn.execute("""
                    UPDATE key_metadata 
                    SET updated_at = ?, last_updated_by = ?, 
                        keychain_service_name = ?
                    WHERE LOWER(service_name) = LOWER(?) AND LOWER(environment) = LOWER(?)
                """, (now, user, keychain_service_name, 
                     service_name, environment))
            conn.commit()
            
    def remove_key(self, service_name: str, environment: str) -> None:
        """Remove a key's metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM key_metadata 
                WHERE LOWER(service_name) = LOWER(?) AND LOWER(environment) = LOWER(?)
            """, (service_name, environment))
            conn.commit()
            
    def get_key_metadata(self, 
                        service_name: str, 
                        environment: str) -> Optional[dict]:
        """Get metadata for a specific key."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM key_metadata 
                WHERE LOWER(service_name) = LOWER(?) AND LOWER(environment) = LOWER(?)
            """, (service_name, environment))
            row = cursor.fetchone()
            return dict(row) if row else None
            
    def list_keys(self, service_name: Optional[str] = None) -> List[Tuple[str, str, datetime, str]]:
        """
        List all keys or keys for a specific service.
        Returns: List of (service_name, environment, updated_at, last_updated_by)
        """
        with sqlite3.connect(self.db_path) as conn:
            if service_name:
                cursor = conn.execute("""
                    SELECT service_name, environment, updated_at, last_updated_by 
                    FROM key_metadata 
                    WHERE LOWER(service_name) = LOWER(?)
                    ORDER BY service_name, environment
                """, (service_name,))
            else:
                cursor = conn.execute("""
                    SELECT service_name, environment, updated_at, last_updated_by 
                    FROM key_metadata 
                    ORDER BY service_name, environment
                """)
            return cursor.fetchall() 

    def normalize_service_names(self) -> None:
        """
        Normalize all service names in the database to lowercase.
        This is a one-time migration to ensure consistency.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # First get all unique service names
            cursor.execute("SELECT DISTINCT service_name FROM key_metadata")
            service_names = cursor.fetchall()
            
            # Update any that aren't lowercase
            for (service_name,) in service_names:
                if service_name != service_name.lower():
                    cursor.execute(
                        "UPDATE key_metadata SET service_name = ? WHERE service_name = ?",
                        (service_name.lower(), service_name)
                    )
            conn.commit() 