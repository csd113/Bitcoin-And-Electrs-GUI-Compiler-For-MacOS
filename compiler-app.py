import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import requests
import os
import multiprocessing
import shutil
import re
import sys

# ================== CONFIG ==================
BITCOIN_API = "https://api.github.com/repos/bitcoin/bitcoin/releases"
ELECTRS_API = "https://api.github.com/repos/romanz/electrs/releases"
DEFAULT_BUILD_DIR = os.path.expanduser("~/Downloads")

# ================== HOMEBREW DETECTION ==================
def find_brew():
	paths = ["/opt/homebrew/bin/brew", "/usr/local/bin/brew"]
	for p in paths:
		if os.path.isfile(p):
			return p
	return None

BREW = find_brew()

# ================== GUI-SAFE HELPERS ==================
def log(msg):
	log_text.after(0, lambda: (
		log_text.insert("end", msg),
		log_text.see("end")
	))

def set_progress(val):
	progress.after(0, lambda: progress_var.set(val))

def run_command(cmd, cwd=None, progress_cb=None, env=None):
	log(f"\n$ {cmd}\n")
	if env is None:
		env = os.environ.copy()
		env["PATH"] = f"{os.path.expanduser('~/.cargo/bin')}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

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
		if progress_cb:
			progress_cb(line)

	process.wait()
	if process.returncode != 0:
		raise RuntimeError(cmd)

# ================== VERSION LOGIC ==================
def parse_version(tag):
	m = re.match(r"v?(\d+)\.(\d+)", tag)
	return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

def use_cmake(version):
	major, _ = parse_version(version)
	return major >= 25

def get_bitcoin_versions():
	r = requests.get(BITCOIN_API, timeout=10)
	r.raise_for_status()
	versions = []
	for rel in r.json():
		tag = rel["tag_name"]
		if "rc" in tag.lower():
			continue
		versions.append(tag)
		if len(versions) == 10:
			break
	return versions

def get_electrs_versions():
	r = requests.get(ELECTRS_API, timeout=10)
	r.raise_for_status()
	versions = []
	for rel in r.json():
		tag = rel["tag_name"]
		if "rc" in tag.lower():
			continue
		versions.append(tag)
		if len(versions) == 10:
			break
	return versions

# ================== DEPENDENCY CHECKER ==================
def check_dependencies():
	def task():
		try:
			log("Checking system dependencies...\n")

			if not BREW:
				log("Homebrew not found. Please install from https://brew.sh\n")
				messagebox.showerror("Missing Dependency", "Homebrew not found!")
				return

			brew_packages = [
				"automake", "libtool", "pkg-config", "boost",
				"berkeley-db@4", "openssl", "miniupnpc",
				"zeromq", "sqlite", "python", "cmake", "llvm", "curl"
			]

			missing = []
			for pkg in brew_packages:
				result = subprocess.run([BREW, "list", pkg], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
				if result.returncode != 0:
					missing.append(pkg)

			if missing:
				log(f"Missing packages: {', '.join(missing)}\n")
				if messagebox.askyesno(
					"Install Missing Dependencies",
					f"The following packages are missing:\n{', '.join(missing)}\nInstall now?"
				):
					for pkg in missing:
						log(f"Installing {pkg}...\n")
						run_command(f"{BREW} install {pkg}")
				else:
					log("Dependencies not installed. Compile may fail.\n")
			else:
				log("All brew dependencies are satisfied.\n")

			# Rust
			env = os.environ.copy()
			cargo_bin = os.path.expanduser("~/.cargo/bin")
			env["PATH"] = f"{cargo_bin}:{env.get('PATH','')}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

			result = subprocess.run(["rustc", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
			if result.returncode != 0:
				log("Rust not found. Installing via Homebrew...\n")
				run_command(f"{BREW} install rust")
			else:
				log(f"Rust found: {result.stdout.strip()}\n")

			result = subprocess.run(["cargo", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
			if result.returncode != 0:
				log("Cargo not found; installing via Homebrew...\n")
				run_command(f"{BREW} install rust")
			else:
				log(f"Cargo found: {result.stdout.strip()}\n")

			# LLVM for Electrs
			llvm_prefix = "/opt/homebrew/opt/llvm"
			if os.path.isdir(llvm_prefix):
				log(f"LLVM found at {llvm_prefix}\n")
				env["PATH"] = f"{llvm_prefix}/bin:" + env["PATH"]
				env["LIBCLANG_PATH"] = f"{llvm_prefix}/lib"
				env["DYLD_LIBRARY_PATH"] = f"{llvm_prefix}/lib"
			else:
				log("LLVM not found. Installing via Homebrew...\n")
				run_command(f"{BREW} install llvm")
				env["PATH"] = f"{llvm_prefix}/bin:" + env["PATH"]
				env["LIBCLANG_PATH"] = f"{llvm_prefix}/lib"
				env["DYLD_LIBRARY_PATH"] = f"{llvm_prefix}/lib"

			messagebox.showinfo("Dependency Check", "All dependencies for Bitcoin and Electrs are installed and ready!")

		except Exception as e:
			log(f"Error during dependency check: {e}\n")

	threading.Thread(target=task, daemon=True).start()

# ================== BUILD FUNCTIONS ==================
# (Keep all previous compile_bitcoin_source, compile_electrs_source, compile_selected, cleanup, refresh versions, GUI setup...)
# (Insert the full code as previously provided above here)

# ================== GUI ==================
# (Keep all GUI code from above, unchanged except replacing check_dependencies with this updated version)

# --- Final snippet for log and compile button ---
log_text = tk.Text(root, height=20, wrap="none")
log_text.pack(fill="both", expand=True, padx=15, pady=5)
scrollbar = ttk.Scrollbar(log_text, command=log_text.yview)
log_text.config(yscrollcommand=scrollbar.set)
scrollbar.pack(side="right", fill="y")

compile_btn = ttk.Button(root, text="Compile Selected", command=lambda: threading.Thread(target=compile_selected, daemon=True).start())
compile_btn.pack(pady=10)

root.mainloop()
