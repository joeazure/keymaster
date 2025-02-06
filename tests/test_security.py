import pytest
from keymaster.security import KeyStore
from unittest.mock import patch, MagicMock, Mock
from keyring.errors import KeyringError, PasswordDeleteError
import keyring.backends
import keyring.backend
import os
from datetime import datetime

class MockKeyring(keyring.backend.KeyringBackend):
    """Mock keyring backend for testing."""
    
    def __init__(self):
        self.passwords = {}
        
    def get_password(self, service, username):
        return self.passwords.get(f"{service}:{username}")
        
    def set_password(self, service, username, password):
        self.passwords[f"{service}:{username}"] = password
        
    def delete_password(self, service, username):
        key = f"{service}:{username}"
        if key in self.passwords:
            del self.passwords[key]
        else:
            raise PasswordDeleteError("Password not found")
            
    def get_credential(self, service, username):
        return None

@pytest.fixture
def mock_keyring():
    """Create a mock keyring backend and set it as the default."""
    mock_kr = MockKeyring()
    with patch('keyring.get_keyring', return_value=mock_kr), \
         patch('keymaster.security.KeyStore._verify_backend'), \
         patch('keyring.set_password', side_effect=mock_kr.set_password), \
         patch('keyring.get_password', side_effect=mock_kr.get_password), \
         patch('keyring.delete_password', side_effect=mock_kr.delete_password):
        yield mock_kr

@pytest.fixture
def mock_db():
    """Create a mock database that simulates key metadata storage."""
    mock_db = MagicMock()
    mock_db.get_key_metadata.return_value = {
        'keychain_service_name': 'keymaster-openai',
        'service_name': 'openai',
        'environment': 'test'
    }
    with patch('keymaster.security.KeyDatabase', return_value=mock_db):
        yield mock_db

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
    def test_store_key(self, test_db, mock_keyring, mock_db):
        KeyStore.store_key('OpenAI', 'test', 'test-key')
        assert mock_keyring.get_password('keymaster-openai', 'test') == 'test-key'
        mock_db.add_key.assert_called_once()
            
    def test_get_key(self, test_db, mock_keyring, mock_db):
        # First store a key
        KeyStore.store_key('OpenAI', 'test', 'test-key')
        
        # Now test getting the key
        key = KeyStore.get_key('OpenAI', 'test')
        assert key == 'test-key'
            
    def test_get_nonexistent_key(self, test_db, mock_keyring, mock_db):
        """Test getting a key that doesn't exist"""
        mock_db.get_key_metadata.return_value = None
        key = KeyStore.get_key('NonExistent', 'test')
        assert key is None
            
    def test_remove_key(self, test_db, mock_keyring, mock_db):
        # First store a key
        KeyStore.store_key('OpenAI', 'test', 'test-key')
        
        # Then remove it
        KeyStore.remove_key('OpenAI', 'test')
        assert mock_keyring.get_password('keymaster-openai', 'test') is None
        mock_db.remove_key.assert_called_once()
            
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
                
    def test_list_keys_empty(self, test_db, mock_keyring, mock_db):
        """Test listing keys when none exist"""
        mock_db.list_keys.return_value = []
        keys = KeyStore.list_keys()
        assert keys == []
        
    @patch('keymaster.providers.get_provider_by_name')
    def test_list_keys_with_filter(self, mock_get_provider, test_db, mock_keyring, mock_db):
        # Setup mock provider that returns canonical name
        mock_provider = Mock()
        mock_provider.service_name = 'OpenAI'
        mock_get_provider.return_value = mock_provider
        
        # Setup mock database response
        mock_db.list_keys.return_value = [
            ('openai', 'dev', datetime.utcnow().isoformat(), 'testuser'),
            ('openai', 'prod', datetime.utcnow().isoformat(), 'testuser')
        ]
        
        # Store test keys
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
    def test_list_keys_all(self, mock_load_providers, mock_get_provider, test_db, mock_keyring, mock_db):
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
        
        # Setup mock database response
        mock_db.list_keys.return_value = [
            ('openai', 'dev', datetime.utcnow().isoformat(), 'testuser'),
            ('anthropic', 'dev', datetime.utcnow().isoformat(), 'testuser')
        ]
        
        # Store test keys
        KeyStore.store_key('openai', 'dev', 'test-key-1')
        KeyStore.store_key('anthropic', 'dev', 'test-key-2')
        
        # List all keys
        keys = KeyStore.list_keys()
        key_pairs = [(svc, env) for svc, env, _, _ in keys]
        assert ('OpenAI', 'dev') in key_pairs
        assert ('Anthropic', 'dev') in key_pairs
        assert len(keys) == 2
        
    def test_remove_nonexistent_key(self, test_db, mock_keyring, mock_db):
        """Test removing a key that doesn't exist"""
        mock_db.get_key_metadata.return_value = None
        # Should not raise an error
        KeyStore.remove_key('NonExistent', 'test')
        
    def test_remove_key_delete_error(self, test_db, mock_keyring, mock_db):
        """Test handling of PasswordDeleteError during key removal"""
        # First store a key
        KeyStore.store_key('OpenAI', 'test', 'test-key')
        
        # Mock the delete operation to fail
        with patch.object(mock_keyring, 'delete_password', side_effect=PasswordDeleteError):
            # Should not raise an error
            KeyStore.remove_key('OpenAI', 'test')
            
    def test_store_key_case_insensitive(self, test_db, mock_keyring, mock_db):
        """Test that service names are case-insensitive"""
        mock_provider = MagicMock()
        mock_provider.service_name = "OpenAI"
        
        with patch('keymaster.providers.get_provider_by_name', return_value=mock_provider):
            KeyStore.store_key('OPENAI', 'test', 'test-key')
            KeyStore.store_key('openai', 'prod', 'test-key')
            
            mock_db.list_keys.return_value = [
                ('openai', 'test', datetime.utcnow().isoformat(), 'testuser'),
                ('openai', 'prod', datetime.utcnow().isoformat(), 'testuser')
            ]
            
            keys = KeyStore.list_keys(service='OpenAI')
            assert len(keys) == 2
            # Check only service names, ignoring environment, timestamps and user
            service_names = [svc for svc, _, _, _ in keys]
            assert all(svc == 'OpenAI' for svc in service_names)
        
    def test_get_key_case_insensitive(self, test_db, mock_keyring, mock_db):
        """Test case-insensitive key retrieval"""
        KeyStore.store_key('OpenAI', 'TEST', 'test-key')
        key = KeyStore.get_key('OPENAI', 'test')
        assert key == 'test-key'
            
    def test_keyring_service_name_format(self):
        """Test the format of generated keyring service names"""
        service_name = KeyStore._get_keyring_service_name('OpenAI', 'prod')
        assert service_name == 'keymaster-openai'
        assert service_name.islower()  # Should be lowercase 