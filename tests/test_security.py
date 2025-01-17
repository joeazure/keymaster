import pytest
from keymaster.security import KeyStore
from unittest.mock import patch, MagicMock
from keyring.errors import KeyringError, PasswordDeleteError
import keyring.backends

class TestKeyStore:
    def test_store_key(self, test_db):
        with patch('keyring.set_password') as mock_set:
            KeyStore.store_key('OpenAI', 'test', 'test-key')
            mock_set.assert_called_once()
            
    def test_get_key(self, test_db):
        # First store a key to set up the database
        with patch('keyring.set_password'):
            KeyStore.store_key('OpenAI', 'test', 'test-key')
        
        # Now test getting the key
        with patch('keyring.get_password', return_value='test-key'):
            key = KeyStore.get_key('OpenAI', 'test')
            assert key == 'test-key'
            
    def test_get_nonexistent_key(self, test_db):
        """Test getting a key that doesn't exist"""
        key = KeyStore.get_key('NonExistent', 'test')
        assert key is None
            
    def test_remove_key(self, test_db):
        with patch('keyring.delete_password') as mock_delete:
            # First store a key
            with patch('keyring.set_password'):
                KeyStore.store_key('OpenAI', 'test', 'test-key')
            
            # Then remove it
            KeyStore.remove_key('OpenAI', 'test')
            mock_delete.assert_called_once()
            
    def test_verify_backend_secure(self):
        """Test backend verification with a secure backend"""
        mock_backend = MagicMock(spec=keyring.backends.macOS.Keyring)
        with patch('keyring.get_keyring', return_value=mock_backend):
            KeyStore._verify_backend()  # Should not raise an error
            
    def test_verify_backend_insecure(self):
        """Test backend verification with an insecure backend"""
        mock_backend = MagicMock()  # Generic mock, not a secure backend
        with patch('keyring.get_keyring', return_value=mock_backend):
            with pytest.raises(KeyringError):
                KeyStore._verify_backend()
                
    def test_list_keys_empty(self, test_db):
        """Test listing keys when none exist"""
        keys = KeyStore.list_keys()
        assert keys == []
        
    def test_list_keys_with_filter(self, test_db):
        """Test listing keys with service filter"""
        # Store some test keys
        with patch('keyring.set_password'):
            KeyStore.store_key('OpenAI', 'dev', 'key1')
            KeyStore.store_key('OpenAI', 'prod', 'key2')
            KeyStore.store_key('Anthropic', 'dev', 'key3')
            
        # List only OpenAI keys
        keys = KeyStore.list_keys(service='OpenAI')
        assert len(keys) == 2
        assert ('OpenAI', 'dev') in keys
        assert ('OpenAI', 'prod') in keys
        
    def test_list_keys_all(self, test_db):
        """Test listing all keys"""
        # Store some test keys
        with patch('keyring.set_password'):
            KeyStore.store_key('OpenAI', 'dev', 'key1')
            KeyStore.store_key('Anthropic', 'dev', 'key2')
            
        keys = KeyStore.list_keys()
        assert len(keys) == 2
        assert ('OpenAI', 'dev') in keys
        assert ('Anthropic', 'dev') in keys
        
    def test_remove_nonexistent_key(self, test_db):
        """Test removing a key that doesn't exist"""
        # Should not raise an error
        KeyStore.remove_key('NonExistent', 'test')
        
    def test_remove_key_delete_error(self, test_db):
        """Test handling of PasswordDeleteError during key removal"""
        with patch('keyring.set_password'):
            KeyStore.store_key('OpenAI', 'test', 'test-key')
            
        with patch('keyring.delete_password', side_effect=PasswordDeleteError):
            # Should not raise an error
            KeyStore.remove_key('OpenAI', 'test')
            
    def test_store_key_case_insensitive(self, test_db):
        """Test that service names are case-insensitive"""
        with patch('keyring.set_password'):
            KeyStore.store_key('OPENAI', 'test', 'test-key')
            KeyStore.store_key('openai', 'prod', 'test-key')
            
        keys = KeyStore.list_keys(service='OpenAI')
        assert len(keys) == 2
        assert all(svc == 'OpenAI' for svc, _ in keys)
        
    def test_get_key_case_insensitive(self, test_db):
        """Test case-insensitive key retrieval"""
        with patch('keyring.set_password'):
            KeyStore.store_key('OpenAI', 'TEST', 'test-key')
            
        with patch('keyring.get_password', return_value='test-key'):
            key = KeyStore.get_key('OPENAI', 'test')
            assert key == 'test-key'
            
    def test_keyring_service_name_format(self):
        """Test the format of generated keyring service names"""
        service_name = KeyStore._get_keyring_service_name('OpenAI', 'prod')
        assert service_name == 'keymaster-openai'
        assert service_name.islower()  # Should be lowercase 