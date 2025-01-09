from datetime import datetime
import pytest
from keymaster.db import KeyDatabase

class TestKeyDatabase:
    def test_add_key(self, test_db):
        test_db.add_key(
            service_name="OpenAI",
            environment="test",
            keychain_service_name="keymaster-openai",
            user="testuser"
        )
        
        metadata = test_db.get_key_metadata("OpenAI", "test")
        assert metadata is not None
        assert metadata["service_name"].lower() == "openai"
        assert metadata["environment"].lower() == "test"
        
    def test_remove_key(self, test_db):
        # First add a key
        test_db.add_key(
            service_name="OpenAI",
            environment="test",
            keychain_service_name="keymaster-openai",
            user="testuser"
        )
        
        # Then remove it
        test_db.remove_key("OpenAI", "test")
        
        # Verify it's gone
        metadata = test_db.get_key_metadata("OpenAI", "test")
        assert metadata is None 