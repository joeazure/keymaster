import os
import yaml
import structlog
from typing import Any, Dict

log = structlog.get_logger()

class ConfigManager:
    """
    Manages loading and writing the Keymaster configuration file.
    """

    CONFIG_FILENAME = "keymaster.yaml"

    @classmethod
    def _get_config_path(cls) -> str:
        """
        Get the path to the config file located in the user's home directory.
        """
        home_dir = os.path.expanduser("~")
        return os.path.join(home_dir, cls.CONFIG_FILENAME)

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """
        Load the config file from the user’s home directory or return an empty dictionary if not found.
        """
        path = cls._get_config_path()
        if not os.path.exists(path):
            log.info("No config file found; returning empty config.")
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                log.info("Config file loaded successfully", path=path)
                return data if data else {}
        except Exception as e:
            log.error("Failed to load config file", error=str(e))
            return {}

    @classmethod
    def write_config(cls, data: Dict[str, Any]) -> None:
        """
        Write the config data to the user’s home directory in YAML format.
        """
        path = cls._get_config_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f)
            log.info("Config file written successfully", path=path)
        except Exception as e:
            log.error("Failed to write config file", error=str(e))

    @classmethod
    def encrypt_data(cls, data: str) -> str:
        """
        Placeholder for encryption logic. In a real scenario, you can use cryptography or a similar library.
        """
        # For demonstration, we simply reverse the string. Replace with strong encryption in production.
        return data[::-1]

    @classmethod
    def decrypt_data(cls, data: str) -> str:
        """
        Placeholder for decryption logic. Mirror for the above demonstration function.
        """
        return data[::-1] 