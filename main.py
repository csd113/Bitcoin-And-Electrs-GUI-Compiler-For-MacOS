#!/usr/bin/env python3
"""
main.py
-------
Application entry point.

Responsible for:
  - PyInstaller multiprocessing freeze support
  - Creating the GUI
  - Starting the Tkinter event loop
  - Top-level exception handling
"""

import multiprocessing
import sys
import traceback
from tkinter import messagebox

from config import is_pyinstaller
from gui import create_gui


def main() -> None:
    """Create the GUI and start the event loop."""
    try:
        root = create_gui()
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        traceback.print_exc()
        try:
            messagebox.showerror(
                "Fatal Error",
                f"Application crashed:\n\n{e}\n\nCheck console for details.",
            )
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    if is_pyinstaller():
        multiprocessing.freeze_support()
    main()
