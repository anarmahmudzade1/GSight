# GSight

Translucent desktop AI vision utility powered by Gemini, for developers and power users.

GSight sits in your system tray. Summon it with a global hotkey, crop any part of your
screen, and ask Gemini about it in a floating glassmorphism chat window — no alt-tabbing,
no uploading files by hand.

## Features

- **Two hotkeys, two modes** — `Ctrl+Shift+A` opens the floating chat directly; `Ctrl+Shift+S`
  jumps straight into the drag-to-crop snipper.
- **Multi-thread chat history**, stored locally in `config.json`.
- **Streaming Gemini replies** with Markdown rendering and syntax-highlighted code blocks.
- **Glassmorphism UI** — translucent, frameless, resizable chat window.

## Getting Started

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python assets\generate_icon.py   # generates assets/icon.png + icon.ico
python main.py                   # first run prompts for a Gemini API key
```

On first launch, GSight blocks all features behind a one-time API key setup dialog that
links to [Google AI Studio](https://aistudio.google.com/apikey) and validates the key
before letting you in.

### Optional: desktop shortcuts

```
pip install pywin32
python scripts\create_shortcuts.py
```

This writes two shortcuts to your Desktop — "GSight - Main Chat" and
"GSight - Quick Screen Capture" — each launching `main.py` with the matching `--mode` flag.
Nothing is created automatically; this is an explicit, user-run step.

## Privacy & Data Collection

GSight ships with privacy-scoped usage telemetry via [PostHog](https://posthog.com), enabled
by default.

- **Enabled by default**: the shipped build includes a PostHog project key, so telemetry is
  active out of the box. Set `telemetry_enabled: false` in `config.json` to disable it, or
  override `POSTHOG_API_KEY` / `POSTHOG_HOST` via environment variables to point at a
  different project.
- **Anonymous identity only**: a random `uuid4`, generated locally and stored as
  `distinct_id` in `config.json`. It is never derived from hardware, your name, or your
  email, and is not linked to any other account.
- **Never collected, under any configuration**: prompt text, screenshot/image pixel data,
  Gemini responses, or your Gemini API key. `services/telemetry.py` also strips any
  property whose key looks sensitive as a defense-in-depth safeguard.

### Exact event schema

| Event | Properties sent | When it fires |
|---|---|---|
| `app_launched` | `mode` (`"chat"` or `"capture"`) | Every process start |
| `shortcut_triggered` | `mode` (`"chat"` or `"capture"`) | A global hotkey or tray menu action fires |
| `crop_captured` | *(none)* | A drag-to-crop selection completes |
| `chat_created` | *(none)* | A new chat thread is created |
| `api_error_raised` | `stage` (e.g. `"stream"`) | A Gemini request fails |

That is the complete list — `services/telemetry.py` raises an error rather than sending
any event not in this table.

## Project Layout

See `CLAUDE.md` for the full architecture reference (directory layout, config.json schema,
hotkey wiring, and visual design system).
