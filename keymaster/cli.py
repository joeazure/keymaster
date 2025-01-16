import click
from keymaster.security import KeychainSecurity
from keymaster.config import ConfigManager
from datetime import datetime
import os
from typing import Optional
from keymaster.audit import AuditLogger
from keymaster.env import EnvManager
from keymaster.utils import prompt_selection
from keymaster.providers import get_providers, get_provider_by_name
import sys

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
    
    # 2. Verify system requirements
    if sys.platform != "darwin":
        click.echo("Warning: Keymaster is designed for macOS. Some features may not work on other platforms.")
    
    try:
        # Test keychain access
        test_service = "__keymaster_test__"
        test_env = "__test__"
        test_value = "test_value"
        
        KeychainSecurity.store_key(test_service, test_env, test_value)
        retrieved = KeychainSecurity.get_key(test_service, test_env)
        KeychainSecurity.remove_key(test_service, test_env)
        
        if retrieved != test_value:
            click.echo("Warning: Keychain access test failed. Key storage may not work correctly.")
        else:
            click.echo("Verified keychain access.")
    except Exception as e:
        click.echo(f"Warning: Could not verify keychain access: {str(e)}")
    
    # Log initialization
    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="init",
        user=os.getlogin(),
        additional_data={
            "action": "init",
            "platform": sys.platform,
            "keychain_test": "success" if retrieved == test_value else "failed"
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
    existing_key = KeychainSecurity.get_key(service_name, environment)
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
        
        # Backup the old key
        audit_logger = AuditLogger()
        audit_logger.log_event(
            event_type="key_backup",
            service=service_name,
            environment=environment,
            user=os.getlogin(),
            sensitive_data=existing_key,
            additional_data={
                "action": "backup",
                "reason": "key_replacement"
            }
        )
    
    # Store the new key
    KeychainSecurity.store_key(service_name, environment, api_key)
    
    # Add audit logging for the new key
    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="add_key",
        service=service_name,
        environment=environment,
        user=os.getlogin(),
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
    # If service not provided, prompt for it
    if not service:
        available_services = list(provider.service_name for provider in get_providers().values())
        service, _ = prompt_selection("Select service:", available_services, show_descriptions=True)
    
    # If environment not provided, prompt for it
    if not environment:
        environment, _ = prompt_selection("Select environment:", DEFAULT_ENVIRONMENTS, allow_new=True)
    
    provider = get_provider_by_name(service)
    if not provider:
        click.echo(f"Unsupported service: {service}")
        return
        
    service_name = provider.service_name
    
    # First check if the key exists
    existing_key = KeychainSecurity.get_key(service_name, environment)
    if not existing_key:
        click.echo(f"No key found for service '{service_name}' in environment '{environment}'")
        return

    try:
        KeychainSecurity.remove_key(service_name, environment)
        
        # Add audit logging
        audit_logger = AuditLogger()
        audit_logger.log_event(
            event_type="remove_key",
            service=service_name,
            environment=environment,
            user=os.getlogin(),
            additional_data={"action": "remove"}
        )
        
        click.echo(f"Key for service '{service_name}' ({environment}) removed from Keychain.")
    except Exception as e:
        click.echo(f"Error removing key: {str(e)}")


@cli.command()
@click.option("--service", required=False, help="Filter by service name.")
@click.option("--show-values", is_flag=True, default=False, help="Show the actual key values (use with caution).")
def list_keys(service: str | None, show_values: bool) -> None:
    """
    List stored API keys in the macOS Keychain (service names only by default).
    """
    keys = KeychainSecurity.list_keys(service)
    if not keys:
        click.echo("No keys found.")
    else:
        click.echo("Stored keys:")
        for svc, env in keys:
            if show_values:
                key_value = KeychainSecurity.get_key(svc, env)
                click.echo(f" - Service: {svc}, Environment: {env}")
                click.echo(f"   Key: {key_value}")
            else:
                click.echo(f" - Service: {svc}, Environment: {env}")


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
def test_key(service: str | None, environment: str | None, verbose: bool) -> None:
    """Test an API key to verify it works with the service."""
    # Get list of stored keys
    stored_keys = KeychainSecurity.list_keys()
    if not stored_keys:
        click.echo("No keys found to test.")
        return
        
    # Get unique services that have stored keys and map to canonical names
    stored_service_names = set(service.lower() for service, _ in stored_keys)
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
    available_environments = sorted(set(
        env for svc, env in stored_keys 
        if svc.lower() == service_name.lower()
    ))
    
    # If environment not provided, prompt for it from available environments
    if not environment:
        if len(available_environments) == 0:
            click.echo(f"No environments found with stored keys for service {service_name}.")
            return
            
        environment, _ = prompt_selection(
            f"Select environment for {service_name}:", 
            available_environments,
            allow_new=False  # Don't allow new environments since we're testing existing keys
        )
    
    # Verify the key exists
    key = KeychainSecurity.get_key(service_name, environment)
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
                "verbose": verbose
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
                "verbose": verbose
            }
        )


