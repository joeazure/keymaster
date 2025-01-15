import os
import yaml
import structlog
from typing import Any, Dict

log = structlog.get_logger()

class ConfigManager:
    """
    Manages loading and writing the Keymaster configuration file.
    """

    CONFIG_FILENAME = "config.yaml"

    @classmethod
    def _get_config_path(cls) -> str:
        """
        Get the path to the config file located in the .keymaster directory.
        """
        home_dir = os.path.expanduser("~")
        config_dir = os.path.join(home_dir, ".keymaster")
        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, cls.CONFIG_FILENAME)

    @classmethod
    def config_exists(cls) -> bool:
        """
        Check if the config file exists.
        
        Returns:
            bool: True if the config file exists, False otherwise.
        """
        path = cls._get_config_path()
        return os.path.exists(path)

    @classmethod
    def load_config(cls) -> Dict[str, Any]:
        """
        Load the config file from the .keymaster directory or return an empty dictionary if not found.
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
        Write the config data to the .keymaster directory in YAML format.
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
        return data[::-1]

    @classmethod
    def decrypt_data(cls, data: str) -> str:
        """
        Placeholder for decryption logic. Mirror for the above demonstration function.
        """
        return data[::-1]

    @classmethod
    def config_exists(cls) -> bool:
        """
        Check if the config file exists.
        
        Returns:
            bool: True if the config file exists, False otherwise.
        """
        path = cls._get_config_path()
        return os.path.exists(path) 