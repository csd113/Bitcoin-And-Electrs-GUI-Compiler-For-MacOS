# -*- mode: python ; coding: utf-8 -*-
#
# bitcoin_compiler.spec
# ---------------------
# PyInstaller spec file for Bitcoin & Electrs Compiler.
#
# Build with:
#   pyinstaller bitcoin_compiler.spec
#
# Or use the provided build.sh which handles the full pipeline.

import sys
import os
from PyInstaller.building.build_main import Analysis, PYZ, EXE, BUNDLE, COLLECT

# ── Paths ──────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(SPEC))  # directory containing this .spec

# ── Analysis ───────────────────────────────────────────────────────────────
# List every module that is only reachable at runtime (not via static imports).
hidden_imports = [
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "tkinter.filedialog",
    "requests",
    "requests.adapters",
    "requests.auth",
    "requests.cookies",
    "requests.exceptions",
    "requests.models",
    "requests.sessions",
    "urllib3",
    "certifi",
    "charset_normalizer",
    "idna",
    # App modules (PyInstaller may miss them because they're imported via strings)
    "config",
    "state",
    "gui_helpers",
    "versions",
    "environment",
    "dependencies",
    "builder",
    "gui",
]

a = Analysis(
    ["main.py"],
    pathex=[HERE],
    binaries=[],
    datas=[
        # If you add a custom icon or any data files, include them here:
        # ("assets/icon.icns", "assets"),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Strip heavyweight packages that are never used
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
        "scipy",
        "PyQt5",
        "PyQt6",
        "wx",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

# ── Executable (the inner Unix binary inside the .app) ─────────────────────
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # COLLECT handles binaries (keeps .app lean)
    name="Bitcoin Compiler",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # UPX can break macOS code-signing; keep off
    console=False,           # No terminal window — pure GUI app
    disable_windowed_traceback=False,
    argv_emulation=True,     # Needed for macOS file-open events
    target_arch=None,        # None = match host; set "universal2" for fat binary
    # NOTE: Do NOT pass codesign_identity or entitlements_file here.
    # PyInstaller's internal ad-hoc signing pass uses `codesign -s -` which
    # cannot handle Hardened Runtime entitlements or the --timestamp flag.
    # Real signing (with a Developer ID) is done by build.sh after the fact.
)

# ── Collect all binaries / dylibs into the .app bundle ────────────────────
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Bitcoin Compiler",
)

# ── macOS .app Bundle ──────────────────────────────────────────────────────
app = BUNDLE(
    coll,
    name="Bitcoin Compiler.app",
    # icon path is resolved by build.sh; override with --icon flag if needed
    icon=os.path.join(HERE, "assets", "icon.icns") if os.path.exists(
        os.path.join(HERE, "assets", "icon.icns")) else None,
    bundle_identifier="com.bitcoincompiler.app",
    version="1.0.0",
    info_plist={
        # ── Identity ──────────────────────────────────────────────────────
        "CFBundleName":               "Bitcoin Compiler",
        "CFBundleDisplayName":        "Bitcoin Compiler",
        "CFBundleIdentifier":         "com.bitcoincompiler.app",
        "CFBundleVersion":            "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleExecutable":         "Bitcoin Compiler",

        # ── App type ──────────────────────────────────────────────────────
        "CFBundlePackageType":        "APPL",
        "CFBundleSignature":          "????",
        "LSApplicationCategoryType":  "public.app-category.developer-tools",

        # ── UI behaviour ──────────────────────────────────────────────────
        "NSHighResolutionCapable":    True,
        "NSRequiresAquaSystemAppearance": False,  # Allow Dark Mode
        "LSMinimumSystemVersion":     "12.0",    # Monterey+

        # ── Privacy / permissions ─────────────────────────────────────────
        # The app runs subprocesses (git, cargo, make) — no special entitlements
        # beyond what's in entitlements.plist are needed.
        "NSAppleEventsUsageDescription":
            "Bitcoin Compiler uses Apple Events to run build tools.",

        # ── Prevent Gatekeeper complaining about "damaged app" ────────────
        "LSEnvironment": {
            "PYTHONDONTWRITEBYTECODE": "1",
        },

        # ── Dock / Launchpad ──────────────────────────────────────────────
        "NSPrincipalClass": "NSApplication",
        "NSMainNibFile": "",   # We use code-only UI (Tkinter)
    },
)
