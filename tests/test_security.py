import pytest
from keymaster.security import KeychainSecurity
from unittest.mock import patch

class TestKeychainSecurity:
    def test_store_key(self, test_db):
        with patch('keyring.set_password') as mock_set:
            KeychainSecurity.store_key('OpenAI', 'test', 'test-key')
            mock_set.assert_called_once()
            
    def test_get_key(self, test_db):
        # First store a key to set up the database
        with patch('keyring.set_password'):
            KeychainSecurity.store_key('OpenAI', 'test', 'test-key')
        
        # Now test getting the key
        with patch('keyring.get_password', return_value='test-key'):
            key = KeychainSecurity.get_key('OpenAI', 'test')
            assert key == 'test-key'
            
    def test_get_nonexistent_key(self, test_db):
        """Test getting a key that doesn't exist"""
        key = KeychainSecurity.get_key('NonExistent', 'test')
        assert key is None
            
    def test_remove_key(self, test_db):
        with patch('keyring.delete_password') as mock_delete:
            # First store a key
            with patch('keyring.set_password'):
                KeychainSecurity.store_key('OpenAI', 'test', 'test-key')
            
            # Then remove it
            KeychainSecurity.remove_key('OpenAI', 'test')
            mock_delete.assert_called_once() 