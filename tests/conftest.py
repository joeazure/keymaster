"""
Shared pytest fixtures and configuration.
"""
import os
import tempfile
import pytest
from keymaster.db import KeyDatabase
from keymaster.audit import AuditLogger

@pytest.fixture
def temp_home_dir():
    """Create a temporary home directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        old_home = os.environ.get('HOME')
        os.environ['HOME'] = temp_dir
        yield temp_dir
        if old_home:
            os.environ['HOME'] = old_home

@pytest.fixture
def test_db(temp_home_dir):
    """Create a test database instance."""
    return KeyDatabase()

@pytest.fixture
def test_audit_logger(temp_home_dir):
    """Create a test audit logger instance."""
    return AuditLogger() 