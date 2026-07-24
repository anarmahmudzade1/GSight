# GSight - Technical Architecture & Developer Context

## 1. Project Overview & Positioning
- **Name:** GSight (`gsight`)
- **Tagline:** Translucent desktop AI vision utility powered by Gemini for developers and power users.
- **Repository Location:** `D:\DevProjects\GSight`
- **Core Functionality:** Lightweight Windows background application summoned via global hotkeys. Captures custom screen crops, processes visual context via Google's Gemini multimodal models, and maintains local, multi-thread chat history.
- **Key Target:** Minimalist developer tool designed for GitHub showcase and resume highlighting (Clean PyQt6 UI, native OS integration, low memory footprint).

---

## 2. Environment & System Requirements
- **OS Target:** Windows 10 / 11 (64-bit mandatory)
- **Runtime Environment:** Python 3.13 (64-bit) located in project-isolated `venv`
- **Virtual Environment Path:** `D:\DevProjects\GSight\venv`
- **Activation Command:** `venv\Scripts\activate`

### Installed Dependencies & Version Constraints
- **GUI Engine:** `PyQt6` (64-bit binary wheels only — *no source compilation or qmake dependencies*)
- **AI SDK:** `google-genai` (Gemini 2.5 Flash multimodal + streaming endpoints)
- **Image Processing:** `Pillow` (JPEG / PNG crop manipulation, downscaling, and icon generation)
- **Input & Hotkeys:** `pynput` (Global keyboard listener for system-wide shortcuts)
- **Networking:** `requests` (GitHub Releases API checks)
- **Telemetry:** `posthog` (privacy-scoped, anonymous, disabled unless a project key is configured — see §6)
- **Optional (shortcut creation only):** `pywin32` — only needed to run `scripts/create_shortcuts.py`, not a runtime dependency of the app.

Install everything with `pip install -r requirements.txt`.

---

## 3. Directory & File Structure
```text
D:\DevProjects\GSight\
├── main.py                    # Entry point, tray icon lifecycle, dual-mode hotkey routing
├── CLAUDE.md                  # Claude CLI developer context & architectural rules
├── README.md                  # Public-facing overview + Privacy & Data Collection section
├── requirements.txt           # pip dependencies
├── .gitignore                 # Ignores venv/, __pycache__/, .env, captures/, config.json
├── assets/
│   ├── generate_icon.py       # Programmatically draws the two-'G' logo
│   ├── icon.png                # Generated app/tray icon (Gemini Electric Blue)
│   └── icon.ico                 # Generated multi-size Windows icon (taskbar/shortcuts)
├── scripts/
│   └── create_shortcuts.py    # Optional: writes the two .lnk desktop shortcuts (run manually)
├── ui/
│   ├── __init__.py
│   ├── window.py               # Translucent glassmorphism chat window (frameless, resizable)
│   ├── snipper.py              # Full-screen translucent drag-to-crop snippet widget
│   ├── chat_bubble.py          # iMessage-style user bubbles / Gemini glass bubbles, Markdown + code highlighting
│   ├── highlighter.py          # QSyntaxHighlighter for chat code blocks
│   └── dialogs.py              # ApiKeyOnboardingDialog, ChatSelectorDialog, SettingsDialog
├── services/
│   ├── __init__.py
│   ├── gemini_api.py           # Google GenAI SDK interface: key validation + streaming prompt handler
│   ├── storage.py              # config.json: API key, telemetry prefs, multi-thread chat history
│   └── telemetry.py            # Privacy-first PostHog wrapper
└── captures/                  # Temporary local directory for screen crops
```

---

## 4. Dual Operating Modes & Hotkeys
GSight is launched via two independent entry points that both start `main.py` with a `--mode` flag:

| Mode | Flag | Global Hotkey | Behavior |
|---|---|---|---|
| **A — Main Chat** | `--mode=chat` (default) | `Ctrl+Shift+A` | Opens the floating glass chat interface directly, loading the most recent thread (or creating one). |
| **B — Quick Screen Capture** | `--mode=capture` | `Ctrl+Shift+S` | Immediately shows the translucent drag-to-crop snipper overlay. |

Both hotkeys are also active at runtime regardless of which mode the process started in (`main.HotkeyBridge`). Desktop shortcuts pointing at each mode are generated on demand by `scripts/create_shortcuts.py` — they are **not** created automatically by the app.

### Post-Capture Chat Selector
After a crop is released, `ChatSelectorDialog` ("Select Chat to Continue") is shown whenever:
- the capture was triggered via Mode B, **or**
- more than one chat thread already exists.

Otherwise the crop routes straight to the single existing (or newly created) thread. Selecting a thread auto-attaches the crop thumbnail above the composer and focuses the prompt input.

