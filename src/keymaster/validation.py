"""
Input validation for Keymaster.

This module provides comprehensive validation for all user inputs to ensure
security and data integrity.
"""

import re
from typing import Optional, List
from keymaster.exceptions import ValidationError


# Constants for validation
MIN_API_KEY_LENGTH = 8
MAX_API_KEY_LENGTH = 2048
MAX_SERVICE_NAME_LENGTH = 100
MAX_ENVIRONMENT_LENGTH = 50

# Allowed characters for service names (alphanumeric, hyphens, underscores)
SERVICE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')

# Allowed characters for environments (alphanumeric, hyphens, underscores)
ENVIRONMENT_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')

# Common API key patterns for validation
API_KEY_PATTERNS = {
    'openai': re.compile(r'^sk-[a-zA-Z0-9]{48}$'),
    'anthropic': re.compile(r'^sk-ant-[a-zA-Z0-9_-]{93}$'),
    'stability': re.compile(r'^sk-[a-zA-Z0-9]{32}$'),
    'deepseek': re.compile(r'^sk-[a-zA-Z0-9]{48}$'),
}

# Standard environments
STANDARD_ENVIRONMENTS = ['dev', 'development', 'staging', 'stage', 'prod', 'production', 'test', 'testing']


def validate_api_key(api_key: str, provider: str = None) -> str:
    """
    Validate an API key.
    
    Args:
        api_key: The API key to validate
        provider: Optional provider name for specific validation
        
    Returns:
        The validated and cleaned API key
        
    Raises:
        ValidationError: If the API key is invalid
    """
    if not api_key:
        raise ValidationError("API key cannot be empty", field="api_key")
    
    if not isinstance(api_key, str):
        raise ValidationError("API key must be a string", field="api_key")
    
    # Strip whitespace
    api_key = api_key.strip()
    
    if not api_key:
        raise ValidationError("API key cannot be empty or only whitespace", field="api_key")
    
    # Length validation
    if len(api_key) < MIN_API_KEY_LENGTH:
        raise ValidationError(
            f"API key must be at least {MIN_API_KEY_LENGTH} characters long",
            field="api_key"
        )
    
    if len(api_key) > MAX_API_KEY_LENGTH:
        raise ValidationError(
            f"API key must be no more than {MAX_API_KEY_LENGTH} characters long",
            field="api_key"
        )
    
    # Check for common issues
    if api_key.startswith(' ') or api_key.endswith(' '):
        raise ValidationError("API key cannot start or end with whitespace", field="api_key")
    
    if '\n' in api_key or '\r' in api_key or '\t' in api_key:
        raise ValidationError("API key cannot contain newlines or tabs", field="api_key")
    
    # Provider-specific validation
    if provider and provider.lower() in API_KEY_PATTERNS:
        pattern = API_KEY_PATTERNS[provider.lower()]
        if not pattern.match(api_key):
            raise ValidationError(
                f"API key format is invalid for {provider}",
                field="api_key"
            )
    
    # Check for obviously fake or placeholder keys
    fake_patterns = [
        'your_api_key_here',
        'insert_api_key',
        'api_key_placeholder',
        'sk-example',
        'sk-test',
        'sk-fake',
        'sk-placeholder'
    ]
    
    api_key_lower = api_key.lower()
    for pattern in fake_patterns:
        if pattern in api_key_lower:
            raise ValidationError(
                f"API key appears to be a placeholder or example key",
                field="api_key"
            )
    
    return api_key


def validate_service_name(service_name: str) -> str:
    """
    Validate a service name.
    
    Args:
        service_name: The service name to validate
        
    Returns:
        The validated and normalized service name
        
    Raises:
        ValidationError: If the service name is invalid
    """
    if not service_name:
        raise ValidationError("Service name cannot be empty", field="service_name")
    
    if not isinstance(service_name, str):
        raise ValidationError("Service name must be a string", field="service_name")
    
    # Strip whitespace and convert to lowercase for consistency
    service_name = service_name.strip().lower()
    
    if not service_name:
        raise ValidationError("Service name cannot be empty or only whitespace", field="service_name")
    
    # Length validation
    if len(service_name) > MAX_SERVICE_NAME_LENGTH:
        raise ValidationError(
            f"Service name must be no more than {MAX_SERVICE_NAME_LENGTH} characters long",
            field="service_name"
        )
    
    # Pattern validation
    if not SERVICE_NAME_PATTERN.match(service_name):
        raise ValidationError(
            "Service name can only contain letters, numbers, hyphens, and underscores, "
            "and must start with a letter or number",
            field="service_name"
        )
    
    # Reserved names check
    reserved_names = [
        'keymaster', 'system', 'admin', 'root', 'config', 'settings',
        'internal', 'test', 'debug', 'temp', 'tmp'
    ]
    
    if service_name in reserved_names:
        raise ValidationError(
            f"Service name '{service_name}' is reserved and cannot be used",
            field="service_name"
        )
    
    return service_name


