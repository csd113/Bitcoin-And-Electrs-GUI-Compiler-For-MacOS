"""
gui_helpers.py
--------------
Thread-safe helpers that bridge background worker threads with the Tkinter
main thread.  All functions here are safe to call from *any* thread.

Also contains run_command(), which streams subprocess output to the log
widget in real time.
"""

import os
import subprocess
import threading
from tkinter import messagebox

import state


# ================== LOGGING ==================

def log(msg: str) -> None:
    """Append *msg* to the build-log widget (thread-safe)."""
    try:
        widget = state.log_text
        if widget is not None and widget.winfo_exists():
            widget.after(0, lambda: (
                widget.insert("end", msg),
                widget.see("end"),
            ))
    except Exception:
        pass  # Silently swallow errors during early initialisation


# ================== PROGRESS ==================

def set_progress(val: float) -> None:
    """Update the progress bar (thread-safe)."""
    if state.progress is not None:
        state.progress.after(0, lambda: state.progress_var.set(val))  # type: ignore[union-attr]


# ================== MESSAGEBOX WRAPPERS ==================

def show_message(kind: str, title: str, msg: str) -> None:
    """Fire-and-forget thread-safe wrapper for non-blocking messagebox dialogs.

    Args:
        kind:  Any messagebox function name — 'showerror', 'showinfo',
               'showwarning', etc.
        title: Dialog title.
        msg:   Dialog body text.
    """
    if state.root is not None:
        state.root.after(0, lambda: getattr(messagebox, kind)(title, msg))


def ask_yes_no_threadsafe(title: str, msg: str) -> bool:
    """Blocking thread-safe wrapper for messagebox.askyesno.

    Posts the dialog to the main thread, then blocks the *calling* thread
    until the user responds.  Returns the boolean answer.
    """
    result: list[bool | None] = [None]
    event = threading.Event()

    def _ask() -> None:
        result[0] = messagebox.askyesno(title, msg)
        event.set()

    if state.root is not None:
        state.root.after(0, _ask)
    event.wait()
    return bool(result[0])


# ================== COMMAND RUNNER ==================

def run_command(cmd: str, cwd: str | None = None, env: dict | None = None) -> int:
    """Execute a shell command and stream its output to the log widget.

    Args:
        cmd:  Shell command string.
        cwd:  Working directory for the subprocess.
        env:  Environment mapping; defaults to os.environ copy.

    Returns:
        The process return code (always 0 — raises on non-zero).

    Raises:
        RuntimeError: If the command exits with a non-zero return code.
    """
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
        env=env,
    )

    for line in process.stdout:  # type: ignore[union-attr]
        log(line)

    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"Command failed: {cmd}")

    return process.returncode
