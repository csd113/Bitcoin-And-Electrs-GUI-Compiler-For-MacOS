import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import requests
import multiprocessing
import shutil
import re
import platform

# ================== FIX GUI APP PATH ==================
os.environ["PATH"] = (
    "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:"
    + os.path.expanduser("~/.cargo/bin")
)

# ================== CONFIG ==================
BITCOIN_API = "https://api.github.com/repos/bitcoin/bitcoin/releases"
ELECTRS_API = "https://api.github.com/repos/romanz/electrs/releases"
DEFAULT_BUILD_DIR = os.path.expanduser("~/Downloads/bitcoin_builds")

# ================== HOMEBREW DETECTION ==================
def find_brew():
    """Find Homebrew installation (Apple Silicon or Intel Mac)"""
    for path in ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]:
        if os.path.isfile(path):
            return path
    return None

BREW = find_brew()

# Determine Homebrew prefix based on architecture
if BREW:
    if "/opt/homebrew" in BREW:
        BREW_PREFIX = "/opt/homebrew"
    else:
        BREW_PREFIX = "/usr/local"
else:
    BREW_PREFIX = None

# ================== GUI HELPERS ==================
def log(msg):
    """Thread-safe logging to GUI text widget"""
    # Only log if the widget exists (GUI is initialized)
    try:
        if 'log_text' in globals() and log_text.winfo_exists():
            log_text.after(0, lambda: (
                log_text.insert("end", msg),
                log_text.see("end")
            ))
    except:
        # Silently fail during initialization
        pass

def set_progress(val):
    """Thread-safe progress bar update"""
    progress.after(0, lambda: progress_var.set(val))

def run_command(cmd, cwd=None, env=None):
    """Execute shell command and log output in real-time"""
    log(f"\n$ {cmd}\n")
    if env is None:
        env = os.environ.copy()
    
    process = subprocess.Popen(
        cmd,
        shell=True,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env
    )
    
    for line in process.stdout:
        log(line)
    
    process.wait()
    
    if process.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")
    
    return process.returncode

# ================== VERSION LOGIC ==================
def parse_version(tag):
    """Parse version number from git tag"""
    # Remove 'v' prefix if present
    tag = tag.lstrip('v')
    m = re.match(r"(\d+)\.(\d+)", tag)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

def use_cmake(version):
    """Determine if version uses CMake (v25+) or Autotools"""
    major, _ = parse_version(version)
    return major >= 25

def get_bitcoin_versions():
    """Fetch latest Bitcoin Core releases from GitHub"""
    try:
        r = requests.get(BITCOIN_API, timeout=10)
        r.raise_for_status()
        versions = []
        for rel in r.json():
            tag = rel["tag_name"]
            # Skip release candidates
            if "rc" in tag.lower():
                continue
            versions.append(tag)
            if len(versions) == 10:
                break
        log(f"Found {len(versions)} Bitcoin versions\n")
        return versions
    except Exception as e:
        log(f"Failed to fetch Bitcoin versions: {e}\n")
        # Return empty list on failure, don't show error dialog during init
        return []

def get_electrs_versions():
    """Fetch latest Electrs releases from GitHub"""
    try:
        r = requests.get(ELECTRS_API, timeout=10)
        r.raise_for_status()
        versions = []
        for rel in r.json():
            tag = rel["tag_name"]
            # Skip release candidates
            if "rc" in tag.lower():
                continue
            versions.append(tag)
            if len(versions) == 10:
                break
        log(f"Found {len(versions)} Electrs versions\n")
        return versions
    except Exception as e:
        log(f"Failed to fetch Electrs versions: {e}\n")
        # Return empty list on failure, don't show error dialog during init
        return []

