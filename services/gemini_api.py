"""Google GenAI SDK interface: image + text prompt handler for Gemini."""

import re

from PIL import Image
from google import genai

from services.storage import get_api_key

DEFAULT_MODEL = "gemini-3.6-flash"

SYSTEM_INSTRUCTION = (
    "You are an expert AI assistant. Provide direct, natural, and concise responses. "
    "When asked for steps or instructions, omit conversational preamble and present the "
    "steps immediately in a clean format: Step 1: ..., Step 2: ..., etc."
)

# Supports both classic Gemini/AI Studio keys ("AIzaSy" + 33 URL-safe chars, 39
# total) and the newer "AQ." Auth-token-style keys AI Studio has started issuing.
# This is a format sanity check only — it does not guarantee the key is active
# or scoped for the Gemini API.
API_KEY_FORMAT = re.compile(r"^(AIzaSy[A-Za-z0-9_-]{33}|AQ\.[A-Za-z0-9_\.-]{30,80})$")


def clean_api_key(api_key: str) -> str:
    """Strip ALL whitespace (leading, trailing, and embedded) - real keys never contain
    any, but copy-pasting can smuggle in spaces, tabs, or a stray newline."""
    return re.sub(r"\s+", "", api_key or "")


def is_valid_key_format(api_key: str) -> bool:
    return bool(API_KEY_FORMAT.match(clean_api_key(api_key)))


def validate_api_key_live(api_key: str) -> tuple[bool, str]:
    """Confirm the key actually authenticates by listing models (cheap - no generation cost).

    Blocking - call off the UI thread.
    """
    clean_key = clean_api_key(api_key)
    if not clean_key:
        return False, "API key is empty."
    if not is_valid_key_format(clean_key):
        return False, "Key does not match the expected 'AIzaSy...' or 'AQ....' format."
    try:
        client = genai.Client(api_key=clean_key)
        # Pulling the first model forces the auth round-trip immediately and
        # confirms the key is actually active on Google's backend.
        next(iter(client.models.list()))
    except Exception as exc:  # noqa: BLE001 - surfacing any SDK/network failure to the user
        return False, str(exc)
    return True, ""


class GeminiService:
    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if self._client is None:
            api_key = get_api_key()
            if not api_key:
                raise RuntimeError("No Gemini API key configured. Set one via services.storage.set_api_key().")
            self._client = genai.Client(api_key=api_key)
        return self._client

    def send_prompt(self, images: list[Image.Image], prompt: str) -> str:
        """Send up to 5 screen crops + a text prompt to Gemini and return the reply text."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt, *images],
            config={"system_instruction": SYSTEM_INSTRUCTION},
        )
        return response.text

    def send_prompt_stream(self, images: list[Image.Image], prompt: str):
        """Yield response text chunks as they stream in from Gemini, images (0-5) + text."""
        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=[prompt, *images],
            config={"system_instruction": SYSTEM_INSTRUCTION},
        ):
            if chunk.text:
                yield chunk.text

    def send_text_stream(self, prompt: str):
        """Yield response text chunks for a text-only follow-up (no new attachment)."""
        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=[prompt],
            config={"system_instruction": SYSTEM_INSTRUCTION},
        ):
            if chunk.text:
                yield chunk.text

    def generate_title(self, first_message: str) -> str:
        """Summarize a thread's opening message into a concise 3-5 word title."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                "Summarize the following chat message into a concise 3-5 word title. "
                "No punctuation at the end, no quotes, title case, just the words:\n\n"
                f"{first_message}"
            ],
        )
        return response.text.strip().strip('"').strip()


if __name__ == "__main__":
    # Quick manual smoke test: requires a configured API key.
    service = GeminiService()
    try:
        blank = Image.new("RGB", (64, 64), color="white")
        print(service.send_prompt([blank], "Describe this image in one sentence."))
    except RuntimeError as exc:
        print(f"Skipped live test: {exc}")
