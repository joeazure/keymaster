# Product Requirements Document - Keymaster

## Project Overview
Keymaster is a local-first API key management tool designed for developers working with AI services. It provides secure storage, easy access, and seamless integration with development environments.

## MVP Scope

### Core Features

1. **Local Key Management**
   - Secure storage using macOS Keychain
   - Support for OpenAI, Anthropic, and Stability AI
   - Environment-based key management (dev/staging/prod)
   - Automatic .env file generation
   - Key rotation capabilities

2. **CLI Interface**
   - Git-style command structure
   - Interactive key addition and management
   - Environment switching
   - Configuration management
   - Usage monitoring

3. **Security**
   - macOS Keychain integration
   - Encryption for config files
   - Secure memory handling
   - Audit logging
   - Key access monitoring

### Technical Requirements

1. **Core Application**
   - Language: Python 3.11+
   - CLI Framework: Click or Typer
   - Key Storage: macOS Keychain
   - Configuration: YAML
   - Logging: structlog

2. **API Integration**
   - OpenAI API
   - Anthropic API
   - Stability AI API
   - Rate limiting support
   - Error handling

3. **Development Tools Integration**
   - Cursor AI compatibility
   - Windsurf IDE support
   - VSCode integration
   - Environment variable management
   - Direct key access API

4. **Security Implementation**
   - AES-256 encryption for file storage
   - Keychain access control
   - Secure key transmission
   - Memory security measures
   - Audit trail implementation

## Detailed Specifications

### CLI Commands

```bash
keymaster init           # Initialize in project directory
keymaster add           # Add new API key
keymaster ls            # List available keys
keymaster use           # Use key(s) in project
keymaster env           # Switch environments
keymaster rotate        # Rotate keys
keymaster remove        # Remove keys
keymaster audit         # View audit log
keymaster config        # Manage configuration
```

### Configuration File Structure

```yaml
version: 1
settings:
  default_environment: dev
  auto_rotate: false
  audit_log: true

services:
  openai:
    environments:
      - dev
      - prod
    auto_rotate: 30d
    
  anthropic:
    environments:
      - dev
      - staging
      - prod
    
  stability:
    environments:
      - dev
      - prod
```

### Security Requirements

1. **Key Storage**
   - All keys stored in macOS Keychain
   - Encrypted backup storage option
   - Memory wiping after use
   - Secure key transmission

2. **Access Control**
   - Local user authentication
   - Command-specific permissions
   - Environment restrictions
   - Audit logging

### Integration Features

1. **Environment Variables**
   - Automatic .env file management
   - Environment-specific variables
   - Template support
   - Git integration (.gitignore)

2. **IDE Integration**
   - Cursor AI environment detection
   - Windsurf configuration support
   - VSCode extension compatibility
   - Auto-completion support

## Development Guidelines

### Code Organization
```
keymaster/
├── cli/
│   ├── commands/
│   ├── utils/
│   └── main.py
├── core/
│   ├── security/
│   ├── storage/
│   └── config/
├── providers/
│   ├── openai.py
│   ├── anthropic.py
│   └── stability.py
├── integration/
│   ├── env.py
│   └── ide.py
└── tests/
```

### Testing Requirements
- Unit tests: 90% coverage minimum
- Integration tests for each provider
- Security tests
- CLI interface tests
- Environment integration tests

### Documentation Requirements
- CLI command documentation
- API documentation
- Security best practices
- Integration guides
- Development setup guide

## Release Strategy

### Phase 1: Core Implementation
1. Basic CLI structure
2. Key storage implementation
3. OpenAI integration
4. Environment variable support
5. Basic security features

### Phase 2: Provider Expansion
1. Anthropic integration
2. Stability AI integration
3. Enhanced security features
4. Key rotation implementation

### Phase 3: Integration & Polish
1. IDE integration
2. Advanced CLI features
3. Documentation
4. Testing & security audit

## Success Criteria

### Technical
- All core commands implemented
- Security audit passed
- Test coverage >= 90%
- Zero critical security issues
- Successful integration with specified IDEs

### User Experience
- Command completion < 1s
- Clear error messages
- Intuitive command structure
- Seamless IDE integration
- Minimal configuration required

## Future Considerations

