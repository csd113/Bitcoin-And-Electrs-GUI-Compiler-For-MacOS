"""
builder.py
----------
Core compilation logic for Bitcoin Core and Electrs.

All long-running work runs in daemon threads so the GUI stays responsive.
GUI state is touched only through gui_helpers (thread-safe).
"""

import os
import shutil
import subprocess
import threading
import traceback

import state
from config import BITCOIN_REPO, ELECTRS_REPO
from environment import setup_build_environment
from gui_helpers import log, run_command, set_progress, show_message
from versions import use_cmake


# ================== BINARY UTILITIES ==================

def copy_binaries(src_dir: str, dest_dir: str, binary_files: list[str]) -> list[str]:
    """Copy *binary_files* into *dest_dir*, making each file executable.

    Args:
        src_dir:      Source build tree root (used for logging only).
        dest_dir:     Destination directory; created if absent.
        binary_files: Full paths to the binaries to copy.

    Returns:
        List of destination paths for successfully copied binaries.
    """
    os.makedirs(dest_dir, exist_ok=True)
    copied: list[str] = []

    log(f"Copying binaries to: {dest_dir}\n")

    for binary in binary_files:
        if os.path.exists(binary):
            try:
                dest = os.path.join(dest_dir, os.path.basename(binary))
                shutil.copy2(binary, dest)
                os.chmod(dest, 0o755)
                copied.append(dest)
                log(f"✓ Copied: {os.path.basename(binary)} → {dest}\n")
            except Exception as e:
                log(f"⚠️  Failed to copy {os.path.basename(binary)}: {e}\n")
        else:
            log(f"⚠️  Binary not found (skipping): {binary}\n")

    if not copied:
        log("❌ WARNING: No binaries were copied!\n")

    return copied


# ================== BITCOIN CORE ==================

def compile_bitcoin_source(version: str, build_dir: str, cores: int) -> str:
    """Clone (or update) Bitcoin Core source and build it.

    Args:
        version:   Git tag to check out, e.g. 'v27.0'.
        build_dir: Parent directory for the source tree and output binaries.
        cores:     Number of parallel compile jobs.

    Returns:
        Path to the directory containing the compiled binaries.

    Raises:
        RuntimeError: On any build failure.
    """
    try:
        log(f"\n{'='*60}\n")
        log(f"COMPILING BITCOIN CORE {version}\n")
        log(f"{'='*60}\n")

        version_clean = version.lstrip('v')
        src_dir = os.path.join(build_dir, f"bitcoin-{version_clean}")
        os.makedirs(build_dir, exist_ok=True)

        # Clone or refresh source
        if not os.path.exists(src_dir):
            log(f"\n📥 Cloning Bitcoin Core repository...\n")
            run_command(
                f"git clone --depth 1 --branch {version} {BITCOIN_REPO} {src_dir}",
                cwd=build_dir,
            )
            log(f"✓ Source cloned to {src_dir}\n")
        else:
            log(f"✓ Source directory already exists: {src_dir}\n")
            log(f"📥 Updating to {version}...\n")
            run_command(f"git fetch --depth 1 origin tag {version}", cwd=src_dir)
            run_command(f"git checkout {version}", cwd=src_dir)
            log(f"✓ Updated to {version}\n")

        env = setup_build_environment()
        log(f"\nEnvironment setup:\n")
        log(f"  PATH: {env['PATH'][:150]}...\n")
        log(f"  Building node-only (wallet support disabled)\n")

        if use_cmake(version):
            # ---- CMake build (v25+) ----
            log(f"\n🔨 Building with CMake (Bitcoin Core {version})...\n")
            log(f"\n⚙️  Configuring (wallet support disabled for node-only build)...\n")
            run_command(
                "cmake -B build -DENABLE_WALLET=OFF -DENABLE_IPC=OFF",
                cwd=src_dir, env=env,
            )
            log(f"\n🔧 Compiling with {cores} cores...\n")
            run_command(f"cmake --build build -j{cores}", cwd=src_dir, env=env)

            binary_dir = os.path.join(src_dir, "build", "bin")
            binaries = [
                os.path.join(binary_dir, b)
                for b in ["bitcoind", "bitcoin-cli", "bitcoin-tx",
                          "bitcoin-wallet", "bitcoin-util"]
            ]

        else:
            # ---- Autotools build (pre-v25) ----
            log(f"\n🔨 Building with Autotools (Bitcoin Core {version})...\n")
            config_cmd = "./configure --disable-wallet --disable-gui"

            log(f"\n⚙️  Running autogen.sh...\n")
            run_command("./autogen.sh", cwd=src_dir, env=env)
            log(f"\n⚙️  Configuring (wallet support disabled for node-only build)...\n")
            run_command(config_cmd, cwd=src_dir, env=env)
            log(f"\n🔧 Compiling with {cores} cores...\n")
            run_command(f"make -j{cores}", cwd=src_dir, env=env)

            binary_dir = os.path.join(src_dir, "bin")
            binaries = [
                os.path.join(binary_dir, b)
                for b in ["bitcoind", "bitcoin-cli", "bitcoin-tx", "bitcoin-wallet"]
            ]

        # Copy to output
        log(f"\n📋 Collecting binaries...\n")
        output_dir = os.path.join(build_dir, "binaries", f"bitcoin-{version_clean}")
        copied = copy_binaries(src_dir, output_dir, binaries)

        if not copied:
            log("⚠️  Warning: No binaries were copied. Checking what exists...\n")
            for b in binaries:
                log(f"  {'✓' if os.path.exists(b) else '❌'} {b}\n")

        log(f"\n{'='*60}\n")
        log(f"✅ BITCOIN CORE {version} COMPILED SUCCESSFULLY!\n")
        log(f"{'='*60}\n")
        log(f"\n📍 Binaries location: {output_dir}\n")
        log(f"   Found {len(copied)} binaries\n\n")

        return output_dir

    except Exception as e:
        log(f"\n❌ Error compiling Bitcoin: {e}\n")
        log(f"\nFull traceback:\n{traceback.format_exc()}\n")
        raise


