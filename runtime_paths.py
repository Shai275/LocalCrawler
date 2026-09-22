"""Stable locations shared by source and packaged builds."""
from __future__ import annotations

import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent

if FROZEN:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    DATA_DIR = local / "LocalCrawler"
else:
    DATA_DIR = APP_DIR

DATA_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR = DATA_DIR / "downloads"
PREFERENCES_FILE = DATA_DIR / "settings.json"
LOG_FILE = DATA_DIR / "app.log"

# PyInstaller places bundled data in its runtime directory (`_internal` for onedir).
runtime_dir = Path(getattr(sys, "_MEIPASS", APP_DIR)).resolve()
BROWSER_DIR = runtime_dir / "browser"
if FROZEN and BROWSER_DIR.is_dir():
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(BROWSER_DIR))