# ================== ENVIRONMENT SETUP ==================
def setup_build_environment():
    """Setup environment variables for building"""
    env = os.environ.copy()
    
    if not BREW_PREFIX:
        return env
    
    # Add Homebrew to PATH
    env["PATH"] = f"{BREW_PREFIX}/bin:{env['PATH']}"
    
    # Add Cargo to PATH
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if os.path.exists(cargo_bin):
        env["PATH"] = f"{cargo_bin}:{env['PATH']}"
    
    # LLVM setup for Electrs
    llvm_prefix = f"{BREW_PREFIX}/opt/llvm"
    if os.path.isdir(llvm_prefix):
        env["PATH"] = f"{llvm_prefix}/bin:{env['PATH']}"
        env["LIBCLANG_PATH"] = f"{llvm_prefix}/lib"
        env["DYLD_LIBRARY_PATH"] = f"{llvm_prefix}/lib"
    
    # Berkeley DB for Bitcoin
    bdb_prefix = f"{BREW_PREFIX}/opt/berkeley-db@4"
    if os.path.isdir(bdb_prefix):
        env["BDB_PREFIX"] = bdb_prefix
    
    # OpenSSL
    openssl_prefix = f"{BREW_PREFIX}/opt/openssl"
    if os.path.isdir(openssl_prefix):
        env["OPENSSL_ROOT_DIR"] = openssl_prefix
        env["PKG_CONFIG_PATH"] = f"{openssl_prefix}/lib/pkgconfig:{env.get('PKG_CONFIG_PATH', '')}"
    
    return env

