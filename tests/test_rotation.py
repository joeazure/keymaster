"""Tests for key rotation functionality."""

import pytest
import tempfile
import os
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from keymaster.rotation import KeyRotator, KeyRotationHistory, RotationError


class TestKeyRotationHistory:
    """Test the KeyRotationHistory class."""
    
    def setup_method(self):
        """Setup test environment."""
        # Use temporary file for history
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.temp_file.close()
        self.history = KeyRotationHistory()
        self.history.history_file = self.temp_file.name
        self.history._ensure_history_file()
    
    def teardown_method(self):
        """Cleanup test environment."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_record_rotation_success(self):
        """Test recording a successful rotation."""
        self.history.record_rotation(
            service="openai",
            environment="dev",
            success=True,
            backup_path="/path/to/backup.kmbackup"
        )
        
        rotations = self.history.get_rotation_history("openai", "dev")
        assert len(rotations) == 1
        
        rotation = rotations[0]
        assert rotation["success"] is True
        assert rotation["backup_path"] == "/path/to/backup.kmbackup"
        assert "timestamp" in rotation
        assert "user" in rotation
    
    def test_record_rotation_failure(self):
        """Test recording a failed rotation."""
        self.history.record_rotation(
            service="openai",
            environment="dev",
            success=False,
            error_message="Key validation failed"
        )
        
        rotations = self.history.get_rotation_history("openai", "dev")
        assert len(rotations) == 1
        
        rotation = rotations[0]
        assert rotation["success"] is False
        assert rotation["error_message"] == "Key validation failed"
    
    def test_multiple_rotations_limit(self):
        """Test that rotation history is limited to 10 entries."""
        # Record 15 rotations
        for i in range(15):
            self.history.record_rotation(
                service="openai",
                environment="dev",
                success=True
            )
        
        rotations = self.history.get_rotation_history("openai", "dev")
        # Should only keep last 10
        assert len(rotations) == 10
    
    def test_get_last_rotation(self):
        """Test getting the last successful rotation."""
        # Record failed rotation
        self.history.record_rotation(
            service="openai",
            environment="dev",
            success=False
        )
        
        # Record successful rotation
        self.history.record_rotation(
            service="openai",
            environment="dev",
            success=True,
            backup_path="/backup.kmbackup"
        )
        
        last_rotation = self.history.get_last_rotation("openai", "dev")
        assert last_rotation is not None
        assert last_rotation["success"] is True
        assert last_rotation["backup_path"] == "/backup.kmbackup"
    
    def test_get_last_rotation_none(self):
        """Test getting last rotation when none exist."""
        last_rotation = self.history.get_last_rotation("nonexistent", "dev")
        assert last_rotation is None
    
    @patch('keymaster.rotation.KeyStore.list_keys')
    def test_get_keys_due_for_rotation(self, mock_list_keys):
        """Test getting keys due for rotation."""
        # Mock stored keys
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        recent_date = (datetime.now() - timedelta(days=30)).isoformat()
        
        mock_list_keys.return_value = [
            ('openai', 'dev', old_date, 'user1'),
            ('anthropic', 'prod', recent_date, 'user1')
        ]
        
        # Record a recent rotation for anthropic
        self.history.record_rotation("anthropic", "prod", True)
        
        due_keys = self.history.get_keys_due_for_rotation(days_threshold=90)
        
        # Only openai should be due (no recent rotation recorded)
        assert len(due_keys) == 1
        assert due_keys[0][0] == "openai"
        assert due_keys[0][1] == "dev"
    
    def test_get_rotation_stats(self):
        """Test getting rotation statistics."""
        # Record some rotations
        self.history.record_rotation("openai", "dev", True)
        self.history.record_rotation("openai", "dev", False)
        self.history.record_rotation("anthropic", "prod", True)
        
        stats = self.history.get_rotation_stats()
        
        assert stats["total_keys_tracked"] == 2
        assert stats["total_rotations"] == 3
        assert stats["successful_rotations"] == 2
        assert stats["failed_rotations"] == 1
        assert stats["keys_never_rotated"] == 0


class TestKeyRotator:
    """Test the KeyRotator class."""
    
    def setup_method(self):
        """Setup test environment."""
        self.rotator = KeyRotator()
        self.test_service = "openai"
        self.test_environment = "dev"
        self.test_key = "sk-test123456789"
    
    @patch('keymaster.rotation.KeyStore.get_key')
    @patch('keymaster.rotation.KeyStore.store_key')
    @patch('keymaster.rotation.get_provider_by_name')
    def test_rotate_key_success(self, mock_get_provider, mock_store_key, mock_get_key):
        """Test successful key rotation."""
        # Mock existing key
        mock_get_key.return_value = "old_key_value"
        
        # Mock provider for testing
        mock_provider = MagicMock()
        mock_provider.test_key.return_value = {"status": "valid"}
        mock_get_provider.return_value = mock_provider
        
        # Perform rotation
        result = self.rotator.rotate_key(
            service=self.test_service,
            environment=self.test_environment,
            new_key=self.test_key,
            test_key=True,
            create_backup=False  # Skip backup for test
        )
        
        # Verify results
        assert result["rotation_successful"] is True
        assert result["key_tested"] is True
        assert result["backup_created"] is False
        
        # Verify key was stored
        mock_store_key.assert_called_with(self.test_service, self.test_environment, self.test_key)
    
    @patch('keymaster.rotation.KeyStore.get_key')
    @patch('keymaster.rotation.get_provider_by_name')
    def test_rotate_key_test_failure(self, mock_get_provider, mock_get_key):
        """Test rotation with key test failure."""
        mock_get_key.return_value = "old_key_value"
        
        # Mock provider that fails testing
        mock_provider = MagicMock()
        mock_provider.test_key.side_effect = Exception("Invalid key")
        mock_get_provider.return_value = mock_provider
        
        # Should raise RotationError
        with pytest.raises(RotationError) as exc_info:
            self.rotator.rotate_key(
                service=self.test_service,
                environment=self.test_environment,
                new_key=self.test_key,
                test_key=True,
                create_backup=False
            )
        
        assert "validation failed" in str(exc_info.value)
    
    @patch('keymaster.rotation.KeyStore.get_key')
    @patch('keymaster.rotation.KeyStore.store_key')
    @patch('keymaster.rotation.get_provider_by_name')
    def test_rotate_key_no_test(self, mock_get_provider, mock_store_key, mock_get_key):
        """Test rotation without key testing."""
        mock_get_key.return_value = "old_key_value"
        mock_get_provider.return_value = None  # No provider available
        
        # Should succeed even without provider (no testing)
        result = self.rotator.rotate_key(
            service=self.test_service,
            environment=self.test_environment,
            new_key=self.test_key,
            test_key=False,
            create_backup=False
        )
        
        assert result["rotation_successful"] is True
        assert result["key_tested"] is False
    
    @patch('keymaster.rotation.KeyStore.get_key')
    @patch('keymaster.rotation.KeyStore.store_key')
    @patch('keymaster.rotation.get_provider_by_name')
    @patch.object(KeyRotator, '_create_pre_rotation_backup')
    def test_rotate_key_with_backup(self, mock_backup, mock_get_provider, mock_store_key, mock_get_key):
        """Test rotation with backup creation."""
        mock_get_key.return_value = "old_key_value"
        mock_get_provider.return_value = None  # No testing
        mock_backup.return_value = "/path/to/backup.kmbackup"
        
        result = self.rotator.rotate_key(
            service=self.test_service,
            environment=self.test_environment,
            new_key=self.test_key,
            test_key=False,
            create_backup=True,
            backup_password="test_password"
        )
        
        assert result["backup_created"] is True
        assert result["backup_path"] == "/path/to/backup.kmbackup"
        mock_backup.assert_called_once()
    
    @patch('keymaster.rotation.KeyStore.get_key')
    @patch('keymaster.rotation.KeyStore.store_key')
    def test_backup_old_key_in_keystore(self, mock_store_key, mock_get_key):
        """Test backing up old key in keystore."""
        old_key = "old_key_value"
        
        self.rotator._backup_old_key_in_keystore(
            self.test_service,
            self.test_environment,
            old_key
        )
        
        # Should have called store_key with backup service name
        calls = mock_store_key.call_args_list
        assert len(calls) == 1
        
        backup_service = calls[0][0][0]
        assert backup_service.startswith(f"{self.test_service}_backup_")
        assert calls[0][0][1] == self.test_environment
        assert calls[0][0][2] == old_key
    
    @patch('keymaster.rotation.KeyStore.list_keys')
    def test_list_rotation_candidates(self, mock_list_keys):
        """Test listing rotation candidates."""
        # Mock keys with different ages
        old_date = (datetime.now() - timedelta(days=200)).isoformat()
        medium_date = (datetime.now() - timedelta(days=120)).isoformat()
        recent_date = (datetime.now() - timedelta(days=30)).isoformat()
        
        mock_list_keys.return_value = [
            ('openai', 'dev', old_date, 'user1'),
            ('anthropic', 'prod', medium_date, 'user1'),
            ('stability', 'dev', recent_date, 'user1')
        ]
        
        candidates = self.rotator.list_rotation_candidates(days_threshold=90)
        
        # Should return candidates (old and medium age, recent should be excluded)
        assert len(candidates) >= 1  # At least the old one
        
        # Find the high urgency candidate
        high_urgency = [c for c in candidates if c["urgency"] == "high"]
        assert len(high_urgency) >= 1
        assert high_urgency[0]["service"] == "openai"
    
    def test_find_recent_backup(self):
        """Test finding recent backup files."""
        # Create temporary backup directory
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = os.path.join(temp_dir, "rotation_backups")
            os.makedirs(backup_dir)
            
            # Create mock backup files
            backup1 = os.path.join(backup_dir, "pre_rotation_openai_dev_20231201_120000.kmbackup")
            backup2 = os.path.join(backup_dir, "pre_rotation_openai_dev_20231202_120000.kmbackup")
            backup3 = os.path.join(backup_dir, "pre_rotation_anthropic_dev_20231203_120000.kmbackup")
            
            for backup in [backup1, backup2, backup3]:
                with open(backup, 'w') as f:
                    f.write("test")
            
            # Patch the backup directory path
            with patch('keymaster.rotation.os.path.expanduser', return_value=temp_dir):
                # Should find the most recent backup for openai/dev
                recent_backup = self.rotator._find_recent_backup("openai", "dev")
                assert recent_backup == backup2  # Most recent
                
                # Should return None for non-existent service
                no_backup = self.rotator._find_recent_backup("nonexistent", "dev")
                assert no_backup is None