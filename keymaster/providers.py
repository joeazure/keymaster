from abc import ABC, abstractmethod
import os
from typing import Any, Dict, ClassVar, Optional
import structlog
import requests
from dataclasses import dataclass, asdict
import json

log = structlog.get_logger()

def _get_providers_file() -> str:
    """Get the path to the providers JSON file."""
    home_dir = os.path.expanduser("~")
    config_dir = os.path.join(home_dir, ".keymaster")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "providers.json")

def _load_generic_providers() -> None:
    """Load generic providers from the JSON file."""
    providers_file = _get_providers_file()
    if not os.path.exists(providers_file):
        return
        
    try:
        with open(providers_file, 'r') as f:
            providers_data = json.load(f)
            
        for provider_data in providers_data:
            GenericProvider.create(**provider_data)
    except Exception as e:
        log.error("Failed to load generic providers", error=str(e))

def _save_generic_providers() -> None:
    """Save generic providers to the JSON file."""
    providers_file = _get_providers_file()
    
    # Get all generic providers
    generic_providers = [
        asdict(provider) for provider in _providers.values()
        if isinstance(provider, GenericProvider)
    ]
    
    try:
        with open(providers_file, 'w') as f:
            json.dump(generic_providers, f, indent=2)
    except Exception as e:
        log.error("Failed to save generic providers", error=str(e))

class BaseProvider:
    """Base class for API providers."""
    service_name: str
    description: str
    api_url: str = ""
    
    @classmethod
    def test_key(cls, api_key: str) -> dict:
        """Test if an API key is valid."""
        raise NotImplementedError

@dataclass
class GenericProvider(BaseProvider):
    """
    A generic provider for any API service.
    Supports optional key validation through a test URL.
    """
    service_name: str
    description: str
    test_url: Optional[str] = None
    
    @classmethod
    def create(cls, 
               service_name: str, 
               description: str, 
               test_url: Optional[str] = None) -> 'GenericProvider':
        """
        Create a new generic provider.
        
        Args:
            service_name: The canonical name of the service
            description: A description of what the service provides
            test_url: Optional URL to test API key validity
            
        Returns:
            A configured GenericProvider instance
        """
        provider = cls(
            service_name=service_name,
            description=description,
            test_url=test_url
        )
        
        # Register the provider
        _register_provider(provider)
        
        # Save to file
        _save_generic_providers()
        
        return provider
        
    def test_key(self, api_key: str) -> dict:
        """
        Test if an API key is valid using the provided test URL.
        
        Args:
            api_key: The API key to test
            
        Returns:
            A dict containing the test response
            
        Raises:
            ValueError: If no test URL was provided
            requests.RequestException: If the test request fails
        """
        if not self.test_url:
            return {"status": "untested", "message": "No test URL provided"}
            
        # Add the API key as a query parameter if not already in URL
        url = self.test_url
        if '?' in url:
            url += f"&appid={api_key}"
        else:
            url += f"?appid={api_key}"
            
        response = requests.get(url)
        response.raise_for_status()
        
        return {
            "status": "valid",
            "message": "API key is valid",
            "response": response.json()
        }

class OpenAIProvider(BaseProvider):
    service_name = "OpenAI"
    description = "OpenAI's GPT models and other AI services including DALL-E and embeddings"
    api_url = "https://api.openai.com/v1/chat/completions"
    
    @classmethod
    def test_key(cls, api_key: str) -> dict:
        response = requests.post(
            cls.api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Say 'test' if you can read this."}],
                "max_tokens": 10
            }
        )
        response.raise_for_status()
        return response.json()

class AnthropicProvider(BaseProvider):
    service_name = "Anthropic"
    description = "Anthropic's Claude models for natural language understanding and generation"
    api_url = "https://api.anthropic.com/v1/messages"
    
    @classmethod
    def test_key(cls, api_key: str) -> dict:
        response = requests.post(
            cls.api_url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-3-opus-20240229",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Say 'test' if you can read this."}]
            }
        )
        response.raise_for_status()
        return response.json()

class StabilityProvider(BaseProvider):
    service_name = "Stability"
    description = "Stability AI's image generation and AI models"
    api_url = "https://api.stability.ai/v1/engines/list"
    
    @classmethod
    def test_key(cls, api_key: str) -> dict:
        response = requests.get(
            cls.api_url,
            headers={"Authorization": f"Bearer {api_key}"}
        )
        response.raise_for_status()
        return response.json()

class DeepSeekProvider(BaseProvider):
    service_name = "DeepSeek"
    description = "DeepSeek's language models and AI services"
    api_url = "https://api.deepseek.com/v1/chat/completions"
    
    @classmethod
    def test_key(cls, api_key: str) -> dict:
        response = requests.post(
            cls.api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "Say 'test' if you can read this."}],
                "max_tokens": 10
            }
        )
        response.raise_for_status()
        return response.json()

# Dictionary to store all providers
_providers: Dict[str, BaseProvider] = {}

def _register_provider(provider: BaseProvider) -> None:
    """Register a provider in the global provider dictionary."""
    _providers[provider.service_name.lower()] = provider

# Register built-in providers
_register_provider(OpenAIProvider)
_register_provider(AnthropicProvider)
_register_provider(StabilityProvider)
_register_provider(DeepSeekProvider)

# Load any saved generic providers
_load_generic_providers()

def get_providers() -> Dict[str, BaseProvider]:
    """Get all registered providers."""
    return _providers

def get_provider_by_name(name: str) -> Optional[BaseProvider]:
    """Get a provider by name (case-insensitive)."""
    return _providers.get(name.lower()) 