"""
gui.py
------
Creates and configures the main Tkinter window.

create_gui() populates the state module with live widget references, then
returns the root window so main.py can start the event loop.

Version-refresh callbacks live here too because they directly manipulate
the combo-box widgets.
"""

import multiprocessing
import platform
import threading
import tkinter as tk
from tkinter import filedialog, ttk

import state
from builder import compile_selected
from config import BREW_PREFIX, DEFAULT_BUILD_DIR, is_pyinstaller
from dependencies import check_dependencies
from gui_helpers import log, show_message
from versions import get_bitcoin_versions, get_electrs_versions


# ================== VERSION REFRESH ==================

def refresh_bitcoin_versions() -> None:
    """Fetch Bitcoin release tags and populate the version combo-box.

    Safe to call from a background thread.
    """
    log("\n📡 Fetching Bitcoin versions from GitHub...\n")
    versions = get_bitcoin_versions()
    if versions:
        state.bitcoin_combo.configure(values=versions)  # type: ignore[union-attr]
        if state.bitcoin_version_var.get() not in versions:  # type: ignore[union-attr]
            state.bitcoin_version_var.set(versions[0])       # type: ignore[union-attr]
        log(f"✓ Loaded {len(versions)} Bitcoin versions\n")
    else:
        log("⚠️  Could not fetch Bitcoin versions (check internet connection)\n")
        show_message("showwarning", "Network Error",
                     "Could not fetch Bitcoin versions. Check your internet connection.")


def refresh_electrs_versions() -> None:
    """Fetch Electrs release tags and populate the version combo-box.

    Safe to call from a background thread.
    """
    log("\n📡 Fetching Electrs versions from GitHub...\n")
    versions = get_electrs_versions()
    if versions:
        state.electrs_combo.configure(values=versions)  # type: ignore[union-attr]
        if state.electrs_version_var.get() not in versions:  # type: ignore[union-attr]
            state.electrs_version_var.set(versions[0])       # type: ignore[union-attr]
        log(f"✓ Loaded {len(versions)} Electrs versions\n")
    else:
        log("⚠️  Could not fetch Electrs versions (check internet connection)\n")
        show_message("showwarning", "Network Error",
                     "Could not fetch Electrs versions. Check your internet connection.")


def _initial_version_load() -> None:
    """Load both version lists once the GUI is fully initialised."""
    def task() -> None:
        refresh_bitcoin_versions()
        refresh_electrs_versions()
    threading.Thread(target=task, daemon=True).start()


# ================== WINDOW CONSTRUCTION ==================

