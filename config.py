#!/usr/bin/env python3
"""
config.py
---------
Application-wide constants, Homebrew detection, and PyInstaller helpers.
Nothing here imports from other app modules, so it is safe to import first.
"""

import os
import sys
import platform

# ================== PYINSTALLER COMPATIBILITY ==================

def is_pyinstaller() -> bool:
    """Return True when running inside a PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

def get_base_path() -> str:
    """Return the base resource path (works both frozen and unfrozen)."""
    if is_pyinstaller():
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.abspath(".")

BASE_PATH: str = get_base_path()

# Prevent double-launch on macOS when bundled
if is_pyinstaller() and platform.system() == 'Darwin':
    os.environ['APP_STARTED'] = '1'

# ================== PATH BOOTSTRAP ==================
# Ensure key tool directories are in PATH even when launched via GUI
os.environ["PATH"] = (
    "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:"
    + os.path.expanduser("~/.cargo/bin")
)

# ================== GITHUB API / REPO URLS ==================
BITCOIN_API  = "https://api.github.com/repos/bitcoin/bitcoin/releases"
BITCOIN_REPO = "https://github.com/bitcoin/bitcoin.git"
ELECTRS_API  = "https://api.github.com/repos/romanz/electrs/releases"
ELECTRS_REPO = "https://github.com/romanz/electrs.git"

DEFAULT_BUILD_DIR: str = os.path.expanduser("~/Downloads/bitcoin_builds")

# ================== HOMEBREW DETECTION ==================

def find_brew() -> str | None:
    """Return the path to the brew binary, or None if not installed."""
    for path in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
        if os.path.isfile(path):
            return path
    return None

BREW: str | None = find_brew()

if BREW:
    BREW_PREFIX: str | None = "/opt/homebrew" if "/opt/homebrew" in BREW else "/usr/local"
else:
    BREW_PREFIX = None
