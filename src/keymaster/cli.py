import click
from keymaster.security import KeyStore
from keymaster.config import ConfigManager
from datetime import datetime
import os
from typing import Optional
from keymaster.audit import AuditLogger
from keymaster.env import EnvManager
from keymaster.utils import prompt_selection
from keymaster.providers import get_providers, get_provider_by_name
from keymaster.selection import ServiceEnvironmentSelector
from keymaster.backup import BackupManager
from keymaster.rotation import KeyRotator, KeyRotationHistory
from keymaster.memory_security import secure_temp_string
import sys
from keyring.errors import KeyringError
from collections import defaultdict
import locale

# Default environments
DEFAULT_ENVIRONMENTS = ["dev", "staging", "prod"]

@click.group()
def cli() -> None:
    """
    Keymaster CLI: Secure API key management for AI services.
    """
    pass


@cli.command()
def init() -> None:
    """
    Initialize Keymaster configuration and resources.
    """
    # Track changes
    changes_made = []
    
    # Check if already initialized by looking for config and directories
    config_manager = ConfigManager()
    is_initialized = (
        config_manager.config_exists() and
        os.path.exists(os.path.expanduser("~/.keymaster/logs")) and
        os.path.exists(os.path.expanduser("~/.keymaster/db"))
    )
    
    if is_initialized:
        click.echo("Keymaster is already initialized and ready to use.")
        click.echo("No changes were necessary.")
        return
        
    click.echo("Initializing Keymaster...")
    
    # 1. Create initial config file if not present
    if not config_manager.config_exists():
        initial_config = {
            "log_level": "INFO",
            "log_file": "~/.keymaster/logs/keymaster.log",
            "audit_file": "~/.keymaster/logs/audit.log",
            "db_path": "~/.keymaster/db/keymaster.db"
        }
        config_manager.write_config(initial_config)
        changes_made.append("Created initial configuration file")
    
    # Create necessary directories
    dirs_to_create = [
        os.path.expanduser("~/.keymaster/logs"),
        os.path.expanduser("~/.keymaster/db")
    ]
    
    for directory in dirs_to_create:
        if not os.path.exists(directory):
            os.makedirs(directory, mode=0o700)  # Secure permissions
            changes_made.append(f"Created directory: {directory}")
    
    # 2. Verify system requirements and secure storage backend
    try:
        KeyStore._verify_backend()
        click.echo("Verified secure storage backend.")
        
        # Test key storage
        test_service = "__keymaster_test__"
        test_env = "__test__"
        test_value = "test_value"
        
        KeyStore.store_key(test_service, test_env, test_value)
        retrieved = KeyStore.get_key(test_service, test_env)
        KeyStore.remove_key(test_service, test_env)
        
        if retrieved != test_value:
            click.echo("Warning: Secure storage test failed. Key storage may not work correctly.")
        else:
            click.echo("Verified secure storage access.")
            changes_made.append("Verified secure storage access")
    except KeyringError as e:
        click.echo(f"Warning: {str(e)}")
    except Exception as e:
        click.echo(f"Warning: Could not verify secure storage access: {str(e)}")
    
    # Log initialization
    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="init",
        user=os.getenv("USER", "unknown"),
        additional_data={
            "action": "init",
            "platform": sys.platform,
            "storage_test": "success" if retrieved == test_value else "failed",
            "changes_made": changes_made
        }
    )
    
    if changes_made:
        click.echo("\nChanges made during initialization:")
        for change in changes_made:
            click.echo(f"- {change}")
    else:
        click.echo("\nNo changes were necessary during initialization.")
    
    click.echo("\nKeymaster initialization complete.")


