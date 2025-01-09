import pytest
import responses
from keymaster.providers import OpenAIProvider, AnthropicProvider, StabilityProvider

class TestOpenAIProvider:
    @responses.activate
    def test_valid_key(self):
        responses.add(
            responses.GET,
            "https://api.openai.com/v1/models",
            json={"data": []},
            status=200
        )
        
        result = OpenAIProvider.test_key("test-key")
        assert result["status"] == "valid"
        
    @responses.activate
    def test_invalid_key(self):
        responses.add(
            responses.GET,
            "https://api.openai.com/v1/models",
            json={"error": "Invalid key"},
            status=401
        )
        
        with pytest.raises(ValueError):
            OpenAIProvider.test_key("invalid-key") 