@cli.command()
@click.option("--service", required=False, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=False, help="Environment (dev/staging/prod)")
@click.option("--output", required=False, help="Output .env file path")
def generate_env(service: str | None, environment: str | None, output: str | None) -> None:
    """Generate a .env file for the specified service and environment."""
    # If service not provided, prompt for it
    if not service:
        available_services = list(provider.service_name for provider in get_providers().values())
        service, _ = prompt_selection("Select service:", available_services, show_descriptions=True)
    
    # If environment not provided, prompt for it
    if not environment:
        environment, _ = prompt_selection("Select environment:", DEFAULT_ENVIRONMENTS, allow_new=True)
    
    # If output not provided, prompt for it with a default
    if not output:
        default_output = ".env"
        output = click.prompt("Output file path", default=default_output)
    
    # Get the canonical service name
    provider = get_provider_by_name(service)
    if not provider:
        click.echo(f"Unsupported service: {service}")
        return
        
    service_name = provider.service_name  # Use the canonical name
    
    # Get the key
    key = KeychainSecurity.get_key(service_name, environment)
    if not key:
        click.echo(f"No key found for {service_name} in {environment} environment.")
        return
        
    env_vars = {
        "OPENAI": "OPENAI_API_KEY",
        "ANTHROPIC": "ANTHROPIC_API_KEY",
        "STABILITY": "STABILITY_API_KEY",
        "DEEPSEEK": "DEEPSEEK_API_KEY"
    }
    
    if service_name.upper() not in env_vars:
        click.echo(f"Unsupported service: {service_name}")
        return
        
    env_var_name = env_vars[service_name.upper()]
    
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
@click.option("--service", required=True, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=True, help="Environment (dev/staging/prod)")
def rotate_key(service: str, environment: str) -> None:
    """Rotate an API key (requires manual input of new key)."""
    old_key = KeychainSecurity.get_key(service, environment)
    if not old_key:
        click.echo(f"No existing key found for {service} in {environment} environment.")
        return
        
    new_key = click.prompt("Enter new API key", hide_input=True)
    confirm_key = click.prompt("Confirm new API key", hide_input=True)
    
    if new_key != confirm_key:
        click.echo("Keys do not match!")
        return
        
    # Test the new key before replacing the old one
    provider_map = {
        "openai": "OpenAIProvider",
        "anthropic": "AnthropicProvider",
        "stability": "StabilityProvider"
    }
    
    if service.lower() not in provider_map:
        click.echo(f"Unsupported service: {service}")
        return
        
    provider_name = provider_map[service.lower()]
    provider_module = __import__(f"keymaster.providers", fromlist=[provider_name])
    provider_class = getattr(provider_module, provider_name)
    
    try:
        provider_class.test_key(new_key)
    except Exception as e:
        click.echo(f"New key validation failed: {str(e)}")
        return
        
    # Store the new key
    KeychainSecurity.store_key(service, environment, new_key)
    
    # Log the rotation
    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="key_rotation",
        service=service,
        environment=environment,
        user=os.getlogin(),
        additional_data={"rotation_successful": True}
    )
    
    click.echo(f"Successfully rotated key for {service} ({environment})")


if __name__ == "__main__":
    cli() 