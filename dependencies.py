"""
dependencies.py
---------------
Checks for and optionally installs all system dependencies:
  - Homebrew packages required by Bitcoin Core and Electrs
  - The Rust toolchain (rustc + cargo)

Functions that talk to the GUI use gui_helpers so they remain thread-safe.
The public entry point (check_dependencies) spawns its own background thread
so it can be wired directly to a Tkinter Button command.
"""

import os
import subprocess
import threading
import time

from config import BREW, BREW_PREFIX
from gui_helpers import log, run_command, show_message, ask_yes_no_threadsafe

# Homebrew packages required for a node-only (no wallet) Bitcoin + Electrs build
BREW_PACKAGES: list[str] = [
    "automake", "libtool", "pkg-config", "boost",
    "miniupnpc", "zeromq", "sqlite", "python", "cmake",
    "llvm", "libevent", "rocksdb", "rust", "git",
]


# ================== RUST CHECK ==================

def check_rust_installation() -> bool:
    """Verify rustc and cargo are present; attempt Homebrew install if not.

    Returns:
        True if both rustc and cargo are functional after the check.
    """
    log("\n=== Checking Rust Toolchain ===\n")

    rust_search_paths: list[str] = [p for p in [
        os.path.expanduser("~/.cargo/bin"),
        f"{BREW_PREFIX}/bin" if BREW_PREFIX else None,
        "/usr/local/bin",
        "/opt/homebrew/bin",
    ] if p]

    rustc_found = False
    cargo_found = False

    for path in rust_search_paths:
        rustc_candidate = os.path.join(path, "rustc")
        cargo_candidate = os.path.join(path, "cargo")

        if os.path.isfile(rustc_candidate) and not rustc_found:
            r = subprocess.run(
                [rustc_candidate, "--version"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            if r.returncode == 0:
                rustc_found = True
                log(f"✓ rustc found at: {rustc_candidate}\n")
                log(f"  Version: {r.stdout.strip()}\n")

        if os.path.isfile(cargo_candidate) and not cargo_found:
            r = subprocess.run(
                [cargo_candidate, "--version"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            if r.returncode == 0:
                cargo_found = True
                log(f"✓ cargo found at: {cargo_candidate}\n")
                log(f"  Version: {r.stdout.strip()}\n")

    if rustc_found and cargo_found:
        return True

    # ---- Attempt installation via Homebrew ----
    log("\n❌ Rust toolchain not found or incomplete!\n")
    log("Installing Rust via Homebrew...\n")

    try:
        probe = subprocess.run(
            [BREW, "info", "rust"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )

        if probe.returncode != 0:
            log("❌ Rust formula not found in Homebrew\n")
            show_message(
                "showerror",
                "Rust Installation Failed",
                "Could not install Rust via Homebrew.\n\n"
                "Please install manually:\n"
                "1. Visit https://rustup.rs\n"
                "2. Run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh\n"
                "3. Restart this app",
            )
            return False

        log("📦 Installing rust from Homebrew...\n")
        run_command(f"{BREW} install rust")

        log("\nVerifying Rust installation...\n")
        time.sleep(2)

        # Re-check after installation
        for path in rust_search_paths:
            if not rustc_found and os.path.isfile(os.path.join(path, "rustc")):
                r = subprocess.run(
                    [os.path.join(path, "rustc"), "--version"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                if r.returncode == 0:
                    log(f"✓ rustc installed successfully: {r.stdout.strip()}\n")
                    rustc_found = True

            if not cargo_found and os.path.isfile(os.path.join(path, "cargo")):
                r = subprocess.run(
                    [os.path.join(path, "cargo"), "--version"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                if r.returncode == 0:
                    log(f"✓ cargo installed successfully: {r.stdout.strip()}\n")
                    cargo_found = True

        if not (rustc_found and cargo_found):
            log("⚠️  Rust installed but binaries not found in PATH\n")
            show_message(
                "showwarning",
                "Rust Installation",
                "Rust was installed but may not be in PATH.\n\n"
                "Please:\n"
                "1. Close and reopen this app\n"
                "2. OR manually add ~/.cargo/bin to your PATH",
            )

    except Exception as e:
        log(f"❌ Failed to install Rust: {e}\n")
        show_message(
            "showerror",
            "Installation Error",
            f"Failed to install Rust: {e}\n\n"
            "Please install manually from https://rustup.rs",
        )

    return rustc_found and cargo_found


# ================== FULL DEPENDENCY CHECK ==================

def _run_dependency_check() -> None:
    """Worker function executed in a background thread by check_dependencies()."""
    try:
        log("\n=== Checking System Dependencies ===\n")

        if not BREW:
            log("❌ Homebrew not found!\n")
            log("Please install Homebrew from https://brew.sh\n")
            show_message(
                "showerror",
                "Missing Dependency",
                "Homebrew not found! Please install from https://brew.sh",
            )
            return

        log(f"✓ Homebrew found at: {BREW}\n")
        log(f"  Homebrew prefix: {BREW_PREFIX}\n")

        # ---- Check Homebrew packages ----
        log("\nChecking Homebrew packages...\n")
        missing: list[str] = []
        for pkg in BREW_PACKAGES:
            r = subprocess.run(
                [BREW, "list", pkg],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            if r.returncode != 0:
                log(f"  ❌ {pkg} - not installed\n")
                missing.append(pkg)
            else:
                log(f"  ✓ {pkg}\n")

        if missing:
            log(f"\n⚠️  Missing Homebrew packages: {', '.join(missing)}\n")

            pkg_count = len(missing)
            pkg_list = ", ".join(missing[:5])
            if pkg_count > 5:
                pkg_list += f", and {pkg_count - 5} more"

            try:
                install_deps = ask_yes_no_threadsafe(
                    "Install Missing Dependencies",
                    f"Found {pkg_count} missing package{'s' if pkg_count > 1 else ''}:\n\n"
                    f"{pkg_list}\n\n"
                    f"Install all missing packages now?",
                )
            except Exception as e:
                log(f"⚠️  Error showing dialog: {e}\n")
                install_deps = ask_yes_no_threadsafe(
                    "Install Dependencies",
                    f"Install {pkg_count} missing packages?",
                )

            if install_deps:
                for pkg in missing:
                    log(f"\n📦 Installing {pkg}...\n")
                    try:
                        run_command(f"{BREW} install {pkg}")
                        log(f"✓ {pkg} installed successfully\n")
                    except Exception as e:
                        log(f"❌ Failed to install {pkg}: {e}\n")
                        try:
                            show_message("showerror", "Installation Failed", f"Failed to install {pkg}")
                        except Exception:
                            log("⚠️  Could not show error dialog\n")
            else:
                log("\n⚠️  Dependencies not installed. Compilation may fail.\n")
        else:
            log("\n✓ All Homebrew packages are installed!\n")

        # ---- Check Rust ----
        rust_ok = check_rust_installation()

        if rust_ok:
            log("\n✓ Rust toolchain is ready!\n")
        else:
            log("\n⚠️  Rust toolchain needs attention (see messages above)\n")

        log("\n=== Dependency Check Complete ===\n")

        if rust_ok:
            show_message(
                "showinfo",
                "Dependency Check",
                "✅ All dependencies are installed and ready!\n\n"
                "You can now proceed with compilation.",
            )
        else:
            show_message(
                "showwarning",
                "Dependency Check",
                "⚠️  Some dependencies need attention.\n\n"
                "Check the log for details.\n"
                "You may need to restart the app after installing Rust.",
            )

    except Exception as e:
        log(f"\n❌ Error during dependency check: {e}\n")
        import traceback
        log(traceback.format_exc() + "\n")
        show_message("showerror", "Error", f"Dependency check failed: {e}")


def check_dependencies() -> None:
    """Launch a background thread to check and optionally install dependencies.

    Designed to be passed directly as a Tkinter Button command.
    """
    threading.Thread(target=_run_dependency_check, daemon=True).start()
