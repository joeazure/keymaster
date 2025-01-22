import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
import structlog
from keymaster.config import ConfigManager

log = structlog.get_logger()

class AuditLogger:
    """
    Secure audit logging system for Keymaster operations.
    Encrypts sensitive data in logs while maintaining searchability.
    """
    
    def __init__(self):
        self.config = ConfigManager.load_config()
        self._ensure_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        # Ensure log file exists
        self._ensure_log_file()
        
    def _ensure_encryption_key(self) -> None:
        """Initialize or load encryption key for audit logs."""
        config = ConfigManager.load_config()
        if 'audit' not in config:
            config['audit'] = {}
        
        if 'encryption_key' not in config['audit']:
            self.encryption_key = Fernet.generate_key()
            config['audit']['encryption_key'] = self.encryption_key.decode()
            ConfigManager.write_config(config)
        else:
            self.encryption_key = config['audit']['encryption_key'].encode()

    def _get_log_path(self) -> str:
        """Get the path to the audit log file."""
        home_dir = os.path.expanduser("~")
        log_dir = os.path.join(home_dir, ".keymaster", "logs")
        os.makedirs(log_dir, exist_ok=True)
        return os.path.join(log_dir, "audit.log")

    def _ensure_log_file(self) -> None:
        """Ensure the audit log file exists."""
        log_path = self._get_log_path()
        if not os.path.exists(log_path):
            # Create an empty log file
            with open(log_path, "w") as f:
                pass  # Just create an empty file
            log.info("Created new audit log file", path=log_path)

    def _encrypt_sensitive_data(self, data: str) -> str:
        """Encrypt sensitive data for storage."""
        return self.fernet.encrypt(data.encode()).decode()

    def _decrypt_sensitive_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data from storage."""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

    def log_event(self, 
                event_type: str,
                user: str,
                service: str | None = None,
                environment: str | None = None,
                sensitive_data: str | None = None,
                additional_data: dict | None = None) -> None:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (e.g., add_key, remove_key)
            user: Username performing the action
            service: Optional service name (e.g., OpenAI)
            environment: Optional environment (e.g., dev, prod)
            sensitive_data: Optional sensitive data to encrypt
            additional_data: Optional additional metadata
        """
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
        with open(self._get_log_path(), 'a') as f:
            json.dump(event, f)
            f.write('\n')
            
        log.info("Audit event logged", 
                event_type=event_type, 
                service=service, 
                environment=environment)

    def get_events(self, 
                  start_date: Optional[datetime] = None,
                  end_date: Optional[datetime] = None,
                  event_type: Optional[str] = None,
                  service: Optional[str] = None,
                  environment: Optional[str] = None,
                  decrypt: bool = False) -> list[Dict[str, Any]]:
        """
        Retrieve audit events with optional filtering and decryption.
        """
        events = []
        log_path = self._get_log_path()
        
        # Return empty list if log file is empty
        if os.path.getsize(log_path) == 0:
            return events
            
        with open(log_path, "r") as f:
            for line in f:
                if not line.strip():  # Skip empty lines
                    continue
                event = json.loads(line)
                
                # Apply filters
                if start_date and datetime.fromisoformat(event["timestamp"]) < start_date:
                    continue
                if end_date and datetime.fromisoformat(event["timestamp"]) > end_date:
                    continue
                if event_type and event["event_type"] != event_type:
                    continue
                if service and event["service"] != service:
                    continue
                if environment and event["environment"] != environment:
                    continue
                
                # Optionally decrypt sensitive data
                if decrypt and "encrypted_data" in event:
                    event["decrypted_data"] = self._decrypt_sensitive_data(event["encrypted_data"])
                    
                events.append(event)
                
        return events 