def create_gui() -> tk.Tk:
    """Build the main window, populate the state module, and return the root."""

    root = tk.Tk()
    root.title("Bitcoin & Electrs Compiler for macOS")
    root.geometry("900x800")
    root.protocol("WM_DELETE_WINDOW", root.quit)

    # macOS: bring window to front on launch
    if platform.system() == 'Darwin':
        try:
            root.lift()
            root.attributes('-topmost', True)
            root.after_idle(root.attributes, '-topmost', False)
        except Exception:
            pass

    # ---- Populate state before any widget is used ----
    state.root = root

    # -- Header --
    ttk.Label(root, text="Bitcoin Core & Electrs Compiler",
              font=("Arial", 16, "bold")).pack(pady=10)

    # -- Step 1: Dependencies --
    dep_frame = ttk.Frame(root)
    dep_frame.pack(pady=10)
    ttk.Label(dep_frame, text="Step 1:", font=("Arial", 10, "bold")).pack(side="left", padx=5)
    ttk.Button(dep_frame, text="Check & Install Dependencies",
               command=check_dependencies).pack(side="left")

    ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=10)

    # -- Step 2: Target / cores / build dir --
    target_frame = ttk.LabelFrame(root, text="Step 2: Select What to Compile", padding=10)
    target_frame.pack(fill="x", padx=20, pady=5)

    ttk.Label(target_frame, text="Target:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
    state.target_var = tk.StringVar(value="Bitcoin")
    ttk.Combobox(
        target_frame,
        values=["Bitcoin", "Electrs", "Both"],
        textvariable=state.target_var,
        state="readonly",
        width=15,
    ).grid(row=0, column=1, sticky="w", padx=5, pady=5)

    ttk.Label(target_frame, text="CPU Cores:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
    state.cores_var = tk.IntVar(value=max(1, multiprocessing.cpu_count() - 1))
    ttk.Spinbox(
        target_frame,
        from_=1,
        to=multiprocessing.cpu_count(),
        textvariable=state.cores_var,
        width=5,
    ).grid(row=0, column=3, sticky="w", padx=5, pady=5)
    ttk.Label(
        target_frame,
        text=f"(max: {multiprocessing.cpu_count()})",
        font=("Arial", 9),
    ).grid(row=0, column=4, sticky="w", padx=2, pady=5)

    ttk.Label(target_frame, text="Build Directory:").grid(
        row=1, column=0, sticky="w", padx=5, pady=5)
    state.build_dir_var = tk.StringVar(value=DEFAULT_BUILD_DIR)
    ttk.Entry(target_frame, textvariable=state.build_dir_var, width=40).grid(
        row=1, column=1, columnspan=3, sticky="ew", padx=5, pady=5)
    ttk.Button(
        target_frame,
        text="Browse",
        command=lambda: state.build_dir_var.set(  # type: ignore[union-attr]
            filedialog.askdirectory(initialdir=state.build_dir_var.get())  # type: ignore[union-attr]
        ),
    ).grid(row=1, column=4, padx=5, pady=5)

    # -- Step 3: Versions --
    version_frame = ttk.LabelFrame(root, text="Step 3: Select Versions", padding=10)
    version_frame.pack(fill="x", padx=20, pady=5)

    ttk.Label(version_frame, text="Bitcoin Version:").grid(
        row=0, column=0, sticky="w", padx=5, pady=5)
    state.bitcoin_version_var = tk.StringVar(value="Loading...")
    state.bitcoin_combo = ttk.Combobox(
        version_frame,
        values=["Loading..."],
        textvariable=state.bitcoin_version_var,
        state="readonly",
        width=20,
    )
    state.bitcoin_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
    ttk.Button(
        version_frame,
        text="Refresh",
        command=lambda: threading.Thread(
            target=refresh_bitcoin_versions, daemon=True).start(),
    ).grid(row=0, column=2, padx=5, pady=5)

    ttk.Label(version_frame, text="Electrs Version:").grid(
        row=1, column=0, sticky="w", padx=5, pady=5)
    state.electrs_version_var = tk.StringVar(value="Loading...")
    state.electrs_combo = ttk.Combobox(
        version_frame,
        values=["Loading..."],
        textvariable=state.electrs_version_var,
        state="readonly",
        width=20,
    )
    state.electrs_combo.grid(row=1, column=1, sticky="w", padx=5, pady=5)
    ttk.Button(
        version_frame,
        text="Refresh",
        command=lambda: threading.Thread(
            target=refresh_electrs_versions, daemon=True).start(),
    ).grid(row=1, column=2, padx=5, pady=5)

    # -- Progress bar --
    progress_frame = ttk.Frame(root)
    progress_frame.pack(fill="x", padx=20, pady=10)
    ttk.Label(progress_frame, text="Progress:").pack(anchor="w")
    state.progress_var = tk.DoubleVar()
    state.progress = ttk.Progressbar(
        progress_frame, variable=state.progress_var, maximum=100)
    state.progress.pack(fill="x", pady=5)

    # -- Build log terminal --
    log_frame = ttk.LabelFrame(root, text="Build Log", padding=5)
    log_frame.pack(fill="both", expand=True, padx=20, pady=5)

    log_text_frame = tk.Frame(log_frame)
    log_text_frame.pack(fill="both", expand=True)

    state.log_text = tk.Text(
        log_text_frame,
        height=15,
        wrap="none",
        bg="#1e1e1e",
        fg="#00ff00",
        font=("Courier", 10),
    )
    state.log_text.pack(side="left", fill="both", expand=True)

    scrollbar_y = ttk.Scrollbar(log_text_frame, command=state.log_text.yview)
    scrollbar_y.pack(side="right", fill="y")
    state.log_text.config(yscrollcommand=scrollbar_y.set)

    scrollbar_x = ttk.Scrollbar(log_frame, orient="horizontal",
                                 command=state.log_text.xview)
    scrollbar_x.pack(fill="x")
    state.log_text.config(xscrollcommand=scrollbar_x.set)

    # -- Compile button --
    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10)
    state.compile_btn = ttk.Button(
        button_frame,
        text="🚀 Start Compilation",
        command=compile_selected,
    )
    state.compile_btn.pack()

    # -- Status bar --
    status_frame = ttk.Frame(root)
    status_frame.pack(fill="x", side="bottom")
    ttk.Label(
        status_frame,
        text=(
            f"System: macOS {platform.mac_ver()[0]} | "
            f"Homebrew: {BREW_PREFIX if BREW_PREFIX else 'Not Found'} | "
            f"CPUs: {multiprocessing.cpu_count()}"
        ),
        relief="sunken",
        anchor="w",
    ).pack(fill="x")

    # -- Initial log messages --
    log("=" * 60 + "\n")
    log("Bitcoin Core & Electrs Compiler\n")
    log("=" * 60 + "\n")
    log(f"System: macOS {platform.mac_ver()[0]}\n")
    log(f"Homebrew: {BREW_PREFIX if BREW_PREFIX else 'Not Found'}\n")
    log(f"CPU Cores: {multiprocessing.cpu_count()}\n")
    if is_pyinstaller():
        log("Running as: PyInstaller Bundle\n")
    log("=" * 60 + "\n\n")
    log("👉 Click 'Check & Install Dependencies' to begin\n\n")
    log("📝 Note: Both Bitcoin and Electrs pull source from GitHub\n\n")

    # Defer version loading until after the event loop starts
    root.after(100, _initial_version_load)

    return root
