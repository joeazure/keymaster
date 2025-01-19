import pytest
from keymaster.security import KeyStore
from unittest.mock import patch, MagicMock, Mock
from keyring.errors import KeyringError, PasswordDeleteError
import keyring.backends

@pytest.fixture
def test_db(tmp_path):
    """Create a temporary test database."""
    with patch('keymaster.db.KeyDatabase._get_db_path') as mock_db_path:
        db_file = tmp_path / "test.db"
        mock_db_path.return_value = str(db_file)
        yield db_file
        # Clean up the database after each test
        if db_file.exists():
            db_file.unlink()

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
        
    @patch('keymaster.providers.get_provider_by_name')
    def test_list_keys_with_filter(self, mock_get_provider, test_db):
        # Setup mock provider that returns canonical name
        mock_provider = Mock()
        mock_provider.service_name = 'OpenAI'
        mock_get_provider.return_value = mock_provider
        
        # Store test keys
        with patch('keyring.set_password'):
            KeyStore.store_key('openai', 'dev', 'test-key-1')
            KeyStore.store_key('openai', 'prod', 'test-key-2')
        
        # List keys filtered by service
        keys = KeyStore.list_keys('openai')
        key_pairs = [(svc, env) for svc, env, _, _ in keys]
        assert ('OpenAI', 'dev') in key_pairs
        assert ('OpenAI', 'prod') in key_pairs
        assert len(keys) == 2
        
    @patch('keymaster.providers.get_provider_by_name')
    @patch('keymaster.providers._load_generic_providers')  # Mock this to prevent actual file operations
    def test_list_keys_all(self, mock_load_providers, mock_get_provider, test_db):
        # Setup mock provider that returns canonical names
        def get_canonical_name(service):
            canonical_names = {
                'openai': 'OpenAI',
                'anthropic': 'Anthropic'
            }
            mock_provider = Mock()
            mock_provider.service_name = canonical_names.get(service.lower(), service.title())
            return mock_provider
        mock_get_provider.side_effect = get_canonical_name
        
        # Store test keys
        with patch('keyring.set_password'):
            KeyStore.store_key('openai', 'dev', 'test-key-1')
            KeyStore.store_key('anthropic', 'dev', 'test-key-2')
        
        # List all keys
        keys = KeyStore.list_keys()
        key_pairs = [(svc, env) for svc, env, _, _ in keys]
        assert ('OpenAI', 'dev') in key_pairs
        assert ('Anthropic', 'dev') in key_pairs
        assert len(keys) == 2
        
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
        mock_provider = MagicMock()
        mock_provider.service_name = "OpenAI"
        
        with patch('keyring.set_password'), \
             patch('keymaster.providers.get_provider_by_name', return_value=mock_provider):
            KeyStore.store_key('OPENAI', 'test', 'test-key')
            KeyStore.store_key('openai', 'prod', 'test-key')
            
            keys = KeyStore.list_keys(service='OpenAI')
            assert len(keys) == 2
            # Check only service names, ignoring environment, timestamps and user
            service_names = [svc for svc, _, _, _ in keys]
            assert all(svc == 'OpenAI' for svc in service_names)
        
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