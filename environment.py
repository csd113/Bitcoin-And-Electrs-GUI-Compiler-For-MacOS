"""
environment.py
--------------
Constructs the shell environment dictionary used when invoking build tools
(CMake, Cargo, make, etc.).

Kept separate from config.py because it performs filesystem probing at
call-time rather than at import-time.
"""

import os

from config import BREW_PREFIX
from gui_helpers import log


def setup_build_environment() -> dict[str, str]:
    """Build and return a clean os.environ copy with all necessary paths set.

    Adds (in priority order):
      - Homebrew bin directory
      - Common Homebrew locations (both Apple Silicon and Intel paths)
      - Cargo/Rust bin directories
      - LLVM bin directories (needed to compile Electrs)
      - The existing PATH

    Also sets:
      - LIBCLANG_PATH and DYLD_LIBRARY_PATH for libclang (Electrs / bindgen)
    """
    env = os.environ.copy()

    if not BREW_PREFIX:
        log("⚠️  Warning: Homebrew prefix not detected, using defaults\n")

    path_components: list[str] = []

    # Homebrew
    if BREW_PREFIX:
        path_components.append(f"{BREW_PREFIX}/bin")
    path_components.extend(["/opt/homebrew/bin", "/usr/local/bin"])

    # Cargo / Rust
    for rust_path in [
        os.path.expanduser("~/.cargo/bin"),
        f"{BREW_PREFIX}/bin" if BREW_PREFIX else None,
    ]:
        if rust_path and os.path.isdir(rust_path):
            path_components.append(rust_path)

    # LLVM (required by Electrs / rust-bindgen)
    for llvm_bin in [
        f"{BREW_PREFIX}/opt/llvm/bin" if BREW_PREFIX else None,
        "/opt/homebrew/opt/llvm/bin",
        "/usr/local/opt/llvm/bin",
    ]:
        if llvm_bin and os.path.isdir(llvm_bin):
            path_components.append(llvm_bin)

    # Existing PATH last
    path_components.append(env.get("PATH", ""))

    # De-duplicate while preserving insertion order
    seen: set[str] = set()
    unique: list[str] = []
    for p in path_components:
        if p and p not in seen:
            seen.add(p)
            unique.append(p)

    env["PATH"] = ":".join(unique)

    # LLVM library path for libclang / bindgen
    for llvm_prefix in [
        f"{BREW_PREFIX}/opt/llvm" if BREW_PREFIX else None,
        "/opt/homebrew/opt/llvm",
        "/usr/local/opt/llvm",
    ]:
        if llvm_prefix and os.path.isdir(llvm_prefix):
            env["LIBCLANG_PATH"] = f"{llvm_prefix}/lib"
            env["DYLD_LIBRARY_PATH"] = f"{llvm_prefix}/lib"
            break

    return env
