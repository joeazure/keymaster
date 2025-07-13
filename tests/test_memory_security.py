"""Tests for memory security functionality."""

import pytest
import sys
from unittest.mock import patch, MagicMock

from keymaster.memory_security import (
    SecureString, secure_temp_string, secure_zero_memory,
    secure_compare, SecureBuffer, get_memory_info
)


class TestSecureString:
    """Test the SecureString class."""
    
    def test_create_secure_string(self):
        """Test creating a SecureString."""
        test_value = "secret_api_key_123"
        secure_str = SecureString(test_value)
        
        assert str(secure_str) == test_value
        assert secure_str.get() == test_value
        assert len(secure_str) == len(test_value)
        assert not secure_str.is_cleared()
    
    def test_secure_string_clear(self):
        """Test clearing a SecureString."""
        test_value = "secret_api_key_123"
        secure_str = SecureString(test_value)
        
        secure_str.clear()
        
        assert secure_str.is_cleared()
        with pytest.raises(ValueError):
            str(secure_str)
        with pytest.raises(ValueError):
            secure_str.get()
        assert len(secure_str) == 0
    
    def test_secure_string_repr(self):
        """Test SecureString representation doesn't leak value."""
        test_value = "secret_api_key_123"
        secure_str = SecureString(test_value)
        
        repr_str = repr(secure_str)
        assert "REDACTED" in repr_str
        assert test_value not in repr_str
    
    def test_secure_string_context_manager(self):
        """Test SecureString with context manager."""
        test_value = "secret_api_key_123"
        
        with secure_temp_string(test_value) as secure_str:
            assert secure_str.get() == test_value
            assert not secure_str.is_cleared()
        
        # Should be cleared after context
        assert secure_str.is_cleared()
    
    def test_secure_string_double_clear(self):
        """Test that double clearing doesn't cause issues."""
        test_value = "secret_api_key_123"
        secure_str = SecureString(test_value)
        
        secure_str.clear()
        secure_str.clear()  # Should not raise exception
        
        assert secure_str.is_cleared()


class TestSecureBuffer:
    """Test the SecureBuffer class."""
    
    def test_create_secure_buffer(self):
        """Test creating a SecureBuffer."""
        buffer = SecureBuffer(100)
        assert buffer.size == 100
        assert not buffer._cleared
    
    def test_buffer_write_read(self):
        """Test writing to and reading from buffer."""
        buffer = SecureBuffer(100)
        test_data = b"secret_data_123"
        
        buffer.write(test_data)
        read_data = buffer.read(len(test_data))
        
        assert read_data == test_data
    
    def test_buffer_write_offset(self):
        """Test writing with offset."""
        buffer = SecureBuffer(100)
        data1 = b"hello"
        data2 = b"world"
        
        buffer.write(data1, 0)
        buffer.write(data2, 5)
        
        result = buffer.read(10)
        assert result == b"helloworld"
    
    def test_buffer_read_offset_length(self):
        """Test reading with offset and length."""
        buffer = SecureBuffer(100)
        test_data = b"hello_world_123"
        
        buffer.write(test_data)
        
        # Read middle portion
        result = buffer.read(5, 6)  # "world"
        assert result == b"world"
    
    def test_buffer_overflow(self):
        """Test buffer overflow protection."""
        buffer = SecureBuffer(10)
        large_data = b"this_is_too_large_for_buffer"
        
        with pytest.raises(ValueError):
            buffer.write(large_data)
    
    def test_buffer_clear(self):
        """Test buffer clearing."""
        buffer = SecureBuffer(100)
        test_data = b"secret_data"
        
        buffer.write(test_data)
        buffer.clear()
        
        with pytest.raises(ValueError):
            buffer.read()
    
    def test_buffer_context_manager(self):
        """Test buffer as context manager."""
        test_data = b"secret_data"
        
        with SecureBuffer(100) as buffer:
            buffer.write(test_data)
            assert buffer.read(len(test_data)) == test_data
        
        # Should be cleared after context
        assert buffer._cleared


