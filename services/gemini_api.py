"""Google GenAI SDK interface: image + text prompt handler for Gemini."""

from PIL import Image
from google import genai

from services.storage import get_api_key

DEFAULT_MODEL = "gemini-2.5-flash"


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

    def send_prompt(self, image: Image.Image, prompt: str) -> str:
        """Send a screen crop + text prompt to Gemini and return the reply text."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=[prompt, image],
        )
        return response.text


if __name__ == "__main__":
    # Quick manual smoke test: requires a configured API key.
    service = GeminiService()
    try:
        blank = Image.new("RGB", (64, 64), color="white")
        print(service.send_prompt(blank, "Describe this image in one sentence."))
    except RuntimeError as exc:
        print(f"Skipped live test: {exc}")
