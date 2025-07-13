"""Tests for backup and restore functionality."""

import pytest
import tempfile
import os
import json
from unittest.mock import patch, MagicMock

from keymaster.backup import BackupManager
from keymaster.exceptions import BackupError


class TestBackupManager:
    """Test the BackupManager class."""
    
    def setup_method(self):
        """Setup test environment."""
        self.backup_manager = BackupManager()
        self.test_password = "test_password_123"
    
    @patch('keymaster.backup.KeyStore.list_keys')
    @patch('keymaster.backup.KeyStore.get_key')
    def test_create_backup_success(self, mock_get_key, mock_list_keys):
        """Test successful backup creation."""
        # Mock stored keys
        mock_list_keys.return_value = [
            ('openai', 'dev', '2023-01-01T00:00:00', 'user1'),
            ('anthropic', 'prod', '2023-01-01T00:00:00', 'user1')
        ]
        
        # Mock key retrieval
        mock_get_key.side_effect = lambda service, env: f"key_for_{service}_{env}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.kmbackup') as f:
            backup_path = f.name
        
        try:
            # Create backup
            summary = self.backup_manager.create_backup(
                backup_path=backup_path,
                password=self.test_password,
                include_audit_logs=False
            )
            
            # Verify summary
            assert summary['keys_count'] == 2
            assert 'openai' in summary['services']
            assert 'anthropic' in summary['services']
            assert 'dev' in summary['environments']
            assert 'prod' in summary['environments']
            assert summary['file_size'] > 0
            
            # Verify file exists and has content
            assert os.path.exists(backup_path)
            assert os.path.getsize(backup_path) > 0
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    @patch('keymaster.backup.KeyStore.list_keys')
    @patch('keymaster.backup.KeyStore.get_key')
    def test_create_backup_with_filters(self, mock_get_key, mock_list_keys):
        """Test backup creation with service/environment filters."""
        # Mock stored keys
        mock_list_keys.return_value = [
            ('openai', 'dev', '2023-01-01T00:00:00', 'user1'),
            ('openai', 'prod', '2023-01-01T00:00:00', 'user1'),
            ('anthropic', 'dev', '2023-01-01T00:00:00', 'user1')
        ]
        
        mock_get_key.side_effect = lambda service, env: f"key_for_{service}_{env}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.kmbackup') as f:
            backup_path = f.name
        
        try:
            # Create backup with service filter
            summary = self.backup_manager.create_backup(
                backup_path=backup_path,
                password=self.test_password,
                service_filter="openai",
                environment_filter="dev"
            )
            
            # Should only have the filtered keys
            # Note: list_keys with service filter returns all, then we filter in collect_backup_data
            assert summary['keys_count'] == 1
            assert 'openai' in summary['services']
            assert 'dev' in summary['environments']
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    def test_create_backup_invalid_path(self):
        """Test backup creation with invalid path."""
        invalid_path = "/invalid/path/backup.kmbackup"
        
        with pytest.raises(BackupError):
            self.backup_manager.create_backup(
                backup_path=invalid_path,
                password=self.test_password
            )
    
    @patch('keymaster.backup.KeyStore.list_keys')
    @patch('keymaster.backup.KeyStore.get_key')
    @patch('keymaster.backup.KeyStore.store_key')
    def test_restore_backup_success(self, mock_store_key, mock_get_key, mock_list_keys):
        """Test successful backup restore."""
        # Create a backup first
        mock_list_keys.return_value = [
            ('openai', 'dev', '2023-01-01T00:00:00', 'user1')
        ]
        mock_get_key.side_effect = lambda service, env: f"key_for_{service}_{env}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.kmbackup') as f:
            backup_path = f.name
        
        try:
            # Create backup
            self.backup_manager.create_backup(
                backup_path=backup_path,
                password=self.test_password
            )
            
            # Mock empty existing keys for restore
            mock_list_keys.return_value = []
            # During restore, get_key should return None for the key being restored
            mock_get_key.side_effect = lambda service, env: None
            
            # Restore backup
            summary = self.backup_manager.restore_backup(
                backup_path=backup_path,
                password=self.test_password,
                overwrite_existing=False
            )
            
            # Verify restore summary
            assert summary['restored_keys'] == 1  # Should restore the key
            assert summary['total_processed'] == 1
            assert len(summary['errors']) == 0
            
            # Verify store_key was called
            mock_store_key.assert_called_with('openai', 'dev', 'key_for_openai_dev')
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    @patch('keymaster.backup.KeyStore.list_keys')
    @patch('keymaster.backup.KeyStore.get_key')
    def test_restore_backup_dry_run(self, mock_get_key, mock_list_keys):
        """Test backup restore in dry run mode."""
        # Create a backup first
        mock_list_keys.return_value = [
            ('openai', 'dev', '2023-01-01T00:00:00', 'user1')
        ]
        mock_get_key.side_effect = lambda service, env: f"key_for_{service}_{env}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.kmbackup') as f:
            backup_path = f.name
        
        try:
            # Create backup
            self.backup_manager.create_backup(
                backup_path=backup_path,
                password=self.test_password
            )
            
            # Dry run restore
            summary = self.backup_manager.restore_backup(
                backup_path=backup_path,
                password=self.test_password,
                dry_run=True
            )
            
            # Should return analysis without actually restoring
            assert 'total_keys' in summary
            assert 'new_keys' in summary
            assert 'conflicts' in summary
            assert summary['total_keys'] == 1
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    def test_restore_backup_wrong_password(self):
        """Test restore with wrong password."""
        # Create a dummy encrypted file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.kmbackup') as f:
            f.write(b"invalid_encrypted_data")
            backup_path = f.name
        
        try:
            with pytest.raises(BackupError) as exc_info:
                self.backup_manager.restore_backup(
                    backup_path=backup_path,
                    password="wrong_password"
                )
            
            assert "decrypt" in str(exc_info.value)
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    def test_restore_backup_missing_file(self):
        """Test restore with missing backup file."""
        with pytest.raises(BackupError) as exc_info:
            self.backup_manager.restore_backup(
                backup_path="/nonexistent/backup.kmbackup",
                password=self.test_password
            )
        
        assert "not found" in str(exc_info.value)
    
    @patch('keymaster.backup.KeyStore.list_keys')
    @patch('keymaster.backup.KeyStore.get_key')
    def test_verify_backup(self, mock_get_key, mock_list_keys):
        """Test backup verification."""
        # Create a backup first
        mock_list_keys.return_value = [
            ('openai', 'dev', '2023-01-01T00:00:00', 'user1')
        ]
        mock_get_key.side_effect = lambda service, env: f"key_for_{service}_{env}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.kmbackup') as f:
            backup_path = f.name
        
        try:
            # Create backup
            self.backup_manager.create_backup(
                backup_path=backup_path,
                password=self.test_password
            )
            
            # Test verification with correct password
            assert self.backup_manager.verify_backup(backup_path, self.test_password) is True
            
            # Test verification with wrong password
            assert self.backup_manager.verify_backup(backup_path, "wrong_password") is False
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)
    
    def test_derive_key_from_password(self):
        """Test password-based key derivation."""
        key1 = self.backup_manager._derive_key_from_password("password123")
        key2 = self.backup_manager._derive_key_from_password("password123")
        key3 = self.backup_manager._derive_key_from_password("different")
        
        # Same password should generate same key
        assert key1 == key2
        
        # Different password should generate different key
        assert key1 != key3
        
        # Key should be proper length for Fernet
        assert len(key1) == 44  # Base64 encoded 32-byte key
    
    @patch('keymaster.backup.KeyStore.list_keys')
    @patch('keymaster.backup.KeyStore.get_key')
    @patch('keymaster.backup.KeyStore.store_key')
    def test_restore_with_conflicts(self, mock_store_key, mock_get_key, mock_list_keys):
        """Test restore with existing key conflicts."""
        # Create a backup first
        mock_list_keys.return_value = [
            ('openai', 'dev', '2023-01-01T00:00:00', 'user1')
        ]
        mock_get_key.side_effect = lambda service, env: f"key_for_{service}_{env}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.kmbackup') as f:
            backup_path = f.name
        
        try:
            # Create backup
            self.backup_manager.create_backup(
                backup_path=backup_path,
                password=self.test_password
            )
            
            # Mock existing key for restore (conflict)
            mock_get_key.return_value = "existing_key"
            
            # Restore without overwrite (should skip)
            summary = self.backup_manager.restore_backup(
                backup_path=backup_path,
                password=self.test_password,
                overwrite_existing=False
            )
            
            assert summary['restored_keys'] == 0
            assert summary['skipped_keys'] == 1
            
            # Restore with overwrite (should replace)
            summary = self.backup_manager.restore_backup(
                backup_path=backup_path,
                password=self.test_password,
                overwrite_existing=True
            )
            
            assert summary['restored_keys'] == 1
            assert summary['skipped_keys'] == 0
            
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)