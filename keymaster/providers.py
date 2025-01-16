from abc import ABC, abstractmethod
import os
from typing import Any, Dict, ClassVar
import structlog
import requests

log = structlog.get_logger()

class BaseProvider(ABC):
    """Base class for API providers with common functionality."""
    
    service_name: ClassVar[str]  # Will be set by each provider
    description: ClassVar[str]  # Description of the provider's service
    api_url: ClassVar[str]  # Base API URL for the provider
    
    @classmethod
    @abstractmethod
    def test_key(cls, api_key: str) -> Dict[str, Any]:
        """Test if an API key is valid. Should be implemented by subclasses."""
        pass

class OpenAIProvider(BaseProvider):
    """OpenAI API provider implementation."""
    service_name = "OpenAI"
    description = "OpenAI's GPT models and API services for natural language processing"
    api_url = "https://api.openai.com/v1/models"
    
    @staticmethod
    def test_key(api_key: str) -> Dict[str, Any]:
        """Test if an OpenAI API key is valid."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            OpenAIProvider.api_url,
            headers=headers
        )
        
        if response.status_code == 200:
            return {"status": "valid", "models": response.json()}
        else:
            raise ValueError(f"Invalid API key: {response.text}")

class AnthropicProvider(BaseProvider):
    """Anthropic API provider implementation."""
    service_name = "Anthropic"
    description = "Anthropic's Claude models for advanced language understanding and generation"
    api_url = "https://api.anthropic.com/v1/models"
    
    @staticmethod
    def test_key(api_key: str) -> Dict[str, Any]:
        """Test if an Anthropic API key is valid."""
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        response = requests.get(
            AnthropicProvider.api_url,
            headers=headers
        )
        
        if response.status_code == 200:
            return {"status": "valid", "models": response.json()}
        else:
            raise ValueError(f"Invalid API key: {response.text}")

class StabilityProvider(BaseProvider):
    """Stability AI provider implementation."""
    service_name = "Stability"
    description = "Stability AI's image generation and AI models"
    api_url = "https://api.stability.ai/v1/engines/list"
    
    @staticmethod
    def test_key(api_key: str) -> Dict[str, Any]:
        """Test if a Stability AI key is valid."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            StabilityProvider.api_url,
            headers=headers
        )
        
        if response.status_code == 200:
            return {"status": "valid", "engines": response.json()}
        else:
            raise ValueError(f"Invalid API key: {response.text}")

class DeepSeekProvider(BaseProvider):
    """DeepSeek API provider implementation."""
    service_name = "DeepSeek"
    description = "DeepSeek's language models with OpenAI-compatible API"
    api_url = "https://api.deepseek.com/chat/completions"
    
    @staticmethod
    def test_key(api_key: str) -> Dict[str, Any]:
        """Test if a DeepSeek API key is valid."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello!"}
            ],
            "stream": False
        }
        
        response = requests.post(
            DeepSeekProvider.api_url,
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            return {"status": "valid", "model": "deepseek-chat"}
        else:
            raise ValueError(f"Invalid API key: {response.text}")

def get_providers() -> Dict[str, type[BaseProvider]]:
    """Get all available providers."""
    return {
        provider.service_name.lower(): provider
        for provider in [OpenAIProvider, AnthropicProvider, StabilityProvider, DeepSeekProvider]
    }

def get_provider_by_name(name: str) -> type[BaseProvider]:
    """Get a provider by name (case-insensitive)."""
    providers = get_providers()
    return providers.get(name.lower()) 