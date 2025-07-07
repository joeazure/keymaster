"""
Tests for the exceptions module.
"""
import pytest
from keymaster.exceptions import (
    KeymasterError, ValidationError, ServiceNotFoundError, 
    EnvironmentNotFoundError, KeyValidationError, StorageError,
    _get_closest_matches
)


class TestExceptionHierarchy:
    """Test exception hierarchy and base functionality."""
    
    def test_keymaster_error_base(self):
        """Test KeymasterError base exception."""
        error = KeymasterError("Test error", context={"key": "value"})
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.context == {"key": "value"}
    
    def test_validation_error(self):
        """Test ValidationError with field information."""
        error = ValidationError("Invalid field", field="api_key", value="bad_value")
        assert str(error) == "Invalid field"
        assert error.field == "api_key"
        assert error.value == "bad_value"
        assert error.context["field"] == "api_key"
        assert error.context["value"] == "bad_value"


class TestServiceNotFoundError:
    """Test ServiceNotFoundError functionality."""
    
    def test_service_not_found_basic(self):
        """Test basic ServiceNotFoundError."""
        error = ServiceNotFoundError("testservice")
        assert "testservice" in str(error)
        assert error.service_name == "testservice"
    
    def test_service_not_found_with_suggestions(self):
        """Test ServiceNotFoundError with suggestions."""
        available = ["openai", "anthropic", "stability"]
        error = ServiceNotFoundError("openapi", available_services=available)
        assert "openapi" in str(error)
        assert "Did you mean" in str(error)
        assert "openai" in str(error)  # Should suggest similar name
        assert error.suggestions  # Should have suggestions
    
    def test_service_not_found_with_available_list(self):
        """Test ServiceNotFoundError with available services."""
        available = ["openai", "anthropic"]
        error = ServiceNotFoundError("unknown", available_services=available)
        assert "Available services" in str(error)
        assert "anthropic" in str(error)
        assert "openai" in str(error)


class TestEnvironmentNotFoundError:
    """Test EnvironmentNotFoundError functionality."""
    
    def test_environment_not_found_basic(self):
        """Test basic EnvironmentNotFoundError."""
        error = EnvironmentNotFoundError("testing")
        assert "testing" in str(error)
        assert error.environment == "testing"
    
    def test_environment_not_found_with_service(self):
        """Test EnvironmentNotFoundError with service context."""
        error = EnvironmentNotFoundError("testing", service="openai")
        assert "testing" in str(error)
        assert "openai" in str(error)
        assert error.service == "openai"
    
    def test_environment_not_found_with_suggestions(self):
        """Test EnvironmentNotFoundError with suggestions."""
        available = ["dev", "staging", "prod"]
        error = EnvironmentNotFoundError("development", available_environments=available)
        assert "development" in str(error)
        assert "Did you mean" in str(error)
        assert "dev" in str(error)  # Should suggest similar name


class TestKeyValidationError:
    """Test KeyValidationError functionality."""
    
    def test_key_validation_error(self):
        """Test KeyValidationError with context."""
        error = KeyValidationError("Invalid key format", api_key_prefix="sk-123", provider="openai")
        assert "Invalid key format" in str(error)
        assert error.api_key_prefix == "sk-123"
        assert error.provider == "openai"
        assert error.context["provider"] == "openai"
        assert error.context["key_prefix"] == "sk-123"


class TestStorageError:
    """Test StorageError functionality."""
    
    def test_storage_error(self):
        """Test StorageError with operation context."""
        error = StorageError("Failed to store", operation="store_key", service="openai")
        assert "Failed to store" in str(error)
        assert error.operation == "store_key"
        assert error.service == "openai"
        assert error.context["operation"] == "store_key"
        assert error.context["service"] == "openai"


class TestFuzzyMatching:
    """Test fuzzy matching functionality."""
    
    def test_get_closest_matches(self):
        """Test fuzzy string matching."""
        candidates = ["openai", "anthropic", "stability", "deepseek"]
        
        # Test exact match
        matches = _get_closest_matches("openai", candidates)
        assert "openai" in matches
        
        # Test close match
        matches = _get_closest_matches("openapi", candidates)
        assert "openai" in matches
        
        # Test substring match
        matches = _get_closest_matches("anthrop", candidates)
        assert "anthropic" in matches
        
        # Test no good matches
        matches = _get_closest_matches("xyz", candidates)
        assert len(matches) == 0  # No good matches with similarity > 0.3
    
    def test_get_closest_matches_empty(self):
        """Test fuzzy matching with empty inputs."""
        assert _get_closest_matches("", ["test"]) == []
        assert _get_closest_matches("test", []) == []
        assert _get_closest_matches("", []) == []
    
    def test_get_closest_matches_limit(self):
        """Test fuzzy matching respects max matches limit."""
        candidates = ["test1", "test2", "test3", "test4", "test5"]
        matches = _get_closest_matches("test", candidates, max_matches=2)
        assert len(matches) <= 2