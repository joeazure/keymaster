"""Data models for the keymaster sync functionality."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID, uuid4


class DeviceType(str, Enum):
    """Type of device for sync purposes."""
    DESKTOP = "desktop"
    LAPTOP = "laptop"
    SERVER = "server"


class DeviceStatus(str, Enum):
    """Status of a sync device."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"


class SyncStatus(str, Enum):
    """Status of a synced key."""
    PENDING = "pending"
    SYNCED = "synced"
    CONFLICT = "conflict"


@dataclass
class Device:
    """Represents a device in the sync system."""
    name: str
    type: DeviceType
    public_key: bytes
    description: Optional[str] = None
    id: UUID = field(default_factory=uuid4)
    last_sync: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: DeviceStatus = DeviceStatus.ACTIVE
    sync_config: Dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate and convert fields after initialization."""
        if isinstance(self.id, str):
            self.id = UUID(self.id)
        if isinstance(self.type, str):
            self.type = DeviceType(self.type.lower())
        if isinstance(self.status, str):
            self.status = DeviceStatus(self.status.lower())
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at)
        if isinstance(self.last_sync, str):
            self.last_sync = datetime.fromisoformat(self.last_sync)


@dataclass
class SyncMetadata:
    """Metadata for a synced key."""
    key_id: UUID
    service: str
    environment: str
    version: int
    modified_by: UUID
    checksum: str
    sync_status: SyncStatus = SyncStatus.PENDING
    last_modified: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate and convert fields after initialization."""
        if isinstance(self.key_id, str):
            self.key_id = UUID(self.key_id)
        if isinstance(self.modified_by, str):
            self.modified_by = UUID(self.modified_by)
        if isinstance(self.sync_status, str):
            self.sync_status = SyncStatus(self.sync_status.lower())
        if isinstance(self.last_modified, str):
            self.last_modified = datetime.fromisoformat(self.last_modified)


@dataclass
class SyncState:
    """Current sync state for a device."""
    device_id: UUID
    last_sync: Optional[datetime] = None
    sync_token: Optional[str] = None
    pending_changes: List[SyncMetadata] = field(default_factory=list)
    conflicts: List['Conflict'] = field(default_factory=list)

    def __post_init__(self):
        """Validate and convert fields after initialization."""
        if isinstance(self.device_id, str):
            self.device_id = UUID(self.device_id)
        if isinstance(self.last_sync, str):
            self.last_sync = datetime.fromisoformat(self.last_sync)


@dataclass
class Conflict:
    """Represents a sync conflict between local and remote changes."""
    key_id: UUID
    local_version: SyncMetadata
    remote_version: SyncMetadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    resolution_strategy: Optional[str] = None

    def __post_init__(self):
        """Validate and convert fields after initialization."""
        if isinstance(self.key_id, str):
            self.key_id = UUID(self.key_id)
        if isinstance(self.created_at, str):
            self.created_at = datetime.fromisoformat(self.created_at) 