### Planned Features
- Team collaboration
- Cloud sync
- Additional providers
- Advanced monitoring
- Cost optimization

### Technical Debt Monitoring
- Regular security audits
- Dependency updates
- Performance monitoring
- User feedback tracking

# Cloud Backup and Synchronization

## Overview
Keymaster will support secure cloud backup and synchronization of the keystore to prevent data loss and enable key sharing across devices. The initial implementation will support Dropbox and iCloud, with potential for additional cloud providers in the future.

## Cloud Provider Support

### Phase 1: Initial Providers
1. **Dropbox Integration**
   - OAuth2 authentication flow
   - Automatic backup scheduling
   - Encrypted backup file storage
   - Version history maintenance
   - Selective key backup
   - Cross-device synchronization
   - Device registration and management

2. **iCloud Integration**
   - Native macOS iCloud integration
   - Automatic sync with iCloud Drive
   - Encrypted backup storage
   - Version tracking
   - Selective key backup
   - Cross-device synchronization
   - Device registration and management

## Key Synchronization

### Core Principles
1. **Non-Destructive Operations**
   - Pull operations never delete local keys
   - Conflicts resolved through merging
   - Local keys take precedence by default
   - Option to skip or merge conflicting keys
   - Detailed conflict resolution logging

2. **Device Management**
   - Unique device identification
   - Device registration required
   - Device authorization controls
   - Active device listing
   - Device removal capabilities

3. **Selective Synchronization**
   - Service-level sync control
   - Environment-level sync control
   - Key metadata sync options
   - Provider configuration sync
   - Custom sync rules

### Security Requirements
- End-to-end encryption of synced data
- Per-device encryption keys
- Device authentication
- Sync operation verification
- Audit logging of all sync events
- Secure device registration
- Key version tracking

### Sync Management
1. **Sync Operations**
   - Manual sync initiation
   - Automatic background sync
   - Selective service sync
   - Conflict detection
   - Merge strategies
   - Sync status monitoring

2. **Conflict Resolution**
   - Automatic conflict detection
   - Interactive conflict resolution
   - Version comparison
   - Metadata merge
   - Key difference highlighting
   - Resolution strategy selection

3. **Configuration Options**
   - Sync frequency settings
   - Service inclusion/exclusion
   - Environment filters
   - Conflict resolution preferences
   - Bandwidth controls
   - Notification settings

### CLI Commands
```bash
# Sync commands
keymaster sync init                    # Initialize sync for device
keymaster sync configure              # Configure sync settings
keymaster sync now                    # Trigger immediate sync
keymaster sync status                # Check sync status
keymaster sync devices               # List registered devices
keymaster sync conflicts             # Show and resolve conflicts

# Device management
keymaster device register            # Register current device
keymaster device list                # List all devices
keymaster device remove              # Remove device
keymaster device rename              # Rename device
```

### Command Options
```bash
# Initialize sync
keymaster sync init --provider [dropbox|icloud]
                    --device-name [name]

# Configure sync settings
keymaster sync configure --frequency [realtime|hourly|daily]
                        --services [...]
                        --environments [...]
                        --conflict-strategy [skip|merge|prompt]

# Perform sync
keymaster sync now --services [...]           # Sync specific services
                   --environments [...]       # Sync specific environments
                   --force                   # Force sync despite conflicts
                   --dry-run                # Show what would be synced

# Manage devices
keymaster device register --name [device-name]
                         --type [desktop|laptop|server]
                         --description [text]
```

### Audit Logging
1. **Sync Events**
   - Sync initiation and completion
   - Key additions and updates
   - Conflict detections and resolutions
   - Device registrations and removals
   - Error conditions and resolutions

2. **Log Content**
   - Timestamp
   - Device identifier
   - Operation type
   - Affected services/environments
   - Resolution decisions
   - User actions
   - Error details

### Implementation Requirements

#### Authentication
- OAuth2 flow for Dropbox
- iCloud keychain integration
- Secure credential storage
- Token refresh handling
- Session management
- Device authentication
- Cross-device authorization

#### Encryption
- AES-256-GCM for data encryption
- Argon2id for key derivation
- Secure random IV generation
- MAC verification
- Key rotation support
- Per-device key management
- Sync operation verification

