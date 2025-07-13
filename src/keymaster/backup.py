"""
Backup and restore functionality for Keymaster.

This module provides secure backup and restore capabilities for API keys,
metadata, and audit logs with strong encryption.
"""

import os
import json
import zipfile
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import structlog
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from keymaster.security import KeyStore
from keymaster.audit import AuditLogger
from keymaster.exceptions import BackupError
from keymaster.config import ConfigManager

log = structlog.get_logger()


class BackupManager:
    """Manages backup and restore operations for Keymaster data."""
    
    BACKUP_VERSION = "1.0"
    BACKUP_MAGIC = "KEYMASTER_BACKUP"
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.audit_logger = AuditLogger()
    
    def create_backup(
        self, 
        backup_path: str, 
        password: str,
        include_audit_logs: bool = True,
        service_filter: Optional[str] = None,
        environment_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create an encrypted backup of keys and metadata.
        
        Args:
            backup_path: Path to save the backup file
            password: Password for encryption
            include_audit_logs: Whether to include audit logs
            service_filter: Optional service name filter
            environment_filter: Optional environment filter
            
        Returns:
            Dict with backup summary information
            
        Raises:
            BackupError: If backup creation fails
        """
        try:
            log.info("Starting backup creation", path=backup_path)
            
            # Generate encryption key from password
            encryption_key = self._derive_key_from_password(password)
            fernet = Fernet(encryption_key)
            
            # Collect data to backup
            backup_data = self._collect_backup_data(
                include_audit_logs=include_audit_logs,
                service_filter=service_filter,
                environment_filter=environment_filter
            )
            
            # Create backup file
            backup_summary = self._create_encrypted_backup_file(
                backup_path, backup_data, fernet
            )
            
            # Log backup creation
            self.audit_logger.log_event(
                event_type="backup_created",
                user=os.getenv("USER", "unknown"),
                additional_data={
                    "backup_path": backup_path,
                    "include_audit_logs": include_audit_logs,
                    "service_filter": service_filter,
                    "environment_filter": environment_filter,
                    "summary": backup_summary
                }
            )
            
            log.info("Backup created successfully", summary=backup_summary)
            return backup_summary
            
        except Exception as e:
            log.error("Backup creation failed", error=str(e))
            raise BackupError(f"Failed to create backup: {str(e)}", "create", backup_path)
    
    def restore_backup(
        self, 
        backup_path: str, 
        password: str,
        dry_run: bool = False,
        overwrite_existing: bool = False
    ) -> Dict[str, Any]:
        """
        Restore data from an encrypted backup.
        
        Args:
            backup_path: Path to the backup file
            password: Password for decryption
            dry_run: If True, only validate backup without restoring
            overwrite_existing: Whether to overwrite existing keys
            
        Returns:
            Dict with restore summary information
            
        Raises:
            BackupError: If restore fails
        """
        try:
            log.info("Starting backup restore", path=backup_path, dry_run=dry_run)
            
            # Validate backup file exists
            if not os.path.exists(backup_path):
                raise BackupError(f"Backup file not found: {backup_path}", "restore", backup_path)
            
            # Generate decryption key from password
            encryption_key = self._derive_key_from_password(password)
            fernet = Fernet(encryption_key)
            
            # Extract and decrypt backup data
            backup_data = self._extract_backup_data(backup_path, fernet)
            
            # Validate backup integrity
            self._validate_backup_data(backup_data)
            
            if dry_run:
                return self._analyze_backup_contents(backup_data)
            
            # Perform actual restore
            restore_summary = self._restore_backup_data(backup_data, overwrite_existing)
            
            # Log restore operation
            self.audit_logger.log_event(
                event_type="backup_restored",
                user=os.getenv("USER", "unknown"),
                additional_data={
                    "backup_path": backup_path,
                    "overwrite_existing": overwrite_existing,
                    "summary": restore_summary
                }
            )
            
            log.info("Backup restored successfully", summary=restore_summary)
            return restore_summary
            
        except Exception as e:
            log.error("Backup restore failed", error=str(e))
            raise BackupError(f"Failed to restore backup: {str(e)}", "restore", backup_path)
    
    def list_backup_contents(self, backup_path: str, password: str) -> Dict[str, Any]:
        """
        List contents of a backup file without restoring.
        
        Args:
            backup_path: Path to the backup file
            password: Password for decryption
            
        Returns:
            Dict with backup contents information
        """
        return self.restore_backup(backup_path, password, dry_run=True)
    
    def verify_backup(self, backup_path: str, password: str) -> bool:
        """
        Verify backup file integrity and password.
        
        Args:
            backup_path: Path to the backup file
            password: Password for decryption
            
        Returns:
            True if backup is valid and password is correct
        """
        try:
            self.list_backup_contents(backup_path, password)
            return True
        except Exception:
            return False
    
    def _derive_key_from_password(self, password: str) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        # Use a fixed salt for simplicity - in production, should use random salt stored with backup
        salt = b"keymaster_backup_salt_v1"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _collect_backup_data(
        self, 
        include_audit_logs: bool,
        service_filter: Optional[str],
        environment_filter: Optional[str]
    ) -> Dict[str, Any]:
        """Collect all data to be included in backup."""
        backup_data = {
            "version": self.BACKUP_VERSION,
            "magic": self.BACKUP_MAGIC,
            "created_at": datetime.now().isoformat(),
            "created_by": os.getenv("USER", "unknown"),
            "keys": [],
            "metadata": [],
            "config": {},
            "audit_logs": []
        }
        
        # Collect keys and metadata
        stored_keys = KeyStore.list_keys(service_filter)
        for service, environment, updated_at, updated_by in stored_keys:
            # Apply service filter if specified (KeyStore.list_keys might not filter properly)
            if service_filter and service.lower() != service_filter.lower():
                continue
                
            # Apply environment filter if specified
            if environment_filter and environment != environment_filter:
                continue
                
            # Get the actual key
            key_value = KeyStore.get_key(service, environment)
            if key_value:
                backup_data["keys"].append({
                    "service": service,
                    "environment": environment,
                    "key": key_value,
                    "updated_at": updated_at,
                    "updated_by": updated_by
                })
        
        # Collect configuration
        try:
            config_data = self.config_manager.load_config()
            backup_data["config"] = config_data
        except Exception as e:
            log.warning("Failed to include config in backup", error=str(e))
        
        # Collect audit logs if requested
        if include_audit_logs:
            try:
                # Get all audit events (we'll limit them after retrieval if needed)
                audit_events = self.audit_logger.get_events(decrypt=True)
                # Limit to last 1000 events for backup size management
                backup_data["audit_logs"] = audit_events[-1000:] if len(audit_events) > 1000 else audit_events
            except Exception as e:
                log.warning("Failed to include audit logs in backup", error=str(e))
        
        return backup_data
    
    def _create_encrypted_backup_file(
        self, 
        backup_path: str, 
        backup_data: Dict[str, Any], 
        fernet: Fernet
    ) -> Dict[str, Any]:
        """Create encrypted backup file."""
        # Convert to JSON and encrypt
        json_data = json.dumps(backup_data, indent=2)
        encrypted_data = fernet.encrypt(json_data.encode())
        
        # Create backup file
        backup_dir = os.path.dirname(backup_path)
        if backup_dir and not os.path.exists(backup_dir):
            os.makedirs(backup_dir, mode=0o700)
        
        with open(backup_path, 'wb') as f:
            f.write(encrypted_data)
        
        # Set secure file permissions
        os.chmod(backup_path, 0o600)
        
        # Create summary
        summary = {
            "keys_count": len(backup_data["keys"]),
            "services": list(set(k["service"] for k in backup_data["keys"])),
            "environments": list(set(k["environment"] for k in backup_data["keys"])),
            "audit_logs_count": len(backup_data["audit_logs"]),
            "file_size": os.path.getsize(backup_path),
            "created_at": backup_data["created_at"]
        }
        
        return summary
    
    def _extract_backup_data(self, backup_path: str, fernet: Fernet) -> Dict[str, Any]:
        """Extract and decrypt backup data from file."""
        with open(backup_path, 'rb') as f:
            encrypted_data = f.read()
        
        try:
            decrypted_data = fernet.decrypt(encrypted_data)
            backup_data = json.loads(decrypted_data.decode())
            return backup_data
        except Exception as e:
            raise BackupError(f"Failed to decrypt backup - invalid password or corrupted file: {str(e)}", "decrypt", backup_path)
    
    def _validate_backup_data(self, backup_data: Dict[str, Any]) -> None:
        """Validate backup data structure and integrity."""
        required_fields = ["version", "magic", "created_at", "keys"]
        for field in required_fields:
            if field not in backup_data:
                raise BackupError(f"Invalid backup format - missing field: {field}", "validate")
        
        if backup_data["magic"] != self.BACKUP_MAGIC:
            raise BackupError("Invalid backup format - not a Keymaster backup", "validate")
        
        # Check version compatibility
        if backup_data["version"] != self.BACKUP_VERSION:
            log.warning("Backup version mismatch", 
                       backup_version=backup_data["version"], 
                       current_version=self.BACKUP_VERSION)
    
    def _analyze_backup_contents(self, backup_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze backup contents for dry run."""
        existing_keys = {(s, e) for s, e, _, _ in KeyStore.list_keys()}
        backup_keys = {(k["service"], k["environment"]) for k in backup_data["keys"]}
        
        conflicts = existing_keys.intersection(backup_keys)
        new_keys = backup_keys - existing_keys
        
        return {
            "total_keys": len(backup_data["keys"]),
            "new_keys": len(new_keys),
            "conflicts": len(conflicts),
            "services": list(set(k["service"] for k in backup_data["keys"])),
            "environments": list(set(k["environment"] for k in backup_data["keys"])),
            "audit_logs_count": len(backup_data.get("audit_logs", [])),
            "created_at": backup_data["created_at"],
            "created_by": backup_data.get("created_by", "unknown"),
            "conflicting_keys": list(conflicts),
            "new_keys_list": list(new_keys)
        }
    
    def _restore_backup_data(
        self, 
        backup_data: Dict[str, Any], 
        overwrite_existing: bool
    ) -> Dict[str, Any]:
        """Restore data from backup."""
        restored_keys = 0
        skipped_keys = 0
        errors = []
        
        for key_data in backup_data["keys"]:
            service = key_data["service"]
            environment = key_data["environment"]
            key_value = key_data["key"]
            
            try:
                # Check if key already exists
                existing_key = KeyStore.get_key(service, environment)
                if existing_key and not overwrite_existing:
                    skipped_keys += 1
                    continue
                
                # Store the key
                KeyStore.store_key(service, environment, key_value)
                restored_keys += 1
                
            except Exception as e:
                error_msg = f"Failed to restore key for {service}/{environment}: {str(e)}"
                errors.append(error_msg)
                log.error("Key restore failed", service=service, environment=environment, error=str(e))
        
        return {
            "restored_keys": restored_keys,
            "skipped_keys": skipped_keys,
            "errors": errors,
            "total_processed": len(backup_data["keys"])
        }