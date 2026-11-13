import os
import io
import re
import sys
import json
import math
import time
import uuid
import base64
import queue
import shutil
import socket
import ssl
import ctypes
from ctypes import wintypes
import random
import tempfile
import zipfile
import importlib
import threading
import subprocess
import webbrowser
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor, wait as futures_wait
import tkinter as tk
from tkinter import messagebox, filedialog

# =====================================================================
# 0. PRE-CONFIGURAZIONE DLL PRIMA DI 'import vlc'
# =====================================================================
APP_NAME = "Twixy"

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

CONFIG_FILE = os.path.join(APP_DIR, "twixy_config.json")
LOGO_PATH = os.path.join(APP_DIR, "logo.ico") if os.path.exists(os.path.join(APP_DIR, "logo.ico")) else os.path.join(BUNDLE_DIR, "logo.ico")
LOGO_PNG_PATH = os.path.join(APP_DIR, "logo.png") if os.path.exists(os.path.join(APP_DIR, "logo.png")) else os.path.join(BUNDLE_DIR, "logo.png")

VENDOR_VLC_DIR = os.path.join(APP_DIR, "vendor", "vlc")
BUNDLE_VLC_DIR = os.path.join(BUNDLE_DIR, "vendor", "vlc")
PORTABLE_VLC_DIR = os.path.join(APP_DIR, "vlc_portable")

VENDOR_MPV_DIR = os.path.join(APP_DIR, "vendor", "mpv")
BUNDLE_MPV_DIR = os.path.join(BUNDLE_DIR, "vendor", "mpv")


def find_vlc_directory(custom_dir=None):
    candidates = [custom_dir, APP_DIR, BUNDLE_DIR, VENDOR_VLC_DIR, BUNDLE_VLC_DIR]
    for pdir in [PORTABLE_VLC_DIR, VENDOR_VLC_DIR, BUNDLE_VLC_DIR]:
        if pdir and os.path.isdir(pdir):
            candidates.append(pdir)
            try:
                for sub in os.listdir(pdir):
                    sub_p = os.path.join(pdir, sub)
                    if os.path.isdir(sub_p):
                        candidates.append(sub_p)
            except Exception:
                pass

    if sys.platform.startswith("win"):
        try:
            import winreg
            for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
                for reg_path in [r"SOFTWARE\VideoLAN\VLC", r"SOFTWARE\WOW6432Node\VideoLAN\VLC"]:
                    try:
                        with winreg.OpenKey(hive, reg_path) as key:
                            inst_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                            if inst_dir and os.path.isdir(inst_dir):
                                candidates.append(inst_dir)
                    except OSError:
                        pass
        except Exception:
            pass

    for drive in ["C:", "D:", "E:"]:
        candidates.extend([
            os.path.join(drive, os.sep, "Program Files", "VideoLAN", "VLC"),
            os.path.join(drive, os.sep, "VLC"),
        ])

    is_py64 = sys.maxsize > 2**32
    for d in candidates:
        if not d or not os.path.isdir(d):
            continue
        dll = os.path.join(d, "libvlc.dll")
        if os.path.isfile(dll):
            if is_py64 and "(x86)" in d:
                continue
            return d
    return None


def pre_configure_vlc_environment():
    vlc_dir = find_vlc_directory()
    if vlc_dir and os.path.isdir(vlc_dir):
        dll_path = os.path.join(vlc_dir, "libvlc.dll")
        plugins_path = os.path.join(vlc_dir, "plugins")
        os.environ["PYTHON_VLC_MODULE_PATH"] = vlc_dir
        os.environ["PYTHON_VLC_LIB_PATH"] = dll_path
        if os.path.isdir(plugins_path):
            os.environ["VLC_PLUGIN_PATH"] = plugins_path
        os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(vlc_dir)
            except Exception:
                pass

pre_configure_vlc_environment()


def _ensure_packages():
    required = [
        ("requests", "requests"),
        ("vlc", "python-vlc"),
        ("customtkinter", "customtkinter"),
        ("PIL", "pillow")
    ]
    for mod_name, pip_name in required:
        try:
            __import__(mod_name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

if not getattr(sys, "frozen", False):
    _ensure_packages()

import requests
from requests.adapters import HTTPAdapter
import vlc
import customtkinter as ctk
from PIL import Image, ImageTk, ImageDraw, ImageFilter

for _p in (APP_DIR, BUNDLE_DIR):
    if _p and _p not in sys.path:
        sys.path.insert(0, _p)
from emote_engine import EmoteAndBadgeManager


# =====================================================================
# COSTANTI E PALETTE COLORI
# =====================================================================
GQL_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
TV_CLIENT_ID = "ue6666qo983tsx6so1t0vnawi233wa"
ANDROID_CLIENT_ID = "kd1unb4b3q4t58fwlpcbzcbnm76a8fp"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

VLC_PORTABLE_URLS = [
    "https://ftp.fau.de/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip",
    "https://mirror.init7.net/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip",
    "https://download.videolan.org/pub/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip"
]

C_BG_ROOT = ("#ECEEF3", "#09090b")
C_BG_SIDEBAR = ("#F2F3F7", "#101014")
C_BG_HEADER = ("#ECEEF3", "#121217")
C_BG_CARD = ("#FFFFFF", "#18181f")
C_BG_CARD_HOVER = ("#E2E4EC", "#22222c")
C_BG_INPUT = ("#E4E6EE", "#1e1e26")
C_CHAT_BG = ("#D6DBE6", "#101014")
C_VIDEO_LETTERBOX = ("#DFE3EC", "#000000")
C_SHADOW_OUTER = ("#D5DCEB", "#0a0a0e")
C_SHADOW_MID = ("#B5BFD5", "#050508")
C_SHADOW_INNER = ("#8E9AB6", "#010102")
C_BORDER = ("#D5D8E2", "#272732")
C_ACCENT = "#8b5cf6"
C_ACCENT_HOVER = "#7c3aed"
C_LIVE = "#ef4444"
C_GREEN = ("#047857", "#10b981")
C_GOLD = ("#b45309", "#f59e0b")
C_CYAN = ("#0369a1", "#06b6d4")
C_TEXT_MAIN = ("#18181b", "#f4f4f6")
C_TEXT_DIM = ("#52525b", "#9ca3af")


def _tk_color(c):
    if isinstance(c, (tuple, list)) and len(c) == 2:
        return c[0] if ctk.get_appearance_mode().lower() == "light" else c[1]
    return c


def _adapt_chat_color(raw_color, theme_mode=None):
    """Adatta i colori chat per garantire leggibilità elevata sia su tema Chiaro che Scuro."""
    col = _tk_color(raw_color)
    if not isinstance(col, str) or not col.startswith("#") or len(col) != 7:
        return col
    try:
        r = int(col[1:3], 16)
        g = int(col[3:5], 16)
        b = int(col[5:7], 16)
    except Exception:
        return col
    is_light = (theme_mode or ctk.get_appearance_mode()).lower() == "light"
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    if is_light and lum > 0.50:
        scale = 0.44 / max(lum, 0.01)
        r, g, b = int(r * scale), int(g * scale), int(b * scale)
    elif (not is_light) and lum < 0.24:
        boost = 0.42
        r = int(r + (255 - r) * boost)
        g = int(g + (255 - g) * boost)
        b = int(b + (255 - b) * boost)
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _set_win_titlebar_theme(win, mode="Dark"):
    if not sys.platform.startswith("win") or win is None:
        return
    try:
        hwnd = get_root_hwnd(win)
        if not hwnd:
            return
        is_light = str(mode).lower().startswith("l") or "bianco" in str(mode).lower()
        val = ctypes.c_int(0 if is_light else 1)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
        if res != 0:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass

VK_LBUTTON = 0x01
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001

GA_ROOT = 2

if sys.platform.startswith("win"):
    from ctypes import wintypes as _wt
    user32 = ctypes.windll.user32
    GetAsyncKeyState = user32.GetAsyncKeyState
    SetWindowPos = user32.SetWindowPos
    try:
        user32.GetForegroundWindow.restype = _wt.HWND
        user32.GetAncestor.argtypes = [_wt.HWND, _wt.UINT]
        user32.GetAncestor.restype = _wt.HWND
        user32.WindowFromPoint.argtypes = [_wt.POINT]
        user32.WindowFromPoint.restype = _wt.HWND
    except Exception:
        pass


def get_root_hwnd(root_window):
    if not sys.platform.startswith("win"):
        return None
    root_window.update_idletasks()
    hwnd = user32.GetParent(root_window.winfo_id())
    return hwnd if hwnd else root_window.winfo_id()


def get_foreground_root_hwnd():
    if not sys.platform.startswith("win"):
        return None
    try:
        fg = user32.GetForegroundWindow()
        if not fg:
            return None
        anc = user32.GetAncestor(fg, GA_ROOT)
        return anc or fg
    except Exception:
        return None


def get_point_root_hwnd(x, y):
    if not sys.platform.startswith("win"):
        return None
    try:
        from ctypes import wintypes as _wt
        hw = user32.WindowFromPoint(_wt.POINT(int(x), int(y)))
        if not hw:
            return None
        anc = user32.GetAncestor(hw, GA_ROOT)
        return anc or hw
    except Exception:
        return None


def apply_windows_enterprise_integration(root_window):
    if not sys.platform.startswith("win"):
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PeppeZ.Twixy.Desktop")
    except Exception:
        pass
    try:
        hwnd = get_root_hwnd(root_window)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(2)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value))
        SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    except Exception:
        pass


def format_seconds_hms(seconds):
    s = max(0, int(seconds))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def bind_vlc_runtime(vlc_dir):
    if not vlc_dir or not os.path.isdir(vlc_dir):
        return None
    dll_path = os.path.join(vlc_dir, "libvlc.dll")
    plugins_path = os.path.join(vlc_dir, "plugins")
    if not os.path.isfile(dll_path):
        return None

    os.environ["PYTHON_VLC_MODULE_PATH"] = vlc_dir
    os.environ["PYTHON_VLC_LIB_PATH"] = dll_path
    if os.path.isdir(plugins_path):
        os.environ["VLC_PLUGIN_PATH"] = plugins_path
    os.environ["PATH"] = vlc_dir + os.pathsep + os.environ.get("PATH", "")

    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(vlc_dir)
        except Exception:
            pass

    vlc_args = [
        "--no-video-title-show",
        "--network-caching=1500",
        "--live-caching=1500",
        "--drop-late-frames",
        "--skip-frames",
        "--no-mouse-events",
        "--no-keyboard-events",
        "--quiet",
    ]
    if sys.platform.startswith("win"):
        # DirectSound garantisce controllo volume e mute rigorosamente separato per ogni player nello stesso processo
        try:
            return vlc.Instance("--aout=directsound", *vlc_args)
        except Exception:
            pass
    try:
        return vlc.Instance(*vlc_args)
    except Exception:
        return None


def find_mpv_executable(custom_dir=None):
    candidates = []
    if custom_dir:
        candidates.append(os.path.join(custom_dir, "mpv.exe"))
    for d in [VENDOR_MPV_DIR, BUNDLE_MPV_DIR, APP_DIR]:
        if os.path.isdir(d):
            candidates.append(os.path.join(d, "mpv.exe"))
            try:
                for sub in os.listdir(d):
                    sub_p = os.path.join(d, sub)
                    if os.path.isdir(sub_p):
                        candidates.append(os.path.join(sub_p, "mpv.exe"))
            except Exception:
                pass

    which_mpv = shutil.which("mpv")
    if which_mpv:
        candidates.append(which_mpv)

    for drive in ["C:", "D:"]:
        candidates.extend([
            os.path.join(drive, os.sep, "Program Files", "mpv", "mpv.exe"),
            os.path.join(drive, os.sep, "mpv", "mpv.exe"),
        ])

    for exe in candidates:
        if exe and os.path.isfile(exe):
            return exe
    return None


def find_ffmpeg_executable():
    candidates = [
        os.path.join(APP_DIR, "ffmpeg.exe"),
        os.path.join(BUNDLE_DIR, "ffmpeg.exe"),
        os.path.join(APP_DIR, "vendor", "ffmpeg", "ffmpeg.exe"),
        os.path.join(BUNDLE_DIR, "vendor", "ffmpeg", "ffmpeg.exe"),
        os.path.join(VENDOR_MPV_DIR, "ffmpeg.exe"),
        os.path.join(BUNDLE_MPV_DIR, "ffmpeg.exe"),
    ]
    which_ff = shutil.which("ffmpeg")
    if which_ff:
        candidates.append(which_ff)
    for drive in ["C:", "D:"]:
        candidates.extend([
            os.path.join(drive, os.sep, "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(drive, os.sep, "Program Files", "ffmpeg", "bin", "ffmpeg.exe"),
        ])
    for exe in candidates:
        if exe and os.path.isfile(exe):
            return exe
    return None


# =====================================================================
# FILTRO LOCALE ANTI-AD HLS
# =====================================================================
class DaemonThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class AdStripperHLSServer:
    MAX_LIVE_BUFFER_SEC = 210.0

    def __init__(self):
        self.http = requests.Session()
        adapter = HTTPAdapter(pool_connections=16, pool_maxsize=32, max_retries=1)
        self.http.mount("https://", adapter)
        self.http.mount("http://", adapter)
        self.http.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})

        self._lock = threading.Lock()
        self.slots = {
            "main": {
                "primary_url": "",
                "backup_url": "",
                "is_vod": False,
                "last_clean_cache": "",
                "live_segments": [],
                "live_seen_keys": set(),
                "live_map_cache": {},
                "live_epoch": 0,
                "live_seq": 0,
                "last_poll_ts": 0.0,
                "paused": False,
            }
        }
        self.ads_blocked_count = 0
        self.clip_tmp_root = os.path.join(tempfile.gettempdir(), f"twixy_clips_{os.getpid()}")
        self._clip_buf_dir = os.path.join(self.clip_tmp_root, "live_buf")
        self._clip_sessions_dir = os.path.join(self.clip_tmp_root, "sessions")
        os.makedirs(self._clip_buf_dir, exist_ok=True)
        os.makedirs(self._clip_sessions_dir, exist_ok=True)
        self.clip_sessions = {}
        self._clip_dl_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="twixy_clip_buf")
        self._closed = False
        self.server = None
        self.port = 0
        self._start_server()
        threading.Thread(target=self._live_clip_poller_loop, daemon=True).start()

    def shutdown(self):
        self._closed = True
        try:
            self._clip_dl_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        try:
            if self.server is not None:
                self.server.shutdown()
        except Exception:
            pass
        try:
            shutil.rmtree(self.clip_tmp_root, ignore_errors=True)
        except Exception:
            pass

    def _live_clip_poller_loop(self):
        while not self._closed:
            time.sleep(2.0)
            if self._closed:
                break
            now = time.time()
            due_slots = []
            with self._lock:
                for sid, sl in self.slots.items():
                    if sl.get("is_vod") or sl.get("paused") or not sl.get("primary_url"):
                        continue
                    lp = float(sl.get("last_poll_ts") or 0.0)
                    # Continua a bufferizzare mentre lo stream è attivo (fino a 30s dopo l'ultima richiesta player)
                    if lp > 0.0 and (now - lp) <= 30.0 and (now - float(sl.get("last_fetch_ts") or 0.0)) >= 1.8:
                        due_slots.append(sid)
            for sid in due_slots:
                try:
                    self.fetch_and_strip_ads(slot_id=sid, from_poller=True)
                except Exception:
                    pass

    def _start_server(self):
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def _send_bytes(self, code, data, ctype="application/octet-stream", cache_ctrl=None):
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(data)))
                    if cache_ctrl:
                        self.send_header("Cache-Control", cache_ctrl)
                    self.end_headers()
                    self.wfile.write(data)
                except Exception:
                    pass

            def _serve_clip_route(self, req_path):
                self.connection.settimeout(12.0)
                parts = [p for p in req_path.split("/") if p]
                # /clip_session/<sid>/playlist.m3u8 | /clip_session/<sid>/map/<idx> | /clip_session/<sid>/seg/<idx>.<ext>
                if len(parts) < 3 or parts[0] != "clip_session":
                    self._send_bytes(404, b"Not found", "text/plain")
                    return
                sid = parts[1]
                with parent._lock:
                    sess = parent.clip_sessions.get(sid)
                if not sess:
                    self._send_bytes(404, b"Clip session closed", "text/plain")
                    return

                if parts[2] == "playlist.m3u8":
                    m3u8_txt = parent._build_session_playlist(sess)
                    self._send_bytes(
                        200, m3u8_txt.encode("utf-8"),
                        "application/vnd.apple.mpegurl",
                        cache_ctrl="no-cache, no-store",
                    )
                    return

                if len(parts) >= 4 and parts[2] == "map":
                    try:
                        m_idx = int(parts[3].split(".", 1)[0])
                    except Exception:
                        self._send_bytes(400, b"Bad map id", "text/plain")
                        return
                    data = parent._ensure_session_map_bytes(sess, m_idx)
                    if data is None:
                        self._send_bytes(502, b"Map fetch error", "text/plain")
                    else:
                        self._send_bytes(200, data, "video/mp4")
                    return

                if len(parts) >= 4 and parts[2] == "seg":
                    try:
                        s_idx = int(parts[3].split(".", 1)[0])
                    except Exception:
                        self._send_bytes(400, b"Bad seg id", "text/plain")
                        return
                    local_file = parent._ensure_session_segment_file(sess, s_idx)
                    if not local_file or not os.path.isfile(local_file):
                        self._send_bytes(502, b"Segment unavailable", "text/plain")
                        return
                    ctype = "video/iso.segment" if local_file.endswith((".m4s", ".mp4")) else "video/mp2t"
                    try:
                        sz = os.path.getsize(local_file)
                        self.send_response(200)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Content-Length", str(sz))
                        self.end_headers()
                        with open(local_file, "rb") as fp:
                            shutil.copyfileobj(fp, self.wfile, 65536)
                    except Exception:
                        pass
                    return

                self._send_bytes(404, b"Unknown clip route", "text/plain")

            def do_GET(self):
                self.connection.settimeout(4.0)
                parsed = urllib.parse.urlparse(self.path or "")
                if parsed.path.startswith("/clip_session/"):
                    self._serve_clip_route(parsed.path)
                    return

                slot_id = "main"
                if parsed.path.startswith("/stream/") and parsed.path.endswith(".m3u8"):
                    slot_id = parsed.path[len("/stream/"):-len(".m3u8")] or "main"

                with parent._lock:
                    slot = parent.slots.get(slot_id)
                    p_url = slot.get("primary_url", "") if slot else ""
                    last_cache = slot.get("last_clean_cache", "") if slot else ""
                    if slot is not None:
                        slot["last_poll_ts"] = time.time()

                if not p_url:
                    self.send_response(404)
                    self.end_headers()
                    return

                try:
                    clean_m3u8 = parent.fetch_and_strip_ads(slot_id=slot_id)
                    body = clean_m3u8.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Cache-Control", "no-cache, no-store")
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    if last_cache:
                        try:
                            body = last_cache.encode("utf-8")
                            self.send_response(200)
                            self.send_header("Content-Type", "application/vnd.apple.mpegurl")
                            self.send_header("Content-Length", str(len(body)))
                            self.end_headers()
                            self.wfile.write(body)
                            return
                        except Exception:
                            pass
                    try:
                        self.send_response(502)
                        self.end_headers()
                    except Exception:
                        pass

        self.server = DaemonThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def set_slot_paused(self, slot_id="main", paused=False):
        safe_slot = "".join(c for c in str(slot_id or "main") if c.isalnum() or c in ("_", "-")) or "main"
        with self._lock:
            sl = self.slots.get(safe_slot)
            if sl is not None:
                sl["paused"] = bool(paused)
                if not paused:
                    sl["last_poll_ts"] = time.time()

    def set_target_stream(self, primary_url, backup_url="", is_vod=False, slot_id="main", backup_urls=None, refresh_cb=None):
        safe_slot = "".join(c for c in str(slot_id or "main") if c.isalnum() or c in ("_", "-")) or "main"
        b_list = []
        for u in ([backup_url] if backup_url else []) + list(backup_urls or []):
            if u and u != primary_url and u not in b_list:
                b_list.append(u)
        old_segs = []
        with self._lock:
            prev = self.slots.get(safe_slot) or {}
            next_epoch = int(prev.get("live_epoch") or 0) + 1
            old_segs = list(prev.get("live_segments") or [])
            self.slots[safe_slot] = {
                "primary_url": primary_url,
                "backup_url": backup_url,
                "backup_urls": b_list,
                "refresh_cb": refresh_cb,
                "last_refresh_ts": 0.0,
                "is_vod": is_vod,
                "last_clean_cache": "",
                "live_segments": [],
                "live_seen_keys": set(),
                "live_map_cache": {},
                "live_epoch": next_epoch,
                "live_seq": 0,
                "last_poll_ts": time.time(),
                "last_fetch_ts": 0.0,
                "paused": False,
            }
        if old_segs:
            def _cleanup_old():
                for s in old_segs:
                    lp = s.get("local_path") or ""
                    if lp and os.path.isfile(lp):
                        try:
                            os.remove(lp)
                        except Exception:
                            pass
            self._clip_dl_executor.submit(_cleanup_old)
        if is_vod:
            return primary_url
        return f"http://127.0.0.1:{self.port}/stream/{safe_slot}.m3u8?r={random.randint(1000, 9999)}"

    def clear_slot(self, slot_id):
        safe_slot = "".join(c for c in str(slot_id or "") if c.isalnum() or c in ("_", "-"))
        if safe_slot:
            with self._lock:
                old = self.slots.pop(safe_slot, None)
            if old:
                for s in old.get("live_segments") or []:
                    lp = s.get("local_path") or ""
                    if lp and os.path.isfile(lp):
                        try:
                            os.remove(lp)
                        except Exception:
                            pass

    @staticmethod
    def parse_m3u8_segments(raw_text, base_url=""):
        segs = []
        cur_dur = 2.0
        cur_map = ""
        cur_byte_range = None
        next_byte_offset = 0
        expect_uri = False
        cum_sec = 0.0
        for line in (raw_text or "").splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith("#EXT-X-MAP:"):
                m = re.search(r'URI="([^"]+)"', s)
                if m:
                    cur_map = urllib.parse.urljoin(base_url, m.group(1)) if base_url else m.group(1)
            elif s.startswith("#EXT-X-BYTERANGE:"):
                br = s[17:].strip()
                try:
                    if "@" in br:
                        ln, off = br.split("@", 1)
                        length, offset = int(ln), int(off)
                    else:
                        length = int(br)
                        offset = next_byte_offset
                    cur_byte_range = (offset, offset + max(1, length) - 1)
                    next_byte_offset = offset + max(1, length)
                except Exception:
                    cur_byte_range = None
            elif s.startswith("#EXTINF:"):
                raw_d = s[8:].split(",", 1)[0].strip()
                try:
                    cur_dur = max(0.2, float(raw_d))
                except Exception:
                    cur_dur = 2.0
                expect_uri = True
            elif not s.startswith("#"):
                if expect_uri or ".ts" in s.lower() or ".m4s" in s.lower() or ".mp4" in s.lower():
                    abs_u = urllib.parse.urljoin(base_url, s) if base_url else s
                    path_low = urllib.parse.urlparse(abs_u).path.lower()
                    ext = ".m4s" if path_low.endswith(".m4s") else (".mp4" if path_low.endswith(".mp4") else ".ts")
                    segs.append({
                        "url": abs_u,
                        "duration": cur_dur,
                        "abs_start": cum_sec,
                        "abs_end": cum_sec + cur_dur,
                        "map_url": cur_map,
                        "byte_range": cur_byte_range,
                        "ext": ext,
                    })
                    cum_sec += cur_dur
                expect_uri = False
                cur_byte_range = None
        return segs

    def _download_url_to_file(self, url, dst_path, timeout=(4.0, 8.0), byte_range=None):
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        tmp_path = f"{dst_path}.{uuid.uuid4().hex[:6]}.tmp"
        req_headers = {}
        if byte_range and len(byte_range) == 2:
            req_headers["Range"] = f"bytes={int(byte_range[0])}-{int(byte_range[1])}"
        try:
            with self.http.get(url, headers=req_headers or None, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            if os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0:
                os.replace(tmp_path, dst_path)
                return True
        except Exception:
            try:
                if os.path.isfile(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        return False

    def _ingest_live_playlist(self, slot_id, clean_m3u8):
        segs = self.parse_m3u8_segments(clean_m3u8)
        if not segs:
            return
        to_download = []
        to_prune = []
        with self._lock:
            slot = self.slots.get(slot_id)
            if not slot or slot.get("is_vod") or slot.get("paused"):
                return
            epoch = int(slot.get("live_epoch") or 0)
            seen = slot.setdefault("live_seen_keys", set())
            buf = slot.setdefault("live_segments", [])
            recent_names = {os.path.basename(urllib.parse.urlparse(s["url"]).path) for s in buf[-12:] if s.get("url")}
            ep_dir = os.path.join(self._clip_buf_dir, slot_id, f"ep_{epoch}")

            for s in segs:
                u = s["url"]
                bname = os.path.basename(urllib.parse.urlparse(u).path)
                dedupe_key = u
                if dedupe_key in seen:
                    continue
                if bname and bname not in ("index.ts", "seg.ts", "chunk.ts") and bname in recent_names:
                    seen.add(dedupe_key)
                    continue
                seen.add(dedupe_key)
                if bname:
                    recent_names.add(bname)
                slot["live_seq"] = int(slot.get("live_seq") or 0) + 1
                seq_num = slot["live_seq"]
                local_path = os.path.join(ep_dir, f"seg_{seq_num:06d}{s['ext']}")
                map_url = s.get("map_url") or ""
                map_local = ""
                if map_url:
                    map_cache = slot.setdefault("live_map_cache", {})
                    if map_url not in map_cache:
                        map_local = os.path.join(ep_dir, f"map_{len(map_cache):03d}.mp4")
                        map_cache[map_url] = map_local
                        to_download.append((map_url, map_local, None))
                    else:
                        map_local = map_cache[map_url]

                entry = {
                    "seq": seq_num,
                    "url": u,
                    "duration": float(s["duration"]),
                    "map_url": map_url,
                    "map_local_path": map_local,
                    "ext": s["ext"],
                    "local_path": local_path,
                    "dl_done": False,
                }
                buf.append(entry)
                to_download.append((u, local_path, entry))

            total_dur = sum(x["duration"] for x in buf)
            while total_dur > self.MAX_LIVE_BUFFER_SEC and len(buf) > 4:
                old = buf.pop(0)
                total_dur -= old["duration"]
                if old.get("local_path"):
                    to_prune.append(old["local_path"])
            if len(seen) > 800:
                slot["live_seen_keys"] = {x["url"] for x in buf}

        for url, lp, ent in to_download:
            def _dl_task(u_d=url, dst=lp, item=ent):
                ok = True if os.path.isfile(dst) else self._download_url_to_file(u_d, dst, timeout=(3.0, 6.0))
                if item is not None:
                    item["dl_done"] = bool(ok)
            try:
                self._clip_dl_executor.submit(_dl_task)
            except Exception:
                pass

        for p_old in to_prune:
            try:
                if os.path.isfile(p_old):
                    os.remove(p_old)
            except Exception:
                pass

    def get_live_buffer_seconds(self, slot_id="main"):
        safe_slot = "".join(c for c in str(slot_id or "main") if c.isalnum() or c in ("_", "-")) or "main"
        with self._lock:
            sl = self.slots.get(safe_slot)
            if not sl:
                return 0.0
            return sum(float(s.get("duration") or 0.0) for s in (sl.get("live_segments") or []))

    def create_live_clip_session(self, slot_id="main", channel=""):
        safe_slot = "".join(c for c in str(slot_id or "main") if c.isalnum() or c in ("_", "-")) or "main"
        with self._lock:
            sl = self.slots.get(safe_slot)
            if not sl:
                raise RuntimeError("Nessuno stream live attivo da clippare.")
            raw_segs = list(sl.get("live_segments") or [])
        if not raw_segs:
            raise RuntimeError("Il buffer Live si sta ancora inizializzando: attendi 2-3 secondi e riprova.")

        sid = uuid.uuid4().hex[:10]
        sess_dir = os.path.join(self._clip_sessions_dir, sid)
        os.makedirs(sess_dir, exist_ok=True)

        map_index_by_url = {}
        maps_list = []
        sess_segs = []
        cum = 0.0
        for idx, s in enumerate(raw_segs):
            dur = float(s.get("duration") or 2.0)
            ext = s.get("ext") or ".ts"
            dst_path = os.path.join(sess_dir, f"seg_{idx:05d}{ext}")
            src_lp = s.get("local_path") or ""
            if src_lp and os.path.isfile(src_lp):
                try:
                    os.link(src_lp, dst_path)
                except Exception:
                    try:
                        shutil.copy2(src_lp, dst_path)
                    except Exception:
                        pass

            map_url = s.get("map_url") or ""
            m_idx = None
            if map_url:
                if map_url not in map_index_by_url:
                    m_idx = len(maps_list)
                    map_index_by_url[map_url] = m_idx
                    m_dst = os.path.join(sess_dir, f"map_{m_idx:02d}.mp4")
                    m_src = s.get("map_local_path") or ""
                    if m_src and os.path.isfile(m_src):
                        try:
                            shutil.copy2(m_src, m_dst)
                        except Exception:
                            pass
                    maps_list.append({"url": map_url, "local_path": m_dst, "lock": threading.Lock()})
                else:
                    m_idx = map_index_by_url[map_url]

            sess_segs.append({
                "idx": idx,
                "url": s["url"],
                "duration": dur,
                "rel_start": cum,
                "rel_end": cum + dur,
                "ext": ext,
                "local_path": dst_path,
                "map_idx": m_idx,
                "lock": threading.Lock(),
            })
            cum += dur

        total_dur = max(0.5, cum)
        def_end = total_dur
        def_start = max(0.0, def_end - 30.0)
        sess = {
            "sid": sid,
            "kind": "live",
            "channel": channel,
            "dir": sess_dir,
            "maps": maps_list,
            "segments": sess_segs,
            "total_dur": total_dur,
            "default_start": def_start,
            "default_end": def_end,
            "vod_offset_sec": 0.0,
            "all_vod_segs": [],
        }
        with self._lock:
            self.clip_sessions[sid] = sess
        # Scarica in background gli ultimi segmenti live eventualmente non ancora pronti su disco
        self.prefetch_session_range(sid, max(0.0, def_start - 2.0), def_end)
        return sess

    def _fetch_media_m3u8_text(self, playlist_url):
        r = self.http.get(playlist_url, timeout=(6.0, 12.0))
        r.raise_for_status()
        m3u8_text = r.text or ""
        media_url = playlist_url
        if "#EXTM3U" not in m3u8_text:
            raise ValueError("Playlist HLS non valida.")
        if "#EXT-X-STREAM-INF:" in m3u8_text and "#EXTINF:" not in m3u8_text:
            best_url = None
            best_bw = -1
            cur_bw = 0
            expect_variant = False
            for ln in m3u8_text.splitlines():
                st = ln.strip()
                if st.startswith("#EXT-X-STREAM-INF:"):
                    m_bw = re.search(r'BANDWIDTH=(\d+)', st)
                    cur_bw = int(m_bw.group(1)) if m_bw else 0
                    expect_variant = True
                elif expect_variant and st and not st.startswith("#"):
                    cand = urllib.parse.urljoin(media_url, st)
                    if cur_bw >= best_bw or best_url is None:
                        best_bw = cur_bw
                        best_url = cand
                    expect_variant = False
            if best_url:
                r2 = self.http.get(best_url, timeout=(6.0, 12.0))
                r2.raise_for_status()
                media_url = best_url
                m3u8_text = r2.text or ""
        return m3u8_text, media_url

    def create_vod_clip_session(self, vod_m3u8_url, anchor_sec, total_vod_sec=0.0, channel=""):
        m3u8_text, media_url = self._fetch_media_m3u8_text(vod_m3u8_url)
        all_segs = self.parse_m3u8_segments(m3u8_text, base_url=media_url)
        if not all_segs:
            raise RuntimeError("Nessun segmento trovato per questo VOD.")

        vod_end = all_segs[-1]["abs_end"]
        anchor = max(0.0, min(float(anchor_sec or 0.0), vod_end))
        win_start = max(0.0, anchor - 90.0)
        win_end = min(vod_end, max(anchor + 90.0, win_start + 180.0))
        if win_end - win_start < 180.0 and win_start > 0.0:
            win_start = max(0.0, win_end - 180.0)

        sid = uuid.uuid4().hex[:10]
        sess_dir = os.path.join(self._clip_sessions_dir, sid)
        os.makedirs(sess_dir, exist_ok=True)
        sess = {
            "sid": sid,
            "kind": "vod",
            "channel": channel,
            "dir": sess_dir,
            "maps": [],
            "segments": [],
            "total_dur": 0.0,
            "default_start": 0.0,
            "default_end": 30.0,
            "vod_offset_sec": 0.0,
            "vod_total_sec": vod_end,
            "anchor_abs": anchor,
            "all_vod_segs": all_segs,
        }
        with self._lock:
            self.clip_sessions[sid] = sess
        self._populate_vod_window(sess, win_start, win_end, anchor_target=anchor)
        self.prefetch_session_range(sid, max(0.0, sess["default_start"] - 2.0), min(sess["total_dur"], sess["default_end"] + 2.0))
        return sess

    def _populate_vod_window(self, sess, win_start, win_end, anchor_target=None):
        all_segs = sess.get("all_vod_segs") or []
        chosen = [s for s in all_segs if s["abs_end"] > win_start and s["abs_start"] < win_end]
        if not chosen:
            chosen = all_segs[:min(15, len(all_segs))]
        slice_origin = chosen[0]["abs_start"]
        sess_dir = sess["dir"]

        existing_by_key = {(s["url"], s.get("byte_range")): s for s in (sess.get("segments") or [])}
        map_index_by_url = {m["url"]: i for i, m in enumerate(sess.get("maps") or [])}
        maps_list = list(sess.get("maps") or [])

        new_segs = []
        cum = 0.0
        for idx, vs in enumerate(chosen):
            dur = float(vs["duration"])
            map_url = vs.get("map_url") or ""
            m_idx = None
            if map_url:
                if map_url not in map_index_by_url:
                    m_idx = len(maps_list)
                    map_index_by_url[map_url] = m_idx
                    maps_list.append({
                        "url": map_url,
                        "local_path": os.path.join(sess_dir, f"map_{m_idx:02d}.mp4"),
                        "lock": threading.Lock(),
                    })
                else:
                    m_idx = map_index_by_url[map_url]

            br = vs.get("byte_range")
            prev_ent = existing_by_key.get((vs["url"], br))
            lp = prev_ent["local_path"] if prev_ent else os.path.join(sess_dir, f"vseg_{len(existing_by_key) + idx:06d}_{uuid.uuid4().hex[:4]}{vs['ext']}")
            new_segs.append({
                "idx": idx,
                "url": vs["url"],
                "duration": dur,
                "rel_start": cum,
                "rel_end": cum + dur,
                "ext": vs["ext"],
                "byte_range": br,
                "local_path": lp,
                "map_idx": m_idx,
                "lock": prev_ent["lock"] if prev_ent else threading.Lock(),
            })
            cum += dur

        sess["maps"] = maps_list
        sess["segments"] = new_segs
        sess["total_dur"] = max(0.5, cum)
        sess["vod_offset_sec"] = slice_origin
        if anchor_target is not None:
            rel_anchor = max(0.0, min(sess["total_dur"], anchor_target - slice_origin))
            if rel_anchor >= 5.0:
                sess["default_end"] = rel_anchor
                sess["default_start"] = max(0.0, rel_anchor - 30.0)
            else:
                sess["default_start"] = 0.0
                sess["default_end"] = min(sess["total_dur"], 30.0)

    def shift_vod_clip_window(self, sid, delta_before=0.0, delta_after=0.0, cur_trim_start=0.0, cur_trim_end=30.0):
        with self._lock:
            sess = self.clip_sessions.get(sid)
        if not sess or sess.get("kind") != "vod":
            return None
        old_origin = float(sess["vod_offset_sec"])
        abs_t0 = old_origin + float(cur_trim_start)
        abs_t1 = old_origin + float(cur_trim_end)
        old_end = old_origin + float(sess["total_dur"])
        vod_tot = float(sess.get("vod_total_sec") or old_end)
        new_start = max(0.0, old_origin - max(0.0, delta_before))
        new_end = min(vod_tot, old_end + max(0.0, delta_after))
        if new_start >= old_origin - 0.5 and new_end <= old_end + 0.5:
            return {
                "changed": False,
                "at_start": old_origin <= 0.5,
                "at_end": old_end >= vod_tot - 0.5,
                "vod_offset_sec": old_origin,
                "total_dur": sess["total_dur"],
                "trim_start": cur_trim_start,
                "trim_end": cur_trim_end,
            }
        self._populate_vod_window(sess, new_start, new_end, anchor_target=None)
        new_origin = float(sess["vod_offset_sec"])
        return {
            "changed": True,
            "at_start": new_origin <= 0.5,
            "at_end": (new_origin + sess["total_dur"]) >= vod_tot - 0.5,
            "vod_offset_sec": new_origin,
            "total_dur": sess["total_dur"],
            "trim_start": max(0.0, min(sess["total_dur"] - 1.0, abs_t0 - new_origin)),
            "trim_end": max(1.0, min(sess["total_dur"], abs_t1 - new_origin)),
        }

    @staticmethod
    def _parse_iso_utc_ts(iso_str):
        if not iso_str:
            return None
        try:
            clean = str(iso_str).strip().replace("Z", "")
            if "." in clean:
                clean = clean.split(".", 1)[0]
            import calendar
            return float(calendar.timegm(time.strptime(clean, "%Y-%m-%dT%H:%M:%S")))
        except Exception:
            return None

    def augment_live_clip_with_archive(self, sid, vod_m3u8_url, vod_created_iso="", max_total_sec=130.0):
        """Estende all'indietro una sessione Clip Live fino a ~2 minuti usando la coda dell'archivio VOD attivo."""
        if not sid or not vod_m3u8_url:
            return False
        with self._lock:
            sess = self.clip_sessions.get(sid)
            if not sess or sess.get("kind") != "live":
                return False
            live_segs = list(sess.get("segments") or [])
            live_dur = float(sess.get("total_dur") or 0.0)
        if live_dur >= 118.0:
            return False
        try:
            m3u8_text, media_url = self._fetch_media_m3u8_text(vod_m3u8_url)
            all_vod = self.parse_m3u8_segments(m3u8_text, base_url=media_url)
        except Exception:
            return False
        if not all_vod:
            return False

        vod_end = float(all_vod[-1]["abs_end"])
        vod_t0 = self._parse_iso_utc_ts(vod_created_iso)
        if vod_t0 is not None:
            elapsed_now = max(vod_end, time.time() - vod_t0)
            win_start = max(0.0, elapsed_now - float(max_total_sec))
            live_start_est = max(0.0, elapsed_now - live_dur)
            cut_end = min(vod_end, max(win_start, live_start_est - 0.5))
        else:
            need_back = max(0.0, float(max_total_sec) - live_dur)
            cut_end = max(0.0, vod_end - max(2.0, live_dur * 0.8))
            win_start = max(0.0, cut_end - need_back)

        chosen = [s for s in all_vod if s["abs_end"] > win_start and s["abs_start"] < cut_end]
        if not chosen:
            return False

        sess_dir = sess["dir"]
        maps_list = list(sess.get("maps") or [])
        map_index_by_url = {m["url"]: i for i, m in enumerate(maps_list)}

        combined = []
        cum = 0.0
        for s in chosen:
            dur = float(s["duration"])
            map_url = s.get("map_url") or ""
            m_idx = None
            if map_url:
                if map_url not in map_index_by_url:
                    m_idx = len(maps_list)
                    map_index_by_url[map_url] = m_idx
                    maps_list.append({
                        "url": map_url,
                        "local_path": os.path.join(sess_dir, f"arch_map_{m_idx:02d}.mp4"),
                        "lock": threading.Lock(),
                    })
                else:
                    m_idx = map_index_by_url[map_url]
            idx = len(combined)
            combined.append({
                "idx": idx,
                "url": s["url"],
                "duration": dur,
                "rel_start": cum,
                "rel_end": cum + dur,
                "ext": s["ext"],
                "byte_range": s.get("byte_range"),
                "local_path": os.path.join(sess_dir, f"arch_{idx:05d}_{uuid.uuid4().hex[:4]}{s['ext']}"),
                "map_idx": m_idx,
                "discontinuity": False,
                "lock": threading.Lock(),
            })
            cum += dur

        for j, ls in enumerate(live_segs):
            dur = float(ls["duration"])
            idx = len(combined)
            ent = dict(ls)
            ent["idx"] = idx
            ent["rel_start"] = cum
            ent["rel_end"] = cum + dur
            ent["discontinuity"] = (j == 0 and len(chosen) > 0)
            combined.append(ent)
            cum += dur

        total_dur = max(0.5, cum)
        with self._lock:
            sess["maps"] = maps_list
            sess["segments"] = combined
            sess["total_dur"] = total_dur
            sess["default_end"] = total_dur
            sess["default_start"] = max(0.0, total_dur - 30.0)
        self.prefetch_session_range(sid, max(0.0, sess["default_start"] - 4.0), total_dur)
        return True

    def _build_session_playlist(self, sess):
        segs = list(sess.get("segments") or [])
        max_d = max([math.ceil(s["duration"]) for s in segs] or [2])
        has_map = bool(sess.get("maps"))
        lines = [
            "#EXTM3U",
            f"#EXT-X-VERSION:{7 if has_map else 3}",
            f"#EXT-X-TARGETDURATION:{max(2, int(max_d))}",
            "#EXT-X-MEDIA-SEQUENCE:0",
            "#EXT-X-PLAYLIST-TYPE:VOD",
        ]
        last_map = None
        for s in segs:
            if s.get("discontinuity"):
                lines.append("#EXT-X-DISCONTINUITY")
                last_map = None
            m_idx = s.get("map_idx")
            if m_idx is not None and m_idx != last_map:
                lines.append(f'#EXT-X-MAP:URI="http://127.0.0.1:{self.port}/clip_session/{sess["sid"]}/map/{m_idx}"')
                last_map = m_idx
            lines.append(f"#EXTINF:{s['duration']:.3f},")
            lines.append(f"http://127.0.0.1:{self.port}/clip_session/{sess['sid']}/seg/{s['idx']}{s['ext']}")
        lines.append("#EXT-X-ENDLIST")
        return "\n".join(lines) + "\n"

    def _ensure_session_map_bytes(self, sess, m_idx):
        maps = sess.get("maps") or []
        if m_idx < 0 or m_idx >= len(maps):
            return None
        mp = maps[m_idx]
        with mp["lock"]:
            lp = mp["local_path"]
            if not os.path.isfile(lp):
                self._download_url_to_file(mp["url"], lp, timeout=(5.0, 10.0))
            if os.path.isfile(lp):
                with open(lp, "rb") as f:
                    return f.read()
        return None

    def _ensure_session_segment_file(self, sess, s_idx):
        segs = sess.get("segments") or []
        if s_idx < 0 or s_idx >= len(segs):
            return None
        s = segs[s_idx]
        with s["lock"]:
            lp = s["local_path"]
            if os.path.isfile(lp) and os.path.getsize(lp) > 0:
                return lp
            if self._download_url_to_file(s["url"], lp, timeout=(6.0, 12.0), byte_range=s.get("byte_range")):
                return lp
        return None

    def prefetch_session_range(self, sid, t_start, t_end):
        with self._lock:
            sess = self.clip_sessions.get(sid)
        if not sess:
            return
        indices = [
            s["idx"] for s in (sess.get("segments") or [])
            if s["rel_end"] >= t_start and s["rel_start"] <= t_end
        ]
        for idx in indices:
            try:
                self._clip_dl_executor.submit(self._ensure_session_segment_file, sess, idx)
            except Exception:
                pass

    def download_session_slice(self, sid, trim_start, trim_end, progress_cb=None):
        with self._lock:
            sess = self.clip_sessions.get(sid)
        if not sess:
            raise RuntimeError("Sessione clip scaduta.")
        selected = [
            s for s in (sess.get("segments") or [])
            if s["rel_end"] > trim_start and s["rel_start"] < trim_end
        ]
        if not selected:
            raise RuntimeError("Nessun segmento video valido nell'intervallo scelto.")

        total = len(selected)
        ready_files = []
        used_maps = set()
        for i, s in enumerate(selected):
            if self._closed:
                raise RuntimeError("Operazione annullata.")
            if s.get("map_idx") is not None and s["map_idx"] not in used_maps:
                self._ensure_session_map_bytes(sess, s["map_idx"])
                used_maps.add(s["map_idx"])
            lp = self._ensure_session_segment_file(sess, s["idx"])
            if not lp or not os.path.isfile(lp):
                raise RuntimeError(f"Download segmento {i + 1}/{total} fallito.")
            ready_files.append((s, lp))
            if progress_cb:
                progress_cb(int(((i + 1) / total) * 45), f"Download segmenti ({i + 1}/{total})...")

        has_fmp4 = bool(used_maps) or any(s["ext"] in (".m4s", ".mp4") for s, _ in ready_files)
        raw_ext = ".mp4" if has_fmp4 else ".ts"
        raw_path = os.path.join(sess["dir"], f"export_raw_{uuid.uuid4().hex[:6]}{raw_ext}")
        with open(raw_path, "wb") as out_f:
            if has_fmp4 and used_maps:
                m0_idx = sorted(used_maps)[0]
                m_bytes = self._ensure_session_map_bytes(sess, m0_idx)
                if m_bytes:
                    out_f.write(m_bytes)
            for _, lp in ready_files:
                with open(lp, "rb") as sf:
                    shutil.copyfileobj(sf, out_f, 131072)

        slice_origin = selected[0]["rel_start"]
        rel_start = max(0.0, float(trim_start) - slice_origin)
        rel_dur = max(0.5, float(trim_end) - float(trim_start))
        return raw_path, rel_start, rel_dur

    def release_clip_session(self, sid):
        if not sid:
            return
        with self._lock:
            sess = self.clip_sessions.pop(sid, None)
        if sess and sess.get("dir"):
            try:
                shutil.rmtree(sess["dir"], ignore_errors=True)
            except Exception:
                pass

    @staticmethod
    def _absolutize_and_filter_m3u8(raw_text, base_url):
        lines = raw_text.splitlines()
        out_lines = []
        clean_seg_count = 0
        had_ads = False
        skip_next_uri = False
        in_ad_block = False

        for line in lines:
            s = line.strip()
            if not s:
                continue

            if s.startswith("#EXT-X-DATERANGE:"):
                low = s.lower()
                if (
                    "twitch-stitched-ad" in low
                    or "stitched-ad" in low
                    or "x-tv-twitch-ad" in low
                    or "twitch-ad-quartile" in low
                    or "amazon" in low
                ):
                    had_ads = True
                    in_ad_block = True
                    continue

            if s.startswith("#EXT-X-CUE-OUT") or s.startswith("#EXT-X-SCTE35"):
                had_ads = True
                in_ad_block = True
                continue
            if s.startswith("#EXT-X-CUE-IN"):
                had_ads = True
                in_ad_block = False
                continue

            if s.startswith("#EXT-X-DISCONTINUITY"):
                if in_ad_block or had_ads:
                    # Evita discontinuità vuote quando i segmenti ad vengono rimossi
                    continue

            if s.startswith("#EXT-X-TWITCH-PREFETCH:"):
                if in_ad_block or had_ads:
                    continue

            if s.startswith("#EXTINF:"):
                title_part = s.split(",", 1)[1].strip().lower() if "," in s else ""
                is_ad_inf = (
                    "amazon" in title_part
                    or "stitched" in title_part
                    or "ad|" in title_part
                    or "|ad" in title_part
                    or "adbreak" in title_part
                    or (title_part and "live" not in title_part)
                )
                if is_ad_inf:
                    had_ads = True
                    in_ad_block = True
                    skip_next_uri = True
                    continue
                else:
                    in_ad_block = False
                    skip_next_uri = False
                    out_lines.append(s)
                    continue

            if skip_next_uri:
                if s.startswith("#"):
                    continue
                else:
                    skip_next_uri = False
                    continue

            if s.startswith("#"):
                if s.startswith("#EXT-X-MAP:URI="):
                    uri_val = s.split('URI="', 1)[1].split('"', 1)[0]
                    abs_uri = urllib.parse.urljoin(base_url, uri_val)
                    s = f'#EXT-X-MAP:URI="{abs_uri}"'
                out_lines.append(s)
            else:
                low_u = s.lower()
                if "/ads/" in low_u or "stitched-ad" in low_u:
                    had_ads = True
                    continue
                abs_seg_url = urllib.parse.urljoin(base_url, s)
                out_lines.append(abs_seg_url)
                clean_seg_count += 1

        return "\n".join(out_lines) + "\n", clean_seg_count, had_ads

    def _try_fetch_playlist(self, url, timeout=(2.5, 3.5)):
        r = self.http.get(url, timeout=timeout)
        r.raise_for_status()
        if "#EXTM3U" not in r.text:
            raise ValueError("Not an M3U8 playlist")
        return self._absolutize_and_filter_m3u8(r.text, url)

    def fetch_and_strip_ads(self, slot_id="main", from_poller=False):
        with self._lock:
            slot = self.slots.get(slot_id)
            if not slot:
                raise RuntimeError("Empty slot")
            p_url = slot["primary_url"]
            b_urls = list(slot.get("backup_urls") or ([] if not slot.get("backup_url") else [slot["backup_url"]]))
            refresh_cb = slot.get("refresh_cb")
            last_refresh_ts = float(slot.get("last_refresh_ts") or 0.0)
            last_clean_cache = slot.get("last_clean_cache") or ""
            slot["last_fetch_ts"] = time.time()
            if not from_poller:
                slot["last_poll_ts"] = time.time()

        def _commit_clean(text):
            with self._lock:
                if slot_id in self.slots:
                    self.slots[slot_id]["last_clean_cache"] = text
            self._ingest_live_playlist(slot_id, text)
            return text

        best_text, best_count, best_had_ads = "", 0, False

        try:
            filtered_text, clean_count, had_ads = self._try_fetch_playlist(p_url, timeout=(2.5, 3.5))
            if had_ads:
                self.ads_blocked_count += 1
            if clean_count > 0 and not had_ads:
                return _commit_clean(filtered_text)
            best_text, best_count, best_had_ads = filtered_text, clean_count, had_ads
        except Exception:
            pass

        # Fallback su pool multiplo (es. as.luminous / site / popout / frontpage / autoplay)
        for bu in b_urls:
            try:
                b_text, b_clean_count, b_had_ads = self._try_fetch_playlist(bu, timeout=(2.0, 3.0))
                if b_clean_count > 0 and not b_had_ads:
                    return _commit_clean(b_text)
                if b_clean_count > best_count:
                    best_text, best_count, best_had_ads = b_text, b_clean_count, b_had_ads
            except Exception:
                continue

        # Se tutte le sorgenti hanno 0 segmenti puliti o token scaduti, rigenera i token al volo (max 1 volta ogni 8s)
        now = time.time()
        if best_count == 0 and refresh_cb and (now - last_refresh_ts >= 8.0):
            with self._lock:
                if slot_id in self.slots:
                    self.slots[slot_id]["last_refresh_ts"] = now
            try:
                new_p, new_bs = refresh_cb()
                candidates = ([new_p] if new_p else []) + list(new_bs or [])
                if new_p:
                    with self._lock:
                        if slot_id in self.slots:
                            self.slots[slot_id]["primary_url"] = new_p
                            self.slots[slot_id]["backup_urls"] = list(new_bs or [])
                for cu in candidates:
                    try:
                        c_text, c_clean, c_ads = self._try_fetch_playlist(cu, timeout=(2.5, 3.5))
                        if c_clean > 0 and not c_ads:
                            return _commit_clean(c_text)
                        if c_clean > best_count:
                            best_text, best_count = c_text, c_clean
                    except Exception:
                        continue
            except Exception:
                pass

        if best_count > 0:
            return _commit_clean(best_text)

        # CRITICO: non restituire mai una playlist con 0 segmenti (farebbe freezare VLC/MPV in EOF)
        if last_clean_cache:
            return last_clean_cache
        if best_text:
            return best_text
        raise RuntimeError("No clean segments available")


# =====================================================================
# MOTORE API TWITCH, DROPS, PUNTI CANALE, SONDAGGI & HEARTBEAT SPADE
# =====================================================================
class TwixyEngine:
    def __init__(self, oauth_token="", auth_client_id="", user_id=""):
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Client-ID": GQL_CLIENT_ID,
            "Accept": "*/*"
        })
        self.oauth_token = oauth_token
        self.auth_client_id = auth_client_id or GQL_CLIENT_ID
        self.user_id = str(user_id or "")
        self.device_id = f"twixy{random.randint(1000000000, 9999999999)}"
        self.ad_stripper = AdStripperHLSServer()
        self._spade_url_cache = "https://spade.twitch.tv/track"
        self.last_redeem_details = {}

    def validate_oauth_token(self, token):
        clean_tok = token.replace("oauth:", "").strip()
        if not clean_tok:
            return None, None, None
        try:
            r = self.session.get(
                "https://id.twitch.tv/oauth2/validate",
                headers={"Authorization": f"OAuth {clean_tok}"},
                timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                self.user_id = str(data.get("user_id") or "")
                return data.get("login"), data.get("client_id"), self.user_id
        except Exception:
            pass
        return None, None, None

    def _gql_headers(self, use_auth=True, custom_client_id=None):
        if custom_client_id:
            cid = custom_client_id
        elif use_auth and self.oauth_token and self.auth_client_id:
            cid = self.auth_client_id
        else:
            cid = GQL_CLIENT_ID

        h = {
            "Client-ID": cid,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "Device-ID": self.device_id
        }
        if use_auth and self.oauth_token:
            h["Authorization"] = f"OAuth {self.oauth_token}"
        return h

    def gql_post(self, payload, use_auth=True, custom_client_id=None):
        # Prova prima col client_id associato al token, poi fallback automatico su GQL_CLIENT_ID
        cids_to_try = [custom_client_id] if custom_client_id else ([self.auth_client_id, GQL_CLIENT_ID] if (use_auth and self.oauth_token) else [GQL_CLIENT_ID])
        last_resp = None
        for cid in cids_to_try:
            if not cid:
                continue
            r = self.session.post(
                "https://gql.twitch.tv/gql",
                headers=self._gql_headers(use_auth, cid),
                json=payload,
                timeout=10
            )
            if r.status_code == 200:
                res_json = r.json()
                if isinstance(res_json, dict) and "errors" in res_json and not res_json.get("data"):
                    last_resp = res_json
                    continue
                return res_json
            last_resp = r
        if isinstance(last_resp, dict):
            return last_resp
        if last_resp is not None:
            last_resp.raise_for_status()
        return {}

    # -----------------------------------------------------------------
    # TELEMETRIA SPADE 'minute-watched' (FA AVANZARE DROP E PUNTI CANALE)
    # -----------------------------------------------------------------
    def send_minute_watched_heartbeat(self, channel_login, channel_id, broadcast_id, game_name=""):
        """
        Invia a Twitch il pacchetto 'minute-watched' ogni 60 secondi:
        è il requisito essenziale di Twitch per far salire la % dei Drop e dare i Punti Canale.
        """
        if not channel_id or not broadcast_id:
            return False

        payload_obj = [{
            "event": "minute-watched",
            "properties": {
                "channel": channel_login,
                "channel_id": str(channel_id),
                "broadcast_id": str(broadcast_id),
                "player": "site",
                "user_id": int(self.user_id) if self.user_id.isdigit() else (self.user_id or None),
                "live": True,
                "game": game_name or "",
                "device_id": self.device_id
            }
        }]
        raw_json = json.dumps(payload_obj, separators=(",", ":"))
        b64_data = base64.b64encode(raw_json.encode("utf-8")).decode("utf-8")

        headers = {"User-Agent": USER_AGENT}
        if self.oauth_token:
            headers["Authorization"] = f"OAuth {self.oauth_token}"

        try:
            r = self.session.post(
                self._spade_url_cache,
                data={"data": b64_data},
                headers=headers,
                timeout=6
            )
            return r.status_code in (200, 204)
        except Exception:
            return False

    # -----------------------------------------------------------------
    # PUNTI CANALE, AUTO-CLAIM BAULE BONUS, SONDAGGI, PRONOSTICI E DROP
    # -----------------------------------------------------------------
    def fetch_channel_live_context(self, channel_login):
        """
        Replica ChannelPointContextResponse.kt, Poll.kt, Prediction.kt di Xtra:
        Recupera in una sola chiamata:
        - ID Canale, ID Broadcast (per i Drop)
        - Saldo Punti Canale dell'utente + ID Baule Bonus da +50 punti
        - Lista completa delle Ricompense Riscattabili (customRewards)
        - Sondaggio attivo (Poll) e Pronostico attivo (Prediction)
        """
        channel_login = channel_login.strip().lower()
        q = {
            "query": """
            query GetChannelFullLiveContext($login: String!) {
              user(login: $login) {
                id
                login
                displayName
                stream {
                  id
                  title
                  viewersCount
                  game { id name }
                }
                channel {
                  id
                  self {
                    communityPoints {
                      balance
                      availableClaim { id }
                    }
                  }
                  communityPointsSettings {
                    name
                    isEnabled
                    customRewards {
                      id
                      title
                      cost
                      prompt
                      isEnabled
                      isPaused
                      isInStock
                      isUserInputRequired
                      backgroundColor
                    }
                  }
                }
              }
            }
            """,
            "variables": {"login": channel_login}
        }
        data = self.gql_post(q, use_auth=bool(self.oauth_token))
        u = (data.get("data") or {}).get("user")
        if not u and self.oauth_token and self.auth_client_id != GQL_CLIENT_ID:
            try:
                hdrs = {"Client-Id": GQL_CLIENT_ID, "Content-Type": "application/json", "Authorization": f"OAuth {self.oauth_token}"}
                r = self.session.post(GQL_URL, json=q, headers=hdrs, timeout=8)
                data = r.json()
                u = (data.get("data") or {}).get("user")
            except Exception:
                pass
        if not u and self.oauth_token:
            try:
                data = self.gql_post(q, use_auth=False)
                u = (data.get("data") or {}).get("user")
            except Exception:
                pass
        if not u:
            return None

        auto_rewards_raw = []
        try:
            q_auto = {
                "query": """
                query GetChannelAutomaticRewards($login: String!) {
                  user(login: $login) {
                    channel {
                      communityPointsSettings {
                        automaticRewards {
                          id
                          type
                          cost
                          defaultCost
                          isEnabled
                          isHiddenForSubs
                          backgroundColor
                        }
                      }
                    }
                  }
                }
                """,
                "variables": {"login": channel_login}
            }
            adata = self.gql_post(q_auto, use_auth=bool(self.oauth_token))
            au = (adata.get("data") or {}).get("user")
            if not au and self.oauth_token:
                adata = self.gql_post(q_auto, use_auth=False)
                au = (adata.get("data") or {}).get("user")
            auto_rewards_raw = ((((au or {}).get("channel") or {}).get("communityPointsSettings") or {}).get("automaticRewards") or [])
        except Exception:
            pass

        poll_pred = self.fetch_channel_polls_and_predictions(channel_login)
        active_poll = poll_pred.get("active_poll")
        active_prediction = poll_pred.get("active_prediction")

        st = u.get("stream") or {}
        ch = u.get("channel") or {}
        ch_self = (ch.get("self") or {}).get("communityPoints") or {}
        cp_settings = ch.get("communityPointsSettings") or {}

        AUTO_REWARD_LABELS = {
            "SEND_HIGHLIGHTED_MESSAGE": ("✨ Evidenzia il mio messaggio", "Metti in risalto il tuo messaggio in chat", True),
            "HIGHLIGHT_MY_MESSAGE": ("✨ Evidenzia il mio messaggio", "Metti in risalto il tuo messaggio in chat", True),
            "RANDOM_SUB_EMOTE_UNLOCK": ("🎲 Sblocca un'emoticon abbonamento", "Sblocca casualmente un'emoticon abbonato del canale per 24 ore", False),
            "CHOSEN_SUB_EMOTE_UNLOCK": ("🎯 Scegli un'emoticon da sbloccare", "Scegli un'emoticon abbonato del canale da sbloccare per 24 ore", False),
            "SINGLE_MESSAGE_BYPASS_SUB_MODE": ("💬 Messaggio in Solo Abbonati", "Invia un messaggio anche se la chat è in modalità Solo Abbonati", True),
            "GIGANTIFY_AN_EMOTE": ("🔍 Ingigantisci un'emoticon", "Rendi gigante un'emoticon nel tuo prossimo messaggio", True),
            "CELEBRATION": ("🎉 Celebrazione in chat", "Attiva una celebrazione con emoticon sullo schermo", False),
            "ON_SCREEN_CELEBRATION": ("🎉 Celebrazione sullo schermo", "Attiva una celebrazione sullo schermo", False),
        }

        rewards = []
        for arw in auto_rewards_raw:
            if not arw or not arw.get("isEnabled", True):
                continue
            cost_val = int(arw.get("cost") or arw.get("defaultCost") or 0)
            if cost_val <= 0:
                continue
            rtype = str(arw.get("type") or "")
            title_lbl, desc_lbl, inp_req = AUTO_REWARD_LABELS.get(
                rtype,
                (rtype.replace("_", " ").title() or "Ricompensa Twitch", "Ricompensa automatica Twitch", False)
            )
            rewards.append({
                "id": arw.get("id") or rtype,
                "title": title_lbl,
                "cost": cost_val,
                "prompt": desc_lbl,
                "input_required": inp_req,
                "color": arw.get("backgroundColor") or C_ACCENT,
                "is_automatic": True,
                "auto_type": rtype
            })

        for rw in (cp_settings.get("customRewards") or []):
            if not rw or not rw.get("isEnabled", True) or rw.get("isPaused", False) or not rw.get("isInStock", True):
                continue
            rewards.append({
                "id": rw["id"],
                "title": rw.get("title") or "Ricompensa",
                "cost": int(rw.get("cost") or 0),
                "prompt": rw.get("prompt") or "",
                "input_required": bool(rw.get("isUserInputRequired")),
                "color": rw.get("backgroundColor") or C_ACCENT,
                "is_automatic": False,
                "auto_type": None
            })
        rewards.sort(key=lambda x: x["cost"])

        ch_id_val = u.get("id") or ch.get("id") or ""
        game_name_val = (st.get("game") or {}).get("name") or ""
        channel_drop_campaigns = []
        drops_eligible = False
        if ch_id_val and st.get("id"):
            try:
                q_ch_drops = {
                    "query": """
                    query ChannelDrops($channelID: ID!) {
                      channel(id: $channelID) {
                        id
                        viewerDropCampaigns {
                          id
                          name
                          status
                          game { id name displayName }
                        }
                      }
                    }
                    """,
                    "variables": {"channelID": str(ch_id_val)}
                }
                dres = self.gql_post(q_ch_drops, use_auth=bool(self.oauth_token))
                raw_cd = (((dres.get("data") or {}).get("channel") or {}).get("viewerDropCampaigns")) or []
                for dc in raw_cd:
                    if not dc:
                        continue
                    dst = str(dc.get("status") or "ACTIVE").upper()
                    if dst in ("EXPIRED", "DISABLED", "ENDED"):
                        continue
                    dg = (dc.get("game") or {}).get("displayName") or (dc.get("game") or {}).get("name") or ""
                    channel_drop_campaigns.append({
                        "id": str(dc.get("id") or ""),
                        "name": str(dc.get("name") or "Drop Attivo"),
                        "status": dst,
                        "game_name": dg,
                    })
                    if dst == "ACTIVE" and (not game_name_val or not dg or dg.lower() == game_name_val.lower()):
                        drops_eligible = True
            except Exception:
                pass

        return {
            "channel_id": ch_id_val,
            "broadcast_id": st.get("id") or "",
            "game_id": (st.get("game") or {}).get("id") or "",
            "game_name": game_name_val,
            "points_balance": ch_self.get("balance"),
            "points_name": cp_settings.get("name") or "Punti Canale",
            "claim_id": (ch_self.get("availableClaim") or {}).get("id"),
            "rewards": rewards,
            "active_poll": active_poll,
            "active_prediction": active_prediction,
            "drops_eligible": drops_eligible,
            "channel_drop_campaigns": channel_drop_campaigns,
        }

    def _gql_query_channel_fallback(self, query_obj):
        """Esegue una query GQL canale con fallback automatico su GQL_CLIENT_ID e chiamata pubblica se il client token fallisce."""
        use_a = bool(self.oauth_token)
        try:
            res = self.gql_post(query_obj, use_auth=use_a)
            user_obj = ((res or {}).get("data") or {}).get("user")
            if user_obj is not None and not (res or {}).get("errors"):
                return res
        except Exception:
            res = {}
        if use_a:
            try:
                res2 = self.gql_post(query_obj, use_auth=True, custom_client_id=GQL_CLIENT_ID)
                user_obj2 = ((res2 or {}).get("data") or {}).get("user")
                if user_obj2 is not None and not (res2 or {}).get("errors"):
                    return res2
            except Exception:
                pass
            try:
                res3 = self.gql_post(query_obj, use_auth=False, custom_client_id=GQL_CLIENT_ID)
                if ((res3 or {}).get("data") or {}).get("user") is not None:
                    return res3
            except Exception:
                pass
        return res or {}

    def fetch_channel_polls_and_predictions(self, channel_login):
        """Recupera Sondaggi attivi (Poll) e Pronostici/Bet (PredictionEvent) per il canale."""
        channel_login = (channel_login or "").strip().lower()
        if not channel_login:
            return {"active_poll": None, "active_prediction": None}

        active_poll = None
        try:
            q_poll = {
                "query": """
                query GetChannelPoll($login: String!) {
                  user(login: $login) {
                    channel {
                      activePoll {
                        id
                        title
                        status
                        totalVoters
                        remainingDurationMilliseconds
                        choices {
                          id
                          title
                          totalVoters
                        }
                      }
                    }
                  }
                }
                """,
                "variables": {"login": channel_login},
            }
            pdata = self._gql_query_channel_fallback(q_poll)
            active_poll = (((pdata.get("data") or {}).get("user") or {}).get("channel") or {}).get("activePoll")
            if active_poll is None:
                q_poll_edge = {
                    "query": """
                    query GetChannelLatestPoll($login: String!) {
                      user(login: $login) {
                        channel {
                          polls(first: 1) {
                            edges {
                              node {
                                id
                                title
                                status
                                totalVoters
                                remainingDurationMilliseconds
                                choices {
                                  id
                                  title
                                  totalVoters
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                    """,
                    "variables": {"login": channel_login},
                }
                ep = self._gql_query_channel_fallback(q_poll_edge)
                edges = ((((ep.get("data") or {}).get("user") or {}).get("channel") or {}).get("polls") or {}).get("edges") or []
                if edges:
                    cand = (edges[0] or {}).get("node")
                    if cand and cand.get("status") in ("ACTIVE", "COMPLETED"):
                        active_poll = cand
        except Exception:
            pass

        active_prediction = None
        try:
            q_pred = {
                "query": """
                query GetChannelPredictions($login: String!) {
                  user(login: $login) {
                    channel {
                      activePredictionEvents {
                        id
                        title
                        status
                        predictionWindowSeconds
                        createdAt
                        lockedAt
                        endedAt
                        winningOutcome { id title }
                        outcomes {
                          id
                          title
                          color
                          totalUsers
                          totalPoints
                        }
                      }
                    }
                  }
                }
                """,
                "variables": {"login": channel_login},
            }
            pr_data = self._gql_query_channel_fallback(q_pred)
            evs = (((pr_data.get("data") or {}).get("user") or {}).get("channel") or {}).get("activePredictionEvents") or []
            for ev in evs:
                if ev and ev.get("status") in ("ACTIVE", "LOCKED", "RESOLVE_PENDING", "RESOLVED"):
                    active_prediction = ev
                    break
            if active_prediction is None:
                q_pred_res = {
                    "query": """
                    query GetChannelResolvedPrediction($login: String!) {
                      user(login: $login) {
                        channel {
                          resolvedPredictionEvents(first: 1) {
                            edges {
                              node {
                                id
                                title
                                status
                                endedAt
                                winningOutcome { id title }
                                outcomes {
                                  id
                                  title
                                  color
                                  totalUsers
                                  totalPoints
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                    """,
                    "variables": {"login": channel_login},
                }
                rr = self._gql_query_channel_fallback(q_pred_res)
                r_edges = ((((rr.get("data") or {}).get("user") or {}).get("channel") or {}).get("resolvedPredictionEvents") or {}).get("edges") or []
                if r_edges:
                    cand_ev = (r_edges[0] or {}).get("node")
                    ended_iso = (cand_ev or {}).get("endedAt") or ""
                    if cand_ev and ended_iso:
                        try:
                            import datetime as _dt
                            dt_end = _dt.datetime.fromisoformat(ended_iso.replace("Z", "+00:00"))
                            age_sec = (_dt.datetime.now(_dt.timezone.utc) - dt_end).total_seconds()
                            if -5 <= age_sec <= 45:
                                active_prediction = cand_ev
                        except Exception:
                            pass
        except Exception:
            pass

        return {"active_poll": active_poll, "active_prediction": active_prediction}

    def cast_poll_vote(self, poll_id, choice_id):
        if not self.oauth_token or not poll_id or not choice_id:
            return False, "Effettua il Login per votare nei sondaggi."
        q = {
            "query": """
            mutation VotePoll($input: VotePollInput!) {
              votePoll(input: $input) {
                poll { id }
              }
            }
            """,
            "variables": {"input": {"pollID": str(poll_id), "choiceID": str(choice_id)}},
        }
        try:
            res = self.gql_post(q, use_auth=True, custom_client_id=GQL_CLIENT_ID)
            if res.get("errors"):
                msg = "; ".join(str(e.get("message") or "") for e in res.get("errors", []))
                return False, msg or "Voto non riuscito (Twitch potrebbe richiedere il browser)."
            if ((res.get("data") or {}).get("votePoll") or {}).get("poll"):
                return True, "Voto registrato!"
            return False, "Impossibile registrare il voto."
        except Exception as e:
            return False, str(e)

    def place_prediction_bet(self, event_id, outcome_id, points):
        if not self.oauth_token or not event_id or not outcome_id:
            return False, "Effettua il Login per puntare nelle bet."
        q = {
            "query": """
            mutation MakePrediction($input: MakePredictionInput!) {
              makePrediction(input: $input) {
                error { code }
              }
            }
            """,
            "variables": {
                "input": {
                    "eventID": str(event_id),
                    "outcomeID": str(outcome_id),
                    "points": int(max(10, points)),
                    "transactionID": uuid.uuid4().hex,
                }
            },
        }
        try:
            res = self.gql_post(q, use_auth=True, custom_client_id=GQL_CLIENT_ID)
            if res.get("errors"):
                msg = "; ".join(str(e.get("message") or "") for e in res.get("errors", []))
                return False, msg or "Puntata non riuscita (Twitch potrebbe richiedere il browser)."
            err = (((res.get("data") or {}).get("makePrediction") or {}).get("error"))
            if err:
                return False, f"Errore Twitch: {err.get('code')}"
            return True, f"Puntati {int(points)} punti!"
        except Exception as e:
            return False, str(e)

    def claim_community_points_bonus(self, channel_id, claim_id):
        """Riscatta automaticamente il baule bonus da +50 Punti Canale."""
        if not self.oauth_token or not channel_id or not claim_id:
            return False
        payload = {
            "operationName": "ClaimCommunityPoints",
            "variables": {
                "input": {
                    "channelID": str(channel_id),
                    "claimID": str(claim_id)
                }
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "46aaeebe02c99afdf4fc97c7c0cba964124bf6b0af229395f1f6d1feed05b3d0"
                }
            }
        }
        try:
            res = self.gql_post(payload, use_auth=True)
            err = (((res.get("data") or {}).get("claimCommunityPoints") or {}).get("error"))
            return err is None
        except Exception:
            return False

    def redeem_custom_reward(self, channel_id, reward_id, title, cost, prompt_text=None, is_automatic=False, auto_type=None):
        """Riscatta una ricompensa punti canale (personalizzata o automatica Twitch)."""
        self.last_redeem_details = {}
        if not self.oauth_token:
            return False, "Devi effettuare il Login per riscattare le ricompense."

        if is_automatic:
            if auto_type == "RANDOM_SUB_EMOTE_UNLOCK":
                inp = {
                    "channelID": str(channel_id),
                    "cost": int(cost),
                    "transactionID": uuid.uuid4().hex
                }
                q = {
                    "query": """
                    mutation UnlockRandomSubscriberEmote($input: UnlockRandomSubscriberEmoteInput!) {
                      unlockRandomSubscriberEmote(input: $input) {
                        error { code }
                        emote { id token }
                        balance
                      }
                    }
                    """,
                    "variables": {"input": inp}
                }
                try:
                    res = self.gql_post(q, use_auth=True)
                    if res.get("errors"):
                        err_msg = "; ".join(str(e.get("message") or "") for e in res.get("errors", []))
                        low = err_msg.lower()
                        if "integrity" in low or "captcha" in low or "challenge" in low or "unauthenticated" in low:
                            return False, "NEED_BROWSER:Twitch richiede la verifica anti-bot dal browser per sbloccare l'emoticon casuale."
                        return False, f"Errore Twitch: {err_msg or 'Riscatto non riuscito'}"
                    payload_res = ((res.get("data") or {}).get("unlockRandomSubscriberEmote") or {})
                    err = payload_res.get("error")
                    if err:
                        return False, f"Errore Twitch: {err.get('code')}"
                    em = payload_res.get("emote") or {}
                    em_id = str(em.get("id") or "")
                    em_token = str(em.get("token") or "")
                    self.last_redeem_details = {
                        "emote_id": em_id,
                        "emote_token": em_token,
                        "balance": payload_res.get("balance"),
                        "emote_url": f"https://static-cdn.jtvnw.net/emoticons/v2/{em_id}/default/dark/2.0" if em_id else "",
                    }
                    if em_token:
                        return True, f"Hai sbloccato l'emoticon '{em_token}'!"
                    return True, "Emoticon abbonamento casuale sbloccata con successo!"
                except Exception:
                    return False, "NEED_BROWSER:Twitch richiede la verifica anti-bot dal browser per questa ricompensa."

            return False, (
                "NEED_BROWSER:Questa ricompensa automatica di Twitch "
                f"('{title}') richiede la conferma anti-bot nella chat web di Twitch."
            )

        inp = {
            "channelID": str(channel_id),
            "cost": int(cost),
            "prompt": prompt_text,
            "rewardID": str(reward_id),
            "title": title,
            "transactionID": uuid.uuid4().hex
        }
        q = {
            "query": """
            mutation RedeemCustomReward($input: RedeemCustomRewardInput!) {
              redeemCustomReward(input: $input) {
                error { code }
              }
            }
            """,
            "variables": {"input": inp}
        }
        try:
            res = self.gql_post(q, use_auth=True)
            err = (((res.get("data") or {}).get("redeemCustomReward") or {}).get("error"))
            if err:
                return False, f"Errore Twitch: {err.get('code')}"
            return True, "Ricompensa riscattata con successo!"
        except Exception as e:
            return False, str(e)

    def fetch_drops_inventory_and_campaigns(self, current_game_name=""):
        """
        Recupera i Drop di Twitch in progresso nell'inventario dell'utente
        (con minuti guardati, minuti richiesti e ID per il claim automatico).
        """
        if not self.oauth_token:
            return [], []

        q = {
            "query": """
            query ViewerDropsInventory {
              currentUser {
                id
                inventory {
                  dropCampaignsInProgress {
                    id
                    name
                    status
                    game { id displayName }
                    timeBasedDrops {
                      id
                      name
                      requiredMinutesWatched
                      self {
                        hasPreconditionsMet
                        currentMinutesWatched
                        isClaimed
                        dropInstanceID
                      }
                      benefitEdges {
                        benefit { name }
                      }
                    }
                  }
                }
              }
            }
            """
        }
        in_progress_drops = []
        auto_claimable_ids = []
        try:
            data = self.gql_post(q, use_auth=True)
            inv = (((data.get("data") or {}).get("currentUser") or {}).get("inventory")) or {}
            for camp in (inv.get("dropCampaignsInProgress") or []):
                if not camp:
                    continue
                g_name = (camp.get("game") or {}).get("displayName") or "Gioco"
                c_name = camp.get("name") or "Campagna Drop"
                is_current_game = bool(current_game_name and current_game_name.lower() == g_name.lower())

                for d in (camp.get("timeBasedDrops") or []):
                    if not d:
                        continue
                    req_min = int(d.get("requiredMinutesWatched") or 0)
                    d_self = d.get("self") or {}
                    cur_min = int(d_self.get("currentMinutesWatched") or 0)
                    claimed = bool(d_self.get("isClaimed"))
                    drop_inst_id = d_self.get("dropInstanceID")

                    benefits = [
                        (b.get("benefit") or {}).get("name", "")
                        for b in (d.get("benefitEdges") or [])
                        if (b.get("benefit") or {}).get("name")
                    ]
                    reward_name = ", ".join(benefits) if benefits else (d.get("name") or "Drop")

                    if not claimed and drop_inst_id and req_min > 0 and cur_min >= req_min:
                        auto_claimable_ids.append((drop_inst_id, reward_name))

                    in_progress_drops.append({
                        "campaign_id": str(camp.get("id") or ""),
                        "campaign_name": c_name,
                        "game_name": g_name,
                        "reward_name": reward_name,
                        "current_min": cur_min,
                        "required_min": req_min,
                        "claimed": claimed,
                        "drop_instance_id": drop_inst_id,
                        "is_current_game": is_current_game
                    })

            in_progress_drops.sort(key=lambda x: (not x["is_current_game"], x["claimed"], -x["current_min"]))
        except Exception:
            pass

        return in_progress_drops, auto_claimable_ids

    def fetch_all_active_drop_campaigns(self, current_game_name="", channel_id="", extra_channel_ids=None):
        """
        Recupera TUTTE le campagne Drop attualmente attive su Twitch combinando:
        1) Dashboard / Inventario utente autenticato (con Client-ID coerente al token);
        2) Campagne sui canali attualmente aperti (Singola o Multi-Live);
        3) Directory live pubblica Twitch ('DropsEnabled' + top giochi con Drop attivi),
           così funziona sempre anche se Twitch ruota gli hash o senza token web.
        """
        campaigns_by_id = {}
        diag_err = ""

        def _parse_drops_preview(raw_drops):
            out = []
            for d in (raw_drops or []):
                if not d:
                    continue
                benefits = [
                    (b.get("benefit") or {}).get("name", "")
                    for b in (d.get("benefitEdges") or [])
                    if (b.get("benefit") or {}).get("name")
                ]
                out.append({
                    "name": ", ".join(benefits) if benefits else (d.get("name") or "Ricompensa Drop"),
                    "required_min": int(d.get("requiredMinutesWatched") or 0),
                })
            return out

        def _register_campaign(camp, sample_channel=""):
            if not camp:
                return
            cid = str(camp.get("id") or "").strip()
            if not cid:
                return
            status = str(camp.get("status") or "ACTIVE").upper()
            if status in ("EXPIRED", "DISABLED", "ENDED"):
                return
            g_obj = camp.get("game") or {}
            g_name = g_obj.get("displayName") or g_obj.get("name") or "Twitch / Evento"
            is_cur = bool(current_game_name and g_name and current_game_name.lower() == g_name.lower())
            end_raw = str(camp.get("endAt") or "")
            end_short = end_raw[:10] if len(end_raw) >= 10 else ""
            preview = _parse_drops_preview(camp.get("timeBasedDrops"))

            existing = campaigns_by_id.get(cid)
            if existing:
                if sample_channel and not existing.get("sample_channel"):
                    existing["sample_channel"] = sample_channel
                if preview and not existing.get("drops_preview"):
                    existing["drops_preview"] = preview
                return

            campaigns_by_id[cid] = {
                "id": cid,
                "name": camp.get("name") or "Campagna Drop",
                "status": status,
                "game_name": g_name,
                "end_at": end_short,
                "details_url": camp.get("detailsURL") or "https://www.twitch.tv/drops/campaigns",
                "is_current_game": is_cur,
                "sample_channel": sample_channel or "",
                "drops_preview": preview,
            }

        # 1. Query autenticata completa (dashboard + inventario in progresso) senza forzare custom_client_id
        if self.oauth_token:
            q_user = {
                "query": """
                query ViewerDropsDashboardCombined {
                  currentUser {
                    id
                    dropCampaigns {
                      id
                      name
                      status
                      startAt
                      endAt
                      detailsURL
                      accountLinkURL
                      game { id name displayName }
                      timeBasedDrops {
                        id
                        name
                        requiredMinutesWatched
                        benefitEdges { benefit { name } }
                      }
                    }
                    inventory {
                      dropCampaignsInProgress {
                        id
                        name
                        status
                        startAt
                        endAt
                        detailsURL
                        game { id name displayName }
                        timeBasedDrops {
                          id
                          name
                          requiredMinutesWatched
                          benefitEdges { benefit { name } }
                        }
                      }
                    }
                  }
                }
                """
            }
            try:
                res = self.gql_post(q_user, use_auth=True)
                cu = (res.get("data") or {}).get("currentUser") or {}
                for c in (cu.get("dropCampaigns") or []):
                    _register_campaign(c)
                inv = cu.get("inventory") or {}
                for c in (inv.get("dropCampaignsInProgress") or []):
                    _register_campaign(c)
                if not campaigns_by_id and res.get("errors"):
                    diag_err = res["errors"][0].get("message", "")
            except Exception as e:
                diag_err = str(e)

        # 2. Campagne attive direttamente sul canale aperto (o sui canali Multi-Live)
        ch_ids = []
        if channel_id:
            ch_ids.append(str(channel_id))
        for cid_extra in (extra_channel_ids or []):
            if cid_extra and str(cid_extra) not in ch_ids:
                ch_ids.append(str(cid_extra))
        for target_cid in ch_ids:
            try:
                q_ch = {
                    "query": """
                    query ChannelDrops($channelID: ID!) {
                      channel(id: $channelID) {
                        id
                        name
                        viewerDropCampaigns {
                          id
                          name
                          status
                          startAt
                          endAt
                          detailsURL
                          game { id name displayName }
                          timeBasedDrops {
                            id
                            name
                            requiredMinutesWatched
                            benefitEdges { benefit { name } }
                          }
                        }
                      }
                    }
                    """,
                    "variables": {"channelID": target_cid}
                }
                res_ch = self.gql_post(q_ch, use_auth=bool(self.oauth_token))
                ch_obj = ((res_ch.get("data") or {}).get("channel") or {})
                ch_login = ch_obj.get("name") or ""
                for c in (ch_obj.get("viewerDropCampaigns") or []):
                    _register_campaign(c, sample_channel=ch_login)
            except Exception:
                pass

        # 3. Scoperta pubblica dalla directory Twitch ('DropsEnabled' + top categorie live)
        try:
            q_public = {
                "query": """
                query PublicActiveDropsDiscovery {
                  streams(first: 30, options: {freeformTags: ["DropsEnabled"]}) {
                    edges {
                      node {
                        broadcaster {
                          id
                          login
                          displayName
                          channel {
                            viewerDropCampaigns {
                              id
                              name
                              status
                              startAt
                              endAt
                              detailsURL
                              game { id name displayName }
                              timeBasedDrops {
                                id
                                name
                                requiredMinutesWatched
                                benefitEdges { benefit { name } }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                  games(first: 30) {
                    edges {
                      node {
                        streams(first: 3) {
                          edges {
                            node {
                              broadcaster {
                                login
                                channel {
                                  viewerDropCampaigns {
                                    id
                                    name
                                    status
                                    startAt
                                    endAt
                                    detailsURL
                                    game { id name displayName }
                                    timeBasedDrops {
                                      id
                                      name
                                      requiredMinutesWatched
                                      benefitEdges { benefit { name } }
                                    }
                                  }
                                }
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
                """
            }
            res_pub = self.gql_post(q_public, use_auth=False, custom_client_id=GQL_CLIENT_ID)
            data_pub = res_pub.get("data") or {}
            for e in ((data_pub.get("streams") or {}).get("edges") or []):
                b = ((e.get("node") or {}).get("broadcaster") or {})
                b_login = b.get("login") or ""
                for c in ((b.get("channel") or {}).get("viewerDropCampaigns") or []):
                    _register_campaign(c, sample_channel=b_login)
            for ge in ((data_pub.get("games") or {}).get("edges") or []):
                for se in (((ge.get("node") or {}).get("streams") or {}).get("edges") or []):
                    b = ((se.get("node") or {}).get("broadcaster") or {})
                    b_login = b.get("login") or ""
                    for c in ((b.get("channel") or {}).get("viewerDropCampaigns") or []):
                        _register_campaign(c, sample_channel=b_login)
        except Exception as e:
            if not diag_err:
                diag_err = str(e)

        active_list = list(campaigns_by_id.values())
        active_list.sort(key=lambda x: (not x["is_current_game"], x["status"] != "ACTIVE", x["game_name"].lower(), x["name"].lower()))
        return active_list, (diag_err if not active_list else "")

    def fetch_notifications(self, limit=35):
        """
        Recupera le notifiche Twitch ufficiali (live, drop sbloccati, eventi account)
        più lo storico recente dei Drop sbloccati dall'inventario (gameEventDrops).
        """
        if not self.oauth_token:
            return {
                "unseen_count": 0,
                "notifications": [],
                "unlocked_drops": [],
                "error": "Effettua il Login a Twitch per vedere le tue notifiche ufficiali e i Drop sbloccati.",
            }

        q = {
            "query": """
            query TwixyNotificationsAndDrops($first: Int!) {
              currentUser {
                id
                notifications(first: $first) {
                  summary {
                    unseenCount
                    lastSeenAt
                  }
                  edges {
                    node {
                      id
                      body
                      type
                      createdAt
                      updatedAt
                      isRead
                      thumbnailURL
                      displayType
                      renderStyle
                      creators {
                        id
                        login
                        displayName
                      }
                      actions {
                        id
                        type
                        label
                        url
                        body
                      }
                    }
                  }
                }
                inventory {
                  gameEventDrops {
                    id
                    name
                    lastAwardedAt
                    imageURL
                    totalCount
                    game {
                      id
                      displayName
                    }
                  }
                }
              }
            }
            """,
            "variables": {"first": int(limit)}
        }
        notifs = []
        unlocked = []
        unseen_count = 0
        err_msg = ""
        try:
            res = self.gql_post(q, use_auth=True)
            cu = (res.get("data") or {}).get("currentUser")
            if cu is None and res.get("errors"):
                err_msg = res["errors"][0].get("message", "")
            cu = cu or {}
            n_conn = cu.get("notifications") or {}
            unseen_count = int(((n_conn.get("summary") or {}).get("unseenCount")) or 0)
            for edge in (n_conn.get("edges") or []):
                node = (edge or {}).get("node") or {}
                if not node:
                    continue
                creators = [c for c in (node.get("creators") or []) if c]
                actions = [a for a in (node.get("actions") or []) if a]
                channel_login = creators[0].get("login") if creators else ""
                act_url = ""
                for a in actions:
                    if a.get("url"):
                        act_url = a["url"]
                        break
                notifs.append({
                    "id": str(node.get("id") or ""),
                    "body": str(node.get("body") or ""),
                    "type": str(node.get("type") or node.get("displayType") or "notification"),
                    "created_at": str(node.get("createdAt") or ""),
                    "is_read": bool(node.get("isRead")),
                    "thumbnail_url": str(node.get("thumbnailURL") or ""),
                    "channel_login": channel_login or "",
                    "url": act_url,
                })

            inv = cu.get("inventory") or {}
            for gd in (inv.get("gameEventDrops") or []):
                if not gd:
                    continue
                unlocked.append({
                    "id": str(gd.get("id") or ""),
                    "name": str(gd.get("name") or "Drop sbloccato"),
                    "game_name": ((gd.get("game") or {}).get("displayName")) or "Twitch Drop",
                    "awarded_at": str(gd.get("lastAwardedAt") or ""),
                    "image_url": str(gd.get("imageURL") or ""),
                    "total_count": int(gd.get("totalCount") or 1),
                })
            unlocked.sort(key=lambda x: x["awarded_at"], reverse=True)
        except Exception as e:
            err_msg = str(e)

        return {
            "unseen_count": unseen_count,
            "notifications": notifs,
            "unlocked_drops": unlocked,
            "error": err_msg,
        }

    def fetch_drop_campaign_details(self, campaign_id, viewer_login=""):
        """Recupera i singoli premi e minuti richiesti per una campagna Drop."""
        if not self.oauth_token or not campaign_id:
            return []
        try:
            q = {
                "operationName": "DropCampaignDetails",
                "variables": {"dropID": str(campaign_id), "channelLogin": viewer_login or self.user_id or ""},
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "e7acdecb05429a62f5984bdcb27ee938ae20543579bf73c3ae44e7c822bc4f54"
                    }
                }
            }
            res = self.gql_post(q, use_auth=True, custom_client_id=GQL_CLIENT_ID)
            camp = ((res.get("data") or {}).get("user") or {}).get("dropCampaign") or {}
            drops_out = []
            for d in (camp.get("timeBasedDrops") or []):
                if not d:
                    continue
                benefits = [
                    (b.get("benefit") or {}).get("name", "")
                    for b in (d.get("benefitEdges") or [])
                    if (b.get("benefit") or {}).get("name")
                ]
                drops_out.append({
                    "name": ", ".join(benefits) if benefits else (d.get("name") or "Ricompensa Drop"),
                    "required_min": int(d.get("requiredMinutesWatched") or 0)
                })
            return drops_out
        except Exception:
            return []

    def claim_drop_reward(self, drop_instance_id):
        """Riscatta un Drop completato (100%) tramite GraphQL."""
        if not self.oauth_token or not drop_instance_id:
            return False
        payload = {
            "operationName": "DropsPage_ClaimDropRewards",
            "variables": {
                "input": {
                    "dropInstanceID": str(drop_instance_id)
                }
            },
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": "a455deea71bdc9015b78eb49f4acfbce8baa7ccbedd28e549bb025bd0f751930"
                }
            }
        }
        try:
            res = self.gql_post(payload, use_auth=True)
            return "errors" not in res
        except Exception:
            return False

    # -----------------------------------------------------------------
    # RICERCA, LIVE STREAM, VOD & FOLLOWED
    # -----------------------------------------------------------------
    @staticmethod
    def _node_to_channel_card(node, force_live=False):
        """Normalize Twitch channel node into card dict, keeping last archive category when offline."""
        st = node.get("stream")
        vod_edges = (node.get("videos") or {}).get("edges") or []
        is_live = True if force_live else (st is not None)
        st_dict = st if isinstance(st, dict) else {}
        game = (st_dict.get("game") or {}).get("name", "") if st else ""
        if not game and vod_edges:
            game = ((vod_edges[0].get("node") or {}).get("game") or {}).get("name", "")
        tags = [t.get("name") for t in (st_dict.get("freeformTags") or []) if t and t.get("name")]
        return {
            "login": node["login"],
            "display_name": node.get("displayName") or node["login"],
            "avatar_url": str(node.get("profileImageURL") or ""),
            "has_vods": bool(vod_edges),
            "is_live": is_live,
            "viewers": st_dict.get("viewersCount", 0) if st else 0,
            "game": game,
            "title": st_dict.get("title", "") if st else "",
            "tags": tags,
        }

    def search_channels(self, query_text, limit=25):
        query_text = query_text.strip()
        if not query_text:
            return []
        gql = {
            "query": """
            query SearchChannels($query: String!, $first: Int!) {
              searchUsers(userQuery: $query, first: $first) {
                edges {
                  node {
                    id
                    login
                    displayName
                    profileImageURL(width: 70)
                    videos(first: 1, type: ARCHIVE) {
                      edges {
                        node { id game { name } }
                      }
                    }
                    stream {
                      id
                      title
                      viewersCount
                      game { name }
                      freeformTags { name }
                    }
                  }
                }
              }
            }
            """,
            "variables": {"query": query_text, "first": limit}
        }
        res = self.gql_post(gql, use_auth=False)
        edges = ((res.get("data") or {}).get("searchUsers") or {}).get("edges") or []
        results = []
        for edge in edges:
            node = edge.get("node")
            if not node or not node.get("login"):
                continue
            st = node.get("stream")
            results.append(self._node_to_channel_card(node))
        return results

    @staticmethod
    def parse_m3u8_variants(m3u8_text):
        qualities = {}
        lines = [line.strip() for line in m3u8_text.splitlines() if line.strip()]
        media_names = {}

        for line in lines:
            if line.startswith("#EXT-X-MEDIA:"):
                group_id, name = "", ""
                for part in line[13:].split(","):
                    if part.startswith("GROUP-ID="):
                        group_id = part.split("=", 1)[1].strip('"')
                    elif part.startswith("NAME="):
                        name = part.split("=", 1)[1].strip('"')
                if group_id and name:
                    media_names[group_id] = name

        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#EXT-X-STREAM-INF:"):
                info = line[18:]
                res, fps, video_group = "", "", ""
                for part in info.split(","):
                    if part.startswith("RESOLUTION="):
                        res = part.split("=", 1)[1].strip('"')
                    elif part.startswith("FRAME-RATE="):
                        try:
                            fps_val = int(round(float(part.split("=", 1)[1])))
                            fps = f"{fps_val}" if fps_val > 30 else ""
                        except Exception:
                            pass
                    elif part.startswith("VIDEO="):
                        video_group = part.split("=", 1)[1].strip('"')

                i += 1
                while i < len(lines) and lines[i].startswith("#"):
                    i += 1
                if i < len(lines):
                    url = lines[i]
                    raw_name = media_names.get(video_group, video_group)
                    if video_group == "chunked" or "source" in raw_name.lower():
                        height = res.split("x")[1] if "x" in res else "1080"
                        label = f"{height}p{fps} (Source)"
                    elif "audio" in video_group.lower() or "audio" in raw_name.lower():
                        label = "Audio Only"
                    elif raw_name:
                        label = raw_name
                    elif "x" in res:
                        label = f"{res.split('x')[1]}p{fps}"
                    else:
                        label = video_group or "Stream"
                    qualities[label] = url
            i += 1
        return qualities

    def _fetch_via_xtra_gql_usher(self, channel, player_types=("site", "embed", "autoplay"), anonymous=True):
        for ptype in player_types:
            try:
                fallback_q = {
                    "query": """
                    query StreamPlaybackAccessToken($login: String!, $playerType: String!) {
                      streamPlaybackAccessToken(channelName: $login, params: {platform: "android", playerBackend: "mediaplayer", playerType: $playerType}) {
                        value
                        signature
                      }
                    }
                    """,
                    "variables": {"login": channel, "playerType": ptype}
                }
                data = self.gql_post(fallback_q, use_auth=(not anonymous and bool(self.oauth_token)))
                token_data = (data.get("data") or {}).get("streamPlaybackAccessToken")
                if not token_data:
                    continue

                params = {
                    "client_id": GQL_CLIENT_ID,
                    "token": token_data["value"],
                    "sig": token_data["signature"],
                    "allow_source": "true",
                    "allow_audio_only": "true",
                    "fast_bread": "true",
                    "player_backend": "mediaplayer",
                    "playlist_include_framerate": "true",
                    "reassignments_supported": "true",
                    "p": str(random.randint(100000, 999999))
                }
                usher_url = f"https://usher.ttvnw.net/api/channel/hls/{channel}.m3u8?{urllib.parse.urlencode(params)}"
                r = self.session.get(usher_url, timeout=8)
                if r.status_code == 200 and "#EXTM3U" in r.text:
                    quals = self.parse_m3u8_variants(r.text)
                    if quals:
                        return quals, f"🛡️ 0 Ads • Xtra Android ({ptype})"
            except Exception:
                pass
        return None, None

    def _fetch_via_xtra_stream_proxy(self, channel):
        proxy_configs = [
            (f"https://eu.luminous.dev/live/{channel}?allow_source=true&allow_audio_only=true&fast_bread=true", {}),
            (f"https://as.luminous.dev/live/{channel}?allow_source=true&allow_audio_only=true&fast_bread=true", {}),
        ]
        for purl, extra_headers in proxy_configs:
            try:
                r = self.session.get(purl, headers=extra_headers, timeout=4.5)
                if r.status_code == 200 and "#EXTM3U" in r.text:
                    quals = self.parse_m3u8_variants(r.text)
                    if quals:
                        return quals, "🛡️ 0 Ads • Proxy"
            except Exception:
                pass
        return None, None

    def get_live_stream_qualities(self, channel, mode="proxy_first"):
        channel = channel.strip().lower()
        # Evita di usare 'embed' come unico backup: su canali partner ad alta densità (es. tumblurr) riceve stitched-ad al 100%
        backup_quals, _ = self._fetch_via_xtra_gql_usher(channel, ("site", "popout", "frontpage", "autoplay"), anonymous=True)

        primary_quals, label = None, None
        if mode == "proxy_first":
            primary_quals, label = self._fetch_via_xtra_stream_proxy(channel)
            if not primary_quals:
                primary_quals, label = self._fetch_via_xtra_gql_usher(channel, ("site", "popout", "frontpage", "embed", "autoplay"), anonymous=True)
        elif mode == "xtra_direct":
            primary_quals, label = self._fetch_via_xtra_gql_usher(channel, ("site", "popout", "frontpage", "embed", "autoplay"), anonymous=True)
            if not primary_quals:
                primary_quals, label = self._fetch_via_xtra_stream_proxy(channel)
        elif mode == "direct_embed":
            primary_quals, label = self._fetch_via_xtra_gql_usher(channel, ("popout", "frontpage", "embed", "autoplay", "site"), anonymous=True)

        if primary_quals:
            return primary_quals, backup_quals or {}, label

        raise RuntimeError(f"Il canale '{channel}' è attualmente Offline o non disponibile.")

    def refresh_slot_urls(self, channel, preferred_q=""):
        """Rigenera al volo URL primari e di backup se il proxy o il token Usher scade/va in ad-break."""
        ch = (channel or "").strip().lower()
        if not ch:
            return None, []
        candidates = []
        p_quals, _ = self._fetch_via_xtra_stream_proxy(ch)
        if p_quals:
            u = p_quals.get(preferred_q) or next(iter(p_quals.values()), None)
            if u:
                candidates.append(u)
        for pt in ("site", "popout", "frontpage", "autoplay"):
            q_map, _ = self._fetch_via_xtra_gql_usher(ch, (pt,), anonymous=True)
            if q_map:
                u = q_map.get(preferred_q) or next(iter(q_map.values()), None)
                if u and u not in candidates:
                    candidates.append(u)
        if not candidates:
            return None, []
        return candidates[0], candidates[1:]

    def get_channel_vods(self, channel, limit=30):
        channel = channel.strip().lower()
        query = {
            "query": """
            query GetChannelVideos($login: String!, $first: Int!) {
              user(login: $login) {
                id
                displayName
                videos(first: $first, sort: TIME) {
                  edges {
                    node {
                      id
                      title
                      lengthSeconds
                      viewCount
                      createdAt
                      broadcastType
                      seekPreviewsURL
                      game { name }
                      resourceRestriction { id type }
                    }
                  }
                }
              }
            }
            """,
            "variables": {"login": channel, "first": limit}
        }
        res = self.gql_post(query, use_auth=False)
        user_node = (res.get("data") or {}).get("user")
        if not user_node or not user_node.get("videos"):
            return []

        vods = []
        for edge in user_node["videos"].get("edges", []):
            node = edge.get("node")
            if not node:
                continue
            vods.append({
                "id": node["id"],
                "title": node.get("title") or "Senza titolo",
                "duration": node.get("lengthSeconds") or 0,
                "views": node.get("viewCount") or 0,
                "created_at": (node.get("createdAt") or "")[:10],
                "broadcast_type": node.get("broadcastType") or "ARCHIVE",
                "seek_previews_url": node.get("seekPreviewsURL") or "",
                "game": (node.get("game") or {}).get("name") or "Twitch",
                "sub_only": node.get("resourceRestriction") is not None
            })
        return vods

    def get_live_archive_vod_playlist(self, channel_login, preferred_quality=""):
        """Recupera la playlist HLS dell'archivio VOD attivo di una live in corso per consentire clip fino a 2 minuti subito."""
        channel_login = (channel_login or "").strip().lower()
        if not channel_login:
            return None, ""
        try:
            q = {
                "query": """
                query GetLiveArchiveVod($login: String!) {
                  user(login: $login) {
                    stream { id createdAt }
                    videos(first: 1, type: ARCHIVE, sort: TIME) {
                      edges {
                        node {
                          id
                          createdAt
                          lengthSeconds
                          seekPreviewsURL
                          broadcastType
                          resourceRestriction { id }
                        }
                      }
                    }
                  }
                }
                """,
                "variables": {"login": channel_login},
            }
            data = self.gql_post(q, use_auth=bool(self.oauth_token))
            u = (data.get("data") or {}).get("user") or {}
            st = u.get("stream")
            edges = ((u.get("videos") or {}).get("edges") or [])
            if not st or not edges or not edges[0].get("node"):
                return None, ""
            node = edges[0]["node"]
            if node.get("resourceRestriction") is not None:
                return None, ""
            st_ts = AdStripperHLSServer._parse_iso_utc_ts(st.get("createdAt"))
            vd_ts = AdStripperHLSServer._parse_iso_utc_ts(node.get("createdAt"))
            if st_ts and vd_ts and abs(vd_ts - st_ts) > 900:
                return None, ""
            vod_info = {
                "id": node["id"],
                "broadcast_type": node.get("broadcastType") or "ARCHIVE",
                "seek_previews_url": node.get("seekPreviewsURL") or "",
            }
            quals, _ = self.get_vod_qualities(vod_info)
            if not quals:
                return None, ""
            chosen_url = ""
            pq = (preferred_quality or "").lower()
            for qk, qu in quals.items():
                if pq and (pq in qk.lower() or qk.lower() in pq) and "audio" not in qk.lower():
                    chosen_url = qu
                    break
            if not chosen_url:
                for qk, qu in quals.items():
                    if "audio" not in qk.lower():
                        chosen_url = qu
                        break
            if not chosen_url:
                chosen_url = next(iter(quals.values()), "")
            return chosen_url or None, (node.get("createdAt") or "")
        except Exception:
            return None, ""

    def get_vod_qualities(self, vod_info):
        vod_id = str(vod_info["id"])
        try:
            query = {
                "operationName": "PlaybackAccessToken",
                "variables": {
                    "isLive": False,
                    "login": "",
                    "isVod": True,
                    "vodID": vod_id,
                    "playerType": "site"
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "0828119ded1c13477966434e15800ff57ddacf13ba1911c129dc2200705b0712"
                    }
                }
            }
            data = self.gql_post(query, use_auth=bool(self.oauth_token))
            token_data = (data.get("data") or {}).get("videoPlaybackAccessToken")
            if token_data:
                params = {
                    "nauth": token_data["value"],
                    "nauthsig": token_data["signature"],
                    "allow_source": "true",
                    "allow_audio_only": "true",
                    "p": str(random.randint(100000, 999999))
                }
                usher_url = f"https://usher.ttvnw.net/vod/{vod_id}.m3u8?{urllib.parse.urlencode(params)}"
                r = self.session.get(usher_url, timeout=6)
                if r.status_code == 200 and "#EXTM3U" in r.text:
                    quals = self.parse_m3u8_variants(r.text)
                    if quals:
                        return quals, "VOD Standard"
        except Exception:
            pass

        seek_url = vod_info.get("seek_previews_url")
        b_type = vod_info.get("broadcast_type", "ARCHIVE")
        if not seek_url:
            q_vod = {"query": f'query {{ video(id: "{vod_id}") {{ seekPreviewsURL broadcastType }} }}'}
            vdata = (self.gql_post(q_vod, use_auth=False).get("data") or {}).get("video") or {}
            seek_url = vdata.get("seekPreviewsURL", "")
            b_type = vdata.get("broadcastType", "ARCHIVE")

        if not seek_url:
            raise RuntimeError("Impossibile estrarre seekPreviewsURL per questo VOD.")

        parsed = urllib.parse.urlparse(seek_url)
        domain = f"{parsed.scheme}://{parsed.netloc}"
        path_parts = [p for p in parsed.path.split("/") if p]
        if not path_parts:
            raise RuntimeError("Formato seekPreviewsURL non valido.")

        base_cf_url = f"{domain}/{path_parts[0]}"
        candidate_qualities = [
            ("1080p60 (Source)", "chunked"),
            ("720p60", "720p60"),
            ("720p30", "720p30"),
            ("480p30", "480p30"),
            ("360p30", "360p30"),
            ("160p30", "160p30"),
            ("Audio Only", "audio_only")
        ]

        def check_q(item):
            label, folder = item
            url = f"{base_cf_url}/{folder}/highlight-{vod_id}.m3u8" if b_type == "HIGHLIGHT" else f"{base_cf_url}/{folder}/index-dvr.m3u8"
            try:
                if self.session.head(url, timeout=4).status_code == 200:
                    return label, url
            except Exception:
                pass
            return None

        found_qualities = {}
        with ThreadPoolExecutor(max_workers=7) as ex:
            for res in ex.map(check_q, candidate_qualities):
                if res:
                    found_qualities[res[0]] = res[1]

        if not found_qualities:
            raise RuntimeError("VOD non trovato sui server CloudFront.")
        return found_qualities, "🔓 Sub-Only Unlocked (CloudFront)"

    def get_channels_status(self, logins):
        if not logins:
            return []
        clean_logins = [l.strip().lower() for l in logins if l.strip()]
        if not clean_logins:
            return []
        query = {
            "query": """
            query GetUsersStatus($logins: [String!]) {
              users(logins: $logins) {
                id
                login
                displayName
                profileImageURL(width: 70)
                videos(first: 1, type: ARCHIVE) {
                  edges {
                    node { id game { name } }
                  }
                }
                stream {
                  id
                  title
                  viewersCount
                  game { name }
                  freeformTags { name }
                }
              }
            }
            """,
            "variables": {"logins": clean_logins[:50]}
        }
        data = self.gql_post(query, use_auth=False)
        users = (data.get("data") or {}).get("users") or []
        found_map = {}
        for u in users:
            if not u:
                continue
            st = u.get("stream")
            found_map[u["login"].lower()] = self._node_to_channel_card(u)

        results = [
            found_map.get(l, {"login": l, "display_name": l, "avatar_url": "", "has_vods": False, "is_live": False, "viewers": 0, "game": "", "title": "", "tags": []})
            for l in clean_logins
        ]
        results.sort(key=lambda x: (not x["is_live"], -x["viewers"], x["login"]))
        return results

    def get_followed_channels(self):
        if not self.oauth_token:
            return None, []

        val_login, val_cid, _ = self.validate_oauth_token(self.oauth_token)
        if val_cid:
            self.auth_client_id = val_cid

        query = {
            "query": """
            query GetFollowedUsers {
              currentUser {
                id
                login
                displayName
                followedLiveUsers(first: 50) {
                  edges {
                    node {
                      login
                      displayName
                      profileImageURL(width: 70)
                      videos(first: 1, type: ARCHIVE) {
                        edges {
                          node { id game { name } }
                        }
                      }
                      stream {
                        title
                        viewersCount
                        game { name }
                        freeformTags { name }
                      }
                    }
                  }
                }
                follows(first: 100) {
                  edges {
                    node {
                      login
                      displayName
                      profileImageURL(width: 70)
                      videos(first: 1, type: ARCHIVE) {
                        edges {
                          node { id game { name } }
                        }
                      }
                      stream {
                        title
                        viewersCount
                        game { name }
                        freeformTags { name }
                      }
                    }
                  }
                }
              }
            }
            """
        }

        curr = None
        for cid in [self.auth_client_id, TV_CLIENT_ID, ANDROID_CLIENT_ID, GQL_CLIENT_ID]:
            if not cid:
                continue
            try:
                data = self.gql_post(query, use_auth=True, custom_client_id=cid)
                curr = (data.get("data") or {}).get("currentUser")
                if curr:
                    self.auth_client_id = cid
                    break
            except Exception:
                continue

        if not curr:
            return val_login, []

        channels_map = {}
        for edge in (curr.get("followedLiveUsers") or {}).get("edges", []):
            node = edge.get("node")
            if node and node.get("login"):
                st = node.get("stream") or {}
                channels_map[node["login"].lower()] = self._node_to_channel_card(node, force_live=True)

        for edge in (curr.get("follows") or {}).get("edges", []):
            node = edge.get("node")
            if node and node.get("login"):
                lg = node["login"].lower()
                if lg not in channels_map:
                    st = node.get("stream")
                    channels_map[lg] = self._node_to_channel_card(node)

        res = list(channels_map.values())
        res.sort(key=lambda x: (not x["is_live"], -x["viewers"], x["login"]))
        return curr.get("displayName") or curr.get("login") or val_login, res


# =====================================================================
# CHAT IRC NATIVA COMPLETA (PRIVMSG + USERNOTICE: Sub, Raid, Gift, Badges)
# =====================================================================
class TwitchIRCChat:
    def __init__(self, msg_queue, on_raid_cb=None):
        self.msg_queue = msg_queue
        self.on_raid_cb = on_raid_cb
        self.sock = None
        self.running = False
        self._conn_id = 0
        self.current_channel = None
        self.username = f"justinfan{random.randint(10000, 99999)}"
        self.oauth_token = None

    def _enqueue(self, user, msg, color, emotes_tag="", badges_tag=""):
        try:
            self.msg_queue.put_nowait((user, msg, color, emotes_tag, badges_tag))
        except Exception:
            pass

    def connect_channel(self, channel, username=None, oauth_token=None):
        self.disconnect()
        self._conn_id += 1
        cid = self._conn_id
        self.current_channel = channel.strip().lower()
        self.oauth_token = oauth_token
        self.username = username.lower() if (username and oauth_token) else f"justinfan{random.randint(10000, 99999)}"
        self.running = True
        threading.Thread(target=lambda: self._run(cid), daemon=True).start()

    def disconnect(self):
        self.running = False
        self._conn_id += 1
        old_sock = self.sock
        self.sock = None
        if old_sock:
            threading.Thread(target=lambda s=old_sock: s.close() if s else None, daemon=True).start()

    def send_chat_message(self, text):
        if not self.sock or not self.current_channel:
            return False
        if self.username.startswith("justinfan") or not self.oauth_token:
            self._enqueue("Twixy", "Effettua il Login per inviare messaggi in chat.", C_LIVE)
            return False
        try:
            self.sock.sendall(f"PRIVMSG #{self.current_channel} :{text}\r\n".encode("utf-8"))
            self._enqueue(self.username, text, C_ACCENT)
            return True
        except Exception as e:
            self._enqueue("Twixy", f"Errore invio: {e}", C_LIVE)
            return False

    def _run(self, cid=0):
        local_sock = None
        try:
            ctx = ssl.create_default_context()
            raw_sock = socket.create_connection(("irc.chat.twitch.tv", 6697), timeout=10)
            if not self.running or cid != self._conn_id:
                raw_sock.close()
                return
            local_sock = ctx.wrap_socket(raw_sock, server_hostname="irc.chat.twitch.tv")
            local_sock.settimeout(1.0)
            self.sock = local_sock

            local_sock.sendall(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
            if self.oauth_token and not self.username.startswith("justinfan"):
                clean_tok = self.oauth_token.replace("oauth:", "").strip()
                local_sock.sendall(f"PASS oauth:{clean_tok}\r\n".encode("utf-8"))
            else:
                local_sock.sendall(b"PASS SCHMOOPIIE\r\n")
            local_sock.sendall(f"NICK {self.username}\r\n".encode("utf-8"))
            local_sock.sendall(f"JOIN #{self.current_channel}\r\n".encode("utf-8"))

            self._enqueue("Twixy", f"Connesso alla chat live di #{self.current_channel}", C_GREEN)

            buffer = ""
            while self.running and cid == self._conn_id:
                try:
                    data = local_sock.recv(4096)
                    if not data:
                        break
                    buffer += data.decode("utf-8", errors="ignore")
                    while "\r\n" in buffer:
                        line, buffer = buffer.split("\r\n", 1)
                        self._handle_line(line)
                except socket.timeout:
                    continue
                except Exception:
                    break
        except Exception as e:
            if self.running and cid == self._conn_id:
                self._enqueue("Twixy", f"Chat disconnessa ({e})", C_LIVE)
        finally:
            if local_sock:
                try:
                    local_sock.close()
                except Exception:
                    pass

    @staticmethod
    def _format_badges(badges_str):
        if not badges_str:
            return ""
        icons = []
        for b in badges_str.split(","):
            b_name = b.split("/")[0]
            if b_name == "broadcaster":
                icons.append("👑")
            elif b_name == "moderator":
                icons.append("⚔️")
            elif b_name == "vip":
                icons.append("💎")
            elif b_name in ("subscriber", "founder"):
                icons.append("⭐")
            elif b_name == "premium":
                icons.append("👑")
        return ("".join(icons) + " ") if icons else ""

    def _handle_line(self, line):
        if line.startswith("PING"):
            try:
                self.sock.sendall(b"PONG :tmi.twitch.tv\r\n")
            except Exception:
                pass
            return

        tags = {}
        rest = line
        if line.startswith("@"):
            parts = line.split(" ", 1)
            if len(parts) == 2:
                tags_part, rest = parts
                for tag in tags_part[1:].split(";"):
                    if "=" in tag:
                        k, v = tag.split("=", 1)
                        tags[k] = v

        # 1. Eventi Speciali in Chat: USERNOTICE (Sub, Resub, Subgift, Raid, Announcement)
        if "USERNOTICE" in rest:
            sys_msg = tags.get("system-msg", "").replace("\\s", " ").strip()
            msg_id = tags.get("msg-id", "evento")
            user_comment = ""
            if " :" in rest:
                user_comment = rest.split(" :", 1)[1].strip()

            if "raid" in msg_id and self.on_raid_cb:
                try:
                    raider = tags.get("msg-param-displayName") or tags.get("msg-param-login") or tags.get("display-name") or tags.get("login") or "Streamer"
                    try:
                        viewers_cnt = int(tags.get("msg-param-viewerCount") or 0)
                    except Exception:
                        viewers_cnt = 0
                    self.on_raid_cb({
                        "channel": self.current_channel or "",
                        "raider": raider,
                        "raider_login": (tags.get("msg-param-login") or raider).lower(),
                        "viewers": viewers_cnt,
                        "message": sys_msg or f"{raider} ha fatto un raid!",
                        "time": time.strftime("%H:%M"),
                    })
                except Exception:
                    pass

            if sys_msg:
                icon = "[EVENTO]"
                if "raid" in msg_id:
                    icon = "RAID"
                elif "sub" in msg_id:
                    icon = "SUB"
                elif "announcement" in msg_id:
                    icon = "ANNUNCIO"
                full_notice = f"{sys_msg}" + (f" — \"{user_comment}\"" if user_comment else "")
                self._enqueue(icon, full_notice, C_GOLD)
            return

        # 2. Messaggi Standard + Bits + Riscatti Punti Canale
        if "PRIVMSG" in rest:
            color = tags.get("color") or "#a78bfa"
            display_name = tags.get("display-name") or ""
            badges_tag = tags.get("badges", "")
            bits = tags.get("bits")
            custom_reward_id = tags.get("custom-reward-id")

            try:
                prefix, msg_part = rest.split(" PRIVMSG ", 1)
                if not display_name:
                    display_name = prefix.split("!")[0].lstrip(":")
                msg = msg_part.split(" :", 1)[1]

                emotes_tag = tags.get("emotes", "")
                if bits:
                    self._enqueue(f"💎 {display_name} ({bits} Bits)", msg, C_CYAN, emotes_tag, badges_tag)
                elif custom_reward_id:
                    self._enqueue(f"🪙 {display_name} [Ricompensa]", msg, C_GOLD, emotes_tag, badges_tag)
                else:
                    self._enqueue(display_name, msg, color, emotes_tag, badges_tag)
            except Exception:
                pass


# =====================================================================
# INTERFACCIA GRAFICA — TWIXY
# =====================================================================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def _install_scrollbar_reentrancy_guard():
    """Evita loop/freeze ricorsivi di CTkScrollbar.set -> _draw -> update_idletasks."""
    cls = ctk.CTkScrollbar
    if getattr(cls, "_twixy_guard", False):
        return
    _orig_set = cls.set

    def _safe_scrollbar_set(self, start_value, end_value):
        try:
            sf, ef = float(start_value), float(end_value)
        except Exception:
            sf, ef = start_value, end_value

        last = getattr(self, "_twixy_last_vals", None)
        if last is not None and isinstance(sf, float) and isinstance(ef, float):
            if abs(sf - last[0]) < 1e-4 and abs(ef - last[1]) < 1e-4:
                return

        if getattr(self, "_twixy_in_set", False):
            self._twixy_pending = (start_value, end_value)
            return

        self._twixy_in_set = True
        try:
            self._twixy_pending = None
            if isinstance(sf, float) and isinstance(ef, float):
                self._twixy_last_vals = (sf, ef)
            _orig_set(self, start_value, end_value)
            pend = getattr(self, "_twixy_pending", None)
            if pend and not getattr(self, "_twixy_flush_id", None):
                def _flush_pending():
                    self._twixy_flush_id = None
                    p = getattr(self, "_twixy_pending", None)
                    self._twixy_pending = None
                    if p:
                        try:
                            if self.winfo_exists():
                                _safe_scrollbar_set(self, p[0], p[1])
                        except Exception:
                            pass
                try:
                    self._twixy_flush_id = self.after(35, _flush_pending)
                except Exception:
                    pass
        finally:
            self._twixy_in_set = False

    cls.set = _safe_scrollbar_set
    cls._twixy_guard = True


_install_scrollbar_reentrancy_guard()


class TwixyDesktopApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Twixy")
        self.geometry("1460x860")
        self.minsize(1020, 620)
        self.configure(fg_color=C_BG_ROOT)
        self.attributes("-topmost", False)

        apply_windows_enterprise_integration(self)
        self._load_app_icon()

        self.config_data = self.load_config()
        self._deactivate_windows_window_header_manipulation = True
        init_theme = "Light" if str(self.config_data.get("theme", "Dark")).lower().startswith("l") else "Dark"
        ctk.set_appearance_mode(init_theme)
        _set_win_titlebar_theme(self, init_theme)
        self._settings_dlg = None
        self._drops_dlg = None
        self._notif_dlg = None
        self._points_dlg = None
        self._login_dlg = None
        self._account_menu_win = None
        self._chat_tag_raw_colors = {}
        self._tracked_seg_bars = []
        self.engine = TwixyEngine(
            oauth_token=self.config_data.get("oauth_token", ""),
            auth_client_id=self.config_data.get("auth_client_id", GQL_CLIENT_ID),
            user_id=self.config_data.get("user_id", "")
        )

        self.chat_queue = queue.Queue(maxsize=500)
        self.chat_line_count = 0
        self.chat = TwitchIRCChat(
            self.chat_queue,
            on_raid_cb=lambda ev: self._safe_ui(lambda e=ev: self._record_raid_event(e)),
        )

        # Stato Player, Finestra, Drops & Punti Canale
        self.current_channel = ""
        self.current_stream_info = {}
        self.current_live_context = {}
        self.current_drops_list = []
        self.current_qualities = {}
        self.current_backup_qualities = {}
        self.is_playing_vod = False
        self.current_vod_duration_sec = 0
        self.is_fullscreen = False
        self.is_theater = False
        self.is_pip = False
        self.video_aspect_ratio = 16.0 / 9.0
        self.saved_normal_geometry = "1460x860"
        self.chat_visible = True
        self.seeking_drag = False
        self.is_paused = False
        self.sidebar_locked = False
        self.app_running = True

        # Telemetria VLC/MPV e Controllo Concorrenza Switch Stream
        self._bg_curr_ms = 0
        self._bg_total_ms = 0
        self._bg_is_playing = False
        self._stream_request_id = 0
        self._playback_lock = threading.Lock()

        # Notifiche Twitch + Log Eventi Sessione + Aggiornamento Real-Time Drops
        self.local_notifications = []
        self.session_raids = []
        self.unread_notif_count = 0
        self.remote_unseen_notif = 0
        self._account_bubble = None
        self._account_bubble_open = False
        self._account_bubble_shadow_imgs = []
        self._drops_dialog_open = False
        self._drops_realtime_cb = None
        self._last_heartbeat_ts = 0.0

        # Modalità Multi-Live in Griglia (fino a 4 live simultanee)
        self.is_multiview = False
        self.multi_tiles = []
        self.multi_focused_idx = 0
        self.multi_chat_idx = 0
        self.multi_solo_audio_var = tk.BooleanVar(value=True)
        self._multi_slot_seq = 0
        self._mv_controls_hidden = False
        self._vol_save_after_id = None

        # Gestione Drag & Resize PiP Frameless
        self._pip_drag_mode = None
        self._pip_start_mouse = (0, 0)
        self._pip_start_rect = (0, 0, 480, 270)
        self._was_lbutton_down = False
        self._pip_wheel_lock = threading.Lock()
        self._pip_wheel_delta = 0
        self._pip_wheel_capture_active = False
        self._pip_hook_active = False
        self._pip_hook_tid = None
        self._pip_hook_proc = None

        self._last_mouse_pos = (0, 0)
        self._last_mouse_move_ts = time.time()
        self.fs_hud_visible = False
        self.pip_hud_visible = False
        self.vod_hover_hud_visible = False
        self._thumb_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="twixy_thumb")
        self._thumb_pil_cache = {}
        self._thumb_cache_lock = threading.Lock()

        # Motore Emote Grafiche (Twitch Native, 7TV, BTTV, FFZ) & Badge Ufficiali
        self._empty_emote_px = None
        self._emote_picker_win = None
        self._pending_emote_seq = 0
        self._pending_emote_tags = []
        self.emote_mgr = EmoteAndBadgeManager(
            self,
            session=self.engine.session,
            client_id=GQL_CLIENT_ID,
            should_animate_cb=lambda: bool(
                getattr(self, "chat_visible", True)
                or (self._emote_picker_win is not None and self._emote_picker_win.winfo_exists())
            ),
        )

        # Motori Video
        self.vlc_instance = None
        self.vlc_player = None
        self.mpv_exe = None
        self.mpv_proc = None
        self.mpv_ipc_pipe = rf"\\.\pipe\twixy_mpv_{os.getpid()}"

        self._sort_mode = "viewers_desc"
        self._sidebar_visible_limit = 10
        self._sidebar_render_seq = 0

        self._inapp_menu_open = False
        self._inapp_active_tab = "Account"
        self._inapp_notif_subtab = "🔔 Tutte"
        self._inapp_drops_highlight = False
        self._inapp_vlc_pending = None
        self._inapp_tab_seq = 0
        self._clip_studio_open = False

        self._init_video_engines()
        self._build_ui_icons()
        self._build_enterprise_ui()
        self._build_fullscreen_hud()
        self._build_pip_hud()
        self._build_vod_hover_hud()
        self._bind_shortcuts()

        self.after(100, lambda: self.attributes("-topmost", False))

        # Worker in background: Telemetria Player + Heartbeat Drops/Punti Canale/Sondaggi
        threading.Thread(target=self._background_player_telemetry_worker, daemon=True).start()
        threading.Thread(target=self._background_drops_and_points_worker, daemon=True).start()

        self.after(250, self.refresh_all_lists)
        self.after(200, self._flush_chat_queue)
        self.after(500, self.update_playback_telemetry_ui)
        self.after(25, self._poll_mouse_and_pip_interaction)
        self._ui_call_queue = queue.Queue()
        self.after(40, self._drain_ui_call_queue)
        self.after(150, self._register_active_hwnd_file)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _safe_ui(self, fn):
        if self.app_running and fn is not None:
            try:
                self._ui_call_queue.put_nowait(fn)
            except Exception:
                pass

    def _drain_ui_call_queue(self):
        if not self.app_running:
            return
        for _ in range(32):
            try:
                fn = self._ui_call_queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                pass
        if self.app_running:
            self.after(40, self._drain_ui_call_queue)

    def _load_app_icon(self):
        self.logo_ctk_image = None
        if os.path.isfile(LOGO_PATH):
            try:
                self.iconbitmap(LOGO_PATH)
            except Exception:
                pass
        img_source = LOGO_PNG_PATH if os.path.isfile(LOGO_PNG_PATH) else LOGO_PATH
        if os.path.isfile(img_source):
            try:
                pil_img = Image.open(img_source)
                self.logo_ctk_image = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(28, 28))
            except Exception:
                pass

    def _init_video_engines(self):
        vlc_dir = find_vlc_directory(self.config_data.get("vlc_custom_dir"))
        if vlc_dir:
            inst = bind_vlc_runtime(vlc_dir)
            if inst:
                self.vlc_instance = inst
                self.vlc_player = self.vlc_instance.media_player_new()
                try:
                    saved_vol = max(0, min(100, int(self.config_data.get("volume", 80))))
                    self.vlc_player.audio_set_mute(False)
                    self.vlc_player.audio_set_volume(saved_vol)
                except Exception:
                    pass
                self.config_data["vlc_custom_dir"] = vlc_dir

        self.mpv_exe = find_mpv_executable(self.config_data.get("mpv_custom_dir"))
        self.save_config()

    def load_config(self):
        default_cfg = {
            "favorites": [],
            "cleaned_old_defaults": True,
            "oauth_token": "",
            "auth_client_id": GQL_CLIENT_ID,
            "user_id": "",
            "username": "",
            "player_engine": "VLC (LibVLC)",
            "stream_mode": "Proxy Luminous (1080p60 No-Ad)",
            "default_quality": "Auto (Migliore)",
            "theme": "Dark",
            "auto_claim_points": True,
            "auto_claim_drops": True,
            "mv_fs_autohide": True,
            "volume": 80,
            "vlc_custom_dir": "",
            "mpv_custom_dir": ""
        }
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if not loaded.get("cleaned_old_defaults"):
                        old_defaults = {"tumblurr", "pow3r", "therealmarzaa", "tenz"}
                        favs = loaded.get("favorites", [])
                        if set(f.lower() for f in favs).issubset(old_defaults):
                            loaded["favorites"] = []
                        loaded["cleaned_old_defaults"] = True
                    default_cfg.update(loaded)
            except Exception:
                pass
        try:
            default_cfg["volume"] = max(0, min(100, int(default_cfg.get("volume", 80))))
        except Exception:
            default_cfg["volume"] = 80
        return default_cfg

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=2)
        except Exception:
            pass

    def _schedule_volume_save(self):
        if getattr(self, "_vol_save_after_id", None):
            try:
                self.after_cancel(self._vol_save_after_id)
            except Exception:
                pass
        if self.app_running:
            self._vol_save_after_id = self.after(250, self._commit_volume_save)

    def _commit_volume_save(self):
        self._vol_save_after_id = None
        if self.app_running:
            self.save_config()

    def _style_segmented_tabs(self, seg):
        if seg is None:
            return
        try:
            if not seg.winfo_exists():
                return
            cur = seg.get()
            btns = getattr(seg, "_buttons_dict", {}) or {}
            for val, b in btns.items():
                if val == cur:
                    b.configure(text_color="#ffffff")
                else:
                    b.configure(text_color=C_TEXT_MAIN)
        except Exception:
            pass

    def _bind_tooltip(self, widget, text):
        tip_win = {"w": None}

        def _show(_e=None):
            try:
                if tip_win["w"] is not None or not widget.winfo_exists():
                    return
                tw = tk.Toplevel(self)
                tw.overrideredirect(True)
                tw.attributes("-topmost", True)
                tw.configure(bg=_tk_color(C_BORDER))
                lbl = tk.Label(
                    tw, text=text, bg=_tk_color(C_BG_CARD), fg=_tk_color(C_TEXT_MAIN),
                    font=("Segoe UI", 9, "bold"), padx=8, pady=3, bd=0
                )
                lbl.pack(padx=1, pady=1)
                x = widget.winfo_rootx() + (widget.winfo_width() // 2) - 45
                y = widget.winfo_rooty() - 28
                tw.geometry(f"+{max(4, x)}+{max(4, y)}")
                tip_win["w"] = tw
            except Exception:
                pass

        def _hide(_e=None):
            if tip_win["w"] is not None:
                try:
                    tip_win["w"].destroy()
                except Exception:
                    pass
                tip_win["w"] = None

        widget.bind("<Enter>", _show, add="+")
        widget.bind("<Leave>", _hide, add="+")
        widget.bind("<ButtonPress-1>", _hide, add="+")

    def _update_deck_toggle_styles(self):
        try:
            for btn_attr in ("deck_chat_btn", "deck_theater_btn"):
                btn = getattr(self, btn_attr, None)
                if btn is not None and btn.winfo_exists():
                    btn.configure(fg_color=C_BG_CARD, border_color=C_BORDER)
            if hasattr(self, "deck_pip_btn") and self.deck_pip_btn.winfo_exists():
                self.deck_pip_btn.configure(
                    fg_color=("#EDE9FE", "#2a1f47") if self.is_pip else C_BG_CARD,
                    border_color=C_ACCENT if self.is_pip else C_BORDER,
                )
        except Exception:
            pass

    def close_account_menu(self):
        self.close_inapp_menu()

    def _record_raid_event(self, ev):
        if not ev or not self.app_running:
            return
        self.session_raids.insert(0, ev)
        if len(self.session_raids) > 50:
            self.session_raids = self.session_raids[:50]
        self._push_local_notification("raid", ev.get("message") or "Raid rilevato", channel=ev.get("raider_login") or ev.get("channel") or "")
        if getattr(self, "_inapp_menu_open", False) and getattr(self, "_inapp_active_tab", "") == "Raid":
            self._switch_inapp_tab("Raid")

    def _is_widget_descendant(self, widget, ancestor):
        w = widget
        while w is not None:
            if w == ancestor:
                return True
            w = getattr(w, "master", None)
        return False

    def _on_root_click_bubble(self, event):
        if not getattr(self, "_account_bubble_open", False):
            return
        w = getattr(event, "widget", None)
        if self._account_bubble is not None and self._is_widget_descendant(w, self._account_bubble):
            return
        if hasattr(self, "account_pill"):
            acct_shell = getattr(getattr(self.account_pill, "master", None), "master", None) or self.account_pill
            if self._is_widget_descendant(w, acct_shell):
                return
        self._close_account_bubble()

    def _close_account_bubble(self):
        self._account_bubble_open = False
        b = getattr(self, "_account_bubble", None)
        self._account_bubble = None
        if b is not None:
            try:
                if b.winfo_exists():
                    b.destroy()
            except Exception:
                pass
        self._account_bubble_shadow_imgs = []
        if hasattr(self, "account_arrow_lbl") and self.account_arrow_lbl.winfo_exists():
            self.account_arrow_lbl.configure(
                image=self._icon_chev_up if getattr(self, "_inapp_menu_open", False) else self._icon_chev_down,
                text="",
            )

    def _toggle_account_bubble(self):
        if getattr(self, "_account_bubble_open", False):
            self._close_account_bubble()
        else:
            self._open_account_bubble()

    def _open_account_bubble(self):
        self._close_account_bubble()
        self.update_idletasks()
        is_logged = bool(self.config_data.get("oauth_token"))
        uname = (self.config_data.get("username") or "Connesso") if is_logged else "Modalita Ospite"
        total_unseen = int(self.unread_notif_count or 0) + int(self.remote_unseen_notif or 0)
        raid_cnt = len(getattr(self, "session_raids", []) or [])
        is_light = str(ctk.get_appearance_mode()).strip().lower() == "light"

        bw, bh = 272, 344
        pad = 12
        tip_h = 10
        cw, ch = bw + pad * 2, bh + pad * 2 + tip_h

        host_bg = _tk_color(C_BG_HEADER)
        bubble_cnv = tk.Canvas(
            self, width=cw, height=ch, bg=host_bg,
            highlightthickness=0, bd=0,
        )
        self._account_bubble = bubble_cnv

        # Rendering 2x Pillow nuvola con ombra morbida + freccia verso la pill Accedi
        s = 2
        im = Image.new("RGBA", (cw * s, ch * s), (0, 0, 0, 0))
        bx0, by0 = pad * s, (pad + tip_h) * s
        bx1, by1 = (cw - pad) * s, (ch - pad) * s
        rad = 16 * s
        tip_cx = (cw - pad - 34) * s

        sh_mask = Image.new("L", (cw * s, ch * s), 0)
        sd = ImageDraw.Draw(sh_mask)
        sd.rounded_rectangle((bx0, by0 + 4, bx1, by1 + 4), radius=rad, fill=255)
        sd.polygon([(tip_cx - 16, by0 + 6), (tip_cx, by0 - tip_h * s + 2), (tip_cx + 16, by0 + 6)], fill=255)
        sh_blur = sh_mask.filter(ImageFilter.GaussianBlur(radius=9.5))
        sh_alpha = sh_blur.point(lambda p: int(p * (0.28 if is_light else 0.56)))
        sh_rgba = Image.new("RGBA", (cw * s, ch * s), (15, 23, 42, 255) if is_light else (0, 0, 0, 255))
        sh_rgba.putalpha(sh_alpha)
        im = Image.alpha_composite(im, sh_rgba)

        fill_rgb = (255, 255, 255, 252) if is_light else (24, 24, 32, 252)
        bdr_rgb = (203, 213, 225, 255) if is_light else (58, 58, 78, 255)
        fg_im = Image.new("RGBA", (cw * s, ch * s), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fg_im)
        fd.rounded_rectangle((bx0, by0, bx1, by1), radius=rad, fill=fill_rgb, outline=bdr_rgb, width=2)
        fd.polygon([(tip_cx - 14, by0 + 2), (tip_cx, by0 - tip_h * s), (tip_cx + 14, by0 + 2)], fill=fill_rgb, outline=bdr_rgb)
        # Copri il bordo inferiore della punta con il fill della nuvola
        fd.line((tip_cx - 13, by0 + 1, tip_cx + 13, by0 + 1), fill=fill_rgb, width=4)
        im = Image.alpha_composite(im, fg_im)
        im_1x = im.resize((cw, ch), getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC))
        tk_photo = ImageTk.PhotoImage(im_1x)
        self._account_bubble_shadow_imgs.append(tk_photo)
        bubble_cnv.create_image(0, 0, anchor="nw", image=tk_photo)

        inner_bg = "#ffffff" if is_light else "#181820"
        body = ctk.CTkFrame(bubble_cnv, fg_color=inner_bg, corner_radius=12, width=bw - 14, height=bh - 14)
        body.pack_propagate(False)
        bubble_cnv.create_window(pad + 7, pad + tip_h + 7, anchor="nw", window=body, width=bw - 14, height=bh - 14)

        # Header profilo dentro la nuvola
        prof_row = ctk.CTkFrame(body, fg_color=C_BG_INPUT, corner_radius=10)
        prof_row.pack(fill="x", padx=6, pady=(6, 6))
        ctk.CTkLabel(
            prof_row, text="", image=self._icon_user_accent if not is_logged else self._icon_user,
            width=24,
        ).pack(side="left", padx=(10, 6), pady=8)
        ptxt = ctk.CTkFrame(prof_row, fg_color="transparent")
        ptxt.pack(side="left", fill="x", expand=True, pady=6)
        ctk.CTkLabel(
            ptxt, text=uname, font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=C_TEXT_MAIN, anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            ptxt,
            text="Connesso a Twitch" if is_logged else "Accedi per Drops e Chat",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=C_GREEN if is_logged else C_TEXT_DIM,
            anchor="w",
        ).pack(fill="x")

        def _open_tab_from_bubble(tab_k):
            self._close_account_bubble()
            self.open_inapp_menu(tab=tab_k)

        nav_items = [
            ("Account & Login" if not is_logged else "Profilo Account", "Account", self._icon_user_accent, None),
            ("Notifiche", "Notifiche", self._icon_bell, str(min(99, total_unseen)) if total_unseen > 0 else None),
            ("Twitch Drops", "Drop", self._icon_gift, None),
            ("Raid & Eventi", "Raid", self._icon_raid, str(raid_cnt) if raid_cnt > 0 else None),
            ("Impostazioni", "Impostazioni", self._icon_settings, None),
        ]
        for row_lbl, tab_key, ico_img, badge_txt in nav_items:
            row_fr = ctk.CTkFrame(body, fg_color="transparent", height=34, corner_radius=8)
            row_fr.pack(fill="x", padx=4, pady=1)
            row_fr.pack_propagate(False)
            btn = ctk.CTkButton(
                row_fr, text=f"  {row_lbl}", image=ico_img, compound="left", anchor="w",
                height=32, corner_radius=8,
                fg_color="transparent", hover_color=C_BG_CARD_HOVER,
                text_color=C_TEXT_MAIN, font=ctk.CTkFont("Segoe UI", 12, "bold"),
                command=lambda k=tab_key: _open_tab_from_bubble(k),
            )
            btn.pack(side="left", fill="both", expand=True)
            if badge_txt:
                ctk.CTkLabel(
                    row_fr, text=badge_txt, fg_color=C_ACCENT, text_color="#ffffff",
                    corner_radius=8, padx=7, height=18, font=ctk.CTkFont("Segoe UI", 10, "bold"),
                ).pack(side="right", padx=(0, 8))

        ctk.CTkFrame(body, fg_color=C_BORDER, height=1).pack(fill="x", padx=8, pady=(6, 6))

        foot = ctk.CTkFrame(body, fg_color="transparent")
        foot.pack(fill="x", padx=4, pady=(0, 6))
        next_theme = "Dark" if is_light else "Light"
        ctk.CTkButton(
            foot,
            text=" Scuro" if is_light else " Bianco",
            image=self._icon_moon if is_light else self._icon_sun,
            compound="left", height=30, corner_radius=8,
            fg_color=C_BG_INPUT, hover_color=C_BG_CARD_HOVER,
            text_color=C_TEXT_MAIN, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda m=next_theme: (self._close_account_bubble(), self.apply_theme(m)),
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))

        if is_logged:
            ctk.CTkButton(
                foot, text=" Esci", image=self._icon_logout, compound="left",
                height=30, width=82, corner_radius=8,
                fg_color=("#FEE2E2", "#3b1721"), hover_color=("#FECACA", "#591d2d"),
                text_color=("#dc2626", "#f87171"), font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda: (self._close_account_bubble(), self.logout_account()),
            ).pack(side="right")
        else:
            ctk.CTkButton(
                foot, text=" Accedi", image=self._icon_user_accent, compound="left",
                height=30, width=88, corner_radius=8,
                fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER,
                text_color="#ffffff", font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda: _open_tab_from_bubble("Account"),
            ).pack(side="right")

        try:
            px = self.account_pill.winfo_rootx() - self.winfo_rootx()
            pw = self.account_pill.winfo_width()
            py = (self.account_pill.winfo_rooty() - self.winfo_rooty()) + self.account_pill.winfo_height() - 4
            bx = max(12, min(self.winfo_width() - cw - 6, px + pw - (cw - pad - 34)))
            by = max(48, py)
        except Exception:
            bx = max(12, self.winfo_width() - cw - 8)
            by = 54

        self._account_bubble_open = True
        bubble_cnv.place(x=bx, y=by)
        bubble_cnv.lift()
        if hasattr(self, "account_arrow_lbl") and self.account_arrow_lbl.winfo_exists():
            self.account_arrow_lbl.configure(image=self._icon_chev_up, text="")

    def toggle_account_menu(self):
        self._toggle_account_bubble()

    def open_account_menu(self):
        self.open_inapp_menu(tab="Account")

    def logout_account(self):
        self.config_data.update({"oauth_token": "", "username": "", "user_id": "", "auth_client_id": GQL_CLIENT_ID})
        self.engine.oauth_token = ""
        self.engine.user_id = ""
        self.remote_unseen_notif = 0
        self.save_config()
        self._update_login_badge()
        self._update_notif_badge_ui()
        self.refresh_all_lists()
        self.chat._enqueue("Twixy", "Disconnesso dall'account Twitch.", C_GOLD)
        if getattr(self, "_inapp_menu_open", False) and self._inapp_active_tab == "Account":
            self._switch_inapp_tab("Account")

    def _build_inapp_menu_drawer(self):
        """Costruisce il menu unificato interno a Twixy (Account, Notifiche, Drop, Raid, Impostazioni) senza finestre extra."""
        self.inapp_drawer = ctk.CTkFrame(
            self.workspace, fg_color=C_BG_SIDEBAR, width=540, corner_radius=0,
            border_width=1, border_color=C_BORDER
        )
        self.inapp_drawer.pack_propagate(False)

        top_hdr = ctk.CTkFrame(self.inapp_drawer, fg_color=C_BG_HEADER, height=54, corner_radius=0, border_width=1, border_color=C_BORDER)
        top_hdr.pack(fill="x")
        top_hdr.pack_propagate(False)

        self._inapp_title_lbl = ctk.CTkLabel(
            top_hdr, text=" Menu Twixy", image=self._icon_user_accent, compound="left",
            font=ctk.CTkFont("Segoe UI", 15, "bold"), text_color=C_TEXT_MAIN
        )
        self._inapp_title_lbl.pack(side="left", padx=(14, 8))

        self._inapp_status_pill = ctk.CTkLabel(
            top_hdr, text="Ospite",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            fg_color=C_BG_CARD, text_color=C_TEXT_DIM, corner_radius=6, padx=8, height=22
        )
        self._inapp_status_pill.pack(side="left", padx=2)

        self._make_shadow_btn(
            top_hdr,
            pack_kw={"side": "right", "padx": (4, 12), "pady": 8},
            offset_x=2, offset_y=2,
            text=" Chiudi", image=self._icon_close, compound="left",
            width=78, height=30, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_LIVE, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.close_inapp_menu,
        )

        # Barra 5 sezioni principali del menu interno
        tab_strip = ctk.CTkFrame(self.inapp_drawer, fg_color=C_BG_HEADER, height=46, corner_radius=0)
        tab_strip.pack(fill="x")
        tab_strip.pack_propagate(False)

        self._inapp_tab_btns = {}
        tabs_row = ctk.CTkFrame(tab_strip, fg_color=C_BG_INPUT, corner_radius=10, height=36)
        tabs_row.pack(fill="x", padx=10, pady=5)
        tabs_row.pack_propagate(False)

        for key, label, ico in [
            ("Account", " Account", self._icon_user),
            ("Notifiche", " Notifiche", self._icon_bell),
            ("Drop", " Drop", self._icon_gift),
            ("Raid", " Raid", self._icon_raid),
            ("Impostazioni", " Opzioni", self._icon_settings),
        ]:
            btn = ctk.CTkButton(
                tabs_row, text=label, image=ico, compound="left", height=28, corner_radius=8,
                fg_color="transparent", hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda k=key: self._switch_inapp_tab(k),
            )
            btn.pack(side="left", fill="both", expand=True, padx=2, pady=3)
            self._inapp_tab_btns[key] = btn

        self._inapp_body = ctk.CTkFrame(self.inapp_drawer, fg_color="transparent", corner_radius=0)
        self._inapp_body.pack(fill="both", expand=True, padx=0, pady=0)

    def _refresh_inapp_tab_styles(self):
        cur = getattr(self, "_inapp_active_tab", "Account")
        is_logged = bool(self.config_data.get("oauth_token"))
        uname = (self.config_data.get("username") or "Connesso") if is_logged else "Modalità Ospite"
        total_unseen = int(self.unread_notif_count or 0) + int(self.remote_unseen_notif or 0)
        raid_cnt = len(getattr(self, "session_raids", []) or [])
        if hasattr(self, "_inapp_status_pill") and self._inapp_status_pill.winfo_exists():
            self._inapp_status_pill.configure(
                text=f"● {uname}" if is_logged else "Ospite",
                text_color=C_GREEN if is_logged else C_GOLD,
            )
        if hasattr(self, "_inapp_title_lbl") and self._inapp_title_lbl.winfo_exists():
            title_map = {
                "Account": (" Account & Accesso", self._icon_user_accent),
                "Notifiche": (" Centro Notifiche", self._icon_bell),
                "Drop": (" Twitch Drops", self._icon_gift),
                "Raid": (" Raid & Eventi Live", self._icon_raid),
                "Impostazioni": (" Impostazioni", self._icon_settings),
            }
            t_txt, t_ico = title_map.get(cur, (" Menu Twixy", self._icon_user_accent))
            self._inapp_title_lbl.configure(text=t_txt, image=t_ico)
        icon_idle = {
            "Account": self._icon_user,
            "Notifiche": self._icon_bell,
            "Drop": self._icon_gift,
            "Raid": self._icon_raid,
            "Impostazioni": self._icon_settings,
        }
        icon_sel = {
            "Account": self._icon_user,
            "Notifiche": self._icon_bell_white,
            "Drop": self._icon_gift_white,
            "Raid": self._icon_raid_white,
            "Impostazioni": self._icon_settings_white,
        }
        for key, btn in getattr(self, "_inapp_tab_btns", {}).items():
            if not btn.winfo_exists():
                continue
            lbl = {
                "Account": " Account",
                "Notifiche": f" Notifiche ({min(99, total_unseen)})" if total_unseen > 0 else " Notifiche",
                "Drop": " Drop",
                "Raid": f" Raid ({raid_cnt})" if raid_cnt > 0 else " Raid",
                "Impostazioni": " Opzioni",
            }[key]
            is_sel = (key == cur)
            btn.configure(
                text=lbl,
                image=icon_sel[key] if is_sel else icon_idle[key],
                fg_color=C_ACCENT if is_sel else "transparent",
                hover_color=C_ACCENT_HOVER if is_sel else C_BG_CARD_HOVER,
                text_color="#ffffff" if is_sel else C_TEXT_MAIN,
            )

    def open_inapp_menu(self, tab="Account", drops_highlight=False, notif_subtab=None, vlc_pending_url=None, vlc_pending_time=0):
        self._close_account_bubble()
        if self.is_pip:
            self.toggle_pip_mode()
        if notif_subtab:
            self._inapp_notif_subtab = notif_subtab
        if drops_highlight:
            self._inapp_drops_highlight = True
        if vlc_pending_url is not None:
            self._inapp_vlc_pending = (vlc_pending_url, int(vlc_pending_time or 0))
        if not getattr(self, "_inapp_menu_open", False):
            self._inapp_menu_open = True
            try:
                self.right_sidebar.pack_forget()
            except Exception:
                pass
            self.inapp_drawer.pack(side="right", fill="y", before=self.center_stage)
            if hasattr(self, "account_arrow_lbl"):
                self.account_arrow_lbl.configure(image=self._icon_chev_up, text="")
        self._switch_inapp_tab(tab)

    def close_inapp_menu(self, restore_chat=True):
        self._close_account_bubble()
        if not getattr(self, "_inapp_menu_open", False):
            return
        self._inapp_menu_open = False
        self._inapp_tab_seq += 1
        self._drops_dialog_open = False
        self._drops_realtime_cb = None
        try:
            self.inapp_drawer.pack_forget()
        except Exception:
            pass
        if hasattr(self, "account_arrow_lbl"):
            self.account_arrow_lbl.configure(image=self._icon_chev_down, text="")
        if restore_chat and getattr(self, "chat_visible", True) and not getattr(self, "is_pip", False):
            try:
                if not self.right_sidebar.winfo_manager():
                    self.right_sidebar.pack(side="right", fill="y", before=self.center_stage)
            except Exception:
                pass

    def _switch_inapp_tab(self, tab_name):
        self._inapp_active_tab = tab_name
        self._inapp_tab_seq += 1
        seq = self._inapp_tab_seq
        if tab_name != "Drop":
            self._drops_dialog_open = False
            self._drops_realtime_cb = None
        for child in self._inapp_body.winfo_children():
            child.destroy()
        self._refresh_inapp_tab_styles()
        if tab_name == "Account":
            self._render_inapp_account_tab(seq)
        elif tab_name == "Notifiche":
            self._render_inapp_notif_tab(seq)
        elif tab_name == "Drop":
            self._render_inapp_drops_tab(seq)
        elif tab_name == "Raid":
            self._render_inapp_raid_tab(seq)
        else:
            self._render_inapp_settings_tab(seq)

    def _render_inapp_account_tab(self, seq):
        sc = ctk.CTkScrollableFrame(self._inapp_body, fg_color="transparent")
        sc.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        is_logged = bool(self.config_data.get("oauth_token"))
        uname = (self.config_data.get("username") or "Connesso") if is_logged else "Modalità Ospite"

        # 1. Scheda profilo
        prof = ctk.CTkFrame(sc, fg_color=C_BG_CARD, corner_radius=12, border_width=1, border_color=C_BORDER)
        prof.pack(fill="x", padx=4, pady=(4, 8))
        pr = ctk.CTkFrame(prof, fg_color="transparent")
        pr.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(
            pr, text="", image=self._icon_user_accent if not is_logged else self._icon_user, width=26,
        ).pack(side="left", padx=(0, 10))
        ptxt = ctk.CTkFrame(pr, fg_color="transparent")
        ptxt.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(ptxt, text=uname, font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=C_TEXT_MAIN, anchor="w").pack(fill="x")
        ctk.CTkLabel(
            ptxt,
            text="Account Twitch connesso (Drops, Punti, Seguiti attivi)" if is_logged else "Accedi per sbloccare Drops, Punti Canale, Seguiti e Chat",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=C_GREEN if is_logged else C_TEXT_DIM,
            anchor="w",
        ).pack(fill="x")

        if is_logged:
            self._make_shadow_btn(
                prof,
                pack_kw={"fill": "x", "padx": 12, "pady": (0, 12)},
                offset_x=2, offset_y=3,
                text=" Disconnetti Account (Logout)", image=self._icon_logout, compound="left",
                height=34, corner_radius=9,
                fg_color=("#FEE2E2", "#3b1721"), hover_color=("#FECACA", "#591d2d"),
                border_width=1, border_color=C_LIVE,
                text_color=("#dc2626", "#f87171"),
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                command=self.logout_account,
            )

        # 2. Metodo 1: Device Flow twitch.tv/activate
        card1 = ctk.CTkFrame(sc, fg_color=C_BG_CARD, corner_radius=12, border_width=1, border_color=C_BORDER)
        card1.pack(fill="x", padx=4, pady=6)
        ctk.CTkLabel(card1, text="Connetti / Cambia Account Twitch", font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color=C_TEXT_MAIN).pack(anchor="w", padx=12, pady=(10, 2))
        code_lbl = ctk.CTkLabel(card1, text="Metodo 1: Attivazione rapida tramite codice (twitch.tv/activate)", font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_DIM, wraplength=410, justify="left")
        code_lbl.pack(anchor="w", padx=12, pady=(0, 6))

        code_box = ctk.CTkEntry(
            card1, placeholder_text="Il codice di 8 caratteri apparirà qui...",
            fg_color=C_BG_INPUT, text_color=C_TEXT_MAIN, justify="center",
            font=ctk.CTkFont("Consolas", 14, "bold"), height=34,
        )
        code_box.pack(fill="x", padx=14, pady=4)

        def start_device_flow_async():
            btn_gen.configure(state="disabled", text="⏳ Generazione codice in corso...")

            def worker():
                candidates = [(TV_CLIENT_ID, ""), (ANDROID_CLIENT_ID, ""), (GQL_CLIENT_ID, "")]
                ddata, used_cid = None, TV_CLIENT_ID
                for cid, scp in candidates:
                    try:
                        r = requests.post(
                            "https://id.twitch.tv/oauth2/device",
                            data={"client_id": cid, "scopes": scp},
                            headers={"User-Agent": USER_AGENT},
                            timeout=8,
                        )
                        if r.status_code == 200:
                            ddata = r.json()
                            used_cid = cid
                            break
                    except Exception:
                        pass

                if not ddata or "user_code" not in ddata:
                    self._safe_ui(lambda: (
                        code_lbl.configure(text="Errore di rete su id.twitch.tv. Usa il Metodo 2 sotto.", text_color=C_LIVE) if code_lbl.winfo_exists() else None,
                        btn_gen.configure(state="normal", text="🚀 Genera Codice e Apri twitch.tv/activate") if btn_gen.winfo_exists() else None,
                    ))
                    return

                ucode = ddata["user_code"]
                dcode = ddata["device_code"]
                v_uri = ddata.get("verification_uri", "https://www.twitch.tv/activate")

                def update_ui_with_code():
                    if seq != self._inapp_tab_seq or not code_box.winfo_exists():
                        return
                    code_box.delete(0, "end")
                    code_box.insert(0, ucode)
                    try:
                        self.clipboard_clear()
                        self.clipboard_append(ucode)
                    except Exception:
                        pass
                    code_lbl.configure(text=f"Codice {ucode} copiato! Incollalo nella pagina aperta:", text_color=C_GOLD)
                    btn_gen.configure(state="normal", text="🔄 Rigenera Codice")
                    webbrowser.open(v_uri)

                self._safe_ui(update_ui_with_code)

                for _ in range(45):
                    if seq != self._inapp_tab_seq or not self.app_running:
                        return
                    time.sleep(3)
                    try:
                        tr = requests.post(
                            "https://id.twitch.tv/oauth2/token",
                            data={
                                "client_id": used_cid,
                                "device_code": dcode,
                                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                            },
                            headers={"User-Agent": USER_AGENT},
                            timeout=8,
                        )
                        if tr.status_code == 200:
                            tok = tr.json().get("access_token")
                            if tok:
                                self._safe_ui(lambda t=tok, c=used_cid: self._complete_login(t, None, c))
                                return
                    except Exception:
                        pass

            threading.Thread(target=worker, daemon=True).start()

        btn_gen = self._make_shadow_btn(
            card1,
            pack_kw={"fill": "x", "padx": 14, "pady": (6, 12)},
            offset_x=2, offset_y=3,
            text=" Genera Codice e Apri twitch.tv/activate", image=self._icon_external, compound="left",
            height=34, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            command=start_device_flow_async,
        )

        # 3. Metodo 2: Token OAuth diretto
        card2 = ctk.CTkFrame(sc, fg_color=C_BG_CARD, corner_radius=12, border_width=1, border_color=C_BORDER)
        card2.pack(fill="x", padx=4, pady=6)
        ctk.CTkLabel(card2, text="Metodo 2: Token OAuth Diretto (cookie 'auth-token')", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_DIM).pack(anchor="w", padx=12, pady=(10, 4))
        tok_entry = ctk.CTkEntry(card2, placeholder_text="Incolla qui il tuo auth-token di 30 caratteri...", fg_color=C_BG_INPUT, show="*", height=32)
        tok_entry.pack(fill="x", padx=12, pady=4)
        if self.config_data.get("oauth_token"):
            tok_entry.insert(0, self.config_data["oauth_token"])

        self._make_shadow_btn(
            card2,
            pack_kw={"fill": "x", "padx": 12, "pady": (4, 12)},
            offset_x=2, offset_y=3,
            text=" Salva e Connetti Token", image=self._icon_check_white, compound="left",
            height=32, corner_radius=8,
            fg_color=C_GREEN, hover_color="#059669", text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self._complete_login(tok_entry.get().strip(), None),
        )

    def _render_inapp_notif_tab(self, seq):
        state = {
            "loaded": False,
            "notifs": [],
            "unlocked_drops": [],
            "error": "",
            "render_seq": 0,
            "visible_limit": 20,
            "pump_after": None,
        }
        self.unread_notif_count = 0
        self.remote_unseen_notif = 0
        self._update_notif_badge_ui()
        self._refresh_inapp_tab_styles()

        hdr = ctk.CTkFrame(self._inapp_body, fg_color=C_BG_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
        hdr.pack(fill="x", padx=12, pady=(10, 6))
        hdr_top = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_top.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(hdr_top, text=" Notifiche & Inventario Drop", image=self._icon_bell, compound="left", font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color=C_TEXT_MAIN).pack(side="left")

        refresh_btn = self._make_shadow_btn(
            hdr_top,
            pack_kw={"side": "right"},
            offset_x=2, offset_y=2,
            text=" Aggiorna", image=self._icon_refresh, compound="left", width=94, height=26, corner_radius=6,
            fg_color=C_BG_INPUT, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
        )

        tab_var = ctk.StringVar(value=getattr(self, "_inapp_notif_subtab", "🔔 Tutte"))
        tabs_bar = ctk.CTkSegmentedButton(
            self._inapp_body, values=["🔔 Tutte", "🎁 Drop Sbloccati", "🔴 Twitch", "⚡ Sessione Twixy"],
            variable=tab_var, height=32,
            fg_color=C_BG_INPUT, selected_color=C_ACCENT, selected_hover_color=C_ACCENT_HOVER,
            unselected_color=C_BG_INPUT, unselected_hover_color=C_BG_CARD_HOVER,
            text_color=C_TEXT_MAIN,
        )
        tabs_bar.pack(fill="x", padx=12, pady=(0, 6))
        self._tracked_seg_bars.append(tabs_bar)
        self._style_segmented_tabs(tabs_bar)

        scroll = ctk.CTkScrollableFrame(self._inapp_body, fg_color=C_BG_SIDEBAR)
        scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Font condivisi tra tutte le card (evita centinaia di allocazioni CTkFont dentro CTkScrollableFrame)
        f_emoji = ctk.CTkFont("Segoe UI", 20)
        f_title = ctk.CTkFont("Segoe UI", 11, "bold")
        f_norm = ctk.CTkFont("Segoe UI", 11)
        f_meta = ctk.CTkFont("Segoe UI", 10)
        f_btn = ctk.CTkFont("Segoe UI", 10, "bold")

        def _clip_txt(txt, max_len=280):
            s = str(txt or "").strip()
            return s if len(s) <= max_len else (s[:max_len - 1] + "…")

        def _attach_thumb(lbl, url):
            self._load_cached_thumb_async(lbl, url, size=(40, 40), circle=False, guard_win=scroll)

        def _make_card_shell(border_col):
            card = ctk.CTkFrame(scroll, fg_color=C_BG_CARD, corner_radius=8, border_width=1, border_color=border_col)
            card.pack(fill="x", padx=4, pady=4)
            c_hex = _tk_color(C_BG_CARD)
            row = tk.Frame(card, bg=c_hex, bd=0, highlightthickness=0)
            row._surface_fg_pair = C_BG_CARD
            row.pack(fill="x", padx=10, pady=8)
            th_box = tk.Frame(row, width=42, height=42, bg=c_hex, bd=0, highlightthickness=0)
            th_box._surface_fg_pair = C_BG_CARD
            th_box.pack_propagate(False)
            th_box.pack(side="left", padx=(0, 8))
            return row, th_box, c_hex

        def _render_single_entry(kind, payload):
            if kind == "local":
                ev = payload
                ev["unread"] = False
                row, th_box, c_hex = _make_card_shell(C_ACCENT)
                icon_txt = "🎁" if ev["kind"] == "drop_claimed" else ("🎲" if ev["kind"] == "emote_unlock" else "🪙")
                th = ctk.CTkLabel(th_box, text=icon_txt, width=40, height=40, font=f_emoji, fg_color="transparent", bg_color=C_BG_CARD)
                th.place(relx=0.5, rely=0.5, anchor="center")
                if ev.get("image_url"):
                    _attach_thumb(th, ev["image_url"])
                has_btn = bool(ev.get("channel"))
                if has_btn:
                    ctk.CTkButton(
                        row, text="▶", width=34, height=26, corner_radius=6,
                        fg_color=C_ACCENT, bg_color=C_BG_CARD, hover_color=C_ACCENT_HOVER, font=f_btn,
                        command=lambda ch=ev["channel"]: self.start_live_stream(ch),
                    ).pack(side="right", padx=(6, 0))
                txt_box = tk.Frame(row, bg=c_hex, bd=0, highlightthickness=0)
                txt_box._surface_fg_pair = C_BG_CARD
                txt_box.pack(side="left", fill="x", expand=True)
                ctk.CTkLabel(
                    txt_box, text=_clip_txt(ev["message"]), font=f_title, text_color=C_TEXT_MAIN,
                    fg_color="transparent", bg_color=C_BG_CARD, anchor="w",
                    wraplength=265 if has_btn else 305, justify="left",
                ).pack(fill="x")
                meta = f"Twixy Live • {ev['created_at']}" + (f" • #{ev['channel']}" if ev["channel"] else "")
                ctk.CTkLabel(
                    txt_box, text=meta, font=f_meta, text_color=C_TEXT_DIM,
                    fg_color="transparent", bg_color=C_BG_CARD, anchor="w",
                ).pack(fill="x")
            elif kind == "drop":
                gd = payload
                row, th_box, c_hex = _make_card_shell(C_GREEN)
                th = ctk.CTkLabel(th_box, text="🎁", width=40, height=40, font=f_emoji, fg_color="transparent", bg_color=C_BG_CARD)
                th.place(relx=0.5, rely=0.5, anchor="center")
                if gd.get("image_url"):
                    _attach_thumb(th, gd["image_url"])
                txt_box = tk.Frame(row, bg=c_hex, bd=0, highlightthickness=0)
                txt_box._surface_fg_pair = C_BG_CARD
                txt_box.pack(side="left", fill="x", expand=True)
                ctk.CTkLabel(
                    txt_box, text=_clip_txt(f"DROP: {gd['name']}"), font=f_title, text_color=C_GREEN,
                    fg_color="transparent", bg_color=C_BG_CARD, anchor="w", wraplength=305, justify="left",
                ).pack(fill="x")
                dt_str = (gd.get("awarded_at") or "")[:10]
                sub = f"🎮 {gd['game_name']}" + (f" • {dt_str}" if dt_str else "") + (f" • x{gd['total_count']}" if gd["total_count"] > 1 else "")
                ctk.CTkLabel(
                    txt_box, text=_clip_txt(sub, 140), font=f_meta, text_color=C_TEXT_DIM,
                    fg_color="transparent", bg_color=C_BG_CARD, anchor="w",
                ).pack(fill="x")
            elif kind == "twitch":
                nf = payload
                is_drop_nf = "drop" in nf["type"].lower() or "drop" in nf["body"].lower()
                row, th_box, c_hex = _make_card_shell(C_CYAN if is_drop_nf else (C_BORDER if nf["is_read"] else C_ACCENT))
                th = ctk.CTkLabel(th_box, text="🎁" if is_drop_nf else "🔔", width=40, height=40, font=f_emoji, fg_color="transparent", bg_color=C_BG_CARD)
                th.place(relx=0.5, rely=0.5, anchor="center")
                if nf.get("thumbnail_url"):
                    _attach_thumb(th, nf["thumbnail_url"])
                has_btn = bool(nf.get("channel_login") or nf.get("url"))
                if nf.get("channel_login"):
                    ctk.CTkButton(
                        row, text="▶", width=36, height=26, corner_radius=6,
                        fg_color=C_ACCENT, bg_color=C_BG_CARD, hover_color=C_ACCENT_HOVER, font=f_btn,
                        command=lambda ch=nf["channel_login"]: (self.add_channel_to_multiview(ch) if self.is_multiview else self.start_live_stream(ch)),
                    ).pack(side="right", padx=(6, 0))
                elif nf.get("url"):
                    ctk.CTkButton(
                        row, text="🌐", width=32, height=26, corner_radius=6,
                        fg_color=C_BG_INPUT, bg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, font=f_norm,
                        command=lambda u=nf["url"]: webbrowser.open(u),
                    ).pack(side="right", padx=(6, 0))
                txt_box = tk.Frame(row, bg=c_hex, bd=0, highlightthickness=0)
                txt_box._surface_fg_pair = C_BG_CARD
                txt_box.pack(side="left", fill="x", expand=True)
                body_txt = _clip_txt(nf["body"] or f"Notifica {nf['type']}")
                ctk.CTkLabel(
                    txt_box, text=body_txt, font=(f_title if not nf["is_read"] else f_norm), text_color=C_TEXT_MAIN,
                    fg_color="transparent", bg_color=C_BG_CARD, anchor="w",
                    wraplength=265 if has_btn else 305, justify="left",
                ).pack(fill="x")
                dt_short = nf["created_at"][:16].replace("T", " ") if nf["created_at"] else ""
                ctk.CTkLabel(
                    txt_box, text=dt_short, font=f_meta, text_color=C_TEXT_DIM,
                    fg_color="transparent", bg_color=C_BG_CARD, anchor="w",
                ).pack(fill="x")

        def _render():
            if seq != self._inapp_tab_seq or not scroll.winfo_exists():
                return
            state["render_seq"] += 1
            my_seq = state["render_seq"]
            aid = state.get("pump_after")
            if aid is not None:
                state["pump_after"] = None
                try:
                    self.after_cancel(aid)
                except Exception:
                    pass
            for w in scroll.winfo_children():
                w.destroy()
            if not state["loaded"]:
                ctk.CTkLabel(scroll, text="⏳ Scaricamento notifiche e Drop sbloccati...", font=ctk.CTkFont("Segoe UI", 12), text_color=C_GOLD).pack(pady=40)
                return

            sel = tab_var.get()
            self._inapp_notif_subtab = sel
            entries = []
            if sel in ("🔔 Tutte", "⚡ Sessione Twixy"):
                for ev in self.local_notifications:
                    entries.append(("local", ev))
            if sel in ("🔔 Tutte", "🎁 Drop Sbloccati"):
                for gd in state["unlocked_drops"]:
                    entries.append(("drop", gd))
            if sel in ("🔔 Tutte", "🔴 Twitch"):
                for nf in state["notifs"]:
                    entries.append(("twitch", nf))

            if not entries:
                empty_msg = state["error"] or (
                    "Nessuna notifica o Drop sbloccato trovato in questa sezione."
                    if self.engine.oauth_token
                    else "Effettua il Login nella scheda Account per vedere le notifiche e i Drop sbloccati."
                )
                ctk.CTkLabel(scroll, text=empty_msg, font=ctk.CTkFont("Segoe UI", 12), text_color=C_TEXT_DIM, justify="center", wraplength=340).pack(pady=40)
                return

            cap = max(20, int(state.get("visible_limit", 20)))
            visible_entries = entries[:cap]
            remaining = len(entries) - len(visible_entries)
            BATCH_SIZE = 5

            def _pump_batch(start_idx=0):
                state["pump_after"] = None
                if state["render_seq"] != my_seq or seq != self._inapp_tab_seq or not scroll.winfo_exists():
                    return
                end_idx = min(start_idx + BATCH_SIZE, len(visible_entries))
                for k, p in visible_entries[start_idx:end_idx]:
                    _render_single_entry(k, p)
                if end_idx < len(visible_entries):
                    state["pump_after"] = self.after(18, lambda idx=end_idx: _pump_batch(idx))
                elif remaining > 0:
                    def _load_more():
                        state["visible_limit"] += 20
                        _render()
                    ctk.CTkButton(
                        scroll, text=f"Mostra altri {min(20, remaining)} ({remaining} rimanenti)",
                        height=32, corner_radius=8, fg_color=C_BG_CARD, hover_color=C_ACCENT,
                        text_color=C_TEXT_MAIN, border_width=1, border_color=C_BORDER,
                        font=ctk.CTkFont("Segoe UI", 11, "bold"), command=_load_more,
                    ).pack(fill="x", padx=12, pady=10)

            _pump_batch(0)

        def _reload_notifs():
            state["loaded"] = False
            state["visible_limit"] = 20
            _render()

            def _w():
                res = self.engine.fetch_notifications(limit=35)
                state["notifs"] = res.get("notifications") or []
                state["unlocked_drops"] = res.get("unlocked_drops") or []
                state["error"] = res.get("error") or ""
                state["loaded"] = True
                self._safe_ui(_render)

            threading.Thread(target=_w, daemon=True).start()

        tabs_bar.configure(command=lambda _v: (state.update({"visible_limit": 20}), self._style_segmented_tabs(tabs_bar), _render()))
        refresh_btn.configure(command=_reload_notifs)
        _reload_notifs()

    def _render_inapp_drops_tab(self, seq):
        self._drops_dialog_open = True
        state_hl = {"enabled": bool(getattr(self, "_inapp_drops_highlight", False))}
        self._inapp_drops_highlight = False

        hdr = ctk.CTkFrame(self._inapp_body, fg_color=C_BG_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
        hdr.pack(fill="x", padx=12, pady=(10, 6))
        hdr_top = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_top.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(hdr_top, text=" Twitch Drops Center", image=self._icon_gift, compound="left", font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color=C_CYAN).pack(side="left")

        refresh_btn = self._make_shadow_btn(
            hdr_top,
            pack_kw={"side": "right", "padx": (4, 0)},
            offset_x=2, offset_y=2,
            text=" Aggiorna", image=self._icon_refresh, compound="left", width=90, height=26, corner_radius=6,
            fg_color=C_BG_INPUT, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
        )
        ctk.CTkButton(
            hdr_top, text=" Sbloccati", image=self._icon_bell, compound="left", width=94, height=26, corner_radius=6,
            fg_color=("#EDE9FE", "#2a1f47"), hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=lambda: self.open_inapp_menu(tab="Notifiche", notif_subtab="🎁 Drop Sbloccati"),
        ).pack(side="right")

        live_sync_lbl = ctk.CTkLabel(
            hdr, text="🟢 Sincronizzazione real-time attiva (15s + post-heartbeat).",
            font=ctk.CTkFont("Segoe UI", 10), text_color=C_GREEN, justify="left",
        )
        live_sync_lbl.pack(anchor="w", padx=10, pady=(0, 8))

        g_cur = (self.current_live_context.get("game_name") or (self.current_stream_info or {}).get("game") or "").strip().lower()
        has_personal_cur = bool(self.engine.oauth_token) and any(
            not d.get("claimed") and (d.get("is_current_game") or (g_cur and (d.get("game_name") or "").strip().lower() == g_cur))
            for d in (self.current_drops_list or [])
        )
        default_tab = "📊 I Miei Progressi" if (self.engine.oauth_token and (not state_hl["enabled"] or has_personal_cur)) else "🌍 Tutti i Drop Attivi"
        tab_var = ctk.StringVar(value=default_tab)
        tabs_bar = ctk.CTkSegmentedButton(
            self._inapp_body, values=["📊 I Miei Progressi", "🌍 Tutti i Drop Attivi"],
            variable=tab_var, height=32,
            fg_color=C_BG_INPUT, selected_color=C_ACCENT, selected_hover_color=C_ACCENT_HOVER,
            unselected_color=C_BG_INPUT, unselected_hover_color=C_BG_CARD_HOVER,
            text_color=C_TEXT_MAIN,
        )
        tabs_bar.pack(fill="x", padx=12, pady=(0, 6))
        self._tracked_seg_bars.append(tabs_bar)
        self._style_segmented_tabs(tabs_bar)

        filter_holder = ctk.CTkFrame(self._inapp_body, fg_color="transparent", height=0)
        filter_var = tk.StringVar()
        filter_entry = ctk.CTkEntry(
            filter_holder, textvariable=filter_var,
            placeholder_text="🔍 Filtra per gioco, campagna o premio...",
            fg_color=C_BG_INPUT, border_color=C_BORDER, height=30, font=ctk.CTkFont("Segoe UI", 11),
        )
        filter_entry.pack(fill="x")

        scroll = ctk.CTkScrollableFrame(self._inapp_body, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        state = {
            "loaded": False,
            "progress": list(self.current_drops_list or []),
            "active": [],
            "diag": "",
            "last_sync_ts": 0.0,
        }

        def _render_current_tab(*_):
            if seq != self._inapp_tab_seq or not scroll.winfo_exists():
                return
            for w in scroll.winfo_children():
                w.destroy()
            g_now = (self.current_live_context.get("game_name") or (self.current_stream_info or {}).get("game") or "").strip().lower()
            sel = tab_var.get()
            if sel == "📊 I Miei Progressi":
                filter_holder.pack_forget()
                if not self.engine.oauth_token:
                    ctk.CTkLabel(
                        scroll,
                        text="Effettua il Login nella scheda Account per tracciare i progressi.\nPuoi comunque sfogliare '🌍 Tutti i Drop Attivi' qui accanto!",
                        font=ctk.CTkFont("Segoe UI", 12), text_color=C_GOLD, justify="center", wraplength=380,
                    ).pack(pady=36)
                    return
                if not state["loaded"] and not state["progress"]:
                    ctk.CTkLabel(scroll, text="⏳ Sincronizzazione Drop in corso...", font=ctk.CTkFont("Segoe UI", 12), text_color=C_GOLD).pack(pady=40)
                    return
                drops_list = list(state["progress"])
                if not drops_list:
                    ctk.CTkLabel(
                        scroll,
                        text="Nessun Drop attualmente in progresso.\nApri '🌍 Tutti i Drop Attivi' per scoprire i giochi con Drop ora!",
                        font=ctk.CTkFont("Segoe UI", 12), text_color=C_TEXT_DIM, justify="center", wraplength=380,
                    ).pack(pady=40)
                    return

                def _drop_sort_key(d):
                    is_m = bool(d.get("is_current_game") or (g_now and (d.get("game_name") or "").strip().lower() == g_now))
                    pct_v = (d.get("current_min") or 0) * 100.0 / max(1, d.get("required_min") or 1)
                    return (not (is_m and not d.get("claimed")), bool(d.get("claimed")), -pct_v)

                drops_list.sort(key=_drop_sort_key)
                for d in drops_list:
                    is_match = bool(d.get("is_current_game") or (g_now and (d.get("game_name") or "").strip().lower() == g_now))
                    is_hl = is_match and not d.get("claimed")
                    card = ctk.CTkFrame(
                        scroll,
                        fg_color=("#EEF2FF", "#1e1b4b") if (is_hl and state_hl["enabled"]) else C_BG_CARD,
                        corner_radius=10,
                        border_width=2 if is_hl else 1,
                        border_color=C_ACCENT if is_hl else C_BORDER,
                    )
                    card.pack(fill="x", padx=4, pady=5)
                    if is_hl:
                        ctk.CTkLabel(card, text="⚡ IN COMPLETAMENTO SU QUESTA LIVE", fg_color=C_ACCENT, text_color="#ffffff", corner_radius=5, font=ctk.CTkFont("Segoe UI", 9, "bold"), padx=8, pady=1).pack(anchor="w", padx=10, pady=(8, 0))
                    top = ctk.CTkFrame(card, fg_color="transparent")
                    top.pack(fill="x", padx=10, pady=(6 if is_hl else 8, 2))
                    ctk.CTkLabel(top, text=f"🎮 {d['game_name']} — {d['reward_name']}", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_MAIN, wraplength=275, justify="left").pack(side="left")
                    req_m = max(1, d["required_min"])
                    cur_m = d["current_min"]
                    pct = min(100, int(round(cur_m * 100.0 / req_m)))
                    ctk.CTkLabel(
                        top, text="✔ RISCATTATO" if d["claimed"] else f"{cur_m}/{req_m}m ({pct}%)",
                        font=ctk.CTkFont("Consolas", 10, "bold"), text_color=C_GREEN if d["claimed"] else C_GOLD,
                    ).pack(side="right")
                    pbar = ctk.CTkProgressBar(card, height=9, corner_radius=5, fg_color=C_BG_INPUT, progress_color=C_GREEN if d["claimed"] else (C_ACCENT if is_hl else C_CYAN))
                    pbar.set(1.0 if d["claimed"] else (pct / 100.0))
                    pbar.pack(fill="x", padx=10, pady=(4, 8))
                    if not d["claimed"] and d["drop_instance_id"] and cur_m >= req_m:
                        ctk.CTkButton(
                            card, text="🎁 Riscatta Drop Ora", height=26, fg_color=C_GREEN, font=ctk.CTkFont("Segoe UI", 11, "bold"),
                            command=lambda inst_id=d["drop_instance_id"]: (self.engine.claim_drop_reward(inst_id), _reload_all()),
                        ).pack(fill="x", padx=10, pady=(0, 8))
            else:
                if not filter_holder.winfo_manager():
                    filter_holder.pack(fill="x", padx=12, pady=(0, 4), after=tabs_bar)
                if not state["loaded"]:
                    ctk.CTkLabel(scroll, text="⏳ Scaricamento campagne Drop attive da Twitch...", font=ctk.CTkFont("Segoe UI", 12), text_color=C_GOLD).pack(pady=40)
                    return
                q_flt = filter_var.get().strip().lower()
                camps = []
                for c in state["active"]:
                    if not q_flt:
                        camps.append(c)
                        continue
                    preview_txt = " ".join((p.get("name") or "") for p in (c.get("drops_preview") or []))
                    if q_flt in c["game_name"].lower() or q_flt in c["name"].lower() or q_flt in preview_txt.lower():
                        camps.append(c)
                camps.sort(key=lambda c: (not bool(c.get("is_current_game") or (g_now and c["game_name"].strip().lower() == g_now)), c.get("status") != "ACTIVE"))
                if not camps:
                    extra = f"\n\nDettaglio Twitch API: {state['diag']}" if state["diag"] else ""
                    ctk.CTkLabel(scroll, text=f"Nessuna campagna Drop attiva trovata{extra}", font=ctk.CTkFont("Segoe UI", 12), text_color=C_TEXT_DIM, justify="center", wraplength=380).pack(pady=36)
                    ctk.CTkButton(scroll, text="🌐 Apri Pagina Ufficiale Twitch Drops", height=32, fg_color=C_ACCENT, command=lambda: webbrowser.open("https://www.twitch.tv/drops/campaigns")).pack(pady=6)
                    return
                ctk.CTkLabel(scroll, text=f"Trovate {len(camps)} campagne Drop attive/in arrivo:", font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=C_TEXT_DIM, anchor="w").pack(fill="x", padx=6, pady=(2, 4))
                for camp in camps:
                    is_cur_camp = bool(camp.get("is_current_game") or (g_now and camp["game_name"].strip().lower() == g_now))
                    card = ctk.CTkFrame(
                        scroll,
                        fg_color=("#EEF2FF", "#1e1b4b") if (is_cur_camp and state_hl["enabled"]) else C_BG_CARD,
                        corner_radius=10,
                        border_width=2 if is_cur_camp else 1,
                        border_color=C_ACCENT if (is_cur_camp and state_hl["enabled"]) else (C_CYAN if is_cur_camp else C_BORDER),
                    )
                    card.pack(fill="x", padx=4, pady=4)
                    if is_cur_camp:
                        ctk.CTkLabel(card, text="⚡ ATTIVO SULLA LIVE CORRENTE", fg_color=C_ACCENT, text_color="#ffffff", corner_radius=5, font=ctk.CTkFont("Segoe UI", 9, "bold"), padx=8, pady=1).pack(anchor="w", padx=10, pady=(8, 0))
                    top = ctk.CTkFrame(card, fg_color="transparent")
                    top.pack(fill="x", padx=10, pady=(6 if is_cur_camp else 8, 2))
                    ctk.CTkLabel(top, text=f"🎮 {camp['game_name']}", font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=C_CYAN if is_cur_camp else C_TEXT_MAIN).pack(side="left")
                    st_txt = "ATTIVO" if camp["status"] == "ACTIVE" else "IN ARRIVO"
                    st_col = C_GREEN if camp["status"] == "ACTIVE" else C_GOLD
                    end_info = f" • {camp['end_at']}" if camp["end_at"] else ""
                    ctk.CTkLabel(top, text=f"{st_txt}{end_info}", font=ctk.CTkFont("Consolas", 10, "bold"), text_color=st_col).pack(side="right")
                    ctk.CTkLabel(card, text=camp["name"], font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_DIM, anchor="w", wraplength=390, justify="left").pack(fill="x", padx=10, pady=(0, 4))
                    preview_items = camp.get("drops_preview") or []
                    if preview_items:
                        prev_lines = "\n".join(f"• {it['name']} ({it['required_min']} min)" for it in preview_items[:5])
                        if len(preview_items) > 5:
                            prev_lines += f"\n… +{len(preview_items) - 5} altri premi"
                        ctk.CTkLabel(card, text=prev_lines, font=ctk.CTkFont("Segoe UI", 10), text_color=C_GOLD, anchor="w", justify="left", wraplength=390).pack(fill="x", padx=10, pady=(0, 6))
                    details_lbl = ctk.CTkLabel(card, text="", font=ctk.CTkFont("Segoe UI", 10), text_color=C_GOLD, anchor="w", justify="left", wraplength=390)
                    act = ctk.CTkFrame(card, fg_color="transparent")
                    act.pack(fill="x", padx=10, pady=(0, 8))
                    sample_ch = camp.get("sample_channel") or ""
                    if sample_ch:
                        def _watch_drop_ch(ch_login=sample_ch):
                            if self.is_multiview:
                                self.add_channel_to_multiview(ch_login)
                            else:
                                self.start_live_stream(ch_login)
                        ctk.CTkButton(act, text=f"▶ Guarda ({sample_ch[:12]})", height=26, corner_radius=6, fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, font=ctk.CTkFont("Segoe UI", 10, "bold"), command=_watch_drop_ch).pack(side="left", padx=(0, 6))
                    if not preview_items:
                        def _show_details(cid=camp["id"], lbl=details_lbl):
                            lbl.configure(text="⏳ Caricamento ricompense...")
                            lbl.pack(fill="x", padx=10, pady=(0, 6))
                            def _w():
                                items = self.engine.fetch_drop_campaign_details(cid, viewer_login=self.config_data.get("username") or "")
                                txt = "\n".join([f"• {it['name']} ({it['required_min']} min)" for it in items]) if items else "Apri i dettagli su Twitch."
                                self._safe_ui(lambda t=txt: lbl.configure(text=t) if (seq == self._inapp_tab_seq and lbl.winfo_exists()) else None)
                            threading.Thread(target=_w, daemon=True).start()
                        ctk.CTkButton(act, text="📋 Premi", width=76, height=26, corner_radius=6, fg_color=C_BG_INPUT, hover_color=C_ACCENT, font=ctk.CTkFont("Segoe UI", 10, "bold"), command=_show_details).pack(side="left", padx=(0, 6))
                    ctk.CTkButton(act, text="🌐 Twitch", width=76, height=26, corner_radius=6, fg_color=C_BG_INPUT, hover_color=C_BG_CARD_HOVER, font=ctk.CTkFont("Segoe UI", 10), command=lambda u=camp["details_url"]: webbrowser.open(u)).pack(side="left")

        def _reload_all():
            state["loaded"] = False
            _render_current_tab()
            def _worker():
                g_name = self.current_live_context.get("game_name") or self.current_stream_info.get("game", "")
                ch_id = self.current_live_context.get("channel_id") or ""
                extra_cids = [(t.get("live_ctx") or {}).get("channel_id") for t in (self.multi_tiles or []) if (t.get("live_ctx") or {}).get("channel_id")]
                prog_list = []
                if self.engine.oauth_token:
                    prog_list, _ = self.engine.fetch_drops_inventory_and_campaigns(g_name)
                    self.current_drops_list = prog_list
                act_list, diag = self.engine.fetch_all_active_drop_campaigns(g_name, channel_id=ch_id, extra_channel_ids=extra_cids)
                state["progress"] = prog_list
                state["active"] = act_list
                state["diag"] = diag
                state["loaded"] = True
                state["last_sync_ts"] = time.time()
                self._safe_ui(lambda: (self._update_drops_badge_ui(), _render_current_tab()))
            threading.Thread(target=_worker, daemon=True).start()

        def _on_realtime_push():
            if seq != self._inapp_tab_seq or not self._inapp_menu_open:
                return
            state["progress"] = list(self.current_drops_list or [])
            state["last_sync_ts"] = time.time()
            state["loaded"] = True
            if tab_var.get() == "📊 I Miei Progressi":
                _render_current_tab()

        def _tick_live_banner():
            if seq != self._inapp_tab_seq or not self._inapp_menu_open or not live_sync_lbl.winfo_exists():
                return
            ago = int(time.time() - state["last_sync_ts"]) if state["last_sync_ts"] else 0
            hb_ago = int(time.time() - self._last_heartbeat_ts) if self._last_heartbeat_ts else -1
            hb_txt = f" • Spade {max(0, 60 - hb_ago)}s" if (hb_ago >= 0 and (self.current_channel or self.multi_tiles)) else ""
            live_sync_lbl.configure(text=f"🟢 Real-time (sync {ago}s fa{hb_txt}) • Auto-claim 100%")
            self.after(1000, _tick_live_banner)

        self._drops_realtime_cb = _on_realtime_push
        tabs_bar.configure(command=lambda _v: (self._style_segmented_tabs(tabs_bar), _render_current_tab()))
        filter_var.trace_add("write", _render_current_tab)
        refresh_btn.configure(command=_reload_all)
        _reload_all()
        self.after(1000, _tick_live_banner)

    def _render_inapp_raid_tab(self, seq):
        hdr = ctk.CTkFrame(self._inapp_body, fg_color=C_BG_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
        hdr.pack(fill="x", padx=12, pady=(10, 6))
        hdr_top = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_top.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(
            hdr_top, text=" Raid & Eventi Live", image=self._icon_raid, compound="left",
            font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color=C_TEXT_MAIN,
        ).pack(side="left")

        def _clear_raids():
            self.session_raids.clear()
            self._switch_inapp_tab("Raid")

        if self.session_raids:
            self._make_shadow_btn(
                hdr_top, pack_kw={"side": "right"}, offset_x=2, offset_y=2,
                text=" Pulisci", image=self._icon_trash, compound="left", width=78, height=26, corner_radius=6,
                fg_color=C_BG_INPUT, hover_color=C_LIVE, text_color=C_TEXT_MAIN,
                border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=_clear_raids,
            )

        sc = ctk.CTkScrollableFrame(self._inapp_body, fg_color="transparent")
        sc.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Canale corrente + stato raid IRC
        cur_card = ctk.CTkFrame(sc, fg_color=C_BG_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
        cur_card.pack(fill="x", padx=4, pady=(4, 8))
        cur_ch = self.current_channel or ""
        ctk.CTkLabel(
            cur_card,
            text=f"Ascolto Raid su #{cur_ch}" if cur_ch else "Nessuna live attiva in ascolto",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color=C_GREEN if cur_ch else C_TEXT_DIM, anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            cur_card,
            text="I raid in arrivo o in uscita rilevati nella chat Twitch di sessione compaiono qui in tempo reale.",
            font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM, anchor="w", wraplength=440, justify="left",
        ).pack(fill="x", padx=12, pady=(0, 10))

        # Lista Raid catturati nella sessione
        ctk.CTkLabel(
            sc, text="RAID CATTURATI IN SESSIONE",
            font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=C_ACCENT, anchor="w",
        ).pack(fill="x", padx=8, pady=(2, 4))

        if not self.session_raids:
            ctk.CTkLabel(
                sc, text="Nessun raid registrato finora in questa sessione.",
                font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_DIM, justify="center",
            ).pack(pady=16)
        else:
            for rv in self.session_raids:
                card = ctk.CTkFrame(sc, fg_color=C_BG_CARD, corner_radius=9, border_width=1, border_color=C_GOLD)
                card.pack(fill="x", padx=4, pady=4)
                r = ctk.CTkFrame(card, fg_color="transparent")
                r.pack(fill="x", padx=10, pady=8)
                ctk.CTkLabel(r, text="", image=self._icon_raid, width=22).pack(side="left", padx=(0, 8))
                tb = ctk.CTkFrame(r, fg_color="transparent")
                tb.pack(side="left", fill="x", expand=True)
                ctk.CTkLabel(
                    tb, text=rv.get("message") or f"{rv.get('raider')} -> #{rv.get('channel')}",
                    font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_MAIN, anchor="w", wraplength=310, justify="left",
                ).pack(fill="x")
                v_cnt = int(rv.get("viewers") or 0)
                sub_meta = f"#{rv.get('channel') or '--'} • {rv.get('time') or ''}" + (f" • {v_cnt:,} spettatori".replace(",", ".") if v_cnt > 0 else "")
                ctk.CTkLabel(tb, text=sub_meta, font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM, anchor="w").pack(fill="x")
                target_login = rv.get("raider_login") or ""
                if target_login:
                    ctk.CTkButton(
                        r, text=" Apri", image=self._icon_play_white, compound="left", width=66, height=26, corner_radius=6,
                        fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
                        font=ctk.CTkFont("Segoe UI", 10, "bold"),
                        command=lambda ch=target_login: self.start_live_stream(ch),
                    ).pack(side="right", padx=(6, 0))

        # Streamer seguiti attualmente live (comodo per raid / passaggio veloce)
        live_cands = [c for c in (list(self.fav_data or []) + list(self.followed_data or [])) if c.get("is_live")]
        seen_logins = set()
        dedup_cands = []
        for c in live_cands:
            lg = (c.get("login") or "").lower()
            if lg and lg not in seen_logins:
                seen_logins.add(lg)
                dedup_cands.append(c)
        if dedup_cands:
            ctk.CTkLabel(
                sc, text="CANALI LIVE DISPONIBILI",
                font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=C_TEXT_DIM, anchor="w",
            ).pack(fill="x", padx=8, pady=(12, 4))
            for ch_item in dedup_cands[:10]:
                lg = ch_item["login"]
                c_card = ctk.CTkFrame(sc, fg_color=C_BG_CARD, corner_radius=8, border_width=1, border_color=C_BORDER)
                c_card.pack(fill="x", padx=4, pady=3)
                cr = ctk.CTkFrame(c_card, fg_color="transparent")
                cr.pack(fill="x", padx=10, pady=6)
                ctk.CTkLabel(
                    cr, text=f"{ch_item.get('display_name') or lg}  ({ch_item.get('viewers', 0):,} spett.)".replace(",", "."),
                    font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_MAIN, anchor="w",
                ).pack(side="left", fill="x", expand=True)
                ctk.CTkButton(
                    cr, text=" Guarda", image=self._icon_play_white, compound="left", width=74, height=26, corner_radius=6,
                    fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
                    font=ctk.CTkFont("Segoe UI", 10, "bold"),
                    command=lambda c_lg=lg, inf=ch_item: self.start_live_stream(c_lg, inf),
                ).pack(side="right", padx=(4, 0))
                ctk.CTkButton(
                    cr, text="", image=self._icon_plus, width=28, height=26, corner_radius=6,
                    fg_color=C_BG_INPUT, hover_color=C_BG_CARD_HOVER,
                    command=lambda c_lg=lg, inf=ch_item: self.add_channel_to_multiview(c_lg, inf),
                ).pack(side="right")

    def _render_inapp_settings_tab(self, seq):
        sc = ctk.CTkScrollableFrame(self._inapp_body, fg_color=C_BG_SIDEBAR)
        sc.pack(fill="both", expand=True, padx=10, pady=(8, 12))

        def _section(title, icon_img=None):
            card = ctk.CTkFrame(sc, fg_color=C_BG_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
            card.pack(fill="x", padx=4, pady=6)
            ctk.CTkLabel(
                card, text=f" {title}" if icon_img else title, image=icon_img, compound="left",
                font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=C_ACCENT, anchor="w",
            ).pack(fill="x", padx=12, pady=(10, 6))
            return card

        # 1. Aspetto & Tema
        sec_theme = _section("Aspetto & Tema", self._icon_sun)
        theme_row = ctk.CTkFrame(sec_theme, fg_color="transparent")
        theme_row.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkLabel(theme_row, text="Tema Interfaccia", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_MAIN).pack(side="left")
        curr_t = "☀️ Tema Bianco" if str(self.config_data.get("theme", "Dark")).lower() == "light" else "🌙 Tema Scuro"
        theme_var = ctk.StringVar(value=curr_t)
        theme_seg = ctk.CTkSegmentedButton(
            theme_row, values=["🌙 Tema Scuro", "☀️ Tema Bianco"],
            variable=theme_var, height=30,
            fg_color=C_BG_INPUT, selected_color=C_ACCENT, selected_hover_color=C_ACCENT_HOVER,
            unselected_color=C_BG_INPUT, unselected_hover_color=C_BG_CARD_HOVER,
            text_color=C_TEXT_MAIN,
            command=lambda choice: self.apply_theme("Light" if "Bianco" in choice else "Dark"),
        )
        theme_seg.pack(side="right")
        self._tracked_seg_bars.append(theme_seg)
        self._style_segmented_tabs(theme_seg)

        # 2. Video & Anti-Ad
        sec_vid = _section("🎬 Motore Video & Connessione Anti-Ad")
        r_eng = ctk.CTkFrame(sec_vid, fg_color="transparent")
        r_eng.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(r_eng, text="Motore Riproduzione", font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_MAIN).pack(side="left")
        ctk.CTkOptionMenu(
            r_eng, variable=self.engine_var, width=180, height=30, corner_radius=8,
            fg_color=C_BG_INPUT, button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER,
            text_color=C_TEXT_MAIN, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            values=["VLC (LibVLC)", "MPV (GPU Engine)"], command=self.on_engine_changed,
        ).pack(side="right")

        r_mode = ctk.CTkFrame(sec_vid, fg_color="transparent")
        r_mode.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(r_mode, text="Modalità Proxy/Ad", font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_MAIN).pack(side="left")
        ctk.CTkOptionMenu(
            r_mode, variable=self.mode_var, width=210, height=30, corner_radius=8,
            fg_color=C_BG_INPUT, button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER,
            text_color=C_TEXT_MAIN, font=ctk.CTkFont("Segoe UI", 10),
            values=["Proxy Luminous (1080p60 No-Ad)", "Xtra Direct Usher (Android)", "Xtra Direct (Embed No-Ad)"],
            command=lambda val: (self.config_data.update({"stream_mode": val}), self.save_config()),
        ).pack(side="right")

        r_qual = ctk.CTkFrame(sec_vid, fg_color="transparent")
        r_qual.pack(fill="x", padx=12, pady=(4, 12))
        ctk.CTkLabel(r_qual, text="Qualità Predefinita", font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_MAIN).pack(side="left")
        def_q_var = ctk.StringVar(value=self.config_data.get("default_quality", "Auto (Migliore)"))
        ctk.CTkOptionMenu(
            r_qual, variable=def_q_var, width=180, height=30, corner_radius=8,
            fg_color=C_BG_INPUT, button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER,
            text_color=C_TEXT_MAIN, font=ctk.CTkFont("Segoe UI", 11),
            values=["Auto (Migliore)", "1080p60", "720p60", "480p"],
            command=lambda val: (self.config_data.update({"default_quality": val}), self.save_config()),
        ).pack(side="right")

        # 3. Automazioni & Multi-Live
        sec_auto = _section("⚡ Automazioni & Multi-Live")
        pts_var = tk.BooleanVar(value=bool(self.config_data.get("auto_claim_points", True)))
        drops_var = tk.BooleanVar(value=bool(self.config_data.get("auto_claim_drops", True)))
        mv_hide_var = tk.BooleanVar(value=bool(self.config_data.get("mv_fs_autohide", True)))

        def _save_toggles():
            self.config_data["auto_claim_points"] = bool(pts_var.get())
            self.config_data["auto_claim_drops"] = bool(drops_var.get())
            self.config_data["mv_fs_autohide"] = bool(mv_hide_var.get())
            self.save_config()

        for lbl_txt, var in [
            ("Riscatta automaticamente bauli +50 Punti Canale", pts_var),
            ("Riscatta automaticamente Twitch Drops al 100%", drops_var),
            ("Nascondi controlli Multi-Live in Fullscreen dopo 2,5s", mv_hide_var),
        ]:
            ctk.CTkSwitch(
                sec_auto, text=lbl_txt, variable=var, onvalue=True, offvalue=False,
                progress_color=C_ACCENT, text_color=C_TEXT_MAIN, font=ctk.CTkFont("Segoe UI", 11),
                command=_save_toggles,
            ).pack(anchor="w", padx=12, pady=5)
        ctk.CTkFrame(sec_auto, fg_color="transparent", height=6).pack()

        # 4. Cache & Manutenzione + VLC Portable Inline
        sec_cache = _section("🧹 Cache & Motori Video")
        cache_info_lbl = ctk.CTkLabel(
            sec_cache,
            text=f"In RAM: {len(self.emote_mgr.photo_cache)} emote/badge • {self.engine.ad_stripper.ads_blocked_count} ad bloccati",
            font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM, anchor="w",
        )
        cache_info_lbl.pack(fill="x", padx=12, pady=(0, 6))

        btn_row = ctk.CTkFrame(sec_cache, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(2, 8))
        ctk.CTkButton(
            btn_row, text=" Svuota Emote", image=self._icon_trash, compound="left", height=30, corner_radius=8,
            fg_color=C_BG_INPUT, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self._clear_emote_cache(cache_info_lbl),
        ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(
            btn_row, text=" Svuota Ad-Stripper", image=self._icon_refresh, compound="left", height=30, corner_radius=8,
            fg_color=C_BG_INPUT, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self._clear_adstripper_cache(cache_info_lbl),
        ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        vlc_p = find_vlc_directory(self.config_data.get("vlc_custom_dir")) or "Non rilevato"
        mpv_p = find_mpv_executable(self.config_data.get("mpv_custom_dir")) or "Non rilevato"
        ffmpeg_p = find_ffmpeg_executable() or "Fallback interno attivo"
        ctk.CTkLabel(
            sec_cache,
            text=f"VLC: {vlc_p}\nMPV: {mpv_p}\nFFmpeg (Clip): {ffmpeg_p}",
            font=ctk.CTkFont("Consolas", 9), text_color=C_TEXT_DIM, justify="left", anchor="w", wraplength=410,
        ).pack(fill="x", padx=12, pady=(2, 6))

        vlc_prog_lbl = ctk.CTkLabel(
            sec_cache,
            text="Se necessario, scarica/ripara VLC 64-bit Portable direttamente qui dentro Twixy:",
            font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM, anchor="w", wraplength=410, justify="left",
        )
        vlc_prog_lbl.pack(fill="x", padx=12, pady=(0, 6))

        def _dl_vlc_inline():
            btn_vlc_dl.configure(state="disabled")
            pend = getattr(self, "_inapp_vlc_pending", None)
            self._inapp_vlc_pending = None

            def worker():
                zip_path = os.path.join(APP_DIR, "vlc_temp.zip")
                try:
                    os.makedirs(PORTABLE_VLC_DIR, exist_ok=True)
                    for url in VLC_PORTABLE_URLS:
                        try:
                            with requests.get(url, stream=True, timeout=15) as r:
                                if r.status_code != 200:
                                    continue
                                total = int(r.headers.get("content-length", 0))
                                dl = 0
                                with open(zip_path, "wb") as f:
                                    for chunk in r.iter_content(chunk_size=262144):
                                        if chunk:
                                            f.write(chunk)
                                            dl += len(chunk)
                                            if total > 0:
                                                pct = int(dl * 100 / total)
                                                self._safe_ui(lambda p=pct: vlc_prog_lbl.configure(text=f"⏳ Download VLC 64-bit: {p}%...", text_color=C_GOLD) if vlc_prog_lbl.winfo_exists() else None)
                            if os.path.isfile(zip_path) and os.path.getsize(zip_path) > 10_000_000:
                                break
                        except Exception:
                            continue
                    self._safe_ui(lambda: vlc_prog_lbl.configure(text="📦 Estrazione componenti VLC...", text_color=C_GOLD) if vlc_prog_lbl.winfo_exists() else None)
                    with zipfile.ZipFile(zip_path, "r") as zf:
                        zf.extractall(PORTABLE_VLC_DIR)
                    try:
                        os.remove(zip_path)
                    except Exception:
                        pass

                    def done():
                        self._init_video_engines()
                        if seq == self._inapp_tab_seq and vlc_prog_lbl.winfo_exists():
                            vlc_prog_lbl.configure(text="✔ VLC 64-bit Portable pronto e attivo!", text_color=C_GREEN)
                            btn_vlc_dl.configure(state="normal")
                        if pend and pend[0]:
                            self._play_url(pend[0], pend[1])

                    self._safe_ui(done)
                except Exception as e:
                    self._safe_ui(lambda err=str(e): (
                        vlc_prog_lbl.configure(text=f"Errore: {err}", text_color=C_LIVE) if vlc_prog_lbl.winfo_exists() else None,
                        btn_vlc_dl.configure(state="normal") if btn_vlc_dl.winfo_exists() else None,
                    ))

            threading.Thread(target=worker, daemon=True).start()

        btn_vlc_dl = ctk.CTkButton(
            sec_cache, text=" Scarica / Ripara VLC 64-bit Portable (1-Click)",
            image=self._icon_download, compound="left",
            height=30, corner_radius=8, fg_color=C_BG_INPUT, hover_color=C_ACCENT,
            text_color=C_TEXT_MAIN, font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=_dl_vlc_inline,
        )
        btn_vlc_dl.pack(fill="x", padx=12, pady=(0, 12))
        if getattr(self, "_inapp_vlc_pending", None):
            vlc_prog_lbl.configure(text="⚠ Motore video mancante: clicca il pulsante qui sotto per installarlo automaticamente.", text_color=C_GOLD)

    def _build_ui_icons(self):
        """Genera suite completa di icone vettoriali minimali (Lucide-style, 2x supersampling Light/Dark)."""
        _RS = Image.Resampling.LANCZOS

        def _vec(sz, light_col, dark_col, draw_fn):
            def _render(col):
                s = sz * 2
                im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                draw_fn(d, s, col)
                return im.resize((sz, sz), _RS)

            return ctk.CTkImage(light_image=_render(light_col), dark_image=_render(dark_col), size=(sz, sz))

        def _star_img(color_hex, filled=True, sz=18):
            s = sz * 2
            im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            cx, cy = s / 2.0, s / 2.0
            r_out, r_in = s * 0.43, s * 0.19
            pts = []
            for k in range(10):
                ang = -math.pi / 2.0 + k * (math.pi / 5.0)
                rr = r_out if k % 2 == 0 else r_in
                pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
            if filled:
                d.polygon(pts, fill=color_hex)
            else:
                d.polygon(pts, outline=color_hex, width=3)
            return im.resize((sz, sz), _RS)

        def _draw_dots(d, s, c):
            cx = s // 2
            for cy in (7, 16, 25):
                d.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=c)

        def _draw_game(d, s, c):
            d.rounded_rectangle((2, 7, s - 3, s - 6), radius=7, outline=c, width=3)
            d.line((7, 14, 13, 14), fill=c, width=3)
            d.line((10, 11, 10, 17), fill=c, width=3)
            d.ellipse((s - 12, 11, s - 8, 15), fill=c)
            d.ellipse((s - 9, 14, s - 5, 18), fill=c)

        def _draw_fs(d, s, c):
            p, a, w = 4, 9, 4
            d.line((p, p + a, p, p, p + a, p), fill=c, width=w)
            d.line((s - p - a, p, s - p, p, s - p, p + a), fill=c, width=w)
            d.line((p, s - p - a, p, s - p, p + a, s - p), fill=c, width=w)
            d.line((s - p - a, s - p, s - p, s - p, s - p, s - p - a), fill=c, width=w)

        def _draw_grid(d, s, c):
            for bx, by in ((3, 3), (16, 3), (3, 16), (16, 16)):
                d.rounded_rectangle((bx, by, bx + 10, by + 10), radius=3, outline=c, width=3)

        def _draw_search(d, s, c):
            r = int(s * 0.28)
            cx, cy = int(s * 0.42), int(s * 0.42)
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=c, width=3)
            d.line((cx + int(r * 0.72), cy + int(r * 0.72), s - 5, s - 5), fill=c, width=4)

        def _draw_user(d, s, c):
            cx = s // 2
            d.ellipse((cx - 6, 4, cx + 6, 16), outline=c, width=3)
            d.arc((5, 17, s - 5, s + 6), start=195, end=345, fill=c, width=3)

        def _draw_bell(d, s, c):
            d.arc((6, 4, s - 6, s - 8), start=180, end=360, fill=c, width=3)
            d.line((6, s // 2, 4, s - 9, s - 4, s - 9, s - 6, s // 2), fill=c, width=3)
            d.arc((s // 2 - 4, s - 10, s // 2 + 4, s - 3), start=0, end=180, fill=c, width=3)

        def _draw_gift(d, s, c):
            d.rounded_rectangle((4, 10, s - 4, 16), radius=2, outline=c, width=3)
            d.rounded_rectangle((6, 16, s - 6, s - 4), radius=2, outline=c, width=3)
            d.line((s // 2, 10, s // 2, s - 4), fill=c, width=3)
            d.arc((6, 3, s // 2, 11), start=160, end=360, fill=c, width=3)
            d.arc((s // 2, 3, s - 6, 11), start=180, end=20, fill=c, width=3)

        def _draw_raid(d, s, c):
            d.polygon([(s * 0.56, 3), (5, s * 0.54), (s * 0.48, s * 0.54),
                       (s * 0.42, s - 3), (s - 5, s * 0.44), (s * 0.52, s * 0.44)], fill=c)

        def _draw_settings(d, s, c):
            cx, cy = s / 2.0, s / 2.0
            r1, r2 = s * 0.29, s * 0.41
            for k in range(6):
                a = k * math.pi / 3.0
                d.line((cx + r1 * 0.8 * math.cos(a), cy + r1 * 0.8 * math.sin(a),
                        cx + r2 * math.cos(a), cy + r2 * math.sin(a)), fill=c, width=4)
            d.ellipse((cx - r1, cy - r1, cx + r1, cy + r1), outline=c, width=4)
            d.ellipse((cx - 4, cy - 4, cx + 4, cy + 4), fill=c)

        def _draw_logout(d, s, c):
            d.line((s // 2, 4, 5, 4, 5, s - 4, s // 2, s - 4), fill=c, width=3)
            d.line((s // 2 - 2, s // 2, s - 5, s // 2), fill=c, width=3)
            d.line((s - 10, s // 2 - 5, s - 4, s // 2, s - 10, s // 2 + 5), fill=c, width=3)

        def _draw_refresh(d, s, c):
            d.arc((4, 4, s - 4, s - 4), start=35, end=315, fill=c, width=3)
            d.polygon([(s - 6, 5), (s - 4, 13), (s - 12, 11)], fill=c)

        def _draw_plus(d, s, c):
            m = s // 2
            d.line((m, 5, m, s - 5), fill=c, width=4)
            d.line((5, m, s - 5, m), fill=c, width=4)

        def _draw_close(d, s, c):
            d.line((6, 6, s - 6, s - 6), fill=c, width=4)
            d.line((s - 6, 6, 6, s - 6), fill=c, width=4)

        def _draw_sort(d, s, c):
            d.line((4, 8, s - 4, 8), fill=c, width=3)
            d.line((7, s // 2, s - 7, s // 2), fill=c, width=3)
            d.line((11, s - 8, s - 11, s - 8), fill=c, width=3)

        def _draw_play(d, s, c):
            d.polygon([(7, 5), (s - 5, s // 2), (7, s - 5)], fill=c)

        def _draw_pause(d, s, c):
            d.rounded_rectangle((7, 5, 12, s - 5), radius=2, fill=c)
            d.rounded_rectangle((s - 12, 5, s - 7, s - 5), radius=2, fill=c)

        def _draw_skip_back(d, s, c):
            d.line((7, 6, 7, s - 6), fill=c, width=3)
            d.polygon([(s - 6, 6), (11, s // 2), (s - 6, s - 6)], fill=c)

        def _draw_skip_fwd(d, s, c):
            d.line((s - 7, 6, s - 7, s - 6), fill=c, width=3)
            d.polygon([(6, 6), (s - 11, s // 2), (6, s - 6)], fill=c)

        def _draw_clip(d, s, c):
            # Icona forbici / taglio professionale per Clip
            d.ellipse((4, s - 12, 12, s - 4), outline=c, width=3)
            d.ellipse((4, 4, 12, 12), outline=c, width=3)
            d.line((11, 10, s - 4, s - 5), fill=c, width=3)
            d.line((11, s - 10, s - 4, 5), fill=c, width=3)

        def _draw_chat(d, s, c):
            d.rounded_rectangle((4, 5, s - 4, s - 9), radius=5, outline=c, width=3)
            d.polygon([(8, s - 10), (7, s - 3), (15, s - 10)], fill=c)

        def _draw_pip(d, s, c):
            d.rounded_rectangle((3, 5, s - 3, s - 5), radius=4, outline=c, width=3)
            d.rounded_rectangle((s // 2, s // 2 - 1, s - 6, s - 8), radius=2, fill=c)

        def _draw_theater(d, s, c):
            d.rounded_rectangle((3, 6, s - 3, s - 6), radius=4, outline=c, width=3)
            d.line((s - 10, 6, s - 10, s - 6), fill=c, width=2)

        def _draw_volume(d, s, c):
            d.polygon([(4, 11), (10, 11), (16, 5), (16, s - 5), (10, s - 11), (4, s - 11)], fill=c)
            d.arc((13, 8, s - 5, s - 8), start=300, end=60, fill=c, width=3)
            d.arc((16, 4, s - 2, s - 4), start=300, end=60, fill=c, width=3)

        def _draw_mute(d, s, c):
            d.polygon([(4, 11), (10, 11), (16, 5), (16, s - 5), (10, s - 11), (4, s - 11)], fill=c)
            d.line((19, 10, s - 4, s - 10), fill=c, width=3)
            d.line((s - 4, 10, 19, s - 10), fill=c, width=3)

        def _draw_emote(d, s, c):
            d.ellipse((4, 4, s - 4, s - 4), outline=c, width=3)
            d.ellipse((9, 10, 13, 14), fill=c)
            d.ellipse((s - 13, 10, s - 9, 14), fill=c)
            d.arc((9, 10, s - 9, s - 8), start=20, end=160, fill=c, width=3)

        def _draw_send(d, s, c):
            d.polygon([(4, 5), (s - 4, s // 2), (4, s - 5), (9, s // 2)], fill=c)

        def _draw_coins(d, s, c):
            d.ellipse((5, 5, s - 5, s - 5), outline=c, width=3)
            d.ellipse((10, 10, s - 10, s - 10), fill=c)

        def _draw_check(d, s, c):
            d.line((5, s // 2 + 1, s // 2 - 2, s - 6, s - 4, 6), fill=c, width=4)

        def _draw_folder(d, s, c):
            d.polygon([(4, 7), (13, 7), (16, 10), (s - 4, 10), (s - 4, s - 5), (4, s - 5)], outline=c, width=3)

        def _draw_trash(d, s, c):
            d.line((5, 8, s - 5, 8), fill=c, width=3)
            d.line((11, 5, s - 11, 5), fill=c, width=3)
            d.rounded_rectangle((7, 8, s - 7, s - 4), radius=2, outline=c, width=3)

        def _draw_download(d, s, c):
            cx = s // 2
            d.line((cx, 4, cx, s - 10), fill=c, width=3)
            d.line((cx - 5, s - 14, cx, s - 9, cx + 5, s - 14), fill=c, width=3)
            d.line((5, s - 7, 5, s - 4, s - 5, s - 4, s - 5, s - 7), fill=c, width=3)

        def _draw_moon(d, s, c):
            d.arc((5, 4, s - 5, s - 4), start=55, end=295, fill=c, width=3)
            d.arc((9, 6, s - 1, s - 6), start=85, end=265, fill=c, width=3)

        def _draw_sun(d, s, c):
            cx, cy = s // 2, s // 2
            d.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), outline=c, width=3)
            for k in range(8):
                a = k * math.pi / 4.0
                d.line((cx + int(8 * math.cos(a)), cy + int(8 * math.sin(a)),
                        cx + int(11 * math.cos(a)), cy + int(11 * math.sin(a))), fill=c, width=3)

        def _draw_external(d, s, c):
            d.line((s // 2, 5, 5, 5, 5, s - 5, s - 5, s - 5, s - 5, s // 2), fill=c, width=3)
            d.line((s // 2, s // 2, s - 5, 5), fill=c, width=3)
            d.line((s - 12, 5, s - 5, 5, s - 5, 12), fill=c, width=3)

        def _draw_expand(d, s, c):
            d.line((6, 13, 6, 6, 13, 6), fill=c, width=3)
            d.line((6, 6, s // 2 - 2, s // 2 - 2), fill=c, width=3)
            d.line((s - 6, s - 13, s - 6, s - 6, s - 13, s - 6), fill=c, width=3)
            d.line((s - 6, s - 6, s // 2 + 2, s // 2 + 2), fill=c, width=3)

        def _draw_swap(d, s, c):
            d.line((5, 10, s - 6, 10), fill=c, width=3)
            d.line((s - 11, 5, s - 5, 10, s - 11, 15), fill=c, width=3)
            d.line((6, s - 10, s - 5, s - 10), fill=c, width=3)
            d.line((11, s - 15, 5, s - 10, 11, s - 5), fill=c, width=3)

        def _draw_chev_down(d, s, c):
            d.line((6, 10, s // 2, s - 9, s - 6, 10), fill=c, width=3)

        def _draw_chev_up(d, s, c):
            d.line((6, s - 10, s // 2, 9, s - 6, s - 10), fill=c, width=3)

        def _draw_shield(d, s, c):
            d.polygon([(s // 2, 4), (s - 5, 7), (s - 6, 16), (s // 2, s - 4), (6, 16), (5, 7)], outline=c, width=3)
            d.line((s // 2 - 4, s // 2, s // 2 - 1, s // 2 + 3, s // 2 + 5, s // 2 - 4), fill=c, width=3)

        def _draw_eye(d, s, c):
            d.arc((3, 7, s - 3, s - 7), start=195, end=345, fill=c, width=3)
            d.arc((3, 7, s - 3, s - 7), start=15, end=165, fill=c, width=3)
            d.ellipse((s // 2 - 3, s // 2 - 3, s // 2 + 3, s // 2 + 3), fill=c)

        DL = "#0f172a"
        DD = "#e2e8f0"
        ML = "#475569"
        MD = "#94a3b8"
        WH = "#ffffff"
        AC = "#8b5cf6"
        CY = "#06b6d4"
        GD = "#f59e0b"
        RD = "#ef4444"
        GR = "#10b981"

        star_gold = _star_img(GD, filled=True, sz=18)
        self._icon_star_filled = ctk.CTkImage(light_image=star_gold, dark_image=star_gold, size=(18, 18))
        self._icon_star_outline = ctk.CTkImage(
            light_image=_star_img("#64748b", filled=False, sz=18),
            dark_image=_star_img("#94a3b8", filled=False, sz=18),
            size=(18, 18),
        )
        self._icon_dots_vert = _vec(16, ML, "#cbd5e1", _draw_dots)
        self._icon_game_purple = _vec(14, AC, "#a78bfa", _draw_game)
        self._icon_fullscreen = _vec(16, DL, WH, _draw_fs)
        self._icon_multiview_active = _vec(14, WH, WH, _draw_grid)
        self._icon_multiview_idle = _vec(14, DL, DD, _draw_grid)

        self._icon_search = _vec(15, ML, MD, _draw_search)
        self._icon_search_white = _vec(14, WH, WH, _draw_search)
        self._icon_user = _vec(16, DL, DD, _draw_user)
        self._icon_user_accent = _vec(16, AC, "#a78bfa", _draw_user)
        self._icon_bell = _vec(15, DL, DD, _draw_bell)
        self._icon_bell_white = _vec(15, WH, WH, _draw_bell)
        self._icon_gift = _vec(15, "#0284c7", "#38bdf8", _draw_gift)
        self._icon_gift_white = _vec(15, WH, WH, _draw_gift)
        self._icon_raid = _vec(15, "#d97706", "#fbbf24", _draw_raid)
        self._icon_raid_white = _vec(15, WH, WH, _draw_raid)
        self._icon_settings = _vec(15, DL, DD, _draw_settings)
        self._icon_settings_white = _vec(15, WH, WH, _draw_settings)
        self._icon_logout = _vec(15, "#dc2626", "#f87171", _draw_logout)
        self._icon_refresh = _vec(15, DL, DD, _draw_refresh)
        self._icon_plus = _vec(14, DL, DD, _draw_plus)
        self._icon_plus_white = _vec(14, WH, WH, _draw_plus)
        self._icon_close = _vec(13, ML, MD, _draw_close)
        self._icon_close_white = _vec(13, WH, WH, _draw_close)
        self._icon_sort = _vec(14, DL, DD, _draw_sort)
        self._icon_play = _vec(14, DL, DD, _draw_play)
        self._icon_play_white = _vec(14, WH, WH, _draw_play)
        self._icon_pause = _vec(14, DL, DD, _draw_pause)
        self._icon_skip_back = _vec(14, DL, DD, _draw_skip_back)
        self._icon_skip_fwd = _vec(14, DL, DD, _draw_skip_fwd)
        self._icon_clip = _vec(15, DL, DD, _draw_clip)
        self._icon_chat = _vec(15, DL, DD, _draw_chat)
        self._icon_chat_white = _vec(15, WH, WH, _draw_chat)
        self._icon_pip = _vec(14, DL, DD, _draw_pip)
        self._icon_theater = _vec(14, DL, DD, _draw_theater)
        self._icon_volume = _vec(15, DL, DD, _draw_volume)
        self._icon_mute = _vec(15, RD, "#f87171", _draw_mute)
        self._icon_emote = _vec(16, DL, DD, _draw_emote)
        self._icon_send_white = _vec(14, WH, WH, _draw_send)
        self._icon_coins = _vec(15, "#d97706", "#fbbf24", _draw_coins)
        self._icon_check = _vec(15, GR, "#34d399", _draw_check)
        self._icon_check_white = _vec(15, WH, WH, _draw_check)
        self._icon_folder = _vec(14, DL, DD, _draw_folder)
        self._icon_trash = _vec(14, DL, DD, _draw_trash)
        self._icon_download = _vec(15, DL, DD, _draw_download)
        self._icon_moon = _vec(14, DL, DD, _draw_moon)
        self._icon_sun = _vec(14, "#d97706", "#fbbf24", _draw_sun)
        self._icon_external = _vec(14, ML, MD, _draw_external)
        self._icon_expand = _vec(13, DL, DD, _draw_expand)
        self._icon_expand_white = _vec(13, WH, WH, _draw_expand)
        self._icon_swap = _vec(14, DL, DD, _draw_swap)
        self._icon_chev_down = _vec(12, ML, MD, _draw_chev_down)
        self._icon_chev_up = _vec(12, ML, MD, _draw_chev_up)
        self._icon_shield = _vec(14, "#059669", "#34d399", _draw_shield)
        self._icon_eye = _vec(13, ML, MD, _draw_eye)

    @staticmethod
    def _build_shadow_toolkit():
        import math as _math
        import tkinter as _tk
        import tkinter.font as _tkfont

        _RESAMPLE_LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
        _IMG_CACHE = {}

        def _is_dark():
            try:
                return str(ctk.get_appearance_mode()).strip().lower() == "dark"
            except Exception:
                return True

        def _color_pair(c, fallback=("#FFFFFF", "#18181f")):
            if isinstance(c, (tuple, list)) and len(c) >= 2:
                a = str(c[0] or fallback[0])
                b = str(c[1] or fallback[1])
                return (fallback[0] if a.lower() == "transparent" else a,
                        fallback[1] if b.lower() == "transparent" else b)
            if isinstance(c, str) and c.strip() and c.strip().lower() != "transparent":
                s = c.strip()
                return (s, s)
            return fallback

        def _pick_mode(pair_or_color, fallback=("#FFFFFF", "#18181f")):
            l_col, d_col = _color_pair(pair_or_color, fallback)
            return d_col if _is_dark() else l_col

        def _parent_bg_pair(widget):
            w = widget
            tk_fallback = None
            for _ in range(18):
                if w is None:
                    break
                surf = getattr(w, "_surface_fg_pair", None)
                if surf is not None:
                    return _color_pair(surf)
                try:
                    fg = w.cget("fg_color")
                    if isinstance(fg, (tuple, list)) or (isinstance(fg, str) and fg.strip().lower() not in ("", "transparent")):
                        return _color_pair(fg)
                except Exception:
                    pass
                if tk_fallback is None and not isinstance(w, ctk.CTkBaseClass):
                    try:
                        bg = str(w.cget("bg"))
                        if bg.startswith("#"):
                            tk_fallback = bg
                    except Exception:
                        pass
                w = getattr(w, "master", None)
            if tk_fallback is not None:
                return (tk_fallback, tk_fallback)
            return ("#F2F3F7", "#101014")

        def _parse_rgba(widget, color_str, alpha=255):
            s = (color_str or "").strip()
            if not s or s.lower() == "transparent":
                return (0, 0, 0, 0)
            if s.startswith("#"):
                h = s[1:]
                if len(h) == 3:
                    return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), alpha)
                if len(h) >= 6:
                    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)
            try:
                r16, g16, b16 = widget.winfo_rgb(s)
                return (r16 >> 8, g16 >> 8, b16 >> 8, alpha)
            except Exception:
                return (24, 24, 31, alpha)

        def _get_scale(widget):
            try:
                sc = float(ctk.ScalingTracker.get_widget_scaling(widget))
                return sc if 0.5 <= sc <= 4.0 else 1.0
            except Exception:
                return 1.0

        def _shadow_metrics(ox, oy, sc=1.0):
            ox_s = max(1, int(round(max(1, ox) * sc)))
            oy_s = max(1, int(round(max(1, oy) * sc)))
            blur = round(max(2.6, min(4.2, 2.0 + max(ox, oy) * 0.42)) * sc, 2)
            pl = int(round((3 if ox <= 2 else 4) * sc))
            pt = int(round((2 if oy <= 3 else 3) * sc))
            pr = ox_s + int(round((5 if ox <= 2 else 6) * sc))
            pb = oy_s + int(round((5 if oy <= 3 else 6) * sc))
            return ox_s, oy_s, blur, pl, pt, pr, pb

        def _render_shadow_photo(widget, w, h, pl, pt, pr, pb, cr, ox, oy, blur,
                                 bg_hex, face_hex, border_hex, bw, dark_flag, glow_hex=""):
            w = max(8, int(w))
            h = max(8, int(h))
            bw = max(0, int(bw))
            glow_str = str(glow_hex or "")
            key = (w, h, pl, pt, pr, pb, int(cr), int(ox), int(oy),
                   int(round(blur * 10)), bg_hex, face_hex, border_hex if bw > 0 else "", bw, bool(dark_flag), glow_str)
            cached = _IMG_CACHE.get(key)
            if cached is not None:
                return cached

            S = 2
            ws, hs = w * S, h * S
            bg_rgba = _parse_rgba(widget, bg_hex, 255)
            face_rgba = _parse_rgba(widget, face_hex, 255)
            border_rgba = _parse_rgba(widget, border_hex, 255) if bw > 0 else (0, 0, 0, 0)

            base = Image.new("RGBA", (ws, hs), bg_rgba)
            sh = Image.new("RGBA", (ws, hs), (0, 0, 0, 0))
            d_sh = ImageDraw.Draw(sh)

            bx0, by0 = pl * S, pt * S
            bx1, by1 = max(bx0 + 2, (w - pr) * S - 1), max(by0 + 2, (h - pb) * S - 1)
            max_r = max(0, min((bx1 - bx0) // 2, (by1 - by0) // 2))
            r_eff = min(max(0, int(cr) * S), max_r)

            sx0, sy0 = bx0 + ox * S, by0 + oy * S
            sx1, sy1 = min(ws - 2, bx1 + ox * S), min(hs - 2, by1 + oy * S)

            amb_col = (0, 0, 0, 62 if dark_flag else 20)
            drop_col = (0, 0, 0, 152 if dark_flag else 48)
            if sx1 > sx0 + 1 and sy1 > sy0 + 1:
                d_sh.rounded_rectangle([sx0, sy0, sx1, sy1], radius=r_eff, fill=drop_col)
            d_sh.rounded_rectangle([bx0, by0, bx1, by1], radius=r_eff, fill=amb_col)
            if glow_str:
                gr, gg, gb, _ = _parse_rgba(widget, glow_str, 255)
                gx0, gy0 = max(S, bx0 - S), max(S, by0 - S)
                gx1, gy1 = min(ws - S - 1, bx1 + S), min(hs - S - 1, by1 + S)
                d_sh.rounded_rectangle(
                    [gx0, gy0, gx1, gy1],
                    radius=min(max_r + S, r_eff + S),
                    outline=(gr, gg, gb, 148 if dark_flag else 108),
                    width=max(2, S * 2),
                )
            sh = sh.filter(ImageFilter.GaussianBlur(radius=max(1.0, blur * S)))

            # Azzera il bordo esterno da 1px (S px a 2x) del layer ombra senza usare ImageChops
            sh.paste((0, 0, 0, 0), (0, 0, ws, S))
            sh.paste((0, 0, 0, 0), (0, max(0, hs - S), ws, hs))
            sh.paste((0, 0, 0, 0), (0, 0, S, hs))
            sh.paste((0, 0, 0, 0), (max(0, ws - S), 0, ws, hs))

            comp = Image.alpha_composite(base, sh)

            fg = Image.new("RGBA", (ws, hs), (0, 0, 0, 0))
            d_fg = ImageDraw.Draw(fg)
            if face_rgba[3] > 0 or bw > 0:
                d_fg.rounded_rectangle(
                    [bx0, by0, bx1, by1],
                    radius=r_eff,
                    fill=(face_rgba if face_rgba[3] > 0 else bg_rgba),
                    outline=(border_rgba if bw > 0 else None),
                    width=(bw * S if bw > 0 else 0),
                )
            comp = Image.alpha_composite(comp, fg).resize((w, h), _RESAMPLE_LANCZOS)

            if len(_IMG_CACHE) >= 512:
                for k_old in list(_IMG_CACHE.keys())[:256]:
                    _IMG_CACHE.pop(k_old, None)
            tk_img = ImageTk.PhotoImage(comp)
            _IMG_CACHE[key] = tk_img
            return tk_img

        def _sync_theme_subtree(parent, cur_bg_pair, mode_str):
            cur_pair = _color_pair(cur_bg_pair)
            try:
                children = list(parent.winfo_children())
            except Exception:
                return
            for ch in children:
                try:
                    if isinstance(ch, (_SmoothShadowShell, _SmoothShadowBtn)):
                        continue
                    if isinstance(ch, ctk.CTkBaseClass):
                        next_bg = cur_pair
                        try:
                            fg = ch.cget("fg_color")
                            if isinstance(fg, (tuple, list)):
                                a = str(fg[0] or "").strip().lower()
                                b = str(fg[1] or "").strip().lower()
                                if a != "transparent" or b != "transparent":
                                    next_bg = _color_pair(fg, cur_pair)
                            elif isinstance(fg, str) and fg.strip().lower() not in ("", "transparent"):
                                next_bg = _color_pair(fg, cur_pair)
                        except Exception:
                            pass
                        try:
                            ch.configure(bg_color=cur_pair)
                        except Exception:
                            pass
                        try:
                            ch._set_appearance_mode(mode_str)
                        except Exception:
                            pass
                        _sync_theme_subtree(ch, next_bg, mode_str)
                    elif isinstance(ch, _tk.Frame):
                        surf_fg = getattr(ch, "_surface_fg_pair", None)
                        next_bg = _color_pair(surf_fg, cur_pair) if surf_fg is not None else cur_pair
                        try:
                            ch.configure(bg=_pick_mode(next_bg))
                        except Exception:
                            pass
                        _sync_theme_subtree(ch, next_bg, mode_str)
                except Exception:
                    pass

        class _SmoothShadowShell(_tk.Canvas):
            def __init__(self, parent, corner_radius=10, offset_x=3, offset_y=4,
                         surface_fg=None, border_color=None, border_width=0,
                         cursor="", fixed_height=None, fixed_propagate=True,
                         hover_border_color=None, hover_glow_color=None):
                self._bg_pair = _parent_bg_pair(parent)
                self._fg_pair = _color_pair(surface_fg if surface_fg is not None else C_BG_CARD)
                self._border_pair = _color_pair(border_color if border_color is not None else C_BORDER)
                self._hover_border_pair = _color_pair(hover_border_color) if hover_border_color is not None else None
                self._hover_glow_pair = _color_pair(hover_glow_color) if hover_glow_color is not None else None
                self._bw = max(0, int(border_width or 0))
                self._cr = max(0, int(corner_radius or 0))
                self._raw_ox = max(1, int(offset_x))
                self._raw_oy = max(1, int(offset_y))
                self._fixed_h = fixed_height
                self._cur_photo = None
                self._img_id = None
                self._last_sig = None
                self._in_redraw = False
                self._hovered = False
                self._hover_leave_after = None

                super().__init__(
                    parent,
                    width=1, height=1,
                    bg=_pick_mode(self._bg_pair),
                    highlightthickness=0, bd=0, relief="flat",
                    cursor=(cursor or ""),
                )

                sc = _get_scale(self)
                ox_s, oy_s, blur, pl, pt, pr, pb = _shadow_metrics(self._raw_ox, self._raw_oy, sc)
                cr_s = int(round(self._cr * sc))
                bw_s = max(0, int(round(self._bw * sc))) if self._bw > 0 else 0
                fh_s = int(round(fixed_height * sc)) if fixed_height else None

                r_ref = max(0, min(cr_s, (fh_s // 2) if fh_s else cr_s))
                r_in = max(0, r_ref - bw_s - 1)
                dy_base = (bw_s + 3) if r_ref >= int(14 * sc) else (bw_s + 2)
                if fh_s and (fh_s - 2 * dy_base) < int(26 * sc):
                    dy_base = max(bw_s + 1, (fh_s - int(26 * sc)) // 2)
                if r_ref > dy_base and r_in > (r_ref - dy_base):
                    dx_base = int(_math.ceil(r_ref - _math.sqrt(max(0, r_in * r_in - (r_ref - dy_base) ** 2))))
                elif r_ref > 0:
                    dx_base = max(bw_s + 2, r_ref // 2)
                else:
                    dx_base = bw_s + 1
                dx_in = max(bw_s + 1, min(cr_s, dx_base))
                dy_in = max(bw_s + 1, dy_base)

                shell = self

                class _SurfaceFrame(_tk.Frame):
                    def __init__(sf, master, fg_pair, **kw):
                        sf._ctk_fg_pair = fg_pair
                        sf._surface_fg_pair = fg_pair
                        super().__init__(master, **kw)

                    def cget(sf, key):
                        if key == "fg_color":
                            return sf._ctk_fg_pair
                        if key == "bg_color":
                            return shell._bg_pair
                        if key in ("corner_radius", "border_width"):
                            return 0
                        return super().cget(key)

                    def configure(sf, cnf=None, **kw):
                        if cnf is None and not kw:
                            return super().configure()
                        if isinstance(cnf, dict):
                            kw = {**cnf, **kw}
                            cnf = None
                        redraw_needed = False
                        if "fg_color" in kw:
                            fg_v = kw.pop("fg_color")
                            if fg_v is not None:
                                prev_pair = shell._fg_pair
                                shell._fg_pair = _color_pair(fg_v, shell._fg_pair)
                                sf._ctk_fg_pair = shell._fg_pair
                                sf._surface_fg_pair = shell._fg_pair
                                try:
                                    super().configure(bg=_pick_mode(shell._fg_pair))
                                except Exception:
                                    pass
                                if shell._fg_pair != prev_pair:
                                    _sync_theme_subtree(sf, shell._fg_pair, ("Dark" if _is_dark() else "Light"))
                                redraw_needed = True
                        if "border_color" in kw:
                            bc = kw.pop("border_color")
                            if bc is not None:
                                shell._border_pair = _color_pair(bc, shell._border_pair)
                                redraw_needed = True
                        if "border_width" in kw:
                            bwv = kw.pop("border_width")
                            if bwv is not None:
                                shell._bw = max(0, int(bwv))
                                redraw_needed = True
                        kw.pop("corner_radius", None)
                        kw.pop("bg_color", None)
                        if cnf is not None:
                            res = super().configure(cnf, **kw)
                        elif kw:
                            res = super().configure(**kw)
                        else:
                            res = None
                        sp_ref = getattr(shell, "_spacer", None)
                        if sp_ref is not None:
                            try:
                                sp_ref.configure(bg=_pick_mode(shell._fg_pair))
                            except Exception:
                                pass
                        if redraw_needed:
                            shell._last_sig = None
                            shell._redraw()
                        return res

                    config = configure

                self.inner = _SurfaceFrame(
                    self, self._fg_pair,
                    width=0, height=0, bd=0, highlightthickness=0,
                    bg=_pick_mode(self._fg_pair),
                    cursor=(cursor or ""),
                )
                self.inner._shadow_outer = self
                self._spacer = None

                if fh_s:
                    if not fixed_propagate:
                        self.pack_propagate(False)
                        super().configure(width=1, height=max(12, fh_s + pt + pb))
                        self.inner.pack_propagate(False)
                    else:
                        inner_h = max(1, int(round((fixed_height * sc) - 2 * dy_in)))
                        sp = _tk.Frame(
                            self.inner, width=0, height=inner_h,
                            bg=_pick_mode(self._fg_pair), bd=0, highlightthickness=0,
                        )
                        sp.pack_propagate(False)
                        sp.pack(side="left", padx=0, pady=0)
                        self._spacer = sp

                self.inner.pack(
                    fill="both", expand=True,
                    padx=(pl + dx_in, pr + dx_in),
                    pady=(pt + dy_in, pb + dy_in),
                )

                orig_bind = self.inner.bind

                def _inner_bind(sequence=None, func=None, add=True):
                    if func is None:
                        return orig_bind(sequence)
                    add_arg = "+" if add in (None, False) else add
                    res = orig_bind(sequence, func, add=add_arg)
                    if sequence:
                        try:
                            self.bind(sequence, func, add="+")
                        except Exception:
                            pass
                    return res

                self.inner.bind = _inner_bind
                self.bind("<Configure>", self._on_configure, add="+")

            def _on_configure(self, event):
                self._redraw(event.width, event.height)

            def _redraw(self, w=None, h=None):
                if getattr(self, "_in_redraw", False):
                    return
                try:
                    if not self.winfo_exists():
                        return
                except Exception:
                    return
                if w is None:
                    w = self.winfo_width()
                if h is None:
                    h = self.winfo_height()
                if w <= 8 or h <= 8:
                    return
                self._in_redraw = True
                try:
                    sc = _get_scale(self)
                    ox_s, oy_s, blur, pl, pt, pr, pb = _shadow_metrics(self._raw_ox, self._raw_oy, sc)
                    cr_s = int(round(self._cr * sc))
                    bw_s = max(0, int(round(self._bw * sc))) if self._bw > 0 else 0
                    dark = _is_dark()
                    bg_hex = _pick_mode(self._bg_pair)
                    face_hex = _pick_mode(self._fg_pair)
                    hover_active = bool(self._hovered and (self._hover_border_pair or self._hover_glow_pair))
                    border_hex = _pick_mode(self._hover_border_pair if (hover_active and self._hover_border_pair) else self._border_pair)
                    glow_hex = _pick_mode(self._hover_glow_pair) if (hover_active and self._hover_glow_pair) else ""

                    sig = (w, h, dark, bg_hex, face_hex, border_hex, glow_hex, bw_s, cr_s)
                    if sig == self._last_sig and self._img_id is not None:
                        return
                    self._last_sig = sig

                    try:
                        super().configure(bg=bg_hex)
                    except Exception:
                        pass
                    if self._spacer is not None:
                        try:
                            self._spacer.configure(bg=face_hex)
                        except Exception:
                            pass

                    photo = _render_shadow_photo(
                        self, w, h, pl, pt, pr, pb, cr_s, ox_s, oy_s, blur,
                        bg_hex, face_hex, border_hex, bw_s, dark, glow_hex=glow_hex
                    )
                    self._cur_photo = photo
                    if self._img_id is None:
                        self._img_id = self.create_image(0, 0, anchor="nw", image=photo)
                        self.tag_lower(self._img_id)
                    else:
                        self.itemconfigure(self._img_id, image=photo)
                finally:
                    self._in_redraw = False

            def _set_hover_glow(self, active):
                active_b = bool(active)
                if active_b == self._hovered:
                    return
                self._hovered = active_b
                self._redraw()

            def enable_hover_glow(self):
                def _is_inside():
                    try:
                        px, py = self.winfo_pointerxy()
                        hit = self.winfo_containing(px, py)
                        cur = hit
                        while cur is not None:
                            if cur == self:
                                return True
                            cur = getattr(cur, "master", None)
                    except Exception:
                        pass
                    return False

                def _check_leave():
                    self._hover_leave_after = None
                    if not _is_inside():
                        self._set_hover_glow(False)

                def _on_enter(_e=None):
                    if self._hover_leave_after is not None:
                        try:
                            self.after_cancel(self._hover_leave_after)
                        except Exception:
                            pass
                        self._hover_leave_after = None
                    self._set_hover_glow(True)

                def _on_leave(_e=None):
                    if self._hover_leave_after is not None:
                        try:
                            self.after_cancel(self._hover_leave_after)
                        except Exception:
                            pass
                    try:
                        self._hover_leave_after = self.after(20, _check_leave)
                    except Exception:
                        pass

                targets = [self, self.inner]
                stack = list(self.inner.winfo_children())
                while stack:
                    w = stack.pop(0)
                    targets.append(w)
                    try:
                        stack.extend(w.winfo_children())
                    except Exception:
                        pass
                for tw in targets:
                    try:
                        tw.bind("<Enter>", _on_enter, add="+")
                        tw.bind("<Leave>", _on_leave, add="+")
                    except Exception:
                        pass

            def refresh_theme(self):
                self._bg_pair = _parent_bg_pair(self.master)
                self._last_sig = None
                try:
                    self.inner.configure(fg_color=self._fg_pair)
                except Exception:
                    pass
                mode_str = "Dark" if _is_dark() else "Light"
                _sync_theme_subtree(self.inner, self._fg_pair, mode_str)
                self._redraw()

        class _SmoothShadowBtn(_tk.Canvas):
            def __init__(self, parent, offset_x=3, offset_y=4, **btn_kw):
                self._raw_ox = max(1, int(offset_x))
                self._raw_oy = max(1, int(offset_y))
                self._text = str(btn_kw.get("text", "") or "")
                self._ctk_image = btn_kw.get("image", None)
                self._compound = str(btn_kw.get("compound", "left") or "left")
                self._command = btn_kw.get("command", None)
                self._state = str(btn_kw.get("state", "normal") or "normal")
                self._font = btn_kw.get("font", None)
                self._cr = int(btn_kw.get("corner_radius", 8) or 8)
                self._req_w = int(btn_kw.get("width", 0) or 0)
                self._req_h = int(btn_kw.get("height", 28) or 28)
                self._bw = max(0, int(btn_kw.get("border_width", 0) or 0))

                self._bg_pair = _parent_bg_pair(parent)
                self._fg_pair = _color_pair(btn_kw.get("fg_color", C_ACCENT), C_ACCENT)
                self._hover_pair = _color_pair(btn_kw.get("hover_color", self._fg_pair), self._fg_pair)
                self._txt_pair = _color_pair(btn_kw.get("text_color", ("#0f172a", "#ffffff")), ("#0f172a", "#ffffff"))
                self._border_pair = _color_pair(btn_kw.get("border_color", C_BORDER), C_BORDER)

                self._hovered = False
                self._pressed = False
                self._cur_photo = None
                self._cur_icon_tk = None
                self._bg_item = None
                self._icon_item = None
                self._txt_item = None
                self._last_bg_sig = None

                super().__init__(
                    parent,
                    bg=_pick_mode(self._bg_pair),
                    highlightthickness=0, bd=0, relief="flat",
                    cursor=("hand2" if self._state != "disabled" else ""),
                )
                self._shadow_wrap = self
                self._apply_requested_size()

                self.bind("<Configure>", self._on_configure, add="+")
                self.bind("<Enter>", self._on_enter, add="+")
                self.bind("<Leave>", self._on_leave, add="+")
                self.bind("<ButtonPress-1>", self._on_press, add="+")
                self.bind("<ButtonRelease-1>", self._on_release, add="+")

            def _measure_text_px(self):
                if not self._text:
                    return 0
                try:
                    f = self._font
                    if f is not None and isinstance(f, _tkfont.Font):
                        return f.measure(self._text)
                    return _tkfont.Font(family="Segoe UI", size=11).measure(self._text)
                except Exception:
                    return len(self._text) * 7

            def _apply_requested_size(self):
                sc = _get_scale(self)
                _, _, _, pl, pt, pr, pb = _shadow_metrics(self._raw_ox, self._raw_oy, sc)
                if self._req_w > 0:
                    box_w = int(round(self._req_w * sc))
                else:
                    icon_w = 0
                    if self._ctk_image is not None:
                        sz = getattr(self._ctk_image, "_size", (16, 16))
                        icon_w = int(round(sz[0] * sc)) + (6 if self._text else 0)
                    txt_w = self._measure_text_px()
                    box_w = max(int(round(28 * sc)), txt_w + icon_w + int(round(18 * sc)))
                box_h = int(round(max(18, self._req_h) * sc))
                try:
                    super().configure(width=box_w + pl + pr, height=box_h + pt + pb)
                except Exception:
                    pass

            def _on_configure(self, event):
                self._redraw(event.width, event.height)

            def _on_enter(self, _evt=None):
                if self._state != "disabled":
                    self._hovered = True
                    self._redraw()

            def _on_leave(self, _evt=None):
                if self._hovered or self._pressed:
                    self._hovered = False
                    self._pressed = False
                    self._redraw()

            def _on_press(self, _evt=None):
                if self._state != "disabled":
                    self._pressed = True
                    self._redraw()

            def _on_release(self, evt=None):
                was_pressed = self._pressed
                self._pressed = False
                self._redraw()
                if was_pressed and self._state != "disabled" and self._command is not None:
                    try:
                        w, h = self.winfo_width(), self.winfo_height()
                        if evt is None or (0 <= evt.x <= w and 0 <= evt.y <= h):
                            self._command()
                    except Exception:
                        pass

            def configure(self, **kw):
                size_dirty = False
                tk_kw = {}
                if "text" in kw:
                    self._text = str(kw.pop("text") or "")
                    size_dirty = (self._req_w <= 0)
                if "image" in kw:
                    self._ctk_image = kw.pop("image")
                    size_dirty = (self._req_w <= 0)
                if "compound" in kw:
                    self._compound = str(kw.pop("compound") or "left")
                if "command" in kw:
                    self._command = kw.pop("command")
                if "font" in kw:
                    self._font = kw.pop("font")
                    size_dirty = (self._req_w <= 0)
                if "fg_color" in kw and kw["fg_color"] is not None:
                    self._fg_pair = _color_pair(kw.pop("fg_color"), self._fg_pair)
                if "hover_color" in kw and kw["hover_color"] is not None:
                    self._hover_pair = _color_pair(kw.pop("hover_color"), self._hover_pair)
                if "text_color" in kw and kw["text_color"] is not None:
                    self._txt_pair = _color_pair(kw.pop("text_color"), self._txt_pair)
                if "border_color" in kw and kw["border_color"] is not None:
                    self._border_pair = _color_pair(kw.pop("border_color"), self._border_pair)
                if "border_width" in kw and kw["border_width"] is not None:
                    self._bw = max(0, int(kw.pop("border_width")))
                if "corner_radius" in kw and kw["corner_radius"] is not None:
                    self._cr = max(0, int(kw.pop("corner_radius")))
                if "width" in kw and kw["width"] is not None:
                    self._req_w = int(kw.pop("width"))
                    size_dirty = True
                if "height" in kw and kw["height"] is not None:
                    self._req_h = int(kw.pop("height"))
                    size_dirty = True
                if "state" in kw and kw["state"] is not None:
                    self._state = str(kw.pop("state"))
                    tk_kw["cursor"] = "hand2" if self._state != "disabled" else ""
                for k in ("cursor",):
                    if k in kw:
                        tk_kw[k] = kw.pop(k)
                if tk_kw:
                    super().configure(**tk_kw)
                if size_dirty:
                    self._apply_requested_size()
                self._last_bg_sig = None
                self._redraw()

            def cget(self, key):
                if key == "text":
                    return self._text
                if key == "fg_color":
                    return self._fg_pair
                if key == "hover_color":
                    return self._hover_pair
                if key == "text_color":
                    return self._txt_pair
                if key == "state":
                    return self._state
                if key == "image":
                    return self._ctk_image
                return super().cget(key)

            def _redraw(self, w=None, h=None):
                try:
                    if not self.winfo_exists():
                        return
                except Exception:
                    return
                if w is None:
                    w = self.winfo_width()
                if h is None:
                    h = self.winfo_height()
                if w <= 8 or h <= 8:
                    return

                sc = _get_scale(self)
                ox_s, oy_s, blur, pl, pt, pr, pb = _shadow_metrics(self._raw_ox, self._raw_oy, sc)
                cr_s = int(round(self._cr * sc))
                bw_s = max(0, int(round(self._bw * sc))) if self._bw > 0 else 0
                dark = _is_dark()
                self._bg_pair = _parent_bg_pair(self.master)
                bg_hex = _pick_mode(self._bg_pair)
                face_pair = self._hover_pair if (self._hovered and self._state != "disabled") else self._fg_pair
                face_hex = _pick_mode(face_pair)
                border_hex = _pick_mode(self._border_pair)
                txt_hex = _pick_mode(self._txt_pair)

                bg_sig = (w, h, dark, bg_hex, face_hex, border_hex, bw_s, cr_s)
                if bg_sig != self._last_bg_sig or self._bg_item is None:
                    self._last_bg_sig = bg_sig
                    try:
                        super().configure(bg=bg_hex)
                    except Exception:
                        pass
                    photo = _render_shadow_photo(
                        self, w, h, pl, pt, pr, pb, cr_s, ox_s, oy_s, blur,
                        bg_hex, face_hex, border_hex, bw_s, dark
                    )
                    self._cur_photo = photo
                    if self._bg_item is None:
                        self._bg_item = self.create_image(0, 0, anchor="nw", image=photo)
                    else:
                        self.itemconfigure(self._bg_item, image=photo)

                # Icona + testo centrati sul corpo reale del pulsante (esclusa l'ombra)
                cx = (pl + (w - pr)) / 2.0
                cy = (pt + (h - pb)) / 2.0 + (1.0 if self._pressed else 0.0)

                icon_tk = None
                icon_w = 0
                if self._ctk_image is not None:
                    try:
                        pil_src = getattr(self._ctk_image, "_dark_image" if dark else "_light_image", None)
                        if pil_src is None:
                            pil_src = getattr(self._ctk_image, "_light_image", None)
                        if pil_src is not None:
                            sz = getattr(self._ctk_image, "_size", pil_src.size)
                            iw = max(1, int(round(sz[0] * sc)))
                            ih = max(1, int(round(sz[1] * sc)))
                            icon_w = iw
                            pil_rs = pil_src.convert("RGBA")
                            if pil_rs.size != (iw, ih):
                                pil_rs = pil_rs.resize((iw, ih), _RESAMPLE_LANCZOS)
                            icon_tk = ImageTk.PhotoImage(pil_rs)
                    except Exception:
                        icon_tk = None
                        icon_w = 0
                self._cur_icon_tk = icon_tk

                has_txt = bool(self._text)
                has_ico = icon_tk is not None
                gap = int(round(5 * sc)) if (has_txt and has_ico) else 0
                txt_w = self._measure_text_px() if has_txt else 0
                total_w = icon_w + gap + txt_w

                if has_ico:
                    ix = cx if not has_txt else (
                        (cx - total_w / 2.0 + icon_w / 2.0) if self._compound != "right"
                        else (cx + total_w / 2.0 - icon_w / 2.0)
                    )
                    if self._icon_item is None:
                        self._icon_item = self.create_image(ix, cy, anchor="center", image=icon_tk)
                    else:
                        self.coords(self._icon_item, ix, cy)
                        self.itemconfigure(self._icon_item, image=icon_tk, state="normal")
                elif self._icon_item is not None:
                    self.itemconfigure(self._icon_item, state="hidden")

                if has_txt:
                    tx = cx if not has_ico else (
                        (cx - total_w / 2.0 + icon_w + gap + txt_w / 2.0) if self._compound != "right"
                        else (cx - total_w / 2.0 + txt_w / 2.0)
                    )
                    fnt = self._font if self._font is not None else ("Segoe UI", 11)
                    if self._txt_item is None:
                        self._txt_item = self.create_text(tx, cy, anchor="center", text=self._text, font=fnt, fill=txt_hex)
                    else:
                        self.coords(self._txt_item, tx, cy)
                        self.itemconfigure(self._txt_item, text=self._text, font=fnt, fill=txt_hex, state="normal")
                elif self._txt_item is not None:
                    self.itemconfigure(self._txt_item, state="hidden")

                if self._bg_item is not None:
                    self.tag_lower(self._bg_item)

            def refresh_theme(self):
                self._bg_pair = _parent_bg_pair(self.master)
                self._last_bg_sig = None
                self._redraw()

        return _SmoothShadowShell, _SmoothShadowBtn

    def _track_shadow_widget(self, widget):
        import weakref as _weakref
        if not hasattr(self, "_smooth_shadow_widgets"):
            self._smooth_shadow_widgets = _weakref.WeakSet()
        self._smooth_shadow_widgets.add(widget)
        return widget

    def _create_shadow_shell(self, parent, corner_radius=10, offset_x=4, offset_y=5,
                             surface_fg=None, border_color=None, border_width=0,
                             cursor="", fixed_height=None, fixed_propagate=True,
                             hover_border_color=None, hover_glow_color=None):
        """Crea un'ombra sfocata reale Pillow lungo l'intero perimetro curvo senza angoli spigolosi."""
        cls_pair = getattr(self, "_shadow_cls_pair", None)
        if cls_pair is None:
            cls_pair = self._build_shadow_toolkit()
            self._shadow_cls_pair = cls_pair
        _SmoothShadowShell, _ = cls_pair
        shell = _SmoothShadowShell(
            parent,
            corner_radius=corner_radius,
            offset_x=offset_x,
            offset_y=offset_y,
            surface_fg=(surface_fg if surface_fg is not None else C_BG_CARD),
            border_color=(border_color if border_color is not None else C_BORDER),
            border_width=border_width,
            cursor=cursor,
            fixed_height=fixed_height,
            fixed_propagate=fixed_propagate,
            hover_border_color=hover_border_color,
            hover_glow_color=hover_glow_color,
        )
        self._track_shadow_widget(shell)
        return shell, shell.inner

    def _make_shadow_btn(self, parent, pack_kw=None, offset_x=3, offset_y=4, **btn_kw):
        """Crea un pulsante con angoli curvi anti-alias e ombra morbida sfocata Pillow."""
        cls_pair = getattr(self, "_shadow_cls_pair", None)
        if cls_pair is None:
            cls_pair = self._build_shadow_toolkit()
            self._shadow_cls_pair = cls_pair
        _, _SmoothShadowBtn = cls_pair
        btn = _SmoothShadowBtn(parent, offset_x=offset_x, offset_y=offset_y, **btn_kw)
        self._track_shadow_widget(btn)
        if pack_kw is not None:
            btn.pack(**pack_kw)
        return btn

    def _layout_video_canvas(self, force=False):
        """Centra il canvas video col giusto aspect ratio così le bande laterali/verticali seguono C_VIDEO_LETTERBOX."""
        if not hasattr(self, "video_stage") or not hasattr(self, "video_canvas"):
            return
        try:
            if not self.video_stage.winfo_exists() or not self.video_canvas.winfo_exists():
                return
            sw = self.video_stage.winfo_width()
            sh = self.video_stage.winfo_height()
            if sw <= 10 or sh <= 10:
                return
            if self.is_pip:
                fit_x, fit_y, fit_w, fit_h = 0, 0, sw, sh
            else:
                ar = max(0.5, min(3.5, float(self.video_aspect_ratio or (16.0 / 9.0))))
                stage_ar = float(sw) / float(sh)
                if stage_ar > ar:
                    fit_h = sh
                    fit_w = max(16, int(round(sh * ar)))
                else:
                    fit_w = sw
                    fit_h = max(9, int(round(sw / ar)))
                fit_x = (sw - fit_w) // 2
                fit_y = (sh - fit_h) // 2
            sig = (fit_x, fit_y, fit_w, fit_h)
            if not force and getattr(self, "_last_video_canvas_sig", None) == sig:
                return
            self._last_video_canvas_sig = sig
            self.video_canvas.place_configure(
                anchor="nw", relx=0.0, rely=0.0, relwidth=0.0, relheight=0.0,
                x=fit_x, y=fit_y, width=fit_w, height=fit_h,
            )
        except Exception:
            pass

    def _probe_and_sync_video_aspect(self):
        if self.is_pip or self.is_multiview or not self.vlc_player:
            return
        try:
            vw, vh = self.vlc_player.video_get_size(0)
            if vw > 0 and vh > 0:
                new_ar = float(vw) / float(vh)
                if abs(new_ar - float(self.video_aspect_ratio or 1.7777)) > 0.015:
                    self.video_aspect_ratio = new_ar
                    self._layout_video_canvas()
        except Exception:
            pass

    # =================================================================
    # COSTRUZIONE INTERFACCIA PRINCIPALE
    # =================================================================
    def _build_enterprise_ui(self):
        self.header = ctk.CTkFrame(self, fg_color=C_BG_HEADER, height=62, corner_radius=0, border_width=1, border_color=C_BORDER)
        self.header.pack(side="top", fill="x")
        self.header.pack_propagate(False)

        search_sh, search_container = self._create_shadow_shell(
            self.header, corner_radius=18, offset_x=3, offset_y=4,
            surface_fg=C_BG_INPUT, border_color=C_BORDER, border_width=1, fixed_height=36,
        )
        search_sh.pack(side="left", padx=(12, 6), pady=(3, 3))

        ctk.CTkLabel(
            search_container, text="", image=self._icon_search, width=18,
            fg_color="transparent", bg_color=C_BG_INPUT
        ).pack(side="left", padx=(10, 0))

        self.search_entry = ctk.CTkEntry(
            search_container, placeholder_text="Cerca streamer...",
            fg_color="transparent", bg_color=C_BG_INPUT, border_width=0, width=165, height=28,
            font=ctk.CTkFont("Segoe UI", 12), text_color=C_TEXT_MAIN
        )
        self.search_entry.pack(side="left", padx=(4, 4))
        self.search_entry.bind("<Return>", lambda e: self.perform_streamer_search())

        self._make_shadow_btn(
            search_container,
            pack_kw={"side": "right", "padx": (2, 4), "pady": 2},
            offset_x=2, offset_y=2,
            text=" Cerca", image=self._icon_search_white, compound="left",
            width=72, height=24, corner_radius=12,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.perform_streamer_search
        )

        brand_frame = ctk.CTkFrame(self.header, fg_color="transparent")
        brand_frame.place(relx=0.5, rely=0.5, anchor="center")

        if self.logo_ctk_image:
            ctk.CTkLabel(brand_frame, text="", image=self.logo_ctk_image).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(brand_frame, text="Twixy", font=ctk.CTkFont("Segoe UI", 21, "bold"), text_color=C_TEXT_MAIN).pack(side="left")

        self.mode_var = ctk.StringVar(value=self.config_data.get("stream_mode", "Proxy Luminous (1080p60 No-Ad)"))
        self.engine_var = ctk.StringVar(value=self.config_data.get("player_engine", "VLC (LibVLC)"))

        acct_sh, self.account_pill = self._create_shadow_shell(
            self.header, corner_radius=20, offset_x=3, offset_y=4,
            surface_fg=C_BG_CARD, border_color=C_BORDER, border_width=1, cursor="hand2", fixed_height=38,
        )
        acct_sh.pack(side="right", padx=(6, 12), pady=(2, 3))

        self.account_dot_lbl = ctk.CTkLabel(
            self.account_pill, text="", image=self._icon_user_accent,
            fg_color="transparent", bg_color=C_BG_CARD
        )
        self.account_dot_lbl.pack(side="left", padx=(12, 6), pady=6)

        self.account_name_lbl = ctk.CTkLabel(
            self.account_pill, text="Accedi", font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color=C_TEXT_MAIN, fg_color="transparent", bg_color=C_BG_CARD
        )
        self.account_name_lbl.pack(side="left", padx=(0, 6), pady=6)

        self.account_notif_dot = ctk.CTkLabel(
            self.account_pill, text="", font=ctk.CTkFont("Segoe UI", 10, "bold"),
            fg_color=C_ACCENT, bg_color=C_BG_CARD, text_color="#ffffff", corner_radius=8, padx=6
        )

        self.account_arrow_lbl = ctk.CTkLabel(
            self.account_pill, text="", image=self._icon_chev_down,
            fg_color="transparent", bg_color=C_BG_CARD
        )
        self.account_arrow_lbl.pack(side="right", padx=(4, 12), pady=6)

        self._acct_hover = False
        self._acct_hover_after = None

        def _set_acct_hover(hovered):
            if self._acct_hover == hovered:
                return
            self._acct_hover = hovered
            bg_c = C_BG_CARD_HOVER if hovered else C_BG_CARD
            bd_c = C_ACCENT if hovered else C_BORDER
            self.account_pill.configure(fg_color=bg_c, border_color=bd_c)
            for lbl in (self.account_dot_lbl, self.account_name_lbl, self.account_notif_dot, self.account_arrow_lbl):
                try:
                    if lbl.winfo_exists():
                        lbl.configure(bg_color=bg_c)
                except Exception:
                    pass

        def _check_acct_leave():
            self._acct_hover_after = None
            try:
                px, py = self.winfo_pointerxy()
                hit = self.winfo_containing(px, py)
                cur = hit
                while cur is not None:
                    if cur in (acct_sh, self.account_pill):
                        return
                    if cur == self:
                        break
                    cur = getattr(cur, "master", None)
            except Exception:
                pass
            _set_acct_hover(False)

        def _on_acct_enter(_e=None):
            if self._acct_hover_after is not None:
                try:
                    self.after_cancel(self._acct_hover_after)
                except Exception:
                    pass
                self._acct_hover_after = None
            _set_acct_hover(True)

        def _on_acct_leave(_e=None):
            if self._acct_hover_after is not None:
                try:
                    self.after_cancel(self._acct_hover_after)
                except Exception:
                    pass
            self._acct_hover_after = self.after(25, _check_acct_leave)

        for w in (acct_sh, self.account_pill, self.account_dot_lbl, self.account_name_lbl, self.account_notif_dot, self.account_arrow_lbl):
            w.bind("<Button-1>", lambda e: self.toggle_account_menu(), add="+")
            w.bind("<Enter>", _on_acct_enter, add="+")
            w.bind("<Leave>", _on_acct_leave, add="+")

        self.login_btn = self.account_name_lbl
        self._update_login_badge()

        # ---------------- 2. MAIN WORKSPACE ----------------
        self.workspace = ctk.CTkFrame(self, fg_color=C_BG_ROOT, corner_radius=0)
        self.workspace.pack(side="top", fill="both", expand=True)

        self.left_sidebar = ctk.CTkFrame(self.workspace, fg_color=C_BG_SIDEBAR, width=440, corner_radius=0, border_width=1, border_color=C_BORDER)
        self.left_sidebar.pack(side="left", fill="y")
        self.left_sidebar.pack_propagate(False)

        self.nav_var = ctk.StringVar(value="Preferiti")
        nav_sh, self.nav_bar = self._create_shadow_shell(
            self.left_sidebar, corner_radius=10, offset_x=3, offset_y=4,
            surface_fg=C_BG_INPUT, border_width=0, fixed_height=40, fixed_propagate=False,
        )
        nav_sh.pack(fill="x", padx=10, pady=(8, 4))

        self._nav_tab_btns = {}
        for tab_lbl in ("Preferiti", "Seguiti", "Cerca", "VOD"):
            tb = ctk.CTkButton(
                self.nav_bar,
                text=tab_lbl,
                width=58,
                height=32,
                corner_radius=8,
                fg_color="transparent",
                bg_color=C_BG_INPUT,
                hover_color=C_BG_CARD_HOVER,
                text_color=C_TEXT_MAIN,
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda t=tab_lbl: self._on_nav_tab_click(t),
            )
            tb.pack(side="left", fill="both", expand=True, padx=2, pady=4)
            self._nav_tab_btns[tab_lbl] = tb

        self.multiview_btn = ctk.CTkButton(
            self.nav_bar,
            text="Multi-Live",
            image=self._icon_multiview_idle,
            compound="left",
            width=96,
            height=32,
            corner_radius=8,
            fg_color="transparent",
            bg_color=C_BG_INPUT,
            hover_color=C_ACCENT_HOVER,
            text_color=C_TEXT_MAIN,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.toggle_multiview_mode,
        )
        self.multiview_btn.pack(side="left", fill="both", expand=True, padx=(2, 3), pady=4)
        self._nav_tab_btns["Multi-Live"] = self.multiview_btn

        self.side_toolbar = ctk.CTkFrame(self.left_sidebar, fg_color="transparent", height=34)
        self.side_toolbar.pack(fill="x", padx=14, pady=(2, 6))

        ctk.CTkLabel(
            self.side_toolbar, text="●", font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color=C_ACCENT, fg_color="transparent"
        ).pack(side="left", padx=(0, 6))

        self.side_title_lbl = ctk.CTkLabel(
            self.side_toolbar, text="Live", font=ctk.CTkFont("Segoe UI", 15, "bold"),
            text_color=C_TEXT_MAIN
        )
        self.side_title_lbl.pack(side="left")

        self.sort_btn = self._make_shadow_btn(
            self.side_toolbar,
            pack_kw={"side": "right", "padx": (4, 0)},
            offset_x=2, offset_y=2,
            text=" Ordina", image=self._icon_sort, compound="left",
            width=92, height=30, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._open_sort_menu
        )
        self._bind_tooltip(self.sort_btn, "Ordina la lista degli streamer")

        self._refresh_list_btn = self._make_shadow_btn(
            self.side_toolbar,
            pack_kw={"side": "right", "padx": 3},
            offset_x=2, offset_y=2,
            text="", image=self._icon_refresh, width=30, height=30, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            command=self.refresh_all_lists
        )
        self._bind_tooltip(self._refresh_list_btn, "Aggiorna liste")

        self.add_fav_btn = self._make_shadow_btn(
            self.side_toolbar,
            pack_kw={"side": "right", "padx": 3},
            offset_x=2, offset_y=2,
            text="", image=self._icon_plus, width=30, height=30, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            command=self.prompt_add_favorite
        )
        self._bind_tooltip(self.add_fav_btn, "Aggiungi streamer ai Preferiti")
        self._refresh_nav_tab_styles()

        self.sidebar_body = ctk.CTkFrame(self.left_sidebar, fg_color="transparent", corner_radius=0)
        self.sidebar_body.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self.cards_scroll = ctk.CTkScrollableFrame(self.sidebar_body, fg_color=C_BG_SIDEBAR, corner_radius=0)
        self.cards_scroll.pack(fill="both", expand=True)

        self.sidebar_lock_frame = ctk.CTkFrame(self.sidebar_body, fg_color=C_BG_SIDEBAR, corner_radius=0)
        self.sidebar_lock_lbl = ctk.CTkLabel(
            self.sidebar_lock_frame, text="⏳ Preparazione lista in corso...",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=C_GOLD
        )
        self.sidebar_lock_lbl.place(relx=0.5, rely=0.45, anchor="center")

        self.bind_all("<MouseWheel>", self._on_global_mousewheel, add="+")
        self.bind_all("<Button-1>", self._on_root_click_bubble, add="+")

        self.fav_data = []
        self.followed_data = []
        self.search_data = []
        self.vods_data = []
        self.vods_channel_name = ""

        # RIGHT SIDEBAR (Chat IRC + Sondaggi + Punti Canale + Drops)
        self.right_sidebar = ctk.CTkFrame(self.workspace, fg_color=C_CHAT_BG, width=345, corner_radius=0, border_width=1, border_color=C_BORDER)
        self.right_sidebar.pack(side="right", fill="y")
        self.right_sidebar.pack_propagate(False)
        self._build_chat_sidebar()

        # DRAWER INTERNO UNIFICATO (Account/Login, Notifiche, Drop, Impostazioni)
        self._build_inapp_menu_drawer()

        # CENTER STAGE (Single Video Canvas + Multi-Live Grid Container)
        self.center_stage = ctk.CTkFrame(self.workspace, fg_color=C_VIDEO_LETTERBOX, corner_radius=0)
        self.center_stage.pack(side="left", fill="both", expand=True)

        self.video_stage = ctk.CTkFrame(self.center_stage, fg_color=C_VIDEO_LETTERBOX, corner_radius=0)
        self.video_stage.pack(side="top", fill="both", expand=True)
        self.video_stage.bind("<Configure>", lambda _e: self._layout_video_canvas(), add="+")
        self.video_stage.bind("<Double-Button-1>", lambda e: self.toggle_fullscreen(), add="+")

        self.video_canvas = tk.Canvas(self.video_stage, bg=_tk_color(C_VIDEO_LETTERBOX), highlightthickness=0, bd=0)
        self.video_canvas.place(anchor="nw", x=0, y=0, width=640, height=360)
        self.video_canvas.bind("<Double-Button-1>", lambda e: self.toggle_fullscreen())
        self.video_canvas.bind("<Configure>", self._on_video_canvas_configure)

        self._build_multiview_container()

        # Bottom Control & Telemetry Deck
        self.deck = ctk.CTkFrame(self.center_stage, fg_color=C_BG_HEADER, height=98, corner_radius=0, border_width=1, border_color=C_BORDER)
        self.deck.pack(side="bottom", fill="x")
        self.deck.pack_propagate(False)

        seek_row = ctk.CTkFrame(self.deck, fg_color="transparent", height=32)
        seek_row.pack(fill="x", padx=14, pady=(6, 0))

        self.badge_live_lbl = ctk.CTkLabel(
            seek_row, text=" ● READY ", fg_color=C_BG_CARD, text_color=C_TEXT_DIM,
            corner_radius=6, font=ctk.CTkFont("Consolas", 11, "bold")
        )
        self.badge_live_lbl.pack(side="left", padx=(0, 8))

        self.deck_fs_btn = self._make_shadow_btn(
            seek_row,
            pack_kw={"side": "right", "padx": (3, 0)},
            offset_x=2, offset_y=2,
            text="", image=self._icon_fullscreen, width=34, height=28, corner_radius=7,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            command=self.toggle_fullscreen
        )
        self._bind_tooltip(self.deck_fs_btn, "Schermo Intero")

        self.deck_theater_btn = self._make_shadow_btn(
            seek_row,
            pack_kw={"side": "right", "padx": 3},
            offset_x=2, offset_y=2,
            text=" Teatro", image=self._icon_theater, compound="left",
            width=72, height=28, corner_radius=7,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self.toggle_theater_mode
        )
        self._bind_tooltip(self.deck_theater_btn, "Modalità Teatro")

        self.deck_chat_btn = self._make_shadow_btn(
            seek_row,
            pack_kw={"side": "right", "padx": 3},
            offset_x=2, offset_y=2,
            text="", image=self._icon_chat, width=34, height=28, corner_radius=7,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            command=self.toggle_chat
        )
        self._bind_tooltip(self.deck_chat_btn, "Mostra / Nascondi Chat")

        self.deck_pip_btn = self._make_shadow_btn(
            seek_row,
            pack_kw={"side": "right", "padx": 3},
            offset_x=2, offset_y=2,
            text=" PiP", image=self._icon_pip, compound="left",
            width=54, height=28, corner_radius=7,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self.toggle_pip_mode
        )
        self._bind_tooltip(self.deck_pip_btn, "Picture-in-Picture (PiP)")

        self.time_lbl = ctk.CTkLabel(seek_row, text="00:00:00", font=ctk.CTkFont("Consolas", 11), text_color=C_TEXT_DIM)
        self.time_lbl.pack(side="right", padx=(6, 8))

        self.seek_slider = ctk.CTkSlider(
            seek_row, from_=0, to=1000, number_of_steps=1000, height=14,
            fg_color=C_BG_INPUT, progress_color=C_ACCENT,
            button_color=("#7c3aed", "#ffffff"), button_hover_color=C_ACCENT_HOVER,
            command=self.on_seek_drag
        )
        self.seek_slider.set(0)
        self.seek_slider.pack(side="left", fill="x", expand=True, padx=4)
        self.seek_slider.bind("<ButtonPress-1>", lambda e: setattr(self, "seeking_drag", True))
        self.seek_slider.bind("<ButtonRelease-1>", self.on_seek_release)

        ctrl_row = ctk.CTkFrame(self.deck, fg_color="transparent")
        ctrl_row.pack(fill="both", expand=True, padx=14, pady=(2, 6))
        self.deck_ctrl_row = ctrl_row

        self.play_btn = self._make_shadow_btn(
            ctrl_row,
            pack_kw={"side": "left", "padx": (0, 4)},
            offset_x=2, offset_y=2,
            text=" Pausa", image=self._icon_pause, compound="left",
            width=82, height=30, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.toggle_pause
        )

        self.seek_back_btn = self._make_shadow_btn(
            ctrl_row,
            pack_kw=None,
            offset_x=2, offset_y=2,
            text=" -10s", image=self._icon_skip_back, compound="left",
            width=68, height=30, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self.seek_relative(-10)
        )

        self.seek_fwd_btn = self._make_shadow_btn(
            ctrl_row,
            pack_kw=None,
            offset_x=2, offset_y=3,
            text="+30s ", image=self._icon_skip_fwd, compound="right",
            width=68, height=28, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: self.seek_relative(30)
        )

        self.clip_btn = self._make_shadow_btn(
            ctrl_row,
            pack_kw={"side": "left", "padx": (4, 0)},
            offset_x=3, offset_y=4,
            text=" Clip", image=self._icon_clip, compound="left",
            width=74, height=28, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.open_clip_dialog
        )
        self._bind_tooltip(self.clip_btn, "Crea Clip (ultimi 30s o fino a 2+ minuti)")

        self.stream_meta_lbl = ctk.CTkLabel(
            ctrl_row, text="Seleziona uno streamer o cerca un canale per iniziare (1080p60 Zero-Ads)",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=C_TEXT_MAIN, anchor="w"
        )
        self.stream_meta_lbl.pack(side="left", fill="x", expand=True, padx=12)

        self.vol_pct_lbl = ctk.CTkLabel(
            ctrl_row, text=f" {self.config_data.get('volume', 80)}%",
            image=self._icon_volume, compound="left",
            font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_DIM, width=58
        )
        self.vol_pct_lbl.pack(side="right", padx=(4, 0))

        self.vol_slider = ctk.CTkSlider(
            ctrl_row, from_=0, to=100, width=105, height=14,
            fg_color=C_BG_INPUT, progress_color=C_GREEN,
            button_color=("#059669", "#ffffff"), button_hover_color=C_GREEN,
            command=self.on_volume_change
        )
        self.vol_slider.set(self.config_data.get("volume", 80))
        self.vol_slider.pack(side="right", padx=4)

        self.drops_live_badge = self._make_shadow_btn(
            ctrl_row,
            pack_kw=None,
            offset_x=2, offset_y=2,
            text=" Drops Attivi", image=self._icon_gift, compound="left",
            height=26, corner_radius=7,
            fg_color=("#E0F2FE", "#102a43"), hover_color=C_ACCENT,
            text_color=("#0369A1", "#38bdf8"), border_width=1, border_color=C_CYAN,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=lambda: self.open_drops_dialog(highlight_active=True)
        )
        self._bind_tooltip(self.drops_live_badge, "Questa live è idonea ai Twitch Drops! Clicca per aprire i progressi.")

        self.shield_badge = ctk.CTkLabel(
            ctrl_row, text=" 0 Ads • Ready", image=self._icon_shield, compound="left",
            fg_color=("#D1FAE5", "#132a20"), text_color=C_GREEN,
            corner_radius=6, font=ctk.CTkFont("Segoe UI", 10, "bold"), padx=8, pady=2
        )
        self.shield_badge.pack(side="right", padx=6)

        self.quality_var = ctk.StringVar(value="1080p60 (Source)")
        self.quality_menu = ctk.CTkOptionMenu(
            ctrl_row, variable=self.quality_var, width=128, height=28, corner_radius=8,
            fg_color=C_BG_CARD, button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER,
            text_color=C_TEXT_MAIN,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            values=["1080p60 (Source)"],
            command=self.on_quality_changed
        )
        self.quality_menu.pack(side="right", padx=(4, 4))
        self._update_deck_toggle_styles()

    def _build_chat_sidebar(self):
        # Header Chat con pulsante Pulisci
        chat_hdr = ctk.CTkFrame(self.right_sidebar, fg_color=C_BG_HEADER, height=44, corner_radius=0)
        chat_hdr.pack(fill="x")
        chat_hdr.pack_propagate(False)
        self.chat_hdr = chat_hdr

        self.chat_header_lbl = ctk.CTkLabel(chat_hdr, text=" CHAT", image=self._icon_chat, compound="left", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_MAIN)
        self.chat_header_lbl.pack(side="left", padx=10)

        self._make_shadow_btn(
            chat_hdr,
            pack_kw={"side": "right", "padx": (2, 8)},
            offset_x=2, offset_y=2,
            text="Pulisci", width=48, height=24, corner_radius=6,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10),
            command=self.clear_chat
        )

        # Barra Switcher Chat Multi-Live sopra la chat (attiva sia in finestra normale che in Schermo Intero)
        self.mv_chat_switcher = ctk.CTkFrame(
            self.right_sidebar, fg_color=C_BG_HEADER, corner_radius=0,
            border_width=1, border_color=C_BORDER
        )

        # Banner Dinamico Sondaggi (Polls) e Bet (Predictions) in cima alla Chat
        self.poll_banner = ctk.CTkFrame(self.right_sidebar, fg_color=("#EDE9FE", "#1e1b4b"), corner_radius=8, border_width=1, border_color=C_ACCENT)
        self.poll_title_lbl = ctk.CTkLabel(self.poll_banner, text="📊 SONDAGGIO IN CORSO", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_GOLD, anchor="w", justify="left", wraplength=305)
        self.poll_title_lbl.pack(fill="x", padx=8, pady=(6, 2))
        self.poll_choices_lbl = ctk.CTkLabel(self.poll_banner, text="", font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_MAIN, justify="left", anchor="w", wraplength=305)
        self.poll_choices_lbl.pack(fill="x", padx=8, pady=(0, 4))
        self.poll_vote_row = ctk.CTkFrame(self.poll_banner, fg_color="transparent")

        self.bet_banner = ctk.CTkFrame(self.right_sidebar, fg_color=("#EFF6FF", "#16192c"), corner_radius=8, border_width=1, border_color=("#3b82f6", "#8b5cf6"))
        self.bet_title_lbl = ctk.CTkLabel(self.bet_banner, text="🔮 BET IN CORSO", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=("#2563eb", "#38bdf8"), anchor="w", justify="left", wraplength=305)
        self.bet_title_lbl.pack(fill="x", padx=8, pady=(6, 2))
        self.bet_choices_lbl = ctk.CTkLabel(self.bet_banner, text="", font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_MAIN, justify="left", anchor="w", wraplength=305)
        self.bet_choices_lbl.pack(fill="x", padx=8, pady=(0, 4))
        self.bet_action_row = ctk.CTkFrame(self.bet_banner, fg_color="transparent")
        self._bet_stake_val = 50
        self._announced_poll_sig = None
        self._announced_pred_sig = None
        self._last_poll_render_sig = None
        self._last_pred_render_sig = None
        self._voted_poll_ids = set()
        self._bet_event_ids = set()

        # Box Messaggi Chat
        self.chat_box = tk.Text(
            self.right_sidebar, bg=_tk_color(C_CHAT_BG), fg=_tk_color(C_TEXT_MAIN), relief=tk.FLAT,
            font=("Segoe UI", 10), wrap=tk.WORD, state=tk.DISABLED, padx=10, pady=8,
            highlightthickness=0, bd=0
        )
        self.chat_box.pack(fill="both", expand=True, padx=2, pady=2)

        # Barra Punti Canale & Ricompense (stile Twitch ufficiale sotto la chat)
        self.points_bar = ctk.CTkFrame(self.right_sidebar, fg_color=C_BG_CARD, height=44, corner_radius=0, border_width=1, border_color=C_BORDER)
        self.points_bar.pack(fill="x", side="bottom")
        self.points_bar.pack_propagate(False)

        self.points_btn = self._make_shadow_btn(
            self.points_bar,
            pack_kw={"side": "left", "fill": "x", "expand": True, "padx": 8, "pady": 4},
            offset_x=3, offset_y=4,
            text=" Punti: -- (Ricompense)", image=self._icon_coins, compound="left",
            height=26, corner_radius=6,
            fg_color=C_BG_INPUT, hover_color=C_ACCENT, text_color=C_GOLD,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.open_channel_points_dialog
        )

        # Input Invio Messaggio Chat
        chat_bottom = ctk.CTkFrame(self.right_sidebar, fg_color=C_BG_HEADER, height=52, corner_radius=0)
        chat_bottom.pack(fill="x", side="bottom")
        chat_bottom.pack_propagate(False)

        self.chat_entry = ctk.CTkEntry(
            chat_bottom, placeholder_text="Invia un messaggio in chat...",
            fg_color=C_BG_INPUT, border_width=1, border_color=C_BORDER,
            text_color=C_TEXT_MAIN, height=32,
            font=ctk.CTkFont("Segoe UI", 11)
        )
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(8, 4), pady=7)
        self.chat_entry.bind("<Return>", lambda e: self.send_chat())

        self._make_shadow_btn(
            chat_bottom,
            pack_kw={"side": "left", "padx": (0, 4), "pady": 6},
            offset_x=2, offset_y=2,
            text="", image=self._icon_emote, width=32, height=32, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            command=self.open_emote_picker
        )

        self._make_shadow_btn(
            chat_bottom,
            pack_kw={"side": "right", "padx": (2, 8), "pady": 6},
            offset_x=2, offset_y=2,
            text=" Invia", image=self._icon_send_white, compound="left",
            width=72, height=32, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.send_chat
        )

    # =================================================================
    # WORKER BACKGROUND: HEARTBEAT MINUTE-WATCHED, DROPS, PUNTI E SONDAGGI
    # =================================================================
    def _push_local_notification(self, kind, message, channel="", image_url=""):
        ts_str = time.strftime("%H:%M:%S")
        entry = {
            "id": uuid.uuid4().hex[:10],
            "kind": kind,
            "message": message,
            "channel": channel or "",
            "image_url": image_url or "",
            "created_at": ts_str,
            "unread": True,
        }
        self.local_notifications.insert(0, entry)
        if len(self.local_notifications) > 80:
            self.local_notifications = self.local_notifications[:80]
        self.unread_notif_count += 1
        self._safe_ui(self._update_notif_badge_ui)

    def _update_notif_badge_ui(self):
        if not self.app_running or not hasattr(self, "account_notif_dot"):
            return
        total_unseen = int(self.unread_notif_count or 0) + int(self.remote_unseen_notif or 0)
        try:
            if total_unseen > 0:
                self.account_notif_dot.configure(text=str(min(99, total_unseen)))
                self.account_notif_dot.pack(side="left", padx=(2, 2), pady=4, before=self.account_arrow_lbl)
            else:
                self.account_notif_dot.pack_forget()
        except Exception:
            pass

    def _background_drops_and_points_worker(self):
        """
        Gira in background senza mai toccare il Main Thread:
        1. Ogni 20s aggiorna Punti Canale, riscatta in automatico i bauli +50 punti e aggiorna i Sondaggi in chat.
        2. Ogni 60s invia il pacchetto 'minute-watched' a Spade su tutte le live attive (Singola o Multi-Live).
        3. Aggiorna i Twitch Drops in tempo reale (ogni 15s a finestra Drop aperta / subito dopo heartbeat, o 45s in background)
           e riscatta automaticamente quelli arrivati al 100%, registrandoli nelle Notifiche.
        """
        last_heartbeat = 0
        last_drops_check = 0
        last_notif_check = 0
        last_full_ctx_check = 0
        last_poll_pred_check = 0
        force_drops_sync_at = 0

        while self.app_running:
            time.sleep(3)
            active_multiview = bool(self.is_multiview and self.multi_tiles)
            watching_live = active_multiview or (bool(self.current_channel) and not self.is_playing_vod and not self.is_paused)
            on_live_channel = bool(self.current_channel) and not self.is_playing_vod
            now = time.time()

            # Controllo leggero notifiche Twitch non lette ogni 90s (anche senza stream)
            if self.engine.oauth_token and (now - last_notif_check >= 90):
                last_notif_check = now
                try:
                    n_res = self.engine.fetch_notifications(limit=15)
                    self.remote_unseen_notif = int(n_res.get("unseen_count") or 0)
                    self._safe_ui(self._update_notif_badge_ui)
                except Exception:
                    pass

            # Aggiornamento rapido Sondaggi e Bet (ogni ~6s finché si è su un canale live, anche in pausa)
            if on_live_channel and (now - last_poll_pred_check >= 6):
                last_poll_pred_check = now
                try:
                    pp = self.engine.fetch_channel_polls_and_predictions(self.current_channel)
                    if isinstance(pp, dict):
                        if not isinstance(self.current_live_context, dict):
                            self.current_live_context = {}
                        self.current_live_context["active_poll"] = pp.get("active_poll")
                        self.current_live_context["active_prediction"] = pp.get("active_prediction")
                        self._safe_ui(self._update_points_and_poll_ui)
                except Exception:
                    pass

            if not watching_live:
                # Se la finestra Drops è aperta e l'utente è loggato, aggiorna comunque ogni 20s
                if self._drops_dialog_open and self.engine.oauth_token and (now - last_drops_check >= 20):
                    last_drops_check = now
                    try:
                        drops_list, claimable = self.engine.fetch_drops_inventory_and_campaigns("")
                        self.current_drops_list = drops_list
                        self._safe_ui(self._update_drops_badge_ui)
                        cb_rt = self._drops_realtime_cb
                        if cb_rt:
                            self._safe_ui(cb_rt)
                    except Exception:
                        pass
                continue

            # 1. Aggiorna Contesto Canale focus (punti, bauli +50, ricompense, drop) ogni ~15s
            if self.current_channel and (now - last_full_ctx_check >= 15):
                last_full_ctx_check = now
                last_poll_pred_check = now
                try:
                    ctx = self.engine.fetch_channel_live_context(self.current_channel)
                    if ctx:
                        self.current_live_context = ctx
                        claim_id = ctx.get("claim_id")
                        ch_id = ctx.get("channel_id")
                        if claim_id and ch_id and self.engine.oauth_token and self.config_data.get("auto_claim_points", True):
                            if self.engine.claim_community_points_bonus(ch_id, claim_id):
                                self.chat._enqueue("🪙 BONUS", "+50 Punti Canale riscattati automaticamente!", C_GOLD)
                                self._push_local_notification("points", "+50 Punti Canale riscattati automaticamente", channel=self.current_channel)
                                if ctx.get("points_balance") is not None:
                                    ctx["points_balance"] += 50
                        self._safe_ui(self._update_points_and_poll_ui)
                except Exception:
                    pass

            # 2. Invia Heartbeat 'minute-watched' ogni ~58 secondi (Singola o Multi-Live)
            if now - last_heartbeat >= 58:
                targets = []
                if active_multiview:
                    for tile in list(self.multi_tiles):
                        t_ch = tile.get("channel")
                        if not t_ch:
                            continue
                        t_ctx = tile.get("live_ctx") or {}
                        if not t_ctx.get("channel_id"):
                            try:
                                t_ctx = self.engine.fetch_channel_live_context(t_ch) or {}
                                tile["live_ctx"] = t_ctx
                            except Exception:
                                t_ctx = {}
                        targets.append((
                            t_ch,
                            t_ctx.get("channel_id"),
                            t_ctx.get("broadcast_id"),
                            t_ctx.get("game_name") or (tile.get("stream_info") or {}).get("game", ""),
                            t_ctx.get("claim_id"),
                        ))
                elif self.current_channel:
                    targets.append((
                        self.current_channel,
                        self.current_live_context.get("channel_id"),
                        self.current_live_context.get("broadcast_id"),
                        self.current_live_context.get("game_name") or self.current_stream_info.get("game", ""),
                        None,
                    ))

                hb_sent = False
                for t_ch, ch_id, b_id, g_name, extra_claim in targets:
                    if extra_claim and ch_id and t_ch != self.current_channel and self.engine.oauth_token and self.config_data.get("auto_claim_points", True):
                        try:
                            if self.engine.claim_community_points_bonus(ch_id, extra_claim):
                                self._push_local_notification("points", f"+50 Punti su #{t_ch}", channel=t_ch)
                        except Exception:
                            pass
                    if ch_id and b_id:
                        self.engine.send_minute_watched_heartbeat(t_ch, ch_id, b_id, g_name)
                        hb_sent = True

                if hb_sent:
                    last_heartbeat = now
                    self._last_heartbeat_ts = now
                    # Forza una sincronizzazione Drop 4 secondi dopo il segnale minute-watched per aggiornamento quasi istantaneo
                    force_drops_sync_at = now + 4.0

            # 3. Controlla progresso Twitch Drops in tempo reale (15s se finestra aperta, 4s post-heartbeat, altrimenti 45s)
            drops_interval = 15 if self._drops_dialog_open else 45
            should_check_drops = (now - last_drops_check >= drops_interval) or (force_drops_sync_at and now >= force_drops_sync_at)
            if self.engine.oauth_token and should_check_drops:
                last_drops_check = now
                force_drops_sync_at = 0
                try:
                    g_name = self.current_live_context.get("game_name") or self.current_stream_info.get("game", "")
                    drops_list, claimable = self.engine.fetch_drops_inventory_and_campaigns(g_name)
                    self.current_drops_list = drops_list

                    if self.config_data.get("auto_claim_drops", True):
                        for d_inst_id, r_name in claimable:
                            if self.engine.claim_drop_reward(d_inst_id):
                                self.chat._enqueue("🎁 DROP RISCATTATO", f"Hai ottenuto automaticamente: {r_name}!", C_CYAN)
                                self._push_local_notification("drop_claimed", f"Drop sbloccato e riscattato: {r_name}", channel=self.current_channel)

                    self._safe_ui(self._update_drops_badge_ui)
                    cb_rt = self._drops_realtime_cb
                    if cb_rt:
                        self._safe_ui(cb_rt)
                except Exception:
                    pass

    def _fmt_compact_num(self, n):
        n = int(n or 0)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1_000:.1f}K"
        return str(n)

    def _submit_poll_vote_async(self, poll_id, choice_id, choice_title):
        if poll_id in self._voted_poll_ids:
            return
        self._voted_poll_ids.add(poll_id)
        self._last_poll_render_sig = None
        self._update_points_and_poll_ui()

        def _w():
            ok, msg = self.engine.cast_poll_vote(poll_id, choice_id)
            if ok:
                self.chat._enqueue("📊 VOTO", f"Hai votato: {choice_title}", C_GOLD)
            else:
                self._voted_poll_ids.discard(poll_id)
                self._last_poll_render_sig = None
                self.chat._enqueue("⚠️ SONDAGGIO", msg, C_TEXT_DIM)
                self._safe_ui(self._update_points_and_poll_ui)

        threading.Thread(target=_w, daemon=True).start()

    def _submit_prediction_bet_async(self, event_id, outcome_id, outcome_title, points):
        if event_id in self._bet_event_ids:
            return
        self._bet_event_ids.add(event_id)
        self._last_pred_render_sig = None
        self._update_points_and_poll_ui()

        def _w():
            ok, msg = self.engine.place_prediction_bet(event_id, outcome_id, points)
            if ok:
                self.chat._enqueue("🔮 BET PIAZZATA", f"{self._fmt_compact_num(points)} pt su '{outcome_title}'", C_CYAN)
            else:
                self._bet_event_ids.discard(event_id)
                self._last_pred_render_sig = None
                self.chat._enqueue("⚠️ BET", msg, C_TEXT_DIM)
                self._safe_ui(self._update_points_and_poll_ui)

        threading.Thread(target=_w, daemon=True).start()

    def _update_points_and_poll_ui(self):
        if not self.app_running or self.state() == "iconic":
            return
        ctx = self.current_live_context or {}
        bal = ctx.get("points_balance")
        p_name = ctx.get("points_name") or "Punti"
        rw_count = len(ctx.get("rewards") or [])

        if bal is not None:
            bal_str = f"{bal:,}".replace(",", ".")
            self.points_btn.configure(text=f" {bal_str} {p_name}  •  {rw_count} Ricompense")
        elif self.engine.oauth_token:
            self.points_btn.configure(text=f" {p_name}  •  {rw_count} Ricompense")
        else:
            self.points_btn.configure(text=" Accedi per vedere i tuoi Punti Canale")

        # 1. Aggiorna Banner Sondaggio (Poll) in cima alla chat
        poll = ctx.get("active_poll")
        if poll and poll.get("status") in ("ACTIVE", "COMPLETED"):
            p_id = str(poll.get("id") or "")
            p_st = str(poll.get("status") or "")
            p_title = str(poll.get("title") or "")
            rem_sec = max(0, int((poll.get("remainingDurationMilliseconds") or 0) / 1000))
            status_tag = f"({rem_sec}s)" if p_st == "ACTIVE" else "(Concluso)"
            self.poll_title_lbl.configure(text=f"📊 SONDAGGIO {status_tag}: {p_title}")

            total_v = int(poll.get("totalVoters") or poll.get("TotalVoters") or 0)
            choices = list(poll.get("choices") or [])
            lines = []
            for idx, ch_opt in enumerate(choices, 1):
                v = int(ch_opt.get("totalVoters") or 0)
                pct = int(round(v * 100.0 / total_v)) if total_v > 0 else 0
                lines.append(f"{idx}. {ch_opt.get('title')}: {pct}% ({v} voti)")
            self.poll_choices_lbl.configure(text="\n".join(lines))

            can_vote = bool(self.engine.oauth_token and p_st == "ACTIVE" and p_id not in self._voted_poll_ids and choices)
            poll_btn_sig = (p_id, p_st, p_id in self._voted_poll_ids, bool(self.engine.oauth_token), tuple(c.get("id") for c in choices))
            if poll_btn_sig != self._last_poll_render_sig:
                self._last_poll_render_sig = poll_btn_sig
                for w in self.poll_vote_row.winfo_children():
                    w.destroy()
                if can_vote:
                    for idx, ch_opt in enumerate(choices[:4], 1):
                        cid = str(ch_opt.get("id") or "")
                        ctitle = str(ch_opt.get("title") or f"Opz {idx}")
                        short_c = ctitle if len(ctitle) <= 10 else ctitle[:9] + "…"
                        ctk.CTkButton(
                            self.poll_vote_row, text=f"{idx}. {short_c}", height=22, width=62, corner_radius=6,
                            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
                            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 9, "bold"),
                            command=lambda pid=p_id, ch_id=cid, ct=ctitle: self._submit_poll_vote_async(pid, ch_id, ct),
                        ).pack(side="left", padx=(0, 4), pady=2)
                    self.poll_vote_row.pack(fill="x", padx=8, pady=(0, 6))
                elif p_id in self._voted_poll_ids and p_st == "ACTIVE":
                    ctk.CTkLabel(
                        self.poll_vote_row, text="✓ Voto inviato", font=ctk.CTkFont("Segoe UI", 9, "bold"),
                        text_color=C_GREEN, anchor="w", height=18,
                    ).pack(side="left")
                    self.poll_vote_row.pack(fill="x", padx=8, pady=(0, 5))
                else:
                    self.poll_vote_row.pack_forget()

            p_ann = (p_id, p_st)
            if p_id and p_ann != self._announced_poll_sig:
                self._announced_poll_sig = p_ann
                if p_st == "ACTIVE":
                    opts_s = " | ".join(str(c.get("title") or "") for c in choices[:4])
                    self.chat._enqueue("📊 SONDAGGIO", f"{p_title} — [{opts_s}]", C_GOLD)

            if not self.poll_banner.winfo_manager():
                self.poll_banner.pack(fill="x", padx=6, pady=(4, 2), before=self.chat_box)
        else:
            if self.poll_banner.winfo_manager():
                self.poll_banner.pack_forget()

        # 2. Aggiorna Banner Bet / Pronostico (Prediction) in cima alla chat
        pred = ctx.get("active_prediction")
        if pred and pred.get("status") in ("ACTIVE", "LOCKED", "RESOLVE_PENDING", "RESOLVED"):
            ev_id = str(pred.get("id") or "")
            ev_st = str(pred.get("status") or "")
            ev_title = str(pred.get("title") or "Pronostico")
            win_id = str(((pred.get("winningOutcome") or {}).get("id")) or "")
            outcomes = list(pred.get("outcomes") or [])
            pool_pts = sum(int(o.get("totalPoints") or 0) for o in outcomes)

            rem_txt = ""
            if ev_st == "ACTIVE" and pred.get("createdAt") and pred.get("predictionWindowSeconds"):
                try:
                    import datetime as _dt
                    dt_c = _dt.datetime.fromisoformat(str(pred["createdAt"]).replace("Z", "+00:00"))
                    rem_s = max(0, int(int(pred["predictionWindowSeconds"]) - (_dt.datetime.now(_dt.timezone.utc) - dt_c).total_seconds()))
                    mm, ss = divmod(rem_s, 60)
                    rem_txt = f" ({mm}:{ss:02d})" if mm else f" ({ss}s)"
                except Exception:
                    pass

            if ev_st == "ACTIVE":
                hdr_st = f"🔮 BET APERTA{rem_txt}"
            elif ev_st in ("LOCKED", "RESOLVE_PENDING"):
                hdr_st = "🔒 BET BLOCCATA (in attesa esito)"
            else:
                hdr_st = "🏆 RISULTATO BET"
            self.bet_title_lbl.configure(text=f"{hdr_st}: {ev_title}")

            out_lines = []
            for o in outcomes:
                col_name = str(o.get("color") or "").upper()
                dot = "🔵" if col_name == "BLUE" else ("🔴" if col_name == "PINK" else "🟣")
                pts = int(o.get("totalPoints") or 0)
                users = int(o.get("totalUsers") or 0)
                pct = int(round(pts * 100.0 / pool_pts)) if pool_pts > 0 else 0
                odds = f" • 1:{(pool_pts / pts):.1f}" if pts > 0 and pool_pts > pts else ""
                win_mark = "  ✅ VINCE" if (ev_st == "RESOLVED" and str(o.get("id") or "") == win_id) else ""
                out_lines.append(f"{dot} {o.get('title')}: {pct}% ({self._fmt_compact_num(pts)} pt • {users}{odds}){win_mark}")
            self.bet_choices_lbl.configure(text="\n".join(out_lines))

            can_bet = bool(self.engine.oauth_token and ev_st == "ACTIVE" and ev_id not in self._bet_event_ids and outcomes)
            pred_btn_sig = (ev_id, ev_st, ev_id in self._bet_event_ids, self._bet_stake_val, bool(self.engine.oauth_token), tuple(o.get("id") for o in outcomes))
            if pred_btn_sig != self._last_pred_render_sig:
                self._last_pred_render_sig = pred_btn_sig
                for w in self.bet_action_row.winfo_children():
                    w.destroy()
                if can_bet:
                    stakes_bar = ctk.CTkFrame(self.bet_action_row, fg_color="transparent")
                    stakes_bar.pack(fill="x", pady=(0, 3))
                    ctk.CTkLabel(stakes_bar, text="Puntata:", font=ctk.CTkFont("Segoe UI", 9, "bold"), text_color=C_TEXT_DIM).pack(side="left", padx=(0, 4))
                    for stk in (10, 50, 250, 1000):
                        is_sel = (self._bet_stake_val == stk)
                        ctk.CTkButton(
                            stakes_bar, text=self._fmt_compact_num(stk), width=36, height=19, corner_radius=5,
                            fg_color=C_ACCENT if is_sel else C_BG_CARD,
                            hover_color=C_ACCENT_HOVER if is_sel else C_BG_CARD_HOVER,
                            text_color="#ffffff" if is_sel else C_TEXT_MAIN,
                            border_width=1, border_color=C_ACCENT if is_sel else C_BORDER,
                            font=ctk.CTkFont("Segoe UI", 9, "bold"),
                            command=lambda v=stk: (setattr(self, "_bet_stake_val", v), self._update_points_and_poll_ui()),
                        ).pack(side="left", padx=2)
                    outs_bar = ctk.CTkFrame(self.bet_action_row, fg_color="transparent")
                    outs_bar.pack(fill="x")
                    for o in outcomes[:4]:
                        oid = str(o.get("id") or "")
                        otitle = str(o.get("title") or "Opzione")
                        short_o = otitle if len(otitle) <= 13 else otitle[:12] + "…"
                        col_name = str(o.get("color") or "").upper()
                        btn_col = ("#2563eb", "#1d4ed8") if col_name == "BLUE" else (("#db2777", "#be185d") if col_name == "PINK" else C_ACCENT)
                        ctk.CTkButton(
                            outs_bar, text=f"Punta {short_o}", height=22, corner_radius=6,
                            fg_color=btn_col, hover_color=C_ACCENT, text_color="#ffffff",
                            font=ctk.CTkFont("Segoe UI", 9, "bold"),
                            command=lambda eid=ev_id, o_id=oid, ot=otitle: self._submit_prediction_bet_async(eid, o_id, ot, self._bet_stake_val),
                        ).pack(side="left", fill="x", expand=True, padx=2)
                    self.bet_action_row.pack(fill="x", padx=8, pady=(0, 6))
                elif ev_id in self._bet_event_ids and ev_st == "ACTIVE":
                    ctk.CTkLabel(
                        self.bet_action_row, text="✓ Puntata piazzata", font=ctk.CTkFont("Segoe UI", 9, "bold"),
                        text_color=C_CYAN, anchor="w", height=18,
                    ).pack(side="left")
                    self.bet_action_row.pack(fill="x", padx=8, pady=(0, 5))
                else:
                    self.bet_action_row.pack_forget()

            ev_ann = (ev_id, ev_st)
            if ev_id and ev_ann != self._announced_pred_sig:
                self._announced_pred_sig = ev_ann
                if ev_st == "ACTIVE":
                    opts_s = " vs ".join(str(o.get("title") or "") for o in outcomes[:4])
                    self.chat._enqueue("🔮 BET APERTA", f"{ev_title} ({opts_s})", C_CYAN)
                elif ev_st == "RESOLVED":
                    win_title = (pred.get("winningOutcome") or {}).get("title") or "?"
                    self.chat._enqueue("🏆 RISULTATO BET", f"{ev_title} — Vince: {win_title}", C_GOLD)

            if not self.bet_banner.winfo_manager():
                self.bet_banner.pack(fill="x", padx=6, pady=(2, 4), before=self.chat_box)
        else:
            if self.bet_banner.winfo_manager():
                self.bet_banner.pack_forget()

    def _is_current_stream_drop_eligible(self):
        if self.is_playing_vod or self.is_multiview or not self.current_channel:
            return False, None
        ctx = self.current_live_context or {}
        g_cur = (ctx.get("game_name") or (self.current_stream_info or {}).get("game") or "").strip().lower()
        active_drop = None
        for d in (self.current_drops_list or []):
            if d.get("claimed") or not d.get("required_min"):
                continue
            if d.get("is_current_game") or (g_cur and (d.get("game_name") or "").strip().lower() == g_cur):
                active_drop = d
                break
        eligible = bool(ctx.get("drops_eligible")) or bool(ctx.get("channel_drop_campaigns")) or (active_drop is not None)
        return eligible, active_drop

    def _update_drops_badge_ui(self):
        if not self.app_running:
            return
        badge = getattr(self, "drops_live_badge", None)
        if badge is None or not badge.winfo_exists():
            return
        badge_wrap = getattr(badge, "_shadow_wrap", badge)
        eligible, active_drop = self._is_current_stream_drop_eligible()
        if not eligible:
            if badge_wrap.winfo_manager():
                badge_wrap.pack_forget()
            return
        if active_drop:
            req_m = max(1, active_drop.get("required_min", 1))
            pct = min(100, int(round(active_drop.get("current_min", 0) * 100.0 / req_m)))
            badge.configure(text=f" Drops Attivi • {pct}%")
        else:
            badge.configure(text=" Drops Attivi")
        if not badge_wrap.winfo_manager():
            badge_wrap.pack(side="right", padx=4, after=self.shield_badge)

    # =================================================================
    # DIALOG NEGOZIO RICOMPENSE PUNTI CANALE & DIALOG TWITCH DROPS
    # =================================================================
    def open_channel_points_dialog(self):
        existing = getattr(self, "_points_dlg", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    if str(existing.state()) in ("withdrawn", "iconic"):
                        existing.deiconify()
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                self._points_dlg = None

        dlg = ctk.CTkToplevel(self)
        dlg._deactivate_windows_window_header_manipulation = True
        self._points_dlg = dlg
        dlg.title(f"Twixy — Punti Canale & Ricompense ({self.current_channel or 'Canale'})")
        dlg.geometry("520x540")
        dlg.configure(fg_color=C_BG_SIDEBAR)
        dlg.transient(self)
        _set_win_titlebar_theme(dlg, self.config_data.get("theme", "Dark"))
        dlg.bind("<Destroy>", lambda e: setattr(self, "_points_dlg", None) if (e.widget is dlg and self._points_dlg is dlg) else None)
        dlg.after(100, dlg.lift)

        ctx = self.current_live_context or {}
        bal = ctx.get("points_balance")
        p_name = ctx.get("points_name") or "Punti Canale"
        bal_txt = f"{bal:,}".replace(",", ".") if bal is not None else ("Caricamento..." if self.engine.oauth_token else "Effettua il Login")

        hdr = ctk.CTkFrame(dlg, fg_color=C_BG_HEADER, corner_radius=10, border_width=1, border_color=C_BORDER)
        hdr.pack(fill="x", padx=16, pady=(14, 8))
        bal_lbl = ctk.CTkLabel(hdr, text=f"🪙 Saldo attuale: {bal_txt} {p_name}", font=ctk.CTkFont("Segoe UI", 15, "bold"), text_color=C_GOLD)
        bal_lbl.pack(pady=(10, 2))
        ctk.CTkLabel(hdr, text="✨ I bauli bonus (+50 pt) vengono riscattati in automatico mentre guardi la live!", font=ctk.CTkFont("Segoe UI", 10), text_color=C_GREEN).pack(pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(dlg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=6)

        def _render_rewards(ctx_data):
            if not dlg.winfo_exists():
                return
            for w in scroll.winfo_children():
                w.destroy()

            c_bal = ctx_data.get("points_balance")
            c_pname = ctx_data.get("points_name") or "Punti Canale"
            c_bal_txt = f"{c_bal:,}".replace(",", ".") if c_bal is not None else "Effettua il Login"
            bal_lbl.configure(text=f"🪙 Saldo attuale: {c_bal_txt} {c_pname}")

            rewards = ctx_data.get("rewards") or []
            if not rewards:
                msg = (
                    "Nessuna ricompensa personale attiva su questo canale."
                    if self.current_channel
                    else "Avvia una live per caricare le ricompense riscattabili del canale."
                )
                ctk.CTkLabel(
                    scroll, text=msg,
                    font=ctk.CTkFont("Segoe UI", 12), text_color=C_TEXT_DIM
                ).pack(pady=40)
                return

            ch_id = ctx_data.get("channel_id")
            for rw in rewards:
                card = ctk.CTkFrame(scroll, fg_color=C_BG_CARD, corner_radius=8, border_width=1, border_color=C_BORDER)
                card.pack(fill="x", padx=4, pady=4)

                top = ctk.CTkFrame(card, fg_color="transparent")
                top.pack(fill="x", padx=10, pady=(8, 2))

                ctk.CTkLabel(top, text=rw["title"], font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color=C_TEXT_MAIN).pack(side="left")
                cost_str = f"🪙 {rw['cost']:,}".replace(",", ".")
                ctk.CTkLabel(top, text=cost_str, font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=C_GOLD).pack(side="right")

                if rw["prompt"]:
                    ctk.CTkLabel(card, text=rw["prompt"], font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM, wraplength=440, justify="left", anchor="w").pack(fill="x", padx=10, pady=(0, 4))

                def _redeem_action(r_obj=rw):
                    user_text = None
                    if r_obj["input_required"] and not r_obj.get("is_automatic"):
                        inp_dlg = ctk.CTkInputDialog(text=f"Inserisci il messaggio per '{r_obj['title']}':", title="Testo Ricompensa")
                        user_text = inp_dlg.get_input()
                        if not user_text:
                            return
                    ok, msg = self.engine.redeem_custom_reward(
                        ch_id,
                        r_obj["id"],
                        r_obj["title"],
                        r_obj["cost"],
                        user_text,
                        is_automatic=r_obj.get("is_automatic", False),
                        auto_type=r_obj.get("auto_type")
                    )
                    if ok:
                        details = self.engine.last_redeem_details or {}
                        em_tok = details.get("emote_token") or ""
                        em_url = details.get("emote_url") or ""
                        if em_tok:
                            if em_url:
                                self.emote_mgr.register_emote(em_tok, em_url, source="Twitch", is_channel=True)
                            self.chat._enqueue("🎲 EMOTE SBLOCCATA", f"Hai sbloccato l'emoticon '{em_tok}' ({r_obj['cost']} pt)!", C_GOLD)
                            self._push_local_notification("emote_unlock", f"Emoticon sbloccata: {em_tok}", channel=self.current_channel, image_url=em_url)
                            self._show_unlocked_emote_dialog(em_tok, em_url, parent_win=dlg)
                        else:
                            self.chat._enqueue("🪙 RICOMPENSA", f"Hai riscattato '{r_obj['title']}' ({r_obj['cost']} pt)!", C_GOLD)
                            self._push_local_notification("reward", f"Ricompensa riscattata: {r_obj['title']}", channel=self.current_channel)
                            messagebox.showinfo("Riscattata!", msg, parent=dlg)
                    elif msg.startswith("NEED_BROWSER:"):
                        reason = msg.split("NEED_BROWSER:", 1)[1]
                        if self.current_channel and messagebox.askyesno(
                            "Conferma su Twitch",
                            f"{reason}\n\nVuoi aprire la chat di #{self.current_channel} su Twitch nel browser?",
                            parent=dlg
                        ):
                            webbrowser.open(f"https://www.twitch.tv/popout/{self.current_channel}/chat")
                    else:
                        messagebox.showerror("Errore Riscatto", msg, parent=dlg)

                can_afford = (c_bal is None) or (c_bal >= rw["cost"])
                ctk.CTkButton(
                    card, text="Riscatta Ricompensa" if can_afford else "Punti Insufficienti",
                    height=28, corner_radius=6,
                    state="normal" if can_afford else "disabled",
                    fg_color=C_ACCENT if can_afford else C_BG_INPUT,
                    hover_color=C_ACCENT_HOVER,
                    font=ctk.CTkFont("Segoe UI", 11, "bold"),
                    command=_redeem_action
                ).pack(fill="x", padx=10, pady=(4, 8))

        if ctx.get("rewards"):
            _render_rewards(ctx)
        elif self.current_channel:
            loading_lbl = ctk.CTkLabel(scroll, text="⏳ Caricamento ricompense del canale...", font=ctk.CTkFont("Segoe UI", 12), text_color=C_GOLD)
            loading_lbl.pack(pady=40)
            target_ch = self.current_channel

            def _fetch_now():
                fresh = None
                try:
                    fresh = self.engine.fetch_channel_live_context(target_ch)
                except Exception:
                    pass
                if fresh and target_ch == self.current_channel:
                    self.current_live_context = fresh
                    self.after(0, self._update_points_and_poll_ui)
                self.after(0, lambda: _render_rewards(fresh or self.current_live_context or {}))

            threading.Thread(target=_fetch_now, daemon=True).start()
        else:
            _render_rewards({})

    def _show_unlocked_emote_dialog(self, emote_token, emote_url="", parent_win=None):
        """Mostra quale emoticon abbonamento casuale è stata appena sbloccata con anteprima grafica e azioni rapide."""
        pop = ctk.CTkToplevel(parent_win or self)
        pop.title("🎲 Emoticon Casuale Sbloccata!")
        pop.geometry("390x285")
        pop.configure(fg_color=C_BG_SIDEBAR)
        pop.resizable(False, False)
        pop.transient(parent_win or self)
        pop.after(60, pop.lift)

        ctk.CTkLabel(
            pop, text="🎉 Hai sbloccato una nuova emoticon!",
            font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=C_GOLD
        ).pack(pady=(16, 8))

        preview_box = ctk.CTkFrame(pop, fg_color=C_BG_CARD, width=110, height=110, corner_radius=12, border_width=1, border_color=C_ACCENT)
        preview_box.pack(pady=4)
        preview_box.pack_propagate(False)

        img_lbl = ctk.CTkLabel(preview_box, text="😀", font=ctk.CTkFont("Segoe UI", 34))
        img_lbl.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            pop, text=emote_token,
            font=ctk.CTkFont("Consolas", 16, "bold"), text_color=C_CYAN
        ).pack(pady=(8, 10))

        if emote_url:
            def _load_preview():
                try:
                    r = self.engine.session.get(emote_url, timeout=6)
                    if r.status_code == 200 and r.content:
                        im = Image.open(io.BytesIO(r.content)).convert("RGBA")
                        im.thumbnail((68, 68), Image.Resampling.LANCZOS)
                        c_img = ctk.CTkImage(light_image=im, dark_image=im, size=im.size)

                        def _apply():
                            if pop.winfo_exists() and img_lbl.winfo_exists():
                                img_lbl.configure(image=c_img, text="")
                                img_lbl._twixy_img = c_img

                        self.after(0, _apply)
                except Exception:
                    pass

            threading.Thread(target=_load_preview, daemon=True).start()

        btn_row = ctk.CTkFrame(pop, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 14))

        def _insert_in_chat():
            curr = self.chat_entry.get()
            if curr and not curr.endswith(" "):
                self.chat_entry.insert("end", " ")
            self.chat_entry.insert("end", emote_token + " ")
            self.chat_entry.focus_set()
            pop.destroy()

        def _copy_code():
            try:
                self.clipboard_clear()
                self.clipboard_append(emote_token)
            except Exception:
                pass
            copy_btn.configure(text="✔ Copiata!", fg_color=C_GREEN)

        ctk.CTkButton(
            btn_row, text="💬 Inserisci in Chat", height=32, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=_insert_in_chat
        ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        copy_btn = ctk.CTkButton(
            btn_row, text="📋 Copia", width=92, height=32, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=_copy_code
        )
        copy_btn.pack(side="left")

    def open_drops_dialog(self, highlight_active=False):
        self.open_inapp_menu(tab="Drop", drops_highlight=highlight_active)

    def _fetch_and_cache_thumb_pil(self, url, size=(42, 42), circle=False):
        if not url or not self.app_running:
            return None
        cache_key = (str(url), tuple(size), bool(circle))
        with self._thumb_cache_lock:
            cached = self._thumb_pil_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            r = self.engine.session.get(url, timeout=4.5)
            if r.status_code != 200 or not r.content:
                return None
            im = Image.open(io.BytesIO(r.content)).convert("RGBA")
            if circle:
                im = im.resize(size, Image.Resampling.LANCZOS)
                mask = Image.new("L", size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size[0] - 1, size[1] - 1), fill=255)
                im.putalpha(mask)
            else:
                im.thumbnail(size, Image.Resampling.LANCZOS)
            with self._thumb_cache_lock:
                if len(self._thumb_pil_cache) >= 260:
                    for old_k in list(self._thumb_pil_cache.keys())[:60]:
                        self._thumb_pil_cache.pop(old_k, None)
                self._thumb_pil_cache[cache_key] = im
            return im
        except Exception:
            return None

    def _prefetch_thumbs_sync(self, urls, size=(42, 42), circle=False, timeout=1.1):
        pending = []
        seen = set()
        for url in (urls or ()):
            u = str(url or "").strip()
            if not u or u in seen:
                continue
            seen.add(u)
            cache_key = (u, tuple(size), bool(circle))
            with self._thumb_cache_lock:
                if cache_key in self._thumb_pil_cache:
                    continue
            try:
                pending.append(self._thumb_executor.submit(self._fetch_and_cache_thumb_pil, u, size, circle))
            except Exception:
                pass
        if pending:
            try:
                futures_wait(pending, timeout=timeout)
            except Exception:
                pass

    def _get_circle_initial_ctk_img(self, letter, is_live, size=42):
        """Genera (e mette in cache) un badge circolare trasparente per l'iniziale dello streamer senza bordi quadrati."""
        ch = (str(letter or "?").strip()[:1] or "?").upper()
        sz = max(16, int(size))
        key = (ch, bool(is_live), sz)
        cache = getattr(self, "_circle_init_cache", None)
        if cache is None:
            cache = {}
            self._circle_init_cache = cache
        cached = cache.get(key)
        if cached is not None:
            return cached

        def _pair(c):
            return (c[0], c[1]) if isinstance(c, (tuple, list)) and len(c) >= 2 else (c, c)

        l_bg, d_bg = _pair(C_ACCENT) if is_live else _pair(C_BG_INPUT)
        l_fg, d_fg = ("#ffffff", "#ffffff") if is_live else _pair(C_TEXT_DIM)

        fnt = None
        try:
            from PIL import ImageFont
            for fname in ("seguibd.ttf", "arialbd.ttf", "arial.ttf"):
                try:
                    fnt = ImageFont.truetype(fname, int(round(sz * 0.92)))
                    break
                except Exception:
                    pass
            if fnt is None:
                fnt = ImageFont.load_default()
        except Exception:
            fnt = None

        S = 2
        sw = sz * S
        resample_lanczos = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)
        imgs = []
        for bg_c, fg_c in ((l_bg, l_fg), (d_bg, d_fg)):
            im = Image.new("RGBA", (sw, sw), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.ellipse([1, 1, sw - 2, sw - 2], fill=bg_c)
            if fnt is not None:
                try:
                    d.text((sw / 2.0, sw / 2.0), ch, fill=fg_c, font=fnt, anchor="mm")
                except Exception:
                    try:
                        d.text((sw * 0.34, sw * 0.24), ch, fill=fg_c, font=fnt)
                    except Exception:
                        pass
            imgs.append(im.resize((sz, sz), resample_lanczos))

        c_img = ctk.CTkImage(light_image=imgs[0], dark_image=imgs[1], size=(sz, sz))
        if len(cache) >= 256:
            cache.clear()
        cache[key] = c_img
        return c_img

    def _load_cached_thumb_async(self, lbl, url, size=(42, 42), circle=False, guard_win=None):
        """Scarica e ridimensiona una miniatura usando il pool limitato e costruisce CTkImage SOLO sul thread UI."""
        if not url or not self.app_running:
            return
        cache_key = (str(url), tuple(size), bool(circle))

        def _apply(pil_img):
            if not self.app_running or pil_img is None:
                return
            try:
                if guard_win is not None and not guard_win.winfo_exists():
                    return
                if not lbl.winfo_exists():
                    return
                c_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                lbl.configure(image=c_img, text="")
                lbl._twixy_img = c_img
            except Exception:
                pass

        with self._thumb_cache_lock:
            cached = self._thumb_pil_cache.get(cache_key)
        if cached is not None:
            _apply(cached)
            return

        def _fetch():
            if not self.app_running:
                return
            try:
                if guard_win is not None and not guard_win.winfo_exists():
                    return
            except Exception:
                return
            im = self._fetch_and_cache_thumb_pil(url, size=size, circle=circle)
            if im is not None:
                self._safe_ui(lambda img=im: _apply(img))

        try:
            self._thumb_executor.submit(_fetch)
        except Exception:
            pass

    def open_notifications_dialog(self, initial_tab="🔔 Tutte"):
        self.open_inapp_menu(tab="Notifiche", notif_subtab=initial_tab)

    def _on_global_mousewheel(self, event):
        if self.sidebar_locked:
            return "break"

    def _cancel_sidebar_reveal(self):
        aid = getattr(self, "_sidebar_reveal_after", None)
        if aid is not None:
            self._sidebar_reveal_after = None
            try:
                self.after_cancel(aid)
            except Exception:
                pass

    def _lock_sidebar(self, text="⏳ Preparazione lista..."):
        self._cancel_sidebar_reveal()
        self.sidebar_locked = True
        try:
            self.sidebar_lock_lbl.configure(text=text)
            self.sidebar_lock_lbl.place(relx=0.5, rely=0.45, anchor="center")
        except Exception:
            pass
        self.sidebar_lock_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.sidebar_lock_frame.lift()

    def _unlock_sidebar(self):
        self._cancel_sidebar_reveal()
        def _reset_scroll():
            try:
                if self.app_running and self.cards_scroll.winfo_exists():
                    self.cards_scroll._parent_canvas.yview_moveto(0.0)
            except Exception:
                pass
        self.after_idle(_reset_scroll)
        try:
            self.sidebar_lock_frame.place_forget()
        except Exception:
            pass
        self.sidebar_locked = False

    def apply_theme(self, mode):
        target_mode = "Light" if str(mode).lower().startswith("l") or "bianco" in str(mode).lower() else "Dark"
        self.config_data["theme"] = target_mode
        try:
            if getattr(self, "_theme_save_after", None) is not None:
                self.after_cancel(self._theme_save_after)
        except Exception:
            pass
        self._theme_save_after = self.after(200, self.save_config)

        try:
            self._close_sidebar_popover()
        except Exception:
            pass

        self._deactivate_windows_window_header_manipulation = True
        for w in self.winfo_children():
            if isinstance(w, ctk.CTkToplevel):
                w._deactivate_windows_window_header_manipulation = True

        # Congela il ridisegno GDI su Windows finché TUTTI i widget non hanno cambiato colore, poi ridisegna in un colpo solo
        _hwnd = 0
        if sys.platform.startswith("win"):
            try:
                if self.winfo_ismapped():
                    _hwnd = int(self.winfo_id())
                    ctypes.windll.user32.SendMessageW(_hwnd, 0x000B, 0, 0)
            except Exception:
                _hwnd = 0

        try:
            if ctk.get_appearance_mode().lower() != target_mode.lower():
                ctk.set_appearance_mode(target_mode)
            try:
                self.configure(fg_color=C_BG_ROOT)
                tk.Tk.configure(self, bg=_tk_color(C_BG_ROOT))
            except Exception:
                pass

            try:
                self.chat_box.configure(bg=_tk_color(C_CHAT_BG), fg=_tk_color(C_TEXT_MAIN))
                for tag, raw_col in list(self._chat_tag_raw_colors.items()):
                    try:
                        self.chat_box.tag_config(tag, foreground=_adapt_chat_color(raw_col, target_mode))
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                self.video_canvas.configure(bg=_tk_color(C_VIDEO_LETTERBOX))
                for tile in getattr(self, "multi_tiles", []):
                    if tile.get("canvas") and tile["canvas"].winfo_exists():
                        tile["canvas"].configure(bg=_tk_color(C_VIDEO_LETTERBOX))
                for stage_attr in ("center_stage", "video_stage", "multiview_frame"):
                    st = getattr(self, stage_attr, None)
                    if st is not None and st.winfo_exists():
                        st.configure(fg_color=C_VIDEO_LETTERBOX)
                if hasattr(self, "mv_grid_body") and self.mv_grid_body.winfo_exists():
                    self.mv_grid_body.configure(fg_color=("#D5D9E4", "#050507"))
            except Exception:
                pass
            try:
                self.fs_hud.configure(bg=_tk_color(C_BG_HEADER))
                self.pip_hud.configure(bg=_tk_color(C_BG_HEADER))
                if hasattr(self, "fs_hud_inner") and self.fs_hud_inner.winfo_exists():
                    self.fs_hud_inner.configure(fg_color=C_BG_HEADER)
                if hasattr(self, "pip_hud_inner") and self.pip_hud_inner.winfo_exists():
                    self.pip_hud_inner.configure(fg_color=C_BG_HEADER)
            except Exception:
                pass

            def _sync_scrollable_colors(cs_widget, bg_pair):
                if cs_widget is None:
                    return
                bg_hex = _tk_color(bg_pair)
                try:
                    cs_widget.configure(fg_color=bg_pair)
                except Exception:
                    pass
                try:
                    tk.Frame.configure(cs_widget, bg=bg_hex)
                except Exception:
                    pass
                try:
                    if hasattr(cs_widget, "_parent_canvas"):
                        cs_widget._parent_canvas.configure(bg=bg_hex)
                except Exception:
                    pass
                try:
                    if hasattr(cs_widget, "_scrollable_frame"):
                        sf_cs = cs_widget._scrollable_frame
                        if isinstance(sf_cs, ctk.CTkBaseClass):
                            sf_cs.configure(fg_color=bg_pair)
                        else:
                            sf_cs.configure(bg=bg_hex)
                except Exception:
                    pass
                try:
                    if hasattr(cs_widget, "_parent_frame"):
                        cs_widget._parent_frame.configure(fg_color=bg_pair)
                except Exception:
                    pass

            try:
                if hasattr(self, "cards_scroll") and self.cards_scroll.winfo_exists():
                    _sync_scrollable_colors(self.cards_scroll, C_BG_SIDEBAR)
            except Exception:
                pass

            if hasattr(self, "_inapp_body") and self._inapp_body.winfo_exists():
                try:
                    st_walk = list(self._inapp_body.winfo_children())
                    while st_walk:
                        cw = st_walk.pop(0)
                        if isinstance(cw, ctk.CTkScrollableFrame):
                            _sync_scrollable_colors(cw, C_BG_SIDEBAR)
                        elif isinstance(cw, tk.Frame) and not isinstance(cw, ctk.CTkBaseClass):
                            sp = getattr(cw, "_surface_fg_pair", None)
                            if sp is not None:
                                try:
                                    cw.configure(bg=_tk_color(sp))
                                except Exception:
                                    pass
                        try:
                            st_walk.extend(cw.winfo_children())
                        except Exception:
                            pass
                except Exception:
                    pass

            # Aggiorna testi delle segmented bars e controlli custom
            alive_segs = []
            for seg in list(getattr(self, "_tracked_seg_bars", [])):
                try:
                    if seg is not None and seg.winfo_exists():
                        self._style_segmented_tabs(seg)
                        alive_segs.append(seg)
                except Exception:
                    pass
            self._tracked_seg_bars = alive_segs

            self._update_deck_toggle_styles()
            self._refresh_nav_tab_styles()
            self._update_login_badge()
            if getattr(self, "_inapp_menu_open", False):
                self._refresh_inapp_tab_styles()

            # Aggiorna il Selettore Emote (contiene tk.Button nativi) se aperto
            ep = getattr(self, "_emote_picker_win", None)
            if ep is not None:
                try:
                    if ep.winfo_exists():
                        for child in ep.winfo_children():
                            if isinstance(child, ctk.CTkScrollableFrame):
                                for b in child.winfo_children():
                                    if isinstance(b, tk.Button):
                                        b.configure(bg=_tk_color(C_BG_INPUT), fg=_tk_color(C_TEXT_DIM))
                except Exception:
                    pass

            # Aggiorna barra titolo Windows e ombre Pillow (prima i contenitori, poi i pulsanti)
            _set_win_titlebar_theme(self, target_mode)
            sw_list = [w for w in list(getattr(self, "_smooth_shadow_widgets", ())) if w is not None and w.winfo_exists()]
            sw_shells = [w for w in sw_list if hasattr(w, "inner")]
            sw_btns = [w for w in sw_list if not hasattr(w, "inner")]
            for _sw in sw_shells + sw_btns:
                try:
                    if _sw.winfo_exists():
                        _sw.refresh_theme()
                except Exception:
                    pass

            for dlg_attr in ("_emote_picker_win", "_points_dlg"):
                dlg_obj = getattr(self, dlg_attr, None)
                if dlg_obj is not None:
                    try:
                        if dlg_obj.winfo_exists():
                            _set_win_titlebar_theme(dlg_obj, target_mode)
                            if str(dlg_obj.state()) in ("withdrawn", "iconic"):
                                dlg_obj.deiconify()
                    except Exception:
                        setattr(self, dlg_attr, None)
        finally:
            if _hwnd:
                try:
                    ctypes.windll.user32.SendMessageW(_hwnd, 0x000B, 1, 0)
                    ctypes.windll.user32.RedrawWindow(_hwnd, None, None, 0x0181)
                except Exception:
                    pass

    def _clear_emote_cache(self, status_lbl=None):
        with self.emote_mgr._lock:
            cnt = len(self.emote_mgr.photo_cache)
            anim_cnt = len(self.emote_mgr._animated_keys)
            self.emote_mgr.photo_cache.clear()
            self.emote_mgr._animated_keys.clear()
            self.emote_mgr._loading.clear()
            self.emote_mgr._failed.clear()
            self.emote_mgr._callbacks.clear()
        if status_lbl is not None and status_lbl.winfo_exists():
            status_lbl.configure(
                text=f"✔ Cache emote svuotata ({cnt} immagini / {anim_cnt} animazioni liberate).",
                text_color=C_GREEN
            )

    def _clear_adstripper_cache(self, status_lbl=None):
        with self.engine.ad_stripper._lock:
            for slot in self.engine.ad_stripper.slots.values():
                slot["last_clean_cache"] = ""
                slot["last_refresh_ts"] = 0.0
        blocked = self.engine.ad_stripper.ads_blocked_count
        self.engine.ad_stripper.ads_blocked_count = 0
        if status_lbl is not None and status_lbl.winfo_exists():
            status_lbl.configure(
                text=f"✔ Cache playlist e contatore ad ({blocked}) azzerati.",
                text_color=C_GREEN
            )

    def open_settings_dialog(self):
        self.open_inapp_menu(tab="Impostazioni")

    # =================================================================
    # HUD FLOTTANTE IN SCHERMO INTERO & PIP HUD
    # =================================================================
    def _build_fullscreen_hud(self):
        self.fs_hud = tk.Toplevel()
        self.fs_hud.withdraw()
        self.fs_hud.overrideredirect(True)
        self.fs_hud.configure(bg=_tk_color(C_BG_HEADER))

        self.fs_hud_inner = ctk.CTkFrame(self.fs_hud, fg_color=C_BG_HEADER, corner_radius=12, border_width=1, border_color=C_ACCENT)
        hud_inner = self.fs_hud_inner
        hud_inner.pack(fill="both", expand=True, padx=2, pady=2)

        self.fs_seek_row = ctk.CTkFrame(hud_inner, fg_color="transparent", height=30)

        self._make_shadow_btn(
            self.fs_seek_row,
            pack_kw={"side": "left", "padx": (12, 2), "pady": (4, 0)},
            offset_x=1, offset_y=2,
            text="⏪ -10s", width=56, height=24, corner_radius=6,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 10),
            command=lambda: self.seek_relative(-10)
        )

        self._make_shadow_btn(
            self.fs_seek_row,
            pack_kw={"side": "left", "padx": (2, 8), "pady": (4, 0)},
            offset_x=1, offset_y=2,
            text="+30s ⏩", width=56, height=24, corner_radius=6,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 10),
            command=lambda: self.seek_relative(30)
        )

        self.fs_seek_slider = ctk.CTkSlider(
            self.fs_seek_row, from_=0, to=1000, number_of_steps=1000, height=14,
            fg_color=C_BG_INPUT, progress_color=C_ACCENT,
            button_color=("#7c3aed", "#ffffff"), button_hover_color=C_ACCENT,
            command=self.on_seek_drag
        )
        self.fs_seek_slider.set(0)
        self.fs_seek_slider.pack(side="left", fill="x", expand=True, padx=6, pady=(6, 0))
        self.fs_seek_slider.bind("<ButtonPress-1>", lambda e: setattr(self, "seeking_drag", True))
        self.fs_seek_slider.bind("<ButtonRelease-1>", self.on_seek_release)

        self.fs_time_lbl = ctk.CTkLabel(
            self.fs_seek_row, text="00:00:00 / 00:00:00",
            font=ctk.CTkFont("Consolas", 11, "bold"), text_color=C_TEXT_MAIN
        )
        self.fs_time_lbl.pack(side="right", padx=(8, 14), pady=(6, 0))

        self.fs_ctrl_row = ctk.CTkFrame(hud_inner, fg_color="transparent")
        self.fs_ctrl_row.pack(fill="x", expand=True)

        self.fs_play_btn = self._make_shadow_btn(
            self.fs_ctrl_row,
            pack_kw={"side": "left", "padx": (12, 4), "pady": 6},
            offset_x=2, offset_y=2,
            text=" Pausa", image=self._icon_pause, compound="left",
            width=82, height=32, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.toggle_pause
        )

        self.fs_clip_btn = self._make_shadow_btn(
            self.fs_ctrl_row,
            pack_kw={"side": "left", "padx": (2, 6), "pady": 6},
            offset_x=2, offset_y=2,
            text=" Clip", image=self._icon_clip, compound="left",
            width=74, height=32, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.open_clip_dialog
        )

        ctk.CTkLabel(self.fs_ctrl_row, text="", image=self._icon_volume, width=20).pack(side="left", padx=(8, 2))
        self.fs_vol_slider = ctk.CTkSlider(
            self.fs_ctrl_row, from_=0, to=100, width=110, height=14,
            fg_color=C_BG_INPUT, progress_color=C_GREEN, button_color=("#059669", "#ffffff"),
            command=self.on_volume_change
        )
        self.fs_vol_slider.set(self.config_data.get("volume", 80))
        self.fs_vol_slider.pack(side="left", padx=(2, 12))

        ctk.CTkLabel(self.fs_ctrl_row, text="Qualità:", font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_DIM).pack(side="left", padx=(4, 4))
        self.fs_quality_menu = ctk.CTkOptionMenu(
            self.fs_ctrl_row, variable=self.quality_var, width=155, height=32, corner_radius=8,
            fg_color=C_BG_CARD, button_color=C_ACCENT, button_hover_color=C_ACCENT_HOVER,
            text_color=C_TEXT_MAIN,
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            values=["1080p60 (Source)"],
            command=self.on_quality_changed
        )
        self.fs_quality_menu.pack(side="left", padx=(0, 12))

        self.fs_chat_btn = self._make_shadow_btn(
            self.fs_ctrl_row,
            pack_kw={"side": "left", "padx": 6},
            offset_x=2, offset_y=2,
            text=" Chat", image=self._icon_chat_white, compound="left",
            width=92, height=32, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.toggle_chat_in_fullscreen
        )

        self._make_shadow_btn(
            self.fs_ctrl_row,
            pack_kw={"side": "right", "padx": (6, 12), "pady": 6},
            offset_x=2, offset_y=2,
            text=" Esci", image=self._icon_close_white, compound="left",
            width=82, height=32, corner_radius=8,
            fg_color=C_LIVE, hover_color="#dc2626", text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.exit_fullscreen
        )

    def _build_pip_hud(self):
        self.pip_hud = tk.Toplevel()
        self.pip_hud.withdraw()
        self.pip_hud.overrideredirect(True)
        self.pip_hud.configure(bg=_tk_color(C_BG_HEADER))

        self.pip_hud_inner = ctk.CTkFrame(self.pip_hud, fg_color=C_BG_HEADER, corner_radius=8, border_width=1, border_color=C_ACCENT)
        p_inner = self.pip_hud_inner
        p_inner.pack(fill="both", expand=True, padx=1, pady=1)

        self._make_shadow_btn(
            p_inner,
            pack_kw={"side": "left", "padx": 6, "pady": 3},
            offset_x=1, offset_y=2,
            text=" Espandi", image=self._icon_expand_white, compound="left",
            width=84, height=24, corner_radius=6,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self.toggle_pip_mode
        )

        self.pip_play_btn = self._make_shadow_btn(
            p_inner,
            pack_kw={"side": "left", "padx": 2, "pady": 3},
            offset_x=1, offset_y=2,
            text="", image=self._icon_pause, width=30, height=24, corner_radius=6,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            command=self.toggle_pause
        )

        self.pip_vol_slider = ctk.CTkSlider(
            p_inner, from_=0, to=100, width=85, height=12,
            fg_color=C_BG_INPUT, progress_color=C_GREEN, button_color=("#059669", "#ffffff"),
            command=self.on_volume_change
        )
        self.pip_vol_slider.set(self.config_data.get("volume", 80))
        self.pip_vol_slider.pack(side="right", padx=6)

    def _load_pil_font(self, size):
        for fname in ("segoeuib.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf"):
            for base in (os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"), ""):
                fpath = os.path.join(base, fname) if base else fname
                try:
                    if os.path.isfile(fpath):
                        from PIL import ImageFont
                        return ImageFont.truetype(fpath, size)
                except Exception:
                    pass
        try:
            from PIL import ImageFont
            return ImageFont.load_default()
        except Exception:
            return None

    def _build_vod_hud_icons(self):
        """Genera icone vettoriali minimali senza sfondo per l'overlay VOD."""
        key_rgb = (1, 2, 3)

        def _finalize(w, h, fg_2x):
            sh_2x = Image.new("RGBA", fg_2x.size, (0, 0, 0, 0))
            # Crea alone/ombra scura sottile (-1..+1px) dal canale alpha
            fg_alpha = fg_2x.split()[3]
            dark_fill = Image.new("RGBA", fg_2x.size, (14, 14, 18, 195))
            for ox, oy in ((2, 3), (0, 2), (2, 0), (-1, 0), (0, -1)):
                sh_2x.paste(dark_fill, (ox, oy), fg_alpha)
            comp_2x = Image.alpha_composite(sh_2x, fg_2x)
            comp = comp_2x.resize((w, h), Image.Resampling.LANCZOS)
            px = comp.load()
            out = Image.new("RGB", (w, h), key_rgb)
            opx = out.load()
            for yy in range(h):
                for xx in range(w):
                    r, g, b, a = px[xx, yy]
                    if a < 32:
                        opx[xx, yy] = key_rgb
                    else:
                        # Miscela sul grigio-scuro invece del key_rgb per evitare frange
                        rr = (r * a + 16 * (255 - a)) // 255
                        gg = (g * a + 16 * (255 - a)) // 255
                        bb = (b * a + 22 * (255 - a)) // 255
                        if (rr, gg, bb) == key_rgb:
                            rr, gg, bb = (2, 3, 4)
                        opx[xx, yy] = (rr, gg, bb)
            from PIL import ImageTk
            return ImageTk.PhotoImage(out)

        def _make_pause(hover=False):
            w, h = 70, 70
            im = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            col = (224, 212, 255, 255) if hover else (255, 255, 255, 248)
            d.rounded_rectangle((45, 34, 60, 106), radius=7, fill=col)
            d.rounded_rectangle((80, 34, 95, 106), radius=7, fill=col)
            return _finalize(w, h, im)

        def _make_play(hover=False):
            w, h = 70, 70
            im = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            col = (224, 212, 255, 255) if hover else (255, 255, 255, 248)
            d.polygon([(48, 30), (106, 70), (48, 110)], fill=col)
            return _finalize(w, h, im)

        def _make_seek(label_txt, is_fwd=False, hover=False):
            w, h = 78, 70
            im = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            col = (224, 212, 255, 255) if hover else (255, 255, 255, 248)
            cx, cy, rad = (w, h + 6, 44)
            bbox = (cx - rad, cy - rad, cx + rad, cy + rad)
            if not is_fwd:
                d.arc(bbox, start=215, end=145, fill=col, width=7)
                d.polygon([(34, 59), (38, 34), (58, 50)], fill=col)
            else:
                d.arc(bbox, start=35, end=325, fill=col, width=7)
                d.polygon([(w * 2 - 34, 59), (w * 2 - 38, 34), (w * 2 - 58, 50)], fill=col)
            fnt = self._load_pil_font(32)
            if fnt is not None:
                d.text((cx, cy + 2), label_txt, fill=col, font=fnt, anchor="mm")
            return _finalize(w, h, im)

        self._vod_hud_imgs = {
            "rewind": (_make_seek("10", False, False), _make_seek("10", False, True)),
            "forward": (_make_seek("30", True, False), _make_seek("30", True, True)),
            "pause": (_make_pause(False), _make_pause(True)),
            "play": (_make_play(False), _make_play(True)),
        }

    def _set_vod_center_paused_ui(self, paused):
        lbl = getattr(self, "_vod_hud_center_lbl", None)
        if lbl is None or not getattr(self, "_vod_hud_imgs", None):
            return
        try:
            key = "play" if paused else "pause"
            pair = self._vod_hud_imgs[key]
            lbl._img_normal, lbl._img_hover = pair
            lbl.configure(image=pair[1] if getattr(lbl, "_is_hovered", False) else pair[0])
        except Exception:
            pass

    def _build_vod_hover_hud(self):
        """Overlay minimali e grandi sopra il video (-10s, ⏸/▶, +30s) con hitbox quadrata estesa e legati solo a Twixy."""
        self._vod_hud_wins = []
        self._vod_hud_pairs = []
        self.vod_hover_hud_visible = False
        self._build_vod_hud_icons()
        key_hex = "#010203"

        def _make_minimal_btn(w, h, hit_w, hit_h, img_pair, cmd):
            hit_win = tk.Toplevel(self)
            hit_win.withdraw()
            hit_win.overrideredirect(True)
            hit_win.transient(self)
            hit_win.configure(bg="#09090d", cursor="hand2")
            try:
                hit_win.attributes("-alpha", 0.02)
            except Exception:
                pass

            win = tk.Toplevel(self)
            win.withdraw()
            win.overrideredirect(True)
            win.transient(self)
            win.configure(bg=key_hex)
            try:
                win.attributes("-transparentcolor", key_hex)
            except Exception:
                win.configure(bg="#14141c")
            try:
                win.attributes("-alpha", 0.88)
            except Exception:
                pass
            lbl = tk.Label(
                win, image=img_pair[0], bg=key_hex if win.cget("bg") == key_hex else "#14141c",
                bd=0, highlightthickness=0, cursor="hand2"
            )
            lbl._img_normal, lbl._img_hover = img_pair
            lbl._is_hovered = False
            lbl.pack(fill="both", expand=True)

            def _on_enter(_e=None):
                lbl._is_hovered = True
                lbl.configure(image=lbl._img_hover)
                try:
                    hit_win.attributes("-alpha", 0.14)
                    win.attributes("-alpha", 1.0)
                except Exception:
                    pass

            def _on_leave(_e=None):
                try:
                    mx, my = hit_win.winfo_pointerxy()
                    hx, hy = hit_win.winfo_rootx(), hit_win.winfo_rooty()
                    hw, hh = hit_win.winfo_width(), hit_win.winfo_height()
                    if (hx <= mx <= hx + hw) and (hy <= my <= hy + hh):
                        return
                except Exception:
                    pass
                lbl._is_hovered = False
                lbl.configure(image=lbl._img_normal)
                try:
                    hit_win.attributes("-alpha", 0.02)
                    win.attributes("-alpha", 0.88)
                except Exception:
                    pass

            def _on_click(_e=None):
                try:
                    cmd()
                finally:
                    self.after(10, self.focus_set)

            for w_bind in (hit_win, lbl):
                w_bind.bind("<Enter>", _on_enter)
                w_bind.bind("<Leave>", _on_leave)
                w_bind.bind("<Button-1>", _on_click)
            self._vod_hud_wins.append((hit_win, hit_w, hit_h))
            self._vod_hud_wins.append((win, w, h))
            self._vod_hud_pairs.append((hit_win, hit_w, hit_h, win, w, h))
            return hit_win, win, lbl

        _, self._vod_hud_left_win, self._vod_hud_left_lbl = _make_minimal_btn(
            78, 70, 108, 98, self._vod_hud_imgs["rewind"], lambda: self.seek_relative(-10)
        )
        _, self._vod_hud_center_win, self._vod_hud_center_lbl = _make_minimal_btn(
            70, 70, 108, 98, self._vod_hud_imgs["pause"], self.toggle_pause
        )
        self.vod_hover_play_btn = self._vod_hud_center_lbl
        _, self._vod_hud_right_win, self._vod_hud_right_lbl = _make_minimal_btn(
            78, 70, 108, 98, self._vod_hud_imgs["forward"], lambda: self.seek_relative(30)
        )

        self.bind("<Unmap>", lambda e: self._hide_vod_hover_hud() if e.widget is self else None, add="+")
        self.bind("<FocusOut>", lambda _e: self.after(40, self._check_vod_overlay_focus), add="+")

    def _check_vod_overlay_focus(self):
        if not self.app_running or not getattr(self, "vod_hover_hud_visible", False):
            return
        if not self._is_vod_overlay_allowed():
            self._hide_vod_hover_hud()

    def _is_vod_overlay_allowed(self, mx=None, my=None):
        """Mostra gli overlay VOD solo se Twixy è in primo piano e il video non è coperto da altre app o dialog."""
        if (
            not self.app_running
            or not self.is_playing_vod
            or self.is_pip
            or self.is_multiview
            or self.state() == "iconic"
            or not self.video_canvas.winfo_viewable()
        ):
            return False
        if sys.platform.startswith("win"):
            try:
                main_hwnd = user32.GetAncestor(self.winfo_id(), GA_ROOT) or self.winfo_id()
                hud_hwnds = set()
                for hw, _, _ in getattr(self, "_vod_hud_wins", []):
                    try:
                        rhw = user32.GetAncestor(hw.winfo_id(), GA_ROOT) or hw.winfo_id()
                        if rhw:
                            hud_hwnds.add(rhw)
                    except Exception:
                        pass
                allowed = {h for h in ({main_hwnd} | hud_hwnds) if h}
                fg_root = get_foreground_root_hwnd()
                if not fg_root or fg_root not in allowed:
                    return False
                if mx is not None and my is not None:
                    pt_root = get_point_root_hwnd(mx, my)
                    if not pt_root or pt_root not in allowed:
                        return False
            except Exception:
                pass
        return True

    # =================================================================
    # INTERAZIONE MOUSE: FULLSCREEN HUD + PIP FRAMELESS SENZA BARRA WINDOWS
    # =================================================================
    def _get_video_aspect_ratio(self):
        if self.vlc_player:
            try:
                vw, vh = self.vlc_player.video_get_size(0)
                if vw > 0 and vh > 0:
                    self.video_aspect_ratio = float(vw) / float(vh)
            except Exception:
                pass
        return self.video_aspect_ratio

    def _force_pip_zero_black_bars(self, width, height):
        if width <= 10 or height <= 10:
            return
        if self.vlc_player:
            try:
                g = math.gcd(int(width), int(height))
                rw = max(1, int(width) // g)
                rh = max(1, int(height) // g)
                ratio_str = f"{rw}:{rh}"
                self.vlc_player.video_set_scale(0)
                self.vlc_player.video_set_aspect_ratio(None)
                self.vlc_player.video_set_crop_geometry(ratio_str)
            except Exception:
                pass
        if self.mpv_proc:
            self._send_mpv_ipc(["set_property", "keepaspect", True])
            self._send_mpv_ipc(["set_property", "panscan", 1.0])

    def _on_video_canvas_configure(self, event):
        if self.is_pip and event.width > 10 and event.height > 10:
            self._force_pip_zero_black_bars(event.width, event.height)

    def _detect_pip_hit_zone(self, mx, my, wx, wy, ww, wh):
        margin = 12
        on_left = wx <= mx <= wx + margin
        on_right = wx + ww - margin <= mx <= wx + ww
        on_top = wy <= my <= wy + margin
        on_bottom = wy + wh - margin <= my <= wy + wh

        if on_top and on_left:
            return "nw", "size_nw_se"
        if on_bottom and on_right:
            return "se", "size_nw_se"
        if on_top and on_right:
            return "ne", "size_ne_sw"
        if on_bottom and on_left:
            return "sw", "size_ne_sw"
        if on_left:
            return "w", "size_we"
        if on_right:
            return "e", "size_we"
        if on_top:
            return "n", "size_ns"
        if on_bottom:
            return "s", "size_ns"
        return "move", "fleur"

    def _start_pip_wheel_hook(self):
        if not sys.platform.startswith("win") or self._pip_hook_active:
            return

        def _hook_thread():
            try:
                from ctypes import wintypes

                WH_MOUSE_LL = 14
                WM_MOUSEWHEEL = 0x020A
                LRESULT = ctypes.c_ssize_t

                class MSLLHOOKSTRUCT(ctypes.Structure):
                    _fields_ = [
                        ("pt", wintypes.POINT),
                        ("mouseData", wintypes.DWORD),
                        ("flags", wintypes.DWORD),
                        ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t),
                    ]

                HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

                user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
                user32.SetWindowsHookExW.restype = ctypes.c_void_p
                user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
                user32.CallNextHookEx.restype = LRESULT
                user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
                user32.UnhookWindowsHookEx.restype = wintypes.BOOL
                user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
                user32.GetMessageW.restype = wintypes.BOOL

                def _low_level_mouse_proc(nCode, wParam, lParam):
                    if nCode >= 0 and wParam == WM_MOUSEWHEEL and self._pip_wheel_capture_active:
                        try:
                            ms = ctypes.cast(lParam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                            delta = ctypes.c_short((ms.mouseData >> 16) & 0xFFFF).value
                            if delta != 0:
                                with self._pip_wheel_lock:
                                    self._pip_wheel_delta += delta
                        except Exception:
                            pass
                    return user32.CallNextHookEx(None, nCode, wParam, lParam)

                proc = HOOKPROC(_low_level_mouse_proc)
                hhook = user32.SetWindowsHookExW(WH_MOUSE_LL, proc, None, 0)
                if not hhook:
                    return

                self._pip_hook_proc = proc
                self._pip_hook_tid = ctypes.windll.kernel32.GetCurrentThreadId()
                self._pip_hook_active = True

                msg = wintypes.MSG()
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))

                user32.UnhookWindowsHookEx(hhook)
            except Exception:
                pass
            finally:
                self._pip_hook_active = False
                self._pip_hook_tid = None
                self._pip_hook_proc = None

        threading.Thread(target=_hook_thread, daemon=True).start()

    def _stop_pip_wheel_hook(self):
        self._pip_wheel_capture_active = False
        with self._pip_wheel_lock:
            self._pip_wheel_delta = 0
        if sys.platform.startswith("win") and self._pip_hook_tid:
            try:
                user32.PostThreadMessageW(self._pip_hook_tid, 0x0012, 0, 0)
            except Exception:
                pass

    def _on_pip_tk_mouse_wheel(self, event):
        if not self.is_pip or self._pip_hook_active:
            return
        delta = getattr(event, "delta", 0)
        if not delta:
            num = getattr(event, "num", 0)
            delta = 120 if num == 4 else (-120 if num == 5 else 0)
        if delta:
            with self._pip_wheel_lock:
                self._pip_wheel_delta += delta

    def _resize_pip_by_wheel(self, wheel_delta, mx, my, curr_x, curr_y, curr_w, curr_h):
        ar = self._get_video_aspect_ratio()
        steps = wheel_delta / 120.0
        min_w = 240
        max_w = max(480, int(self.winfo_screenwidth() * 0.85))
        new_w = int(round(curr_w * (1.08 ** steps)))
        if new_w == curr_w:
            new_w = curr_w + (16 if wheel_delta > 0 else -16)
        new_w = max(min_w, min(max_w, new_w))
        new_h = max(135, int(round(new_w / ar)))

        rel_x = min(1.0, max(0.0, (mx - curr_x) / max(1, curr_w)))
        rel_y = min(1.0, max(0.0, (my - curr_y) / max(1, curr_h)))
        new_x = int(round(mx - rel_x * new_w))
        new_y = int(round(my - rel_y * new_h))

        self.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
        self._force_pip_zero_black_bars(new_w, new_h)

        if self._pip_drag_mode:
            self._pip_start_mouse = (mx, my)
            self._pip_start_rect = (new_x, new_y, new_w, new_h)

    def _poll_mouse_and_pip_interaction(self):
        if not self.app_running:
            return

        try:
            mx, my = self.winfo_pointerxy()
            now = time.time()

            if (mx, my) != self._last_mouse_pos:
                self._last_mouse_pos = (mx, my)
                self._last_mouse_move_ts = now
                if self.is_fullscreen:
                    self._show_fullscreen_hud()
                    if self.is_multiview:
                        self._set_multiview_controls_visible(True)

            lbutton_down = bool(GetAsyncKeyState(VK_LBUTTON) & 0x8000) if sys.platform.startswith("win") else False
            if self.is_fullscreen:
                idle_sec = now - self._last_mouse_move_ts
                hovering_hud = False
                if self.fs_hud_visible:
                    hx, hy = self.fs_hud.winfo_rootx(), self.fs_hud.winfo_rooty()
                    hw, hh = self.fs_hud.winfo_width(), self.fs_hud.winfo_height()
                    hovering_hud = (hx <= mx <= hx + hw) and (hy <= my <= hy + hh)
                if self.fs_hud_visible and not hovering_hud and not self.seeking_drag and not lbutton_down and idle_sec >= 2.5:
                    self._hide_fullscreen_hud()
                if self.is_multiview and self.config_data.get("mv_fs_autohide", True) and not self._mv_controls_hidden and not self.seeking_drag and not lbutton_down and idle_sec >= 2.5:
                    self._set_multiview_controls_visible(False)

            if self.is_pip:
                wx, wy = self.winfo_rootx(), self.winfo_rooty()
                ww, wh = self.winfo_width(), self.winfo_height()
                inside_pip = (wx <= mx <= wx + ww) and (wy <= my <= wy + wh)

                over_pip_hud = False
                if self.pip_hud_visible:
                    px, py = self.pip_hud.winfo_rootx(), self.pip_hud.winfo_rooty()
                    pw, ph = self.pip_hud.winfo_width(), self.pip_hud.winfo_height()
                    over_pip_hud = (px <= mx <= px + pw) and (py <= my <= py + ph)

                curr_x, curr_y, curr_w, curr_h = wx, wy, ww, wh

                if lbutton_down:
                    if not self._was_lbutton_down:
                        if inside_pip and not over_pip_hud:
                            zone, _ = self._detect_pip_hit_zone(mx, my, wx, wy, ww, wh)
                            self._pip_drag_mode = zone
                            self._pip_start_mouse = (mx, my)
                            self._pip_start_rect = (wx, wy, ww, wh)
                            self._get_video_aspect_ratio()
                    elif self._pip_drag_mode:
                        dx = mx - self._pip_start_mouse[0]
                        dy = my - self._pip_start_mouse[1]
                        sx, sy, sw_orig, sh_orig = self._pip_start_rect
                        ar = self.video_aspect_ratio

                        if self._pip_drag_mode == "move":
                            curr_x, curr_y, curr_w, curr_h = sx + dx, sy + dy, sw_orig, sh_orig
                            self.geometry(f"{curr_w}x{curr_h}+{curr_x}+{curr_y}")
                        else:
                            if self._pip_drag_mode in ("e", "se", "ne"):
                                new_w = max(240, sw_orig + dx)
                            elif self._pip_drag_mode in ("w", "sw", "nw"):
                                new_w = max(240, sw_orig - dx)
                            elif self._pip_drag_mode == "s":
                                new_h_tmp = max(135, sh_orig + dy)
                                new_w = max(240, int(round(new_h_tmp * ar)))
                            elif self._pip_drag_mode == "n":
                                new_h_tmp = max(135, sh_orig - dy)
                                new_w = max(240, int(round(new_h_tmp * ar)))
                            else:
                                new_w = sw_orig

                            new_h = max(135, int(round(new_w / ar)))
                            new_x = sx + (sw_orig - new_w) if "w" in self._pip_drag_mode else sx
                            new_y = sy + (sh_orig - new_h) if "n" in self._pip_drag_mode else sy
                            curr_x, curr_y, curr_w, curr_h = new_x, new_y, new_w, new_h
                            self.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
                            self._force_pip_zero_black_bars(new_w, new_h)
                else:
                    self._pip_drag_mode = None
                    if inside_pip and not over_pip_hud:
                        _, cur_name = self._detect_pip_hit_zone(mx, my, wx, wy, ww, wh)
                        self.video_canvas.configure(cursor=cur_name)
                    else:
                        self.video_canvas.configure(cursor="")

                self._was_lbutton_down = lbutton_down
                self._pip_wheel_capture_active = bool(self._pip_drag_mode) or (inside_pip and not over_pip_hud)

                with self._pip_wheel_lock:
                    wheel_delta = self._pip_wheel_delta
                    self._pip_wheel_delta = 0

                if wheel_delta and self._pip_wheel_capture_active:
                    self._resize_pip_by_wheel(wheel_delta, mx, my, curr_x, curr_y, curr_w, curr_h)

                if (inside_pip or over_pip_hud) and not self._pip_drag_mode and (now - self._last_mouse_move_ts <= 2.2):
                    self._show_pip_hud(wx, wy, ww, wh)
                else:
                    self._hide_pip_hud()
            else:
                self._pip_drag_mode = None
                self._was_lbutton_down = False
                self._pip_wheel_capture_active = False
                with self._pip_wheel_lock:
                    self._pip_wheel_delta = 0
                self._hide_pip_hud()

            # Overlay VOD su hover mouse: -10s (sx), ⏸/▶ (centro), +30s (dx), SOLO se finestra attiva e scoperta
            if self._is_vod_overlay_allowed(mx, my):
                vx = self.video_canvas.winfo_rootx()
                vy = self.video_canvas.winfo_rooty()
                vw = self.video_canvas.winfo_width()
                vh = self.video_canvas.winfo_height()
                over_canvas = (vw > 220 and vh > 140) and (vx <= mx <= vx + vw) and (vy <= my <= vy + vh)
                over_vod_pill = False
                if self.vod_hover_hud_visible:
                    for w_ov, _, _ in getattr(self, "_vod_hud_wins", []):
                        try:
                            ox, oy = w_ov.winfo_rootx(), w_ov.winfo_rooty()
                            ow, oh = w_ov.winfo_width(), w_ov.winfo_height()
                            if (ox <= mx <= ox + ow) and (oy <= my <= oy + oh):
                                over_vod_pill = True
                                break
                        except Exception:
                            pass
                if (over_canvas and (now - self._last_mouse_move_ts <= 2.2)) or over_vod_pill:
                    self._show_vod_hover_hud(vx, vy, vw, vh)
                else:
                    self._hide_vod_hover_hud()
            else:
                self._hide_vod_hover_hud()
        except Exception:
            pass

        self.after(25, self._poll_mouse_and_pip_interaction)

    def _show_vod_hover_hud(self, vx, vy, vw, vh):
        if not getattr(self, "_vod_hud_wins", None):
            return
        self._set_vod_center_paused_ui(self.is_paused)
        lw, lh = 78, 70
        cw, ch = 70, 70
        rw, rh = 78, 70
        hit_w, hit_h = 108, 98
        cy = vy + vh // 2
        lx_c = vx + max(hit_w // 2 + 12, int(vw * 0.14))
        cx_c = vx + vw // 2
        rx_c = vx + min(vw - hit_w // 2 - 12, int(vw * 0.86))

        pairs = getattr(self, "_vod_hud_pairs", [])
        centers = [(lx_c, cy, lw, lh), (cx_c, cy, cw, ch), (rx_c, cy, rw, rh)]
        for idx, (px_c, py_c, iw, ih) in enumerate(centers):
            if idx >= len(pairs):
                break
            hit_win, hw, hh, win, _, _ = pairs[idx]
            hit_win.geometry(f"{hw}x{hh}+{px_c - hw // 2}+{py_c - hh // 2}")
            win.geometry(f"{iw}x{ih}+{px_c - iw // 2}+{py_c - ih // 2}")
            if not self.vod_hover_hud_visible:
                hit_win.deiconify()
                win.deiconify()
                hit_win.lift()
                win.lift()
                if sys.platform.startswith("win"):
                    try:
                        SetWindowPos(hit_win.winfo_id(), 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | 0x0010)
                        SetWindowPos(win.winfo_id(), 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | 0x0010)
                    except Exception:
                        pass
        self.vod_hover_hud_visible = True

    def _hide_vod_hover_hud(self):
        if not getattr(self, "vod_hover_hud_visible", False):
            return
        for win, _, _ in getattr(self, "_vod_hud_wins", []):
            try:
                win.withdraw()
            except Exception:
                pass
        self.vod_hover_hud_visible = False

    def _show_fullscreen_hud(self):
        if not self.is_fullscreen:
            return
        if self.is_playing_vod:
            self.fs_seek_row.pack(side="top", fill="x", before=self.fs_ctrl_row)
            hud_w, hud_h = 800, 88
        else:
            self.fs_seek_row.pack_forget()
            hud_w, hud_h = 780, 52

        target_stage = self.multiview_frame if self.is_multiview else self.video_stage
        vx, vy = target_stage.winfo_rootx(), target_stage.winfo_rooty()
        vw, vh = target_stage.winfo_width(), target_stage.winfo_height()
        x = vx + max(10, (vw - hud_w) // 2)
        y = vy + vh - hud_h - 28
        self.fs_hud.geometry(f"{hud_w}x{hud_h}+{x}+{y}")
        if not self.fs_hud_visible:
            self.fs_hud.attributes("-topmost", True)
            self.fs_hud.deiconify()
            self.fs_hud.lift()
            self.fs_hud_visible = True

    def _hide_fullscreen_hud(self):
        if self.fs_hud_visible:
            self.fs_hud.attributes("-topmost", False)
            self.fs_hud.withdraw()
            self.fs_hud_visible = False

    def _show_pip_hud(self, vx, vy, vw, vh):
        pw = min(max(210, vw - 16), 260)
        ph = 34
        px = vx + (vw - pw) // 2
        py = vy + vh - ph - 8
        self.pip_hud.geometry(f"{pw}x{ph}+{px}+{py}")
        if not self.pip_hud_visible:
            self.pip_hud.attributes("-topmost", True)
            self.pip_hud.deiconify()
            self.pip_hud.lift()
            self.pip_hud_visible = True

    def _hide_pip_hud(self):
        if self.pip_hud_visible:
            self.pip_hud.attributes("-topmost", False)
            self.pip_hud.withdraw()
            self.pip_hud_visible = False

    def toggle_chat_in_fullscreen(self):
        self.chat_visible = not self.chat_visible
        if self.chat_visible:
            self.right_sidebar.pack(side="right", fill="y", before=self.center_stage)
            if self.is_multiview:
                self._refresh_multiview_chat_switcher()
        else:
            self.right_sidebar.pack_forget()
        self.update_idletasks()
        self._show_fullscreen_hud()

    def _bind_shortcuts(self):
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.exit_fullscreen())
        self.bind_all("<MouseWheel>", self._on_pip_tk_mouse_wheel, add="+")
        self.bind_all("<Button-4>", self._on_pip_tk_mouse_wheel, add="+")
        self.bind_all("<Button-5>", self._on_pip_tk_mouse_wheel, add="+")

    # =================================================================
    # RENDERING ATOMICO CON SIDEBAR BLOCCATA
    # =================================================================
    def _close_sidebar_popover(self):
        pop = getattr(self, "_sidebar_popover_win", None)
        self._sidebar_popover_win = None
        if pop is not None:
            try:
                if pop.winfo_exists():
                    pop.destroy()
            except Exception:
                pass

    def _on_nav_tab_click(self, tab_name):
        self._sidebar_visible_limit = 10
        self.nav_var.set(tab_name)
        self._refresh_nav_tab_styles()
        self.switch_sidebar_tab(tab_name)

    def _refresh_nav_tab_styles(self):
        cur = self.nav_var.get() if hasattr(self, "nav_var") else "Preferiti"
        btns = getattr(self, "_nav_tab_btns", None) or {}
        for name, btn in btns.items():
            try:
                if not btn.winfo_exists():
                    continue
                if name == "Multi-Live":
                    active_mv = bool(getattr(self, "is_multiview", False))
                    btn.configure(
                        fg_color=C_ACCENT if active_mv else "transparent",
                        hover_color=C_ACCENT_HOVER if active_mv else C_BG_CARD_HOVER,
                        text_color="#ffffff" if active_mv else C_TEXT_MAIN,
                        image=self._icon_multiview_active if active_mv else self._icon_multiview_idle,
                    )
                else:
                    is_sel = (name == cur)
                    btn.configure(
                        fg_color=C_ACCENT if is_sel else "transparent",
                        hover_color=C_ACCENT_HOVER if is_sel else C_BG_CARD_HOVER,
                        text_color="#ffffff" if is_sel else C_TEXT_MAIN,
                    )
            except Exception:
                pass

    def _sort_channels_list(self, channels):
        items = list(channels or [])
        mode = getattr(self, "_sort_mode", "viewers_desc")
        if mode == "viewers_asc":
            items.sort(key=lambda x: (not bool(x.get("is_live")), int(x.get("viewers") or 0), (x.get("login") or "").lower()))
        elif mode == "name_asc":
            items.sort(key=lambda x: (not bool(x.get("is_live")), (x.get("display_name") or x.get("login") or "").lower()))
        elif mode == "online_first":
            items.sort(key=lambda x: (not bool(x.get("is_live")), (x.get("login") or "").lower()))
        else:
            # viewers_desc (default)
            items.sort(key=lambda x: (not bool(x.get("is_live")), -int(x.get("viewers") or 0), (x.get("login") or "").lower()))
        return items

    def _open_sort_menu(self):
        self._close_sidebar_popover()
        pop = ctk.CTkToplevel(self)
        pop._deactivate_windows_window_header_manipulation = True
        self._sidebar_popover_win = pop
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(fg_color=C_BG_ROOT)

        box = ctk.CTkFrame(pop, fg_color=C_BG_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
        box.pack(fill="both", expand=True)

        options = [
            ("Spettatori (Decrescente)", "viewers_desc"),
            ("Spettatori (Crescente)", "viewers_asc"),
            ("Live prima", "online_first"),
            ("Nome (A → Z)", "name_asc"),
        ]
        cur_mode = getattr(self, "_sort_mode", "viewers_desc")

        def _pick(m):
            self._close_sidebar_popover()
            self._sort_mode = m
            self._sidebar_visible_limit = 10
            cur_tab = self.nav_var.get()
            if cur_tab == "Preferiti":
                self._render_channel_cards_locked(self.fav_data, is_fav_tab=True)
            elif cur_tab == "Seguiti":
                self._render_channel_cards_locked(self.followed_data, is_fav_tab=False)
            elif cur_tab == "Cerca":
                self._render_channel_cards_locked(self.search_data, is_fav_tab=False)

        for label, key in options:
            sel = (key == cur_mode)
            ctk.CTkButton(
                box,
                text=("●  " if sel else "   ") + label,
                height=32, corner_radius=7, anchor="w",
                fg_color=C_ACCENT if sel else "transparent",
                hover_color=C_ACCENT_HOVER if sel else C_BG_CARD_HOVER,
                text_color="#ffffff" if sel else C_TEXT_MAIN,
                font=ctk.CTkFont("Segoe UI", 11, "bold" if sel else "normal"),
                command=lambda m=key: _pick(m),
            ).pack(fill="x", padx=6, pady=2)

        try:
            self.update_idletasks()
            pop.update_idletasks()
            w = max(206, box.winfo_reqwidth() + 4)
            h = box.winfo_reqheight() + 4
            rx = self.sort_btn.winfo_rootx() + self.sort_btn.winfo_width() - w
            ry = self.sort_btn.winfo_rooty() + self.sort_btn.winfo_height() + 4
            pop.geometry(f"{w}x{h}+{max(8, rx)}+{max(8, ry)}")
        except Exception:
            pop.geometry("206x150")

        pop.bind("<Escape>", lambda e: self._close_sidebar_popover())
        pop.bind("<FocusOut>", lambda e: self.after(120, self._check_sidebar_popover_focus))
        pop.after(25, pop.focus_force)

    def _check_sidebar_popover_focus(self):
        pop = getattr(self, "_sidebar_popover_win", None)
        if pop is None or not pop.winfo_exists():
            return
        try:
            foc = self.focus_get()
            w = foc
            while w is not None:
                if w == pop:
                    return
                w = getattr(w, "master", None)
            self._close_sidebar_popover()
        except Exception:
            self._close_sidebar_popover()

    def _open_tags_popover(self, anchor_widget, all_tags):
        self._close_sidebar_popover()
        if not all_tags:
            return
        pop = ctk.CTkToplevel(self)
        pop._deactivate_windows_window_header_manipulation = True
        self._sidebar_popover_win = pop
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(fg_color=C_BG_ROOT)

        box = ctk.CTkFrame(pop, fg_color=C_BG_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
        box.pack(fill="both", expand=True)

        ctk.CTkLabel(
            box, text="Tag della live", font=ctk.CTkFont("Segoe UI", 10, "bold"),
            text_color=C_TEXT_DIM, anchor="w", height=16
        ).pack(fill="x", padx=10, pady=(8, 4))

        for tg in all_tags:
            ctk.CTkLabel(
                box, text=str(tg),
                fg_color=C_BG_INPUT, text_color=C_TEXT_MAIN,
                corner_radius=6, font=ctk.CTkFont("Segoe UI", 10),
                padx=8, pady=2, anchor="w",
            ).pack(anchor="w", padx=10, pady=2)

        ctk.CTkFrame(box, height=6, fg_color="transparent").pack()

        try:
            self.update_idletasks()
            pop.update_idletasks()
            w = max(168, box.winfo_reqwidth() + 12)
            h = box.winfo_reqheight() + 4
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            rx = max(8, min(anchor_widget.winfo_rootx(), sw - w - 8))
            ry = max(8, min(anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4, sh - h - 8))
            pop.geometry(f"{w}x{h}+{rx}+{ry}")
        except Exception:
            pop.geometry("180x140")

        pop.bind("<Escape>", lambda e: self._close_sidebar_popover())
        pop.bind("<FocusOut>", lambda e: self.after(120, self._check_sidebar_popover_focus))
        pop.after(25, pop.focus_force)

    def _open_card_context_menu(self, anchor_widget, item, is_fav):
        self._close_sidebar_popover()
        pop = ctk.CTkToplevel(self)
        pop._deactivate_windows_window_header_manipulation = True
        self._sidebar_popover_win = pop
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(fg_color=C_BG_ROOT)

        box = ctk.CTkFrame(pop, fg_color=C_BG_CARD, corner_radius=10, border_width=1, border_color=C_BORDER)
        box.pack(fill="both", expand=True)

        login_name = item["login"]
        is_live = bool(item.get("is_live"))
        has_vods = bool(item.get("has_vods", True))

        def _act(fn):
            self._close_sidebar_popover()
            self.after(15, fn)

        actions = []
        if is_live:
            actions.append(("Guarda Live", lambda: self.start_live_stream(login_name, item), C_ACCENT))
            actions.append(("Aggiungi a Multi-Live", lambda: self.add_channel_to_multiview(login_name, item), C_TEXT_MAIN))
        if has_vods:
            actions.append(("Apri Archivio VOD / Sub", lambda: self.fetch_vods_for_channel(login_name), C_TEXT_MAIN))
        actions.append((
            "Rimuovi dai Preferiti" if is_fav else "Aggiungi ai Preferiti",
            lambda: self.remove_favorite(login_name) if is_fav else self._add_single_favorite(login_name),
            C_GOLD if is_fav else C_TEXT_MAIN,
        ))
        actions.append(("Apri su Twitch", lambda: webbrowser.open(f"https://www.twitch.tv/{login_name}"), C_TEXT_DIM))

        for lbl, fn, col in actions:
            ctk.CTkButton(
                box, text=lbl, height=32, corner_radius=7, anchor="w",
                fg_color="transparent", hover_color=C_BG_CARD_HOVER,
                text_color=col, font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda f=fn: _act(f),
            ).pack(fill="x", padx=6, pady=2)

        try:
            self.update_idletasks()
            pop.update_idletasks()
            w = max(196, box.winfo_reqwidth() + 8)
            h = box.winfo_reqheight() + 6
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            rx = max(8, min(anchor_widget.winfo_rootx() + anchor_widget.winfo_width() - w, sw - w - 8))
            ry = max(8, min(anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4, sh - h - 8))
            pop.geometry(f"{w}x{h}+{rx}+{ry}")
        except Exception:
            pop.geometry("200x160")

        pop.bind("<Escape>", lambda e: self._close_sidebar_popover())
        pop.bind("<FocusOut>", lambda e: self.after(120, self._check_sidebar_popover_focus))
        pop.after(25, pop.focus_force)

    def _add_single_favorite(self, login):
        lg = login.strip().lower()
        favs = self.config_data.get("favorites", [])
        if lg and lg not in [f.lower() for f in favs]:
            favs.append(lg)
            self.config_data["favorites"] = favs
            self.save_config()
            self.refresh_favorites()

    def _set_add_fav_btn_visible(self, visible):
        w = getattr(self.add_fav_btn, "_shadow_wrap", self.add_fav_btn)
        ref = getattr(self._refresh_list_btn, "_shadow_wrap", self._refresh_list_btn)
        try:
            if visible:
                if not w.winfo_manager():
                    w.pack(side="right", padx=3, after=ref)
            else:
                if w.winfo_manager():
                    w.pack_forget()
        except Exception:
            pass

    def switch_sidebar_tab(self, tab_name):
        self._close_sidebar_popover()
        self._refresh_nav_tab_styles()
        if tab_name == "Preferiti":
            self.side_title_lbl.configure(text="Live")
            self._set_add_fav_btn_visible(True)
            self._render_channel_cards_locked(self.fav_data, is_fav_tab=True)
        elif tab_name == "Seguiti":
            self.side_title_lbl.configure(text="Seguiti")
            self._set_add_fav_btn_visible(False)
            if not self.config_data.get("oauth_token"):
                self._render_empty_message("Effettua il Login in alto a destra\nper sincronizzare i tuoi Streamer Seguiti!")
            elif not self.followed_data:
                self._lock_sidebar("⏳ Sincronizzazione canali seguiti...")
                self.refresh_followed()
            else:
                self._render_channel_cards_locked(self.followed_data, is_fav_tab=False)
        elif tab_name == "Cerca":
            self.side_title_lbl.configure(text="Risultati")
            self._set_add_fav_btn_visible(False)
            self._render_channel_cards_locked(self.search_data, is_fav_tab=False)
        elif tab_name == "VOD":
            ch_short = self.vods_channel_name[:14] if self.vods_channel_name else ""
            title = f"VOD • {ch_short}" if ch_short else "Archivio VOD"
            self.side_title_lbl.configure(text=title)
            self._set_add_fav_btn_visible(False)
            self._render_vod_cards_locked(self.vods_data)

    def _clear_cards(self):
        for w in self.cards_scroll.winfo_children():
            w.destroy()

    def _render_empty_message(self, msg):
        self._clear_cards()
        ctk.CTkLabel(
            self.cards_scroll, text=msg, font=ctk.CTkFont("Segoe UI", 12),
            text_color=C_TEXT_DIM, justify="center"
        ).pack(pady=40, padx=12)
        self._unlock_sidebar()

    def _render_channel_cards_locked(self, channels, is_fav_tab=False, animate=False):
        self._sidebar_render_seq += 1
        my_seq = self._sidebar_render_seq
        self._lock_sidebar("⏳ Caricamento canali...")

        def _build_all():
            if my_seq != self._sidebar_render_seq or not self.app_running:
                return
            self._clear_cards()
            sorted_ch = self._sort_channels_list(channels)
            if not sorted_ch:
                msg = "Nessun preferito salvato.\nUsa '＋' in alto o clicca la stellina su uno streamer!" if is_fav_tab else "Nessun canale da mostrare."
                self._render_empty_message(msg)
                return

            fav_set = {f.lower() for f in self.config_data.get("favorites", [])}
            cap = max(8, int(getattr(self, "_sidebar_visible_limit", 10)))
            visible_items = sorted_ch[:cap]
            remaining = len(sorted_ch) - len(visible_items)

            built_cards = []
            for item in visible_items:
                c_sh = self._create_single_channel_card(item, is_fav_tab, fav_set)
                if c_sh is not None:
                    built_cards.append(c_sh)

            # Pulsante Mostra altri in fondo alla lista
            def _on_show_more():
                if remaining > 0:
                    self._sidebar_visible_limit += 10
                    self._render_channel_cards_locked(channels, is_fav_tab=is_fav_tab)
                else:
                    self.refresh_all_lists()

            more_txt = f"Mostra altri ({remaining})  ▼" if remaining > 0 else "Mostra altri  ▼"
            more_btn = self._make_shadow_btn(
                self.cards_scroll,
                pack_kw={"fill": "x", "padx": 6, "pady": (6, 10)},
                offset_x=2, offset_y=3,
                text=more_txt,
                height=36,
                corner_radius=10,
                fg_color=C_BG_CARD,
                hover_color=C_BG_CARD_HOVER,
                border_width=1,
                border_color=C_BORDER,
                text_color=C_TEXT_MAIN,
                font=ctk.CTkFont("Segoe UI", 12, "bold"),
                command=_on_show_more,
            )

            # Pre-risolve layout e ombre sotto la tendina di caricamento così ogni card appare intera in un colpo solo
            try:
                self.cards_scroll.update_idletasks()
            except Exception:
                pass

            if animate and built_cards:
                try:
                    self.sidebar_lock_lbl.place_forget()
                    self.sidebar_lock_frame.place_configure(relx=0, rely=0.0, relwidth=1, relheight=1.0)
                    self.sidebar_lock_frame.lift()
                except Exception:
                    self._unlock_sidebar()
                    return

                def _wipe_step(step=1):
                    if my_seq != self._sidebar_render_seq or not self.app_running:
                        return
                    total = 7
                    if step <= total:
                        t = step / float(total)
                        ease = 1.0 - (1.0 - t) ** 2
                        try:
                            self.sidebar_lock_frame.place_configure(
                                relx=0, rely=ease, relwidth=1, relheight=max(0.0, 1.0 - ease)
                            )
                        except Exception:
                            self._unlock_sidebar()
                            return
                        self._sidebar_reveal_after = self.after(14, lambda s=step + 1: _wipe_step(s))
                    else:
                        self._sidebar_reveal_after = None
                        self._unlock_sidebar()

                self._sidebar_reveal_after = self.after(10, lambda: _wipe_step(1))
            else:
                self._unlock_sidebar()

        self.after(15, _build_all)

    def _create_single_channel_card(self, item, is_fav_tab, fav_set):
        is_live = bool(item.get("is_live"))
        has_vods = bool(item.get("has_vods", False))
        login_name = item["login"]
        disp_name = item.get("display_name") or login_name
        is_fav = login_name.lower() in fav_set
        tags = [str(t).strip() for t in (item.get("tags") or []) if str(t).strip()]
        card_h = 120 if (tags or has_vods) else 80

        card_sh_out, card = self._create_shadow_shell(
            self.cards_scroll, corner_radius=12, offset_x=4, offset_y=5,
            surface_fg=C_BG_CARD, border_color=C_BORDER, border_width=1, cursor="hand2",
            fixed_height=card_h, fixed_propagate=False,
            hover_border_color=("#9146FF", "#a855f7"),
            hover_glow_color=("#a855f7", "#9146FF"),
        )
        card_sh_out.pack(fill="x", padx=6, pady=4)

        card_bg_hex = _tk_color(C_BG_CARD)

        body = tk.Frame(card, bg=card_bg_hex, bd=0, highlightthickness=0)
        body._surface_fg_pair = C_BG_CARD
        body.pack(fill="x", padx=5, pady=6)

        # Colonna 1 (Estrema sinistra): Stellina preferiti
        star_col = tk.Frame(body, bg=card_bg_hex, bd=0, highlightthickness=0, width=28)
        star_col._surface_fg_pair = C_BG_CARD
        star_col.pack(side="left", fill="y", padx=(0, 6))

        star_btn = ctk.CTkButton(
            star_col,
            text="",
            image=self._icon_star_filled if is_fav else self._icon_star_outline,
            width=26, height=26,
            corner_radius=7,
            fg_color="transparent",
            bg_color=C_BG_CARD,
            hover_color=C_BG_CARD_HOVER,
        )
        star_btn.configure(command=lambda ch=login_name, b=star_btn: self.toggle_favorite_instant(ch, b))
        star_btn.pack(anchor="w", pady=(8, 0))

        # Colonna principale a destra della stellina: intestazione + avatar in alto, tag + VOD in basso sotto l'avatar
        right_col = tk.Frame(body, bg=card_bg_hex, bd=0, highlightthickness=0)
        right_col._surface_fg_pair = C_BG_CARD
        right_col.pack(side="left", fill="x", expand=True)

        top_sec = tk.Frame(right_col, bg=card_bg_hex, bd=0, highlightthickness=0)
        top_sec._surface_fg_pair = C_BG_CARD
        top_sec.pack(fill="x")

        # Avatar circolare dello streamer (42x42 px) senza sfondo quadrato dietro
        av_sz = 42
        init_img = self._get_circle_initial_ctk_img(disp_name, is_live, size=av_sz)
        avatar_lbl = ctk.CTkLabel(
            top_sec,
            text="",
            image=init_img,
            width=av_sz, height=av_sz,
            corner_radius=0,
            fg_color="transparent",
            bg_color=C_BG_CARD,
            cursor="hand2",
        )
        avatar_lbl._twixy_img = init_img
        avatar_lbl.pack(side="left", anchor="n", padx=(0, 10), pady=2)
        if item.get("avatar_url"):
            self._load_cached_thumb_async(
                avatar_lbl,
                item["avatar_url"],
                size=(av_sz, av_sz),
                circle=True,
                guard_win=self,
            )

        info_col = tk.Frame(top_sec, bg=card_bg_hex, bd=0, highlightthickness=0)
        info_col._surface_fg_pair = C_BG_CARD
        info_col.pack(side="left", fill="x", expand=True)

        # --- PRIMA RIGA: Nome in grassetto + pallino rosso grande + spettatori grandi a destra ---
        row1 = tk.Frame(info_col, bg=card_bg_hex, bd=0, highlightthickness=0)
        row1._surface_fg_pair = C_BG_CARD
        row1.pack(fill="x")

        v_txt = f"{item['viewers']:,}".replace(",", ".") if is_live else "-"
        viewers_lbl = ctk.CTkLabel(
            row1, text=v_txt,
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            fg_color="transparent",
            bg_color=C_BG_CARD,
            text_color=C_TEXT_MAIN if is_live else C_TEXT_DIM,
            height=22,
        )
        viewers_lbl.pack(side="right", padx=(5, 0))

        live_dot = ctk.CTkLabel(
            row1, text="●",
            font=ctk.CTkFont("Segoe UI", 17, "bold"),
            fg_color="transparent",
            bg_color=C_BG_CARD,
            text_color=("#ef4444", "#f43f5e") if is_live else C_TEXT_DIM,
            height=22,
        )
        live_dot.pack(side="right", padx=(6, 0))

        short_disp = disp_name if len(disp_name) <= 16 else disp_name[:15] + "…"
        name_lbl = ctk.CTkLabel(
            row1, text=short_disp,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color="transparent",
            bg_color=C_BG_CARD,
            text_color=C_TEXT_MAIN, anchor="w", cursor="hand2",
            height=22,
        )
        name_lbl.pack(side="left", fill="x", expand=True)

        # --- SECONDA RIGA: Icona viola + Categoria/Gioco + menu tre puntini ---
        row2 = tk.Frame(info_col, bg=card_bg_hex, bd=0, highlightthickness=0)
        row2._surface_fg_pair = C_BG_CARD
        row2.pack(fill="x", pady=(1, 1))

        dots_btn = ctk.CTkButton(
            row2, text="", image=self._icon_dots_vert,
            width=24, height=22, corner_radius=6,
            fg_color="transparent", bg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER,
        )
        dots_btn.configure(command=lambda ch=login_name, inf=item, btn=dots_btn: self._open_card_context_menu(
            btn, inf, ch.lower() in {f.lower() for f in self.config_data.get("favorites", [])}
        ))
        dots_btn.pack(side="right", padx=(3, 0))

        off_game = (item.get("game") or "").strip()
        if is_live:
            cat_text = off_game or "Just Chatting"
        elif off_game:
            cat_text = f"Offline • {off_game}"
        else:
            cat_text = "VOD / Sub" if has_vods else "Offline"
        cat_trim = cat_text if len(cat_text) <= 28 else cat_text[:27] + "…"
        cat_lbl = ctk.CTkLabel(
            row2,
            text=f" {cat_trim}",
            image=self._icon_game_purple,
            compound="left",
            font=ctk.CTkFont("Segoe UI", 11),
            fg_color="transparent",
            bg_color=C_BG_CARD,
            text_color=C_TEXT_DIM,
            anchor="w",
            height=20,
        )
        cat_lbl.pack(side="left", fill="x", expand=True)

        # --- TERZA RIGA (da sotto la foto profilo): Tag con ombra morbida + VOD fissato nell'angolo destro ---
        bottom_row = None
        tag_click_widgets = []
        if tags or has_vods:
            bottom_row = tk.Frame(right_col, bg=card_bg_hex, bd=0, highlightthickness=0, height=35)
            bottom_row._surface_fg_pair = C_BG_CARD
            bottom_row.pack(fill="x", pady=(6, 0))
            bottom_row.pack_propagate(False)

            if has_vods:
                self._make_shadow_btn(
                    bottom_row,
                    pack_kw={"side": "right", "padx": (6, 0), "pady": 1},
                    offset_x=2, offset_y=3,
                    text=" VOD", image=self._icon_play_white, compound="left",
                    width=56, height=23, corner_radius=7,
                    fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
                    font=ctk.CTkFont("Segoe UI", 10, "bold"),
                    command=lambda ch=login_name: self.fetch_vods_for_channel(ch),
                )

            if tags:
                if not hasattr(self, "_tag_measure_font"):
                    import tkinter.font as tkfont
                    self._tag_measure_font = tkfont.Font(family="Segoe UI", size=10)

                max_row_w = 272 if has_vods else 334
                plus_reserve = 60
                used_w = 0
                shown_idx = 0
                for idx, tg in enumerate(tags):
                    txt_w = self._tag_measure_font.measure(tg)
                    pill_w = txt_w + 28
                    has_more = (idx < len(tags) - 1)
                    needed = used_w + pill_w + (plus_reserve if has_more else 0)
                    if idx > 0 and needed > max_row_w:
                        break
                    tg_btn = self._make_shadow_btn(
                        bottom_row,
                        pack_kw={"side": "left", "padx": (0, 5), "pady": 1},
                        offset_x=2, offset_y=3,
                        text=tg,
                        width=txt_w + 18, height=22, corner_radius=7,
                        fg_color=C_BG_INPUT, hover_color=C_BG_CARD_HOVER,
                        text_color=C_TEXT_MAIN, border_width=0,
                        font=ctk.CTkFont("Segoe UI", 10),
                        command=lambda _c=None: None,
                    )
                    tag_click_widgets.append(tg_btn)
                    used_w += pill_w + 5
                    shown_idx = idx + 1

                hidden_cnt = len(tags) - shown_idx
                if hidden_cnt > 0:
                    plus_txt = f"+{hidden_cnt}"
                    plus_w = max(48, self._tag_measure_font.measure(plus_txt) + 28)
                    plus_btn = self._make_shadow_btn(
                        bottom_row,
                        pack_kw={"side": "left", "pady": 1},
                        offset_x=2, offset_y=3,
                        text=plus_txt,
                        width=plus_w, height=22, corner_radius=7,
                        fg_color=C_BG_INPUT, hover_color=C_BG_CARD_HOVER,
                        text_color=C_TEXT_MAIN,
                        font=ctk.CTkFont("Segoe UI", 10, "bold"),
                    )
                    plus_btn.configure(command=lambda b=plus_btn, tlist=tags: self._open_tags_popover(b, tlist))

        # Click sull'area della card apre la live (o i VOD se offline)
        def _open_stream(_evt=None, ch=login_name, inf=item, live_now=is_live, v_ok=has_vods):
            if live_now:
                self.start_live_stream(ch, inf)
            elif v_ok:
                self.fetch_vods_for_channel(ch)

        click_targets = [card, body, right_col, top_sec, avatar_lbl, info_col, row1, name_lbl, live_dot, viewers_lbl, row2, cat_lbl]
        if bottom_row is not None:
            click_targets.append(bottom_row)
            click_targets.extend(tag_click_widgets)
        for click_w in click_targets:
            click_w.bind("<Button-1>", _open_stream, add="+")
        card_sh_out.enable_hover_glow()
        return card_sh_out

    def toggle_favorite_instant(self, login, btn_widget):
        login_low = login.strip().lower()
        current_favs = [f.lower() for f in self.config_data.get("favorites", [])]
        if login_low in current_favs:
            self.config_data["favorites"] = [f for f in self.config_data["favorites"] if f.lower() != login_low]
            btn_widget.configure(image=self._icon_star_outline)
        else:
            self.config_data["favorites"].append(login_low)
            btn_widget.configure(image=self._icon_star_filled)
        self.save_config()
        self.refresh_favorites()

    def _render_vod_cards_locked(self, vods):
        self._lock_sidebar("⏳ Caricamento archivio VOD...")

        def _build_all():
            self._clear_cards()
            if not vods:
                self._render_empty_message("Seleziona uno streamer e clicca '📼 VOD / Sub'\nper esplorare le sue live passate.")
                return

            for v in vods:
                v_sh_out, card = self._create_shadow_shell(
                    self.cards_scroll, corner_radius=10, offset_x=4, offset_y=5,
                    surface_fg=C_BG_CARD, border_color=C_BORDER, border_width=1,
                    fixed_height=130, fixed_propagate=False,
                )
                v_sh_out.pack(fill="x", padx=5, pady=4)

                top_row = ctk.CTkFrame(card, fg_color="transparent")
                top_row.pack(fill="x", padx=4, pady=(2, 2))

                hrs, rem = divmod(v["duration"], 3600)
                mins, _ = divmod(rem, 60)

                if v["sub_only"]:
                    ctk.CTkLabel(
                        top_row, text=" SUB-ONLY ", fg_color=("#FEF3C7", "#3b2706"), text_color=C_GOLD,
                        corner_radius=5, font=ctk.CTkFont("Segoe UI", 9, "bold")
                    ).pack(side="left", padx=(0, 6))
                else:
                    ctk.CTkLabel(
                        top_row, text=" VOD ", fg_color=C_BG_INPUT, text_color=C_TEXT_DIM,
                        corner_radius=5, font=ctk.CTkFont("Segoe UI", 9, "bold")
                    ).pack(side="left", padx=(0, 6))

                ctk.CTkLabel(top_row, text=f"{v['created_at']} • {hrs}h {mins:02d}m", font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM).pack(side="left")
                ctk.CTkLabel(
                    top_row, text=f" {v['views']:,}".replace(",", "."),
                    image=self._icon_eye, compound="left",
                    font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM
                ).pack(side="right")

                title_short = v["title"] if len(v["title"]) <= 44 else v["title"][:42] + "…"
                ctk.CTkLabel(card, text=title_short, font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=C_TEXT_MAIN, anchor="w").pack(fill="x", padx=4, pady=(2, 0))
                ctk.CTkLabel(
                    card, text=f" {v['game']}",
                    image=self._icon_game_purple, compound="left",
                    font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM, anchor="w"
                ).pack(fill="x", padx=4, pady=(0, 4))

                self._make_shadow_btn(
                    card,
                    pack_kw={"fill": "x", "padx": 4, "pady": (2, 2)},
                    offset_x=2, offset_y=2,
                    text=" Riproduci VOD", image=self._icon_play_white, compound="left",
                    height=28, corner_radius=7,
                    fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
                    font=ctk.CTkFont("Segoe UI", 11, "bold"),
                    command=lambda vod_obj=v: self.start_vod_stream(vod_obj)
                )

            self._unlock_sidebar()

        self.after(15, _build_all)

    # =================================================================
    # LOGICA RIPRODUZIONE DUAL-ENGINE CON FILTRO ANTI-AD LOCALE
    # =================================================================
    def _stop_all_engines(self):
        if self.vlc_player:
            try:
                self.vlc_player.stop()
            except Exception:
                pass
        if self.mpv_proc:
            try:
                self.mpv_proc.terminate()
            except Exception:
                pass
            self.mpv_proc = None

    def on_engine_changed(self, chosen_engine):
        self.config_data["player_engine"] = chosen_engine
        self.save_config()
        if self.is_multiview and self.multi_tiles:
            for tile in list(self.multi_tiles):
                q = tile.get("selected_quality") or ""
                if q and q in tile.get("qualities", {}):
                    b_url = tile["backup_qualities"].get(q) or next(iter(tile["backup_qualities"].values()), "")
                    self._play_url_for_tile(tile, tile["qualities"][q], backup_url=b_url)
            return
        q = self.quality_var.get()
        if q in self.current_qualities:
            b_url = self.current_backup_qualities.get(q) or next(iter(self.current_backup_qualities.values()), "")
            self._play_url(self.current_qualities[q], backup_url=b_url)

    def _send_mpv_ipc(self, command_list, pipe_name=None):
        target_pipe = pipe_name or self.mpv_ipc_pipe
        if pipe_name is None and (not self.mpv_proc or self.mpv_proc.poll() is not None):
            return

        def _ipc_worker():
            try:
                payload = (json.dumps({"command": command_list}) + "\n").encode("utf-8")
                with open(target_pipe, "r+b", buffering=0) as pipe:
                    pipe.write(payload)
            except Exception:
                pass

        threading.Thread(target=_ipc_worker, daemon=True).start()

    def _query_mpv_ipc_property(self, prop_name, pipe_name=None):
        target_pipe = pipe_name or self.mpv_ipc_pipe
        try:
            payload = (json.dumps({"command": ["get_property", prop_name]}) + "\n").encode("utf-8")
            with open(target_pipe, "r+b", buffering=0) as pipe:
                pipe.write(payload)
                raw = pipe.readline()
            if raw:
                return json.loads(raw.decode("utf-8", errors="ignore")).get("data")
        except Exception:
            pass
        return None

    def _schedule_vlc_volume_sync(self, vp, vol_val, muted=False, check_fn=None):
        """Applica volume e stato mute al player VLC subito e dopo l'apertura del flusso audio."""
        if not vp:
            return

        def _sync_worker():
            for delay in (0.0, 0.25, 0.7, 1.4):
                if delay > 0:
                    time.sleep(delay)
                if not self.app_running:
                    return
                if check_fn and not check_fn():
                    return
                try:
                    vp.audio_set_mute(bool(muted))
                    vp.audio_set_volume(0 if muted else int(vol_val))
                except Exception:
                    pass

        threading.Thread(target=_sync_worker, daemon=True).start()

    def _play_url(self, stream_url, start_time_ms=0, backup_url="", req_id=None):
        if req_id is None:
            req_id = self._stream_request_id

        b_list = [u for u in self.current_backup_qualities.values() if u] if not self.is_playing_vod else []
        ch_for_refresh = self.current_channel
        q_for_refresh = self.quality_var.get()
        final_playback_url = self.engine.ad_stripper.set_target_stream(
            primary_url=stream_url,
            backup_url=backup_url,
            is_vod=self.is_playing_vod,
            backup_urls=b_list,
            refresh_cb=(lambda ch=ch_for_refresh, pq=q_for_refresh: self.engine.refresh_slot_urls(ch, pq)) if not self.is_playing_vod else None,
        )

        chosen_engine = self.engine_var.get()
        hwnd = self.video_canvas.winfo_id()
        try:
            vol_val = max(0, min(100, int(self.config_data.get("volume", self.vol_slider.get()))))
        except Exception:
            vol_val = int(self.vol_slider.get())
        self.vol_slider.set(vol_val)
        self.fs_vol_slider.set(vol_val)
        self.pip_vol_slider.set(vol_val)
        self.vol_pct_lbl.configure(
            text=f" {vol_val}%",
            image=self._icon_mute if vol_val == 0 else self._icon_volume,
        )
        is_pip_now = self.is_pip
        cw = max(16, self.video_canvas.winfo_width())
        ch = max(9, self.video_canvas.winfo_height())

        def _playback_worker():
            with self._playback_lock:
                if req_id != self._stream_request_id or not self.app_running:
                    return

                self._stop_all_engines()

                if req_id != self._stream_request_id or not self.app_running:
                    return

                if "MPV" in chosen_engine:
                    if not self.mpv_exe:
                        self.mpv_exe = find_mpv_executable(self.config_data.get("mpv_custom_dir"))
                    if self.mpv_exe:
                        args = [
                            self.mpv_exe,
                            f"--wid={hwnd}",
                            "--hwdec=auto",
                            "--vo=gpu",
                            "--framedrop=vo",
                            "--panscan=1.0" if is_pip_now else "--panscan=0.0",
                            "--keepaspect=yes",
                            "--mute=no",
                            f"--volume={vol_val}",
                            "--keep-open=yes",
                            "--osc=no",
                            "--input-default-bindings=no",
                            f"--input-ipc-server={self.mpv_ipc_pipe}"
                        ]
                        if start_time_ms > 0:
                            args.append(f"--start=+{start_time_ms / 1000.0:.1f}")
                        args.append(final_playback_url)
                        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                        self.mpv_proc = subprocess.Popen(args, creationflags=creation_flags)
                        self.is_paused = False
                        self._safe_ui(self._sync_play_pause_buttons)
                        return
                    else:
                        self._safe_ui(lambda: (
                            messagebox.showinfo("MPV non trovato", "mpv.exe non trovato: passo automaticamente al motore VLC integrato."),
                            self.engine_var.set("VLC (LibVLC)")
                        ))

                if not self.vlc_player:
                    self._init_video_engines()

                if self.vlc_player:
                    media = self.vlc_instance.media_new(final_playback_url)
                    self.vlc_player.set_media(media)
                    if sys.platform.startswith("win"):
                        self.vlc_player.set_hwnd(hwnd)
                    elif sys.platform.startswith("linux"):
                        self.vlc_player.set_xwindow(hwnd)
                    elif sys.platform == "darwin":
                        self.vlc_player.set_nsobject(hwnd)

                    if is_pip_now:
                        self._force_pip_zero_black_bars(cw, ch)
                    else:
                        self.vlc_player.video_set_aspect_ratio(None)
                        self.vlc_player.video_set_crop_geometry(None)

                    self.vlc_player.play()
                    self._schedule_vlc_volume_sync(
                        self.vlc_player, vol_val, muted=False,
                        check_fn=lambda r=req_id: r == self._stream_request_id
                    )
                    self.is_paused = False
                    self._safe_ui(self._sync_play_pause_buttons)

                    if start_time_ms and start_time_ms > 0:
                        self._safe_ui(lambda r=req_id, t=int(start_time_ms): self.after(800, lambda: self.vlc_player.set_time(t) if r == self._stream_request_id else None))
                    return

                self._safe_ui(lambda: self.open_vlc_setup_dialog(pending_url=stream_url, pending_time=start_time_ms))

        threading.Thread(target=_playback_worker, daemon=True).start()

    def _set_vod_seek_controls_visible(self, is_vod):
        try:
            b_wrap = getattr(self.seek_back_btn, "_shadow_wrap", self.seek_back_btn)
            f_wrap = getattr(self.seek_fwd_btn, "_shadow_wrap", self.seek_fwd_btn)
            anchor_w = getattr(self.clip_btn, "_shadow_wrap", self.stream_meta_lbl)
            if is_vod:
                if hasattr(self, "seek_back_btn") and not b_wrap.winfo_manager():
                    b_wrap.pack(side="left", padx=2, before=anchor_w)
                if hasattr(self, "seek_fwd_btn") and not f_wrap.winfo_manager():
                    f_wrap.pack(side="left", padx=2, before=anchor_w)
            else:
                self._hide_vod_hover_hud()
                if hasattr(self, "seek_back_btn") and b_wrap.winfo_manager():
                    b_wrap.pack_forget()
                if hasattr(self, "seek_fwd_btn") and f_wrap.winfo_manager():
                    f_wrap.pack_forget()
        except Exception:
            pass

    def start_live_stream(self, channel, stream_info=None):
        if self.is_multiview:
            self._exit_multiview_mode(preserve_focused=False)
        self.video_aspect_ratio = 16.0 / 9.0
        self._layout_video_canvas(force=True)
        self._stream_request_id += 1
        req_id = self._stream_request_id
        self.current_channel = channel.strip().lower()
        self.current_stream_info = stream_info or {"display_name": self.current_channel, "game": "Live", "title": ""}
        self.current_live_context = {}
        self._announced_poll_sig = None
        self._announced_pred_sig = None
        self._last_poll_render_sig = None
        self._last_pred_render_sig = None
        self.is_playing_vod = False
        self.current_vod_duration_sec = 0
        self._bg_curr_ms = 0
        self._bg_total_ms = 0
        self._bg_is_playing = False
        self._set_vod_seek_controls_visible(False)
        self._update_points_and_poll_ui()
        self._update_drops_badge_ui()

        self.badge_live_lbl.configure(text=" BUFFERING ", fg_color=C_GOLD, text_color="#000000")
        self.stream_meta_lbl.configure(text=f"Connessione a {self.current_channel} in corso...")

        self.clear_chat()
        self.chat_header_lbl.configure(text=f" #{self.current_channel.upper()}")
        self.emote_mgr.load_channel_assets(
            self.current_channel,
            "",
            oauth_token=self.engine.oauth_token,
            auth_client_id=self.engine.auth_client_id,
        )
        self.chat.connect_channel(
            self.current_channel,
            username=self.config_data.get("username"),
            oauth_token=self.config_data.get("oauth_token")
        )

        val = self.mode_var.get()
        if "Proxy" in val:
            mode = "proxy_first"
        elif "Embed" in val:
            mode = "direct_embed"
        else:
            mode = "xtra_direct"

        def worker():
            try:
                quals, backup_quals, badge_txt = self.engine.get_live_stream_qualities(self.current_channel, mode=mode)
                if req_id != self._stream_request_id or not self.app_running:
                    return
                self.after(0, lambda: self._apply_stream_ready(quals, badge_txt, is_vod=False, backup_quals=backup_quals, req_id=req_id) if req_id == self._stream_request_id else None)
                ctx = self.engine.fetch_channel_live_context(self.current_channel)
                if ctx and req_id == self._stream_request_id:
                    self.current_live_context = ctx
                    self.after(0, lambda: (self._update_points_and_poll_ui(), self._update_drops_badge_ui()))
                    self.emote_mgr.load_channel_assets(
                        self.current_channel,
                        ctx.get("channel_id", ""),
                        oauth_token=self.engine.oauth_token,
                        auth_client_id=self.engine.auth_client_id,
                    )
                    if ctx.get("channel_id") and ctx.get("broadcast_id"):
                        self.engine.send_minute_watched_heartbeat(
                            self.current_channel, ctx["channel_id"], ctx["broadcast_id"], ctx.get("game_name", "")
                        )
            except Exception as e:
                if req_id == self._stream_request_id and self.app_running:
                    self.after(0, lambda err=str(e): messagebox.showerror("Stream Offline", err))

        threading.Thread(target=worker, daemon=True).start()

    def start_vod_stream(self, vod_info):
        if self.is_multiview:
            self._exit_multiview_mode(preserve_focused=False)
        self.video_aspect_ratio = 16.0 / 9.0
        self._layout_video_canvas(force=True)
        self._stream_request_id += 1
        req_id = self._stream_request_id
        self.is_playing_vod = True
        self.current_live_context = {}
        self._announced_poll_sig = None
        self._announced_pred_sig = None
        self._last_poll_render_sig = None
        self._last_pred_render_sig = None
        self.current_vod_info = dict(vod_info or {})
        self.current_vod_duration_sec = int(vod_info.get("duration") or 0)
        self._bg_curr_ms = 0
        self._bg_total_ms = 0
        self._bg_is_playing = False
        self._set_vod_seek_controls_visible(True)
        self._update_points_and_poll_ui()
        self._update_drops_badge_ui()
        self.badge_live_lbl.configure(text=" SBLOCCO VOD ", fg_color=C_GOLD, text_color="#000000")
        self.stream_meta_lbl.configure(text=f"Caricamento VOD: {vod_info['title'][:55]}")

        def worker():
            try:
                quals, badge_txt = self.engine.get_vod_qualities(vod_info)
                if req_id != self._stream_request_id or not self.app_running:
                    return
                self.after(0, lambda: self._apply_stream_ready(quals, badge_txt, is_vod=True, vod_info=vod_info, req_id=req_id) if req_id == self._stream_request_id else None)
            except Exception as e:
                if req_id == self._stream_request_id and self.app_running:
                    self.after(0, lambda err=str(e): messagebox.showerror("Errore VOD", err))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_stream_ready(self, qualities_dict, shield_text, is_vod=False, vod_info=None, backup_quals=None, req_id=None):
        if req_id is not None and req_id != self._stream_request_id:
            return
        self.current_qualities = qualities_dict
        self.current_backup_qualities = backup_quals or {}
        q_names = list(qualities_dict.keys())
        self.quality_menu.configure(values=q_names)
        self.fs_quality_menu.configure(values=q_names)
        best_q = q_names[0]
        pref_q = self.config_data.get("default_quality", "Auto (Migliore)")
        if pref_q and pref_q != "Auto (Migliore)":
            pref_key = pref_q.split()[0].lower()
            matched_q = next((qn for qn in q_names if pref_key in qn.lower()), None)
            if matched_q:
                best_q = matched_q
        self.quality_var.set(best_q)
        self.shield_badge.configure(text=shield_text)

        self._set_vod_seek_controls_visible(bool(is_vod and vod_info))
        self._update_drops_badge_ui()

        if is_vod and vod_info:
            self.badge_live_lbl.configure(text=" VOD PLAYBACK ", fg_color=C_ACCENT, text_color="#ffffff")
            self.stream_meta_lbl.configure(text=f"{vod_info['title'][:60]}  •  {vod_info['game']}")
            self.seek_slider.set(0)
            self.fs_seek_slider.set(0)
            tot_hms = format_seconds_hms(self.current_vod_duration_sec)
            self.time_lbl.configure(text=f"00:00:00 / {tot_hms}")
            self.fs_time_lbl.configure(text=f"00:00:00 / {tot_hms}")
            self._play_url(qualities_dict[best_q], req_id=req_id)
        else:
            self.badge_live_lbl.configure(text=" ● LIVE 1080p ", fg_color=C_LIVE, text_color="#ffffff")
            inf = self.current_stream_info
            meta = f"{inf.get('display_name', self.current_channel)}"
            if inf.get("game"):
                meta += f"  •  {inf['game']}"
            if inf.get("title"):
                meta += f"  —  {inf['title'][:52]}"
            self.stream_meta_lbl.configure(text=meta)

            b_url = self.current_backup_qualities.get(best_q) or next(iter(self.current_backup_qualities.values()), "")
            self._play_url(qualities_dict[best_q], backup_url=b_url, req_id=req_id)

    def on_quality_changed(self, chosen_q):
        if self.is_multiview and self.multi_tiles and 0 <= self.multi_focused_idx < len(self.multi_tiles):
            tile = self.multi_tiles[self.multi_focused_idx]
            self._on_tile_quality_changed(tile, chosen_q)
            return
        if chosen_q in self.current_qualities:
            saved_ms = max(0, self._bg_curr_ms) if self.is_playing_vod else 0
            b_url = self.current_backup_qualities.get(chosen_q) or next(iter(self.current_backup_qualities.values()), "")
            self._play_url(self.current_qualities[chosen_q], start_time_ms=saved_ms, backup_url=b_url)

    # =================================================================
    # CONTROLLI PLAYBACK, LIVE SCRUBBING VOD & TELEMETRIA THREAD-SAFE
    # =================================================================
    def _get_effective_vod_total_seconds(self):
        if self._bg_total_ms > 0:
            return self._bg_total_ms // 1000
        return max(0, self.current_vod_duration_sec)

    def on_seek_drag(self, val):
        if not self.is_playing_vod:
            return
        self.seeking_drag = True
        pos_val = float(val)
        self.seek_slider.set(pos_val)
        self.fs_seek_slider.set(pos_val)

        total_sec = self._get_effective_vod_total_seconds()
        if total_sec > 0:
            target_sec = int((pos_val / 1000.0) * total_sec)
            txt = f"{format_seconds_hms(target_sec)} / {format_seconds_hms(total_sec)}"
            self.time_lbl.configure(text=txt, text_color=C_GOLD)
            self.fs_time_lbl.configure(text=txt, text_color=C_GOLD)

    def on_seek_release(self, event=None):
        if not self.is_playing_vod:
            self.seeking_drag = False
            return

        pct = (self.fs_seek_slider.get() if self.is_fullscreen else self.seek_slider.get()) / 1000.0
        pct = max(0.0, min(1.0, pct))
        self.seek_slider.set(pct * 1000.0)
        self.fs_seek_slider.set(pct * 1000.0)

        total_sec = self._get_effective_vod_total_seconds()
        target_ms = int(pct * total_sec * 1000)

        def _do_seek():
            if "MPV" in self.engine_var.get() and self.mpv_proc:
                self._send_mpv_ipc(["seek", pct * 100.0, "absolute-percent"])
            elif self.vlc_player:
                try:
                    if self._bg_total_ms > 0:
                        self.vlc_player.set_position(pct)
                    elif target_ms > 0:
                        self.vlc_player.set_time(target_ms)
                except Exception:
                    pass
            self._bg_curr_ms = target_ms
            self.seeking_drag = False

        threading.Thread(target=_do_seek, daemon=True).start()
        self.time_lbl.configure(text_color=C_TEXT_DIM)
        self.fs_time_lbl.configure(text_color=C_TEXT_MAIN)

    def _sync_play_pause_buttons(self):
        txt = " Play" if self.is_paused else " Pausa"
        ico = self._icon_play if self.is_paused else self._icon_pause
        self.play_btn.configure(text=txt, image=ico)
        self.fs_play_btn.configure(text=txt, image=ico)
        self.pip_play_btn.configure(text="", image=ico)
        self._set_vod_center_paused_ui(self.is_paused)

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        self._sync_play_pause_buttons()
        try:
            self.engine.ad_stripper.set_slot_paused("main", self.is_paused)
        except Exception:
            pass
        if self.is_multiview and self.multi_tiles:
            for tile in list(self.multi_tiles):
                if tile.get("mpv_proc") and tile["mpv_proc"].poll() is None:
                    self._send_tile_mpv_ipc(tile, ["set_property", "pause", self.is_paused])
                elif tile.get("vlc_player"):
                    threading.Thread(target=tile["vlc_player"].pause, daemon=True).start()
            return
        if "MPV" in self.engine_var.get() and self.mpv_proc:
            self._send_mpv_ipc(["set_property", "pause", self.is_paused])
        elif self.vlc_player:
            threading.Thread(target=self.vlc_player.pause, daemon=True).start()

    def seek_relative(self, delta_seconds):
        if not self.is_playing_vod:
            return
        if "MPV" in self.engine_var.get() and self.mpv_proc:
            self._send_mpv_ipc(["seek", delta_seconds, "relative"])
        elif self.vlc_player:
            def _rel_worker():
                try:
                    curr = self.vlc_player.get_time()
                    total = self.vlc_player.get_length() or (self.current_vod_duration_sec * 1000)
                    if curr >= 0:
                        new_t = max(0, min(total, curr + delta_seconds * 1000)) if total > 0 else max(0, curr + delta_seconds * 1000)
                        self.vlc_player.set_time(int(new_t))
                        self._bg_curr_ms = int(new_t)
                except Exception:
                    pass
            threading.Thread(target=_rel_worker, daemon=True).start()

    def on_volume_change(self, val):
        v = max(0, min(100, int(float(val))))
        self.vol_pct_lbl.configure(
            text=f" {v}%",
            image=self._icon_mute if v == 0 else self._icon_volume,
        )
        self.vol_slider.set(v)
        self.fs_vol_slider.set(v)
        self.pip_vol_slider.set(v)
        if self.is_multiview and self.multi_tiles and 0 <= self.multi_focused_idx < len(self.multi_tiles):
            tile = self.multi_tiles[self.multi_focused_idx]
            tile["volume"] = v
            if v > 0 and tile.get("muted"):
                tile["muted"] = False
            try:
                tile["vol_slider"].set(v)
            except Exception:
                pass
            self._apply_tile_audio(tile)
            return
        self.config_data["volume"] = v
        self._schedule_volume_save()
        if "MPV" in self.engine_var.get() and self.mpv_proc:
            self._send_mpv_ipc(["set_property", "mute", False])
            self._send_mpv_ipc(["set_property", "volume", v])
        elif self.vlc_player:
            def _apply_single_vol():
                try:
                    self.vlc_player.audio_set_mute(False)
                    self.vlc_player.audio_set_volume(v)
                except Exception:
                    pass
            threading.Thread(target=_apply_single_vol, daemon=True).start()

    def _background_player_telemetry_worker(self):
        last_recover_ts = 0.0
        while self.app_running:
            time.sleep(0.5)
            if self.vlc_player and "VLC" in self.config_data.get("player_engine", "VLC (LibVLC)"):
                try:
                    playing = bool(self.vlc_player.is_playing())
                    self._bg_is_playing = playing
                    if playing and self.is_playing_vod:
                        self._bg_total_ms = self.vlc_player.get_length()
                        if not self.seeking_drag:
                            self._bg_curr_ms = self.vlc_player.get_time()
                    elif (
                        not playing
                        and not self.is_playing_vod
                        and not self.is_paused
                        and not self.is_multiview
                        and self.current_channel
                    ):
                        st = self.vlc_player.get_state()
                        if st in (vlc.State.Ended, vlc.State.Error):
                            now = time.time()
                            if now - last_recover_ts >= 10.0:
                                last_recover_ts = now
                                ch_rec = self.current_channel
                                inf_rec = dict(self.current_stream_info or {})
                                self._safe_ui(lambda c=ch_rec, inf=inf_rec: self.start_live_stream(c, inf))
                except Exception:
                    pass

    def update_playback_telemetry_ui(self):
        if not self.app_running:
            return
        if self.state() != "iconic":
            if self._bg_is_playing and "VLC" in self.engine_var.get():
                self._probe_and_sync_video_aspect()
                if self.is_playing_vod:
                    total_sec = self._get_effective_vod_total_seconds()
                    curr_sec = max(0, self._bg_curr_ms // 1000)
                    if total_sec > 0 and not self.seeking_drag:
                        pos = min(1000.0, max(0.0, (curr_sec / total_sec) * 1000.0))
                        self.seek_slider.set(pos)
                        self.fs_seek_slider.set(pos)
                        txt = f"{format_seconds_hms(curr_sec)} / {format_seconds_hms(total_sec)}"
                        self.time_lbl.configure(text=txt)
                        self.fs_time_lbl.configure(text=txt)
                else:
                    self.seek_slider.set(1000)
                    blocked = self.engine.ad_stripper.ads_blocked_count
                    self.time_lbl.configure(text=f"LIVE • {blocked} Ads Blocked" if blocked else "● IN DIRETTA")
        self.after(500, self.update_playback_telemetry_ui)

    # =================================================================
    # MODALITÀ PIP FRAMELESS (SENZA BARRA WINDOWS, SCALA RIGIDA ZERO BARRE NERE)
    # =================================================================
    def toggle_pip_mode(self):
        if self.is_multiview:
            self._exit_multiview_mode(preserve_focused=True)
        if self.is_fullscreen:
            self.exit_fullscreen()

        self.is_pip = not self.is_pip
        if self.is_pip:
            self._close_account_bubble()
            self.close_inapp_menu(restore_chat=False)
            self._close_sidebar_popover()
            if getattr(self, "_clip_studio_open", False):
                self.close_clip_studio(restore_stage=True)

            self.saved_was_zoomed = (self.state() == "zoomed")
            if self.saved_was_zoomed:
                self.state("normal")
                self.update_idletasks()
            self.saved_normal_geometry = self.geometry()

            self.header.pack_forget()
            self.left_sidebar.pack_forget()
            self.right_sidebar.pack_forget()
            self.deck.pack_forget()

            ar = self._get_video_aspect_ratio()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()

            w = max(360, min(520, int(sw * 0.27)))
            h = max(202, int(round(w / ar)))
            x = sw - w - 28
            y = sh - h - 72

            self.minsize(200, 112)
            self.overrideredirect(True)
            self.attributes("-topmost", True)
            self.geometry(f"{w}x{h}+{x}+{y}")
            self.update_idletasks()
            self._layout_video_canvas(force=True)
            if sys.platform.startswith("win"):
                try:
                    hwnd_root = get_root_hwnd(self)
                    SetWindowPos(hwnd_root, -1, x, y, w, h, 0x0040)
                except Exception:
                    pass
            self._force_pip_zero_black_bars(w, h)
            self._start_pip_wheel_hook()
        else:
            self._stop_pip_wheel_hook()
            self._hide_pip_hud()
            self.video_canvas.configure(cursor="")
            self.attributes("-topmost", False)
            self.overrideredirect(False)
            self.minsize(1020, 620)

            if self.vlc_player:
                try:
                    self.vlc_player.video_set_aspect_ratio(None)
                    self.vlc_player.video_set_crop_geometry(None)
                except Exception:
                    pass
            if self.mpv_proc:
                self._send_mpv_ipc(["set_property", "panscan", 0.0])
                self._send_mpv_ipc(["set_property", "keepaspect", True])

            self.geometry(self.saved_normal_geometry)
            if getattr(self, "saved_was_zoomed", False):
                self.state("zoomed")
            apply_windows_enterprise_integration(self)
            _set_win_titlebar_theme(self, self.config_data.get("theme", "Dark"))

            self.header.pack(side="top", fill="x", before=self.workspace)
            if not self.is_theater:
                self.left_sidebar.pack(side="left", fill="y", before=self.center_stage)
            if self.chat_visible:
                self.right_sidebar.pack(side="right", fill="y", before=self.center_stage)
            self.deck.pack(side="bottom", fill="x")
            self.update_idletasks()
            self._layout_video_canvas(force=True)
        self._update_deck_toggle_styles()

    def toggle_theater_mode(self):
        if self.is_pip:
            self.toggle_pip_mode()
        self.is_theater = not self.is_theater
        if self.is_theater:
            self.left_sidebar.pack_forget()
        else:
            if not self.is_fullscreen:
                self.left_sidebar.pack(side="left", fill="y", before=self.center_stage)
        self._update_deck_toggle_styles()

    def toggle_fullscreen(self):
        if self.is_pip:
            self.toggle_pip_mode()

        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)
        if self.is_fullscreen:
            self.close_inapp_menu(restore_chat=False)
            self.header.pack_forget()
            self.left_sidebar.pack_forget()
            self.right_sidebar.pack_forget()
            self.chat_visible = False
            self.deck.pack_forget()
            self._last_mouse_move_ts = time.time()
            self._show_fullscreen_hud()
            if self.is_multiview:
                self._set_multiview_controls_visible(True)
        else:
            self._hide_fullscreen_hud()
            self.attributes("-topmost", False)
            self.header.pack(side="top", fill="x", before=self.workspace)
            if not self.is_theater:
                self.left_sidebar.pack(side="left", fill="y", before=self.center_stage)
            self.chat_visible = True
            self.right_sidebar.pack(side="right", fill="y", before=self.center_stage)
            self.deck.pack(side="bottom", fill="x")
            if self.is_multiview:
                self._set_multiview_controls_visible(True)
                self._refresh_multiview_chat_switcher()
        self._update_deck_toggle_styles()

    def exit_fullscreen(self):
        if getattr(self, "_account_bubble_open", False):
            self._close_account_bubble()
        elif self.is_fullscreen:
            self.toggle_fullscreen()
        elif self.is_pip:
            self.toggle_pip_mode()
        elif getattr(self, "_clip_studio_open", False):
            self.close_clip_studio()
        elif getattr(self, "_inapp_menu_open", False):
            self.close_inapp_menu()

    def toggle_chat(self):
        if getattr(self, "_inapp_menu_open", False):
            self.chat_visible = True
            self.close_inapp_menu(restore_chat=True)
            self._update_deck_toggle_styles()
            return
        self.chat_visible = not self.chat_visible
        if self.chat_visible:
            self.right_sidebar.pack(side="right", fill="y", before=self.center_stage)
        else:
            self.right_sidebar.pack_forget()
        self._update_deck_toggle_styles()

    # =================================================================
    # RICERCA, PREFERITI, SEGUITI E VOD
    # =================================================================
    def perform_streamer_search(self):
        q = self.search_entry.get().strip()
        if not q:
            return
        self._sidebar_visible_limit = 10
        self.nav_var.set("Cerca")
        self._refresh_nav_tab_styles()
        self._set_add_fav_btn_visible(False)
        self.side_title_lbl.configure(text=f"Cerca • {q[:14]}")
        self._lock_sidebar(f"⏳ Ricerca di '{q}' in corso...")

        def worker():
            try:
                res = self.engine.search_channels(q)
                self.search_data = res
                sorted_preview = self._sort_channels_list(res)
                cap = max(8, int(getattr(self, "_sidebar_visible_limit", 10)))
                av_urls = [it.get("avatar_url") for it in sorted_preview[:cap] if it.get("avatar_url")]
                if av_urls:
                    self._prefetch_thumbs_sync(av_urls, size=(42, 42), circle=True, timeout=1.1)
                self.after(0, lambda: self._render_channel_cards_locked(res, is_fav_tab=False, animate=True))
            except Exception as e:
                self.after(0, lambda: self._render_empty_message(f"Errore ricerca: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def fetch_vods_for_channel(self, channel):
        self.vods_channel_name = channel.strip().lower()
        self._sidebar_visible_limit = 10
        self.nav_var.set("VOD")
        self._refresh_nav_tab_styles()
        self._set_add_fav_btn_visible(False)
        self.side_title_lbl.configure(text=f"VOD • {self.vods_channel_name[:14]}")
        self._lock_sidebar(f"⏳ Caricamento VOD di {self.vods_channel_name}...")

        def worker():
            try:
                vods = self.engine.get_channel_vods(self.vods_channel_name)
                self.vods_data = vods
                self.after(0, lambda: self._render_vod_cards_locked(vods))
            except Exception as e:
                self.after(0, lambda: self._render_empty_message(f"Errore caricamento VOD: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_all_lists(self):
        self.refresh_favorites()
        if self.config_data.get("oauth_token"):
            self.refresh_followed()

    def refresh_favorites(self):
        favs = self.config_data.get("favorites", [])
        if not favs:
            self.fav_data = []
            if self.nav_var.get() == "Preferiti":
                self._render_channel_cards_locked([], is_fav_tab=True)
            return

        def worker():
            try:
                self.fav_data = self.engine.get_channels_status(favs)
                if self.nav_var.get() == "Preferiti":
                    self.after(0, lambda: self._render_channel_cards_locked(self.fav_data, is_fav_tab=True))
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    def refresh_followed(self):
        if not self.config_data.get("oauth_token"):
            return

        if self.nav_var.get() == "Seguiti":
            self._lock_sidebar("⏳ Aggiornamento canali seguiti...")

        def worker():
            try:
                uname, data = self.engine.get_followed_channels()
                if uname:
                    self.config_data["username"] = uname
                    self.config_data["auth_client_id"] = self.engine.auth_client_id
                    self.config_data["user_id"] = self.engine.user_id
                    self.save_config()
                    self.after(0, self._update_login_badge)
                self.followed_data = data
                if self.nav_var.get() == "Seguiti":
                    self.after(0, lambda: self._render_channel_cards_locked(self.followed_data, is_fav_tab=False))
            except Exception:
                if self.nav_var.get() == "Seguiti":
                    self.after(0, self._unlock_sidebar)

        threading.Thread(target=worker, daemon=True).start()

    def add_favorite(self, login):
        login = login.strip().lower()
        if login and login not in [f.lower() for f in self.config_data["favorites"]]:
            self.config_data["favorites"].append(login)
            self.save_config()
            self.refresh_favorites()

    def remove_favorite(self, login):
        self.config_data["favorites"] = [f for f in self.config_data["favorites"] if f.lower() != login.lower()]
        self.save_config()
        self.refresh_favorites()

    def prompt_add_favorite(self):
        dialog = ctk.CTkInputDialog(text="Inserisci l'username Twitch dello streamer:", title="Aggiungi Streamer Preferito")
        ch = dialog.get_input()
        if ch:
            self.add_favorite(ch)

    # =================================================================
    # LOGIN DIALOG
    # =================================================================
    def _update_login_badge(self):
        if self.config_data.get("oauth_token"):
            uname = self.config_data.get("username") or "Connesso"
            if hasattr(self, "account_dot_lbl"):
                self.account_dot_lbl.configure(text="●", image=None, text_color=C_GREEN)
            if hasattr(self, "account_name_lbl"):
                self.account_name_lbl.configure(text=uname, text_color=C_TEXT_MAIN)
            if hasattr(self, "account_pill"):
                self.account_pill.configure(border_color=C_BORDER)
        else:
            if hasattr(self, "account_dot_lbl"):
                self.account_dot_lbl.configure(text="", image=self._icon_user_accent)
            if hasattr(self, "account_name_lbl"):
                self.account_name_lbl.configure(text="Accedi", text_color=C_TEXT_MAIN)
            if hasattr(self, "account_pill"):
                self.account_pill.configure(border_color=C_ACCENT)

    def open_login_dialog(self):
        self.open_inapp_menu(tab="Account")

    def _complete_login(self, token, dlg=None, preferred_cid=None):
        token = token.replace("oauth:", "").strip()
        if not token:
            self.config_data.update({"oauth_token": "", "username": "", "user_id": "", "auth_client_id": GQL_CLIENT_ID})
            self.engine.oauth_token = ""
            self.engine.user_id = ""
            self.save_config()
            self._update_login_badge()
            if dlg and dlg.winfo_exists():
                dlg.destroy()
            if getattr(self, "_inapp_menu_open", False) and self._inapp_active_tab == "Account":
                self._switch_inapp_tab("Account")
            return

        def validate_worker():
            uname, cid, uid = self.engine.validate_oauth_token(token)
            if not uname and not cid:
                self.after(0, lambda: messagebox.showerror("Token Non Valido", "Il token inserito non è valido o è scaduto."))
                return

            final_cid = cid or preferred_cid or GQL_CLIENT_ID
            self.config_data.update({
                "oauth_token": token,
                "username": uname or "Utente",
                "user_id": uid or "",
                "auth_client_id": final_cid
            })
            self.engine.oauth_token = token
            self.engine.auth_client_id = final_cid
            self.engine.user_id = uid or ""
            self.save_config()

            def finish_ui():
                self._update_login_badge()
                self.nav_var.set("Seguiti")
                self.refresh_followed()
                if dlg and dlg.winfo_exists():
                    dlg.destroy()
                if getattr(self, "_inapp_menu_open", False) and self._inapp_active_tab == "Account":
                    self._switch_inapp_tab("Account")

            self.after(0, finish_ui)

        threading.Thread(target=validate_worker, daemon=True).start()

    def open_vlc_setup_dialog(self, pending_url=None, pending_time=0):
        self.open_inapp_menu(tab="Impostazioni", vlc_pending_url=pending_url, vlc_pending_time=pending_time)

    # =================================================================
    # CHAT HELPERS, BADGE GRAFICI & EMOTE (Twitch, 7TV, BTTV, FFZ)
    # =================================================================
    @staticmethod
    def _parse_twitch_emotes_tag(emotes_tag):
        spans = []
        if not emotes_tag:
            return spans
        for entry in emotes_tag.split("/"):
            if ":" not in entry:
                continue
            eid, ranges_str = entry.split(":", 1)
            for rng in ranges_str.split(","):
                if "-" not in rng:
                    continue
                try:
                    s_str, e_str = rng.split("-", 1)
                    spans.append((int(s_str), int(e_str), eid))
                except ValueError:
                    continue
        spans.sort(key=lambda x: x[0])
        return spans

    def _insert_pending_chat_image(self, fallback_text, cache_key, url, target_height=22, is_badge=False, trailing_space=""):
        if not fallback_text:
            self.emote_mgr.get_or_request_image(cache_key, url, target_height=target_height, is_badge=is_badge)
            return

        self._pending_emote_seq += 1
        ptag = f"_ep_{self._pending_emote_seq}"
        start_idx = self.chat_box.index("end-1c")
        self.chat_box.insert(tk.END, fallback_text)
        end_idx = self.chat_box.index("end-1c")
        self.chat_box.tag_add(ptag, start_idx, end_idx)
        self._pending_emote_tags.append(ptag)

        if trailing_space:
            self.chat_box.insert(tk.END, trailing_space)

        def _swap(_k, photo, t=ptag):
            if not self.app_running:
                return
            try:
                rng = self.chat_box.tag_ranges(t)
                if not rng or len(rng) < 2:
                    self.chat_box.tag_delete(t)
                    return
                was_disabled = (self.chat_box.cget("state") == tk.DISABLED)
                if was_disabled:
                    self.chat_box.config(state=tk.NORMAL)
                s_idx, e_idx = rng[0], rng[1]
                self.chat_box.delete(s_idx, e_idx)
                self.chat_box.image_create(s_idx, image=photo)
                self.chat_box.tag_delete(t)
                if was_disabled:
                    self.chat_box.config(state=tk.DISABLED)
            except Exception:
                try:
                    self.chat_box.tag_delete(t)
                except Exception:
                    pass

        self.emote_mgr.get_or_request_image(
            cache_key, url, target_height=target_height, is_badge=is_badge, on_loaded=_swap
        )

    def _insert_badges_inline(self, badges_tag):
        if not badges_tag:
            return
        fallback_icons = {
            "broadcaster": "👑",
            "moderator": "⚔️",
            "vip": "💎",
            "subscriber": "⭐",
            "founder": "⭐",
            "premium": "👑",
            "partner": "☑️",
        }
        for b in badges_tag.split(","):
            if "/" not in b:
                continue
            set_id, version = b.split("/", 1)
            set_id = set_id.strip()
            version = version.strip()
            if not set_id:
                continue
            info = self.emote_mgr.get_badge_info(set_id, version)
            if not info or not info.get("url"):
                fb = fallback_icons.get(set_id)
                if fb:
                    self.chat_box.insert(tk.END, fb + " ")
                continue
            url = info["url"]
            ck = f"badge:{set_id}/{version}:{url}"
            photo = self.emote_mgr.get_badge_photo(set_id, version, target_height=18)
            if photo:
                self.chat_box.image_create(tk.END, image=photo)
                self.chat_box.insert(tk.END, " ")
            else:
                fb = fallback_icons.get(set_id, "")
                self._insert_pending_chat_image(
                    fb, ck, url, target_height=18, is_badge=True, trailing_space=" " if fb else ""
                )

    def _insert_plain_with_named_emotes(self, segment):
        if not segment:
            return
        parts = segment.split(" ")
        for idx, tok in enumerate(parts):
            if idx > 0:
                self.chat_box.insert(tk.END, " ")
            em_info = self.emote_mgr.get_emote_info(tok) if tok else None
            if em_info and em_info.get("url"):
                url = em_info["url"]
                ck = f"name:{tok}:{url}"
                photo = self.emote_mgr.get_emote_photo(ck, url, target_height=22)
                if photo:
                    self.chat_box.image_create(tk.END, image=photo)
                else:
                    self._insert_pending_chat_image(tok, ck, url, target_height=22, is_badge=False)
            else:
                self.chat_box.insert(tk.END, tok)

    def _insert_text_with_emotes(self, msg, emotes_tag=""):
        spans = self._parse_twitch_emotes_tag(emotes_tag)
        if not spans:
            self._insert_plain_with_named_emotes(msg)
            return

        cursor = 0
        msg_len = len(msg)
        for start, end, eid in spans:
            if start < cursor or start >= msg_len:
                continue
            if start > cursor:
                self._insert_plain_with_named_emotes(msg[cursor:start])
            token_txt = msg[start:min(end + 1, msg_len)]
            url = f"https://static-cdn.jtvnw.net/emoticons/v2/{eid}/default/dark/1.0"
            if token_txt:
                self.emote_mgr.register_emote(token_txt, url, source="Twitch", is_channel=False)
            ck = f"tw:{eid}"
            photo = self.emote_mgr.get_emote_photo(ck, url, target_height=22)
            if photo:
                self.chat_box.image_create(tk.END, image=photo)
            else:
                self._insert_pending_chat_image(token_txt, ck, url, target_height=22, is_badge=False)
            cursor = end + 1

        if cursor < msg_len:
            self._insert_plain_with_named_emotes(msg[cursor:])

    def open_emote_picker(self):
        if self._emote_picker_win is not None:
            try:
                if self._emote_picker_win.winfo_exists():
                    if str(self._emote_picker_win.state()) in ("withdrawn", "iconic"):
                        self._emote_picker_win.deiconify()
                    self._emote_picker_win.lift()
                    self._emote_picker_win.focus_force()
                    return
            except Exception:
                self._emote_picker_win = None

        pop = ctk.CTkToplevel(self)
        pop._deactivate_windows_window_header_manipulation = True
        self._emote_picker_win = pop
        pop.title("Twixy — Selettore Emote (7TV / BTTV / FFZ / Twitch)")
        pop.geometry("400x440")
        pop.configure(fg_color=C_BG_SIDEBAR)
        pop.transient(self)
        _set_win_titlebar_theme(pop, self.config_data.get("theme", "Dark"))
        pop.bind("<Destroy>", lambda e: setattr(self, "_emote_picker_win", None) if (e.widget is pop and self._emote_picker_win is pop) else None)

        try:
            rx = self.right_sidebar.winfo_rootx()
            ry = self.right_sidebar.winfo_rooty() + max(30, self.right_sidebar.winfo_height() - 490)
            pop.geometry(f"400x440+{max(20, rx - 50)}+{max(20, ry)}")
        except Exception:
            pass

        search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            pop, textvariable=search_var, placeholder_text="🔍 Cerca emote (7TV, BTTV, FFZ, Twitch)...",
            fg_color=C_BG_INPUT, border_color=C_BORDER, text_color=C_TEXT_MAIN, height=32
        )
        search_entry.pack(fill="x", padx=10, pady=(10, 6))

        source_var = tk.StringVar(value="Tutte")
        src_seg = ctk.CTkSegmentedButton(
            pop,
            values=["Tutte", "Canale", "7TV", "BTTV", "FFZ", "Twitch"],
            variable=source_var,
            fg_color=C_BG_INPUT,
            selected_color=C_ACCENT,
            selected_hover_color=C_ACCENT_HOVER,
            unselected_color=C_BG_INPUT,
            unselected_hover_color=C_BG_CARD_HOVER,
            text_color=C_TEXT_MAIN,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            height=28,
        )
        src_seg.pack(fill="x", padx=10, pady=(0, 6))
        self._tracked_seg_bars.append(src_seg)
        self._style_segmented_tabs(src_seg)

        scroll = ctk.CTkScrollableFrame(pop, fg_color=C_BG_CARD, corner_radius=8)
        scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        if self._empty_emote_px is None:
            self._empty_emote_px = tk.PhotoImage(width=1, height=1)

        def _insert_emote(name):
            cur = self.chat_entry.get()
            spacer = " " if cur and not cur.endswith(" ") else ""
            self.chat_entry.insert(tk.END, f"{spacer}{name} ")
            self.chat_entry.focus_set()

        def _rebuild_grid(*_):
            if not pop.winfo_exists():
                return
            for w in scroll.winfo_children():
                w.destroy()

            flt = search_var.get().strip().lower()
            src_flt = source_var.get()
            if src_flt == "Canale":
                pool = self.emote_mgr.channel_emotes
            else:
                pool = self.emote_mgr.emote_catalog

            items = []
            for k, info in pool.items():
                if flt and flt not in k.lower():
                    continue
                if src_flt not in ("Tutte", "Canale") and info.get("source") != src_flt:
                    continue
                items.append((k, info.get("url", ""), info.get("source", "")))

            items = items[:80]
            if not items:
                ctk.CTkLabel(scroll, text="Nessuna emote trovata per questo filtro.", text_color=C_TEXT_DIM).pack(pady=30)
                return

            cols = 4
            for i, (name, url, _src) in enumerate(items):
                ck = f"name:{name}:{url}"
                photo = self.emote_mgr.get_emote_photo(ck, url, target_height=24)
                r_idx, c_idx = divmod(i, cols)
                btn = tk.Button(
                    scroll,
                    text=name[:11],
                    image=photo if photo else self._empty_emote_px,
                    compound="top",
                    font=("Segoe UI", 8),
                    bg=_tk_color(C_BG_INPUT), fg=_tk_color(C_TEXT_DIM),
                    activebackground=C_ACCENT, activeforeground="#ffffff",
                    relief=tk.FLAT, bd=0, padx=2, pady=3, width=78, height=52,
                    cursor="hand2",
                    command=lambda n=name: _insert_emote(n)
                )
                btn.image = photo if photo else self._empty_emote_px
                btn.grid(row=r_idx, column=c_idx, padx=4, pady=4, sticky="nsew")

                if not photo:
                    def _on_img(_k, new_photo, b=btn):
                        if pop.winfo_exists() and b.winfo_exists():
                            b.configure(image=new_photo, compound="top")
                            b.image = new_photo
                    self.emote_mgr.get_emote_photo(ck, url, target_height=24, on_loaded=_on_img)

        src_seg.configure(command=lambda _v: (self._style_segmented_tabs(src_seg), _rebuild_grid()))
        search_var.trace_add("write", _rebuild_grid)
        self.emote_mgr.load_channel_assets(
            self.current_channel or "",
            (self.current_live_context or {}).get("channel_id", ""),
            oauth_token=self.engine.oauth_token,
            auth_client_id=self.engine.auth_client_id,
            on_updated=_rebuild_grid,
        )
        _rebuild_grid()

    def clear_chat(self):
        while not self.chat_queue.empty():
            try:
                self.chat_queue.get_nowait()
            except Exception:
                break
        self.emote_mgr.clear_pending_callbacks()
        self.chat_line_count = 0
        self.chat_box.config(state=tk.NORMAL)
        self.chat_box.delete("1.0", tk.END)
        for t in self._pending_emote_tags:
            try:
                self.chat_box.tag_delete(t)
            except Exception:
                pass
        self._pending_emote_tags.clear()
        self.chat_box.config(state=tk.DISABLED)

    def _flush_chat_queue(self):
        if not self.app_running:
            return

        batch = []
        while len(batch) < 40:
            try:
                batch.append(self.chat_queue.get_nowait())
            except queue.Empty:
                break

        if batch:
            self.chat_box.config(state=tk.NORMAL)
            for item in batch:
                user = item[0]
                msg = item[1]
                color = item[2]
                emotes_tag = item[3] if len(item) >= 4 else ""
                badges_tag = item[4] if len(item) >= 5 else ""

                self._insert_badges_inline(badges_tag)

                tag = f"c_{id(color)}" if isinstance(color, (tuple, list)) else f"c_{color}"
                self._chat_tag_raw_colors[tag] = color
                try:
                    self.chat_box.tag_config(tag, foreground=_adapt_chat_color(color), font=("Segoe UI", 10, "bold"))
                except Exception:
                    self.chat_box.tag_config(tag, foreground=C_ACCENT, font=("Segoe UI", 10, "bold"))
                self.chat_box.insert(tk.END, f"{user}: ", tag)
                self._insert_text_with_emotes(msg, emotes_tag)
                self.chat_box.insert(tk.END, "\n")
                self.chat_line_count += 1

            if self.chat_line_count > 300:
                excess = self.chat_line_count - 250
                self.chat_box.delete("1.0", f"{excess}.0")
                self.chat_line_count = 250

            if len(self._pending_emote_tags) > 120:
                stale = self._pending_emote_tags[:-60]
                self._pending_emote_tags = self._pending_emote_tags[-60:]
                for t in stale:
                    try:
                        if not self.chat_box.tag_ranges(t):
                            self.chat_box.tag_delete(t)
                    except Exception:
                        pass

            if self.state() != "iconic" and self.chat_visible:
                self.chat_box.see(tk.END)
            self.chat_box.config(state=tk.DISABLED)

        self.after(200, self._flush_chat_queue)

    def send_chat(self):
        txt = self.chat_entry.get().strip()
        if txt and self.chat.send_chat_message(txt):
            self.chat_entry.delete(0, tk.END)

    # =================================================================
    # MODALITÀ MULTI-LIVE IN GRIGLIA (FINO A 4 STREAM SIMULTANEI)
    # =================================================================
    MAX_MULTI_TILES = 4

    def _build_multiview_container(self):
        self.multiview_frame = ctk.CTkFrame(self.center_stage, fg_color=C_VIDEO_LETTERBOX, corner_radius=0)

        mv_bar = ctk.CTkFrame(self.multiview_frame, fg_color=C_BG_HEADER, height=40, corner_radius=0, border_width=1, border_color=C_BORDER)
        mv_bar.pack(side="top", fill="x")
        mv_bar.pack_propagate(False)
        self.mv_bar = mv_bar

        self.mv_status_lbl = ctk.CTkLabel(
            mv_bar, text=" MULTI-LIVE (0/4) — Clicca un riquadro per aprire la chat e gestire l'audio",
            image=self._icon_multiview_idle, compound="left",
            font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_MAIN
        )
        self.mv_status_lbl.pack(side="left", padx=12)

        self._make_shadow_btn(
            mv_bar,
            pack_kw={"side": "right", "padx": (4, 10), "pady": 5},
            offset_x=2, offset_y=2,
            text=" Torna a Singola", image=self._icon_close, compound="left",
            width=122, height=26, corner_radius=6,
            fg_color=C_BG_CARD, hover_color=C_LIVE, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=lambda: self._exit_multiview_mode(preserve_focused=True)
        )

        self.mv_add_btn = self._make_shadow_btn(
            mv_bar,
            pack_kw={"side": "right", "padx": 4, "pady": 5},
            offset_x=2, offset_y=2,
            text=" Aggiungi Live", image=self._icon_plus_white, compound="left",
            width=116, height=26, corner_radius=6,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._open_add_multiview_dialog
        )

        self.mv_audio_mode_btn = self._make_shadow_btn(
            mv_bar,
            pack_kw={"side": "right", "padx": 6, "pady": 5},
            offset_x=2, offset_y=2,
            text=" Audio: Solo Attiva", image=self._icon_volume, compound="left",
            width=148, height=26, corner_radius=6,
            fg_color=("#E0F2FE", "#1f2937"), hover_color=C_ACCENT, text_color=C_CYAN,
            border_width=1, border_color=C_BORDER,
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._toggle_multiview_audio_mode
        )

        self.mv_grid_body = ctk.CTkFrame(self.multiview_frame, fg_color=("#D5D9E4", "#050507"), corner_radius=0)
        self.mv_grid_body.pack(side="top", fill="both", expand=True, padx=4, pady=4)

        self.mv_placeholder = ctk.CTkFrame(
            self.mv_grid_body, fg_color=C_BG_CARD, corner_radius=12, border_width=1, border_color=C_BORDER
        )
        ctk.CTkLabel(
            self.mv_placeholder, text=" Aggiungi Live alla Griglia",
            image=self._icon_multiview_idle, compound="left",
            font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=C_TEXT_MAIN
        ).pack(pady=(24, 6), padx=16)
        ctk.CTkLabel(
            self.mv_placeholder,
            text="Usa il menu a tre puntini su qualsiasi live nella barra a sinistra\noppure premi il pulsante qui sotto (fino a 4 live simultanee).",
            font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_DIM, justify="center"
        ).pack(pady=(0, 14), padx=16)
        self._make_shadow_btn(
            self.mv_placeholder,
            pack_kw={"pady": (0, 22)},
            offset_x=2, offset_y=2,
            text=" Aggiungi Streamer", image=self._icon_plus_white, compound="left",
            height=32, corner_radius=8,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self._open_add_multiview_dialog
        )

    def _update_multiview_header_badge(self):
        if not hasattr(self, "multiview_btn"):
            return
        n = len(self.multi_tiles)
        if self.is_multiview:
            self.multiview_btn.configure(text=f"Grid {n}/{self.MAX_MULTI_TILES}")
            if hasattr(self, "mv_status_lbl"):
                foc = self.multi_tiles[self.multi_focused_idx]["channel"] if (0 <= self.multi_focused_idx < n) else "--"
                self.mv_status_lbl.configure(
                    text=f" MULTI-LIVE ({n}/{self.MAX_MULTI_TILES})  •  Chat & Focus: #{foc.upper()}"
                )
        else:
            self.multiview_btn.configure(text="Multi-Live")
        self._refresh_nav_tab_styles()

    def _toggle_multiview_audio_mode(self):
        solo = not self.multi_solo_audio_var.get()
        self.multi_solo_audio_var.set(solo)
        self.mv_audio_mode_btn.configure(
            text=" Audio: Solo Attiva" if solo else " Audio: Mix Libero",
            text_color=C_CYAN if solo else C_GREEN
        )
        if solo and 0 <= self.multi_focused_idx < len(self.multi_tiles):
            for idx, tile in enumerate(self.multi_tiles):
                tile["muted"] = (idx != self.multi_focused_idx)
                self._apply_tile_audio(tile)

    def _open_add_multiview_dialog(self):
        if len(self.multi_tiles) >= self.MAX_MULTI_TILES:
            messagebox.showinfo("Griglia Piena", f"Puoi guardare fino a {self.MAX_MULTI_TILES} live contemporaneamente.\nChiudi una live (✕) prima di aggiungerne un'altra.")
            return

        pop = ctk.CTkToplevel(self)
        pop._deactivate_windows_window_header_manipulation = True
        pop.title("Aggiungi Live alla Griglia Multi-Live")
        pop.geometry("420x440")
        pop.configure(fg_color=C_BG_SIDEBAR)
        pop.transient(self)
        _set_win_titlebar_theme(pop, self.config_data.get("theme", "Dark"))
        pop.after(80, pop.lift)

        ctk.CTkLabel(pop, text="📺 Aggiungi Streamer (max 4 live)", font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=C_TEXT_MAIN).pack(pady=(14, 8))

        inp_row = ctk.CTkFrame(pop, fg_color="transparent")
        inp_row.pack(fill="x", padx=16, pady=4)
        ch_entry = ctk.CTkEntry(inp_row, placeholder_text="Nome canale Twitch...", fg_color=C_BG_INPUT, border_color=C_BORDER, text_color=C_TEXT_MAIN, height=34)
        ch_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def _submit_manual():
            val = ch_entry.get().strip().lower()
            if val:
                pop.destroy()
                self.add_channel_to_multiview(val)

        ch_entry.bind("<Return>", lambda _e: _submit_manual())
        ctk.CTkButton(inp_row, text="Aggiungi", width=84, height=34, fg_color=C_ACCENT, text_color="#ffffff", command=_submit_manual).pack(side="right")

        ctk.CTkLabel(pop, text="Oppure scegli dai tuoi Canali Live (Preferiti / Seguiti):", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_DIM, anchor="w").pack(fill="x", padx=16, pady=(12, 4))

        sc = ctk.CTkScrollableFrame(pop, fg_color="transparent")
        sc.pack(fill="both", expand=True, padx=12, pady=(2, 12))

        already = {t["channel"] for t in self.multi_tiles}
        live_pool = []
        seen = set()
        for src in (self.fav_data or []) + (self.followed_data or []):
            if src.get("is_live") and src.get("login"):
                lg = src["login"].lower()
                if lg not in seen and lg not in already:
                    seen.add(lg)
                    live_pool.append(src)

        if not live_pool:
            ctk.CTkLabel(sc, text="Nessun canale live extra nella lista locale.\nScrivi il nome dello streamer qui sopra.", font=ctk.CTkFont("Segoe UI", 11), text_color=C_TEXT_DIM, justify="center").pack(pady=24)
        else:
            for item in live_pool[:25]:
                row = ctk.CTkFrame(sc, fg_color=C_BG_CARD, corner_radius=8)
                row.pack(fill="x", padx=4, pady=3)
                info_txt = f"🔴 {item['display_name']}  •  {item.get('game') or 'Live'} ({item.get('viewers', 0)})"
                ctk.CTkLabel(row, text=info_txt, font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_MAIN, anchor="w").pack(side="left", padx=10, pady=8, fill="x", expand=True)
                ctk.CTkButton(
                    row, text="＋ Grid", width=66, height=26, corner_radius=6,
                    fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
                    command=lambda it=item: (pop.destroy(), self.add_channel_to_multiview(it["login"], it))
                ).pack(side="right", padx=8, pady=6)

    def toggle_multiview_mode(self):
        if self.is_multiview:
            self._exit_multiview_mode(preserve_focused=True)
        else:
            self._enter_multiview_mode(seed_channel=self.current_channel if not self.is_playing_vod else "")

    def _enter_multiview_mode(self, seed_channel=""):
        if self.is_pip:
            self.toggle_pip_mode()
        if self.is_multiview:
            return

        seed_info = dict(self.current_stream_info or {}) if seed_channel else {}
        seed_quals = dict(self.current_qualities or {}) if seed_channel else {}
        seed_bquals = dict(self.current_backup_qualities or {}) if seed_channel else {}
        seed_ctx = dict(self.current_live_context or {}) if seed_channel else {}
        seed_q_choice = self.quality_var.get() if seed_quals else ""

        self._stream_request_id += 1
        self._stop_all_engines()
        self.engine.ad_stripper.set_target_stream("", "", slot_id="main")
        self.is_playing_vod = False
        self.is_paused = False
        self._set_vod_seek_controls_visible(False)
        self._update_drops_badge_ui()
        self._sync_play_pause_buttons()

        self.video_stage.pack_forget()
        self.multiview_frame.pack(side="top", fill="both", expand=True, before=self.deck)
        self.is_multiview = True
        self._mv_controls_hidden = False
        self.multi_chat_idx = 0
        self._update_multiview_header_badge()
        self.update_idletasks()

        if seed_channel and not any(t["channel"] == seed_channel for t in self.multi_tiles):
            tile = self._create_multi_tile(seed_channel, seed_info)
            tile["live_ctx"] = seed_ctx
            self._relayout_multiview_grid()
            self.update_idletasks()
            self._focus_multiview_tile(0)
            if seed_quals and seed_q_choice in seed_quals:
                self._apply_tile_qualities(tile, seed_quals, seed_bquals, preferred_q=seed_q_choice)
            else:
                self._load_tile_stream_async(tile)
        else:
            self._relayout_multiview_grid()
            self.update_idletasks()

    def _exit_multiview_mode(self, preserve_focused=True):
        if not self.is_multiview:
            return

        target_ch = ""
        target_info = {}
        if preserve_focused and self.multi_tiles and 0 <= self.multi_focused_idx < len(self.multi_tiles):
            foc = self.multi_tiles[self.multi_focused_idx]
            target_ch = foc["channel"]
            target_info = dict(foc.get("stream_info") or {})

        for tile in list(self.multi_tiles):
            self._destroy_tile_resources(tile)
        self.multi_tiles.clear()
        self.multi_focused_idx = 0
        self.multi_chat_idx = 0
        self._set_multiview_controls_visible(True)

        self.multiview_frame.pack_forget()
        self.video_stage.pack(side="top", fill="both", expand=True, before=self.deck)
        self._layout_video_canvas(force=True)
        self.is_multiview = False
        self._update_multiview_header_badge()
        self._refresh_multiview_chat_switcher()

        if target_ch:
            self.start_live_stream(target_ch, target_info)

    def _set_multiview_controls_visible(self, visible):
        hidden = not bool(visible)
        if getattr(self, "_mv_controls_hidden", False) == hidden:
            return
        self._mv_controls_hidden = hidden
        if hidden and self.is_multiview:
            try:
                self.mv_bar.pack_forget()
                self.mv_grid_body.pack_configure(padx=0, pady=0)
                for tile in self.multi_tiles:
                    if tile.get("hdr"):
                        tile["hdr"].pack_forget()
                    if tile.get("ctrl_bar"):
                        tile["ctrl_bar"].pack_forget()
                    if tile.get("card"):
                        tile["card"].configure(border_width=0, corner_radius=0)
            except Exception:
                pass
        else:
            try:
                self.mv_grid_body.pack_configure(padx=4, pady=4)
                if not self.mv_bar.winfo_manager():
                    self.mv_bar.pack(side="top", fill="x", before=self.mv_grid_body)
                for idx, tile in enumerate(self.multi_tiles):
                    stage_w = tile.get("canvas_stage") or tile.get("canvas")
                    if tile.get("card"):
                        tile["card"].configure(
                            border_width=2,
                            corner_radius=8,
                            border_color=C_ACCENT if idx == self.multi_focused_idx else C_BORDER
                        )
                    if tile.get("hdr") and stage_w and not tile["hdr"].winfo_manager():
                        tile["hdr"].pack(side="top", fill="x", before=stage_w)
                    if tile.get("ctrl_bar") and stage_w and not tile["ctrl_bar"].winfo_manager():
                        tile["ctrl_bar"].pack(side="bottom", fill="x", before=stage_w)
            except Exception:
                pass

    def _refresh_multiview_chat_switcher(self):
        if not hasattr(self, "mv_chat_switcher"):
            return
        for w in self.mv_chat_switcher.winfo_children():
            w.destroy()

        if not self.is_multiview:
            self.mv_chat_switcher.pack_forget()
            return

        if not self.mv_chat_switcher.winfo_manager():
            self.mv_chat_switcher.pack(fill="x", side="top", after=self.chat_hdr)

        top_r = ctk.CTkFrame(self.mv_chat_switcher, fg_color="transparent")
        top_r.pack(fill="x", padx=8, pady=(5, 3))

        ctk.CTkLabel(
            top_r, text=" CHAT MULTI-LIVE", image=self._icon_chat, compound="left",
            font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=C_CYAN
        ).pack(side="left")

        n = len(self.multi_tiles)
        if n > 0:
            self.multi_chat_idx = max(0, min(self.multi_chat_idx, n - 1))

        self._make_shadow_btn(
            top_r,
            pack_kw={"side": "right"},
            offset_x=1, offset_y=2,
            text=" Cambia Chat", image=self._icon_swap, compound="left",
            width=108, height=24, corner_radius=6,
            fg_color=C_ACCENT if n > 1 else C_BG_CARD,
            hover_color=C_ACCENT_HOVER,
            state="normal" if n > 1 else "disabled",
            font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=self._cycle_multiview_chat
        )

        pills_r = ctk.CTkFrame(self.mv_chat_switcher, fg_color="transparent")
        pills_r.pack(fill="x", padx=6, pady=(0, 6))

        if n == 0:
            ctk.CTkLabel(
                pills_r, text="Aggiungi almeno 2 live per cambiare chat rapidamente",
                font=ctk.CTkFont("Segoe UI", 10), text_color=C_TEXT_DIM
            ).pack(side="left", padx=4)
            return

        for idx, tile in enumerate(self.multi_tiles):
            is_active = (idx == self.multi_chat_idx)
            ch_label = tile["channel"].upper()
            if len(ch_label) > 9:
                ch_label = ch_label[:8] + "…"
            self._make_shadow_btn(
                pills_r,
                pack_kw={"side": "left", "fill": "x", "expand": True, "padx": 2},
                offset_x=1, offset_y=2,
                text=f"#{ch_label}",
                height=24, width=64, corner_radius=6,
                fg_color=C_ACCENT if is_active else C_BG_CARD,
                hover_color=C_ACCENT_HOVER if is_active else C_BG_CARD_HOVER,
                border_width=1, border_color=C_CYAN if is_active else C_BORDER,
                text_color="#ffffff" if is_active else C_TEXT_DIM,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=lambda i=idx: self._switch_multiview_chat(i)
            )

    def _cycle_multiview_chat(self):
        if not self.is_multiview or len(self.multi_tiles) < 2:
            return
        next_idx = (self.multi_chat_idx + 1) % len(self.multi_tiles)
        self._switch_multiview_chat(next_idx)

    def _switch_multiview_chat(self, idx):
        if not self.is_multiview or idx < 0 or idx >= len(self.multi_tiles):
            return
        self.multi_chat_idx = idx
        tile = self.multi_tiles[idx]
        ch = tile["channel"]
        self.current_channel = ch
        self.current_stream_info = dict(tile.get("stream_info") or {"display_name": ch})
        self.current_live_context = dict(tile.get("live_ctx") or {})
        self._update_points_and_poll_ui()
        self._refresh_multiview_chat_switcher()

        if self.chat.current_channel != ch:
            self.clear_chat()
            self.chat_header_lbl.configure(text=f" #{ch.upper()}")
            self.emote_mgr.load_channel_assets(
                ch,
                self.current_live_context.get("channel_id", ""),
                oauth_token=self.engine.oauth_token,
                auth_client_id=self.engine.auth_client_id,
            )
            self.chat.connect_channel(
                ch,
                username=self.config_data.get("username"),
                oauth_token=self.config_data.get("oauth_token")
            )

    def add_channel_to_multiview(self, channel, stream_info=None):
        ch = channel.strip().lower()
        if not ch:
            return

        if not self.is_multiview:
            seed = self.current_channel if (self.current_channel and not self.is_playing_vod and self.current_channel != ch) else ""
            self._enter_multiview_mode(seed_channel=seed)

        for idx, tile in enumerate(self.multi_tiles):
            if tile["channel"] == ch:
                self._focus_multiview_tile(idx)
                return

        if len(self.multi_tiles) >= self.MAX_MULTI_TILES:
            messagebox.showwarning("Limite Multi-Live", f"Sono già aperte {self.MAX_MULTI_TILES} live simultanee.\nChiudine una (✕) per aggiungerne un'altra.")
            return

        tile = self._create_multi_tile(ch, stream_info or {"display_name": ch, "game": "Live", "title": ""})
        new_idx = len(self.multi_tiles) - 1
        self._relayout_multiview_grid()
        self._focus_multiview_tile(new_idx)
        self._load_tile_stream_async(tile)

    def _create_multi_tile(self, channel, stream_info):
        self._multi_slot_seq += 1
        slot_id = f"tile_{self._multi_slot_seq}"
        init_vol = int(self.config_data.get("volume", 80))
        is_first = (len(self.multi_tiles) == 0)

        card = ctk.CTkFrame(
            self.mv_grid_body, fg_color=C_VIDEO_LETTERBOX, corner_radius=8,
            border_width=2, border_color=C_ACCENT if is_first else C_BORDER
        )

        # Top header bar del riquadro
        hdr = ctk.CTkFrame(card, fg_color=C_BG_HEADER, height=28, corner_radius=0)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)

        hdr_lbl = ctk.CTkLabel(
            hdr, text=f" ⏳ #{channel.upper()}",
            font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_MAIN, anchor="w"
        )
        hdr_lbl.pack(side="left", padx=(8, 4), fill="x", expand=True)

        canvas_stage = ctk.CTkFrame(card, fg_color=C_VIDEO_LETTERBOX, corner_radius=0)
        canvas_stage.pack(side="top", fill="both", expand=True)

        canvas = tk.Canvas(canvas_stage, bg=_tk_color(C_VIDEO_LETTERBOX), highlightthickness=0, bd=0)
        canvas.place(anchor="nw", x=0, y=0, width=320, height=180)

        def _fit_tile_canvas(_e=None, stg=canvas_stage, cnv=canvas):
            try:
                sw = stg.winfo_width()
                sh = stg.winfo_height()
                if sw <= 10 or sh <= 10:
                    return
                ar = 16.0 / 9.0
                if float(sw) / float(sh) > ar:
                    fh = sh
                    fw = max(16, int(round(sh * ar)))
                else:
                    fw = sw
                    fh = max(9, int(round(sw / ar)))
                cnv.place_configure(
                    anchor="nw", relx=0.0, rely=0.0, relwidth=0.0, relheight=0.0,
                    x=(sw - fw) // 2, y=(sh - fh) // 2, width=fw, height=fh,
                )
            except Exception:
                pass

        canvas_stage.bind("<Configure>", _fit_tile_canvas)

        # Bottom control bar per riquadro (Qualità, Volume indipendente, Mute, Chat, Focus Singola)
        bar = ctk.CTkFrame(card, fg_color=C_BG_HEADER, height=34, corner_radius=0)
        bar.pack(side="bottom", fill="x", before=canvas_stage)
        bar.pack_propagate(False)

        tile = {
            "slot_id": slot_id,
            "channel": channel,
            "stream_info": dict(stream_info or {}),
            "qualities": {},
            "backup_qualities": {},
            "selected_quality": "",
            "volume": init_vol,
            "muted": False if is_first else bool(self.multi_solo_audio_var.get()),
            "vlc_inst": None,
            "vlc_player": None,
            "mpv_proc": None,
            "mpv_pipe": rf"\\.\pipe\twixy_mpv_{os.getpid()}_{slot_id}",
            "live_ctx": {},
            "req_id": 0,
            "card": card,
            "hdr": hdr,
            "hdr_lbl": hdr_lbl,
            "canvas_stage": canvas_stage,
            "canvas": canvas,
            "ctrl_bar": bar,
            "qual_menu": None,
            "mute_btn": None,
            "vol_slider": None,
            "vol_lbl": None,
        }

        def _focus_this(_evt=None, t=tile):
            if t in self.multi_tiles:
                self._focus_multiview_tile(self.multi_tiles.index(t))

        self._make_shadow_btn(
            hdr,
            pack_kw={"side": "right", "padx": (2, 6), "pady": 2},
            offset_x=1, offset_y=2,
            text="", image=self._icon_close, width=24, height=20, corner_radius=5,
            fg_color=C_BG_CARD, hover_color=C_LIVE, text_color=C_TEXT_DIM,
            border_width=1, border_color=C_BORDER,
            command=lambda t=tile: self._remove_multi_tile(t)
        )

        self._make_shadow_btn(
            hdr,
            pack_kw={"side": "right", "padx": 2, "pady": 2},
            offset_x=1, offset_y=2,
            text="", image=self._icon_expand, width=24, height=20, corner_radius=5,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            command=lambda t=tile: self._promote_multi_tile_to_single(t)
        )

        qual_menu = ctk.CTkOptionMenu(
            bar, values=["Auto"], width=102, height=24, corner_radius=6,
            fg_color=C_BG_CARD, button_color=C_BG_INPUT, button_hover_color=C_ACCENT,
            text_color=C_TEXT_MAIN,
            font=ctk.CTkFont("Segoe UI", 10),
            command=lambda q, t=tile: self._on_tile_quality_changed(t, q)
        )
        qual_menu.pack(side="left", padx=(6, 4), pady=4)
        tile["qual_menu"] = qual_menu

        mute_btn = self._make_shadow_btn(
            bar,
            pack_kw={"side": "left", "padx": 2, "pady": 3},
            offset_x=1, offset_y=2,
            text="", image=self._icon_mute if tile["muted"] else self._icon_volume,
            width=28, height=24, corner_radius=6,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER,
            command=lambda t=tile: self._toggle_tile_mute(t)
        )
        tile["mute_btn"] = mute_btn

        vol_slider = ctk.CTkSlider(
            bar, from_=0, to=100, width=95, height=12,
            fg_color=C_BG_INPUT, progress_color=C_GREEN, button_color=("#059669", "#ffffff"),
            command=lambda val, t=tile: self._set_tile_volume(t, val)
        )
        vol_slider.set(init_vol)
        vol_slider.pack(side="left", padx=4, pady=4)
        tile["vol_slider"] = vol_slider

        vol_lbl = ctk.CTkLabel(
            bar, text=f"{init_vol}%", width=34,
            font=ctk.CTkFont("Consolas", 10), text_color=C_TEXT_DIM
        )
        vol_lbl.pack(side="left", padx=(2, 6))
        tile["vol_lbl"] = vol_lbl

        hdr_lbl.bind("<Button-1>", _focus_this)
        canvas_stage.bind("<Button-1>", _focus_this)
        canvas_stage.bind("<Double-Button-1>", lambda _e, t=tile: self._promote_multi_tile_to_single(t))
        canvas.bind("<Button-1>", _focus_this)
        canvas.bind("<Double-Button-1>", lambda _e, t=tile: self._promote_multi_tile_to_single(t))

        self.multi_tiles.append(tile)
        self._set_multiview_controls_visible(True)
        return tile

    def _relayout_multiview_grid(self):
        if not self.is_multiview:
            return
        for child in self.mv_grid_body.winfo_children():
            child.grid_forget()

        for col in range(2):
            self.mv_grid_body.grid_columnconfigure(col, weight=0, uniform="")
        for row in range(2):
            self.mv_grid_body.grid_rowconfigure(row, weight=0, uniform="")

        n = len(self.multi_tiles)
        if n == 0:
            self.mv_grid_body.grid_columnconfigure(0, weight=1, uniform="mv_col")
            self.mv_grid_body.grid_rowconfigure(0, weight=1, uniform="mv_row")
            self.mv_placeholder.grid(row=0, column=0, sticky="nsew", padx=40, pady=40)
        elif n == 1:
            self.mv_grid_body.grid_columnconfigure(0, weight=1, uniform="mv_col")
            self.mv_grid_body.grid_columnconfigure(1, weight=1, uniform="mv_col")
            self.mv_grid_body.grid_rowconfigure(0, weight=1, uniform="mv_row")
            self.multi_tiles[0]["card"].grid(row=0, column=0, sticky="nsew", padx=3, pady=3)
            self.mv_placeholder.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        elif n == 2:
            self.mv_grid_body.grid_columnconfigure(0, weight=1, uniform="mv_col")
            self.mv_grid_body.grid_columnconfigure(1, weight=1, uniform="mv_col")
            self.mv_grid_body.grid_rowconfigure(0, weight=1, uniform="mv_row")
            for idx, tile in enumerate(self.multi_tiles):
                tile["card"].grid(row=0, column=idx, sticky="nsew", padx=3, pady=3)
        else:
            for c in range(2):
                self.mv_grid_body.grid_columnconfigure(c, weight=1, uniform="mv_col")
            for r in range(2):
                self.mv_grid_body.grid_rowconfigure(r, weight=1, uniform="mv_row")
            for idx, tile in enumerate(self.multi_tiles):
                tile["card"].grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=3, pady=3)
            if n == 3:
                self.mv_placeholder.grid(row=1, column=1, sticky="nsew", padx=8, pady=8)

        self._update_multiview_header_badge()
        self._refresh_multiview_chat_switcher()

    def _load_tile_stream_async(self, tile):
        tile["req_id"] += 1
        req_id = tile["req_id"]
        ch = tile["channel"]

        val = self.mode_var.get()
        if "Proxy" in val:
            mode = "proxy_first"
        elif "Embed" in val:
            mode = "direct_embed"
        else:
            mode = "xtra_direct"

        def _worker():
            try:
                quals, backup_quals, _badge_txt = self.engine.get_live_stream_qualities(ch, mode=mode)
                if not self.app_running or tile not in self.multi_tiles or req_id != tile["req_id"]:
                    return
                self._safe_ui(lambda: self._apply_tile_qualities(tile, quals, backup_quals))
                ctx = self.engine.fetch_channel_live_context(ch)
                if ctx and tile in self.multi_tiles and req_id == tile["req_id"]:
                    tile["live_ctx"] = ctx
                    if 0 <= self.multi_chat_idx < len(self.multi_tiles) and self.multi_tiles[self.multi_chat_idx] is tile:
                        self.current_live_context = ctx
                        self._safe_ui(self._update_points_and_poll_ui)
                        self.emote_mgr.load_channel_assets(
                            ch, ctx.get("channel_id", ""),
                            oauth_token=self.engine.oauth_token,
                            auth_client_id=self.engine.auth_client_id,
                        )
                    if ctx.get("channel_id") and ctx.get("broadcast_id"):
                        self.engine.send_minute_watched_heartbeat(ch, ctx["channel_id"], ctx["broadcast_id"], ctx.get("game_name", ""))
            except Exception as e:
                if self.app_running and tile in self.multi_tiles and req_id == tile["req_id"]:
                    self._safe_ui(lambda err=str(e): tile["hdr_lbl"].configure(text=f" ✕ #{ch.upper()} (Offline/Err)", text_color=C_LIVE))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_tile_qualities(self, tile, quals, backup_quals, preferred_q=""):
        if tile not in self.multi_tiles or not quals:
            return
        tile["qualities"] = quals
        tile["backup_qualities"] = backup_quals or {}
        q_names = list(quals.keys())
        tile["qual_menu"].configure(values=q_names)

        # Se ci sono 2+ live, preferisci 720p60 sui riquadri secondari se non specificato (o la migliore)
        chosen = preferred_q if preferred_q in quals else q_names[0]
        if not preferred_q and len(self.multi_tiles) > 1 and tile is not self.multi_tiles[0]:
            chosen_720 = next((qn for qn in q_names if "720" in qn), None)
            if chosen_720:
                chosen = chosen_720
        tile["selected_quality"] = chosen
        tile["qual_menu"].set(chosen)

        g = (tile.get("stream_info") or {}).get("game") or ""
        g_suffix = f" • {g}" if g else ""
        tile["hdr_lbl"].configure(text=f" ● #{tile['channel'].upper()}{g_suffix}", text_color=C_TEXT_MAIN)

        b_url = tile["backup_qualities"].get(chosen) or next(iter(tile["backup_qualities"].values()), "")
        self._play_url_for_tile(tile, quals[chosen], backup_url=b_url)

    def _on_tile_quality_changed(self, tile, chosen_q):
        if tile not in self.multi_tiles or chosen_q not in tile["qualities"]:
            return
        tile["selected_quality"] = chosen_q
        tile["qual_menu"].set(chosen_q)
        b_url = tile["backup_qualities"].get(chosen_q) or next(iter(tile["backup_qualities"].values()), "")
        self._play_url_for_tile(tile, tile["qualities"][chosen_q], backup_url=b_url)
        if 0 <= self.multi_focused_idx < len(self.multi_tiles) and self.multi_tiles[self.multi_focused_idx] is tile:
            self.quality_var.set(chosen_q)

    def _stop_tile_players(self, tile):
        if tile.get("vlc_player"):
            try:
                tile["vlc_player"].stop()
            except Exception:
                pass
        if tile.get("mpv_proc"):
            try:
                tile["mpv_proc"].terminate()
            except Exception:
                pass
            tile["mpv_proc"] = None

    def _destroy_tile_resources(self, tile):
        tile["req_id"] += 1
        self._stop_tile_players(tile)
        if tile.get("vlc_player"):
            try:
                tile["vlc_player"].release()
            except Exception:
                pass
            tile["vlc_player"] = None
        if tile.get("vlc_inst"):
            try:
                tile["vlc_inst"].release()
            except Exception:
                pass
            tile["vlc_inst"] = None
        self.engine.ad_stripper.clear_slot(tile["slot_id"])
        try:
            tile["card"].destroy()
        except Exception:
            pass

    def _send_tile_mpv_ipc(self, tile, command_list):
        proc = tile.get("mpv_proc")
        if not proc or proc.poll() is not None:
            return
        pipe_name = tile["mpv_pipe"]

        def _w():
            try:
                payload = (json.dumps({"command": command_list}) + "\n").encode("utf-8")
                with open(pipe_name, "r+b", buffering=0) as p:
                    p.write(payload)
            except Exception:
                pass

        threading.Thread(target=_w, daemon=True).start()

    def _play_url_for_tile(self, tile, stream_url, backup_url=""):
        if tile not in self.multi_tiles:
            return
        slot_id = tile["slot_id"]
        req_id = tile["req_id"]
        t_backups = [u for u in (tile.get("backup_qualities") or {}).values() if u]
        t_ch = tile.get("channel", "")
        t_pq = tile.get("selected_quality", "")
        final_url = self.engine.ad_stripper.set_target_stream(
            primary_url=stream_url,
            backup_url=backup_url,
            is_vod=False,
            slot_id=slot_id,
            backup_urls=t_backups,
            refresh_cb=lambda ch=t_ch, pq=t_pq: self.engine.refresh_slot_urls(ch, pq),
        )
        chosen_engine = self.engine_var.get()
        try:
            tile["canvas"].update_idletasks()
            if tile["canvas"].winfo_width() <= 1 or tile["canvas"].winfo_height() <= 1:
                if not tile.get("_hwnd_retry_pending"):
                    tile["_hwnd_retry_pending"] = True
                    self.after(60, lambda t=tile, u=stream_url, b=backup_url, r=req_id: (
                        t.update({"_hwnd_retry_pending": False}),
                        self._play_url_for_tile(t, u, backup_url=b) if (t in self.multi_tiles and t.get("req_id") == r) else None
                    ))
                    return
            tile["_hwnd_retry_pending"] = False
            hwnd = tile["canvas"].winfo_id()
        except Exception:
            return
        eff_vol = 0 if tile.get("muted") else int(tile.get("volume", 80))

        def _worker():
            if not self.app_running or tile not in self.multi_tiles or req_id != tile["req_id"]:
                return
            self._stop_tile_players(tile)

            if "MPV" in chosen_engine:
                if not self.mpv_exe:
                    self.mpv_exe = find_mpv_executable(self.config_data.get("mpv_custom_dir"))
                if self.mpv_exe:
                    args = [
                        self.mpv_exe,
                        f"--wid={hwnd}",
                        "--hwdec=auto",
                        "--vo=gpu",
                        "--framedrop=vo",
                        "--keepaspect=yes",
                        f"--volume={eff_vol}",
                        f"--mute={'yes' if tile.get('muted') else 'no'}",
                        "--keep-open=yes",
                        "--osc=no",
                        "--input-default-bindings=no",
                        f"--input-ipc-server={tile['mpv_pipe']}",
                        final_url,
                    ]
                    flags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                    tile["mpv_proc"] = subprocess.Popen(args, creationflags=flags)
                    return

            if not tile.get("vlc_inst"):
                vlc_dir = find_vlc_directory(self.config_data.get("vlc_custom_dir"))
                if vlc_dir:
                    tile["vlc_inst"] = bind_vlc_runtime(vlc_dir)
            inst = tile.get("vlc_inst")
            if inst:
                if not tile.get("vlc_player"):
                    tile["vlc_player"] = inst.media_player_new()
                vp = tile["vlc_player"]
                media = inst.media_new(final_url)
                vp.set_media(media)
                if sys.platform.startswith("win"):
                    vp.set_hwnd(hwnd)
                elif sys.platform.startswith("linux"):
                    vp.set_xwindow(hwnd)
                elif sys.platform == "darwin":
                    vp.set_nsobject(hwnd)
                vp.play()
                self._schedule_vlc_volume_sync(
                    vp, eff_vol, muted=bool(tile.get("muted")),
                    check_fn=lambda t=tile, r=req_id: t in self.multi_tiles and r == t["req_id"]
                )

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_tile_audio(self, tile):
        muted = bool(tile.get("muted"))
        vol = int(tile.get("volume", 80))
        eff_vol = 0 if muted else vol
        try:
            tile["mute_btn"].configure(
                text="",
                image=self._icon_mute if muted else self._icon_volume,
                fg_color=("#FEE2E2", "#3f1d28") if muted else C_BG_CARD
            )
            tile["vol_lbl"].configure(text="MUTE" if muted else f"{vol}%")
        except Exception:
            pass

        if tile.get("mpv_proc") and tile["mpv_proc"].poll() is None:
            self._send_tile_mpv_ipc(tile, ["set_property", "mute", muted])
            self._send_tile_mpv_ipc(tile, ["set_property", "volume", eff_vol])
        elif tile.get("vlc_player"):
            vp = tile["vlc_player"]

            def _set_vlc():
                try:
                    vp.audio_set_mute(muted)
                    vp.audio_set_volume(eff_vol)
                except Exception:
                    pass

            threading.Thread(target=_set_vlc, daemon=True).start()

    def _set_tile_volume(self, tile, val):
        v = int(float(val))
        tile["volume"] = v
        if v > 0 and tile.get("muted"):
            tile["muted"] = False
            if self.multi_solo_audio_var.get() and tile in self.multi_tiles:
                idx = self.multi_tiles.index(tile)
                if idx != self.multi_focused_idx:
                    self.multi_solo_audio_var.set(False)
                    self.mv_audio_mode_btn.configure(text=" Audio: Mix Libero", text_color=C_GREEN)
        self._apply_tile_audio(tile)
        if 0 <= self.multi_focused_idx < len(self.multi_tiles) and self.multi_tiles[self.multi_focused_idx] is tile:
            self.vol_slider.set(v)
            self.vol_pct_lbl.configure(text=f" {v}%", image=self._icon_mute if v == 0 else self._icon_volume)

    def _toggle_tile_mute(self, tile):
        new_mute = not bool(tile.get("muted"))
        tile["muted"] = new_mute
        if not new_mute and self.multi_solo_audio_var.get() and tile in self.multi_tiles:
            idx = self.multi_tiles.index(tile)
            if idx != self.multi_focused_idx:
                # L'utente ha voluto sentire un secondo stream manualmente -> passa a Mix Libero
                self.multi_solo_audio_var.set(False)
                self.mv_audio_mode_btn.configure(text=" Audio: Mix Libero", text_color=C_GREEN)
        self._apply_tile_audio(tile)

    def _focus_multiview_tile(self, idx):
        if not self.is_multiview or idx < 0 or idx >= len(self.multi_tiles):
            return
        self.multi_focused_idx = idx
        foc = self.multi_tiles[idx]

        for i, t in enumerate(self.multi_tiles):
            try:
                if not self._mv_controls_hidden:
                    t["card"].configure(border_color=C_ACCENT if i == idx else C_BORDER)
            except Exception:
                pass
            if self.multi_solo_audio_var.get():
                t["muted"] = (i != idx)
                self._apply_tile_audio(t)

        if foc.get("qualities"):
            self.current_qualities = dict(foc["qualities"])
            self.current_backup_qualities = dict(foc.get("backup_qualities") or {})
            self.quality_menu.configure(values=list(self.current_qualities.keys()))
            if foc.get("selected_quality") in self.current_qualities:
                self.quality_var.set(foc["selected_quality"])

        foc_vol = foc.get("volume", 80)
        self.vol_slider.set(foc_vol)
        self.fs_vol_slider.set(foc_vol)
        self.vol_pct_lbl.configure(text=f" {foc_vol}%", image=self._icon_mute if foc_vol == 0 else self._icon_volume)
        ch = foc["channel"]
        self.stream_meta_lbl.configure(text=f"Multi-Live Focus: #{ch.upper()}")
        self.badge_live_lbl.configure(text=f" ● GRID {len(self.multi_tiles)}/4 ", fg_color=C_LIVE, text_color="#ffffff")
        self._update_multiview_header_badge()
        self._switch_multiview_chat(idx)

    def _remove_multi_tile(self, tile):
        if tile not in self.multi_tiles:
            return
        idx = self.multi_tiles.index(tile)
        self.multi_tiles.pop(idx)
        self._destroy_tile_resources(tile)
        if self.multi_tiles:
            new_idx = min(self.multi_focused_idx, len(self.multi_tiles) - 1)
            self.multi_chat_idx = min(self.multi_chat_idx, len(self.multi_tiles) - 1)
            self._relayout_multiview_grid()
            self._focus_multiview_tile(new_idx)
        else:
            self.multi_focused_idx = 0
            self.multi_chat_idx = 0
            self._relayout_multiview_grid()

    def _promote_multi_tile_to_single(self, tile):
        if tile in self.multi_tiles:
            self.multi_focused_idx = self.multi_tiles.index(tile)
        self._exit_multiview_mode(preserve_focused=True)

    # =================================================================
    # CLIP STUDIO INTERNO (LIVE & VOD, ANTEPRIMA, TRIM PRECISIONE, 2+ MIN)
    # =================================================================
    def _register_active_hwnd_file(self):
        if not self.app_running or not sys.platform.startswith("win"):
            return
        try:
            hwnd = get_root_hwnd(self) or self.winfo_id()
            hwnd_file = os.path.join(tempfile.gettempdir(), "twixy_active_hwnd.txt")
            with open(hwnd_file, "w", encoding="utf-8") as f:
                f.write(f"{int(hwnd)}\n{os.getpid()}\n")
        except Exception:
            pass

    def _stop_clip_preview_engines(self):
        vp = getattr(self, "_clip_preview_vlc", None)
        self._clip_preview_vlc = None
        if vp is not None:
            def _stop_vp():
                try:
                    vp.stop()
                    vp.release()
                except Exception:
                    pass
            threading.Thread(target=_stop_vp, daemon=True).start()
        mp = getattr(self, "_clip_preview_mpv", None)
        self._clip_preview_mpv = None
        if mp is not None:
            try:
                mp.terminate()
            except Exception:
                pass

    def _set_main_stream_clip_muted(self, muted):
        """Silenzia temporaneamente il player principale mentre è aperta l'anteprima Clip."""
        if self.is_multiview and self.multi_tiles:
            for tile in list(self.multi_tiles):
                try:
                    if muted:
                        tile["_pre_clip_muted"] = tile.get("muted", False)
                        eff_mute = True
                    else:
                        eff_mute = bool(tile.pop("_pre_clip_muted", tile.get("muted", False)))
                    vol = 0 if eff_mute else int(tile.get("volume", 80))
                    if tile.get("mpv_proc") and tile["mpv_proc"].poll() is None:
                        self._send_tile_mpv_ipc(tile, ["set_property", "mute", eff_mute])
                        self._send_tile_mpv_ipc(tile, ["set_property", "volume", vol])
                    elif tile.get("vlc_player"):
                        tvp = tile["vlc_player"]
                        threading.Thread(target=lambda p=tvp, m=eff_mute, v=vol: (p.audio_set_mute(m), p.audio_set_volume(v)), daemon=True).start()
                except Exception:
                    pass
            return

        vol_val = max(0, min(100, int(self.config_data.get("volume", 80))))
        if "MPV" in self.engine_var.get() and self.mpv_proc:
            self._send_mpv_ipc(["set_property", "mute", bool(muted)])
        elif self.vlc_player:
            vp = self.vlc_player
            threading.Thread(
                target=lambda: (vp.audio_set_mute(bool(muted)), None if muted else vp.audio_set_volume(vol_val)),
                daemon=True,
            ).start()

    def close_clip_studio(self, restore_stage=True):
        if not getattr(self, "_clip_studio_open", False):
            return
        self._clip_studio_open = False
        self._clip_session_seq = getattr(self, "_clip_session_seq", 0) + 1
        self._stop_clip_preview_engines()

        sid = getattr(self, "_clip_active_sid", None)
        self._clip_active_sid = None
        if sid:
            try:
                self.engine.ad_stripper.release_clip_session(sid)
            except Exception:
                pass

        fr = getattr(self, "clip_studio_frame", None)
        self.clip_studio_frame = None
        if fr is not None:
            try:
                if fr.winfo_exists():
                    fr.destroy()
            except Exception:
                pass

        if restore_stage and self.app_running:
            self._set_main_stream_clip_muted(False)
            try:
                if self.is_multiview:
                    if not self.multiview_frame.winfo_manager():
                        self.multiview_frame.pack(side="top", fill="both", expand=True)
                else:
                    if not self.video_stage.winfo_manager():
                        self.video_stage.pack(side="top", fill="both", expand=True)
                if not self.deck.winfo_manager() and not self.is_fullscreen and not self.is_pip:
                    self.deck.pack(side="bottom", fill="x")
                self.update_idletasks()
                self._layout_video_canvas(force=True)
            except Exception:
                pass

    def open_clip_dialog(self):
        if self.is_fullscreen:
            self.exit_fullscreen()
        elif self.is_pip:
            self.toggle_pip_mode()
        self.close_inapp_menu(restore_chat=True)

        # Determina sorgente attiva (Multi-Live, VOD o Live singola)
        is_vod = bool(self.is_playing_vod and not self.is_multiview)
        slot_id = "main"
        ch_name = self.current_channel or ""
        vod_url = ""
        vod_anchor_sec = 0.0
        vod_total_sec = 0.0

        if self.is_multiview:
            if not self.multi_tiles or not (0 <= self.multi_focused_idx < len(self.multi_tiles)):
                self.stream_meta_lbl.configure(text="⚠ Avvia prima una Live per creare una Clip!")
                return
            foc = self.multi_tiles[self.multi_focused_idx]
            slot_id = f"mv_{foc['slot_id']}"
            ch_name = foc.get("channel") or "multilive"
        elif is_vod:
            q_sel = self.quality_var.get()
            vod_url = (self.current_qualities or {}).get(q_sel) or next(iter((self.current_qualities or {}).values()), "")
            if not vod_url:
                self.stream_meta_lbl.configure(text="⚠ Nessun flusso VOD attivo da clippare.")
                return
            ch_name = (getattr(self, "current_vod_info", None) or {}).get("channel") or self.vods_channel_name or self.current_channel or "vod"
            vod_total_sec = float(self._get_effective_vod_total_seconds() or 0.0)
            slider_frac = 0.0
            try:
                slider_frac = max(0.0, min(1.0, float(self.seek_slider.get() or 0.0) / 1000.0))
            except Exception:
                slider_frac = 0.0
            slider_sec = (slider_frac * vod_total_sec) if vod_total_sec > 0 else 0.0
            bg_sec = max(0.0, float(self._bg_curr_ms or 0) / 1000.0)
            if "MPV" in self.engine_var.get() and self.mpv_proc:
                t_pos = self._query_mpv_ipc_property("time-pos")
                if t_pos is not None and float(t_pos) >= 0:
                    vod_anchor_sec = float(t_pos)
                else:
                    pct_pos = self._query_mpv_ipc_property("percent-pos")
                    if pct_pos is not None and vod_total_sec > 0:
                        vod_anchor_sec = (max(0.0, min(100.0, float(pct_pos))) / 100.0) * vod_total_sec
                    else:
                        vod_anchor_sec = bg_sec if bg_sec > 0 else slider_sec
            elif self.vlc_player:
                t_sec = None
                pos_sec = None
                try:
                    t_ms = self.vlc_player.get_time()
                    if t_ms is not None and t_ms >= 0:
                        t_sec = float(t_ms) / 1000.0
                except Exception:
                    pass
                try:
                    pos_f = self.vlc_player.get_position()
                    if pos_f is not None and 0.0 <= float(pos_f) <= 1.0 and vod_total_sec > 0:
                        pos_sec = float(pos_f) * vod_total_sec
                except Exception:
                    pass
                if pos_sec is not None and t_sec is not None:
                    # Su alcuni VOD HLS Twitch LibVLC riporta PTS errati a fine stream in get_time()
                    vod_anchor_sec = pos_sec if abs(t_sec - pos_sec) > 45.0 else t_sec
                elif t_sec is not None and (vod_total_sec <= 0 or t_sec <= vod_total_sec + 5.0):
                    vod_anchor_sec = t_sec
                elif pos_sec is not None:
                    vod_anchor_sec = pos_sec
                elif bg_sec > 0 and (vod_total_sec <= 0 or bg_sec <= vod_total_sec + 5.0):
                    vod_anchor_sec = bg_sec
                else:
                    vod_anchor_sec = slider_sec
        else:
            if not self.current_channel:
                self.stream_meta_lbl.configure(text="⚠ Avvia prima una Live o un VOD per creare una Clip!")
                return

        if getattr(self, "_clip_studio_open", False):
            self.close_clip_studio(restore_stage=False)

        self._clip_studio_open = True
        self._clip_session_seq = getattr(self, "_clip_session_seq", 0) + 1
        my_seq = self._clip_session_seq
        self._set_main_stream_clip_muted(True)
        self._hide_vod_hover_hud()

        try:
            self.video_stage.pack_forget()
        except Exception:
            pass
        try:
            self.multiview_frame.pack_forget()
        except Exception:
            pass
        try:
            self.deck.pack_forget()
        except Exception:
            pass

        studio = ctk.CTkFrame(self.center_stage, fg_color=C_BG_ROOT, corner_radius=0)
        studio.pack(side="top", fill="both", expand=True)
        self.clip_studio_frame = studio

        # 1. Header Clip Studio
        hdr = ctk.CTkFrame(studio, fg_color=C_BG_HEADER, height=48, corner_radius=0, border_width=1, border_color=C_BORDER)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        src_kind = "VOD" if is_vod else "LIVE"
        ctk.CTkLabel(
            hdr, text=f" Clip Studio — #{ch_name.upper()} ({src_kind})",
            image=self._icon_clip, compound="left",
            font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=C_TEXT_MAIN,
        ).pack(side="left", padx=14)

        self._clip_window_badge = ctk.CTkLabel(
            hdr, text="Preparazione clip (ultimi 30s)...",
            fg_color=("#EDE9FE", "#231b3a"), text_color=C_ACCENT,
            corner_radius=7, font=ctk.CTkFont("Segoe UI", 11, "bold"), padx=10, height=26,
        )
        self._clip_window_badge.pack(side="left", padx=6)

        self._make_shadow_btn(
            hdr,
            pack_kw={"side": "right", "padx": (4, 14), "pady": 8},
            offset_x=2, offset_y=2,
            text=" Annulla (ESC)", image=self._icon_close, compound="left",
            width=116, height=30, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_LIVE, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=self.close_clip_studio,
        )

        # 2. Area Video Preview
        prev_outer = ctk.CTkFrame(studio, fg_color=C_VIDEO_LETTERBOX, corner_radius=0)
        prev_outer.pack(fill="both", expand=True, padx=12, pady=(8, 4))

        prev_canvas = tk.Canvas(prev_outer, bg="#000000", highlightthickness=0, bd=0)
        prev_canvas.pack(fill="both", expand=True)

        loading_ov = ctk.CTkLabel(
            prev_outer,
            text=" Cattura segmenti e preparazione anteprima...",
            image=self._icon_download, compound="left",
            fg_color=("#18181f", "#18181f"), text_color="#f59e0b",
            corner_radius=10, font=ctk.CTkFont("Segoe UI", 13, "bold"), padx=18, pady=12,
        )
        loading_ov.place(relx=0.5, rely=0.5, anchor="center")

        # 3. Dock inferiore: Timeline interattiva + Controlli Trim + Export MP4
        ctrl_dock = ctk.CTkFrame(studio, fg_color=C_BG_HEADER, corner_radius=10, border_width=1, border_color=C_BORDER)
        ctrl_dock.pack(fill="x", padx=12, pady=(2, 10))

        clip_state = {
            "sid": None,
            "playlist_url": "",
            "rev": 0,
            "vod_offset_sec": 0.0,
            "total_dur": 30.0,
            "trim_start": 0.0,
            "trim_end": 30.0,
            "playhead": 0.0,
            "paused": True,
            "range_play": False,
            "preview_mpv_pipe": rf"\\.\pipe\twixy_clip_{os.getpid()}_{uuid.uuid4().hex[:6]}",
            "use_mpv": False,
            "saved_path": "",
            "exporting": False,
            "last_drag_seek_ts": 0.0,
        }

        def _fmt_sec(sec):
            sec = max(0.0, float(sec))
            m, s = divmod(int(sec), 60)
            tenths = int(round((sec - int(sec)) * 10)) % 10
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}.{tenths}"
            return f"{m:02d}:{s:02d}.{tenths}"

        def _update_trim_labels():
            d_sel = max(0.5, clip_state["trim_end"] - clip_state["trim_start"])
            t_tot = clip_state["total_dur"]
            off_v = float(clip_state.get("vod_offset_sec", 0.0) or 0.0)
            if self._clip_window_badge.winfo_exists():
                if is_vod:
                    w_start_s = format_seconds_hms(off_v)
                    w_end_s = format_seconds_hms(off_v + t_tot)
                    c_start_s = format_seconds_hms(off_v + clip_state["trim_start"])
                    c_end_s = format_seconds_hms(off_v + clip_state["trim_end"])
                    self._clip_window_badge.configure(
                        text=f"VOD {w_start_s} -> {w_end_s}  •  Clip {c_start_s} - {c_end_s} ({d_sel:.1f}s)"
                    )
                else:
                    self._clip_window_badge.configure(
                        text=f"Inizio {_fmt_sec(clip_state['trim_start'])}  •  Fine {_fmt_sec(clip_state['trim_end'])}  •  Durata {d_sel:.1f}s (Disponibili {t_tot:.0f}s)"
                    )
            if info_lbl.winfo_exists():
                if is_vod:
                    cur_vod_t = format_seconds_hms(off_v + clip_state["playhead"])
                    info_lbl.configure(
                        text=f"Posizione: {_fmt_sec(clip_state['playhead'])} ({cur_vod_t} VOD)   |   Selezione: {d_sel:.1f}s"
                    )
                else:
                    info_lbl.configure(
                        text=f"Posizione: {_fmt_sec(clip_state['playhead'])}   |   Selezione: {d_sel:.1f}s (trascina i bordi viola/ciano fino a 2+ min)"
                    )

        def _seek_preview_abs(sec_val, play=None):
            sec_val = max(0.0, min(clip_state["total_dur"], float(sec_val)))
            clip_state["playhead"] = sec_val
            clip_state["last_drag_seek_ts"] = time.time()
            timeline.set_values(playhead=sec_val)
            _update_trim_labels()
            if clip_state["use_mpv"]:
                mp = getattr(self, "_clip_preview_mpv", None)
                if mp and mp.poll() is None:
                    self._send_mpv_ipc(["seek", sec_val, "absolute"], pipe_name=clip_state["preview_mpv_pipe"])
                    if play is not None:
                        clip_state["paused"] = not play
                        self._send_mpv_ipc(["set_property", "pause", not play], pipe_name=clip_state["preview_mpv_pipe"])
            else:
                vp = getattr(self, "_clip_preview_vlc", None)
                if vp is not None:
                    def _vlc_sk():
                        try:
                            if play is True:
                                vp.set_pause(0)
                            elif play is False:
                                vp.set_pause(1)
                            vp.set_time(int(sec_val * 1000))
                        except Exception:
                            pass
                    threading.Thread(target=_vlc_sk, daemon=True).start()
                    if play is not None:
                        clip_state["paused"] = not play
            try:
                btn_play_pause.configure(
                    text=" Play" if clip_state["paused"] else " Pausa",
                    image=self._icon_play if clip_state["paused"] else self._icon_pause,
                )
            except Exception:
                pass

        def _on_timeline_drag(which, val):
            if which == "start":
                clip_state["trim_start"] = max(0.0, min(clip_state["trim_end"] - 1.0, float(val)))
                seek_t = clip_state["trim_start"]
            elif which == "end":
                clip_state["trim_end"] = max(clip_state["trim_start"] + 1.0, min(clip_state["total_dur"], float(val)))
                seek_t = max(0.0, clip_state["trim_end"] - 1.5)
            else:
                dur = clip_state["trim_end"] - clip_state["trim_start"]
                ns = max(0.0, min(clip_state["total_dur"] - dur, float(val)))
                clip_state["trim_start"] = ns
                clip_state["trim_end"] = ns + dur
                seek_t = ns
            clip_state["range_play"] = False
            timeline.set_values(trim_start=clip_state["trim_start"], trim_end=clip_state["trim_end"])
            now = time.time()
            if now - clip_state["last_drag_seek_ts"] >= 0.08:
                clip_state["last_drag_seek_ts"] = now
                _seek_preview_abs(seek_t, play=False)
            else:
                clip_state["playhead"] = seek_t
                timeline.set_values(playhead=seek_t)
                _update_trim_labels()

        def _on_timeline_release(which, val):
            _on_timeline_drag(which, val)
            seek_t = clip_state["trim_start"] if which in ("start", "move") else max(clip_state["trim_start"], clip_state["trim_end"] - 2.0)
            _seek_preview_abs(seek_t, play=False)

        def _on_timeline_seek(sec_val):
            clip_state["range_play"] = False
            _seek_preview_abs(sec_val, play=None)

        timeline = _ClipTimelineCanvas(
            ctrl_dock,
            on_handle_drag=_on_timeline_drag,
            on_handle_release=_on_timeline_release,
            on_seek=_on_timeline_seek,
        )
        timeline.pack(fill="x", padx=14, pady=(10, 4))

        info_lbl = ctk.CTkLabel(
            ctrl_dock,
            text="Posizione: 00:00.0   |   Selezione: 30.0s",
            font=ctk.CTkFont("Consolas", 11, "bold"), text_color=C_TEXT_MAIN, anchor="w",
        )
        info_lbl.pack(fill="x", padx=16, pady=(0, 4))

        # Riga 1 controllo anteprima + preset durata (15s, 30s, 1m, 2m, Max) + espansione VOD
        p_row = ctk.CTkFrame(ctrl_dock, fg_color="transparent")
        p_row.pack(fill="x", padx=14, pady=(2, 4))

        def _preview_selection():
            clip_state["range_play"] = True
            _seek_preview_abs(clip_state["trim_start"], play=True)

        def _preview_end_tail():
            clip_state["range_play"] = True
            t_tail = max(clip_state["trim_start"], clip_state["trim_end"] - 3.0)
            _seek_preview_abs(t_tail, play=True)

        def _toggle_preview_pause():
            clip_state["range_play"] = False
            _seek_preview_abs(clip_state["playhead"], play=clip_state["paused"])

        self._make_shadow_btn(
            p_row, pack_kw={"side": "left", "padx": (0, 4)}, offset_x=2, offset_y=2,
            text=" Vai all'Inizio", image=self._icon_skip_back, compound="left",
            width=122, height=30, corner_radius=7,
            fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=lambda: (clip_state.update({"range_play": False}), _seek_preview_abs(clip_state["trim_start"], play=False)),
        )
        self._make_shadow_btn(
            p_row, pack_kw={"side": "left", "padx": 3}, offset_x=2, offset_y=2,
            text=" Guarda Selezione", image=self._icon_play_white, compound="left",
            width=148, height=30, corner_radius=7,
            fg_color=C_ACCENT, hover_color=C_ACCENT_HOVER, text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=_preview_selection,
        )
        btn_play_pause = self._make_shadow_btn(
            p_row, pack_kw={"side": "left", "padx": 3}, offset_x=2, offset_y=2,
            text=" Play", image=self._icon_play, compound="left",
            width=84, height=30, corner_radius=7,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            command=_toggle_preview_pause,
        )
        self._make_shadow_btn(
            p_row, pack_kw={"side": "left", "padx": 3}, offset_x=2, offset_y=2,
            text=" Testa Fine", image=self._icon_skip_fwd, compound="left",
            width=102, height=30, corner_radius=7,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
            command=_preview_end_tail,
        )

        # Nudge di precisione Inizio (-1s / +1s)
        def _nudge_start(delta):
            clip_state["range_play"] = False
            ns = max(0.0, min(clip_state["trim_end"] - 1.0, clip_state["trim_start"] + delta))
            clip_state["trim_start"] = ns
            timeline.set_values(trim_start=ns)
            _seek_preview_abs(ns, play=False)

        def _nudge_end(delta):
            clip_state["range_play"] = False
            ne = max(clip_state["trim_start"] + 1.0, min(clip_state["total_dur"], clip_state["trim_end"] + delta))
            clip_state["trim_end"] = ne
            timeline.set_values(trim_end=ne)
            _seek_preview_abs(max(0.0, ne - 1.5), play=False)

        def _apply_duration_preset(sec_len):
            clip_state["range_play"] = False
            tot = clip_state["total_dur"]
            anchor_end = clip_state["trim_end"]
            if sec_len is None:
                clip_state["trim_start"] = 0.0
                clip_state["trim_end"] = tot
            else:
                req = float(sec_len)
                ns = max(0.0, anchor_end - req)
                ne = min(tot, ns + req)
                clip_state["trim_start"] = ns
                clip_state["trim_end"] = ne
            timeline.set_values(total_dur=tot, trim_start=clip_state["trim_start"], trim_end=clip_state["trim_end"])
            _seek_preview_abs(clip_state["trim_start"], play=False)

        preset_row = ctk.CTkFrame(p_row, fg_color="transparent")
        preset_row.pack(side="right")
        ctk.CTkLabel(preset_row, text="Durata:", font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=C_TEXT_DIM).pack(side="left", padx=(0, 4))
        for p_txt, p_val in [("15s", 15), ("30s", 30), ("1m", 60), ("2m", 120), ("Max", None)]:
            ctk.CTkButton(
                preset_row, text=p_txt, width=36, height=26, corner_radius=6,
                fg_color=C_BG_INPUT, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
                font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=lambda v=p_val: _apply_duration_preset(v),
            ).pack(side="left", padx=2)

        # Riga 2: Regolazioni fini + Espansione finestra VOD (-1m / +1m)
        nudge_row = ctk.CTkFrame(ctrl_dock, fg_color="transparent")
        nudge_row.pack(fill="x", padx=14, pady=(2, 4))

        ctk.CTkLabel(nudge_row, text="Inizio:", font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=C_ACCENT).pack(side="left", padx=(0, 3))
        for lbl_n, dn in [("-5s", -5.0), ("-1s", -1.0), ("+1s", 1.0), ("+5s", 5.0)]:
            ctk.CTkButton(
                nudge_row, text=lbl_n, width=36, height=24, corner_radius=5,
                fg_color=C_BG_INPUT, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
                font=ctk.CTkFont("Consolas", 10, "bold"),
                command=lambda d=dn: _nudge_start(d),
            ).pack(side="left", padx=2)

        ctk.CTkLabel(nudge_row, text="  Fine:", font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=C_CYAN).pack(side="left", padx=(8, 3))
        for lbl_n, dn in [("-5s", -5.0), ("-1s", -1.0), ("+1s", 1.0), ("+5s", 5.0)]:
            ctk.CTkButton(
                nudge_row, text=lbl_n, width=36, height=24, corner_radius=5,
                fg_color=C_BG_INPUT, hover_color=C_CYAN, text_color=C_TEXT_MAIN,
                font=ctk.CTkFont("Consolas", 10, "bold"),
                command=lambda d=dn: _nudge_end(d),
            ).pack(side="left", padx=2)

        if is_vod:
            def _expand_vod_window(d_before, d_after):
                if not clip_state["sid"]:
                    return
                export_lbl.configure(text="Caricamento finestra VOD estesa...", text_color=C_GOLD)

                def _w():
                    res = self.engine.ad_stripper.shift_vod_clip_window(
                        clip_state["sid"],
                        delta_before=d_before,
                        delta_after=d_after,
                        cur_trim_start=clip_state["trim_start"],
                        cur_trim_end=clip_state["trim_end"],
                    )
                    if not res or my_seq != self._clip_session_seq:
                        return
                    self.engine.ad_stripper.prefetch_session_range(clip_state["sid"], 0.0, res["total_dur"])

                    def _apply():
                        if my_seq != self._clip_session_seq or not studio.winfo_exists():
                            return
                        if not res.get("changed", True):
                            lim_msg = "Sei già all'inizio del VOD." if d_before > 0 else "Sei già alla fine del VOD."
                            export_lbl.configure(text=lim_msg, text_color=C_TEXT_DIM)
                            return
                        clip_state["rev"] = int(clip_state.get("rev", 0)) + 1
                        clip_state["playlist_url"] = (
                            f"http://127.0.0.1:{self.engine.ad_stripper.port}/clip_session/"
                            f"{clip_state['sid']}/playlist.m3u8?v={clip_state['rev']}"
                        )
                        clip_state["vod_offset_sec"] = float(res.get("vod_offset_sec", clip_state.get("vod_offset_sec", 0.0)))
                        clip_state["total_dur"] = res["total_dur"]
                        clip_state["trim_start"] = res["trim_start"]
                        clip_state["trim_end"] = res["trim_end"]
                        clip_state["playhead"] = res["trim_start"]
                        clip_state["range_play"] = False
                        timeline.set_values(
                            total_dur=res["total_dur"],
                            trim_start=res["trim_start"],
                            trim_end=res["trim_end"],
                            playhead=clip_state["playhead"],
                        )
                        _start_preview_media()
                        _update_trim_labels()
                        export_lbl.configure(text="Finestra VOD estesa: regola i cursori e salva.", text_color=C_GREEN)

                    self._safe_ui(_apply)

                threading.Thread(target=_w, daemon=True).start()

            ctk.CTkButton(
                nudge_row, text="+1m Dopo", width=72, height=24, corner_radius=6,
                fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
                border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=lambda: _expand_vod_window(0.0, 60.0),
            ).pack(side="right", padx=(4, 0))
            ctk.CTkButton(
                nudge_row, text="-1m Prima", width=76, height=24, corner_radius=6,
                fg_color=C_BG_CARD, hover_color=C_ACCENT, text_color=C_TEXT_MAIN,
                border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 10, "bold"),
                command=lambda: _expand_vod_window(60.0, 0.0),
            ).pack(side="right", padx=4)

        # Riga 3: Nome file + Conferma & Processa Clip
        exp_row = ctk.CTkFrame(ctrl_dock, fg_color="transparent")
        exp_row.pack(fill="x", padx=14, pady=(4, 10))

        default_fname = f"twixy_clip_{re.sub(r'[^a-zA-Z0-9_-]+', '_', ch_name or 'stream')}_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
        fname_var = tk.StringVar(value=default_fname)
        ctk.CTkLabel(exp_row, text="Nome File:", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=C_TEXT_DIM).pack(side="left", padx=(0, 6))
        fname_entry = ctk.CTkEntry(exp_row, textvariable=fname_var, width=250, height=30, fg_color=C_BG_INPUT, border_color=C_BORDER, font=ctk.CTkFont("Consolas", 11))
        fname_entry.pack(side="left", padx=(0, 8))

        export_pbar = ctk.CTkProgressBar(exp_row, width=110, height=10, corner_radius=5, fg_color=C_BG_INPUT, progress_color=C_GREEN)
        export_pbar.set(0.0)
        export_pbar.pack(side="left", padx=(0, 8))

        export_lbl = ctk.CTkLabel(exp_row, text="Caricamento anteprima...", font=ctk.CTkFont("Segoe UI", 10, "bold"), text_color=C_GOLD, anchor="w")
        export_lbl.pack(side="left", fill="x", expand=True)

        open_folder_btn = ctk.CTkButton(
            exp_row, text=" Apri Cartella", image=self._icon_folder, compound="left",
            width=110, height=32, corner_radius=8,
            fg_color=C_BG_CARD, hover_color=C_BG_CARD_HOVER, text_color=C_TEXT_MAIN,
            border_width=1, border_color=C_BORDER, font=ctk.CTkFont("Segoe UI", 11, "bold"),
            state="disabled",
        )

        def _open_saved_dir():
            p = clip_state["saved_path"]
            if p and os.path.exists(p):
                if sys.platform.startswith("win"):
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
                else:
                    webbrowser.open(os.path.dirname(p))

        open_folder_btn.configure(command=_open_saved_dir)

        confirm_btn = self._make_shadow_btn(
            exp_row, pack_kw={"side": "right", "padx": (6, 0)}, offset_x=2, offset_y=3,
            text=" Conferma e Salva Clip", image=self._icon_check_white, compound="left",
            width=172, height=32, corner_radius=8,
            fg_color=C_GREEN, hover_color="#059669", text_color="#ffffff",
            font=ctk.CTkFont("Segoe UI", 11, "bold"), state="disabled",
        )
        open_folder_btn.pack(side="right", padx=(6, 0))

        def _start_preview_media():
            self._stop_clip_preview_engines()
            if my_seq != self._clip_session_seq or not prev_canvas.winfo_exists():
                return
            url = clip_state["playlist_url"]
            if not url:
                return
            hwnd = prev_canvas.winfo_id()
            vol_val = max(0, min(100, int(self.config_data.get("volume", 80))))
            prefer_mpv = ("MPV" in self.engine_var.get() or not self.vlc_instance)
            if prefer_mpv and not self.mpv_exe:
                self.mpv_exe = find_mpv_executable(self.config_data.get("mpv_custom_dir"))

            if prefer_mpv and self.mpv_exe:
                clip_state["use_mpv"] = True
                args = [
                    self.mpv_exe,
                    f"--wid={hwnd}",
                    "--hwdec=auto",
                    "--vo=gpu",
                    "--keepaspect=yes",
                    "--keep-open=yes",
                    "--pause=yes",
                    f"--start=+{clip_state['trim_start']:.2f}",
                    f"--volume={vol_val}",
                    "--osc=no",
                    "--input-default-bindings=no",
                    f"--input-ipc-server={clip_state['preview_mpv_pipe']}",
                    url,
                ]
                flags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0
                self._clip_preview_mpv = subprocess.Popen(args, creationflags=flags)
                clip_state["paused"] = True
                btn_play_pause.configure(text=" Play", image=self._icon_play)
            elif self.vlc_instance:
                clip_state["use_mpv"] = False
                vp = self.vlc_instance.media_player_new()
                self._clip_preview_vlc = vp
                media = self.vlc_instance.media_new(url)
                vp.set_media(media)
                if sys.platform.startswith("win"):
                    vp.set_hwnd(hwnd)
                elif sys.platform.startswith("linux"):
                    vp.set_xwindow(hwnd)
                elif sys.platform == "darwin":
                    vp.set_nsobject(hwnd)
                vp.play()
                clip_state["paused"] = True
                btn_play_pause.configure(text=" Play", image=self._icon_play)

                def _init_seek_vlc():
                    for _ in range(40):
                        if my_seq != self._clip_session_seq or not self.app_running:
                            return
                        try:
                            st = vp.get_state()
                            lg = vp.get_length()
                            if st in (vlc.State.Playing, vlc.State.Paused) or (lg is not None and lg > 0):
                                break
                        except Exception:
                            pass
                        time.sleep(0.1)
                    if my_seq != self._clip_session_seq:
                        return
                    try:
                        vp.audio_set_mute(False)
                        vp.audio_set_volume(vol_val)
                        vp.set_time(int(clip_state["trim_start"] * 1000))
                        if clip_state["paused"]:
                            vp.set_pause(1)
                    except Exception:
                        pass

                threading.Thread(target=_init_seek_vlc, daemon=True).start()

        def _tick_clip_preview():
            if not getattr(self, "_clip_studio_open", False) or my_seq != self._clip_session_seq or not studio.winfo_exists():
                return
            pos_sec = None
            recently_sought = (time.time() - clip_state.get("last_drag_seek_ts", 0.0)) < 0.35
            if clip_state["use_mpv"]:
                mp = getattr(self, "_clip_preview_mpv", None)
                if mp and mp.poll() is None and not clip_state["paused"] and not recently_sought:
                    req_seek_ts = clip_state.get("last_drag_seek_ts", 0.0)
                    def _poll_mpv_t(seek_stamp=req_seek_ts):
                        tp = self._query_mpv_ipc_property("time-pos", pipe_name=clip_state["preview_mpv_pipe"])
                        if tp is not None and clip_state.get("last_drag_seek_ts", 0.0) == seek_stamp and not clip_state["paused"]:
                            clip_state["playhead"] = max(0.0, min(clip_state["total_dur"], float(tp)))
                    threading.Thread(target=_poll_mpv_t, daemon=True).start()
                    pos_sec = clip_state["playhead"]
            else:
                vp = getattr(self, "_clip_preview_vlc", None)
                if vp is not None and not recently_sought:
                    try:
                        if vp.is_playing():
                            t_ms = vp.get_time()
                            if t_ms is not None and t_ms >= 0:
                                pos_sec = max(0.0, min(clip_state["total_dur"], float(t_ms) / 1000.0))
                    except Exception:
                        pass
            if pos_sec is not None:
                clip_state["playhead"] = pos_sec
                timeline.set_values(playhead=pos_sec)
                _update_trim_labels()
                if clip_state["range_play"] and pos_sec >= (clip_state["trim_end"] - 0.08):
                    clip_state["range_play"] = False
                    _seek_preview_abs(clip_state["trim_start"], play=False)
            self.after(90, _tick_clip_preview)

        def _confirm_and_export():
            if clip_state["exporting"] or not clip_state["sid"]:
                return
            clip_state["exporting"] = True
            confirm_btn.configure(state="disabled", text=" Creazione Clip...", image=self._icon_download)
            export_pbar.set(0.05)
            export_lbl.configure(text="Download e unione segmenti in corso...", text_color=C_GOLD)

            out_dir = os.path.join(os.path.expanduser("~"), "Videos", "Twixy Clips")
            try:
                os.makedirs(out_dir, exist_ok=True)
            except Exception:
                out_dir = os.path.join(APP_DIR, "Twixy Clips")
                os.makedirs(out_dir, exist_ok=True)

            raw_name = fname_var.get().strip() or default_fname
            safe_name = re.sub(r'[\\/:*?"<>|]+', "_", raw_name)
            if not safe_name.lower().endswith(".mp4"):
                safe_name += ".mp4"
            out_mp4 = os.path.join(out_dir, safe_name)

            t0 = clip_state["trim_start"]
            t1 = clip_state["trim_end"]
            sid_now = clip_state["sid"]

            def _export_worker():
                raw_path = ""
                try:
                    def _prog_cb(pct_or_frac, msg=None):
                        val = float(pct_or_frac or 0.0)
                        frac = (val / 45.0) if (msg is not None or val > 1.0) else val
                        frac = max(0.0, min(1.0, frac))

                        def _upd():
                            if my_seq != self._clip_session_seq or not studio.winfo_exists():
                                return
                            if export_pbar.winfo_exists():
                                export_pbar.set(0.05 + 0.65 * frac)
                            if msg and export_lbl.winfo_exists():
                                export_lbl.configure(text=str(msg), text_color=C_GOLD)

                        self._safe_ui(_upd)

                    raw_path, rel_start, rel_dur = self.engine.ad_stripper.download_session_slice(
                        sid_now, t0, t1, progress_cb=_prog_cb
                    )
                    self._safe_ui(lambda: (
                        export_pbar.set(0.75),
                        export_lbl.configure(text="Esportazione MP4 di precisione...", text_color=C_GOLD),
                    ) if my_seq == self._clip_session_seq else None)

                    final_out = out_mp4
                    mux_ok = False
                    ff = find_ffmpeg_executable()
                    flags = subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0

                    if ff:
                        r1 = subprocess.run(
                            [ff, "-y", "-fflags", "+genpts", "-ss", f"{rel_start:.3f}", "-i", raw_path,
                             "-t", f"{rel_dur:.3f}", "-c", "copy", "-avoid_negative_ts", "make_zero",
                             "-movflags", "+faststart", final_out],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags, timeout=180,
                        )
                        if r1.returncode == 0 and os.path.isfile(final_out) and os.path.getsize(final_out) > 2048:
                            mux_ok = True
                        else:
                            pre_s = max(0.0, float(rel_start) - 3.0)
                            post_s = max(0.0, float(rel_start) - pre_s)
                            r2 = subprocess.run(
                                [ff, "-y", "-fflags", "+genpts", "-ss", f"{pre_s:.3f}", "-i", raw_path,
                                 "-ss", f"{post_s:.3f}", "-t", f"{rel_dur:.3f}",
                                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                                 "-c:a", "aac", "-b:a", "160k", "-avoid_negative_ts", "make_zero",
                                 "-movflags", "+faststart", final_out],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags, timeout=300,
                            )
                            mux_ok = (r2.returncode == 0 and os.path.isfile(final_out) and os.path.getsize(final_out) > 2048)

                    if not mux_ok and self.vlc_instance:
                        try:
                            dst_vlc = final_out.replace("\\", "/")
                            if hasattr(self.vlc_instance, "media_new_path"):
                                media = self.vlc_instance.media_new_path(raw_path)
                            else:
                                media = self.vlc_instance.media_new(raw_path)
                            media.add_option(f":sout=#std{{access=file,mux=mp4,dst={dst_vlc}}}")
                            media.add_option(f":start-time={rel_start:.3f}")
                            media.add_option(f":stop-time={rel_start + rel_dur:.3f}")
                            media.add_option(":sout-keep")
                            mux_p = self.vlc_instance.media_player_new()
                            mux_p.set_media(media)
                            mux_p.play()
                            t_wait = time.time()
                            while time.time() - t_wait < max(30.0, rel_dur * 1.5 + 15.0):
                                time.sleep(0.25)
                                st_m = mux_p.get_state()
                                if st_m in (vlc.State.Ended, vlc.State.Error, vlc.State.Stopped):
                                    break
                            mux_p.stop()
                            mux_p.release()
                            mux_ok = os.path.isfile(final_out) and os.path.getsize(final_out) > 2048
                        except Exception:
                            pass

                    if not mux_ok:
                        final_out = os.path.splitext(out_mp4)[0] + os.path.splitext(raw_path)[1]
                        shutil.copy2(raw_path, final_out)

                    clip_state["saved_path"] = final_out
                    self._push_local_notification("clip", f"Clip salvata ({rel_dur:.0f}s): {os.path.basename(final_out)}", channel=ch_name)

                    def _done_ui():
                        if my_seq != self._clip_session_seq or not studio.winfo_exists():
                            return
                        clip_state["exporting"] = False
                        export_pbar.set(1.0)
                        export_lbl.configure(text=f"Clip salvata: {os.path.basename(final_out)}", text_color=C_GREEN)
                        confirm_btn.configure(state="normal", text=" Crea Un'Altra Clip", image=self._icon_check_white)
                        open_folder_btn.configure(state="normal")

                    self._safe_ui(_done_ui)
                except Exception as e:
                    def _err_ui(err=str(e)):
                        if my_seq != self._clip_session_seq or not studio.winfo_exists():
                            return
                        clip_state["exporting"] = False
                        export_pbar.set(0.0)
                        export_lbl.configure(text=f"Errore: {err}", text_color=C_LIVE)
                        confirm_btn.configure(state="normal", text=" Riprova Clip", image=self._icon_check_white)
                    self._safe_ui(_err_ui)
                finally:
                    if raw_path and os.path.isfile(raw_path):
                        try:
                            os.remove(raw_path)
                        except Exception:
                            pass

            threading.Thread(target=_export_worker, daemon=True).start()

        confirm_btn.configure(command=_confirm_and_export)

        # Inizializza sessione clip in background
        def _init_session_worker():
            sess = None
            if is_vod:
                try:
                    sess = self.engine.ad_stripper.create_vod_clip_session(
                        vod_url, vod_anchor_sec, total_vod_sec=vod_total_sec, channel=ch_name
                    )
                except Exception:
                    sess = None
            else:
                for _attempt in range(6):
                    try:
                        sess = self.engine.ad_stripper.create_live_clip_session(slot_id=slot_id, channel=ch_name)
                    except Exception:
                        sess = None
                    if sess and sess.get("total_dur", 0.0) >= 1.5:
                        break
                    if my_seq != self._clip_session_seq or not self.app_running:
                        return
                    time.sleep(0.75)

                # Se il buffer live locale ha meno di 2 minuti (es. stream appena aperta), integra fino a ~2 min dall'archivio VOD della diretta in corso
                if sess and sess.get("total_dur", 0.0) < 115.0 and my_seq == self._clip_session_seq and self.app_running:
                    self._safe_ui(lambda: (
                        loading_ov.configure(text=" Espansione cronologia live fino a 2 min...") if loading_ov.winfo_exists() else None,
                        export_lbl.configure(text="Recupero cronologia recente della diretta...", text_color=C_GOLD) if export_lbl.winfo_exists() else None,
                    ))
                    try:
                        arch_url, vod_created = self.engine.get_live_archive_vod_playlist(
                            ch_name, preferred_quality=self.quality_var.get()
                        )
                        if arch_url and my_seq == self._clip_session_seq and self.app_running:
                            if self.engine.ad_stripper.augment_live_clip_with_archive(
                                sess["sid"], arch_url, vod_created_iso=vod_created, max_total_sec=130.0
                            ):
                                with self.engine.ad_stripper._lock:
                                    updated = self.engine.ad_stripper.clip_sessions.get(sess["sid"])
                                    if updated:
                                        sess = dict(updated)
                    except Exception:
                        pass

            if my_seq != self._clip_session_seq or not self.app_running:
                if sess:
                    self.engine.ad_stripper.release_clip_session(sess["sid"])
                return

            if not sess or not sess.get("segments"):
                self._safe_ui(lambda: (
                    loading_ov.configure(text="Buffer live non ancora sufficiente: guarda la stream per qualche secondo e riprova.", image=None, text_color=C_LIVE)
                    if loading_ov.winfo_exists() else None,
                    export_lbl.configure(text="Nessun segmento pronto.", text_color=C_LIVE)
                    if export_lbl.winfo_exists() else None,
                ))
                return

            sid_new = sess["sid"]
            self._clip_active_sid = sid_new
            self.engine.ad_stripper.prefetch_session_range(sid_new, 0.0, sess["total_dur"])

            def _ready_ui():
                if my_seq != self._clip_session_seq or not studio.winfo_exists():
                    return
                try:
                    loading_ov.place_forget()
                except Exception:
                    pass
                clip_state["sid"] = sid_new
                clip_state["rev"] = 0
                clip_state["vod_offset_sec"] = float(sess.get("vod_offset_sec", 0.0) or 0.0)
                clip_state["playlist_url"] = f"http://127.0.0.1:{self.engine.ad_stripper.port}/clip_session/{sid_new}/playlist.m3u8?v=0"
                clip_state["total_dur"] = float(sess["total_dur"])
                clip_state["trim_start"] = float(sess["default_start"])
                clip_state["trim_end"] = float(sess["default_end"])
                clip_state["playhead"] = float(sess["default_start"])
                timeline.set_values(
                    total_dur=clip_state["total_dur"],
                    trim_start=clip_state["trim_start"],
                    trim_end=clip_state["trim_end"],
                    playhead=clip_state["playhead"],
                )
                _update_trim_labels()
                confirm_btn.configure(state="normal")
                export_lbl.configure(text="Pronta: controlla l'inizio clip, regola i cursori e conferma.", text_color=C_GREEN)
                _start_preview_media()
                self.after(90, _tick_clip_preview)

            self._safe_ui(_ready_ui)

        threading.Thread(target=_init_session_worker, daemon=True).start()

    def on_close(self):
        self.app_running = False
        if getattr(self, "_vol_save_after_id", None):
            try:
                self.after_cancel(self._vol_save_after_id)
            except Exception:
                pass
            self._vol_save_after_id = None
        self.save_config()
        self.close_clip_studio(restore_stage=False)
        self.close_inapp_menu(restore_chat=False)
        self._hide_vod_hover_hud()
        for win, _, _ in getattr(self, "_vod_hud_wins", []):
            try:
                win.destroy()
            except Exception:
                pass
        try:
            self.engine.ad_stripper.shutdown()
        except Exception:
            pass
        try:
            self._thumb_executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        try:
            self.emote_mgr.stop()
        except Exception:
            pass
        for tile in list(self.multi_tiles):
            try:
                self._destroy_tile_resources(tile)
            except Exception:
                pass
        self.multi_tiles.clear()
        self._stop_pip_wheel_hook()
        self._stop_all_engines()
        self.chat.disconnect()
        if sys.platform.startswith("win"):
            try:
                hwnd_file = os.path.join(tempfile.gettempdir(), "twixy_active_hwnd.txt")
                if os.path.isfile(hwnd_file):
                    with open(hwnd_file, "r", encoding="utf-8") as f:
                        lines = f.read().splitlines()
                    if len(lines) >= 2 and str(os.getpid()) == lines[1].strip():
                        os.remove(hwnd_file)
            except Exception:
                pass
            _release_single_instance_lock()
        self.destroy()


class _ClipTimelineCanvas(tk.Canvas):
    """Timeline interattiva ad alta precisione con maniglie Inizio/Fine trascinabili anche oltre 2+ minuti."""

    def __init__(self, parent, on_handle_drag=None, on_handle_release=None, on_seek=None):
        super().__init__(parent, height=68, bg="#111118", highlightthickness=1, highlightbackground="#272732", bd=0, cursor="hand2")
        self._on_handle_drag = on_handle_drag
        self._on_handle_release = on_handle_release
        self._on_seek = on_seek
        self.total_dur = 30.0
        self.trim_start = 0.0
        self.trim_end = 30.0
        self.playhead = 0.0
        self._drag_mode = None
        self._drag_start_x = 0
        self._drag_orig_start = 0.0
        self._drag_moved = False
        self._pad_x = 18

        self.bind("<Configure>", lambda _e: self._redraw())
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_values(self, total_dur=None, trim_start=None, trim_end=None, playhead=None):
        if total_dur is not None:
            self.total_dur = max(1.0, float(total_dur))
        if trim_start is not None:
            self.trim_start = max(0.0, float(trim_start))
        if trim_end is not None:
            self.trim_end = max(self.trim_start + 0.5, min(self.total_dur, float(trim_end)))
        if playhead is not None:
            self.playhead = max(0.0, min(self.total_dur, float(playhead)))
        self._redraw()

    def _t_to_x(self, t):
        w = max(120, self.winfo_width())
        span = max(10, w - 2 * self._pad_x)
        ratio = max(0.0, min(1.0, float(t) / max(0.5, self.total_dur)))
        return self._pad_x + ratio * span

    def _x_to_t(self, x):
        w = max(120, self.winfo_width())
        span = max(10, w - 2 * self._pad_x)
        ratio = max(0.0, min(1.0, (float(x) - self._pad_x) / span))
        return ratio * max(0.5, self.total_dur)

    @staticmethod
    def _fmt(sec):
        sec = max(0.0, float(sec))
        m, s = divmod(int(sec), 60)
        t = int(round((sec - int(sec)) * 10)) % 10
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}.{t}" if h else f"{m:02d}:{s:02d}.{t}"

    def _redraw(self):
        self.delete("all")
        w = max(120, self.winfo_width())
        x0 = self._pad_x
        xr = w - self._pad_x
        y_top, y_bot = 28, 52

        # Sfondo barra e tacche temporali
        self.create_rectangle(x0, y_top, xr, y_bot, fill="#1d1d28", outline="#2e2e3d")
        tot = max(1.0, self.total_dur)
        step = 30.0 if tot >= 120 else (15.0 if tot >= 45 else 5.0)
        cur_t = 0.0
        while cur_t <= tot + 0.01:
            tx = self._t_to_x(cur_t)
            self.create_line(tx, y_bot + 1, tx, y_bot + 5, fill="#525266")
            if cur_t == 0 or tx < xr - 24:
                self.create_text(tx, y_bot + 11, text=f"{int(cur_t // 60)}:{int(cur_t % 60):02d}", fill="#8c8ca6", font=("Consolas", 8))
            cur_t += step

        sx1 = self._t_to_x(self.trim_start)
        sx2 = self._t_to_x(self.trim_end)

        # Selezione attiva evidenziata
        self.create_rectangle(sx1, y_top, sx2, y_bot, fill="#4c1d95", outline="#8b5cf6", width=2)

        # Etichette in alto sopra maniglie
        self.create_text(max(x0 + 28, min(xr - 90, sx1)), 14, text=f"INIZIO {self._fmt(self.trim_start)}", fill="#c4b5fd", font=("Consolas", 9, "bold"))
        dur = max(0.0, self.trim_end - self.trim_start)
        mid_x = (sx1 + sx2) / 2.0
        if sx2 - sx1 >= 95:
            self.create_text(mid_x, (y_top + y_bot) / 2.0, text=f"{dur:.1f}s", fill="#f5f3ff", font=("Segoe UI", 10, "bold"))
        self.create_text(min(xr - 28, max(x0 + 90, sx2)), 14, text=f"FINE {self._fmt(self.trim_end)}", fill="#67e8f9", font=("Consolas", 9, "bold"))

        # Maniglia sinistra (Viola) e Maniglia destra (Ciano)
        self.create_rectangle(sx1 - 5, y_top - 3, sx1 + 5, y_bot + 3, fill="#8b5cf6", outline="#ffffff", width=1)
        self.create_line(sx1, y_top + 5, sx1, y_bot - 5, fill="#ffffff", width=1)
        self.create_rectangle(sx2 - 5, y_top - 3, sx2 + 5, y_bot + 3, fill="#06b6d4", outline="#ffffff", width=1)
        self.create_line(sx2, y_top + 5, sx2, y_bot - 5, fill="#ffffff", width=1)

        # Playhead (cursore fotogramma corrente)
        px = self._t_to_x(self.playhead)
        self.create_line(px, y_top - 6, px, y_bot + 5, fill="#ffffff", width=2)
        self.create_polygon(px - 5, y_top - 7, px + 5, y_top - 7, px, y_top, fill="#ffffff")

    def _on_press(self, event):
        x = event.x
        sx1 = self._t_to_x(self.trim_start)
        sx2 = self._t_to_x(self.trim_end)
        d1 = abs(x - sx1)
        d2 = abs(x - sx2)
        self._drag_start_x = x
        self._drag_moved = False
        self._drag_orig_start = self.trim_start
        if d1 <= 14 and d1 <= d2:
            self._drag_mode = "start"
        elif d2 <= 14:
            self._drag_mode = "end"
        elif sx1 < x < sx2:
            self._drag_mode = "move"
        else:
            self._drag_mode = "seek"
            if self._on_seek:
                self._on_seek(self._x_to_t(x))

    def _on_motion(self, event):
        if abs(event.x - self._drag_start_x) > 3:
            self._drag_moved = True
        if self._drag_mode == "start":
            t = max(0.0, min(self.trim_end - 1.0, self._x_to_t(event.x)))
            if self._on_handle_drag:
                self._on_handle_drag("start", t)
        elif self._drag_mode == "end":
            t = max(self.trim_start + 1.0, min(self.total_dur, self._x_to_t(event.x)))
            if self._on_handle_drag:
                self._on_handle_drag("end", t)
        elif self._drag_mode == "move" and self._drag_moved:
            dt = self._x_to_t(event.x) - self._x_to_t(self._drag_start_x)
            if self._on_handle_drag:
                self._on_handle_drag("move", self._drag_orig_start + dt)
        elif self._drag_mode == "seek" and self._on_seek:
            self._on_seek(self._x_to_t(event.x))

    def _on_release(self, event):
        mode = self._drag_mode
        moved = self._drag_moved
        self._drag_mode = None
        if mode == "start" and self._on_handle_release:
            t = max(0.0, min(self.trim_end - 1.0, self._x_to_t(event.x)))
            self._on_handle_release("start", t)
        elif mode == "end" and self._on_handle_release:
            t = max(self.trim_start + 1.0, min(self.total_dur, self._x_to_t(event.x)))
            self._on_handle_release("end", t)
        elif mode == "move":
            if moved and self._on_handle_release:
                dt = self._x_to_t(event.x) - self._x_to_t(self._drag_start_x)
                self._on_handle_release("move", self._drag_orig_start + dt)
            elif not moved and self._on_seek:
                self._on_seek(self._x_to_t(event.x))


_SINGLE_INSTANCE_MUTEX_NAME = r"Local\PeppeZ_Twixy_SingleInstance_Mutex"
_SINGLE_INSTANCE_MUTEX_HANDLE = None


def _acquire_single_instance_lock():
    global _SINGLE_INSTANCE_MUTEX_HANDLE
    if not sys.platform.startswith("win"):
        return True
    try:
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        k32.CreateMutexW.restype = wintypes.HANDLE
        handle = k32.CreateMutexW(None, False, _SINGLE_INSTANCE_MUTEX_NAME)
        last_err = k32.GetLastError()
        ERROR_ALREADY_EXISTS = 183
        if not handle:
            return True
        if last_err == ERROR_ALREADY_EXISTS:
            try:
                k32.CloseHandle(handle)
            except Exception:
                pass
            return False
        _SINGLE_INSTANCE_MUTEX_HANDLE = handle
    except Exception:
        pass
    return True


def _release_single_instance_lock():
    global _SINGLE_INSTANCE_MUTEX_HANDLE
    if sys.platform.startswith("win") and _SINGLE_INSTANCE_MUTEX_HANDLE:
        try:
            ctypes.windll.kernel32.CloseHandle(_SINGLE_INSTANCE_MUTEX_HANDLE)
        except Exception:
            pass
        _SINGLE_INSTANCE_MUTEX_HANDLE = None


def _focus_existing_twixy_instance():
    if not sys.platform.startswith("win"):
        return
    try:
        hwnd = None
        hwnd_file = os.path.join(tempfile.gettempdir(), "twixy_active_hwnd.txt")
        if os.path.isfile(hwnd_file):
            with open(hwnd_file, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            if lines and lines[0].strip().isdigit():
                cand = int(lines[0].strip())
                if user32.IsWindow(cand):
                    hwnd = cand
        if not hwnd:
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
            found = []

            def _cb(h, _lp):
                try:
                    if user32.IsWindowVisible(h):
                        n_len = user32.GetWindowTextLengthW(h)
                        if n_len > 0:
                            buf = ctypes.create_unicode_buffer(n_len + 1)
                            user32.GetWindowTextW(h, buf, n_len + 1)
                            if "Twixy" in buf.value:
                                found.append(h)
                                return False
                except Exception:
                    pass
                return True

            user32.EnumWindows(EnumWindowsProc(_cb), 0)
            if found:
                hwnd = found[0]
        if hwnd:
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            else:
                user32.ShowWindow(hwnd, 5)  # SW_SHOW
            user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


if __name__ == "__main__":
    if not _acquire_single_instance_lock():
        _focus_existing_twixy_instance()
        sys.exit(0)
    app = TwixyDesktopApp()
    app.mainloop()
    _release_single_instance_lock()