#### Sync Management
- File change detection
- Conflict resolution
- Bandwidth optimization
- Resume capability
- Error recovery
- Device state tracking
- Version control

#### Error Handling
- Network failure recovery
- Quota management
- Version conflicts
- Corruption detection
- Authentication failures
- Sync conflict resolution
- Device authorization errors

## Future Enhancements
1. Additional cloud providers:
   - Google Drive
   - OneDrive
   - AWS S3
   - Azure Blob Storage

2. Advanced features:
   - Real-time synchronization
   - Team key sharing
   - Role-based sync permissions
   - Sync analytics and reporting
   - Custom merge strategies
   - Advanced conflict resolution
   - Multi-device key rotation

3. Enterprise features:
   - Team management
   - Compliance reporting
   - Audit trail exports
   - Policy enforcement
   - Access controls
   - Emergency access

# Technical Specification: Cloud Sync Implementation

## Data Structures

### Device Registration
```python
class Device:
    id: str                  # UUID for device identification
    name: str                # User-friendly device name
    type: str               # desktop/laptop/server
    description: str        # Optional device description
    public_key: bytes      # Device's public key for E2E encryption
    last_sync: datetime    # Last successful sync timestamp
    created_at: datetime   # Device registration timestamp
    status: str            # active/inactive/revoked
    sync_config: dict      # Device-specific sync preferences
```

### Sync Metadata
```python
class SyncMetadata:
    key_id: str            # Unique identifier for key
    service: str           # Service name (e.g., OpenAI)
    environment: str       # Environment (dev/prod)
    version: int          # Key version number
    last_modified: datetime # Last modification timestamp
    modified_by: str       # Device ID that made the change
    checksum: str         # Hash of key data for integrity
    sync_status: str      # pending/synced/conflict
```

### Sync State
```python
class SyncState:
    device_id: str         # Current device ID
    last_sync: datetime    # Last sync timestamp
    sync_token: str       # Provider-specific sync cursor
    pending_changes: List[SyncMetadata]  # Local changes to sync
    conflicts: List[Conflict]  # Unresolved conflicts
```

### Cloud Storage Format
```json
{
    "metadata": {
        "version": "1.0",
        "encryption_version": "1.0",
        "last_modified": "ISO-8601-timestamp"
    },
    "devices": {
        "device-uuid-1": {
            "name": "MacBook Pro",
            "public_key": "base64-encoded-key",
            "last_sync": "ISO-8601-timestamp"
        }
    },
    "keys": {
        "key-uuid-1": {
            "service": "openai",
            "environment": "dev",
            "version": 1,
            "data": "encrypted-key-data",
            "metadata": "encrypted-metadata",
            "modified_by": "device-uuid-1",
            "modified_at": "ISO-8601-timestamp"
        }
    }
}
```

## Database Schema Extensions

### Device Table
```sql
CREATE TABLE devices (
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
```

### Sync Metadata Table
```sql
CREATE TABLE sync_metadata (
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
```

### Sync State Table
```sql
CREATE TABLE sync_state (
    id INTEGER PRIMARY KEY,
    device_id TEXT NOT NULL,
    last_sync TIMESTAMP,
    sync_token TEXT,
    FOREIGN KEY(device_id) REFERENCES devices(id)
);
```

## Component Architecture

### Cloud Provider Interface
```python
class CloudProvider(Protocol):
    async def initialize(self) -> None: ...
    async def authenticate(self) -> bool: ...
    async def upload_file(self, path: str, data: bytes) -> str: ...
    async def download_file(self, path: str) -> bytes: ...
    async def list_changes(self, cursor: str) -> tuple[list[Change], str]: ...
    async def create_directory(self, path: str) -> None: ...
    async def delete_file(self, path: str) -> None: ...
```

### Sync Manager
```python
class SyncManager:
    def __init__(self, provider: CloudProvider, device: Device):
        self.provider = provider
        self.device = device
        self.crypto = CryptoManager()
        
    async def initialize(self) -> None: ...
    async def sync(self, services: list[str] = None) -> SyncResult: ...
    async def resolve_conflicts(self, strategy: str) -> None: ...
    async def get_status(self) -> SyncStatus: ...
```

