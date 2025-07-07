"""
Tests for the validation module.
"""
import pytest
from keymaster.validation import (
    validate_api_key, validate_service_name, validate_environment,
    validate_file_path, validate_date_string, get_api_key_preview
)
from keymaster.exceptions import ValidationError


class TestAPIKeyValidation:
    """Test API key validation."""
    
    def test_valid_api_key(self):
        """Test valid API key passes validation."""
        api_key = "sk-1234567890abcdef"
        result = validate_api_key(api_key)
        assert result == api_key
    
    def test_empty_api_key(self):
        """Test empty API key raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_api_key("")
        assert exc_info.value.field == "api_key"
        assert "empty" in str(exc_info.value)
    
    def test_api_key_too_short(self):
        """Test API key too short raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_api_key("short")
        assert exc_info.value.field == "api_key"
        assert "at least" in str(exc_info.value)
    
    def test_api_key_too_long(self):
        """Test API key too long raises ValidationError."""
        long_key = "x" * 3000
        with pytest.raises(ValidationError) as exc_info:
            validate_api_key(long_key)
        assert exc_info.value.field == "api_key"
        assert "no more than" in str(exc_info.value)
    
    def test_api_key_with_newlines(self):
        """Test API key with newlines raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_api_key("sk-test\nkey")
        assert exc_info.value.field == "api_key"
        assert "newlines" in str(exc_info.value)
    
    def test_fake_api_key(self):
        """Test obviously fake API key raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_api_key("your_api_key_here")
        assert exc_info.value.field == "api_key"
        assert "placeholder" in str(exc_info.value)
    
    def test_openai_format_validation(self):
        """Test OpenAI-specific API key format validation."""
        # Valid OpenAI key format
        valid_key = "sk-" + "x" * 48
        result = validate_api_key(valid_key, provider="openai")
        assert result == valid_key
        
        # Invalid OpenAI key format
        with pytest.raises(ValidationError) as exc_info:
            validate_api_key("invalid-openai-key", provider="openai")
        assert "invalid for openai" in str(exc_info.value).lower()


class TestServiceNameValidation:
    """Test service name validation."""
    
    def test_valid_service_name(self):
        """Test valid service name passes validation."""
        result = validate_service_name("OpenAI")
        assert result == "openai"  # Should be normalized to lowercase
    
    def test_empty_service_name(self):
        """Test empty service name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_service_name("")
        assert exc_info.value.field == "service_name"
    
    def test_invalid_characters(self):
        """Test service name with invalid characters raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_service_name("test@service")
        assert exc_info.value.field == "service_name"
        assert "letters, numbers" in str(exc_info.value)
    
    def test_reserved_name(self):
        """Test reserved service name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_service_name("keymaster")
        assert exc_info.value.field == "service_name"
        assert "reserved" in str(exc_info.value)


class TestEnvironmentValidation:
    """Test environment validation."""
    
    def test_valid_environment(self):
        """Test valid environment passes validation."""
        result = validate_environment("dev")
        assert result == "dev"
    
    def test_environment_normalization(self):
        """Test environment normalization."""
        assert validate_environment("development") == "dev"
        assert validate_environment("production") == "prod"
        assert validate_environment("staging") == "stage"
    
    def test_empty_environment(self):
        """Test empty environment raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_environment("")
        assert exc_info.value.field == "environment"


class TestDateValidation:
    """Test date string validation."""
    
    def test_valid_date(self):
        """Test valid date string passes validation."""
        result = validate_date_string("2024-01-15")
        assert result == "2024-01-15"
    
    def test_invalid_date_format(self):
        """Test invalid date format raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_string("01/15/2024")
        assert exc_info.value.field == "date"
        assert "YYYY-MM-DD" in str(exc_info.value)
    
    def test_invalid_date(self):
        """Test invalid date raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_date_string("2024-02-30")
        assert exc_info.value.field == "date"


class TestAPIKeyPreview:
    """Test API key preview function."""
    
    def test_api_key_preview(self):
        """Test API key preview generation."""
        api_key = "sk-1234567890abcdefghijklmnop"
        preview = get_api_key_preview(api_key)
        assert preview.startswith("sk-1")
        assert "***" in preview
        assert f"({len(api_key)} chars)" in preview
    
    def test_short_api_key_preview(self):
        """Test API key preview for short keys."""
        api_key = "sk"
        preview = get_api_key_preview(api_key)
        assert preview == "***"
    
    def test_empty_api_key_preview(self):
        """Test API key preview for empty key."""
        preview = get_api_key_preview("")
        assert preview == "***"