# ================== ELECTRS ==================

def compile_electrs_source(version: str, build_dir: str, cores: int) -> str:
    """Clone (or update) Electrs source and build it with Cargo.

    Args:
        version:   Git tag to check out, e.g. 'v0.10.5'.
        build_dir: Parent directory for the source tree and output binary.
        cores:     Number of parallel Cargo jobs.

    Returns:
        Path to the directory containing the compiled binary.

    Raises:
        RuntimeError: On any build failure, including missing Cargo.
    """
    try:
        log(f"\n{'='*60}\n")
        log(f"COMPILING ELECTRS {version}\n")
        log(f"{'='*60}\n")

        env = setup_build_environment()

        # Verify Rust before proceeding
        log("\n🔍 Verifying Rust installation...\n")
        cargo_check = subprocess.run(
            ["cargo", "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )

        if cargo_check.returncode != 0:
            error_msg = (
                "❌ Cargo not found in PATH!\n\n"
                "Electrs requires Rust/Cargo to compile.\n\n"
                "Please:\n"
                "1. Click 'Check & Install Dependencies' button\n"
                "2. Ensure Rust is installed\n"
                "3. Restart this application\n\n"
                f"Current PATH: {env['PATH'][:200]}...\n"
            )
            log(error_msg)
            show_message("showerror", "Rust Not Found", error_msg)
            raise RuntimeError("Cargo not found - cannot compile Electrs")

        log(f"✓ Cargo found: {cargo_check.stdout.strip()}\n")

        rustc_check = subprocess.run(
            ["rustc", "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        )
        if rustc_check.returncode == 0:
            log(f"✓ Rustc found: {rustc_check.stdout.strip()}\n")
        else:
            log("⚠️  Warning: rustc check failed, but cargo found. Proceeding...\n")

        version_clean = version.lstrip('v')
        src_dir = os.path.join(build_dir, f"electrs-{version_clean}")
        os.makedirs(build_dir, exist_ok=True)

        # Clone or refresh source
        if not os.path.exists(src_dir):
            log(f"\n📥 Cloning Electrs repository...\n")
            run_command(
                f"git clone --depth 1 --branch {version} {ELECTRS_REPO} {src_dir}",
                cwd=build_dir, env=env,
            )
            log(f"✓ Source cloned to {src_dir}\n")
        else:
            log(f"✓ Source directory already exists: {src_dir}\n")
            log(f"📥 Updating to {version}...\n")
            run_command(f"git fetch --depth 1 origin tag {version}", cwd=src_dir, env=env)
            run_command(f"git checkout {version}", cwd=src_dir, env=env)
            log(f"✓ Updated to {version}\n")

        log(f"\n🔧 Building with Cargo ({cores} jobs)...\n")
        log(f"Environment details:\n")
        log(f"  PATH: {env['PATH'][:150]}...\n")
        if 'LIBCLANG_PATH' in env:
            log(f"  LIBCLANG_PATH: {env['LIBCLANG_PATH']}\n")

        run_command(f"cargo build --release --jobs {cores}", cwd=src_dir, env=env)

        # Locate and copy the binary
        log(f"\n📋 Collecting binaries...\n")
        binary = os.path.join(src_dir, "target", "release", "electrs")

        if not os.path.exists(binary):
            raise RuntimeError(f"Electrs binary not found at expected location: {binary}")

        output_dir = os.path.join(build_dir, "binaries", f"electrs-{version_clean}")
        copy_binaries(src_dir, output_dir, [binary])

        log(f"\n{'='*60}\n")
        log(f"✅ ELECTRS {version} COMPILED SUCCESSFULLY!\n")
        log(f"{'='*60}\n")
        log(f"\n📍 Binary location: {output_dir}/electrs\n\n")

        return output_dir

    except Exception as e:
        log(f"\n❌ Error compiling Electrs: {e}\n")
        log(f"\nFull traceback:\n{traceback.format_exc()}\n")
        raise


# ================== ORCHESTRATION ==================

def compile_selected() -> None:
    """Read the current GUI form values and start the appropriate compilation(s).

    Spawns a daemon thread so the GUI remains responsive.
    Designed to be passed directly as a Tkinter Button command.
    """
    # Snapshot form state on the main thread before handing off
    target      = state.target_var.get()          # type: ignore[union-attr]
    cores       = state.cores_var.get()           # type: ignore[union-attr]
    build_dir   = state.build_dir_var.get()       # type: ignore[union-attr]
    bitcoin_ver = state.bitcoin_version_var.get() # type: ignore[union-attr]
    electrs_ver = state.electrs_version_var.get() # type: ignore[union-attr]

    def task() -> None:
        try:
            set_progress(0)
            state.compile_btn.config(state="disabled")  # type: ignore[union-attr]

            # Guard: versions must be loaded
            if target in ("Bitcoin", "Both"):
                if not bitcoin_ver or bitcoin_ver == "Loading...":
                    show_message("showerror", "Error",
                                 "Please wait for Bitcoin versions to load, or click Refresh")
                    return

            if target in ("Electrs", "Both"):
                if not electrs_ver or electrs_ver == "Loading...":
                    show_message("showerror", "Error",
                                 "Please wait for Electrs versions to load, or click Refresh")
                    return

            output_dirs: list[str] = []

            if target in ("Bitcoin", "Both"):
                set_progress(10)
                output_dirs.append(compile_bitcoin_source(bitcoin_ver, build_dir, cores))
                set_progress(50)

            if target in ("Electrs", "Both"):
                set_progress(60 if target == "Both" else 10)
                output_dirs.append(compile_electrs_source(electrs_ver, build_dir, cores))
                set_progress(100)

            set_progress(100)

            msg = f"✅ {target} compilation completed successfully!\n\nBinaries saved to:\n"
            for d in output_dirs:
                msg += f"• {d}\n"

            show_message("showinfo", "Compilation Complete", msg)

        except Exception as e:
            log(f"\n❌ Compilation failed: {e}\n")
            show_message("showerror", "Compilation Failed", str(e))
        finally:
            state.compile_btn.config(state="normal")  # type: ignore[union-attr]
            set_progress(0)

    threading.Thread(target=task, daemon=True).start()
