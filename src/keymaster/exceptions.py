"""
Custom exceptions for Keymaster.

This module provides a hierarchy of specific exceptions with clear error messages
and context to help users understand and resolve issues.
"""


class KeymasterError(Exception):
    """Base exception for all Keymaster errors."""
    
    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}


class ValidationError(KeymasterError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None, value: str = None):
        super().__init__(message)
        self.field = field
        self.value = value
        if field:
            self.context = {"field": field, "value": value}


class ServiceNotFoundError(KeymasterError):
    """Raised when a requested service is not found."""
    
    def __init__(self, service_name: str, available_services: list = None):
        available = available_services or []
        suggestions = _get_closest_matches(service_name, available)
        
        message = f"Service '{service_name}' not found."
        if suggestions:
            message += f" Did you mean: {', '.join(suggestions)}?"
        if available:
            message += f" Available services: {', '.join(sorted(available))}"
            
        super().__init__(message)
        self.service_name = service_name
        self.available_services = available
        self.suggestions = suggestions


class EnvironmentNotFoundError(KeymasterError):
    """Raised when a requested environment is not found."""
    
    def __init__(self, environment: str, service: str = None, available_environments: list = None):
        available = available_environments or []
        suggestions = _get_closest_matches(environment, available)
        
        message = f"Environment '{environment}' not found"
        if service:
            message += f" for service '{service}'"
        message += "."
        
        if suggestions:
            message += f" Did you mean: {', '.join(suggestions)}?"
        if available:
            message += f" Available environments: {', '.join(sorted(available))}"
            
        super().__init__(message)
        self.environment = environment
        self.service = service
        self.available_environments = available
        self.suggestions = suggestions


class KeyValidationError(KeymasterError):
    """Raised when API key validation fails."""
    
    def __init__(self, message: str, api_key_prefix: str = None, provider: str = None):
        super().__init__(message)
        self.api_key_prefix = api_key_prefix
        self.provider = provider
        self.context = {"provider": provider, "key_prefix": api_key_prefix}


class StorageError(KeymasterError):
    """Raised when there's an error with secure storage operations."""
    
    def __init__(self, message: str, operation: str = None, service: str = None):
        super().__init__(message)
        self.operation = operation
        self.service = service
        self.context = {"operation": operation, "service": service}


class KeyringError(StorageError):
    """Raised when there's an error with keyring operations."""
    
    def __init__(self, message: str, backend: str = None):
        super().__init__(message)
        self.backend = backend
        if backend:
            self.context["backend"] = backend


class ConfigurationError(KeymasterError):
    """Raised when there's an error with configuration."""
    
    def __init__(self, message: str, config_file: str = None):
        super().__init__(message)
        self.config_file = config_file
        if config_file:
            self.context["config_file"] = config_file


class ProviderError(KeymasterError):
    """Raised when there's an error with provider operations."""
    
    def __init__(self, message: str, provider: str = None, operation: str = None):
        super().__init__(message)
        self.provider = provider
        self.operation = operation
        self.context = {"provider": provider, "operation": operation}


class AuditError(KeymasterError):
    """Raised when there's an error with audit operations."""
    
    def __init__(self, message: str, operation: str = None):
        super().__init__(message)
        self.operation = operation
        if operation:
            self.context["operation"] = operation


class DatabaseError(KeymasterError):
    """Raised when there's an error with database operations."""
    
    def __init__(self, message: str, operation: str = None, table: str = None):
        super().__init__(message)
        self.operation = operation
        self.table = table
        self.context = {"operation": operation, "table": table}


class BackupError(KeymasterError):
    """Raised when there's an error with backup/restore operations."""
    
    def __init__(self, message: str, operation: str = None, file_path: str = None):
        super().__init__(message)
        self.operation = operation
        self.file_path = file_path
        self.context = {"operation": operation, "file_path": file_path}


def _get_closest_matches(target: str, candidates: list, max_matches: int = 3) -> list:
    """
    Get the closest matches for a target string from a list of candidates.
    
    Uses simple string similarity based on common characters and length.
    For production use, consider using python-Levenshtein for better fuzzy matching.
    """
    if not candidates or not target:
        return []
    
    target_lower = target.lower()
    
    # Calculate similarity scores
    scored_candidates = []
    for candidate in candidates:
        candidate_lower = candidate.lower()
        
        # Simple similarity: ratio of common characters to total length
        common_chars = sum(1 for c in target_lower if c in candidate_lower)
        max_len = max(len(target_lower), len(candidate_lower))
        similarity = common_chars / max_len if max_len > 0 else 0
        
        # Boost score if target is a substring of candidate or vice versa
        if target_lower in candidate_lower or candidate_lower in target_lower:
            similarity += 0.5
        
        scored_candidates.append((similarity, candidate))
    
    # Sort by similarity score (descending) and return top matches
    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Only return candidates with reasonable similarity (> 0.3)
    good_matches = [candidate for score, candidate in scored_candidates if score > 0.3]
    
    return good_matches[:max_matches]