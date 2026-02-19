"""
state.py
--------
Shared mutable references to the live Tkinter widgets.

All values start as None and are assigned by gui.create_gui() before the
event loop starts.  Every other module imports from here so that there is
a single, authoritative source for the widget handles — no circular imports.
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional

# Main window
root: Optional[tk.Tk] = None

# Form variables (tk.Var objects)
target_var:          Optional[tk.StringVar] = None
cores_var:           Optional[tk.IntVar]    = None
build_dir_var:       Optional[tk.StringVar] = None
bitcoin_version_var: Optional[tk.StringVar] = None
electrs_version_var: Optional[tk.StringVar] = None

# Widgets
bitcoin_combo:  Optional[ttk.Combobox]   = None
electrs_combo:  Optional[ttk.Combobox]   = None
log_text:       Optional[tk.Text]        = None
progress_var:   Optional[tk.DoubleVar]   = None
progress:       Optional[ttk.Progressbar]= None
compile_btn:    Optional[ttk.Button]     = None
bitcoin_status: Optional[ttk.Label]      = None
electrs_status: Optional[ttk.Label]      = None
