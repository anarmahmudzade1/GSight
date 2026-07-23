"""Local JSON chat history and API key configuration storage."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
CAPTURES_DIR = PROJECT_ROOT / "captures"

DEFAULT_CONFIG = {
    "api_key": "",
    "chat_history": [],
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)
    return {**DEFAULT_CONFIG, **data}


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def get_api_key() -> str:
    return load_config().get("api_key", "")


def set_api_key(api_key: str) -> None:
    config = load_config()
    config["api_key"] = api_key
    save_config(config)


def load_chat_history() -> list:
    return load_config().get("chat_history", [])


def save_chat_history(history: list) -> None:
    config = load_config()
    config["chat_history"] = history
    save_config(config)


def append_chat_message(role: str, text: str) -> None:
    history = load_chat_history()
    history.append({"role": role, "text": text})
    save_chat_history(history)


def ensure_captures_dir() -> Path:
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    return CAPTURES_DIR
