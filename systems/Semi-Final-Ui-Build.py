# Modern UI test version of FileManagerUI (pre-symbols version)
# This file is a copy of ModernFileManagerUI.py before file icon symbol logic was added.

# --- EARLY ERROR LOGGING ---
try:
    with open("error_log.txt", "a", encoding="utf-8") as f:
        f.write("[STARTUP] Script loaded.\n")
except Exception:
    pass

import os
import sys
import subprocess
from datetime import datetime
from typing import List, Dict
import tkinter as tk
import json
import threading
import requests
from io import BytesIO
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from PIL import Image, ImageTk
try:
    import win32api
    import win32con
    import win32gui
    import win32ui
except ImportError:
    win32api = win32con = win32gui = win32ui = None

if sys.platform.startswith('win') and hasattr(sys, 'frozen') == False:
    try:
        import ctypes
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except Exception:
        pass

# --- Github logo URLs ---
GITHUB_LOGO2_URL = "https://raw.githubusercontent.com/toastersss/Scanner-Gate/main/SmallIco.png"  # icon-only
GITHUB_LOGO_WITH_TEXT_URL = "https://raw.githubusercontent.com/toastersss/Scanner-Gate/main/largeIco.png"  # logo with text

def fetch_logo2_from_github():
    try:
        resp = requests.get(GITHUB_LOGO2_URL, timeout=10)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))
    except Exception as e:
        print(f"Failed to fetch logo2 from GitHub: {e}")
        return None

def fetch_logo_with_text_from_github():
    try:
        resp = requests.get(GITHUB_LOGO_WITH_TEXT_URL, timeout=10)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content))
    except Exception as e:
        print(f"Failed to fetch logo_with_text from GitHub: {e}")
        return None

class FileInfo:
    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path)
        self.last_modified = datetime.fromtimestamp(os.path.getmtime(path))
        self.size = os.path.getsize(path)

    def as_dict(self):
        return {
            "Name": self.name,
            "Path": self.path,
            "Last Modified": self.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
            "Size (KB)": f"{self.size // 1024}"
        }

def scan_directory(directory: str) -> List[FileInfo]:
    files = []
    for entry in os.scandir(directory):
        if entry.is_file():
            files.append(FileInfo(entry.path))
    return files

def open_file_with_default_app(filepath: str):
    if sys.platform.startswith('darwin'):
        subprocess.call(('open', filepath))
    elif os.name == 'nt':
        os.startfile(filepath)
    elif os.name == 'posix':
        subprocess.call(('xdg-open', filepath))

def log_error(msg, exc=None):
    try:
        with open("error_log.txt", "a", encoding="utf-8") as f:
            f.write(msg + "\n")
            if exc:
                import traceback
                traceback.print_exc(file=f)
    except Exception:
        pass
    print(msg)
    if exc:
        import traceback
        traceback.print_exc()

SHGFI_ICON = 0x000000100
SHGFI_SMALLICON = 0x000000001
SHGFI_USEFILEATTRIBUTES = 0x000000010
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_ATTRIBUTE_NORMAL = 0x80
DI_NORMAL = 0x0003

