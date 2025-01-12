import pytest
import responses
from keymaster.providers import OpenAIProvider, AnthropicProvider, StabilityProvider, DeepSeekProvider

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

class TestDeepSeekProvider:
    @responses.activate
    def test_valid_key(self):
        responses.add(
            responses.POST,
            "https://api.deepseek.com/chat/completions",
            json={"choices": [{"message": {"content": "Hello!"}}]},
            status=200
        )
        
        result = DeepSeekProvider.test_key("test-key")
        assert result["status"] == "valid"
        assert result["model"] == "deepseek-chat"
        
    @responses.activate
    def test_invalid_key(self):
        responses.add(
            responses.POST,
            "https://api.deepseek.com/chat/completions",
            json={"error": "Invalid key"},
            status=401
        )
        
        with pytest.raises(ValueError):
            DeepSeekProvider.test_key("invalid-key") 