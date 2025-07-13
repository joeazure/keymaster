"""
Service and environment selection utilities for CLI commands.
Eliminates code duplication across CLI functions.
"""

from typing import List, Tuple, Optional, Set
from keymaster.security import KeyStore
from keymaster.providers import get_providers, get_provider_by_name
from keymaster.utils import prompt_selection
from keymaster.exceptions import ServiceNotFoundError, EnvironmentNotFoundError, _get_closest_matches
from collections import defaultdict


class ServiceEnvironmentSelector:
    """Handles service and environment selection for CLI commands."""
    
    @staticmethod
    def get_services_with_keys() -> Set[str]:
        """Get set of service names that have stored keys."""
        stored_keys = KeyStore.list_keys()
        if not stored_keys:
            return set()
            
        # Get unique services that have stored keys and map to canonical names
        stored_service_names = set(service.lower() for service, _, _, _ in stored_keys)
        available_providers = {
            name: provider 
            for name, provider in get_providers().items()
            if name in stored_service_names
        }
        
        return {provider.service_name for provider in available_providers.values()}
    
    @staticmethod
    def get_environments_for_service(service_name: str) -> List[str]:
        """Get list of environments that have stored keys for a service."""
        stored_keys = KeyStore.list_keys()
        if not stored_keys:
            return []
            
        # Get environments that actually have stored keys for this service
        available_environments = sorted(set(
            env for svc, env, _, _ in stored_keys 
            if svc.lower() == service_name.lower()
        ))
        
        return available_environments
    
    @staticmethod
    def select_service_with_keys(prompt_message: str = "Select service:") -> Optional[str]:
        """
        Prompt user to select a service that has stored keys.
        
        Args:
            prompt_message: Custom prompt message
            
        Returns:
            Selected canonical service name, or None if no services available
        """
        services = ServiceEnvironmentSelector.get_services_with_keys()
        if not services:
            return None
            
        service, _ = prompt_selection(
            prompt_message,
            sorted(services),
            show_descriptions=True
        )
        return service
    
    @staticmethod
    def select_environment_for_service(
        service_name: str, 
        prompt_message: Optional[str] = None,
        allow_new: bool = False
    ) -> Optional[str]:
        """
        Prompt user to select an environment for a specific service.
        
        Args:
            service_name: The service to select environment for
            prompt_message: Custom prompt message (auto-generated if None)
            allow_new: Whether to allow creating new environments
            
        Returns:
            Selected environment name, or None if no environments available
        """
        environments = ServiceEnvironmentSelector.get_environments_for_service(service_name)
        if not environments and not allow_new:
            return None
            
        if prompt_message is None:
            prompt_message = f"Select environment for {service_name}:"
            
        environment, _ = prompt_selection(
            prompt_message,
            environments,
            allow_new=allow_new
        )
        return environment
    
    @staticmethod
    def get_canonical_service_name(service_input: str) -> Optional[str]:
        """
        Get the canonical service name from user input.
        
        Args:
            service_input: User input for service name
            
        Returns:
            Canonical service name, or None if provider not found
        """
        provider = get_provider_by_name(service_input)
        if not provider:
            return None
        return provider.service_name
    
    @staticmethod
    def validate_service_has_environment(service_name: str, environment: str) -> bool:
        """
        Check if a service has a specific environment configured.
        
        Args:
            service_name: The canonical service name
            environment: The environment to check
            
        Returns:
            True if the service has the environment, False otherwise
        """
        environments = ServiceEnvironmentSelector.get_environments_for_service(service_name)
        return environment in environments
    
    @staticmethod
    def get_all_available_services() -> List[str]:
        """Get all available service names from registered providers."""
        return [provider.service_name for provider in get_providers().values()]
    
    @staticmethod
    def find_service_with_fuzzy_matching(service_input: str) -> str:
        """
        Find a service name using fuzzy matching.
        
        Args:
            service_input: User input for service name
            
        Returns:
            Best matching service name
            
        Raises:
            ServiceNotFoundError: If no good matches found
        """
        # First try exact match
        provider = get_provider_by_name(service_input)
        if provider:
            return provider.service_name
            
        # Try fuzzy matching against all available services
        all_services = ServiceEnvironmentSelector.get_all_available_services()
        matches = _get_closest_matches(service_input, all_services)
        
        if not matches:
            raise ServiceNotFoundError(service_input, all_services)
            
        # Return the best match (first in the list)
        return matches[0]
    
    @staticmethod
    def find_environment_with_fuzzy_matching(
        environment_input: str, 
        service_name: str
    ) -> str:
        """
        Find an environment name using fuzzy matching.
        
        Args:
            environment_input: User input for environment name
            service_name: The service to find environment for
            
        Returns:
            Best matching environment name
            
        Raises:
            EnvironmentNotFoundError: If no good matches found
        """
        available_environments = ServiceEnvironmentSelector.get_environments_for_service(service_name)
        
        # First try exact match
        if environment_input in available_environments:
            return environment_input
            
        # Try fuzzy matching
        matches = _get_closest_matches(environment_input, available_environments)
        
        if not matches:
            raise EnvironmentNotFoundError(environment_input, service_name, available_environments)
            
        # Return the best match (first in the list)
        return matches[0]