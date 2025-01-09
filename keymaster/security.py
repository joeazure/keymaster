import keyring
import structlog
from typing import List, Tuple
from datetime import datetime
import os
from keymaster.db import KeyDatabase

log = structlog.get_logger()

class KeychainSecurity:
    """
    Provides secure storage and retrieval of API keys using macOS Keychain.
    """
    
    @staticmethod
    def _get_keychain_service_name(service: str, environment: str) -> str:
        """Generate the keychain service name."""
        return f"keymaster-{service.lower()}"
    
    @staticmethod
    def store_key(service: str, environment: str, api_key: str) -> None:
        """
        Store an API key in the system's macOS Keychain.
        """
        keychain_service = KeychainSecurity._get_keychain_service_name(service, environment)
        keyring.set_password(keychain_service, environment.lower(), api_key)
        
        # Store metadata in SQLite
        db = KeyDatabase()
        db.add_key(
            service_name=service,
            environment=environment,
            keychain_service_name=keychain_service,
            user=os.getlogin()
        )
        
        log.info("Stored key in Keychain", service=service, environment=environment)

    @staticmethod
    def get_key(service: str, environment: str) -> str | None:
        """
        Retrieve an API key from the macOS Keychain.
        """
        # First check if key exists in metadata
        db = KeyDatabase()
        metadata = db.get_key_metadata(service, environment)
        if not metadata:
            log.warning("Key metadata not found", service=service, environment=environment)
            return None
            
        key = keyring.get_password(
            metadata['keychain_service_name'],
            environment.lower()
        )
        
        if key is None:
            log.warning("API key not found", service=service, environment=environment)
        else:
            log.info("Retrieved key from Keychain", service=service, environment=environment)
        return key

    @staticmethod
    def remove_key(service: str, environment: str) -> None:
        """
        Remove an API key from the macOS Keychain.
        """
        # First get metadata to know the keychain service name
        db = KeyDatabase()
        metadata = db.get_key_metadata(service, environment)
        if metadata:
            keyring.delete_password(
                metadata['keychain_service_name'],
                environment.lower()
            )
            # Remove metadata after successful keychain deletion
            db.remove_key(service, environment)
            log.info("Removed key from Keychain", service=service, environment=environment)
        else:
            log.warning("Key metadata not found for removal", 
                       service=service, environment=environment)

    @staticmethod
    def list_keys(filter_service: str | None = None) -> List[Tuple[str, str]]:
        """
        List all stored keys (service name and environment only).
        """
        db = KeyDatabase()
        keys = db.list_keys(filter_service)
        return [(key[0], key[1]) for key in keys]  # Return just service and environment 