@cli.command()
@click.option("--service", required=False, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=False, help="Environment (dev/staging/prod)")
@click.option("--api_key", required=False, help="API key to store securely")
@click.option("--force", is_flag=True, help="Force replace existing key without prompting")
def add_key(service: str | None, environment: str | None, api_key: str | None, force: bool = False) -> None:
    """
    Store a service API key securely in the macOS Keychain.
    """
    # If service not provided, prompt for it
    if not service:
        available_services = ServiceEnvironmentSelector.get_all_available_services()
        service, _ = prompt_selection("Select service:", available_services, show_descriptions=True)
    
    # Get the canonical service name from the provider (with fuzzy matching)
    try:
        service_name = ServiceEnvironmentSelector.find_service_with_fuzzy_matching(service)
    except Exception as e:
        click.echo(f"Error: {str(e)}")
        return
    
    # If environment not provided, prompt for it
    if not environment:
        environment, _ = prompt_selection("Select environment:", DEFAULT_ENVIRONMENTS, allow_new=True)
    
    # If api_key not provided, prompt for it
    if not api_key:
        api_key = click.prompt("API key", hide_input=True)
    
    # Check for existing key
    existing_key = KeyStore.get_key(service_name, environment)
    if existing_key and not force:
        click.echo(f"\nA key already exists for {service_name} ({environment})")
        action = click.prompt(
            "Choose action",
            type=click.Choice([
                'replace',
                'keep',
                'view',
                'cancel'
            ]),
            default='cancel'
        )
        
        if action == 'cancel':
            click.echo("Operation cancelled")
            return
        elif action == 'keep':
            click.echo("Keeping existing key")
            return
        elif action == 'view':
            if click.confirm("Are you sure you want to view the existing key?", default=False):
                click.echo(f"Existing key: {existing_key}")
            if not click.confirm("Do you want to replace this key?", default=False):
                click.echo("Operation cancelled")
                return
        # 'replace' continues with the operation
        
        # Backup the old key in secure storage with a timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_service = f"{service_name}_backup_{timestamp}"
        try:
            KeyStore.store_key(backup_service, environment, existing_key)
            click.echo(f"Backed up existing key to {backup_service}")
            
            # Log the backup
            audit_logger = AuditLogger()
            audit_logger.log_event(
                event_type="key_backup",
                service=service_name,
                environment=environment,
                user=os.getenv("USER", "unknown"),
                additional_data={
                    "action": "backup",
                    "reason": "key_replacement",
                    "backup_service": backup_service
                }
            )
        except Exception as e:
            click.echo(f"Warning: Failed to backup existing key: {str(e)}")
            if not click.confirm("Continue without backing up the existing key?", default=False):
                click.echo("Operation cancelled")
                return
    
    # Store the new key
    KeyStore.store_key(service_name, environment, api_key)
    
    # Add audit logging for the new key
    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="add_key",
        service=service_name,
        environment=environment,
        user=os.getenv("USER", "unknown"),
        sensitive_data=api_key,
        additional_data={
            "action": "add",
            "replaced_existing": bool(existing_key)
        }
    )
    
    click.echo(f"Key for service '{service_name}' ({environment}) stored securely.")


@cli.command()
@click.option("--service", required=False, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=False, help="Environment (dev/staging/prod)")
def remove_key(service: str | None, environment: str | None) -> None:
    """
    Remove a service API key from the macOS Keychain.
    """
    # Check if we have any keys stored
    if not KeyStore.list_keys():
        click.echo("No keys found.")
        return
    
    # If service not provided, prompt for it from services with stored keys
    if not service:
        service = ServiceEnvironmentSelector.select_service_with_keys("Select service:")
        if not service:
            click.echo("No services found with stored keys.")
            return
    else:
        # Get the canonical service name (with fuzzy matching)
        try:
            service = ServiceEnvironmentSelector.find_service_with_fuzzy_matching(service)
        except Exception as e:
            click.echo(f"Error: {str(e)}")
            return
        
        # Verify this service has stored keys
        if not ServiceEnvironmentSelector.get_environments_for_service(service):
            click.echo(f"No keys found for service '{service}'")
            return
    
    service_name = service
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        environment = ServiceEnvironmentSelector.select_environment_for_service(
            service_name, 
            allow_new=False
        )
        if not environment:
            click.echo(f"No environments found with stored keys for service {service_name}.")
            return
    else:
        # Validate the environment exists for this service
        if not ServiceEnvironmentSelector.validate_service_has_environment(service_name, environment):
            available_environments = ServiceEnvironmentSelector.get_environments_for_service(service_name)
            click.echo(f"No key found for service '{service_name}' in environment '{environment}'")
            click.echo(f"Available environments: {', '.join(available_environments)}")
            return
    
    # First check if the key exists in metadata
    metadata_exists = KeyStore.get_key_metadata(service_name, environment)
    if not metadata_exists:
        click.echo(f"No key found for service '{service_name}' in environment '{environment}'")
        return

    try:
        # Try to remove from keystore if it exists
        key_exists = KeyStore.get_key(service_name, environment)
        if key_exists:
            try:
                KeyStore.remove_key(service_name, environment)
                click.echo(f"Key for service '{service_name}' ({environment}) removed from secure storage.")
            except Exception as e:
                click.echo(f"Warning: Could not remove key from secure storage: {str(e)}")
        else:
            click.echo(f"Note: No key found in secure storage for '{service_name}' ({environment})")
        
        # Always remove the metadata
        KeyStore.remove_key_metadata(service_name, environment)
        click.echo(f"Metadata for service '{service_name}' ({environment}) removed from database.")
        
        # Add audit logging
        audit_logger = AuditLogger()
        audit_logger.log_event(
            event_type="remove_key",
            service=service_name,
            environment=environment,
            user=os.getenv("USER", "unknown"),
            additional_data={
                "action": "remove",
                "key_existed": bool(key_exists),
                "metadata_existed": True
            }
        )
    except Exception as e:
        click.echo(f"Error during removal: {str(e)}")


