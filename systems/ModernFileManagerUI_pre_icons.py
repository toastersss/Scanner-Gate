# Modern UI test version of FileManagerUI (pre-symbols version)
# This file is a copy of ModernFileManagerUI.py before file icon symbol logic was added.

import os
import sys
import subprocess
from datetime import datetime
from typing import List, Dict
import tkinter as tk
import json
import threading
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *

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

class FileManagerUI(tk.Tk):
    def __init__(self):
        # Enable high-DPI awareness for crisp rendering (Windows only)
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        super().__init__()
        self.title("Scan Destination Manager - Modern UI Test")

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
        self.settings_btn = tb.Button(topbar, text="⚙", width=3, bootstyle="secondary", command=self.open_settings)
        self.settings_btn.pack(side=tk.RIGHT, padx=(10, 0))
        tree_frame = tb.Frame(frame, bootstyle="dark")
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = tb.Treeview(tree_frame, columns=("Name", "Last Modified", "Size (KB)"), show="headings", bootstyle="dark")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=220 if col == "Name" else 140, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        self.tree.bind("<Double-1>", self.preview_file)
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Button-1>", self.on_left_click)
        self.menu = None
        style.configure("Treeview", rowheight=44, font=("Segoe UI", 15), padding=8)
        style.configure("Treeview.Heading", font=("Segoe UI", 15, "bold"))
        style.map("Treeview", foreground=[('selected', '#fff')], background=[('selected', '#222')])
        self.tree.tag_configure("newfile", foreground="#ff5555", font=("Segoe UI", 10, "bold"))
        default_font = ("Segoe UI", 11)
        style.configure("TLabel", font=default_font)
        style.configure("TButton", font=("Segoe UI", 11, "bold"))
        style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"))
        style.configure("Treeview", font=default_font)
        self.update_path_label = lambda: self.path_label.config(text=self.directory or "No folder selected")
        bottombar = tb.Frame(frame, bootstyle="dark")
        bottombar.pack(fill=tk.X, pady=(10, 0))
        self.refresh_btn = tb.Button(bottombar, text="\u21bb  Reload", bootstyle="primary", command=self.refresh_files)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)

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

    def refresh_files(self):
        if not self.directory:
            return
        prev_displayed = self.displayed_files.copy()
        self.files = scan_directory(self.directory)
        self.files.sort(key=lambda f: f.last_modified, reverse=True)
        current_names = set(f.name for f in self.files)
        new_files = current_names - prev_displayed
        self.new_files.update(new_files)
        self.displayed_files = current_names
        for i in self.tree.get_children():
            self.tree.delete(i)
        for file in self.files:
            display_name = file.name
            tags = ()
            if file.name in self.new_files:
                display_name += " [NEW]"
                tags = ("newfile",)
            self.tree.insert("", tk.END, values=(display_name, file.last_modified.strftime("%Y-%m-%d %H:%M:%S"), file.size // 1024), tags=tags)
        self.tree.tag_configure("newfile", foreground="#ff5555", font=("Segoe UI", 10, "bold"))
        self.update_path_label()

    def on_left_click(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            if self.menu:
                self.menu.unpost()
            return
        self.tree.selection_set(row_id)
        if self.menu:
            self.menu.unpost()
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Edit", command=self.menu_edit_file)
        self.menu.add_command(label="Process", command=self.menu_process_file)
        self.menu.add_command(label="Delete", command=self.menu_delete_file)
        self.menu.add_separator()
        self.menu.add_command(label="Cancel", command=self.menu_cancel)
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

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
            if not new_name:
                messagebox.showwarning("No Name", "Please enter a file name.")
                return
            if messagebox.askyesno("Copy Before Delete", "Do you want to copy the renamed file to another folder before deleting?"):
                dest_dir = filedialog.askdirectory(title="Select Folder to Copy Before Delete")
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
            if not new_name:
                messagebox.showwarning("No Name", "Please enter a file name.")
                return
            scan_dir = os.path.dirname(file.path)
            new_scan_path = os.path.join(scan_dir, new_name)
            try:
                os.rename(file.path, new_scan_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename file in scans: {e}")
                return
            dest_dir = filedialog.askdirectory(title="Select Destination Folder")
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
            if not new_name:
                messagebox.showwarning("No Name", "Please enter a file name.")
                return
            dest_dir = filedialog.askdirectory(title="Select Main Destination Folder (copy)")
            if not dest_dir:
                return
            dest_path = os.path.join(dest_dir, new_name)
            try:
                shutil.copy2(file.path, dest_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy to main destination: {e}")
                return
            storage_dir = filedialog.askdirectory(title="Select Storage Folder (copy)")
            if not storage_dir:
                return
            storage_path = os.path.join(storage_dir, new_name)
            try:
                shutil.copy2(file.path, storage_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy to storage: {e}")
                return
            try:
                os.remove(file.path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file from scans: {e}")
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
        self.refresh_files()
        self.after(5000, self.auto_refresh)
    def on_tree_motion(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            row_id = self.tree.identify_row(event.y)
            if row_id:
                values = self.tree.item(row_id, "values")
                if values:
                    name = values[0]
                    if name.endswith(" [NEW]"):
                        real_name = name[:-6]
                        if real_name in self.new_files:
                            self.new_files.remove(real_name)
                            self.tree.item(row_id, values=(real_name, values[1], values[2]), tags=())
    def get_selected_file(self) -> FileInfo:
        selected = self.tree.selection()
        if not selected:
            return None
        idx = self.tree.index(selected[0])
        return self.files[idx]
    def preview_file(self, event=None):
        file = self.get_selected_file()
        if file:
            open_file_with_default_app(file.path)
    def rename_file(self):
        file = self.get_selected_file()
        if not file:
            messagebox.showwarning("No selection", "Please select a file to rename.")
            return
        new_name = tb.simpledialog.askstring("Rename File", "Enter new file name:", initialvalue=file.name)
        if new_name and new_name != file.name:
            new_path = os.path.join(self.directory, new_name)
            try:
                os.rename(file.path, new_path)
                self.refresh_files()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to rename file: {e}")
    def move_file(self):
        file = self.get_selected_file()
        if not file:
            messagebox.showwarning("No selection", "Please select a file to move.")
            return
        dest_dir = filedialog.askdirectory(title="Select Destination Folder")
        if dest_dir:
            new_path = os.path.join(dest_dir, file.name)
            try:
                os.rename(file.path, new_path)
                self.refresh_files()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to move file: {e}")
if __name__ == "__main__":
    try:
        app = FileManagerUI()
        app.mainloop()
    except Exception as e:
        import traceback
        with open("error_log.txt", "w") as f:
            traceback.print_exc(file=f)
        print("An error occurred. See error_log.txt for details.")
        input("Press Enter to exit...")
    else:
        input("Press Enter to exit...")
