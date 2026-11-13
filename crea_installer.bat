@echo off & for %%P in (python.exe py.exe "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%LOCALAPPDATA%\Programs\Python\Python311\python.exe") do (%%P --version >nul 2>nul && (%%P -x "%~f0" & pause & exit /b)) & echo [ERRORE] Python 3 non trovato. Installalo da https://www.python.org/ e seleziona "Add Python to PATH". & pause & exit /b
import os
import sys
import json
import shutil
import struct
import zipfile
import platform
import traceback
import subprocess
import urllib.request

def _detect_target_arch():
    machine = (platform.machine() or "").lower()
    bits = struct.calcsize("P") * 8
    if "arm64" in machine or "aarch64" in machine:
        return "win_arm64", "Windows ARM64"
    if bits == 64 or "amd64" in machine or "x86_64" in machine:
        return "win_x64", "Windows x64"
    return "win_x86", "Windows x86 (32-bit)"

ARCH_TAG, ARCH_LABEL = _detect_target_arch()
SETUP_NAME = f"Twixy_Setup_{ARCH_TAG}"
SETUP_EXE_NAME = f"{SETUP_NAME}.exe"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(BASE_DIR, "vendor")
VLC_DEST = os.path.join(VENDOR_DIR, "vlc")
MPV_DEST = os.path.join(VENDOR_DIR, "mpv")
LOGO_ICO = os.path.join(BASE_DIR, "logo.ico")
LOGO_PNG = os.path.join(BASE_DIR, "logo.png")
GUI_SCRIPT = os.path.join(BASE_DIR, "xtra_gui.py")
EMOTE_ENGINE = os.path.join(BASE_DIR, "emote_engine.py")

VLC_ZIP_URL = "https://ftp.fau.de/videolan/vlc/3.0.21/win64/vlc-3.0.21-win64.zip"


def check_and_autofix_files():
    if not os.path.isfile(GUI_SCRIPT) and os.path.isfile(GUI_SCRIPT + ".txt"):
        shutil.move(GUI_SCRIPT + ".txt", GUI_SCRIPT)
    if not os.path.isfile(LOGO_ICO) and os.path.isfile(LOGO_ICO + ".txt"):
        shutil.move(LOGO_ICO + ".txt", LOGO_ICO)

    if not os.path.isfile(GUI_SCRIPT):
        raise FileNotFoundError(f"Non trovo 'xtra_gui.py' nella cartella:\n{BASE_DIR}")

    with open(GUI_SCRIPT, "r", encoding="utf-8") as f:
        code = f.read()
    if "def get_ root_hwnd" in code:
        code = code.replace("def get_ root_hwnd", "def get_root_hwnd")
        with open(GUI_SCRIPT, "w", encoding="utf-8") as f:
            f.write(code)


def ensure_build_packages():
    print("\n[1/5] Verifica librerie (PyInstaller, CustomTkinter, Pillow, Requests, VLC, 7zr)...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install",
        "pyinstaller", "customtkinter", "pillow", "requests", "python-vlc", "py7zr"
    ])