@cli.command()
@click.option("--service", required=False, help="Filter by service name.")
@click.option("--show-values", is_flag=True, default=False, help="Show the actual key values (use with caution).")
def list_keys(service: str | None, show_values: bool) -> None:
    """
    List stored API keys in the macOS Keychain (service names only by default).
    """
    # Get all keys with their metadata
    keys = KeyStore.list_keys(service)
    if not keys:
        click.echo("No keys found.")
        return
        
    # Group keys by service
    service_groups = defaultdict(list)
    for svc, env, updated_at, updated_by in keys:
        # Convert ISO timestamp to datetime and localize it
        dt = datetime.fromisoformat(updated_at).astimezone()
        
        # Format date based on locale
        locale.setlocale(locale.LC_TIME, '')  # Use system locale
        if locale.getlocale()[0] in ['en_US', 'en_CA']:  # US/Canada format
            date_str = dt.strftime("%m/%d/%Y %H:%M")
        else:  # Rest of world format
            date_str = dt.strftime("%d/%m/%Y %H:%M")
            
        service_groups[svc].append((env, date_str, updated_by))
    
    # Display grouped and sorted keys
    click.echo("Stored keys:")
    for service_name in sorted(service_groups.keys()):
        click.echo(f"\nService: {service_name}")
        
        # Sort environments within each service
        envs = sorted(service_groups[service_name])
        for env, date_str, updated_by in envs:
            if show_values:
                key_value = KeyStore.get_key(service_name, env)
                click.echo(f"  Environment: {env}")
                click.echo(f"    Last updated: {date_str} by {updated_by}")
                click.echo(f"    Key: {key_value}")
            else:
                click.echo(f"  Environment: {env}")
                click.echo(f"    Last updated: {date_str} by {updated_by}")
    
    if show_values:
        click.echo("\nNote: Be careful with displayed key values!")


@cli.command()
@click.option("--action", type=click.Choice(["show", "reset"]), default="show")
def config(action: str) -> None:
    """
    Manage Keymaster configuration. Supports 'show' or 'reset'.
    """
    if action == "show":
        # Show YAML configuration
        data = ConfigManager.load_config()
        click.echo("\nConfiguration from config.yaml:")
        click.echo("=" * 30)
        if data:
            for key, value in data.items():
                click.echo(f"{key}: {value}")
        else:
            click.echo("No configuration settings found.")
            
        # Show providers
        from keymaster.providers import (
            get_providers, 
            _load_generic_providers,
            GenericProvider,
            OpenAIProvider,
            AnthropicProvider,
            StabilityProvider,
            DeepSeekProvider,
            _register_provider,
            _providers
        )
        
        # Clear the provider registry to ensure a clean state
        _providers.clear()
        
        # Register built-in providers
        _register_provider(OpenAIProvider())
        _register_provider(AnthropicProvider())
        _register_provider(StabilityProvider())
        _register_provider(DeepSeekProvider())
        
        # Ensure generic providers are loaded
        _load_generic_providers()
        providers = get_providers()
        
        # Separate built-in and custom providers
        builtin_providers = {
            name: provider for name, provider in providers.items()
            if isinstance(provider, (OpenAIProvider, AnthropicProvider, StabilityProvider, DeepSeekProvider))
        }
        
        custom_providers = {
            name: provider for name, provider in providers.items()
            if isinstance(provider, GenericProvider)
        }
        
        # Show built-in providers
        click.echo("\nBuilt-in Providers:")
        click.echo("=" * 30)
        if builtin_providers:
            for name, provider in sorted(builtin_providers.items(), key=lambda x: x[1].service_name):
                click.echo(f"\nService: {provider.service_name}")
                click.echo(f"Description: {provider.description}")
                if provider.api_url:
                    click.echo(f"API URL: {provider.api_url}")
        else:
            click.echo("No built-in providers available.")
            
        # Show custom registered providers
        click.echo("\nCustom Registered Providers:")
        click.echo("=" * 30)
        if custom_providers:
            for name, provider in sorted(custom_providers.items(), key=lambda x: x[1].service_name):
                click.echo(f"\nService: {provider.service_name}")
                click.echo(f"Description: {provider.description}")
                if provider.test_url:
                    click.echo(f"Test URL: {provider.test_url}")
        else:
            click.echo("No custom providers registered.")
    elif action == "reset":
        ConfigManager.write_config({})
        click.echo("Configuration has been reset.")


