"""Local JSON config storage: API key, telemetry preferences, and chat threads."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.json"
CAPTURES_DIR = PROJECT_ROOT / "captures"

DEFAULT_CONFIG = {
    "api_key": "",
    "telemetry_enabled": True,
    "onboarding_completed": False,
    "distinct_id": "",
    "threads": [],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    config["api_key"] = api_key.strip()
    save_config(config)


def is_telemetry_enabled() -> bool:
    return bool(load_config().get("telemetry_enabled", True))


def set_telemetry_enabled(enabled: bool) -> None:
    config = load_config()
    config["telemetry_enabled"] = bool(enabled)
    save_config(config)


def is_onboarding_completed() -> bool:
    return bool(load_config().get("onboarding_completed", False))


def complete_onboarding(api_key: str, telemetry_enabled: bool) -> None:
    """Atomically persist the outcome of the one-time onboarding flow."""
    config = load_config()
    config["api_key"] = api_key.strip()
    config["telemetry_enabled"] = bool(telemetry_enabled)
    config["onboarding_completed"] = True
    save_config(config)


def list_threads() -> list:
    return load_config().get("threads", [])


def get_thread(thread_id: str) -> dict | None:
    for thread in list_threads():
        if thread["id"] == thread_id:
            return thread
    return None


def create_thread(name: str | None = None) -> dict:
    config = load_config()
    threads = config.setdefault("threads", [])
    thread = {
        "id": str(uuid.uuid4()),
        "name": name or f"Chat {len(threads) + 1}",
        "created_at": _now(),
        "messages": [],
    }
    threads.append(thread)
    save_config(config)
    return thread


def add_message(thread_id: str, role: str, text: str, images: list[str] | None = None) -> dict:
    config = load_config()
    for thread in config.setdefault("threads", []):
        if thread["id"] == thread_id:
            message = {"role": role, "text": text, "images": images or [], "timestamp": _now()}
            thread["messages"].append(message)
            save_config(config)
            return message
    raise KeyError(f"No chat thread with id {thread_id!r}")


def rename_thread(thread_id: str, new_name: str) -> None:
    new_name = new_name.strip()
    if not new_name:
        return
    config = load_config()
    for thread in config.get("threads", []):
        if thread["id"] == thread_id:
            thread["name"] = new_name
            save_config(config)
            return
    raise KeyError(f"No chat thread with id {thread_id!r}")


def ensure_captures_dir() -> Path:
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    return CAPTURES_DIR
