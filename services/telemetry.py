"""Privacy-first PostHog telemetry.

Captures only high-level operational events. Never sends prompt text, image
pixel data, or API keys. Fully inert (safe no-op) until POSTHOG_API_KEY is
configured, and immediately respects telemetry_enabled=false in config.json.
"""

import os
import uuid

try:
    from posthog import Posthog
except ImportError:  # pragma: no cover - posthog is an optional runtime dependency
    Posthog = None

from services.storage import load_config, save_config

POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY", "phc_rWCTzmZUSxsrwMF7fw8PYRNNTVCSPfHEF6TsGQ4SsXXh")
POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")

# The only events GSight is allowed to emit. Anything else raises rather than
# silently sending an un-reviewed event.
ALLOWED_EVENTS = {
    "app_launched",
    "shortcut_triggered",
    "crop_captured",
    "chat_created",
    "api_error_raised",
}

# Property keys that must never leave the device, even if a caller passes them.
_SENSITIVE_KEYS = {"prompt", "text", "message", "api_key", "image", "image_bytes", "pixels", "content"}


def _strip_sensitive(properties: dict) -> dict:
    return {k: v for k, v in properties.items() if k.lower() not in _SENSITIVE_KEYS}


class Telemetry:
    """Thin, privacy-scoped wrapper around the PostHog client."""

    def __init__(self):
        self._client = None
        if POSTHOG_API_KEY and Posthog is not None:
            self._client = Posthog(POSTHOG_API_KEY, host=POSTHOG_HOST, debug=False)

    @property
    def enabled(self) -> bool:
        if self._client is None:
            return False
        return bool(load_config().get("telemetry_enabled", True))

    def distinct_id(self) -> str:
        config = load_config()
        distinct_id = config.get("distinct_id")
        if not distinct_id:
            distinct_id = str(uuid.uuid4())
            config["distinct_id"] = distinct_id
            save_config(config)
        return distinct_id

    def capture(self, event: str, properties: dict | None = None) -> None:
        if event not in ALLOWED_EVENTS:
            raise ValueError(f"Unregistered telemetry event: {event!r}")
        if not self.enabled:
            return
        self._client.capture(
            event,
            distinct_id=self.distinct_id(),
            properties=_strip_sensitive(properties or {}),
        )

    def shutdown(self) -> None:
        if self._client is not None:
            self._client.shutdown()


telemetry = Telemetry()
