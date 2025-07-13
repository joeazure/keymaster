"""
Memory security utilities for Keymaster.

This module provides functions to securely handle sensitive data in memory,
including secure memory clearing and context managers for temporary sensitive data.
"""

import os
import sys
import ctypes
import ctypes.util
from typing import Any, Optional, Union
from contextlib import contextmanager
import structlog

log = structlog.get_logger()


class SecureString:
    """A string wrapper that automatically clears memory when destroyed."""
    
    def __init__(self, value: str):
        self._value = value
        self._cleared = False
    
    def __str__(self) -> str:
        if self._cleared:
            raise ValueError("SecureString has been cleared")
        return self._value
    
    def __repr__(self) -> str:
        return "<SecureString: [REDACTED]>"
    
    def __len__(self) -> int:
        if self._cleared:
            return 0
        return len(self._value)
    
    def __del__(self):
        self.clear()
    
    def clear(self) -> None:
        """Securely clear the string from memory."""
        if not self._cleared and self._value:
            try:
                secure_zero_memory(self._value)
            except Exception as e:
                log.warning("Failed to securely clear memory", error=str(e))
            finally:
                self._value = ""
                self._cleared = True
    
    def get(self) -> str:
        """Get the string value."""
        if self._cleared:
            raise ValueError("SecureString has been cleared")
        return self._value
    
    def is_cleared(self) -> bool:
        """Check if the string has been cleared."""
        return self._cleared


@contextmanager
def secure_temp_string(value: str):
    """
    Context manager for temporarily holding a sensitive string.
    Automatically clears memory when exiting context.
    """
    secure_str = SecureString(value)
    try:
        yield secure_str
    finally:
        secure_str.clear()


def secure_zero_memory(data: Union[str, bytes, bytearray]) -> None:
    """
    Attempt to securely zero out memory containing sensitive data.
    
    This is a best-effort function - Python's memory management makes
    it impossible to guarantee complete memory clearing, but this helps
    reduce the window of exposure.
    
    Args:
        data: The sensitive data to clear from memory
    """
    try:
        if isinstance(data, str):
            _zero_string_memory(data)
        elif isinstance(data, (bytes, bytearray)):
            _zero_bytes_memory(data)
    except Exception as e:
        log.warning("Failed to zero memory", error=str(e), data_type=type(data).__name__)


def _zero_string_memory(s: str) -> None:
    """Attempt to zero string memory using ctypes."""
    if not s:
        return
    
    try:
        # Get the memory address of the string
        string_address = id(s)
        
        # Calculate the size of the string data
        # Python string objects have a header, so we need to find the actual string data
        if sys.platform == "win32":
            # Windows implementation
            _zero_memory_windows(string_address, len(s))
        else:
            # Unix-like systems
            _zero_memory_unix(string_address, len(s))
            
    except Exception as e:
        log.debug("String memory zeroing failed", error=str(e))


def _zero_bytes_memory(data: Union[bytes, bytearray]) -> None:
    """Zero bytes/bytearray memory."""
    if isinstance(data, bytearray):
        # bytearray is mutable, so we can directly modify it
        for i in range(len(data)):
            data[i] = 0
    else:
        # bytes is immutable, try to zero the underlying memory
        try:
            data_address = id(data)
            if sys.platform == "win32":
                _zero_memory_windows(data_address, len(data))
            else:
                _zero_memory_unix(data_address, len(data))
        except Exception as e:
            log.debug("Bytes memory zeroing failed", error=str(e))


def _zero_memory_windows(address: int, size: int) -> None:
    """Zero memory on Windows using kernel32."""
    try:
        kernel32 = ctypes.windll.kernel32
        # Use SecureZeroMemory if available (Windows Vista+)
        if hasattr(kernel32, 'SecureZeroMemory'):
            kernel32.SecureZeroMemory(ctypes.c_void_p(address), ctypes.c_size_t(size))
        else:
            # Fallback to RtlSecureZeroMemory
            kernel32.RtlSecureZeroMemory(ctypes.c_void_p(address), ctypes.c_size_t(size))
    except Exception as e:
        log.debug("Windows memory zeroing failed", error=str(e))


def _zero_memory_unix(address: int, size: int) -> None:
    """Zero memory on Unix-like systems."""
    try:
        # Try to use explicit_bzero if available (BSD/macOS)
        libc_name = ctypes.util.find_library("c")
        if libc_name:
            libc = ctypes.CDLL(libc_name)
            if hasattr(libc, 'explicit_bzero'):
                libc.explicit_bzero(ctypes.c_void_p(address), ctypes.c_size_t(size))
                return
        
        # Fallback to memset with volatile
        _volatile_memset(address, size)
        
    except Exception as e:
        log.debug("Unix memory zeroing failed", error=str(e))


def _volatile_memset(address: int, size: int) -> None:
    """Volatile memset to prevent compiler optimization."""
    try:
        # Create a volatile pointer and zero the memory
        ptr = ctypes.c_char_p(address)
        for i in range(size):
            ptr[i] = b'\x00'
    except Exception as e:
        log.debug("Volatile memset failed", error=str(e))


class SecureBuffer:
    """A secure buffer for sensitive data that zeros memory on destruction."""
    
    def __init__(self, size: int):
        self.size = size
        self.buffer = bytearray(size)
        self._cleared = False
    
    def write(self, data: bytes, offset: int = 0) -> None:
        """Write data to the buffer."""
        if self._cleared:
            raise ValueError("Buffer has been cleared")
        
        if offset + len(data) > self.size:
            raise ValueError("Data too large for buffer")
        
        self.buffer[offset:offset + len(data)] = data
    
    def read(self, length: Optional[int] = None, offset: int = 0) -> bytes:
        """Read data from the buffer."""
        if self._cleared:
            raise ValueError("Buffer has been cleared")
        
        if length is None:
            return bytes(self.buffer[offset:])
        
        return bytes(self.buffer[offset:offset + length])
    
    def clear(self) -> None:
        """Securely clear the buffer."""
        if not self._cleared:
            secure_zero_memory(self.buffer)
            self._cleared = True
    
    def __del__(self):
        self.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.clear()


def get_memory_info() -> dict:
    """Get information about memory security capabilities."""
    capabilities = {
        "platform": sys.platform,
        "secure_zero_available": False,
        "explicit_bzero_available": False,
        "secure_string_support": True,
        "notes": []
    }
    
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.windll.kernel32
            if hasattr(kernel32, 'SecureZeroMemory'):
                capabilities["secure_zero_available"] = True
            capabilities["notes"].append("Windows SecureZeroMemory support detected")
        except Exception:
            capabilities["notes"].append("Windows secure memory functions not available")
    
    else:
        try:
            libc_name = ctypes.util.find_library("c")
            if libc_name:
                libc = ctypes.CDLL(libc_name)
                if hasattr(libc, 'explicit_bzero'):
                    capabilities["explicit_bzero_available"] = True
                    capabilities["notes"].append("explicit_bzero support detected")
        except Exception:
            capabilities["notes"].append("Unix secure memory functions not available")
    
    if not capabilities["secure_zero_available"] and not capabilities["explicit_bzero_available"]:
        capabilities["notes"].append("Using fallback memory clearing - limited security guarantees")
    
    return capabilities


def secure_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing attacks.
    
    Args:
        a: First string
        b: Second string
        
    Returns:
        True if strings are equal, False otherwise
    """
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    
    return result == 0