class FileManagerUI(tk.Tk):
    def __init__(self):
        # --- EARLY ERROR LOGGING ---
        self.first_scan_done = False

        try:
            with open("error_log.txt", "a", encoding="utf-8") as f:
                f.write("[INIT] Entered FileManagerUI.__init__\n")
        except Exception:
            pass
        try:
            log_error("FileManagerUI __init__ starting...")
            # Log pywin32 availability at startup
            if not (win32api and win32gui and win32ui):
                log_error("pywin32 not available: icons will not be shown.")
            else:
                log_error("pywin32 available: attempting to show icons.")
            self.icon_cache = {}  # extension -> PhotoImage
            self._tree_icons = []  # Keep references to icons for Treeview
            self._auto_refresh_id = None
            # Enable high-DPI awareness for crisp rendering (Windows only)
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception as e:
                log_error(f"DPI awareness error: {e}")

            super().__init__()
            # --- ADDITION: Fetch logo2 from GitHub and use as app icon ---
            self.logo2_img_pil = fetch_logo2_from_github()
            self.logo2_img_tk = None
            if self.logo2_img_pil:
                try:
                    self.logo2_img_tk = ImageTk.PhotoImage(self.logo2_img_pil.resize((32, 32), Image.Resampling.LANCZOS))
                    self.iconphoto(False, self.logo2_img_tk)
                except Exception as e:
                    log_error(f"Failed to set app icon from GitHub logo2: {e}")
            # --- ADDITION: Fetch logo with text for settings ---
            self.logo_with_text_img_pil = fetch_logo_with_text_from_github()
            self.logo_with_text_img_tk = None
            if self.logo_with_text_img_pil:
                try:
                    self.logo_with_text_img_tk = ImageTk.PhotoImage(self.logo_with_text_img_pil.resize((280, 80), Image.Resampling.LANCZOS))
                except Exception as e:
                    log_error(f"Failed to set logo_with_text for settings: {e}")

            self.title("Scanner Gate File Manager")

            # Dynamically scale window to monitor size (80% of screen)
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            win_w = int(screen_w * 0.8)
            win_h = int(screen_h * 0.8)
            self.geometry(f"{win_w}x{win_h}")

            self.directory = ""
            self.files: List[FileInfo] = []
            self.config_path = os.path.join(os.path.dirname(sys.argv[0]), "scanner_settings.json")
            self.settings = self.load_settings()
            self.create_widgets()
            self.new_files = set()  # Track new files by name
            self.displayed_files = set()  # Track currently displayed files by name
            self.check_admin()
            default_folder = self.settings.get("default_folder")
            if default_folder and os.path.isdir(default_folder):
                self.directory = default_folder
                self.refresh_files()
            else:
                self.select_folder()
            self.auto_refresh()
            log_error("FileManagerUI __init__ completed.")
        except Exception as e:
            log_error(f"Exception in FileManagerUI __init__: {e}", exc=e)
            import traceback
            traceback.print_exc()
            try:
                messagebox.showerror("Startup Error", f"A fatal error occurred. See error_log.txt for details.\n{e}")
            except Exception:
                pass
            self.destroy()

    def on_left_click(self, event):
        if self.menu:
            self.menu.unpost()
            self.menu = None
            return

        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self.tree.selection_set(row_id)

        # Clear [NEW] tag and red style if present
        item_text = self.tree.item(row_id, "text")
        if item_text.endswith(" [NEW]"):
            real_name = item_text[:-6].strip()
            if real_name in self.new_files:
                self.new_files.remove(real_name)
            self.tree.item(row_id, text=real_name, tags=())

        # ----------- MODIFICATION STARTS HERE -------------
        # Larger font, new order: Process, Edit, Delete, no Cancel
        self.menu = tk.Menu(self, tearoff=0)
        menu_font = ("Segoe UI", 18, "bold")
        self.menu.add_command(label="Process", command=self.menu_process_file, font=menu_font)
        self.menu.add_command(label="Edit", command=self.menu_edit_file, font=menu_font)
        self.menu.add_command(label="Delete", command=self.menu_delete_file, font=menu_font)
        # ----------- MODIFICATION ENDS HERE ---------------

        try:
            self.menu.tk_popup(event.x_root, event.y_root)
            self.tree.focus_set()
            self.tree.selection_set(row_id)
        finally:
            self.menu.grab_release()
            
    def destroy(self):
        if hasattr(self, '_auto_refresh_id') and self._auto_refresh_id:
            try:
                self.after_cancel(self._auto_refresh_id)
            except Exception:
                pass
        super().destroy()
    
    def load_settings(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "default_folder": "",
            "default_storage": "",
            "default_dest_start": ""
        }

    def save_settings(self):
        try:
            with open(self.config_path, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def check_admin(self):
        import ctypes
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        if not is_admin:
            if messagebox.askyesno("Administrator Required", "This software should be run as administrator for full access. Relaunch as admin now?"):
                import sys, os, time
                params = ' '.join([f'"{x}"' for x in sys.argv])
                try:
                    result = ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", sys.executable, params, None, 1
                    )
                    if int(result) <= 32:
                        messagebox.showerror("Error", "Failed to relaunch as admin. Please run this program as administrator manually.")
                        return
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to relaunch as admin: {e}")
                    return
                time.sleep(1)
                self.destroy()
                sys.exit()

    def create_widgets(self):
        style = tb.Style("darkly")
        self.configure(bg=style.colors.bg)
        frame = tb.Frame(self, bootstyle="dark")
        frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        topbar = tb.Frame(frame, bootstyle="dark")
        topbar.pack(fill=tk.X, pady=(0, 10))
        dir_btn = tb.Button(topbar, text="Select Folder", bootstyle="secondary-outline", command=self.select_folder)
        dir_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.path_label = tb.Label(topbar, text=self.directory or "No folder selected", bootstyle="inverse", anchor=tk.W)
        self.path_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.settings_btn = tb.Button(topbar, text="\u2699", width=3, bootstyle="secondary", command=self.open_settings)
        self.settings_btn.pack(side=tk.RIGHT, padx=(10, 0))
        tree_frame = tb.Frame(frame, bootstyle="dark")
        tree_frame.pack(fill=tk.BOTH, expand=True)

        vsb = tb.Scrollbar(tree_frame, orient="vertical", bootstyle="round", command=lambda *args: self.tree.yview(*args))
        vsb.pack(side=tk.RIGHT, fill=tk.Y, padx=2, pady=6)
        self.tree = tb.Treeview(
            tree_frame,
            columns=("Last Modified", "Size (KB)"),
            show="tree headings",
            bootstyle="dark",
            yscrollcommand=vsb.set
        )

        font_family = "Segoe UI"
        font_size = 10
        row_height = 1000

        style.configure("Treeview", rowheight=row_height, font=(font_family, font_size))
        style.configure("Treeview.Heading", font=(font_family, font_size, "bold"))
        style.map("Treeview", foreground=[('selected', '#fff')], background=[('selected', '#222')])
        self.tree.tag_configure("newfile", foreground="#ff5555", font=(font_family, 12, "bold"))

        self.tree.heading("#0", text="Name", anchor=tk.W)
        self.tree.column("#0", width=340, anchor=tk.W, minwidth=150)
        self.tree.heading("Last Modified", text="Last Modified", anchor=tk.W)
        self.tree.column("Last Modified", width=200, anchor=tk.W, minwidth=120)
        self.tree.heading("Size (KB)", text="Size (KB)", anchor=tk.W)
        self.tree.column("Size (KB)", width=140, anchor=tk.W, minwidth=80)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10, padx=2)

        self.tree.bind("<Button-1>", self.on_left_click)
        self.tree.bind("<Double-1>", self.preview_file)
        self.menu = None

        # Enable mousewheel scrolling (Windows/Linux/Mac)
        def _on_mousewheel(event):
            if sys.platform == 'darwin':
                self.tree.yview_scroll(int(-1 * event.delta), "units")
            else:
                self.tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        self.tree.bind("<MouseWheel>", _on_mousewheel)        # Windows, Linux
        self.tree.bind("<Button-4>", _on_mousewheel)          # Linux
        self.tree.bind("<Button-5>", _on_mousewheel)          # Linux
        self.tree.bind("<Shift-MouseWheel>", lambda e: "break")  # Prevent horizontal scroll by accident

        default_font = (font_family, font_size - 2)
        style.configure("TLabel", font=default_font)
        style.configure("TButton", font=(font_family, font_size - 2, "bold"))
        style.configure("Treeview.Heading", font=(font_family, font_size - 2, "bold"))
        style.configure("Treeview", font=default_font)
        self.update_path_label = lambda: self.path_label.config(text=self.directory or "No folder selected")
        bottombar = tb.Frame(frame, bootstyle="dark")
        bottombar.pack(fill=tk.X, pady=(10, 0))
        self.refresh_btn = tb.Button(bottombar, text="\u21bb  Reload", bootstyle="primary", command=self.refresh_files)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)

    def refresh_files(self):
        if not self.directory:
            return
        prev_displayed = self.displayed_files.copy()
        self.files = scan_directory(self.directory)
        # --- SUBSORT: Newest to oldest, then by name (natural sort) ---
        def natural_key(s):
            import re
            return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]
        self.files.sort(key=lambda f: (-f.last_modified.timestamp(), natural_key(f.name)))
        current_names = set(f.name for f in self.files)
        if not getattr(self, "first_scan_done", False):
            # First scan: do not mark anything as new
            self.new_files = set()
            self.displayed_files = current_names
            self.first_scan_done = True
        else:
            new_files = current_names - prev_displayed
            self.new_files.update(new_files)
            self.displayed_files = current_names

        for i in self.tree.get_children():
            self.tree.delete(i)
        self._tree_icons.clear()  # Clear previous icon references
        for file in self.files:
            display_name = file.name
            tags = ()
            if file.name in self.new_files:
                display_name += " [NEW]"
                tags = ("newfile",)
            # --- FIX: Use original get_file_icon logic for file icons ---
            icon = self.get_file_icon(file.path, is_folder=False)
            self._tree_icons.append(icon)
            size_kb = file.size // 1024
            self.tree.insert(
                "", tk.END,
                text=display_name, image=icon,
                values=(file.last_modified.strftime("%Y-%m-%d %H:%M:%S"), f"{size_kb}"),
                tags=tags
            )
        self.tree.tag_configure("newfile", foreground="#ff5555", font=("Segoe UI", 10, "bold"))
        self.update_path_label()
        
    def get_file_icon(self, path, is_folder=False):
        """
        Returns a Tk PhotoImage for the file/folder icon, using pywin32 for Windows shell API.
        Caches by extension or 'folder'.
        """
        if is_folder:
            key = 'folder'
        else:
            ext = os.path.splitext(path)[1].lower()
            key = ext if ext else 'file'
        if key in self.icon_cache:
            return self.icon_cache[key]
        # Use pywin32 to extract icon
        import ctypes
        def extract_icon_for_path(icon_path, attr, flags):
            class SHFILEINFO(ctypes.Structure):
                _fields_ = [
                    ("hIcon", ctypes.c_void_p),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", ctypes.c_uint),
                    ("szDisplayName", ctypes.c_wchar * 260),
                    ("szTypeName", ctypes.c_wchar * 80)
                ]
            shfi = SHFILEINFO()
            try:
                res = ctypes.windll.shell32.SHGetFileInfoW(
                    icon_path,
                    attr,
                    ctypes.byref(shfi),
                    ctypes.sizeof(shfi),
                    flags
                )
            except Exception as e:
                log_error(f"Error calling SHGetFileInfoW for {icon_path}: {e}", exc=e)
                return None
            hicon = shfi.hIcon
            if hicon:
                try:
                    ico_x = win32api.GetSystemMetrics(49)  # SM_CXSMICON
                    ico_y = win32api.GetSystemMetrics(50)  # SM_CYSMICON
                    hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                    hbmp = win32ui.CreateBitmap()
                    hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
                    hdc_mem = hdc.CreateCompatibleDC()
                    hdc_mem.SelectObject(hbmp)
                    win32gui.DrawIconEx(hdc_mem.GetSafeHdc(), 0, 0, hicon, ico_x, ico_y, 0, 0, DI_NORMAL)
                    bmpinfo = hbmp.GetInfo()
                    bmpstr = hbmp.GetBitmapBits(True)
                    image = Image.frombuffer('RGBA', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRA', 0, 1)
                    photo = ImageTk.PhotoImage(image)
                    win32gui.DestroyIcon(hicon)
                    return photo
                except Exception as e:
                    log_error(f"Error extracting icon bitmap for {icon_path}: {e}", exc=e)
                    return None
            return None

        if win32api and win32gui and win32ui:
            try:
                # Try real file first (small icon)
                if os.path.exists(path):
                    log_error(f"Extracting icon for: {path} (is_folder={is_folder}, exists=True)")
                    photo = extract_icon_for_path(path, 0, SHGFI_ICON | SHGFI_SMALLICON)
                    if photo:
                        self.icon_cache[key] = photo
                        log_error(f"Icon extracted for: {path}")
                        return photo
                    else:
                        log_error(f"No hicon returned for: {path}, trying extension fallback")
                # Fallback: use extension (small icon)
                ext = os.path.splitext(path)[1].lower()
                if ext:
                    fake_name = f"C:\\dummy{ext}"
                    photo = extract_icon_for_path(fake_name, FILE_ATTRIBUTE_NORMAL, SHGFI_ICON | SHGFI_SMALLICON | SHGFI_USEFILEATTRIBUTES)
                    if photo:
                        self.icon_cache[key] = photo
                        log_error(f"Extension icon extracted for: {ext}")
                        return photo
                # Fallback: generic file icon
                log_error(f"No icon found for: {path}, using blank icon")
            except Exception as e:
                log_error(f"Error extracting icon for {path}: {e}", exc=e)
        else:
            log_error("pywin32 not available in get_file_icon")
        # fallback: blank image
        img = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
        photo = ImageTk.PhotoImage(img)
        self.icon_cache[key] = photo
        log_error(f"Fallback blank icon for: {path}")
        return photo

    def open_settings(self):
        win = tb.Toplevel(self)
        win.title("Settings")
        # Make settings window 60% of screen width and 50% of screen height
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        ww = int(sw * 0.6)
        wh = int(sh * 0.5)
        win.geometry(f"{ww}x{wh}")
        tb.Label(win, text="Default folder to view on startup:").pack(anchor=tk.W, padx=10, pady=2)
        folder_entry = tb.Entry(win, width=60)
        folder_entry.insert(0, self.settings.get("default_folder", ""))
        folder_entry.pack(padx=10)
        def browse_folder():
            path = filedialog.askdirectory(title="Select Default Folder")
            if path:
                folder_entry.delete(0, tk.END)
                folder_entry.insert(0, path)
        tb.Button(win, text="Browse", command=browse_folder, bootstyle="secondary").pack(anchor=tk.W, padx=10, pady=2)

        tb.Label(win, text="Default storage location (option 3):").pack(anchor=tk.W, padx=10, pady=2)
        storage_entry = tb.Entry(win, width=60)
        storage_entry.insert(0, self.settings.get("default_storage", ""))
        storage_entry.pack(padx=10)
        def browse_storage():
            path = filedialog.askdirectory(title="Select Default Storage")
            if path:
                storage_entry.delete(0, tk.END)
                storage_entry.insert(0, path)
        tb.Button(win, text="Browse", command=browse_storage, bootstyle="secondary").pack(anchor=tk.W, padx=10, pady=2)

        tb.Label(win, text="Default destination start point:").pack(anchor=tk.W, padx=10, pady=2)
        dest_entry = tb.Entry(win, width=60)
        dest_entry.insert(0, self.settings.get("default_dest_start", ""))
        dest_entry.pack(padx=10)
        def browse_dest():
            path = filedialog.askdirectory(title="Select Default Destination Start")
            if path:
                dest_entry.delete(0, tk.END)
                dest_entry.insert(0, path)
        tb.Button(win, text="Browse", command=browse_dest, bootstyle="secondary").pack(anchor=tk.W, padx=10, pady=2)

        def save_and_close():
            self.settings["default_folder"] = folder_entry.get().strip()
            self.settings["default_storage"] = storage_entry.get().strip()
            self.settings["default_dest_start"] = dest_entry.get().strip()
            self.save_settings()
            win.destroy()
        tb.Button(win, text="Save", command=save_and_close, bootstyle="success").pack(pady=10)

        # --- Show logo with text and tagline at the bottom of the settings page ---
        if self.logo_with_text_img_tk:
            logo_with_text_label = tb.Label(win, image=self.logo_with_text_img_tk)
            logo_with_text_label.image = self.logo_with_text_img_tk
            logo_with_text_label.pack(pady=10)

        tb.Label(win, text="Designed by Torsten Jostad Yemm", font=("Segoe UI", 12, "italic")).pack(pady=(0, 15))

        win.transient(self)
        win.grab_set()
        win.focus_set()

    def select_folder(self):
        initialdir = self.settings.get("default_dest_start") or None
        folder = filedialog.askdirectory(initialdir=initialdir)
        if folder:
            self.directory = folder
            self.refresh_files()
            self.update_path_label()

    def menu_cancel(self):
        if self.menu:
            self.menu.unpost()
            self.menu = None

    def menu_edit_file(self):
        file = self.get_selected_file()
        if not file:
            return
        open_file_with_default_app(file.path)

    def menu_process_file(self):
        import shutil
        file = self.get_selected_file()
        if not file:
            return
        rename_win = tb.Toplevel(self)
        rename_win.title("Rename Scan")
        # Make rename window 40% of screen width and 30% of screen height
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        ww = int(sw * 0.4)
        wh = int(sh * 0.3)
        rename_win.geometry(f"{ww}x{wh}")
        tb.Label(rename_win, text="Enter new file name (with extension):").pack(pady=5)
        entry = tb.Entry(rename_win, width=60)
        entry.insert(0, file.name)
        entry.pack(pady=5)
        btn_frame = tb.Frame(rename_win)
        btn_frame.pack(pady=10)
        def do_delete():
            new_name = entry.get().strip()
            # Ensure extension is retained
            orig_ext = os.path.splitext(file.name)[1]
            if not new_name:
                messagebox.showwarning("No Name", "Please enter a file name.")
                return
            if not new_name.lower().endswith(orig_ext.lower()):
                new_name += orig_ext
            if messagebox.askyesno("Copy Before Delete", "Do you want to copy the renamed file to another folder before deleting?"):
                default_dest = self.settings.get("default_dest_start", "")
                dest_dir = filedialog.askdirectory(title="Select Folder to Copy Before Delete", initialdir=default_dest if default_dest else None)
                if dest_dir:
                    new_path = os.path.join(dest_dir, new_name)
                    try:
                        shutil.copy2(file.path, new_path)
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to copy file: {e}")
            rename_win.destroy()
            if messagebox.askyesno("Delete File", f"Are you sure you want to delete {file.name}?"):
                try:
                    os.remove(file.path)
                    self.refresh_files()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to delete file: {e}")
        def do_retain():
            new_name = entry.get().strip()
            orig_ext = os.path.splitext(file.name)[1]
            if not new_name:
                messagebox.showwarning("No Name", "Please enter a file name.")
                return
            if not new_name.lower().endswith(orig_ext.lower()):
                new_name += orig_ext
            scan_dir = os.path.dirname(file.path)
            new_scan_path = os.path.join(scan_dir, new_name)
            try:
                os.rename(file.path, new_scan_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename file in scans: {e}")
                return
            default_dest = self.settings.get("default_dest_start", "")
            dest_dir = filedialog.askdirectory(title="Select Destination Folder", initialdir=default_dest if default_dest else None)
            if not dest_dir:
                return
            new_path = os.path.join(dest_dir, new_name)
            try:
                shutil.copy2(new_scan_path, new_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy file: {e}")
                return
            try:
                if sys.platform.startswith('win'):
                    os.startfile(dest_dir)
                elif sys.platform.startswith('darwin'):
                    subprocess.call(['open', dest_dir])
                elif os.name == 'posix':
                    subprocess.call(['xdg-open', dest_dir])
            except Exception as e:
                messagebox.showwarning("Open Folder", f"Could not open folder: {e}")
            rename_win.destroy()
            self.refresh_files()
        def do_storage():
            new_name = entry.get().strip()
            orig_ext = os.path.splitext(file.name)[1]
            if not new_name:
                messagebox.showwarning("No Name", "Please enter a file name.")
                return
            if not new_name.lower().endswith(orig_ext.lower()):
                new_name += orig_ext
            # Get default destination and storage from settings
            default_dest = self.settings.get("default_dest_start", "")
            default_storage = self.settings.get("default_storage", "")
            # Prompt for main destination, defaulting to settings
            dest_dir = filedialog.askdirectory(title="Select Main Destination Folder (copy)", initialdir=default_dest if default_dest else None)
            if not dest_dir:
                return
            dest_path = os.path.join(dest_dir, new_name)
            # Use storage from settings, no prompt
            if not default_storage:
                messagebox.showerror("Error", "No default storage location set in settings.")
                return
            storage_dir = default_storage
            storage_path = os.path.join(storage_dir, new_name)
            # Copy to main destination
            try:
                shutil.copy2(file.path, dest_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy to main destination: {e}")
                return
            # Copy to storage destination
            try:
                shutil.copy2(file.path, storage_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy to storage: {e}")
                return
            # Delete original file
            try:
                os.remove(file.path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file from scans: {e}")
                # Still proceed to open folders and refresh
            # Open both destination folders
            try:
                if sys.platform.startswith('win'):
                    os.startfile(dest_dir)
                    os.startfile(storage_dir)
                elif sys.platform.startswith('darwin'):
                    subprocess.call(['open', dest_dir])
                    subprocess.call(['open', storage_dir])
                elif os.name == 'posix':
                    subprocess.call(['xdg-open', dest_dir])
                    subprocess.call(['xdg-open', storage_dir])
            except Exception as e:
                messagebox.showwarning("Open Folder", f"Could not open folder: {e}")
            rename_win.destroy()
            self.refresh_files()
        tb.Button(btn_frame, text="Delete Scan", width=18, command=do_delete, bootstyle="danger").pack(side=tk.LEFT, padx=5)
        tb.Button(btn_frame, text="Retain Scan", width=18, command=do_retain, bootstyle="success").pack(side=tk.LEFT, padx=5)
        tb.Button(btn_frame, text="Retain Scan in storage", width=22, command=do_storage, bootstyle="info").pack(side=tk.LEFT, padx=5)
        rename_win.transient(self)
        rename_win.grab_set()
        rename_win.focus_set()
    def menu_delete_file(self):
        file = self.get_selected_file()
        if not file:
            return
        if messagebox.askyesno("Delete File", f"Are you sure you want to delete {file.name}?"):
            try:
                os.remove(file.path)
                self.refresh_files()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file: {e}")
    def auto_refresh(self):
        if not hasattr(self, 'tree') or not self.winfo_exists():
            return
        self.refresh_files()
        self._auto_refresh_id = self.after(5000, self.auto_refresh)
    def get_selected_file(self) -> FileInfo:
        selected = self.tree.selection()
        if not selected:
            return None
        idx = self.tree.index(selected[0])
        return self.files[idx]
    def preview_file(self, event=None):
        file = self.get_selected_file()
        if not file:
            return
        open_file_with_default_app(file.path)
    def rename_file(self):
        file = self.get_selected_file()
        if not file:
            messagebox.showwarning("No selection", "Please select a file to rename.")
            return
        new_name = tb.simpledialog.askstring("Rename File", "Enter new file name:", initialvalue=file.name)
        if new_name and new_name != file.name:
            new_path = os.path.join(self.directory, new_name)
            os.rename(file.path, new_path)

# --- MAIN BLOCK ---
if __name__ == "__main__":
    try:
        with open("error_log.txt", "a", encoding="utf-8") as f:
            f.write("[MAIN] Entered main block.\n")
    except Exception:
        pass
    try:
        app = FileManagerUI()
        app.mainloop()
    except Exception as e:
        import traceback
        with open("error_log.txt", "a", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        print("An error occurred. See error_log.txt for details.")
        input("Press Enter to exit...")