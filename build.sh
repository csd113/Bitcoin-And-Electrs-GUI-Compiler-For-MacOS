#!/usr/bin/env bash
# =============================================================================
# build.sh — Bitcoin & Electrs Compiler  ·  macOS App Build Script
# =============================================================================
#
# USAGE
#   ./build.sh [OPTIONS]
#
# OPTIONS
#   --sign IDENTITY     Code-sign with a Developer ID Application certificate.
#                       IDENTITY is the string shown by:
#                         security find-identity -v -p codesigning
#                       e.g. "Developer ID Application: Jane Smith (TEAM123)"
#
#   --notarize          Submit to Apple Notary after signing.
#                       Requires --sign, APPLE_ID and NOTARIZE_TEAM_ID to be
#                       set as environment variables (or edit the vars below).
#
#   --arch ARCH         Target architecture: x86_64 | arm64 | universal2
#                       Default: native (matches the current machine).
#
#   --skip-dmg          Build the .app but do not package it into a DMG.
#
#   --clean             Remove dist/, build/, and the venv before building.
#
#   --help              Show this help text.
#
# ENVIRONMENT VARIABLES (for notarization)
#   APPLE_ID            Your Apple ID email, e.g. jane@example.com
#   NOTARIZE_TEAM_ID    Your 10-character Apple Team ID
#   NOTARIZE_PASSWORD   App-specific password (or @keychain:AC_PASSWORD)
#
# EXAMPLES
#   # Quick local build — no signing
#   ./build.sh
#
#   # Signed build for distribution
#   ./build.sh --sign "Developer ID Application: Jane Smith (ABC1234XYZ)"
#
#   # Signed + notarized universal binary
#   ./build.sh --arch universal2 \
#              --sign "Developer ID Application: Jane Smith (ABC1234XYZ)" \
#              --notarize
#
# REQUIREMENTS
#   - macOS 12 (Monterey) or later
#   - Python 3.11+ (from python.org or Homebrew; NOT the macOS system Python)
#   - Xcode Command Line Tools  (xcode-select --install)
#   - create-dmg  (brew install create-dmg)  — only needed without --skip-dmg
# =============================================================================

set -euo pipefail

# ── Colour helpers ────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}▶ $*${RESET}"; }
success() { echo -e "${GREEN}✅ $*${RESET}"; }
warn()    { echo -e "${YELLOW}⚠️  $*${RESET}"; }
error()   { echo -e "${RED}❌ $*${RESET}"; exit 1; }
header()  { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════${RESET}"; \
            echo -e "${BOLD}${CYAN}  $*${RESET}"; \
            echo -e "${BOLD}${CYAN}══════════════════════════════════════════${RESET}\n"; }

# ── Script location ───────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Configurable defaults ─────────────────────────────────────────────────────
APP_NAME="Bitcoin Compiler"
BUNDLE_ID="com.bitcoincompiler.app"
VERSION="1.0.0"
PYTHON_MIN="3.11"

VENV_DIR="$SCRIPT_DIR/.venv-build"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR_PI="$SCRIPT_DIR/build"   # PyInstaller's own build dir
ASSETS_DIR="$SCRIPT_DIR/assets"
APP_PATH="$DIST_DIR/${APP_NAME}.app"
DMG_PATH="$DIST_DIR/${APP_NAME}-${VERSION}.dmg"

CODESIGN_IDENTITY=""
DO_NOTARIZE=false
TARGET_ARCH=""          # empty = native
SKIP_DMG=false
DO_CLEAN=false

# Notarization credentials (can also be set as env vars before running)
APPLE_ID="${APPLE_ID:-}"
NOTARIZE_TEAM_ID="${NOTARIZE_TEAM_ID:-}"
NOTARIZE_PASSWORD="${NOTARIZE_PASSWORD:-@keychain:AC_PASSWORD}"

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --sign)        CODESIGN_IDENTITY="$2"; shift 2 ;;
    --notarize)    DO_NOTARIZE=true;       shift   ;;
    --arch)        TARGET_ARCH="$2";       shift 2 ;;
    --skip-dmg)    SKIP_DMG=true;          shift   ;;
    --clean)       DO_CLEAN=true;          shift   ;;
    --help|-h)
      sed -n '/^# USAGE/,/^# ===/p' "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) error "Unknown option: $1" ;;
  esac
done

