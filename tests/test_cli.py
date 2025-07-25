"""Tests for the CLI commands."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, mock_open
from keymaster.cli import cli
from keymaster.providers import (
    OpenAIProvider,
    AnthropicProvider,
    StabilityProvider,
    DeepSeekProvider,
    GenericProvider,
    _register_provider
)
import os

@pytest.fixture
def mock_home_dir(tmp_path):
    """Create a temporary home directory for testing."""
    mock_home = tmp_path / ".keymaster"
    return str(mock_home)

@pytest.fixture
def mock_expanduser(mock_home_dir):
    """Mock os.path.expanduser to return a test directory."""
    with patch('os.path.expanduser') as mock_expand:
        mock_expand.return_value = mock_home_dir
        yield mock_expand

@pytest.fixture
def mock_db():
    """Mock database connection."""
    mock_db = MagicMock()
    with patch('keymaster.db.KeyDatabase') as mock_db_class:
        mock_db_class.return_value = mock_db
        yield mock_db

@pytest.fixture
def mock_audit_logger():
    """Mock audit logger."""
    mock_logger = MagicMock()
    with patch('keymaster.audit.AuditLogger') as mock_logger_class:
        mock_logger_class.return_value = mock_logger
        yield mock_logger

@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()

@pytest.fixture
def mock_config():
    """Mock configuration data."""
    return {
        "log_level": "INFO",
        "audit": {
            "encryption_key": "test-key-123"
        }
    }

@pytest.fixture
def mock_providers_file():
    """Mock providers file data."""
    return [
        {
            "service_name": "TestAPI",
            "description": "Test Service",
            "test_url": "https://api.test.com/validate"
        }
    ]

@pytest.fixture(autouse=True)
def clear_provider_registry():
    """Clear the provider registry before and after each test."""
    from keymaster.providers import _providers
    _providers.clear()
    yield
    _providers.clear()

@pytest.fixture
def register_builtin_providers():
    """Register built-in providers."""
    _register_provider(OpenAIProvider)
    _register_provider(AnthropicProvider)
    _register_provider(StabilityProvider)
    _register_provider(DeepSeekProvider)

class TestConfigCommand:
    def test_config_show_all_providers(self, cli_runner, mock_config, mock_providers_file, 
                                     mock_expanduser, mock_db, mock_audit_logger,
                                     register_builtin_providers):
        """Test that 'config show' displays built-in providers correctly."""
        
        # Simplified test that focuses on core functionality
        # Mock configuration and file operations for no custom providers
        with patch('keymaster.config.ConfigManager.load_config', return_value=mock_config), \
             patch('keymaster.providers._get_providers_file', return_value='/mock/path/providers.json'), \
             patch('os.path.exists', return_value=False):  # No providers file exists
            
            result = cli_runner.invoke(cli, ['config', '--action', 'show'])
            
            # Verify exit code
            assert result.exit_code == 0
            
            # Verify configuration section
            assert "Configuration from config.yaml:" in result.output
            assert "log_level: INFO" in result.output
            assert "encryption_key" in result.output
            
            # Verify built-in providers section
            assert "Built-in Providers:" in result.output
            assert "OpenAI" in result.output
            assert "Anthropic" in result.output
            assert "Stability" in result.output
            assert "DeepSeek" in result.output
            
            # Verify custom providers section shows empty state
            assert "Custom Registered Providers:" in result.output
            assert "No custom providers registered." in result.output
    
    def test_config_show_no_custom_providers(self, cli_runner, mock_config, 
                                           mock_expanduser, mock_db, mock_audit_logger,
                                           register_builtin_providers):
        """Test that 'config show' works correctly with no custom providers."""
        
        # Mock configuration and empty providers file
        with patch('keymaster.config.ConfigManager.load_config', return_value=mock_config), \
             patch('keymaster.providers._get_providers_file', return_value='/mock/path/providers.json'), \
             patch('builtins.open', mock_open(read_data='[]')), \
             patch('json.load', return_value=[]), \
             patch('os.makedirs') as mock_makedirs:

            result = cli_runner.invoke(cli, ['config', '--action', 'show'])
            
            # Verify exit code
            assert result.exit_code == 0
            
            # Verify built-in providers are shown
            assert "Built-in Providers:" in result.output
            assert "OpenAI" in result.output
            assert "Anthropic" in result.output
            assert "Stability" in result.output
            assert "DeepSeek" in result.output
            
            # Verify custom providers section shows as empty
            assert "Custom Registered Providers:" in result.output
            assert "No custom providers registered." in result.output
            
            # Verify no actual file operations occurred
            mock_makedirs.assert_not_called()
            assert not mock_expanduser.called
    
    def test_config_show_no_config(self, cli_runner, mock_expanduser, 
                                 mock_db, mock_audit_logger,
                                 register_builtin_providers):
        """Test that 'config show' handles empty configuration correctly."""
        
        # Mock empty configuration and providers file
        with patch('keymaster.config.ConfigManager.load_config', return_value={}), \
             patch('keymaster.providers._get_providers_file', return_value='/mock/path/providers.json'), \
             patch('builtins.open', mock_open(read_data='[]')), \
             patch('json.load', return_value=[]), \
             patch('os.makedirs') as mock_makedirs:

            result = cli_runner.invoke(cli, ['config', '--action', 'show'])
            
            # Verify exit code
            assert result.exit_code == 0
            
            # Verify empty config message
            assert "No configuration settings found." in result.output
            
            # Verify built-in providers are shown
            assert "Built-in Providers:" in result.output
            assert "OpenAI" in result.output
            assert "Anthropic" in result.output
            assert "Stability" in result.output
            assert "DeepSeek" in result.output
            
            # Verify no actual file operations occurred
            mock_makedirs.assert_not_called()
            assert not mock_expanduser.called
    
    def test_config_reset(self, cli_runner, mock_expanduser, mock_db, mock_audit_logger):
        """Test the 'config reset' action."""
        
        with patch('keymaster.config.ConfigManager.write_config') as mock_write, \
             patch('keymaster.providers._save_generic_providers') as mock_save, \
             patch('os.makedirs') as mock_makedirs, \
             patch('keymaster.cli.KeyStore') as mock_keystore:

            result = cli_runner.invoke(cli, ['config', '--action', 'reset'])
            
            # Verify exit code
            assert result.exit_code == 0
            
            # Verify reset message
            assert "Configuration has been reset." in result.output
            
            # Verify config was reset
            mock_write.assert_called_once_with({})
            
            # Verify no actual file operations occurred
            mock_save.assert_not_called()
            mock_makedirs.assert_not_called()
            assert not mock_expanduser.called 