@cli.command()
@click.option("--service", required=False, help="Filter by service name")
@click.option("--environment", required=False, help="Filter by environment")
@click.option("--start-date", required=False, type=click.DateTime(), help="Start date (YYYY-MM-DD)")
@click.option("--end-date", required=False, type=click.DateTime(), help="End date (YYYY-MM-DD)")
@click.option("--decrypt", is_flag=True, default=False, help="Decrypt sensitive values in logs")
def audit(service: Optional[str], 
         environment: Optional[str],
         start_date: Optional[datetime],
         end_date: Optional[datetime],
         decrypt: bool) -> None:
    """View audit logs with optional filtering."""
    audit_logger = AuditLogger()
    events = audit_logger.get_events(
        start_date=start_date,
        end_date=end_date,
        service=service,
        environment=environment,
        decrypt=decrypt
    )
    
    if not events:
        click.echo("No audit events found matching criteria.")
        return
        
    for event in events:
        # Convert ISO timestamp to local time and format it
        timestamp = datetime.fromisoformat(event['timestamp']).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        click.echo(f"[{timestamp}] {event['event_type']}")
        if 'service' in event:
            click.echo(f"  Service: {event['service']}")
        if 'environment' in event:
            click.echo(f"  Environment: {event['environment']}")
        click.echo(f"  User: {event['user']}")
        if decrypt and "decrypted_data" in event:
            click.echo(f"  Sensitive Data: {event['decrypted_data']}")
        if "metadata" in event:
            click.echo(f"  Additional Data: {event['metadata']}")
        click.echo("")


