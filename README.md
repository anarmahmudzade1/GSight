# GSight

A minimal, fast desktop client for Google Gemini. GSight gives you quick access to Gemini models with native keyboard shortcuts, customizable settings, and local data privacy.

---

## Key Features

* **Instant Access:** Built-in global keyboard shortcuts for rapid workflows.
* **Model Selection:** Quickly toggle between Gemini models depending on your task.
* **Privacy-First:** Your API key, local database, and configuration files stay stored locally on your machine (`%APPDATA%\GSight`).
* **Clean UI:** Frameless, dark-themed interface designed to stay out of your way.

---

## Keyboard Shortcuts

| Action | Shortcut |
| :--- | :--- |
| **Toggle Window / Quick Summon** | `Ctrl + Shift + A` |
| **Open Settings** | `Ctrl + Shift + S` |

---

## Installation

### Option 1: Download Pre-built Executable (Recommended)
1. Go to the **Releases** section on GitHub.
2. Download `GSight.exe`.
3. Double-click to run—no installer or setup required.

### Option 2: Run from Source
If you want to run or modify the code locally:

```bash
# Clone the repository
git clone [https://github.com/anarmahmudzade1/GSight.git](https://github.com/anarmahmudzade1/GSight.git)
cd GSight

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

## Setup

When launching GSight for the first time, you'll be prompted to enter your **Gemini API Key**.

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
2. Paste it into the onboarding prompt in GSight.
3. You're ready to go! You can update or change your key anytime in **Settings**.

## Privacy & Security

GSight connects directly to Google's official Gemini API using your personal API key. Your conversation history and settings are stored locally on your device in `%APPDATA%\GSight`. No private text or chat logs are collected or sent to external servers.

## License

[MIT](LICENSE)
