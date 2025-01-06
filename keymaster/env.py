import os
import structlog
from typing import Dict, Optional
from dotenv import load_dotenv

log = structlog.get_logger()

class EnvManager:
    """
    Manages environment variables for Keymaster usage.
    """

    @staticmethod
    def load_env_file(filepath: str) -> None:
        """
        Load environment variables from a .env file.
        :param filepath: Path to the .env file.
        """
        load_dotenv(dotenv_path=filepath)
        log.info("Environment variables loaded from file", filepath=filepath)

    @staticmethod
    def get_variable(key: str) -> Optional[str]:
        """
        Retrieve a single environment variable from the current environment.
        :param key: Environment variable name.
        :return: The value of the environment variable or None if not found.
        """
        value = os.getenv(key, None)
        if value is None:
            log.warning("Environment variable not found", key=key)
        else:
            log.info("Retrieved environment variable", key=key, value="***")
        return value

    @staticmethod
    def set_variable(key: str, value: str) -> None:
        """
        Set an environment variable in the current process environment.
        :param key: Environment variable name.
        :param value: Value to set for the environment variable.
        """
        os.environ[key] = value
        log.info("Set environment variable", key=key, value="***")

    @staticmethod
    def list_variables(prefix_filter: str = "") -> Dict[str, str]:
        """
        List all environment variables, optionally filtered by a prefix.
        :param prefix_filter: If provided, only return env vars starting with this prefix.
        :return: A dict of environment variable key-value pairs.
        """
        env_vars = {}
        for k, v in os.environ.items():
            if prefix_filter and not k.startswith(prefix_filter):
                continue
            env_vars[k] = v
        log.info("Listed environment variables", count=len(env_vars))
        return env_vars 