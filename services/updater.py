"""Background GitHub Releases update check: keeps the network round trip off
Qt's main thread so opening Settings never blocks on it."""

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from version import APP_VERSION, GITHUB_REPO

RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
REQUEST_TIMEOUT_SECONDS = 5


class UpdateCheckerThread(QThread):
    """Emits update_available(latest_version, download_url) when GitHub's
    latest release tag differs from APP_VERSION, else no_update().

    Never raises: any network or parsing failure (offline, rate-limited,
    repo has no releases yet) is treated the same as "no update" so the
    Settings dialog can stay silent about it.
    """

    update_available = pyqtSignal(str, str)
    no_update = pyqtSignal()

    def run(self):
        try:
            response = requests.get(
                RELEASES_URL,
                headers={"User-Agent": "GSight-App"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            tag_name = data["tag_name"]
            download_url = data["html_url"]
        except (requests.RequestException, ValueError, KeyError):
            self.no_update.emit()
            return

        if tag_name != APP_VERSION:
            self.update_available.emit(tag_name, download_url)
        else:
            self.no_update.emit()