# ── Validate notarization prerequisites ──────────────────────────────────────
if $DO_NOTARIZE; then
  [[ -z "$CODESIGN_IDENTITY" ]] && error "--notarize requires --sign"
  [[ -z "$APPLE_ID"           ]] && error "Set APPLE_ID env var for notarization"
  [[ -z "$NOTARIZE_TEAM_ID"   ]] && error "Set NOTARIZE_TEAM_ID env var for notarization"
fi

# ── OS check ─────────────────────────────────────────────────────────────────
[[ "$(uname)" == "Darwin" ]] || error "This script must run on macOS"

header "Bitcoin Compiler — macOS App Builder"
info "App:     $APP_NAME $VERSION"
info "Bundle:  $BUNDLE_ID"
info "Arch:    ${TARGET_ARCH:-native}"
info "Sign:    ${CODESIGN_IDENTITY:-none (unsigned)}"
info "DMG:     $(! $SKIP_DMG && echo yes || echo no)"
echo

# ── Optional clean ────────────────────────────────────────────────────────────
if $DO_CLEAN; then
  header "Cleaning previous build artefacts"
  rm -rf "$DIST_DIR" "$BUILD_DIR_PI" "$VENV_DIR"
  success "Clean done"
fi

# ── Python version check ──────────────────────────────────────────────────────
header "Checking Python"

