"""Creates the two GSight desktop shortcuts (Mode A: chat, Mode B: quick capture).

Run manually, whenever you want the shortcuts installed - nothing in the app
calls this automatically:

    venv\\Scripts\\python.exe scripts\\create_shortcuts.py

Requires pywin32 (`pip install pywin32`), which is only needed for this script,
not a runtime dependency of GSight itself.
"""

import sys
from pathlib import Path

try:
    import win32com.client
except ImportError:
    sys.exit("pywin32 is required for this script. Install it with: pip install pywin32")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHONW = PROJECT_ROOT / "venv" / "Scripts" / "pythonw.exe"
MAIN_SCRIPT = PROJECT_ROOT / "main.py"
ICON_PATH = PROJECT_ROOT / "assets" / "icon.ico"
DESKTOP = Path.home() / "Desktop"

SHORTCUTS = [
    ("GSight - Main Chat.lnk", "--mode=chat"),
    ("GSight - Quick Screen Capture.lnk", "--mode=capture"),
]


def create_shortcut(name: str, args: str):
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(str(DESKTOP / name))
    shortcut.TargetPath = str(PYTHONW)
    shortcut.Arguments = f'"{MAIN_SCRIPT}" {args}'
    shortcut.WorkingDirectory = str(PROJECT_ROOT)
    if ICON_PATH.exists():
        shortcut.IconLocation = str(ICON_PATH)
    shortcut.Description = "GSight - AI vision utility"
    shortcut.save()
    print(f"Created {DESKTOP / name}")


def main():
    if not PYTHONW.exists():
        sys.exit(f"pythonw.exe not found at {PYTHONW}. Is the venv set up?")
    if not MAIN_SCRIPT.exists():
        sys.exit(f"main.py not found at {MAIN_SCRIPT}")

    for name, args in SHORTCUTS:
        create_shortcut(name, args)


if __name__ == "__main__":
    main()
