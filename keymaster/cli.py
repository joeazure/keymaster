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
    click.echo("Initializing Keymaster...")

    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="init",
        user=os.getlogin(),
        additional_data={"action": "init"}
    )
    # Future steps might include:
    # 1. Create an initial config file (if not already present).
    # 2. Verify system requirements for macOS keychain usage, etc.


@cli.command()
def add_key() -> None:
    """
    Store a service API key securely in the macOS Keychain.
    """
    # Get available services from providers
    available_services = list(provider.service_name for provider in get_providers().values())
    service, _ = prompt_selection("Select service:", available_services)
    
    # Environment selection with option for new
    environment, is_new = prompt_selection("Select environment:", DEFAULT_ENVIRONMENTS, allow_new=True)
    
    api_key = click.prompt("API key", hide_input=True)
    
    # Get the canonical service name from the provider
    provider = get_provider_by_name(service)
    if not provider:
        click.echo(f"Unsupported service: {service}")
        return
        
    service_name = provider.service_name  # Use the canonical name
    
    KeychainSecurity.store_key(service_name, environment, api_key)
    
    # Add audit logging
    audit_logger = AuditLogger()
    audit_logger.log_event(
        event_type="add_key",
        service=service_name,
        environment=environment,
        user=os.getlogin(),
        sensitive_data=api_key,
        additional_data={"action": "add", "new_environment": is_new}
    )
    
    click.echo(f"Key for service '{service_name}' ({environment}) stored securely.")


@cli.command()
def remove_key() -> None:
    """
    Remove a service API key from the macOS Keychain.
    """
    available_services = list(provider.service_name for provider in get_providers().values())
    service, _ = prompt_selection("Select service:", available_services)
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
@click.option("--service", required=True, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=True, help="Environment (dev/staging/prod)")
def test_key(service: str, environment: str) -> None:
    """Test an API key to verify it works with the service."""
    key = KeychainSecurity.get_key(service, environment)
    if not key:
        click.echo(f"No key found for {service} in {environment} environment.")
        return
        
    # Import the appropriate provider
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
        result = provider_class.test_key(key)
        click.echo(f"Key test successful for {service} ({environment})")
        click.echo(f"Response: {result}")
    except Exception as e:
        click.echo(f"Key test failed: {str(e)}")


@cli.command()
@click.option("--service", required=True, help="Service name (e.g., OpenAI)")
@click.option("--environment", required=True, help="Environment (dev/staging/prod)")
@click.option("--output", required=True, help="Output .env file path")
def generate_env(service: str, environment: str, output: str) -> None:
    """Generate a .env file for the specified service and environment."""
    key = KeychainSecurity.get_key(service, environment)
    if not key:
        click.echo(f"No key found for {service} in {environment} environment.")
        return
        
    env_vars = {
        "OPENAI": "OPENAI_API_KEY",
        "ANTHROPIC": "ANTHROPIC_API_KEY",
        "STABILITY": "STABILITY_API_KEY"
    }
    
    if service.upper() not in env_vars:
        click.echo(f"Unsupported service: {service}")
        return
        
    env_var_name = env_vars[service.upper()]
    
    try:
        EnvManager.generate_env_file(output, {env_var_name: key})
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