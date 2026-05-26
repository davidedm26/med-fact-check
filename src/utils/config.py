import json
from pathlib import Path

from utils.logger import get_logger

log = get_logger("ConfigManager")

class Config:
    _instance = None
    _config_data = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        # Look for the config.json file at the project root
        # src/utils/config.py -> the root is 2 levels up
        root_dir = Path(__file__).resolve().parent.parent.parent
        config_path = root_dir / "config.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config_data = json.load(f)
                log.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                log.error(f"Error reading config.json: {e}")
        else:
            log.warning(f"Configuration file not found at {config_path}. Using hardcoded defaults.")

    def get(self, key_path: str, default=None):
        """
        Retrieves a value using dot notation. Example: config.get('llm.temperature', 0.2)
        """
        keys = key_path.split('.')
        val = self._config_data
        try:
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            return default

# Global singleton
config = Config()
