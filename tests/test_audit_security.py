"""
Tests for audit security improvements (Phase 1).
"""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from keymaster.audit import AuditLogger
from keymaster.exceptions import AuditError


class TestAuditSecurity:
    """Test audit security improvements."""
    
    def test_audit_logger_initialization(self, temp_home_dir):
        """Test that AuditLogger initializes with secure storage."""
        with patch('keymaster.security.KeyStore') as mock_keystore:
            # Mock that no key exists in secure storage initially
            mock_keystore.get_system_key.return_value = None
            mock_keystore.store_system_key = MagicMock()
            
            # Create audit logger
            audit_logger = AuditLogger()
            
            # Verify it tried to get the key from secure storage
            mock_keystore.get_system_key.assert_called_with("audit_encryption")
            
            # Verify it stored a new key when none was found
            mock_keystore.store_system_key.assert_called_once()
            call_args = mock_keystore.store_system_key.call_args
            assert call_args[0][0] == "audit_encryption"  # key name
            assert len(call_args[0][1]) > 40  # key value should be long enough
    
    def test_audit_migration_from_config(self, temp_home_dir):
        """Test migration of encryption key from config to secure storage."""
        with patch('keymaster.security.KeyStore') as mock_keystore:
            with patch('keymaster.audit.ConfigManager') as mock_config:
                # Mock that no key exists in secure storage
                mock_keystore.get_system_key.return_value = None
                mock_keystore.store_system_key = MagicMock()
                
                # Mock config with existing encryption key (valid Fernet key)
                old_key = Fernet.generate_key().decode()
                mock_config.load_config.return_value = {
                    'audit': {'encryption_key': old_key},
                    'other_setting': 'value'
                }
                mock_config.write_config = MagicMock()
                
                # Create audit logger - should migrate the key
                audit_logger = AuditLogger()
                
                # Verify it migrated the key to secure storage
                mock_keystore.store_system_key.assert_called_with("audit_encryption", old_key)
                
                # Verify it removed the key from config
                mock_config.write_config.assert_called_once()
                updated_config = mock_config.write_config.call_args[0][0]
                assert 'audit' not in updated_config or 'encryption_key' not in updated_config.get('audit', {})
    
    def test_audit_log_file_permissions(self, temp_home_dir):
        """Test that audit log files are created with secure permissions."""
        with patch('keymaster.security.KeyStore') as mock_keystore:
            # Mock existing key in secure storage (valid Fernet key)
            mock_keystore.get_system_key.return_value = Fernet.generate_key().decode()
            
            # Create audit logger
            audit_logger = AuditLogger()
            
            # Log an event to create the file
            audit_logger.log_event("test_event", "testuser")
            
            # Check that the log file exists and has secure permissions
            log_path = audit_logger._get_log_path()
            assert os.path.exists(log_path)
            
            # Check file permissions (should be 0o600 - read/write for owner only)
            file_stat = os.stat(log_path)
            file_permissions = file_stat.st_mode & 0o777
            assert file_permissions == 0o600
    
    def test_audit_encryption_decryption(self, temp_home_dir):
        """Test that audit encryption/decryption works correctly."""
        with patch('keymaster.security.KeyStore') as mock_keystore:
            # Mock existing key in secure storage (valid Fernet key)
            test_key = Fernet.generate_key().decode()
            mock_keystore.get_system_key.return_value = test_key
            
            # Create audit logger
            audit_logger = AuditLogger()
            
            # Test encryption/decryption
            sensitive_data = "api_key_sk-1234567890"
            encrypted = audit_logger._encrypt_sensitive_data(sensitive_data)
            decrypted = audit_logger._decrypt_sensitive_data(encrypted)
            
            assert encrypted != sensitive_data  # Should be encrypted
            assert decrypted == sensitive_data  # Should decrypt correctly
    
    def test_audit_error_handling(self, temp_home_dir):
        """Test that audit operations raise proper AuditError exceptions."""
        with patch('keymaster.security.KeyStore') as mock_keystore:
            # Mock keystore failure
            mock_keystore.get_system_key.side_effect = Exception("Keystore error")
            
            # Should raise AuditError when keystore fails
            with pytest.raises(AuditError) as exc_info:
                AuditLogger()
            
            assert exc_info.value.operation == "get_encryption_key"
            assert "Keystore error" in str(exc_info.value)
    
    def test_audit_log_directory_permissions(self, temp_home_dir):
        """Test that audit log directory is created with secure permissions."""
        with patch('keymaster.security.KeyStore') as mock_keystore:
            # Mock existing key (valid Fernet key)
            mock_keystore.get_system_key.return_value = Fernet.generate_key().decode()
            
            # Create audit logger
            audit_logger = AuditLogger()
            
            # Check that the log directory has secure permissions
            log_dir = os.path.dirname(audit_logger._get_log_path())
            assert os.path.exists(log_dir)
            
            # Check directory permissions (should be 0o700 - read/write/execute for owner only)
            dir_stat = os.stat(log_dir)
            dir_permissions = dir_stat.st_mode & 0o777
            assert dir_permissions == 0o700