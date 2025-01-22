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
    # Check if already initialized by looking for config and directories
    config_manager = ConfigManager()
    is_initialized = (
        config_manager.config_exists() and
        os.path.exists(os.path.expanduser("~/.keymaster/logs")) and
        os.path.exists(os.path.expanduser("~/.keymaster/db"))
    )
    
    if is_initialized:
        click.echo("Keymaster is already initialized and ready to use.")
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
        click.echo("Created initial configuration file.")
    
    # Create necessary directories
    dirs_to_create = [
        os.path.expanduser("~/.keymaster/logs"),
        os.path.expanduser("~/.keymaster/db")
    ]
    
    for directory in dirs_to_create:
        if not os.path.exists(directory):
            os.makedirs(directory, mode=0o700)  # Secure permissions
            click.echo(f"Created directory: {directory}")
    
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
            "storage_test": "success" if retrieved == test_value else "failed"
        }
    )
    
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
        available_services = list(provider.service_name for provider in get_providers().values())
        service, _ = prompt_selection("Select service:", available_services, show_descriptions=True)
    
    # If environment not provided, prompt for it
    if not environment:
        environment, _ = prompt_selection("Select environment:", DEFAULT_ENVIRONMENTS, allow_new=True)
    
    # If api_key not provided, prompt for it
    if not api_key:
        api_key = click.prompt("API key", hide_input=True)
    
    # Get the canonical service name from the provider
    provider = get_provider_by_name(service)
    if not provider:
        click.echo(f"Unsupported service: {service}")
        return
        
    service_name = provider.service_name  # Use the canonical name
    
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
    # Get list of stored keys with metadata
    stored_keys = KeyStore.list_keys()
    if not stored_keys:
        click.echo("No keys found.")
        return
    
    # If service not provided, prompt for it
    if not service:
        # Get unique services that have stored keys
        available_services = {
            provider.service_name 
            for provider in get_providers().values()
            if any(svc.lower() == provider.service_name.lower() for svc, _, _, _ in stored_keys)
        }
        if not available_services:
            click.echo("No services found with stored keys.")
            return
            
        service, _ = prompt_selection(
            "Select service:", 
            sorted(available_services), 
            show_descriptions=True
        )
    
    # Get the canonical service name
    provider = get_provider_by_name(service)
    if not provider:
        click.echo(f"Unsupported service: {service}")
        return
        
    service_name = provider.service_name
    
    # Get environments that have metadata entries for this service
    available_environments = sorted(set(
        env for svc, env, _, _ in stored_keys 
        if svc.lower() == service_name.lower()
    ))
    
    if not available_environments:
        click.echo(f"No keys found for service '{service_name}'")
        return
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        environment, _ = prompt_selection(
            f"Select environment for {service_name}:", 
            available_environments,
            allow_new=False  # Don't allow new environments since we're removing existing keys
        )
    elif environment not in available_environments:
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
        data = ConfigManager.load_config()
        click.echo("Current configuration:")
        click.echo(str(data))
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
    # Get unique services that have stored keys and map to canonical names
    stored_service_names = set(service.lower() for service, _, _, _ in stored_keys)
    available_providers = {
        name: provider 
        for name, provider in get_providers().items()
        if name in stored_service_names
    }
    
    if not available_providers:
        click.echo("No services found with stored keys.")
        return
    
    # If service not provided, prompt for it from available services
    if not service:
        service_options = [provider.service_name for provider in available_providers.values()]
        service, _ = prompt_selection(
            "Select service with stored keys:", 
            service_options,
            show_descriptions=True
        )
    
    # Get available environments for the selected service
    provider = get_provider_by_name(service)
    if not provider:
        click.echo(f"Unsupported service: {service}")
        return
        
    service_name = provider.service_name  # Use the canonical name
    
    # Get environments that actually have stored keys for this service
    available_environments = sorted(set(
        env for svc, env, _, _ in stored_keys 
        if svc.lower() == service_name.lower()
    ))
    
    if len(available_environments) == 0:
        click.echo(f"No environments found with stored keys for service {service_name}.")
        return
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        environment, _ = prompt_selection(
            f"Select environment for {service_name}:", 
            available_environments,
            allow_new=False  # Don't allow new environments since we're testing existing keys
        )
    elif environment not in available_environments:
        click.echo(f"No key found for {service_name} in {environment} environment.")
        click.echo(f"Available environments: {', '.join(available_environments)}")
        return
    
    # Verify the key exists
    key = KeyStore.get_key(service_name, environment)
    if not key:
        click.echo(f"No key found for {service_name} in {environment} environment.")
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
    
    # Get unique services that have stored keys and map to canonical names
    stored_service_names = set(service.lower() for service, _, _, _ in stored_keys)
    available_providers = {
        name: provider 
        for name, provider in get_providers().items()
        if name in stored_service_names
    }
    
    if not available_providers:
        click.echo("No services found with stored keys.")
        return
    
    # If service not provided, prompt for it from available services
    if not service:
        service_options = [provider.service_name for provider in available_providers.values()]
        service, _ = prompt_selection(
            "Select service with stored keys:", 
            service_options,
            show_descriptions=True
        )
    
    # Get available environments for the selected service
    provider = get_provider_by_name(service)
    if not provider:
        click.echo(f"Unsupported service: {service}")
        return
        
    service_name = provider.service_name  # Use the canonical name
    
    # Get environments that actually have stored keys for this service
    available_environments = sorted(set(
        env for svc, env, _, _ in stored_keys 
        if svc.lower() == service_name.lower()
    ))
    
    if len(available_environments) == 0:
        click.echo(f"No environments found with stored keys for service {service_name}.")
        return
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        environment, _ = prompt_selection(
            f"Select environment for {service_name}:", 
            available_environments,
            allow_new=False  # Don't allow new environments since we're using existing keys
        )
    elif environment not in available_environments:
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
@click.option("--all", "test_all", is_flag=True, default=False, help="Test all stored keys")
def rotate_key(service: str | None, environment: str | None, verbose: bool, test_all: bool) -> None:
    """Rotate an API key (requires manual input of new key)."""
    # Get list of stored keys with metadata
    stored_keys = KeyStore.list_keys()
    if not stored_keys:
        click.echo("No keys found.")
        return
    
    # If service not provided, prompt for it
    if not service:
        # Get unique services that have stored keys
        available_services = {
            provider.service_name 
            for provider in get_providers().values()
            if any(svc.lower() == provider.service_name.lower() for svc, _, _, _ in stored_keys)
        }
        if not available_services:
            click.echo("No services found with stored keys.")
            return
            
        service, _ = prompt_selection(
            "Select service:", 
            sorted(available_services), 
            show_descriptions=True
        )
    
    # Get the canonical service name
    provider = get_provider_by_name(service)
    if not provider:
        click.echo(f"Unsupported service: {service}")
        return
        
    service_name = provider.service_name
    
    # Get environments that have metadata entries for this service
    available_environments = sorted(set(
        env for svc, env, _, _ in stored_keys 
        if svc.lower() == service_name.lower()
    ))
    
    if not available_environments:
        click.echo(f"No keys found for service '{service_name}'")
        return
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        environment, _ = prompt_selection(
            f"Select environment for {service_name}:", 
            available_environments,
            allow_new=False  # Don't allow new environments since we're rotating existing keys
        )
    elif environment not in available_environments:
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
    
    # Test the new key before storing it
    try:
        if verbose := click.confirm("Would you like to see the test results?", default=False):
            click.echo(f"\nTesting new key for {service_name} ({environment})...")
            click.echo(f"API Endpoint: {provider.api_url}")
            
        result = provider.test_key(new_key)
        
        if verbose:
            click.echo("\nAPI Response:")
            click.echo(f"{result}")
            
        click.echo(f"\n✅ New key validation successful for {service_name}")
    except Exception as e:
        click.echo(f"\n❌ New key validation failed: {str(e)}")
        if not click.confirm("Do you want to store the key anyway?", default=False):
            return
    
    # Store the new key
    KeyStore.store_key(service_name, environment, new_key)
    
    # Log the rotation
    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="key_rotation",
        service=service_name,
        environment=environment,
        user=os.getenv("USER", "unknown"),
        additional_data={
            "action": "rotate",
            "old_key_existed": bool(old_key),
            "validation_succeeded": True
        }
    )
    
    click.echo(f"\nSuccessfully rotated key for {service_name} ({environment})")


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