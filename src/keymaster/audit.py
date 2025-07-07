"""
Secure audit logging system for Keymaster operations.

This module provides encrypted audit logging with the encryption key stored
securely in the system keyring rather than in plaintext configuration files.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
import structlog
from keymaster.config import ConfigManager
from keymaster.exceptions import AuditError, StorageError

log = structlog.get_logger()

class AuditLogger:
    """
    Secure audit logging system for Keymaster operations.
    
    Encrypts sensitive data in logs while maintaining searchability.
    The encryption key is stored securely in the system keyring.
    """
    
    def __init__(self):
        self.encryption_key = self._get_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        self._ensure_log_file()
        
    def _get_encryption_key(self) -> bytes:
        """
        Get or create the encryption key for audit logs.
        
        The key is stored securely in the system keyring. If this is the first
        time, it migrates any existing key from the config file.
        
        Returns:
            The encryption key as bytes
            
        Raises:
            AuditError: If encryption key cannot be retrieved or created
        """
        # Import here to avoid circular imports
        from keymaster.security import KeyStore
        
        try:
            # Try to get the key from secure storage first
            key_str = KeyStore.get_system_key("audit_encryption")
            
            if key_str:
                log.debug("Retrieved audit encryption key from secure storage")
                return key_str.encode()
            
            # Key not found in secure storage, check for migration from config
            migrated_key = self._migrate_key_from_config()
            if migrated_key:
                return migrated_key
            
            # No existing key found, generate a new one
            new_key = Fernet.generate_key()
            KeyStore.store_system_key("audit_encryption", new_key.decode())
            log.info("Generated new audit encryption key and stored securely")
            return new_key
            
        except Exception as e:
            log.error("Failed to get audit encryption key", error=str(e))
            raise AuditError(f"Failed to get audit encryption key: {e}", operation="get_encryption_key")
    
    def _migrate_key_from_config(self) -> Optional[bytes]:
        """
        Migrate encryption key from config file to secure storage.
        
        This is for backwards compatibility with installations that have
        the encryption key stored in the config file.
        
        Returns:
            The migrated key as bytes, or None if no key found in config
        """
        try:
            config = ConfigManager.load_config()
            
            # Check if there's an existing key in the config
            if 'audit' in config and 'encryption_key' in config['audit']:
                old_key_str = config['audit']['encryption_key']
                log.info("Found audit encryption key in config file, migrating to secure storage")
                
                # Store in secure storage
                from keymaster.security import KeyStore
                KeyStore.store_system_key("audit_encryption", old_key_str)
                
                # Remove from config file for security
                del config['audit']['encryption_key']
                if not config['audit']:  # Remove empty audit section
                    del config['audit']
                ConfigManager.write_config(config)
                
                log.info("Successfully migrated audit encryption key from config to secure storage")
                return old_key_str.encode()
                
        except Exception as e:
            log.warning("Failed to migrate encryption key from config", error=str(e))
            
        return None

    def _get_log_path(self) -> str:
        """Get the path to the audit log file."""
        home_dir = os.path.expanduser("~")
        log_dir = os.path.join(home_dir, ".keymaster", "logs")
        os.makedirs(log_dir, exist_ok=True, mode=0o700)  # Secure permissions
        return os.path.join(log_dir, "audit.log")

    def _ensure_log_file(self) -> None:
        """Ensure the audit log file exists with secure permissions."""
        log_path = self._get_log_path()
        if not os.path.exists(log_path):
            try:
                # Create an empty log file with secure permissions
                with open(log_path, "w") as f:
                    pass
                os.chmod(log_path, 0o600)  # Read/write for owner only
                log.info("Created new audit log file with secure permissions", path=log_path)
            except Exception as e:
                log.error("Failed to create audit log file", path=log_path, error=str(e))
                raise AuditError(f"Failed to create audit log file: {e}", operation="ensure_log_file")
        else:
            # Ensure existing file has secure permissions
            try:
                os.chmod(log_path, 0o600)
            except Exception as e:
                log.warning("Failed to set secure permissions on audit log", path=log_path, error=str(e))

    def _encrypt_sensitive_data(self, data: str) -> str:
        """
        Encrypt sensitive data for storage.
        
        Args:
            data: The sensitive data to encrypt
            
        Returns:
            The encrypted data as a base64 string
            
        Raises:
            AuditError: If encryption fails
        """
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            log.error("Failed to encrypt sensitive data", error=str(e))
            raise AuditError(f"Failed to encrypt sensitive data: {e}", operation="encrypt")

    def _decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """
        Decrypt sensitive data from storage.
        
        Args:
            encrypted_data: The encrypted data as a base64 string
            
        Returns:
            The decrypted data
            
        Raises:
            AuditError: If decryption fails
        """
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            log.error("Failed to decrypt sensitive data", error=str(e))
            raise AuditError(f"Failed to decrypt sensitive data: {e}", operation="decrypt")

    def log_event(self, 
                event_type: str,
                user: str,
                service: str = None,
                environment: str = None,
                sensitive_data: str = None,
                additional_data: dict = None) -> None:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (e.g., add_key, remove_key, test_key)
            user: Username performing the action
            service: Optional service name (e.g., OpenAI)
            environment: Optional environment (e.g., dev, prod)
            sensitive_data: Optional sensitive data to encrypt
            additional_data: Optional additional metadata
            
        Raises:
            AuditError: If logging fails
        """
        try:
            now = datetime.utcnow().isoformat()
            
            # Create the event data
            event = {
                "timestamp": now,
                "event_type": event_type,
                "user": user
            }
            
            # Add optional fields if provided
            if service:
                event["service"] = service
            if environment:
                event["environment"] = environment
                
            # Encrypt sensitive data if provided
            if sensitive_data:
                event["encrypted_data"] = self._encrypt_sensitive_data(sensitive_data)
                
            # Add any additional metadata
            if additional_data:
                event["metadata"] = additional_data
                
            # Write to log file
            log_path = self._get_log_path()
            with open(log_path, 'a') as f:
                json.dump(event, f, separators=(',', ':'))  # Compact JSON
                f.write('\n')
                
            log.info("Audit event logged", 
                    event_type=event_type, 
                    service=service, 
                    environment=environment)
                    
        except Exception as e:
            log.error("Failed to log audit event", 
                     event_type=event_type, 
                     service=service, 
                     environment=environment, 
                     error=str(e))
            raise AuditError(f"Failed to log audit event: {e}", operation="log_event")

    def get_events(self, 
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None,
                  event_type: Optional[str] = None,
                  service: Optional[str] = None,
                  environment: Optional[str] = None,
                  decrypt: bool = False) -> list[Dict[str, Any]]:
        """
        Retrieve audit events with optional filtering and decryption.
        
        Args:
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            event_type: Optional event type for filtering
            service: Optional service name for filtering
            environment: Optional environment for filtering
            decrypt: Whether to decrypt sensitive data
            
        Returns:
            List of audit events matching the filters
            
        Raises:
            AuditError: If retrieval fails
        """
        try:
            events = []
            log_path = self._get_log_path()
            
            if not os.path.exists(log_path):
                log.warning("Audit log file does not exist", path=log_path)
                return events
            
            # Check if log file is empty
            if os.path.getsize(log_path) == 0:
                return events
                
            with open(log_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:  # Skip empty lines
                        continue
                    
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError as e:
                        log.warning("Failed to parse audit log line", 
                                   line_number=line_num, 
                                   error=str(e))
                        continue
                    
                    # Apply filters
                    if start_date and datetime.fromisoformat(event["timestamp"]) < start_date:
                        continue
                    if end_date and datetime.fromisoformat(event["timestamp"]) > end_date:
                        continue
                    if event_type and event.get("event_type") != event_type:
                        continue
                    if service and event.get("service") != service:
                        continue
                    if environment and event.get("environment") != environment:
                        continue
                    
                    # Optionally decrypt sensitive data
                    if decrypt and "encrypted_data" in event:
                        try:
                            event["decrypted_data"] = self._decrypt_sensitive_data(event["encrypted_data"])
                        except Exception as e:
                            log.warning("Failed to decrypt audit event data", 
                                       line_number=line_num, 
                                       error=str(e))
                            event["decryption_error"] = str(e)
                        
                    events.append(event)
                    
            return events
            
        except Exception as e:
            log.error("Failed to retrieve audit events", error=str(e))
            raise AuditError(f"Failed to retrieve audit events: {e}", operation="get_events")

    def clear_events(self, confirm: bool = False) -> None:
        """
        Clear all audit events (use with caution).
        
        Args:
            confirm: Must be True to actually clear events
            
        Raises:
            AuditError: If clearing fails
        """
        if not confirm:
            raise AuditError("Must confirm clearing of audit events", operation="clear_events")
        
        try:
            log_path = self._get_log_path()
            with open(log_path, 'w') as f:
                pass  # Truncate file
            log.warning("Cleared all audit events")
            
        except Exception as e:
            log.error("Failed to clear audit events", error=str(e))
            raise AuditError(f"Failed to clear audit events: {e}", operation="clear_events")

    def export_events(self, output_path: str, decrypt: bool = False) -> None:
        """
        Export audit events to a file.
        
        Args:
            output_path: Path to export the events to
            decrypt: Whether to decrypt sensitive data in the export
            
        Raises:
            AuditError: If export fails
        """
        try:
            events = self.get_events(decrypt=decrypt)
            
            with open(output_path, 'w') as f:
                json.dump(events, f, indent=2, default=str)
            
            os.chmod(output_path, 0o600)  # Secure permissions
            log.info("Exported audit events", output_path=output_path, count=len(events))
            
        except Exception as e:
            log.error("Failed to export audit events", output_path=output_path, error=str(e))
            raise AuditError(f"Failed to export audit events: {e}", operation="export_events")