---

## 5. First-Run API Key Gatekeeper
`main.GSightApp._pass_api_key_gate()` runs before any window is constructed. If `config.json` has no key matching the Gemini key format (`AIza` + 35 chars — see `services.gemini_api.is_valid_key_format`), `ui.dialogs.ApiKeyOnboardingDialog` is shown modally:
- Links directly to Google AI Studio (`https://aistudio.google.com/apikey`).
- Validates format client-side before enabling "Continue".
- Performs a real (background-threaded) Gemini request via `services.gemini_api.validate_api_key_live` to confirm the key actually works before it is persisted.

Rejecting the dialog exits the app without opening any other window.

---

## 6. Privacy & Data Collection (PostHog Telemetry)
See `services/telemetry.py`. Telemetry is **opt-out** (`telemetry_enabled: true` by default in `config.json`, toggleable from the tray "Settings..." menu) and is a **safe no-op** unless a `POSTHOG_API_KEY` environment variable is set — no events are ever sent without an operator explicitly wiring in a PostHog project key.

**Never captured:** prompt text, image pixel data / screenshots, Gemini responses, or the API key. `Telemetry.capture()` strips any property whose key looks sensitive (`prompt`, `text`, `message`, `api_key`, `image`, `image_bytes`, `pixels`, `content`) as a defense-in-depth measure even if a caller passes one by mistake.

**Identity:** a random, non-hardware-derived `uuid4` stored as `distinct_id` in `config.json` — never tied to a real name, email, or machine identifier.

**Exact event schema tracked:**

| Event | Properties | Trigger |
|---|---|---|
| `app_launched` | `mode` (`"chat"` \| `"capture"`) | Process start |
| `shortcut_triggered` | `mode` (`"chat"` \| `"capture"`) | Either global hotkey or tray menu action fires |
| `crop_captured` | *(none)* | A drag-to-crop selection is completed |
| `chat_created` | *(none)* | A new chat thread is created |
| `api_error_raised` | `stage` (e.g. `"stream"`) | A Gemini request fails |

This table must stay in sync with `ALLOWED_EVENTS` in `services/telemetry.py` and with the mirrored section in `README.md`.

---

## 7. `config.json` Schema
Created on first write under the project root (git-ignored). Never commit a real one.

```json
{
  "api_key": "",
  "telemetry_enabled": true,
  "distinct_id": "",
  "threads": [
    {
      "id": "uuid4",
      "name": "Chat 1",
      "created_at": "iso-8601",
      "messages": [
        {"role": "user" | "gemini", "text": "...", "image": "captures/<uuid>.png | null", "timestamp": "iso-8601"}
      ]
    }
  ]
}
```

---

## 8. Visual Design
- **Brand color:** Gemini Electric Blue, `#1A73E8` / `#4285F4`.
- **Logo:** two 'G' ring glyphs (see `assets/generate_icon.py`), the right one vertically reflected, joined by a horizontal midsection bar. Applied to the tray icon, app/taskbar icon (`assets/icon.ico`), and every window's title bar via `setWindowIcon`.
- **Chat window (`ui/window.py`):** frameless, translucent, resizable (via `QSizeGrip`), `rgba(20,20,24,0.75)` glass panel, `1px solid rgba(255,255,255,0.1)` hairline border, `border-radius: 16px`, `QGraphicsDropShadowEffect` standing in for a background blur (true acrylic/Mica blur needs Windows DWM composition APIs, out of scope for this Qt-only implementation).
- **Message bubbles (`ui/chat_bubble.py`):** user messages are right-aligned `#0A84FF` iMessage-style bubbles with the capture thumbnail rendered above the text; Gemini replies are left-aligned translucent glass bubbles with Markdown rendering (`QLabel` in `Qt.TextFormat.MarkdownText`) and fenced code blocks rendered in a separate monospace `QTextEdit` with `ui/highlighter.py`'s regex-based `QSyntaxHighlighter`. Gemini replies stream in via `GeminiStreamWorker` (backed by `generate_content_stream`), so bubble text grows chunk-by-chunk in real time.

---

## 9. Development Notes for Claude
- Run any package script as a module from the project root (e.g. `python -m services.gemini_api`), not directly, since `services`/`ui` rely on absolute `from services...` / `from ui...` imports.
- `services/storage.py` is the single source of truth for `config.json` reads/writes — do not read/write the file directly elsewhere.
- Keep `ALLOWED_EVENTS` in `services/telemetry.py`, the table in §6 above, and the "Privacy & Data Collection" section of `README.md` in lockstep whenever an event is added, renamed, or removed.
- `main.py` never creates desktop shortcuts itself — that is always an explicit, user-run step via `scripts/create_shortcuts.py`.