def ensure_logo_ico():
    if os.path.isfile(LOGO_PNG):
        try:
            from PIL import Image
            img = Image.open(LOGO_PNG).convert("RGBA")
            # Ridimensiona mantenendo le proporzioni dentro un quadrato 256x256 per un'icona Windows nitida
            max_dim = max(img.size)
            if img.size[0] != img.size[1]:
                canvas = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
                offset = ((max_dim - img.size[0]) // 2, (max_dim - img.size[1]) // 2)
                canvas.paste(img, offset, img)
                img = canvas
            img.save(LOGO_ICO, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            print(f"[OK] Icona ad alta qualita' generata da logo.png -> {LOGO_ICO}")
            return
        except Exception as e:
            print(f"[Nota] Impossibile convertire logo.png ({e}), provo logo.ico esistente...")

    if os.path.isfile(LOGO_ICO):
        try:
            from PIL import Image
            img = Image.open(LOGO_ICO)
            if img.format != "ICO":
                img.save(LOGO_ICO, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
            print(f"[OK] Icona pronta: {LOGO_ICO}")
            return
        except Exception:
            pass

    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((16, 16, 240, 240), radius=56, fill=(139, 92, 246, 255))
    draw.polygon([(95, 75), (95, 181), (185, 128)], fill=(255, 255, 255, 255))
    img.save(LOGO_ICO, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])


def bundle_vlc_64():
    os.makedirs(VLC_DEST, exist_ok=True)
    if os.path.isfile(os.path.join(VLC_DEST, "libvlc.dll")) and os.path.isdir(os.path.join(VLC_DEST, "plugins")):
        print("[2/5] VLC 64-bit e plugins gia' presenti in vendor/vlc.")
        return

    port_vlc = os.path.join(BASE_DIR, "vlc_portable", "vlc-3.0.21")
    sys_vlc = r"C:\Program Files\VideoLAN\VLC"
    for source_dir in [port_vlc, sys_vlc]:
        if os.path.isfile(os.path.join(source_dir, "libvlc.dll")):
            print(f"[2/5] Copio VLC 64-bit da {source_dir} in vendor/vlc...")
            for f in ["libvlc.dll", "libvlccore.dll"]:
                shutil.copy2(os.path.join(source_dir, f), os.path.join(VLC_DEST, f))
            shutil.copytree(os.path.join(source_dir, "plugins"), os.path.join(VLC_DEST, "plugins"), dirs_exist_ok=True)
            return

    print("[2/5] Download VLC 64-bit Portable per l'installer (~42 MB)...")
    tmp_zip = os.path.join(BASE_DIR, "vlc_bundle.zip")
    urllib.request.urlretrieve(VLC_ZIP_URL, tmp_zip)
    with zipfile.ZipFile(tmp_zip, "r") as zf:
        zf.extractall(VENDOR_DIR)
    os.remove(tmp_zip)

    extracted = os.path.join(VENDOR_DIR, "vlc-3.0.21")
    if os.path.isdir(extracted):
        for item in os.listdir(extracted):
            shutil.move(os.path.join(extracted, item), os.path.join(VLC_DEST, item))
        shutil.rmtree(extracted, ignore_errors=True)
    print("[OK] VLC 64-bit integrato in vendor/vlc.")


def bundle_mpv_64():
    os.makedirs(MPV_DEST, exist_ok=True)
    if os.path.isfile(os.path.join(MPV_DEST, "mpv.exe")):
        print("[3/5] MPV 64-bit gia' presente in vendor/mpv.")
        return

    which_mpv = shutil.which("mpv")
    if which_mpv and os.path.isfile(which_mpv):
        shutil.copy2(which_mpv, os.path.join(MPV_DEST, "mpv.exe"))
        return

    print("[3/5] Ricerca ultima release MPV 64-bit da GitHub...")
    try:
        api_url = "https://api.github.com/repos/shinchiro/mpv-winbuild-cmake/releases/latest"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            rel_data = json.loads(r.read().decode("utf-8"))

        dl_url = None
        for asset in rel_data.get("assets", []):
            name = asset.get("name", "")
            if name.startswith("mpv-x86_64-") and name.endswith(".7z") and "v3" not in name:
                dl_url = asset.get("browser_download_url")
                break

        if dl_url:
            print(f"      Scaricamento: {os.path.basename(dl_url)}...")
            tmp_7z = os.path.join(BASE_DIR, "mpv_bundle.7z")
            req_dl = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_dl, timeout=60) as resp, open(tmp_7z, "wb") as out:
                shutil.copyfileobj(resp, out)
            import py7zr
            with py7zr.SevenZipFile(tmp_7z, mode="r") as z:
                z.extractall(path=MPV_DEST)
            os.remove(tmp_7z)
            print("[OK] MPV 64-bit integrato in vendor/mpv.")
    except Exception as e:
        print(f"[Nota] MPV opzionale saltato ({e}), VLC 64-bit principale e' incluso.")


def build_twixy_app():
    print("[4/5] Compilazione di Twixy.exe (con inclusione forzata di libvlc.dll e runtime C++)...")
    libvlc_dll = os.path.join(VLC_DEST, "libvlc.dll")
    libvlccore_dll = os.path.join(VLC_DEST, "libvlccore.dll")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name", "Twixy",
        f"--icon={LOGO_ICO}",
        "--paths", BASE_DIR,
        "--collect-all", "customtkinter",
        "--hidden-import", "vlc",
        "--hidden-import", "PIL",
        "--hidden-import", "requests",
        "--hidden-import", "emote_engine",
        f"--add-binary={libvlc_dll};.",
        f"--add-binary={libvlccore_dll};.",
        f"--add-data={LOGO_ICO};.",
        f"--add-data={VENDOR_DIR};vendor",
    ]
    if os.path.isfile(EMOTE_ENGINE):
        cmd.append(f"--add-data={EMOTE_ENGINE};.")
    if os.path.isfile(LOGO_PNG):
        cmd.append(f"--add-data={LOGO_PNG};.")
    cmd.append(GUI_SCRIPT)
    subprocess.check_call(cmd, cwd=BASE_DIR)

    # Copia di sicurezza di libvlc.dll, libvlccore.dll, plugins/, logo e VC++ runtime anche nella root di dist/Twixy
    dist_twixy = os.path.join(BASE_DIR, "dist", "Twixy")
    if os.path.isfile(EMOTE_ENGINE):
        shutil.copy2(EMOTE_ENGINE, os.path.join(dist_twixy, "emote_engine.py"))
    if os.path.isfile(LOGO_ICO):
        shutil.copy2(LOGO_ICO, os.path.join(dist_twixy, "logo.ico"))
    if os.path.isfile(LOGO_PNG):
        shutil.copy2(LOGO_PNG, os.path.join(dist_twixy, "logo.png"))
    for dll_name in ["libvlc.dll", "libvlccore.dll"]:
        src_dll = os.path.join(VLC_DEST, dll_name)
        if os.path.isfile(src_dll):
            shutil.copy2(src_dll, os.path.join(dist_twixy, dll_name))

    # Copia anche le cartelle vendor/vlc e plugins accanto a Twixy.exe così qualsiasi PC senza VLC le trova al 100%
    shutil.copytree(VENDOR_DIR, os.path.join(dist_twixy, "vendor"), dirs_exist_ok=True)
    if os.path.isdir(os.path.join(VLC_DEST, "plugins")):
        shutil.copytree(os.path.join(VLC_DEST, "plugins"), os.path.join(dist_twixy, "plugins"), dirs_exist_ok=True)

    # Copia le DLL C++ di Windows (vcruntime140.dll, msvcp140.dll) per i PC che non hanno Visual C++ Redistributable
    sys32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    for vc_dll in ["vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"]:
        vc_p = os.path.join(sys32, vc_dll)
        if os.path.isfile(vc_p):
            shutil.copy2(vc_p, os.path.join(dist_twixy, vc_dll))

    print("[OK] Applicazione completa compilata in dist\\Twixy\\Twixy.exe")