def validate_environment(environment: str, service: str = None) -> str:
    """
    Validate an environment name.
    
    Args:
        environment: The environment name to validate
        service: Optional service name for context
        
    Returns:
        The validated and normalized environment name
        
    Raises:
        ValidationError: If the environment is invalid
    """
    if not environment:
        raise ValidationError("Environment cannot be empty", field="environment")
    
    if not isinstance(environment, str):
        raise ValidationError("Environment must be a string", field="environment")
    
    # Strip whitespace and convert to lowercase for consistency
    environment = environment.strip().lower()
    
    if not environment:
        raise ValidationError("Environment cannot be empty or only whitespace", field="environment")
    
    # Length validation
    if len(environment) > MAX_ENVIRONMENT_LENGTH:
        raise ValidationError(
            f"Environment name must be no more than {MAX_ENVIRONMENT_LENGTH} characters long",
            field="environment"
        )
    
    # Pattern validation
    if not ENVIRONMENT_PATTERN.match(environment):
        raise ValidationError(
            "Environment name can only contain letters, numbers, hyphens, and underscores, "
            "and must start with a letter or number",
            field="environment"
        )
    
    # Normalize common environment names
    environment_aliases = {
        'development': 'dev',
        'production': 'prod',
        'staging': 'stage',
        'testing': 'test'
    }
    
    if environment in environment_aliases:
        environment = environment_aliases[environment]
    
    return environment


def validate_file_path(file_path: str, must_exist: bool = False) -> str:
    """
    Validate a file path.
    
    Args:
        file_path: The file path to validate
        must_exist: Whether the file must already exist
        
    Returns:
        The validated file path
        
    Raises:
        ValidationError: If the file path is invalid
    """
    import os
    
    if not file_path:
        raise ValidationError("File path cannot be empty", field="file_path")
    
    if not isinstance(file_path, str):
        raise ValidationError("File path must be a string", field="file_path")
    
    file_path = file_path.strip()
    
    if not file_path:
        raise ValidationError("File path cannot be empty or only whitespace", field="file_path")
    
    # Check for dangerous characters
    dangerous_chars = ['..', '~', '$', '`', ';', '|', '&', '>', '<']
    for char in dangerous_chars:
        if char in file_path:
            raise ValidationError(
                f"File path contains dangerous character: {char}",
                field="file_path"
            )
    
    # Expand user home directory
    file_path = os.path.expanduser(file_path)
    
    if must_exist and not os.path.exists(file_path):
        raise ValidationError(f"File does not exist: {file_path}", field="file_path")
    
    return file_path


def validate_date_string(date_string: str) -> str:
    """
    Validate a date string in YYYY-MM-DD format.
    
    Args:
        date_string: The date string to validate
        
    Returns:
        The validated date string
        
    Raises:
        ValidationError: If the date string is invalid
    """
    from datetime import datetime
    
    if not date_string:
        raise ValidationError("Date cannot be empty", field="date")
    
    if not isinstance(date_string, str):
        raise ValidationError("Date must be a string", field="date")
    
    date_string = date_string.strip()
    
    if not date_string:
        raise ValidationError("Date cannot be empty or only whitespace", field="date")
    
    # Validate format
    date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    if not date_pattern.match(date_string):
        raise ValidationError(
            "Date must be in YYYY-MM-DD format",
            field="date"
        )
    
    # Validate actual date
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
    except ValueError as e:
        raise ValidationError(f"Invalid date: {e}", field="date")
    
    return date_string


def sanitize_for_logging(value: str, max_length: int = 50) -> str:
    """
    Sanitize a string for safe logging.
    
    Args:
        value: The string to sanitize
        max_length: Maximum length for the sanitized string
        
    Returns:
        The sanitized string
    """
    if not value:
        return "<empty>"
    
    if not isinstance(value, str):
        value = str(value)
    
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length-3] + "..."
    
    return sanitized


def get_api_key_preview(api_key: str, show_chars: int = 4) -> str:
    """
    Get a safe preview of an API key for logging/display.
    
    Args:
        api_key: The API key to preview
        show_chars: Number of characters to show at the beginning
        
    Returns:
        A safe preview string
    """
    if not api_key or len(api_key) < show_chars:
        return "***"
    
    return api_key[:show_chars] + "***" + f"({len(api_key)} chars)"