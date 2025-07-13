"""
Enhanced key rotation system for Keymaster.

This module provides comprehensive key rotation capabilities including
automatic backup, rotation tracking, and provider-specific workflows.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import structlog

from keymaster.security import KeyStore
from keymaster.backup import BackupManager
from keymaster.audit import AuditLogger
from keymaster.providers import get_provider_by_name
from keymaster.exceptions import KeymasterError
from keymaster.memory_security import secure_temp_string, secure_zero_memory

log = structlog.get_logger()


class RotationError(KeymasterError):
    """Raised when key rotation fails."""
    
    def __init__(self, message: str, service: str = None, environment: str = None):
        super().__init__(message)
        self.service = service
        self.environment = environment
        self.context = {"service": service, "environment": environment}


class KeyRotationHistory:
    """Tracks key rotation history and schedules."""
    
    def __init__(self):
        self.history_file = os.path.expanduser("~/.keymaster/rotation_history.json")
        self._ensure_history_file()
    
    def _ensure_history_file(self) -> None:
        """Ensure rotation history file exists."""
        history_dir = os.path.dirname(self.history_file)
        if not os.path.exists(history_dir):
            os.makedirs(history_dir, mode=0o700)
        
        if not os.path.exists(self.history_file):
            self._write_history({})
    
    def _read_history(self) -> Dict[str, Any]:
        """Read rotation history from file."""
        try:
            with open(self.history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            log.warning("Failed to read rotation history", error=str(e))
            return {}
    
    def _write_history(self, history: Dict[str, Any]) -> None:
        """Write rotation history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(history, f, indent=2)
            os.chmod(self.history_file, 0o600)
        except Exception as e:
            log.error("Failed to write rotation history", error=str(e))
    
    def record_rotation(
        self, 
        service: str, 
        environment: str, 
        success: bool,
        backup_path: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Record a rotation attempt."""
        history = self._read_history()
        
        key = f"{service}:{environment}"
        if key not in history:
            history[key] = {"rotations": []}
        
        rotation_record = {
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "user": os.getenv("USER", "unknown"),
            "backup_path": backup_path,
            "error_message": error_message
        }
        
        history[key]["rotations"].append(rotation_record)
        
        # Keep only last 10 rotations
        history[key]["rotations"] = history[key]["rotations"][-10:]
        
        # Update last rotation timestamp
        if success:
            history[key]["last_successful_rotation"] = rotation_record["timestamp"]
        
        self._write_history(history)
    
    def get_rotation_history(self, service: str, environment: str) -> List[Dict[str, Any]]:
        """Get rotation history for a specific key."""
        history = self._read_history()
        key = f"{service}:{environment}"
        return history.get(key, {}).get("rotations", [])
    
    def get_last_rotation(self, service: str, environment: str) -> Optional[Dict[str, Any]]:
        """Get the last successful rotation for a key."""
        rotations = self.get_rotation_history(service, environment)
        successful_rotations = [r for r in rotations if r["success"]]
        return successful_rotations[-1] if successful_rotations else None
    
    def get_keys_due_for_rotation(self, days_threshold: int = 90) -> List[Tuple[str, str, datetime]]:
        """Get keys that are due for rotation based on age."""
        history = self._read_history()
        due_keys = []
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        
        # Check all stored keys
        stored_keys = KeyStore.list_keys()
        for service, environment, updated_at, _ in stored_keys:
            key = f"{service}:{environment}"
            
            # Check if we have rotation history
            if key in history and "last_successful_rotation" in history[key]:
                last_rotation = datetime.fromisoformat(history[key]["last_successful_rotation"])
            else:
                # Use key creation/update time
                last_rotation = datetime.fromisoformat(updated_at)
            
            if last_rotation < threshold_date:
                due_keys.append((service, environment, last_rotation))
        
        return due_keys
    
    def get_rotation_stats(self) -> Dict[str, Any]:
        """Get overall rotation statistics."""
        history = self._read_history()
        stats = {
            "total_keys_tracked": len(history),
            "total_rotations": 0,
            "successful_rotations": 0,
            "failed_rotations": 0,
            "keys_never_rotated": 0,
            "oldest_key": None,
            "newest_rotation": None
        }
        
        oldest_date = None
        newest_date = None
        
        for key_data in history.values():
            rotations = key_data.get("rotations", [])
            stats["total_rotations"] += len(rotations)
            
            successful = [r for r in rotations if r["success"]]
            stats["successful_rotations"] += len(successful)
            stats["failed_rotations"] += len(rotations) - len(successful)
            
            if not successful:
                stats["keys_never_rotated"] += 1
            else:
                last_rotation_date = datetime.fromisoformat(successful[-1]["timestamp"])
                if newest_date is None or last_rotation_date > newest_date:
                    newest_date = last_rotation_date
                    stats["newest_rotation"] = successful[-1]["timestamp"]
            
            # Find oldest key
            if rotations:
                first_rotation_date = datetime.fromisoformat(rotations[0]["timestamp"])
                if oldest_date is None or first_rotation_date < oldest_date:
                    oldest_date = first_rotation_date
                    stats["oldest_key"] = rotations[0]["timestamp"]
        
        return stats


class KeyRotator:
    """Manages key rotation operations with backup and validation."""
    
    def __init__(self):
        self.backup_manager = BackupManager()
        self.audit_logger = AuditLogger()
        self.history = KeyRotationHistory()
    
    def rotate_key(
        self,
        service: str,
        environment: str,
        new_key: str,
        test_key: bool = True,
        create_backup: bool = True,
        backup_password: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform enhanced key rotation with backup and validation.
        
        Args:
            service: Service name
            environment: Environment name
            new_key: New API key
            test_key: Whether to test the new key before storing
            create_backup: Whether to create backup before rotation
            backup_password: Password for backup encryption
            
        Returns:
            Dict with rotation results
            
        Raises:
            RotationError: If rotation fails
        """
        log.info("Starting key rotation", service=service, environment=environment)
        
        try:
            with secure_temp_string(new_key) as secure_new_key:
                return self._perform_rotation(
                    service, environment, secure_new_key,
                    test_key, create_backup, backup_password
                )
        except Exception as e:
            log.error("Key rotation failed", service=service, environment=environment, error=str(e))
            self.history.record_rotation(service, environment, False, error_message=str(e))
            raise RotationError(f"Key rotation failed: {str(e)}", service, environment)
    
    def _perform_rotation(
        self,
        service: str,
        environment: str,
        secure_new_key,
        test_key: bool,
        create_backup: bool,
        backup_password: Optional[str]
    ) -> Dict[str, Any]:
        """Internal rotation implementation."""
        rotation_result = {
            "service": service,
            "environment": environment,
            "timestamp": datetime.now().isoformat(),
            "backup_created": False,
            "backup_path": None,
            "key_tested": False,
            "old_key_backed_up": False,
            "rotation_successful": False
        }
        
        # Get current key
        old_key = KeyStore.get_key(service, environment)
        
        # Step 1: Create backup if requested
        backup_path = None
        if create_backup and old_key:
            backup_path = self._create_pre_rotation_backup(
                service, environment, backup_password
            )
            rotation_result["backup_created"] = True
            rotation_result["backup_path"] = backup_path
        
        # Step 2: Test new key if requested
        if test_key:
            self._test_new_key(service, secure_new_key.get())
            rotation_result["key_tested"] = True
        
        # Step 3: Create timestamped backup of old key in keystore
        if old_key:
            self._backup_old_key_in_keystore(service, environment, old_key)
            rotation_result["old_key_backed_up"] = True
        
        # Step 4: Store new key
        KeyStore.store_key(service, environment, secure_new_key.get())
        rotation_result["rotation_successful"] = True
        
        # Step 5: Record rotation in history
        self.history.record_rotation(
            service, environment, True, backup_path
        )
        
        # Step 6: Log audit event
        self.audit_logger.log_event(
            event_type="key_rotation_enhanced",
            service=service,
            environment=environment,
            user=os.getenv("USER", "unknown"),
            additional_data={
                "backup_created": rotation_result["backup_created"],
                "key_tested": rotation_result["key_tested"],
                "old_key_existed": bool(old_key)
            }
        )
        
        log.info("Key rotation completed successfully", 
                service=service, environment=environment)
        
        return rotation_result
    
    def _create_pre_rotation_backup(
        self, 
        service: str, 
        environment: str, 
        password: Optional[str]
    ) -> str:
        """Create a backup before rotation."""
        if not password:
            # Generate a default password based on timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            password = f"rotation_backup_{timestamp}"
        
        backup_dir = os.path.expanduser("~/.keymaster/rotation_backups")
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir, mode=0o700)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"pre_rotation_{service}_{environment}_{timestamp}.kmbackup"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        self.backup_manager.create_backup(
            backup_path=backup_path,
            password=password,
            include_audit_logs=False,
            service_filter=service,
            environment_filter=environment
        )
        
        return backup_path
    
    def _test_new_key(self, service: str, new_key: str) -> None:
        """Test the new key with the provider."""
        provider = get_provider_by_name(service)
        if not provider:
            raise RotationError(f"Provider not found for service: {service}", service)
        
        try:
            provider.test_key(new_key)
        except Exception as e:
            raise RotationError(f"New key validation failed: {str(e)}", service)
    
    def _backup_old_key_in_keystore(
        self, 
        service: str, 
        environment: str, 
        old_key: str
    ) -> None:
        """Backup old key in keystore with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_service = f"{service}_backup_{timestamp}"
        
        try:
            KeyStore.store_key(backup_service, environment, old_key)
            log.info("Old key backed up in keystore", 
                    original_service=service, backup_service=backup_service)
        except Exception as e:
            log.warning("Failed to backup old key in keystore", 
                       service=service, error=str(e))
    
    def rollback_rotation(
        self, 
        service: str, 
        environment: str, 
        backup_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rollback a key rotation by restoring from backup.
        
        Args:
            service: Service name
            environment: Environment name
            backup_path: Path to backup file (if None, looks for recent backup)
            
        Returns:
            Dict with rollback results
        """
        log.info("Starting rotation rollback", service=service, environment=environment)
        
        try:
            # Find backup if not provided
            if not backup_path:
                backup_path = self._find_recent_backup(service, environment)
                if not backup_path:
                    raise RotationError("No recent backup found for rollback", service, environment)
            
            # Get backup password (in real implementation, this would be stored securely)
            password = input("Enter backup password: ")
            
            # Restore from backup
            restore_result = self.backup_manager.restore_backup(
                backup_path=backup_path,
                password=password,
                overwrite_existing=True
            )
            
            # Record rollback in history
            self.history.record_rotation(
                service, environment, True, backup_path, "Rollback operation"
            )
            
            # Log audit event
            self.audit_logger.log_event(
                event_type="key_rotation_rollback",
                service=service,
                environment=environment,
                user=os.getenv("USER", "unknown"),
                additional_data={
                    "backup_path": backup_path,
                    "restore_result": restore_result
                }
            )
            
            return {
                "rollback_successful": True,
                "backup_path": backup_path,
                "restore_result": restore_result
            }
            
        except Exception as e:
            log.error("Rotation rollback failed", service=service, environment=environment, error=str(e))
            raise RotationError(f"Rollback failed: {str(e)}", service, environment)
    
    def _find_recent_backup(self, service: str, environment: str) -> Optional[str]:
        """Find the most recent backup for a service/environment."""
        backup_dir = os.path.expanduser("~/.keymaster/rotation_backups")
        if not os.path.exists(backup_dir):
            return None
        
        pattern = f"pre_rotation_{service}_{environment}_"
        backups = [f for f in os.listdir(backup_dir) if f.startswith(pattern)]
        
        if not backups:
            return None
        
        # Sort by timestamp (newest first)
        backups.sort(reverse=True)
        return os.path.join(backup_dir, backups[0])
    
    def list_rotation_candidates(self, days_threshold: int = 90) -> List[Dict[str, Any]]:
        """List keys that are candidates for rotation."""
        due_keys = self.history.get_keys_due_for_rotation(days_threshold)
        
        candidates = []
        for service, environment, last_rotation in due_keys:
            days_since_rotation = (datetime.now() - last_rotation).days
            
            candidates.append({
                "service": service,
                "environment": environment,
                "last_rotation": last_rotation.isoformat(),
                "days_since_rotation": days_since_rotation,
                "urgency": "high" if days_since_rotation > 180 else "medium" if days_since_rotation > 120 else "low"
            })
        
        # Sort by urgency and days since rotation
        urgency_order = {"high": 3, "medium": 2, "low": 1}
        candidates.sort(key=lambda x: (urgency_order[x["urgency"]], x["days_since_rotation"]), reverse=True)
        
        return candidates