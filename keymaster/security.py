import keyring
import structlog
from typing import List, Tuple

log = structlog.get_logger()

class KeychainSecurity:
    """
    Provides secure storage and retrieval of API keys using macOS Keychain.
    """

    @staticmethod
    def store_key(service: str, environment: str, api_key: str) -> None:
        """
        Store an API key in the system's macOS Keychain.
        :param service: Name of the service (e.g., OpenAI).
        :param environment: Environment name (dev, staging, prod).
        :param api_key: The actual API key.
        """
        keyring.set_password(f"keymaster-{service}", environment, api_key)
        log.info("Stored key in Keychain", service=service, environment=environment)

    @staticmethod
    def get_key(service: str, environment: str) -> str | None:
        """
        Retrieve an API key from the macOS Keychain.
        :param service: Name of the service.
        :param environment: Environment name.
        :return: The stored API key or None if not found.
        """
        key = keyring.get_password(f"keymaster-{service}", environment)
        if key is None:
            log.warning("API key not found", service=service, environment=environment)
        else:
            log.info("Retrieved key from Keychain", service=service, environment=environment)
        return key

    @staticmethod
    def remove_key(service: str, environment: str) -> None:
        """
        Remove an API key from the macOS Keychain.
        :param service: Name of the service.
        :param environment: Environment name.
        """
        keyring.delete_password(f"keymaster-{service}", environment)
        log.info("Removed key from Keychain", service=service, environment=environment)

    @staticmethod
    def list_keys(filter_service: str | None = None) -> List[Tuple[str, str]]:
        """
        List all stored keys (service name and environment only).
        Because Keyring does not provide a direct way to enumerate, 
        keep track in a separate config or similar approach in real usage.
        
        For demonstration, we will store discovered keys in memory or a separate 
        config structure. Currently, returns an empty list or a dummy list for example.
        :param filter_service: Return only keys for a specific service if provided.
        :return: List of tuples (service, environment).
        """
        # NOTE: Keyring does not provide a built-in listing mechanism for all keys.
        # In a real app, you could keep a separate index in config or rely on 
        # OS keychain tools. For now, we'll just return a placeholder.
        # 
        # Example usage:
        #   Return [("OpenAI", "dev"), ("OpenAI", "prod"), ("Anthropic", "staging")]
        
        dummy_data = [
            ("OpenAI", "dev"),
            ("OpenAI", "prod"),
            ("Anthropic", "staging")
        ]
        if filter_service:
            return [(s, e) for (s, e) in dummy_data if s == filter_service]
        return dummy_data 