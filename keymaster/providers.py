import os
from typing import Any, Dict
import structlog
import requests

log = structlog.get_logger()

class BaseProvider:
    """Base class for API providers with common functionality."""
    
    @classmethod
    def test_key(cls, api_key: str) -> Dict[str, Any]:
        """Test if an API key is valid. Should be implemented by subclasses."""
        raise NotImplementedError

class OpenAIProvider(BaseProvider):
    """OpenAI API provider implementation."""
    
    @staticmethod
    def test_key(api_key: str) -> Dict[str, Any]:
        """Test if an OpenAI API key is valid."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers=headers
        )
        
        if response.status_code == 200:
            return {"status": "valid", "models": response.json()}
        else:
            raise ValueError(f"Invalid API key: {response.text}")

class AnthropicProvider(BaseProvider):
    """Anthropic API provider implementation."""
    
    @staticmethod
    def test_key(api_key: str) -> Dict[str, Any]:
        """Test if an Anthropic API key is valid."""
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        # Note: Update this endpoint based on Anthropic's actual API
        response = requests.get(
            "https://api.anthropic.com/v1/models",
            headers=headers
        )
        
        if response.status_code == 200:
            return {"status": "valid", "models": response.json()}
        else:
            raise ValueError(f"Invalid API key: {response.text}")

class StabilityProvider(BaseProvider):
    """Stability AI provider implementation."""
    
    @staticmethod
    def test_key(api_key: str) -> Dict[str, Any]:
        """Test if a Stability AI key is valid."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            "https://api.stability.ai/v1/engines/list",
            headers=headers
        )
        
        if response.status_code == 200:
            return {"status": "valid", "engines": response.json()}
        else:
            raise ValueError(f"Invalid API key: {response.text}") 