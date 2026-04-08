import os
import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "version": 1,
    "project": "py-wikisage-project",
    "sources": {"path": "raw"},
    "output": "wiki",
    "llm": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
}


def create_default_config(path: Path) -> bool:
    """
    Creates a default config.yaml at the given path.
    Returns True if created, False if it already existed.
    """
    config_file = path / "config.yaml"
    if config_file.exists():
        return False

    with open(config_file, "w") as f:
        yaml.dump(DEFAULT_CONFIG, f, sort_keys=False)

    return True


def load_config(path: Path = Path(".")) -> dict:
    config_file = path / "config.yaml"
    if not config_file.exists():
        return DEFAULT_CONFIG

    with open(config_file, "r") as f:
        return yaml.safe_load(f)