def build_standalone_installer():
    print(f"[5/5] Creazione dell'Installer Classico di Windows '{SETUP_EXE_NAME}' ({ARCH_LABEL})...")
    dist_twixy = os.path.join(BASE_DIR, "dist", "Twixy")
    payload_zip = os.path.join(BASE_DIR, "twixy_payload.zip")

    with zipfile.ZipFile(payload_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, _, files in os.walk(dist_twixy):
            for file in files:
                full_p = os.path.join(root_dir, file)
                rel_p = os.path.relpath(full_p, dist_twixy)
                zf.write(full_p, rel_p)

    setup_script = os.path.join(BASE_DIR, "_twixy_setup_wizard.py")
    with open(setup_script, "w", encoding="utf-8") as f:
        f.write(f"ARCH_LABEL = {ARCH_LABEL!r}\nARCH_TAG = {ARCH_TAG!r}\n")
        f.write('''import os, sys, shutil, zipfile, subprocess, threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
PAYLOAD_ZIP = os.path.join(BUNDLE_DIR, "twixy_payload.zip")
LOGO_ICO = os.path.join(BUNDLE_DIR, "logo.ico")
DEFAULT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "Programs", "Twixy")

def get_desktop_dir():
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 0x0010, None, 0, buf) == 0 and os.path.isdir(buf.value):
            return buf.value
    except Exception:
        pass
    return os.path.join(os.path.expanduser("~"), "Desktop")

def refresh_windows_icon_cache():
    try:
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except Exception:
        pass
    try:
        subprocess.run(["ie4uinit.exe", "-show"], creationflags=0x08000000, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def create_shortcut(target_exe, shortcut_path, icon_path):
    try:
        if os.path.exists(shortcut_path):
            os.remove(shortcut_path)
    except Exception:
        pass
    t_esc = target_exe.replace("'", "''")
    s_esc = shortcut_path.replace("'", "''")
    w_esc = os.path.dirname(target_exe).replace("'", "''")
    i_esc = icon_path.replace("'", "''")
    ps_code = f"""
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{s_esc}')
    $Shortcut.TargetPath = '{t_esc}'
    $Shortcut.WorkingDirectory = '{w_esc}'
    $Shortcut.IconLocation = '{i_esc},0'
    $Shortcut.Save()
    """
    subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_code], creationflags=0x08000000)

class ClassicWindowsSetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"Installazione di Twixy ({ARCH_LABEL})")
        self.geometry("580x400")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")
        if os.path.isfile(LOGO_ICO):
            try:
                self.iconbitmap(LOGO_ICO)
            except Exception:
                pass

        self.install_dir_var = tk.StringVar(value=DEFAULT_DIR)
        self.desktop_shortcut_var = tk.BooleanVar(value=True)
        self.startmenu_shortcut_var = tk.BooleanVar(value=True)
        self.launch_now_var = tk.BooleanVar(value=True)

        # Header Bianco stile Windows Wizard
        self.top_banner = tk.Frame(self, bg="#ffffff", height=68)
        self.top_banner.pack(side="top", fill="x")
        self.top_banner.pack_propagate(False)
        self.hdr_title = tk.Label(self.top_banner, text=f"Benvenuti nel programma di installazione di Twixy ({ARCH_LABEL})", bg="#ffffff", fg="#111111", font=("Segoe UI", 12, "bold"))
        self.hdr_title.pack(anchor="w", padx=20, pady=(12, 2))
        self.hdr_sub = tk.Label(self.top_banner, text=f"Edizione {ARCH_LABEL} (VLC e MPV inclusi).", bg="#ffffff", fg="#555555", font=("Segoe UI", 9))
        self.hdr_sub.pack(anchor="w", padx=20)

        tk.Frame(self, bg="#d0d0d0", height=1).pack(side="top", fill="x")

        # Contenitore centrale per le pagine del Wizard
        self.body = tk.Frame(self, bg="#f0f0f0", padx=24, pady=18)
        self.body.pack(side="top", fill="both", expand=True)

        # Barra pulsanti in basso (Indietro, Avanti, Annulla)
        tk.Frame(self, bg="#d0d0d0", height=1).pack(side="bottom", fill="x")
        self.bottom_bar = tk.Frame(self, bg="#e6e6e6", height=48, padx=14, pady=8)
        self.bottom_bar.pack(side="bottom", fill="x")
        self.bottom_bar.pack_propagate(False)

        self.btn_cancel = ttk.Button(self.bottom_bar, text="Annulla", width=12, command=self.destroy)
        self.btn_cancel.pack(side="right", padx=4)

        self.btn_next = ttk.Button(self.bottom_bar, text="Avanti >", width=14, command=self.go_step_2)
        self.btn_next.pack(side="right", padx=4)

        self.btn_back = ttk.Button(self.bottom_bar, text="< Indietro", width=12, state="disabled")
        self.btn_back.pack(side="right", padx=4)

        self.show_step_1()

    def _clear_body(self):
        for w in self.body.winfo_children():
            w.destroy()

    def show_step_1(self):
        self._clear_body()
        self.hdr_title.config(text=f"Benvenuti nel programma di installazione di Twixy ({ARCH_LABEL})")
        self.hdr_sub.config(text=f"Pacchetto completo standalone per {ARCH_LABEL} (non richiede VLC o librerie esterne).")
        self.btn_back.config(state="disabled")
        self.btn_next.config(text="Avanti >", state="normal", command=self.go_step_2)

        tk.Label(
            self.body,
            text=f"Il programma installerà Twixy ({ARCH_LABEL}) sul tuo computer.\\n\\n"
                 "Componenti già inclusi automaticamente nel pacchetto:\\n"
                 "  • Motore Video VLC 64-bit (libvlc.dll + plugins nativi)\\n"
                 "  • Motore Video MPV 64-bit GPU\\n"
                 "  • Runtime C++ di sistema e librerie grafiche\\n"
                 "  • Filtro locale Anti-Ad 1080p60 e Sblocco VOD Sub-Only\\n\\n"
                 "Clicca su 'Avanti' per scegliere la cartella di installazione.",
            bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9), justify="left"
        ).pack(anchor="w", pady=10)

    def go_step_2(self):
        self._clear_body()
        self.hdr_title.config(text="Selezione della cartella di destinazione")
        self.hdr_sub.config(text="Scegli la cartella in cui vuoi installare Twixy.")
        self.btn_back.config(state="normal", command=self.show_step_1)
        self.btn_next.config(text="Installa", state="normal", command=self.go_step_3_install)

        tk.Label(self.body, text="Cartella di destinazione:", bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(4, 4))

        dir_row = tk.Frame(self.body, bg="#f0f0f0")
        dir_row.pack(fill="x", pady=(0, 14))

        entry = ttk.Entry(dir_row, textvariable=self.install_dir_var, font=("Segoe UI", 9))
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8), ipady=2)

        def browse_dir():
            chosen = filedialog.askdirectory(title="Scegli la cartella di installazione di Twixy", initialdir=os.path.dirname(self.install_dir_var.get()))
            if chosen:
                if not chosen.lower().endswith("twixy"):
                    chosen = os.path.join(chosen, "Twixy")
                self.install_dir_var.set(os.path.normpath(chosen))

        ttk.Button(dir_row, text="Sfoglia...", width=12, command=browse_dir).pack(side="right")

        tk.Label(self.body, text="Opzioni aggiuntive:", bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(8, 4))
        ttk.Checkbutton(self.body, text="Crea un'icona sul Desktop", variable=self.desktop_shortcut_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(self.body, text="Crea un collegamento nel Menu Start", variable=self.startmenu_shortcut_var).pack(anchor="w", pady=2)

    def go_step_3_install(self):
        target_dir = self.install_dir_var.get().strip()
        if not target_dir:
            messagebox.showwarning("Cartella mancante", "Specifica una cartella di installazione valida.")
            return

        self._clear_body()
        self.hdr_title.config(text="Installazione in corso...")
        self.hdr_sub.config(text="Attendere mentre i file di Twixy vengono estratti e configurati.")
        self.btn_back.config(state="disabled")
        self.btn_next.config(state="disabled")
        self.btn_cancel.config(state="disabled")

        self.status_lbl = tk.Label(self.body, text="Preparazione cartella...", bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9))
        self.status_lbl.pack(anchor="w", pady=(15, 6))

        self.prog = ttk.Progressbar(self.body, orient="horizontal", length=520, mode="determinate")
        self.prog.pack(fill="x", pady=6)

        threading.Thread(target=lambda: self._install_worker(target_dir), daemon=True).start()

    def _stop_running_twixy(self, target_dir):
        exe_target = os.path.join(target_dir, "Twixy.exe")
        for cmd in (
            ["taskkill", "/F", "/IM", "Twixy.exe", "/T"],
        ):
            try:
                subprocess.run(cmd, creationflags=0x08000000, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            except Exception:
                pass
        # Attendi il rilascio degli handle sui binari (fino a ~4s)
        import time
        deadline = time.time() + 4.0
        while time.time() < deadline:
            if not os.path.exists(exe_target):
                break
            try:
                with open(exe_target, "ab"):
                    break
            except PermissionError:
                time.sleep(0.25)
            except Exception:
                break

    def _install_worker(self, target_dir):
        import time
        try:
            os.makedirs(target_dir, exist_ok=True)
            self.after(0, lambda: self.status_lbl.config(text="Chiusura di Twixy in esecuzione e controllo permessi..."))
            self._stop_running_twixy(target_dir)

            with zipfile.ZipFile(PAYLOAD_ZIP, "r") as zf:
                members = zf.namelist()
                total = max(1, len(members))
                for idx, m in enumerate(members, 1):
                    for attempt in range(5):
                        try:
                            zf.extract(m, target_dir)
                            break
                        except PermissionError:
                            if attempt == 4:
                                raise
                            if attempt == 0:
                                self._stop_running_twixy(target_dir)
                            time.sleep(0.35)
                    if idx == 1 or idx % 5 == 0 or idx == total:
                        pct = int(idx * 100 / total)
                        self.after(0, lambda p=pct, name=m: (
                            self.prog.config(value=p),
                            self.status_lbl.config(text=f"Estrazione ({p}%): {os.path.basename(name) or name}")
                        ))

            exe_path = os.path.join(target_dir, "Twixy.exe")
            ico_path = os.path.join(target_dir, "logo.ico")
            if not os.path.isfile(ico_path):
                ico_path = exe_path

            # Crea uno script di disinstallazione rapida nella cartella scelta
            uninst_bat = os.path.join(target_dir, "Uninstall_Twixy.bat")
            with open(uninst_bat, "w", encoding="utf-8") as uf:
                uf.write(f'@echo off\\necho Rimozione di Twixy in corso...\\nrmdir /s /q "{target_dir}"\\n')

            if self.desktop_shortcut_var.get():
                desktop = get_desktop_dir()
                if os.path.isdir(desktop):
                    create_shortcut(exe_path, os.path.join(desktop, "Twixy.lnk"), ico_path)

            if self.startmenu_shortcut_var.get():
                start_menu = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\\Windows\\Start Menu\\Programs")
                if os.path.isdir(start_menu):
                    create_shortcut(exe_path, os.path.join(start_menu, "Twixy.lnk"), ico_path)

            refresh_windows_icon_cache()
            self.after(0, lambda: self.show_step_4_done(exe_path, target_dir))
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda msg=err_msg: (
                messagebox.showerror(
                    "Errore Installazione",
                    f"Impossibile scrivere nella cartella selezionata.\\nChiudi eventuali finestre di Twixy aperte o scegli un'altra cartella.\\n\\nDettaglio: {msg}"
                ),
                self.go_step_2()
            ))

    def show_step_4_done(self, exe_path, target_dir):
        self._clear_body()
        self.hdr_title.config(text="Installazione di Twixy completata!")
        self.hdr_sub.config(text="Twixy è stato installato correttamente sul computer.")

        tk.Label(
            self.body,
            text=f"Twixy è stato installato con successo in:\\n{target_dir}\\n\\n"
                 "Tutte le librerie e i motori video (VLC 64-bit e MPV) sono stati configurati.",
            bg="#f0f0f0", fg="#222222", font=("Segoe UI", 9), justify="left"
        ).pack(anchor="w", pady=(10, 14))

        ttk.Checkbutton(self.body, text="Avvia Twixy adesso", variable=self.launch_now_var).pack(anchor="w", pady=4)

        def finish_setup():
            if self.launch_now_var.get() and os.path.isfile(exe_path):
                subprocess.Popen([exe_path], cwd=target_dir)
            self.destroy()

        self.btn_next.config(text="Fine", state="normal", command=finish_setup)

if __name__ == "__main__":
    ClassicWindowsSetupWizard().mainloop()
''')

    cmd_setup = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name", SETUP_NAME,
        f"--icon={LOGO_ICO}",
        f"--add-data={LOGO_ICO};.",
        f"--add-data={payload_zip};.",
        setup_script
    ]
    subprocess.check_call(cmd_setup, cwd=BASE_DIR)

    for tmp in [payload_zip, setup_script]:
        try:
            os.remove(tmp)
        except Exception:
            pass

    print("\n============================================================")
    print("COMPLETATO CON SUCCESSO!")
    print(f"-> Target compilazione: {ARCH_LABEL} ({ARCH_TAG})")
    print(f"-> Installer pronto: {os.path.join(BASE_DIR, 'dist', SETUP_EXE_NAME)}")
    print("============================================================")


if __name__ == "__main__":
    try:
        print(f"=== AVVIO CREAZIONE INSTALLER TWIXY ({ARCH_LABEL} / {ARCH_TAG}) ===")
        check_and_autofix_files()
        ensure_build_packages()
        ensure_logo_ico()
        bundle_vlc_64()
        bundle_mpv_64()
        build_twixy_app()
        build_standalone_installer()
    except Exception:
        print("\n[ERRORE DURANTE LA COMPILAZIONE]:")
        traceback.print_exc()