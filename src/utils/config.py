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

                # Post-process config to support available_models and selected_model
                llm_config = self._config_data.get("llm", {})
                providers = llm_config.get("providers", {})
                for provider_name, provider_cfg in providers.items():
                    if isinstance(provider_cfg, dict):
                        if "available_models" in provider_cfg and "selected_model" in provider_cfg:
                            if "model_name" not in provider_cfg:
                                try:
                                    selected_idx = provider_cfg["selected_model"]
                                    models = provider_cfg["available_models"]
                                    provider_cfg["model_name"] = models[selected_idx]
                                except (IndexError, TypeError):
                                    pass

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

    def set(self, key_path: str, value):
        keys = key_path.split('.')
        val = self._config_data
        for k in keys[:-1]:
            val = val.setdefault(k, {})
        val[keys[-1]] = value

# Global singleton
config = Config()