@cli.command()
@click.option("--service", required=False, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=False, help="Environment (dev/staging/prod)")
@click.option("--verbose", is_flag=True, default=False, help="Show detailed test information including API URL and response")
@click.option("--all", "test_all", is_flag=True, default=False, help="Test all stored keys")
def test_key(service: str | None, environment: str | None, verbose: bool, test_all: bool) -> None:
    """Test an API key to verify it works with the service."""
    # Get list of stored keys
    stored_keys = KeyStore.list_keys()
    if not stored_keys:
        click.echo("No keys found to test.")
        return
    
    if test_all:
        click.echo("Testing all stored keys...\n")
        results = []
        
        # Group keys by service for better organization
        service_keys = {}
        for svc, env, _, _ in stored_keys:
            if svc not in service_keys:
                service_keys[svc] = []
            service_keys[svc].append(env)
        
        # Test each key
        for svc in sorted(service_keys.keys()):
            provider = get_provider_by_name(svc)
            if not provider:
                click.echo(f"⚠️  Skipping {svc}: Provider not supported")
                continue
                
            service_name = provider.service_name
            click.echo(f"\n{service_name}:")
            
            for env in sorted(service_keys[svc]):
                key = KeyStore.get_key(service_name, env)
                if not key:
                    click.echo(f"  [{env}] ⚠️  Key not found")
                    continue
                
                try:
                    if verbose:
                        click.echo(f"  [{env}] Testing key...")
                        click.echo(f"  API Endpoint: {provider.api_url}")
                    
                    result = provider.test_key(key)
                    click.echo(f"  [{env}] ✅ Valid")
                    
                    if verbose:
                        click.echo("  Response:")
                        click.echo(f"  {result}")
                    
                    # Log success
                    audit_logger = AuditLogger()
                    audit_logger.log_event(
                        event_type="test_key",
                        service=service_name,
                        environment=env,
                        user=os.getlogin(),
                        additional_data={
                            "action": "test",
                            "result": "success",
                            "verbose": verbose,
                            "batch": True
                        }
                    )
                except Exception as e:
                    click.echo(f"  [{env}] ❌ Invalid: {str(e)}")
                    
                    # Log failure
                    audit_logger = AuditLogger()
                    audit_logger.log_event(
                        event_type="test_key",
                        service=service_name,
                        environment=env,
                        user=os.getlogin(),
                        additional_data={
                            "action": "test",
                            "result": "failed",
                            "error": str(e),
                            "verbose": verbose,
                            "batch": True
                        }
                    )
        
        click.echo("\nKey testing complete.")
        return
        
    # Single key testing logic (existing code)
    # If service not provided, prompt for it from services with stored keys
    if not service:
        service = ServiceEnvironmentSelector.select_service_with_keys("Select service with stored keys:")
        if not service:
            click.echo("No services found with stored keys.")
            return
    else:
        # Get the canonical service name (with fuzzy matching)
        try:
            service = ServiceEnvironmentSelector.find_service_with_fuzzy_matching(service)
        except Exception as e:
            click.echo(f"Error: {str(e)}")
            return
        
        # Verify this service has stored keys
        if not ServiceEnvironmentSelector.get_environments_for_service(service):
            click.echo(f"No environments found with stored keys for service {service}.")
            return
    
    service_name = service
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        environment = ServiceEnvironmentSelector.select_environment_for_service(
            service_name, 
            allow_new=False
        )
        if not environment:
            click.echo(f"No environments found with stored keys for service {service_name}.")
            return
    else:
        # Validate the environment exists for this service
        if not ServiceEnvironmentSelector.validate_service_has_environment(service_name, environment):
            available_environments = ServiceEnvironmentSelector.get_environments_for_service(service_name)
            click.echo(f"No key found for {service_name} in {environment} environment.")
            click.echo(f"Available environments: {', '.join(available_environments)}")
            return
    
    # Verify the key exists
    key = KeyStore.get_key(service_name, environment)
    if not key:
        click.echo(f"No key found for {service_name} in {environment} environment.")
        return
    
    # Get the provider for testing
    provider = get_provider_by_name(service_name)
    if not provider:
        click.echo(f"Error: Provider not found for {service_name}")
        return
    
    try:
        if verbose:
            click.echo(f"\nTesting key for {service_name} ({environment})...")
            click.echo(f"API Endpoint: {provider.api_url}")
            
        result = provider.test_key(key)
        click.echo(f"\n✅ Key test successful for {service_name} ({environment})")
        
        if verbose:
            click.echo("\nAPI Response:")
            click.echo(f"{result}")
        
        # Add audit logging for the test
        audit_logger = AuditLogger()
        audit_logger.log_event(
            event_type="test_key",
            service=service_name,
            environment=environment,
            user=os.getlogin(),
            additional_data={
                "action": "test",
                "result": "success",
                "verbose": verbose,
                "batch": False
            }
        )
    except Exception as e:
        click.echo(f"\n❌ Key test failed for {service_name} ({environment})")
        if verbose:
            click.echo(f"\nError details: {str(e)}")
        
        # Log failed test attempt
        audit_logger = AuditLogger()
        audit_logger.log_event(
            event_type="test_key",
            service=service_name,
            environment=environment,
            user=os.getlogin(),
            additional_data={
                "action": "test",
                "result": "failed",
                "error": str(e),
                "verbose": verbose,
                "batch": False
            }
        )


