import pytest
from keymaster.env import EnvManager
from unittest.mock import patch, mock_open
import os

class TestEnvManager:
    def test_list_variables(self):
        """Test listing environment variables with and without prefix filter."""
        test_env = {
            "OPENAI_API_KEY": "test-key",
            "ANTHROPIC_API_KEY": "test-key",
            "OTHER_VAR": "value"
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            # Test listing all variables
            vars = EnvManager.list_variables()
            assert len(vars) == 3
            assert vars["OPENAI_API_KEY"] == "test-key"
            assert vars["ANTHROPIC_API_KEY"] == "test-key"
            assert vars["OTHER_VAR"] == "value"
            
            # Test filtering by prefix
            vars = EnvManager.list_variables(prefix_filter="OPENAI_")
            assert len(vars) == 1
            assert vars["OPENAI_API_KEY"] == "test-key"
            
            # Test with non-matching prefix
            vars = EnvManager.list_variables(prefix_filter="NONEXISTENT_")
            assert len(vars) == 0
            
    def test_generate_env_file(self, tmp_path):
        """Test generating a .env file with variables."""
        env_file = tmp_path / ".env"
        variables = {
            "OPENAI_API_KEY": "test-key-1",
            "ANTHROPIC_API_KEY": "test-key-2"
        }
        
        EnvManager.generate_env_file(str(env_file), variables)
        
        # Verify file contents
        assert env_file.exists()
        content = env_file.read_text()
        assert "OPENAI_API_KEY=test-key-1" in content
        assert "ANTHROPIC_API_KEY=test-key-2" in content
        
    def test_generate_env_file_empty(self, tmp_path):
        """Test generating a .env file with no variables."""
        env_file = tmp_path / ".env"
        EnvManager.generate_env_file(str(env_file), {})
        
        # Verify empty file was created
        assert env_file.exists()
        assert env_file.read_text() == ""
        
    def test_generate_env_file_overwrite(self, tmp_path):
        """Test overwriting an existing .env file."""
        env_file = tmp_path / ".env"
        
        # Create initial file
        EnvManager.generate_env_file(str(env_file), {"OLD_KEY": "old-value"})
        
        # Overwrite with new content
        new_vars = {"NEW_KEY": "new-value"}
        EnvManager.generate_env_file(str(env_file), new_vars)
        
        # Verify new content
        content = env_file.read_text()
        assert "OLD_KEY" not in content
        assert "NEW_KEY=new-value" in content
        
    def test_generate_env_file_error(self):
        """Test error handling when generating .env file."""
        with patch('builtins.open', mock_open()) as mock_file:
            mock_file.side_effect = IOError("Permission denied")
            
            with pytest.raises(Exception) as exc_info:
                EnvManager.generate_env_file("/nonexistent/.env", {"KEY": "value"})
            assert "Permission denied" in str(exc_info.value)
            
    def test_generate_env_file_special_chars(self, tmp_path):
        """Test handling of special characters in .env file generation."""
        env_file = tmp_path / ".env"
        variables = {
            "KEY_WITH_SPACES": "value with spaces",
            "KEY_WITH_QUOTES": 'value"with"quotes',
            "KEY_WITH_NEWLINES": "value\nwith\nnewlines"
        }
        
        EnvManager.generate_env_file(str(env_file), variables)
        
        # Verify file contents
        content = env_file.read_text()
        assert "KEY_WITH_SPACES=value with spaces" in content
        assert 'KEY_WITH_QUOTES=value"with"quotes' in content
        assert "KEY_WITH_NEWLINES=value\nwith\nnewlines" in content 