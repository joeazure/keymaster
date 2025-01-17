import pytest
import responses
from keymaster.providers import OpenAIProvider, AnthropicProvider, StabilityProvider, DeepSeekProvider
from unittest.mock import patch, MagicMock
import requests
from keymaster.providers import (
    GenericProvider,
    get_providers,
    get_provider_by_name,
    _providers,
    _load_generic_providers,
    _save_generic_providers
)
import os
import json
import tempfile

class TestOpenAIProvider:
    @responses.activate
    def test_valid_key(self):
        responses.add(
            responses.POST,
            "https://api.openai.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "test"}}]},
            status=200
        )
        
        result = OpenAIProvider.test_key("test-key")
        assert "choices" in result
        
    @responses.activate
    def test_invalid_key(self):
        responses.add(
            responses.POST,
            "https://api.openai.com/v1/chat/completions",
            json={"error": "Invalid key"},
            status=401
        )
        
        with pytest.raises(requests.exceptions.HTTPError):
            OpenAIProvider.test_key("invalid-key")

class TestDeepSeekProvider:
    @responses.activate
    def test_valid_key(self):
        responses.add(
            responses.POST,
            "https://api.deepseek.com/v1/chat/completions",
            json={"choices": [{"message": {"content": "test"}}]},
            status=200
        )
        
        result = DeepSeekProvider.test_key("test-key")
        assert "choices" in result
        
    @responses.activate
    def test_invalid_key(self):
        responses.add(
            responses.POST,
            "https://api.deepseek.com/v1/chat/completions",
            json={"error": "Invalid key"},
            status=401
        )
        
        with pytest.raises(requests.exceptions.HTTPError):
            DeepSeekProvider.test_key("invalid-key")

@pytest.fixture
def mock_providers_file():
    """Create a temporary providers file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump([], f)
        
    yield f.name
    os.unlink(f.name)

@pytest.fixture
def clear_providers():
    """Clear the providers registry before and after tests."""
    _providers.clear()
    yield
    _providers.clear()

class TestGenericProvider:
    def test_create_provider(self, clear_providers, mock_providers_file):
        """Test creating a new generic provider."""
        with patch('keymaster.providers._get_providers_file', return_value=mock_providers_file):
            provider = GenericProvider.create(
                service_name="TestAPI",
                description="Test API Service",
                test_url="https://api.test.com/validate"
            )
            
            assert provider.service_name == "TestAPI"
            assert provider.description == "Test API Service"
            assert provider.test_url == "https://api.test.com/validate"
            
            # Verify it's registered
            assert get_provider_by_name("testapi") == provider
            
            # Verify it's saved to file
            with open(mock_providers_file, 'r') as f:
                saved_data = json.load(f)
                assert len(saved_data) == 1
                assert saved_data[0]["service_name"] == "TestAPI"
    
    def test_test_key_with_url(self, clear_providers):
        """Test key validation with a test URL."""
        provider = GenericProvider(
            service_name="TestAPI",
            description="Test API Service",
            test_url="https://api.test.com/validate"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        
        with patch('requests.get', return_value=mock_response) as mock_get:
            result = provider.test_key("test-key")
            assert result["status"] == "valid"
            mock_get.assert_called_once()
            
    def test_test_key_without_url(self, clear_providers):
        """Test key validation without a test URL."""
        provider = GenericProvider(
            service_name="TestAPI",
            description="Test API Service"
        )
        
        result = provider.test_key("test-key")
        assert result["status"] == "untested"
        
    def test_load_generic_providers(self, clear_providers, mock_providers_file):
        """Test loading generic providers from file."""
        test_data = [
            {
                "service_name": "TestAPI1",
                "description": "Test Service 1",
                "test_url": "https://api1.test.com"
            },
            {
                "service_name": "TestAPI2",
                "description": "Test Service 2"
            }
        ]
        
        with open(mock_providers_file, 'w') as f:
            json.dump(test_data, f)
            
        with patch('keymaster.providers._get_providers_file', return_value=mock_providers_file):
            _load_generic_providers()
            
            assert get_provider_by_name("testapi1") is not None
            assert get_provider_by_name("testapi2") is not None
            
    def test_save_generic_providers(self, clear_providers, mock_providers_file):
        """Test saving generic providers to file."""
        with patch('keymaster.providers._get_providers_file', return_value=mock_providers_file):
            # Create some providers
            GenericProvider.create(
                service_name="TestAPI1",
                description="Test Service 1",
                test_url="https://api1.test.com"
            )
            GenericProvider.create(
                service_name="TestAPI2",
                description="Test Service 2"
            )
            
            # Force save
            _save_generic_providers()
            
            # Verify file contents
            with open(mock_providers_file, 'r') as f:
                saved_data = json.load(f)
                assert len(saved_data) == 2
                assert {p["service_name"] for p in saved_data} == {"TestAPI1", "TestAPI2"}
                
    def test_case_insensitive_lookup(self, clear_providers):
        """Test case-insensitive provider lookup."""
        provider = GenericProvider.create(
            service_name="TestAPI",
            description="Test Service"
        )
        
        assert get_provider_by_name("testapi") == provider
        assert get_provider_by_name("TESTAPI") == provider
        assert get_provider_by_name("TestAPI") == provider 