find_python() {
  # Prefer explicit python3.x binaries, then python3
  for candidate in python3.13 python3.12 python3.11 python3; do
    if command -v "$candidate" &>/dev/null; then
      ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
      major=${ver%%.*}; minor=${ver##*.}
      req_major=${PYTHON_MIN%%.*}; req_minor=${PYTHON_MIN##*.}
      if (( major > req_major || (major == req_major && minor >= req_minor) )); then
        echo "$candidate"
        return
      fi
    fi
  done
  echo ""
}

PYTHON=$(find_python)
[[ -z "$PYTHON" ]] && error "Python $PYTHON_MIN+ not found. Install from https://python.org or: brew install python@3.12"
PYTHON_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
success "Using Python $PYTHON_VER at $(command -v "$PYTHON")"

# Warn if using macOS system Python (often causes tkinter issues)
if [[ "$PYTHON" == /usr/bin/python* ]]; then
  warn "System Python detected — tkinter may be missing. Prefer Homebrew/python.org Python."
fi

# ── Virtual environment ───────────────────────────────────────────────────────
header "Setting up build virtual environment"

if [[ ! -d "$VENV_DIR" ]]; then
  info "Creating venv at $VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
success "Activated venv: $VENV_DIR"

# ── Install / upgrade build dependencies ─────────────────────────────────────
header "Installing Python dependencies"

pip install --upgrade pip wheel setuptools --quiet

info "Installing runtime dependencies..."
pip install --upgrade \
  requests \
  certifi \
  charset-normalizer \
  idna \
  urllib3 \
  --quiet

info "Installing PyInstaller..."
pip install --upgrade pyinstaller --quiet

PYINSTALLER_VER=$(pyinstaller --version 2>&1)
success "PyInstaller $PYINSTALLER_VER ready"

# ── Generate app icon ─────────────────────────────────────────────────────────
header "Generating app icon"

mkdir -p "$ASSETS_DIR"
ICON_ICNS="$ASSETS_DIR/icon.icns"

generate_icon() {
  # Requires Xcode CLT (sips + iconutil are standard macOS tools)
  command -v sips    &>/dev/null || { warn "sips not found — skipping icon generation"; return 1; }
  command -v iconutil &>/dev/null || { warn "iconutil not found — skipping icon generation"; return 1; }

  local ICONSET="$ASSETS_DIR/icon.iconset"
  mkdir -p "$ICONSET"

  # Create a 1024×1024 source PNG using Python (no Pillow needed)
  info "Generating source PNG via Python..."
  "$PYTHON" - <<'PYEOF'
import struct, zlib, math

def png(w, h, pixels_rgba):
    def chunk(tag, data):
        c = zlib.crc32(tag + data) & 0xffffffff
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", c)

    raw = b"".join(
        b"\x00" + b"".join(struct.pack("BBBB", *px) for px in pixels_rgba[y])
        for y in range(h)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )

SIZE = 1024
pixels = []
cx, cy = SIZE / 2, SIZE / 2
r_outer, r_inner = SIZE * 0.46, SIZE * 0.30

for y in range(SIZE):
    row = []
    for x in range(SIZE):
        dx, dy = x - cx, y - cy
        dist = math.hypot(dx, dy)
        # Background gradient: deep navy
        bg_r = int(10 + 20 * (y / SIZE))
        bg_g = int(15 + 30 * (y / SIZE))
        bg_b = int(40 + 60 * (y / SIZE))
        # Outer ring (Bitcoin orange)
        if r_inner <= dist <= r_outer:
            t = (dist - r_inner) / (r_outer - r_inner)
            # Smooth step
            t = t * t * (3 - 2 * t)
            row.append((int(247 * (1-t) + bg_r * t),
                        int(147 * (1-t) + bg_g * t),
                        int(26  * (1-t) + bg_b * t), 255))
        elif dist < r_inner:
            # Inner circle: dark with ₿ symbol implied by colour
            row.append((20, 30, 70, 255))
        else:
            row.append((bg_r, bg_g, bg_b, 255))
    pixels.append(row)

import os
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "assets", "icon_1024.png")
with open(out, "wb") as f:
    f.write(png(SIZE, SIZE, pixels))
print(f"  written: {out}")
PYEOF

  SOURCE_PNG="$ASSETS_DIR/icon_1024.png"
  [[ -f "$SOURCE_PNG" ]] || { warn "Source PNG not generated"; return 1; }

  # Resize to every required iconset size
  local SIZES=(16 32 64 128 256 512 1024)
  for sz in "${SIZES[@]}"; do
    sips -z "$sz" "$sz" "$SOURCE_PNG" \
         --out "$ICONSET/icon_${sz}x${sz}.png"        &>/dev/null
    # @2x variant (Retina) — only up to 512@2x (=1024)
    if (( sz <= 512 )); then
      local double=$(( sz * 2 ))
      sips -z "$double" "$double" "$SOURCE_PNG" \
           --out "$ICONSET/icon_${sz}x${sz}@2x.png"   &>/dev/null
    fi
  done

  iconutil -c icns "$ICONSET" -o "$ICON_ICNS"
  rm -rf "$ICONSET" "$SOURCE_PNG"
  success "Icon generated: $ICON_ICNS"
}

if [[ -f "$ICON_ICNS" ]]; then
  info "Using existing icon: $ICON_ICNS"
else
  generate_icon || warn "Icon generation failed — app will use default macOS icon"
fi

# ── Build .app with PyInstaller ───────────────────────────────────────────────
header "Building .app bundle with PyInstaller"

mkdir -p "$DIST_DIR"

PYINSTALLER_ARGS=(
  "$SCRIPT_DIR/bitcoin_compiler.spec"
  "--distpath=$DIST_DIR"
  "--workpath=$BUILD_DIR_PI"
  "--noconfirm"
)

# Pass architecture override if requested
if [[ -n "$TARGET_ARCH" ]]; then
  PYINSTALLER_ARGS+=("--target-arch=$TARGET_ARCH")
  info "Target architecture: $TARGET_ARCH"
fi

info "Running PyInstaller..."
pyinstaller "${PYINSTALLER_ARGS[@]}"

[[ -d "$APP_PATH" ]] || error "Build failed — .app not found at $APP_PATH"
success "App bundle created: $APP_PATH"

# ── Code signing ─────────────────────────────────────────────────────────────
if [[ -n "$CODESIGN_IDENTITY" ]]; then
  header "Code signing"

  info "Signing all binaries and dylibs inside the bundle..."
  # Sign inner libraries first (deep sign), then the outer bundle
  find "$APP_PATH" \
    -type f \( -name "*.so" -o -name "*.dylib" -o -perm +0111 \) \
    | sort \
    | while read -r binary; do
        codesign \
          --force \
          --sign "$CODESIGN_IDENTITY" \
          --options runtime \
          --entitlements "$SCRIPT_DIR/entitlements.plist" \
          --timestamp \
          "$binary" 2>/dev/null || true   # some files may already be signed
      done

  info "Signing the .app bundle..."
  codesign \
    --force \
    --deep \
    --sign "$CODESIGN_IDENTITY" \
    --options runtime \
    --entitlements "$SCRIPT_DIR/entitlements.plist" \
    --timestamp \
    "$APP_PATH"

  info "Verifying signature..."
  codesign --verify --deep --strict --verbose=2 "$APP_PATH"
  spctl --assess --type exec --verbose "$APP_PATH" && \
    success "Gatekeeper assessment passed" || \
    warn "Gatekeeper assessment failed — app may need notarization"
else
  warn "Skipping code signing (no --sign provided). App will trigger Gatekeeper on other Macs."
fi

# ── Create DMG ───────────────────────────────────────────────────────────────
if ! $SKIP_DMG; then
  header "Creating DMG installer"

  command -v create-dmg &>/dev/null || {
    warn "create-dmg not found. Install with: brew install create-dmg"
    warn "Skipping DMG creation."
    SKIP_DMG=true
  }

  if ! $SKIP_DMG; then
    [[ -f "$DMG_PATH" ]] && rm -f "$DMG_PATH"

    DMG_STAGING="$DIST_DIR/dmg-staging"
    rm -rf "$DMG_STAGING"
    mkdir -p "$DMG_STAGING"
    cp -R "$APP_PATH" "$DMG_STAGING/"

    create-dmg \
      --volname "$APP_NAME" \
      --volicon "$ICON_ICNS" \
      --window-pos 200 120 \
      --window-size 660 400 \
      --icon-size 128 \
      --icon "${APP_NAME}.app" 180 170 \
      --hide-extension "${APP_NAME}.app" \
      --app-drop-link 480 170 \
      --no-internet-enable \
      "$DMG_PATH" \
      "$DMG_STAGING"

    rm -rf "$DMG_STAGING"
    [[ -f "$DMG_PATH" ]] && success "DMG created: $DMG_PATH" || warn "DMG creation failed"
  fi
fi

# Sign the DMG too (if we have an identity and a DMG)
if [[ -n "$CODESIGN_IDENTITY" && -f "$DMG_PATH" ]]; then
  info "Signing DMG..."
  codesign \
    --sign "$CODESIGN_IDENTITY" \
    --timestamp \
    "$DMG_PATH"
  success "DMG signed"
fi

# ── Notarization ──────────────────────────────────────────────────────────────
if $DO_NOTARIZE; then
  header "Submitting to Apple Notary Service"

  NOTARIZE_TARGET="${DMG_PATH:-$APP_PATH}"
  # Zip the .app if there is no DMG
  if [[ ! -f "$DMG_PATH" ]]; then
    NOTARIZE_TARGET="$DIST_DIR/${APP_NAME}-${VERSION}.zip"
    info "Zipping .app for notarization..."
    ditto -c -k --keepParent "$APP_PATH" "$NOTARIZE_TARGET"
  fi

  info "Submitting $NOTARIZE_TARGET — this can take several minutes..."
  xcrun notarytool submit "$NOTARIZE_TARGET" \
    --apple-id      "$APPLE_ID" \
    --team-id       "$NOTARIZE_TEAM_ID" \
    --password      "$NOTARIZE_PASSWORD" \
    --wait

  info "Stapling notarization ticket to .app..."
  xcrun stapler staple "$APP_PATH"

  if [[ -f "$DMG_PATH" ]]; then
    info "Re-creating DMG with stapled .app..."
    # Rebuild DMG so the stapled app is included
    DMG_STAGING="$DIST_DIR/dmg-staging-notarized"
    rm -rf "$DMG_STAGING"
    mkdir -p "$DMG_STAGING"
    cp -R "$APP_PATH" "$DMG_STAGING/"
    rm -f "$DMG_PATH"
    create-dmg \
      --volname "$APP_NAME" \
      --volicon "$ICON_ICNS" \
      --window-pos 200 120 \
      --window-size 660 400 \
      --icon-size 128 \
      --icon "${APP_NAME}.app" 180 170 \
      --hide-extension "${APP_NAME}.app" \
      --app-drop-link 480 170 \
      --no-internet-enable \
      "$DMG_PATH" \
      "$DMG_STAGING"
    rm -rf "$DMG_STAGING"
    codesign --sign "$CODESIGN_IDENTITY" --timestamp "$DMG_PATH"
    success "Notarized DMG ready: $DMG_PATH"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
header "Build Complete"
echo -e "${GREEN}${BOLD}Artefacts:${RESET}"
echo -e "  📦 App:  $APP_PATH"
$SKIP_DMG || [[ ! -f "$DMG_PATH" ]] || \
  echo -e "  💿 DMG:  $DMG_PATH"
echo
if [[ -z "$CODESIGN_IDENTITY" ]]; then
  echo -e "${YELLOW}To run on this Mac:${RESET}"
  echo -e "  open \"$APP_PATH\""
  echo
  echo -e "${YELLOW}To distribute to other Macs, re-run with:${RESET}"
  echo -e "  ./build.sh --sign \"Developer ID Application: You (TEAMID)\""
else
  echo -e "${GREEN}To run:${RESET}"
  echo -e "  open \"$APP_PATH\""
fi
echo
