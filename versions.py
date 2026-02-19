"""
versions.py
-----------
Version fetching (GitHub Releases API) and parsing helpers.

All functions here are pure logic or network I/O — no GUI side-effects
except logging through gui_helpers.log().
"""

import re
import requests

from config import BITCOIN_API, ELECTRS_API
from gui_helpers import log


# ================== VERSION PARSING ==================

def parse_version(tag: str) -> tuple[int, int]:
    """Return (major, minor) integers parsed from a git tag like 'v26.1'."""
    tag = tag.lstrip('v')
    m = re.match(r"(\d+)\.(\d+)", tag)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def use_cmake(version: str) -> bool:
    """Return True for Bitcoin Core v25+ which switched to CMake."""
    major, _ = parse_version(version)
    return major >= 25


# ================== GITHUB RELEASE FETCHING ==================

def _fetch_versions(api_url: str, label: str, max_count: int = 10) -> list[str]:
    """Generic helper: fetch stable release tags from a GitHub Releases API URL.

    Args:
        api_url:   Full GitHub API URL, e.g. BITCOIN_API.
        label:     Human-readable project name for log messages.
        max_count: Maximum number of versions to return.

    Returns:
        List of tag strings (release candidates omitted), newest first.
    """
    try:
        r = requests.get(api_url, timeout=10)
        r.raise_for_status()
        versions: list[str] = []
        for rel in r.json():
            tag = rel["tag_name"]
            if "rc" in tag.lower():
                continue
            versions.append(tag)
            if len(versions) == max_count:
                break
        log(f"Found {len(versions)} {label} versions\n")
        return versions
    except Exception as e:
        log(f"Failed to fetch {label} versions: {e}\n")
        return []


def get_bitcoin_versions() -> list[str]:
    """Return up to 10 stable Bitcoin Core release tags."""
    return _fetch_versions(BITCOIN_API, "Bitcoin")


def get_electrs_versions() -> list[str]:
    """Return up to 10 stable Electrs release tags."""
    return _fetch_versions(ELECTRS_API, "Electrs")
