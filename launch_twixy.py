import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_MEIPASS = getattr(sys, "_MEIPASS", "")
if _MEIPASS and _MEIPASS not in sys.path:
    sys.path.insert(0, _MEIPASS)

# Dipendenze importate esplicitamente affinché PyInstaller includa tutto ciò che usa xtra_gui_core.pyc
import base64  # noqa: E402,F401
import calendar  # noqa: E402,F401
import concurrent.futures  # noqa: E402,F401
import ctypes  # noqa: E402,F401
import ctypes.util  # noqa: E402,F401
import ctypes.wintypes  # noqa: E402,F401
import datetime  # noqa: E402,F401
import http.server  # noqa: E402,F401
import importlib  # noqa: E402,F401
import io  # noqa: E402,F401
import json  # noqa: E402,F401
import math  # noqa: E402,F401
import queue  # noqa: E402,F401
import random  # noqa: E402,F401
import re  # noqa: E402,F401
import shutil  # noqa: E402,F401
import socket  # noqa: E402,F401
import ssl  # noqa: E402,F401
import subprocess  # noqa: E402,F401
import tempfile  # noqa: E402,F401
import threading  # noqa: E402,F401
import time  # noqa: E402,F401
import tkinter  # noqa: E402,F401
import tkinter.filedialog  # noqa: E402,F401
import tkinter.font  # noqa: E402,F401
import tkinter.messagebox  # noqa: E402,F401
import tkinter.ttk  # noqa: E402,F401
import urllib.parse  # noqa: E402,F401
import uuid  # noqa: E402,F401
import weakref  # noqa: E402,F401
import webbrowser  # noqa: E402,F401
import winreg  # noqa: E402,F401
import zipfile  # noqa: E402,F401

import customtkinter as ctk  # noqa: E402
import requests  # noqa: E402,F401
import requests.adapters  # noqa: E402,F401
import vlc  # noqa: E402,F401
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageTk  # noqa: E402,F401
import emote_engine  # noqa: E402,F401
import xtra_gui_core as _core  # noqa: E402


_orig_build_ui = _core.TwixyDesktopApp._build_enterprise_ui


def _patched_build_enterprise_ui(self):
    _orig_build_ui(self)
    try:
        if hasattr(self, "header") and self.header.winfo_exists():
            self.header.configure(border_width=0)
            for ch in self.header.winfo_children():
                pi = ch.place_info()
                if pi and pi.get("anchor") in ("w", "e"):
                    ch.place_configure(y=0)
            self.header_bottom_line = ctk.CTkFrame(
                self.header, fg_color=_core.C_BORDER, height=1, corner_radius=0
            )
            self.header_bottom_line.place(relx=0.0, rely=1.0, relwidth=1.0, anchor="sw")
            self.header_bottom_line.lift()
        if hasattr(self, "left_sidebar") and self.left_sidebar.winfo_exists():
            self.left_sidebar.configure(border_width=0)
            self.sidebar_right_line = ctk.CTkFrame(
                self.left_sidebar, fg_color=_core.C_BORDER, width=1, corner_radius=0
            )
            self.sidebar_right_line.place(relx=1.0, rely=0.0, relheight=1.0, anchor="ne")
    except Exception:
        pass


_core.TwixyDesktopApp._build_enterprise_ui = _patched_build_enterprise_ui


if __name__ == "__main__":
    app = _core.TwixyDesktopApp()
    app.mainloop()
