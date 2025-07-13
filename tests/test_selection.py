"""Tests for service and environment selection utilities."""

import pytest
from unittest.mock import patch, MagicMock

from keymaster.selection import ServiceEnvironmentSelector
from keymaster.exceptions import ServiceNotFoundError, EnvironmentNotFoundError


class TestServiceEnvironmentSelector:
    """Test the ServiceEnvironmentSelector utility class."""
    
    @patch('keymaster.selection.KeyStore.list_keys')
    @patch('keymaster.selection.get_providers')
    def test_get_services_with_keys(self, mock_get_providers, mock_list_keys):
        """Test getting services that have stored keys."""
        # Mock stored keys
        mock_list_keys.return_value = [
            ('openai', 'dev', '2023-01-01T00:00:00', 'user1'),
            ('anthropic', 'prod', '2023-01-01T00:00:00', 'user1'),
            ('invalid_service', 'dev', '2023-01-01T00:00:00', 'user1')  # Won't match any provider
        ]
        
        # Mock providers
        mock_openai = MagicMock()
        mock_openai.service_name = 'OpenAI'
        mock_anthropic = MagicMock()
        mock_anthropic.service_name = 'Anthropic'
        
        mock_get_providers.return_value = {
            'openai': mock_openai,
            'anthropic': mock_anthropic
        }
        
        services = ServiceEnvironmentSelector.get_services_with_keys()
        
        # Should return canonical service names for services with stored keys
        assert services == {'OpenAI', 'Anthropic'}
    
    @patch('keymaster.selection.KeyStore.list_keys')
    def test_get_environments_for_service(self, mock_list_keys):
        """Test getting environments for a specific service."""
        mock_list_keys.return_value = [
            ('openai', 'dev', '2023-01-01T00:00:00', 'user1'),
            ('openai', 'prod', '2023-01-01T00:00:00', 'user1'),
            ('anthropic', 'dev', '2023-01-01T00:00:00', 'user1')
        ]
        
        environments = ServiceEnvironmentSelector.get_environments_for_service('openai')
        assert environments == ['dev', 'prod']
        
        environments = ServiceEnvironmentSelector.get_environments_for_service('anthropic')
        assert environments == ['dev']
        
        environments = ServiceEnvironmentSelector.get_environments_for_service('nonexistent')
        assert environments == []
    
    @patch('keymaster.selection.get_provider_by_name')
    def test_get_canonical_service_name(self, mock_get_provider):
        """Test getting canonical service name from user input."""
        mock_provider = MagicMock()
        mock_provider.service_name = 'OpenAI'
        mock_get_provider.return_value = mock_provider
        
        result = ServiceEnvironmentSelector.get_canonical_service_name('openai')
        assert result == 'OpenAI'
        
        mock_get_provider.return_value = None
        result = ServiceEnvironmentSelector.get_canonical_service_name('invalid')
        assert result is None
    
    @patch('keymaster.selection.ServiceEnvironmentSelector.get_environments_for_service')
    def test_validate_service_has_environment(self, mock_get_environments):
        """Test validating if a service has a specific environment."""
        mock_get_environments.return_value = ['dev', 'staging', 'prod']
        
        assert ServiceEnvironmentSelector.validate_service_has_environment('openai', 'dev') is True
        assert ServiceEnvironmentSelector.validate_service_has_environment('openai', 'test') is False
    
    @patch('keymaster.selection.get_providers')
    def test_get_all_available_services(self, mock_get_providers):
        """Test getting all available service names."""
        mock_openai = MagicMock()
        mock_openai.service_name = 'OpenAI'
        mock_anthropic = MagicMock()
        mock_anthropic.service_name = 'Anthropic'
        
        mock_get_providers.return_value = {
            'openai': mock_openai,
            'anthropic': mock_anthropic
        }
        
        services = ServiceEnvironmentSelector.get_all_available_services()
        assert set(services) == {'OpenAI', 'Anthropic'}
    
    @patch('keymaster.selection.get_provider_by_name')
    @patch('keymaster.selection.ServiceEnvironmentSelector.get_all_available_services')
    @patch('keymaster.selection._get_closest_matches')
    def test_find_service_with_fuzzy_matching_exact_match(self, mock_fuzzy, mock_get_all, mock_get_provider):
        """Test fuzzy matching with exact match."""
        mock_provider = MagicMock()
        mock_provider.service_name = 'OpenAI'
        mock_get_provider.return_value = mock_provider
        
        result = ServiceEnvironmentSelector.find_service_with_fuzzy_matching('openai')
        assert result == 'OpenAI'
        
        # Should not call fuzzy matching for exact match
        mock_fuzzy.assert_not_called()
    
    @patch('keymaster.selection.get_provider_by_name')
    @patch('keymaster.selection.ServiceEnvironmentSelector.get_all_available_services')
    @patch('keymaster.selection._get_closest_matches')
    def test_find_service_with_fuzzy_matching_fuzzy_match(self, mock_fuzzy, mock_get_all, mock_get_provider):
        """Test fuzzy matching with approximate match."""
        mock_get_provider.return_value = None  # No exact match
        mock_get_all.return_value = ['OpenAI', 'Anthropic']
        mock_fuzzy.return_value = ['OpenAI']  # Best fuzzy match
        
        result = ServiceEnvironmentSelector.find_service_with_fuzzy_matching('openai')
        assert result == 'OpenAI'
        
        mock_fuzzy.assert_called_once_with('openai', ['OpenAI', 'Anthropic'])
    
    @patch('keymaster.selection.get_provider_by_name')
    @patch('keymaster.selection.ServiceEnvironmentSelector.get_all_available_services')
    @patch('keymaster.selection._get_closest_matches')
    def test_find_service_with_fuzzy_matching_no_match(self, mock_fuzzy, mock_get_all, mock_get_provider):
        """Test fuzzy matching with no good matches."""
        mock_get_provider.return_value = None  # No exact match
        mock_get_all.return_value = ['OpenAI', 'Anthropic']
        mock_fuzzy.return_value = []  # No good fuzzy matches
        
        with pytest.raises(ServiceNotFoundError) as exc_info:
            ServiceEnvironmentSelector.find_service_with_fuzzy_matching('invalid')
        
        assert 'invalid' in str(exc_info.value)
    
    @patch('keymaster.selection.ServiceEnvironmentSelector.get_environments_for_service')
    @patch('keymaster.selection._get_closest_matches')
    def test_find_environment_with_fuzzy_matching_exact_match(self, mock_fuzzy, mock_get_environments):
        """Test environment fuzzy matching with exact match."""
        mock_get_environments.return_value = ['dev', 'staging', 'prod']
        
        result = ServiceEnvironmentSelector.find_environment_with_fuzzy_matching('dev', 'openai')
        assert result == 'dev'
        
        # Should not call fuzzy matching for exact match
        mock_fuzzy.assert_not_called()
    
    @patch('keymaster.selection.ServiceEnvironmentSelector.get_environments_for_service')
    @patch('keymaster.selection._get_closest_matches')
    def test_find_environment_with_fuzzy_matching_fuzzy_match(self, mock_fuzzy, mock_get_environments):
        """Test environment fuzzy matching with approximate match."""
        mock_get_environments.return_value = ['dev', 'staging', 'prod']
        mock_fuzzy.return_value = ['dev']  # Best fuzzy match
        
        result = ServiceEnvironmentSelector.find_environment_with_fuzzy_matching('development', 'openai')
        assert result == 'dev'
        
        mock_fuzzy.assert_called_once_with('development', ['dev', 'staging', 'prod'])
    
    @patch('keymaster.selection.ServiceEnvironmentSelector.get_environments_for_service')
    @patch('keymaster.selection._get_closest_matches')
    def test_find_environment_with_fuzzy_matching_no_match(self, mock_fuzzy, mock_get_environments):
        """Test environment fuzzy matching with no good matches."""
        mock_get_environments.return_value = ['dev', 'staging', 'prod']
        mock_fuzzy.return_value = []  # No good fuzzy matches
        
        with pytest.raises(EnvironmentNotFoundError) as exc_info:
            ServiceEnvironmentSelector.find_environment_with_fuzzy_matching('invalid', 'openai')
        
        assert 'invalid' in str(exc_info.value)
        assert 'openai' in str(exc_info.value)