@cli.command()
@click.option("--service", required=False, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=False, help="Environment (dev/staging/prod)")
@click.option("--output", required=False, help="Output .env file path")
def generate_env(service: str | None, environment: str | None, output: str | None) -> None:
    """Generate a .env file for the specified service and environment."""
    from keymaster.providers import get_providers, get_provider_by_name, _load_generic_providers
    
    # Ensure generic providers are loaded
    _load_generic_providers()
    
    # Get list of stored keys
    stored_keys = KeyStore.list_keys()
    if not stored_keys:
        click.echo("No keys found.")
        return
    
    # If service not provided, prompt for it from services with stored keys
    if not service:
        service = ServiceEnvironmentSelector.select_service_with_keys("Select service with stored keys:")
        if not service:
            click.echo("No services found with stored keys.")
            return
    else:
        # Get the canonical service name (with fuzzy matching)
        try:
            service = ServiceEnvironmentSelector.find_service_with_fuzzy_matching(service)
        except Exception as e:
            click.echo(f"Error: {str(e)}")
            return
        
        # Verify this service has stored keys
        if not ServiceEnvironmentSelector.get_environments_for_service(service):
            click.echo(f"No environments found with stored keys for service {service}.")
            return
    
    service_name = service
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        environment = ServiceEnvironmentSelector.select_environment_for_service(
            service_name, 
            allow_new=False
        )
        if not environment:
            click.echo(f"No environments found with stored keys for service {service_name}.")
            return
    else:
        # Validate the environment exists for this service
        if not ServiceEnvironmentSelector.validate_service_has_environment(service_name, environment):
            available_environments = ServiceEnvironmentSelector.get_environments_for_service(service_name)
            click.echo(f"No key found for {service_name} in {environment} environment.")
            click.echo(f"Available environments: {', '.join(available_environments)}")
            return
    
    # If output not provided, prompt for it with a default
    if not output:
        default_output = ".env"
        output = click.prompt("Output file path", default=default_output)
    
    # Get the key
    key = KeyStore.get_key(service_name, environment)
    if not key:
        click.echo(f"No key found for {service_name} in {environment} environment.")
        return
    
    # Get environment variable name for the service
    env_var_name = f"{service_name.upper()}_API_KEY"
    
    try:
        EnvManager.generate_env_file(output, {env_var_name: key})
        
        # Add audit logging
        audit_logger = AuditLogger()
        audit_logger.log_event(
            event_type="generate_env",
            service=service_name,
            environment=environment,
            user=os.getlogin(),
            additional_data={
                "output_file": output,
                "env_var": env_var_name
            }
        )
        
        click.echo(f"Generated .env file at {output}")
    except Exception as e:
        click.echo(f"Failed to generate .env file: {str(e)}")


@cli.command()
@click.option("--service", required=False, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=False, help="Environment (dev/staging/prod)")
@click.option("--verbose", is_flag=True, default=False, help="Show detailed test information including API URL and response")
@click.option("--no-backup", is_flag=True, default=False, help="Skip creating backup before rotation")
@click.option("--no-test", is_flag=True, default=False, help="Skip testing new key before storage")
def rotate_key(service: str | None, environment: str | None, verbose: bool, no_backup: bool, no_test: bool) -> None:
    """Rotate an API key with enhanced backup and validation capabilities."""
    # Get list of stored keys with metadata
    stored_keys = KeyStore.list_keys()
    if not stored_keys:
        click.echo("No keys found.")
        return
    
    # If service not provided, prompt for it from services with stored keys
    if not service:
        service = ServiceEnvironmentSelector.select_service_with_keys("Select service:")
        if not service:
            click.echo("No services found with stored keys.")
            return
    else:
        # Get the canonical service name (with fuzzy matching)
        try:
            service = ServiceEnvironmentSelector.find_service_with_fuzzy_matching(service)
        except Exception as e:
            click.echo(f"Error: {str(e)}")
            return
        
        # Verify this service has stored keys
        if not ServiceEnvironmentSelector.get_environments_for_service(service):
            click.echo(f"No keys found for service '{service}'")
            return
    
    service_name = service
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        environment = ServiceEnvironmentSelector.select_environment_for_service(
            service_name, 
            allow_new=False
        )
        if not environment:
            click.echo(f"No environments found with stored keys for service {service_name}.")
            return
    else:
        # Validate the environment exists for this service
        if not ServiceEnvironmentSelector.validate_service_has_environment(service_name, environment):
            available_environments = ServiceEnvironmentSelector.get_environments_for_service(service_name)
            click.echo(f"No key found for service '{service_name}' in environment '{environment}'")
            click.echo(f"Available environments: {', '.join(available_environments)}")
            return
    
    # Get the old key
    old_key = KeyStore.get_key(service_name, environment)
    if not old_key:
        click.echo(f"Warning: No existing key found in secure storage for {service_name} in {environment} environment.")
        if not click.confirm("Do you want to continue and set a new key?", default=False):
            return
    
    # Get the new key
    new_key = click.prompt("Enter new API key", hide_input=True)
    confirm_key = click.prompt("Confirm new API key", hide_input=True)
    
    if new_key != confirm_key:
        click.echo("Keys do not match!")
        return
    
    # Use enhanced rotation system
    try:
        rotator = KeyRotator()
        
        # Determine backup password if backup is requested
        backup_password = None
        if not no_backup and old_key:
            if click.confirm("Would you like to set a custom backup password?", default=False):
                backup_password = click.prompt("Backup password", hide_input=True)
        
        # Perform enhanced rotation
        with secure_temp_string(new_key) as secure_key:
            rotation_result = rotator.rotate_key(
                service=service_name,
                environment=environment,
                new_key=secure_key.get(),
                test_key=not no_test,
                create_backup=not no_backup,
                backup_password=backup_password
            )
        
        # Display results
        click.echo(f"\n✅ Successfully rotated key for {service_name} ({environment})")
        
        if rotation_result["backup_created"]:
            click.echo(f"📁 Backup created: {rotation_result['backup_path']}")
        
        if rotation_result["key_tested"]:
            click.echo("🔍 New key validated successfully")
        
        if rotation_result["old_key_backed_up"]:
            click.echo("💾 Old key backed up in secure storage")
        
        if verbose:
            click.echo("\nRotation Details:")
            for key, value in rotation_result.items():
                if key not in ["service", "environment"]:
                    click.echo(f"  {key}: {value}")
    
    except Exception as e:
        click.echo(f"\n❌ Key rotation failed: {str(e)}")
        if click.confirm("Would you like to see rotation history for troubleshooting?", default=False):
            history = KeyRotationHistory()
            rotations = history.get_rotation_history(service_name, environment)
            if rotations:
                click.echo(f"\nRecent rotation attempts for {service_name} ({environment}):")
                for i, rotation in enumerate(rotations[-3:], 1):
                    status = "✅" if rotation["success"] else "❌"
                    click.echo(f"  {i}. {rotation['timestamp']} {status} by {rotation['user']}")
                    if rotation.get("error_message"):
                        click.echo(f"     Error: {rotation['error_message']}")
            else:
                click.echo("No rotation history found.")


