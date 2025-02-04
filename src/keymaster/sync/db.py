"""Database operations for keymaster sync functionality."""

import json
import sqlite3
from datetime import datetime
from typing import List, Optional
from uuid import UUID

import structlog

from keymaster.db import KeyDatabase
from keymaster.sync.models import (
    Device,
    DeviceStatus,
    DeviceType,
    SyncMetadata,
    SyncState,
    SyncStatus,
)

log = structlog.get_logger()

class SyncDatabase:
    """Database operations for sync functionality."""

    def __init__(self):
        """Initialize the sync database using the main KeyDatabase connection."""
        self.db = KeyDatabase()
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Initialize the sync-related database schema."""
        try:
            with self.db.get_connection() as conn:
                conn.executescript("""
                    -- Devices table
                    CREATE TABLE IF NOT EXISTS devices (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        type TEXT NOT NULL,
                        description TEXT,
                        public_key BLOB NOT NULL,
                        last_sync TIMESTAMP,
                        created_at TIMESTAMP NOT NULL,
                        status TEXT NOT NULL,
                        sync_config JSON,
                        UNIQUE(name)
                    );

                    -- Sync metadata table
                    CREATE TABLE IF NOT EXISTS sync_metadata (
                        key_id TEXT PRIMARY KEY,
                        service TEXT NOT NULL,
                        environment TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        last_modified TIMESTAMP NOT NULL,
                        modified_by TEXT NOT NULL,
                        checksum TEXT NOT NULL,
                        sync_status TEXT NOT NULL,
                        FOREIGN KEY(modified_by) REFERENCES devices(id)
                    );

                    -- Sync state table
                    CREATE TABLE IF NOT EXISTS sync_state (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id TEXT NOT NULL,
                        last_sync TIMESTAMP,
                        sync_token TEXT,
                        FOREIGN KEY(device_id) REFERENCES devices(id)
                    );

                    -- Conflicts table
                    CREATE TABLE IF NOT EXISTS sync_conflicts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        key_id TEXT NOT NULL,
                        local_version_id TEXT NOT NULL,
                        remote_version_id TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        resolved BOOLEAN NOT NULL DEFAULT 0,
                        resolution_strategy TEXT,
                        FOREIGN KEY(local_version_id) REFERENCES sync_metadata(key_id),
                        FOREIGN KEY(remote_version_id) REFERENCES sync_metadata(key_id)
                    );
                """)
                log.info("Sync database schema initialized")
        except sqlite3.Error as e:
            log.error("Failed to initialize sync database schema", error=str(e))
            raise

    def add_device(self, device: Device) -> None:
        """Add a new device to the database."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO devices (
                        id, name, type, description, public_key,
                        last_sync, created_at, status, sync_config
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(device.id),
                    device.name,
                    device.type.value,
                    device.description,
                    device.public_key,
                    device.last_sync.isoformat() if device.last_sync else None,
                    device.created_at.isoformat(),
                    device.status.value,
                    json.dumps(device.sync_config)
                ))
                log.info("Added new device", device_id=device.id, name=device.name)
        except sqlite3.Error as e:
            log.error("Failed to add device", error=str(e), device_id=device.id)
            raise

    def get_device(self, device_id: UUID) -> Optional[Device]:
        """Get a device by its ID."""
        try:
            with self.db.get_connection() as conn:
                row = conn.execute("""
                    SELECT * FROM devices WHERE id = ?
                """, (str(device_id),)).fetchone()

                if not row:
                    return None

                return Device(
                    id=row['id'],
                    name=row['name'],
                    type=row['type'],
                    description=row['description'],
                    public_key=row['public_key'],
                    last_sync=row['last_sync'],
                    created_at=row['created_at'],
                    status=row['status'],
                    sync_config=json.loads(row['sync_config'])
                )
        except sqlite3.Error as e:
            log.error("Failed to get device", error=str(e), device_id=device_id)
            raise

    def update_device_sync_time(self, device_id: UUID, sync_time: datetime) -> None:
        """Update a device's last sync timestamp."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE devices SET last_sync = ? WHERE id = ?
                """, (sync_time.isoformat(), str(device_id)))
                log.info("Updated device sync time", device_id=device_id)
        except sqlite3.Error as e:
            log.error("Failed to update device sync time", error=str(e), device_id=device_id)
            raise

    def add_sync_metadata(self, metadata: SyncMetadata) -> None:
        """Add sync metadata for a key."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO sync_metadata (
                        key_id, service, environment, version,
                        last_modified, modified_by, checksum, sync_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(metadata.key_id),
                    metadata.service,
                    metadata.environment,
                    metadata.version,
                    metadata.last_modified.isoformat(),
                    str(metadata.modified_by),
                    metadata.checksum,
                    metadata.sync_status.value
                ))
                log.info("Added sync metadata", key_id=metadata.key_id)
        except sqlite3.Error as e:
            log.error("Failed to add sync metadata", error=str(e), key_id=metadata.key_id)
            raise

    def get_sync_metadata(self, key_id: UUID) -> Optional[SyncMetadata]:
        """Get sync metadata for a key."""
        try:
            with self.db.get_connection() as conn:
                row = conn.execute("""
                    SELECT * FROM sync_metadata WHERE key_id = ?
                """, (str(key_id),)).fetchone()

                if not row:
                    return None

                return SyncMetadata(
                    key_id=row['key_id'],
                    service=row['service'],
                    environment=row['environment'],
                    version=row['version'],
                    last_modified=row['last_modified'],
                    modified_by=row['modified_by'],
                    checksum=row['checksum'],
                    sync_status=row['sync_status']
                )
        except sqlite3.Error as e:
            log.error("Failed to get sync metadata", error=str(e), key_id=key_id)
            raise

    def get_pending_changes(self, device_id: UUID) -> List[SyncMetadata]:
        """Get all pending changes for a device."""
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute("""
                    SELECT m.* FROM sync_metadata m
                    JOIN sync_state s ON s.device_id = ?
                    WHERE m.sync_status = ?
                """, (str(device_id), SyncStatus.PENDING.value)).fetchall()

                return [
                    SyncMetadata(
                        key_id=row['key_id'],
                        service=row['service'],
                        environment=row['environment'],
                        version=row['version'],
                        last_modified=row['last_modified'],
                        modified_by=row['modified_by'],
                        checksum=row['checksum'],
                        sync_status=row['sync_status']
                    )
                    for row in rows
                ]
        except sqlite3.Error as e:
            log.error("Failed to get pending changes", error=str(e), device_id=device_id)
            raise

    def update_sync_status(self, key_id: UUID, status: SyncStatus) -> None:
        """Update the sync status of a key."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE sync_metadata SET sync_status = ? WHERE key_id = ?
                """, (status.value, str(key_id)))
                log.info("Updated sync status", key_id=key_id, status=status.value)
        except sqlite3.Error as e:
            log.error("Failed to update sync status", error=str(e), key_id=key_id)
            raise 