### Crypto Manager
```python
class CryptoManager:
    def generate_device_keypair(self) -> tuple[bytes, bytes]: ...
    def encrypt_key(self, key: str, recipients: list[Device]) -> bytes: ...
    def decrypt_key(self, encrypted_data: bytes) -> str: ...
    def verify_signature(self, data: bytes, signature: bytes) -> bool: ...
```

## Sync Process Flow

1. **Initialization**
   ```python
   async def initialize_sync():
       # Generate device keys
       private_key, public_key = crypto.generate_device_keypair()
       
       # Register device
       device = Device(
           id=uuid4(),
           name=device_name,
           public_key=public_key
       )
       
       # Initialize cloud storage
       await provider.initialize()
       await provider.authenticate()
       
       # Upload device info
       await upload_device_info(device)
   ```

2. **Sync Operation**
   ```python
   async def perform_sync():
       # Get local changes
       local_changes = get_local_changes()
       
       # Get remote changes
       remote_changes = await get_remote_changes()
       
       # Detect conflicts
       conflicts = detect_conflicts(local_changes, remote_changes)
       
       if conflicts and not force:
           return SyncResult(status="conflicts", conflicts=conflicts)
           
       # Apply remote changes
       for change in remote_changes:
           if change.conflicts_with(local_changes):
               handle_conflict(change)
           else:
               apply_remote_change(change)
               
       # Upload local changes
       for change in local_changes:
           await upload_change(change)
           
       return SyncResult(status="success")
   ```

3. **Conflict Resolution**
   ```python
   async def resolve_conflicts(conflicts: list[Conflict], strategy: str):
       for conflict in conflicts:
           if strategy == "local":
               keep_local_version(conflict)
           elif strategy == "remote":
               apply_remote_version(conflict)
           elif strategy == "merge":
               merged = merge_changes(conflict.local, conflict.remote)
               apply_merged_version(merged)
           elif strategy == "prompt":
               resolution = await prompt_user(conflict)
               apply_resolution(resolution)
   ```

## Error Handling

1. **Network Errors**
   ```python
   async def handle_network_error(error: NetworkError):
       if error.is_temporary:
           await retry_with_backoff()
       else:
           log_sync_failure(error)
           raise SyncError(f"Network error: {error}")
   ```

2. **Conflict Errors**
   ```python
   async def handle_conflict_error(conflict: Conflict):
       if conflict.is_resolvable:
           await resolve_conflict(conflict)
       else:
           log_conflict(conflict)
           notify_user(conflict)
   ```

3. **Authentication Errors**
   ```python
   async def handle_auth_error(error: AuthError):
       if error.is_token_expired:
           await refresh_token()
       else:
           log_auth_failure(error)
           raise AuthenticationError("Authentication failed")
   ```

## Security Measures

1. **End-to-End Encryption**
   ```python
   class E2ECrypto:
       def encrypt_for_devices(self, data: bytes, devices: list[Device]) -> bytes:
           # Generate data key
           data_key = generate_random_key()
           
           # Encrypt data with data key
           encrypted_data = encrypt_gcm(data, data_key)
           
           # Encrypt data key for each device
           key_envelope = {
               device.id: encrypt_rsa(data_key, device.public_key)
               for device in devices
           }
           
           return package_encrypted_data(encrypted_data, key_envelope)
   ```

2. **Key Verification**
   ```python
   def verify_key_integrity(key_data: bytes, metadata: SyncMetadata) -> bool:
       computed_hash = sha256(key_data)
       return computed_hash == metadata.checksum
   ```

## Audit Logging

```python
class SyncAuditLogger:
    def log_sync_event(self, event_type: str, details: dict):
        event = {
            "timestamp": datetime.utcnow(),
            "device_id": self.device.id,
            "event_type": event_type,
            "details": details
        }
        self.audit_logger.log_event("sync", **event)
```

## Testing Strategy

1. **Unit Tests**
   - Device registration/management
   - Encryption/decryption
   - Conflict detection/resolution
   - Change tracking

2. **Integration Tests**
   - Cloud provider interactions
   - End-to-end sync operations
   - Error handling scenarios
   - Conflict resolution workflows

3. **Security Tests**
   - Encryption verification
   - Key protection
   - Authentication flows
   - Access controls