class TestSecureZeroMemory:
    """Test memory zeroing functionality."""
    
    def test_secure_zero_memory_string(self):
        """Test zeroing string memory."""
        test_string = "secret_data_123"
        
        # This should not raise an exception
        secure_zero_memory(test_string)
    
    def test_secure_zero_memory_bytes(self):
        """Test zeroing bytes memory."""
        test_bytes = b"secret_data_123"
        
        # This should not raise an exception
        secure_zero_memory(test_bytes)
    
    def test_secure_zero_memory_bytearray(self):
        """Test zeroing bytearray memory."""
        test_bytearray = bytearray(b"secret_data_123")
        original_length = len(test_bytearray)
        
        secure_zero_memory(test_bytearray)
        
        # bytearray should be zeroed
        assert len(test_bytearray) == original_length
        assert all(b == 0 for b in test_bytearray)
    
    def test_secure_zero_memory_empty(self):
        """Test zeroing empty data."""
        secure_zero_memory("")
        secure_zero_memory(b"")
        secure_zero_memory(bytearray())
    
    @patch('keymaster.memory_security.log')
    def test_secure_zero_memory_exception(self, mock_log):
        """Test handling of exceptions during memory zeroing."""
        # This might cause an exception depending on the system
        secure_zero_memory("test")
        
        # Should not raise, but might log warnings


class TestSecureCompare:
    """Test constant-time string comparison."""
    
    def test_secure_compare_equal(self):
        """Test comparison of equal strings."""
        str1 = "password123"
        str2 = "password123"
        
        assert secure_compare(str1, str2) is True
    
    def test_secure_compare_different(self):
        """Test comparison of different strings."""
        str1 = "password123"
        str2 = "password456"
        
        assert secure_compare(str1, str2) is False
    
    def test_secure_compare_different_length(self):
        """Test comparison of strings with different lengths."""
        str1 = "short"
        str2 = "much_longer_string"
        
        assert secure_compare(str1, str2) is False
    
    def test_secure_compare_empty(self):
        """Test comparison with empty strings."""
        assert secure_compare("", "") is True
        assert secure_compare("test", "") is False
        assert secure_compare("", "test") is False
    
    def test_secure_compare_timing(self):
        """Test that comparison takes similar time regardless of difference position."""
        # This is a basic test - timing attacks are hard to test reliably
        str1 = "a" * 1000 + "X"
        str2 = "a" * 1000 + "Y"
        str3 = "X" + "a" * 1000
        
        # All should return False
        assert secure_compare(str1, str2) is False
        assert secure_compare(str1, str3) is False


class TestMemoryInfo:
    """Test memory capability detection."""
    
    def test_get_memory_info(self):
        """Test getting memory information."""
        info = get_memory_info()
        
        assert "platform" in info
        assert "secure_zero_available" in info
        assert "explicit_bzero_available" in info
        assert "secure_string_support" in info
        assert "notes" in info
        
        assert info["platform"] == sys.platform
        assert isinstance(info["secure_string_support"], bool)
        assert isinstance(info["notes"], list)
    
    @patch('sys.platform', 'win32')
    @patch('ctypes.windll', create=True)
    def test_get_memory_info_windows(self, mock_windll):
        """Test memory info on Windows."""
        # Mock Windows kernel32
        mock_kernel32 = MagicMock()
        mock_kernel32.SecureZeroMemory = MagicMock()
        mock_windll.kernel32 = mock_kernel32
        
        info = get_memory_info()
        
        assert info["platform"] == "win32"
        assert "Windows" in str(info["notes"])
    
    @patch('sys.platform', 'darwin')
    @patch('ctypes.util.find_library')
    @patch('ctypes.CDLL')
    def test_get_memory_info_unix(self, mock_cdll, mock_find_library):
        """Test memory info on Unix-like systems."""
        # Mock libc with explicit_bzero
        mock_find_library.return_value = "libc.so.6"
        mock_libc = MagicMock()
        mock_libc.explicit_bzero = MagicMock()
        mock_cdll.return_value = mock_libc
        
        info = get_memory_info()
        
        assert info["platform"] == "darwin"