# ================== DEPENDENCY CHECKER ==================
def check_dependencies():
    """Check and install required system dependencies"""
    def task():
        try:
            log("\n=== Checking System Dependencies ===\n")
            
            if not BREW:
                log("❌ Homebrew not found!\n")
                log("Please install Homebrew from https://brew.sh\n")
                messagebox.showerror("Missing Dependency", "Homebrew not found! Please install from https://brew.sh")
                return

            log(f"✓ Homebrew found at: {BREW}\n")

            # Required Homebrew packages
            brew_packages = [
                "automake", "libtool", "pkg-config", "boost",
                "berkeley-db@4", "openssl", "miniupnpc",
                "zeromq", "sqlite", "python", "cmake", "llvm"
            ]

            log("\nChecking Homebrew packages...\n")
            missing = []
            for pkg in brew_packages:
                result = subprocess.run(
                    [BREW, "list", pkg],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.returncode != 0:
                    log(f"  ❌ {pkg} - not installed\n")
                    missing.append(pkg)
                else:
                    log(f"  ✓ {pkg}\n")

            if missing:
                log(f"\n⚠️  Missing packages: {', '.join(missing)}\n")
                if messagebox.askyesno(
                    "Install Missing Dependencies",
                    f"The following packages are missing:\n\n{chr(10).join(missing)}\n\nInstall now?"
                ):
                    for pkg in missing:
                        log(f"\n📦 Installing {pkg}...\n")
                        try:
                            run_command(f"{BREW} install {pkg}")
                            log(f"✓ {pkg} installed successfully\n")
                        except Exception as e:
                            log(f"❌ Failed to install {pkg}: {e}\n")
                else:
                    log("\n⚠️  Dependencies not installed. Compilation may fail.\n")
            else:
                log("\n✓ All Homebrew packages are installed!\n")

            # Check Rust and Cargo
            log("\nChecking Rust toolchain...\n")
            env = setup_build_environment()

            result = subprocess.run(
                ["rustc", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            if result.returncode != 0:
                log("❌ Rust not found. Installing via Homebrew...\n")
                try:
                    run_command(f"{BREW} install rust")
                    log("✓ Rust installed successfully\n")
                except Exception as e:
                    log(f"❌ Failed to install Rust: {e}\n")
            else:
                log(f"✓ Rust found: {result.stdout.strip()}\n")

            result = subprocess.run(
                ["cargo", "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )
            
            if result.returncode != 0:
                log("❌ Cargo not found. Installing via Homebrew...\n")
                try:
                    run_command(f"{BREW} install rust")
                    log("✓ Cargo installed successfully\n")
                except Exception as e:
                    log(f"❌ Failed to install Cargo: {e}\n")
            else:
                log(f"✓ Cargo found: {result.stdout.strip()}\n")

            log("\n=== Dependency Check Complete ===\n")
            messagebox.showinfo(
                "Dependency Check",
                "All dependencies checked!\n\nYou can now proceed with compilation."
            )

        except Exception as e:
            log(f"\n❌ Error during dependency check: {e}\n")
            messagebox.showerror("Error", f"Dependency check failed: {e}")

    threading.Thread(target=task, daemon=True).start()

def refresh_bitcoin_versions():
    """Refresh Bitcoin version list in dropdown"""
    log("\n📡 Fetching Bitcoin versions from GitHub...\n")
    versions = get_bitcoin_versions()
    if versions:
        bitcoin_combo.configure(values=versions)
        if bitcoin_version_var.get() not in versions:
            bitcoin_version_var.set(versions[0])
        log(f"✓ Loaded {len(versions)} Bitcoin versions\n")
    else:
        log("⚠️  Could not fetch Bitcoin versions (check internet connection)\n")
        messagebox.showwarning("Network Error", "Could not fetch Bitcoin versions. Check your internet connection.")

def refresh_electrs_versions():
    """Refresh Electrs version list in dropdown"""
    log("\n📡 Fetching Electrs versions from GitHub...\n")
    versions = get_electrs_versions()
    if versions:
        electrs_combo.configure(values=versions)
        if electrs_version_var.get() not in versions:
            electrs_version_var.set(versions[0])
        log(f"✓ Loaded {len(versions)} Electrs versions\n")
    else:
        log("⚠️  Could not fetch Electrs versions (check internet connection)\n")
        messagebox.showwarning("Network Error", "Could not fetch Electrs versions. Check your internet connection.")

def initial_version_load():
    """Load versions after GUI is ready"""
    def task():
        refresh_bitcoin_versions()
        refresh_electrs_versions()
    threading.Thread(target=task, daemon=True).start()

# ================== BUILD FUNCTIONS ==================
def copy_binaries(src_dir, dest_dir, binary_files):
    """Copy compiled binaries to destination directory"""
    os.makedirs(dest_dir, exist_ok=True)
    copied = []
    
    for binary in binary_files:
        if os.path.exists(binary):
            dest = os.path.join(dest_dir, os.path.basename(binary))
            shutil.copy2(binary, dest)
            copied.append(dest)
            log(f"✓ Copied: {os.path.basename(binary)} → {dest}\n")
    
    return copied

def compile_bitcoin_source(version, build_dir, cores):
    """Compile Bitcoin Core from source"""
    try:
        log(f"\n{'='*60}\n")
        log(f"COMPILING BITCOIN CORE {version}\n")
        log(f"{'='*60}\n")
        
        version_clean = version.lstrip('v')
        src_dir = os.path.join(build_dir, f"bitcoin-{version_clean}")
        
        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        
        # Download source if not exists
        if not os.path.exists(src_dir):
            log(f"\n📥 Downloading Bitcoin Core {version}...\n")
            tarball = f"bitcoin-{version_clean}.tar.gz"
            run_command(
                f"curl -L https://github.com/bitcoin/bitcoin/archive/refs/tags/{version}.tar.gz -o {tarball}",
                cwd=build_dir
            )
            log(f"\n📦 Extracting {tarball}...\n")
            run_command(f"tar xzf {tarball}", cwd=build_dir)
            log(f"✓ Source extracted to {src_dir}\n")
        else:
            log(f"✓ Source directory already exists: {src_dir}\n")

        # Setup environment
        env = setup_build_environment()
        
        # Determine build method
        if use_cmake(version):
            log(f"\n🔨 Building with CMake (Bitcoin Core {version})...\n")
            build_subdir = os.path.join(src_dir, "build")
            os.makedirs(build_subdir, exist_ok=True)
            
            # Configure with CMake
            cmake_opts = []
            if "BDB_PREFIX" in env:
                cmake_opts.append(f"-DBDB_PREFIX={env['BDB_PREFIX']}")
            if "OPENSSL_ROOT_DIR" in env:
                cmake_opts.append(f"-DOPENSSL_ROOT_DIR={env['OPENSSL_ROOT_DIR']}")
            
            cmake_cmd = f"cmake .. {' '.join(cmake_opts)}"
            log(f"\n⚙️  Configuring...\n")
            run_command(cmake_cmd, cwd=build_subdir, env=env)
            
            log(f"\n🔧 Compiling with {cores} cores...\n")
            run_command(f"make -j{cores}", cwd=build_subdir, env=env)
            
            # Binary locations for CMake build
            binary_dir = os.path.join(build_subdir, "src")
            binaries = [
                os.path.join(binary_dir, "bitcoind"),
                os.path.join(binary_dir, "bitcoin-cli"),
                os.path.join(binary_dir, "bitcoin-tx"),
                os.path.join(binary_dir, "bitcoin-wallet"),
                os.path.join(binary_dir, "bitcoin-util"),
            ]
            
        else:
            log(f"\n🔨 Building with Autotools (Bitcoin Core {version})...\n")
            
            # Configure options
            config_opts = []
            if "BDB_PREFIX" in env:
                config_opts.append(f"BDB_LIBS=\"-L{env['BDB_PREFIX']}/lib -ldb_cxx-4.8\"")
                config_opts.append(f"BDB_CFLAGS=\"-I{env['BDB_PREFIX']}/include\"")
            
            config_cmd = f"./configure {' '.join(config_opts)}"
            
            log(f"\n⚙️  Running autogen.sh...\n")
            run_command("./autogen.sh", cwd=src_dir, env=env)
            
            log(f"\n⚙️  Configuring...\n")
            run_command(config_cmd, cwd=src_dir, env=env)
            
            log(f"\n🔧 Compiling with {cores} cores...\n")
            run_command(f"make -j{cores}", cwd=src_dir, env=env)
            
            # Binary locations for Autotools build
            binary_dir = os.path.join(src_dir, "src")
            binaries = [
                os.path.join(binary_dir, "bitcoind"),
                os.path.join(binary_dir, "bitcoin-cli"),
                os.path.join(binary_dir, "bitcoin-tx"),
                os.path.join(binary_dir, "bitcoin-wallet"),
            ]
        
        # Copy binaries to output directory
        log(f"\n📋 Collecting binaries...\n")
        output_dir = os.path.join(build_dir, "binaries", f"bitcoin-{version_clean}")
        copied = copy_binaries(src_dir, output_dir, binaries)
        
        log(f"\n{'='*60}\n")
        log(f"✅ BITCOIN CORE {version} COMPILED SUCCESSFULLY!\n")
        log(f"{'='*60}\n")
        log(f"\n📍 Binaries location: {output_dir}\n")
        log(f"   Found {len(copied)} binaries\n\n")
        
        return output_dir

    except Exception as e:
        log(f"\n❌ Error compiling Bitcoin: {e}\n")
        raise

def compile_electrs_source(version, build_dir, cores):
    """Compile Electrs from source"""
    try:
        log(f"\n{'='*60}\n")
        log(f"COMPILING ELECTRS {version}\n")
        log(f"{'='*60}\n")
        
        version_clean = version.lstrip('v')
        src_dir = os.path.join(build_dir, f"electrs-{version_clean}")
        
        # Create build directory
        os.makedirs(build_dir, exist_ok=True)
        
        # Download source if not exists
        if not os.path.exists(src_dir):
            log(f"\n📥 Downloading Electrs {version}...\n")
            tarball = f"electrs-{version_clean}.tar.gz"
            run_command(
                f"curl -L https://github.com/romanz/electrs/archive/refs/tags/{version}.tar.gz -o {tarball}",
                cwd=build_dir
            )
            log(f"\n📦 Extracting {tarball}...\n")
            run_command(f"tar xzf {tarball}", cwd=build_dir)
            log(f"✓ Source extracted to {src_dir}\n")
        else:
            log(f"✓ Source directory already exists: {src_dir}\n")

        # Setup environment with LLVM
        env = setup_build_environment()
        
        log(f"\n🔧 Building with Cargo ({cores} jobs)...\n")
        run_command(f"cargo build --release --jobs {cores}", cwd=src_dir, env=env)
        
        # Copy binary
        log(f"\n📋 Collecting binaries...\n")
        binary = os.path.join(src_dir, "target", "release", "electrs")
        output_dir = os.path.join(build_dir, "binaries", f"electrs-{version_clean}")
        copied = copy_binaries(src_dir, output_dir, [binary])
        
        log(f"\n{'='*60}\n")
        log(f"✅ ELECTRS {version} COMPILED SUCCESSFULLY!\n")
        log(f"{'='*60}\n")
        log(f"\n📍 Binary location: {output_dir}/electrs\n\n")
        
        return output_dir

    except Exception as e:
        log(f"\n❌ Error compiling Electrs: {e}\n")
        raise

def compile_selected():
    """Main compilation function triggered by GUI button"""
    target = target_var.get()
    cores = cores_var.get()
    build_dir = build_dir_var.get()
    bitcoin_ver = bitcoin_version_var.get()
    electrs_ver = electrs_version_var.get()

    def task():
        try:
            set_progress(0)
            compile_btn.config(state="disabled")
            
            # Validate versions are loaded
            if target in ["Bitcoin", "Both"]:
                if not bitcoin_ver or bitcoin_ver == "Loading...":
                    messagebox.showerror("Error", "Please wait for Bitcoin versions to load, or click Refresh")
                    return
            
            if target in ["Electrs", "Both"]:
                if not electrs_ver or electrs_ver == "Loading...":
                    messagebox.showerror("Error", "Please wait for Electrs versions to load, or click Refresh")
                    return
            
            output_dirs = []
            
            if target in ["Bitcoin", "Both"]:
                set_progress(10)
                output_dir = compile_bitcoin_source(bitcoin_ver, build_dir, cores)
                output_dirs.append(output_dir)
                set_progress(50)
            
            if target in ["Electrs", "Both"]:
                set_progress(60 if target == "Both" else 10)
                output_dir = compile_electrs_source(electrs_ver, build_dir, cores)
                output_dirs.append(output_dir)
                set_progress(100)
            
            set_progress(100)
            
            msg = f"✅ {target} compilation completed successfully!\n\n"
            msg += "Binaries saved to:\n"
            for d in output_dirs:
                msg += f"• {d}\n"
            
            messagebox.showinfo("Compilation Complete", msg)
            
        except Exception as e:
            log(f"\n❌ Compilation failed: {e}\n")
            messagebox.showerror("Compilation Failed", str(e))
        finally:
            compile_btn.config(state="normal")
            set_progress(0)

    threading.Thread(target=task, daemon=True).start()

# ================== GUI ==================
root = tk.Tk()
root.title("Bitcoin & Electrs Compiler for macOS")
root.geometry("900x800")

# Header
header = ttk.Label(
    root,
    text="Bitcoin Core & Electrs Compiler",
    font=("Arial", 16, "bold")
)
header.pack(pady=10)

# Dependency check button
dep_frame = ttk.Frame(root)
dep_frame.pack(pady=10)
ttk.Label(dep_frame, text="Step 1:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
ttk.Button(
    dep_frame,
    text="Check & Install Dependencies",
    command=check_dependencies
).pack(side="left")

# Separator
ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=10)

# Target selection
target_frame = ttk.LabelFrame(root, text="Step 2: Select What to Compile", padding=10)
target_frame.pack(fill="x", padx=20, pady=5)

ttk.Label(target_frame, text="Target:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
target_var = tk.StringVar(value="Bitcoin")
target_combo = ttk.Combobox(
    target_frame,
    values=["Bitcoin", "Electrs", "Both"],
    textvariable=target_var,
    state="readonly",
    width=15
)
target_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)

# CPU cores
ttk.Label(target_frame, text="CPU Cores:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
cores_var = tk.IntVar(value=max(1, multiprocessing.cpu_count() - 1))
cores_spinbox = ttk.Spinbox(
    target_frame,
    from_=1,
    to=multiprocessing.cpu_count(),
    textvariable=cores_var,
    width=5
)
cores_spinbox.grid(row=0, column=3, sticky="w", padx=5, pady=5)
ttk.Label(
    target_frame,
    text=f"(max: {multiprocessing.cpu_count()})",
    font=("Arial", 9)
).grid(row=0, column=4, sticky="w", padx=2, pady=5)

# Build directory
ttk.Label(target_frame, text="Build Directory:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
build_dir_var = tk.StringVar(value=DEFAULT_BUILD_DIR)
build_entry = ttk.Entry(target_frame, textvariable=build_dir_var, width=40)
build_entry.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
ttk.Button(
    target_frame,
    text="Browse",
    command=lambda: build_dir_var.set(filedialog.askdirectory(initialdir=build_dir_var.get()))
).grid(row=1, column=4, padx=5, pady=5)

# Version selection
version_frame = ttk.LabelFrame(root, text="Step 3: Select Versions", padding=10)
version_frame.pack(fill="x", padx=20, pady=5)

# Bitcoin version
ttk.Label(version_frame, text="Bitcoin Version:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
bitcoin_version_var = tk.StringVar(value="Loading...")
bitcoin_combo = ttk.Combobox(
    version_frame,
    values=["Loading..."],
    textvariable=bitcoin_version_var,
    state="readonly",
    width=20
)
bitcoin_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
ttk.Button(
    version_frame,
    text="Refresh",
    command=lambda: threading.Thread(target=refresh_bitcoin_versions, daemon=True).start()
).grid(row=0, column=2, padx=5, pady=5)

# Electrs version
ttk.Label(version_frame, text="Electrs Version:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
electrs_version_var = tk.StringVar(value="Loading...")
electrs_combo = ttk.Combobox(
    version_frame,
    values=["Loading..."],
    textvariable=electrs_version_var,
    state="readonly",
    width=20
)
electrs_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
ttk.Button(
    version_frame,
    text="Refresh",
    command=lambda: threading.Thread(target=refresh_electrs_versions, daemon=True).start()
).grid(row=1, column=2, padx=5, pady=5)

# Progress bar
progress_frame = ttk.Frame(root)
progress_frame.pack(fill="x", padx=20, pady=10)
ttk.Label(progress_frame, text="Progress:").pack(anchor="w")
progress_var = tk.DoubleVar()
progress = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
progress.pack(fill="x", pady=5)

# Log terminal
log_frame = ttk.LabelFrame(root, text="Build Log", padding=5)
log_frame.pack(fill="both", expand=True, padx=20, pady=5)

log_text_frame = tk.Frame(log_frame)
log_text_frame.pack(fill="both", expand=True)

log_text = tk.Text(
    log_text_frame,
    height=15,
    wrap="none",
    bg="#1e1e1e",
    fg="#00ff00",
    font=("Courier", 10)
)
log_text.pack(side="left", fill="both", expand=True)

scrollbar_y = ttk.Scrollbar(log_text_frame, command=log_text.yview)
scrollbar_y.pack(side="right", fill="y")
log_text.config(yscrollcommand=scrollbar_y.set)

scrollbar_x = ttk.Scrollbar(log_frame, orient="horizontal", command=log_text.xview)
scrollbar_x.pack(fill="x")
log_text.config(xscrollcommand=scrollbar_x.set)

# Compile button
button_frame = ttk.Frame(root)
button_frame.pack(pady=10)
compile_btn = ttk.Button(
    button_frame,
    text="🚀 Start Compilation",
    command=compile_selected
)
compile_btn.pack()

# Status bar
status_frame = ttk.Frame(root)
status_frame.pack(fill="x", side="bottom")
status_label = ttk.Label(
    status_frame,
    text=f"System: macOS {platform.mac_ver()[0]} | Homebrew: {BREW_PREFIX if BREW_PREFIX else 'Not Found'} | CPUs: {multiprocessing.cpu_count()}",
    relief="sunken",
    anchor="w"
)
status_label.pack(fill="x")

# Initial log message
log("=" * 60 + "\n")
log("Bitcoin Core & Electrs Compiler\n")
log("=" * 60 + "\n")
log(f"System: macOS {platform.mac_ver()[0]}\n")
log(f"Homebrew: {BREW_PREFIX if BREW_PREFIX else 'Not Found'}\n")
log(f"CPU Cores: {multiprocessing.cpu_count()}\n")
log("=" * 60 + "\n\n")
log("👉 Click 'Check & Install Dependencies' to begin\n\n")

# Load versions after GUI is ready
root.after(100, initial_version_load)

root.mainloop()