@cli.command()
@click.option("--output", required=False, help="Output backup file path")
@click.option("--password", required=False, help="Encryption password (prompted if not provided)")
@click.option("--service", required=False, help="Filter by service name")
@click.option("--environment", required=False, help="Filter by environment")
@click.option("--no-audit", is_flag=True, default=False, help="Exclude audit logs from backup")
def backup(output: str | None, password: str | None, service: str | None, environment: str | None, no_audit: bool) -> None:
    """Create an encrypted backup of API keys and metadata."""
    try:
        backup_manager = BackupManager()
        
        # Determine output path
        if not output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"keymaster_backup_{timestamp}.kmbackup"
            output = click.prompt("Backup file path", default=default_name)
        
        # Get password
        if not password:
            password = click.prompt("Encryption password", hide_input=True, confirmation_prompt=True)
        
        # Create backup
        click.echo("Creating backup...")
        summary = backup_manager.create_backup(
            backup_path=output,
            password=password,
            include_audit_logs=not no_audit,
            service_filter=service,
            environment_filter=environment
        )
        
        # Display summary
        click.echo(f"\n✅ Backup created successfully: {output}")
        click.echo(f"📊 Keys backed up: {summary['keys_count']}")
        click.echo(f"🏷️  Services: {', '.join(summary['services'])}")
        click.echo(f"🌍 Environments: {', '.join(summary['environments'])}")
        click.echo(f"📝 Audit logs: {summary['audit_logs_count']}")
        click.echo(f"💾 File size: {summary['file_size']} bytes")
        
        click.echo(f"\n⚠️  Keep your encryption password safe - it cannot be recovered!")
        
    except Exception as e:
        click.echo(f"❌ Backup failed: {str(e)}")


@cli.command()
@click.option("--backup-file", required=False, help="Backup file path")
@click.option("--password", required=False, help="Decryption password (prompted if not provided)")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be restored without actually restoring")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing keys")
def restore(backup_file: str | None, password: str | None, dry_run: bool, overwrite: bool) -> None:
    """Restore API keys and metadata from an encrypted backup."""
    try:
        backup_manager = BackupManager()
        
        # Get backup file path
        if not backup_file:
            backup_file = click.prompt("Backup file path")
        
        # Get password
        if not password:
            password = click.prompt("Decryption password", hide_input=True)
        
        # Perform restore
        if dry_run:
            click.echo("Analyzing backup contents...")
            summary = backup_manager.list_backup_contents(backup_file, password)
            
            click.echo(f"\n📋 Backup Contents:")
            click.echo(f"   Total keys: {summary['total_keys']}")
            click.echo(f"   New keys: {summary['new_keys']}")
            click.echo(f"   Conflicts: {summary['conflicts']}")
            click.echo(f"   Services: {', '.join(summary['services'])}")
            click.echo(f"   Environments: {', '.join(summary['environments'])}")
            click.echo(f"   Audit logs: {summary['audit_logs_count']}")
            click.echo(f"   Created: {summary['created_at']} by {summary['created_by']}")
            
            if summary['conflicts'] > 0:
                click.echo(f"\n⚠️  Conflicting keys (already exist):")
                for service, env in summary['conflicting_keys']:
                    click.echo(f"     {service} ({env})")
                click.echo(f"\n💡 Use --overwrite to replace existing keys")
            
            if summary['new_keys'] > 0:
                click.echo(f"\n✨ New keys to be added:")
                for service, env in summary['new_keys_list']:
                    click.echo(f"     {service} ({env})")
        
        else:
            click.echo("Restoring from backup...")
            summary = backup_manager.restore_backup(
                backup_path=backup_file,
                password=password,
                overwrite_existing=overwrite
            )
            
            click.echo(f"\n✅ Restore completed!")
            click.echo(f"📥 Keys restored: {summary['restored_keys']}")
            click.echo(f"⏭️  Keys skipped: {summary['skipped_keys']}")
            
            if summary['errors']:
                click.echo(f"\n❌ Errors encountered:")
                for error in summary['errors']:
                    click.echo(f"   {error}")
        
    except Exception as e:
        click.echo(f"❌ Restore failed: {str(e)}")


