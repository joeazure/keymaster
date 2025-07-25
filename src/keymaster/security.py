import keyring
import structlog
from typing import List, Tuple, Optional
from datetime import datetime
import os
from keymaster.db import KeyDatabase
import sys
from keyring.errors import KeyringError
from keymaster.exceptions import KeyringError as KeymasterKeyringError, StorageError

log = structlog.get_logger()

class KeyStore:
    """
    Provides secure storage and retrieval of API keys using the system's secure storage.
    Supports multiple backends through the keyring module:
    - macOS: Keychain
    - Windows: Windows Credential Locker
    - Linux: SecretService (GNOME Keyring/KWallet)
    
    Falls back to an encrypted file if no secure backend is available.
    """
    
    @classmethod
    def _verify_backend(cls) -> None:
        """
        Verify that a secure backend is being used.
        Raises KeyringError if no secure backend is available.
        """
        # Try to set the most secure backend for the current platform
        if sys.platform == "darwin":
            try:
                from keyring.backends import macOS
                keyring.set_keyring(macOS.Keyring())
            except Exception as e:
                log.warning("Failed to set macOS Keychain backend", error=str(e))
        elif sys.platform == "win32":
            try:
                from keyring.backends import Windows
                keyring.set_keyring(Windows.WinVaultKeyring())
            except Exception as e:
                log.warning("Failed to set Windows Credential Locker backend", error=str(e))
        elif sys.platform.startswith("linux"):
            try:
                from keyring.backends import SecretService
                keyring.set_keyring(SecretService.Keyring())
            except Exception as e:
                log.warning("Failed to set SecretService backend", error=str(e))
                
        # Get the current backend
        backend = keyring.get_keyring()
        backend_name = backend.__class__.__name__
        log.info("Current backend", backend=backend_name)
        
        # List of known secure backend names
        secure_backend_names = {
            "Keyring",              # macOS Keychain
            "WinVaultKeyring",      # Windows Credential Locker
            "SecretService.Keyring", # Linux SecretService
            "DBusKeyring",          # KDE KWallet
        }
        
        # Allow ChainerBackend in test environments
        is_test_env = "pytest" in sys.modules
        if is_test_env and backend_name == "ChainerBackend":
            log.warning("Using ChainerBackend in test environment")
            return
        
        if backend_name not in secure_backend_names:
            raise KeymasterKeyringError(
                f"No secure keyring backend available. Current backend: {backend_name}\n"
                "Please install and configure one of the following:\n"
                "- macOS: Keychain (built-in)\n"
                "- Windows: Windows Credential Locker (built-in)\n"
                "- Linux: SecretService (gnome-keyring or kwallet)",
                backend=backend_name
            )
            
        log.info("Using keyring backend", backend=backend_name)
    
    @staticmethod
    def _get_keyring_service_name(service: str, environment: str) -> str:
        """Generate the keyring service name."""
        return f"keymaster-{service.lower()}"
    
    @classmethod
    def store_key(cls, service: str, environment: str, api_key: str) -> None:
        """
        Store an API key in the system's secure storage.
        
        Args:
            service: Service name (e.g., OpenAI)
            environment: Environment name (e.g., dev, prod)
            api_key: The API key to store
            
        Raises:
            KeyringError: If no secure backend is available
        """
        cls._verify_backend()
        
        # Always use lowercase for storage
        service_lower = service.lower()
        keyring_service = cls._get_keyring_service_name(service_lower, environment)
        keyring.set_password(keyring_service, environment.lower(), api_key)
        
        # Store metadata in SQLite with lowercase service name
        db = KeyDatabase()
        db.add_key(
            service_name=service_lower,  # Store as lowercase
            environment=environment,
            keychain_service_name=keyring_service,
            user=os.getlogin()
        )
        
        log.info("Stored key in secure storage", 
                service=service,  # Log original case for readability
                environment=environment,
                backend=keyring.get_keyring().__class__.__name__)

    @classmethod
    def get_key(cls, service: str, environment: str) -> Optional[str]:
        """
        Retrieve an API key from the system's secure storage.
        
        Args:
            service: Service name (e.g., OpenAI)
            environment: Environment name (e.g., dev, prod)
            
        Returns:
            The API key if found, None otherwise
            
        Raises:
            KeyringError: If no secure backend is available
        """
        cls._verify_backend()
        
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
            log.info("Retrieved key from secure storage", 
                    service=service, 
                    environment=environment,
                    backend=keyring.get_keyring().__class__.__name__)
        return key

    @classmethod
    def remove_key(cls, service: str, environment: str) -> None:
        """
        Remove an API key from the system's secure storage.
        
        Args:
            service: Service name (e.g., OpenAI)
            environment: Environment name (e.g., dev, prod)
            
        Raises:
            KeyringError: If no secure backend is available
        """
        cls._verify_backend()
        
        # First check if key exists in metadata
        db = KeyDatabase()
        metadata = db.get_key_metadata(service, environment)
        if not metadata:
            log.warning("Key metadata not found", service=service, environment=environment)
            return
            
        try:
            keyring.delete_password(
                metadata['keychain_service_name'],
                environment.lower()
            )
            
            # Remove from database
            db.remove_key(service, environment)
            
            log.info("Removed key from secure storage", 
                    service=service, 
                    environment=environment,
                    backend=keyring.get_keyring().__class__.__name__)
        except keyring.errors.PasswordDeleteError:
            log.warning("Key not found in secure storage", 
                       service=service, 
                       environment=environment)

    @classmethod
    def list_keys(cls, service: Optional[str] = None) -> List[Tuple[str, str, str, str]]:
        """
        List all stored API keys (service and environment names only).
        
        Args:
            service: Optional service name to filter by
            
        Returns:
            List of (service, environment, updated_at, last_updated_by) tuples using canonical service names
            
        Raises:
            KeyringError: If no secure backend is available
        """
        cls._verify_backend()
        
        db = KeyDatabase()
        keys = db.list_keys(service)
        
        # Convert service names to canonical form using providers
        from keymaster.providers import get_provider_by_name, _load_generic_providers
        
        # Ensure generic providers are loaded
        _load_generic_providers()
        
        normalized_keys = []
        for svc, env, updated_at, updated_by in keys:
            provider = get_provider_by_name(svc)
            if provider:
                # Use the provider's canonical service name
                normalized_keys.append((provider.service_name, env, updated_at, updated_by))
            else:
                # Keep the original case for generic providers
                normalized_keys.append((svc, env, updated_at, updated_by))
        
        if service:
            # Filter using case-insensitive comparison but preserve original case
            service_lower = service.lower()
            normalized_keys = [
                (s, e, u, b) for s, e, u, b in normalized_keys 
                if s.lower() == service_lower
            ]
            
        return normalized_keys 

    @classmethod
    def get_key_metadata(cls, service: str, environment: str) -> Optional[dict]:
        """
        Get metadata for a key without retrieving the key itself.
        
        Args:
            service: Service name
            environment: Environment name
            
        Returns:
            Dict with metadata if found, None otherwise
        """
        cls._verify_backend()
        db = KeyDatabase()
        return db.get_key_metadata(service, environment)
        
    @classmethod
    def remove_key_metadata(cls, service: str, environment: str) -> None:
        """
        Remove metadata for a key without touching the key in secure storage.
        
        Args:
            service: Service name
            environment: Environment name
        """
        cls._verify_backend()
        db = KeyDatabase()
        db.remove_key(service, environment)

    @classmethod
    def get_system_key(cls, key_name: str) -> Optional[str]:
        """
        Retrieve a system/internal key from secure storage.
        
        Args:
            key_name: Name of the system key (e.g., 'audit_encryption')
            
        Returns:
            The key if found, None otherwise
            
        Raises:
            KeymasterKeyringError: If no secure backend is available
        """
        cls._verify_backend()
        
        try:
            key = keyring.get_password("keymaster-system", key_name)
            if key:
                log.info("Retrieved system key from secure storage", key_name=key_name)
            return key
        except Exception as e:
            log.error("Failed to retrieve system key", key_name=key_name, error=str(e))
            raise StorageError(f"Failed to retrieve system key '{key_name}': {e}", operation="get_system_key")

    @classmethod
    def store_system_key(cls, key_name: str, key_value: str) -> None:
        """
        Store a system/internal key in secure storage.
        
        Args:
            key_name: Name of the system key (e.g., 'audit_encryption')
            key_value: The key value to store
            
        Raises:
            KeymasterKeyringError: If no secure backend is available
        """
        cls._verify_backend()
        
        try:
            keyring.set_password("keymaster-system", key_name, key_value)
            log.info("Stored system key in secure storage", key_name=key_name)
        except Exception as e:
            log.error("Failed to store system key", key_name=key_name, error=str(e))
            raise StorageError(f"Failed to store system key '{key_name}': {e}", operation="store_system_key")

    @classmethod
    def remove_system_key(cls, key_name: str) -> None:
        """
        Remove a system/internal key from secure storage.
        
        Args:
            key_name: Name of the system key to remove
            
        Raises:
            KeymasterKeyringError: If no secure backend is available
        """
        cls._verify_backend()
        
        try:
            keyring.delete_password("keymaster-system", key_name)
            log.info("Removed system key from secure storage", key_name=key_name)
        except keyring.errors.PasswordDeleteError:
            log.warning("System key not found in secure storage", key_name=key_name)
        except Exception as e:
            log.error("Failed to remove system key", key_name=key_name, error=str(e))
            raise StorageError(f"Failed to remove system key '{key_name}': {e}", operation="remove_system_key") 