@cli.command()
@click.option("--days", default=90, help="Show keys older than N days (default: 90)")
@click.option("--stats", is_flag=True, default=False, help="Show rotation statistics")
def rotation_status(days: int, stats: bool) -> None:
    """Show key rotation status and recommendations."""
    try:
        history = KeyRotationHistory()
        rotator = KeyRotator()
        
        if stats:
            # Show rotation statistics
            rotation_stats = history.get_rotation_stats()
            click.echo("📊 Key Rotation Statistics")
            click.echo("=" * 30)
            click.echo(f"Total keys tracked: {rotation_stats['total_keys_tracked']}")
            click.echo(f"Total rotations: {rotation_stats['total_rotations']}")
            click.echo(f"Successful rotations: {rotation_stats['successful_rotations']}")
            click.echo(f"Failed rotations: {rotation_stats['failed_rotations']}")
            click.echo(f"Keys never rotated: {rotation_stats['keys_never_rotated']}")
            
            if rotation_stats['newest_rotation']:
                click.echo(f"Most recent rotation: {rotation_stats['newest_rotation']}")
            if rotation_stats['oldest_key']:
                click.echo(f"Oldest tracked key: {rotation_stats['oldest_key']}")
        
        # Show rotation candidates
        candidates = rotator.list_rotation_candidates(days)
        
        if candidates:
            click.echo(f"\n🔄 Keys due for rotation (older than {days} days):")
            click.echo("=" * 50)
            
            for candidate in candidates:
                urgency_icon = "🔴" if candidate["urgency"] == "high" else "🟡" if candidate["urgency"] == "medium" else "🟢"
                click.echo(f"{urgency_icon} {candidate['service']} ({candidate['environment']})")
                click.echo(f"   Last rotation: {candidate['last_rotation']}")
                click.echo(f"   Days since: {candidate['days_since_rotation']}")
                click.echo(f"   Urgency: {candidate['urgency']}")
                click.echo()
        else:
            click.echo(f"\n✅ All keys are up to date (rotated within {days} days)")
        
    except Exception as e:
        click.echo(f"❌ Failed to get rotation status: {str(e)}")


@cli.command()
def register_provider() -> None:
    """Register a new generic API provider."""
    from keymaster.providers import GenericProvider
    
    # Get provider details
    display_name = click.prompt("Service name (e.g., OpenWeatherMap)")
    description = click.prompt("Service description")
    test_url = click.prompt("Test URL (optional, press Enter to skip)", default="", show_default=False)
    
    # Create the provider with lowercase service name
    provider = GenericProvider.create(
        service_name=display_name.lower(),  # Store as lowercase
        description=description,
        test_url=test_url if test_url else None
    )
    
    # Display using original case
    click.echo(f"\nRegistered new provider: {display_name}")
    click.echo(f"Description: {provider.description}")
    if provider.test_url:
        click.echo(f"Test URL: {provider.test_url}")
    
    # Add audit logging
    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="register_provider",
        service=display_name.lower(),  # Log with lowercase name for consistency
        environment="global",  # Provider registration is global, not environment-specific
        user=os.getenv("USER", "unknown"),
        additional_data={
            "display_name": display_name,  # Keep original case in metadata
            "description": description,
            "test_url": test_url if test_url else None
        }
    )


if __name__ == "__main__":
    cli() 