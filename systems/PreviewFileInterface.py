import os
import sys
import subprocess
from datetime import datetime
from typing import List, Dict
import tkinter as tk
import json
import threading
from tkinter import ttk, filedialog, messagebox

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
        super().__init__()
        self.title("Scan Destination Manager")
        self.geometry("800x500")
        self.directory = ""
        self.files: List[FileInfo] = []
        self.config_path = os.path.join(os.path.dirname(sys.argv[0]), "scanner_settings.json")
        self.settings = self.load_settings()
        self.create_widgets()
        self.new_files = set()  # Track new files by name
        self.displayed_files = set()  # Track currently displayed files by name
        # Check for admin rights
        self.check_admin()
        # Use default folder if set, else prompt
        if self.settings.get("default_folder"):
            self.directory = self.settings["default_folder"]
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
        # Default settings
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
                # Relaunch as admin
                import sys, os
                params = ' '.join([f'"{x}"' for x in sys.argv])
                try:
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to relaunch as admin: {e}")
                self.destroy()
                sys.exit()

    def create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        dir_btn = ttk.Button(frame, text="Select Folder", command=self.select_folder)
        dir_btn.pack(anchor=tk.W)

        style = ttk.Style()
        style.configure("Treeview.NewFile", foreground="red")
        self.tree = ttk.Treeview(frame, columns=("Name", "Last Modified", "Size (KB)"), show="headings")
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=200)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        self.tree.bind("<Double-1>", self.preview_file)
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Button-1>", self.on_left_click)
        self.menu = None

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=5)
        self.refresh_btn = ttk.Button(btn_frame, text="Refresh", command=self.refresh_files)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        # Settings cog icon
        self.settings_btn = ttk.Button(btn_frame, text="⚙", width=3, command=self.open_settings)
        self.settings_btn.pack(side=tk.RIGHT, padx=5)

    def open_settings(self):
        win = tk.Toplevel(self)
        win.title("Settings")
        win.geometry("500x250")
        tk.Label(win, text="Default folder to view on startup:").pack(anchor=tk.W, padx=10, pady=2)
        folder_entry = tk.Entry(win, width=60)
        folder_entry.insert(0, self.settings.get("default_folder", ""))
        folder_entry.pack(padx=10)
        def browse_folder():
            path = filedialog.askdirectory(title="Select Default Folder")
            if path:
                folder_entry.delete(0, tk.END)
                folder_entry.insert(0, path)
        tk.Button(win, text="Browse", command=browse_folder).pack(anchor=tk.W, padx=10, pady=2)

        tk.Label(win, text="Default storage location (option 3):").pack(anchor=tk.W, padx=10, pady=2)
        storage_entry = tk.Entry(win, width=60)
        storage_entry.insert(0, self.settings.get("default_storage", ""))
        storage_entry.pack(padx=10)
        def browse_storage():
            path = filedialog.askdirectory(title="Select Default Storage")
            if path:
                storage_entry.delete(0, tk.END)
                storage_entry.insert(0, path)
        tk.Button(win, text="Browse", command=browse_storage).pack(anchor=tk.W, padx=10, pady=2)

        tk.Label(win, text="Default destination start point:").pack(anchor=tk.W, padx=10, pady=2)
        dest_entry = tk.Entry(win, width=60)
        dest_entry.insert(0, self.settings.get("default_dest_start", ""))
        dest_entry.pack(padx=10)
        def browse_dest():
            path = filedialog.askdirectory(title="Select Default Destination Start")
            if path:
                dest_entry.delete(0, tk.END)
                dest_entry.insert(0, path)
        tk.Button(win, text="Browse", command=browse_dest).pack(anchor=tk.W, padx=10, pady=2)

        def save_and_close():
            self.settings["default_folder"] = folder_entry.get().strip()
            self.settings["default_storage"] = storage_entry.get().strip()
            self.settings["default_dest_start"] = dest_entry.get().strip()
            self.save_settings()
            win.destroy()
        tk.Button(win, text="Save", command=save_and_close).pack(pady=10)
        win.transient(self)
        win.grab_set()
        win.focus_set()

    def select_folder(self):
        initialdir = self.settings.get("default_dest_start") or None
        folder = filedialog.askdirectory(initialdir=initialdir)
        if folder:
            self.directory = folder
            self.refresh_files()

    def refresh_files(self):
        if not self.directory:
            return
        prev_displayed = self.displayed_files.copy()
        self.files = scan_directory(self.directory)
        # Sort files by last_modified, newest first
        self.files.sort(key=lambda f: f.last_modified, reverse=True)
        current_names = set(f.name for f in self.files)
        # Detect new files
        new_files = current_names - prev_displayed
        self.new_files.update(new_files)
        self.displayed_files = current_names
        # Update treeview
        for i in self.tree.get_children():
            self.tree.delete(i)
        for file in self.files:
            display_name = file.name
            tags = ()
            if file.name in self.new_files:
                display_name += " [NEW]"
                tags = ("newfile",)
            self.tree.insert("", tk.END, values=(display_name, file.last_modified.strftime("%Y-%m-%d %H:%M:%S"), file.size // 1024), tags=tags)
        self.tree.tag_configure("newfile", foreground="red")
    def on_left_click(self, event):
        # Show context menu on left click of a file row
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
        # Step 1: Prompt for new name (longer entry)
        rename_win = tk.Toplevel(self)
        rename_win.title("Rename Scan")
        rename_win.geometry("500x120")
        tk.Label(rename_win, text="Enter new file name (with extension):").pack(pady=5)
        entry = tk.Entry(rename_win, width=60)
        entry.insert(0, file.name)
        entry.pack(pady=5)
        btn_frame = tk.Frame(rename_win)
        btn_frame.pack(pady=10)

        def do_delete():
            new_name = entry.get().strip()
            if not new_name:
                messagebox.showwarning("No Name", "Please enter a file name.")
                return
            # Prompt user if they want to copy the renamed file before deletion
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
            # Rename the file in scans folder first
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
            # 1. Prompt for main destination folder (copy)
            dest_dir = filedialog.askdirectory(title="Select Main Destination Folder (copy)")
            if not dest_dir:
                return
            dest_path = os.path.join(dest_dir, new_name)
            try:
                shutil.copy2(file.path, dest_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy to main destination: {e}")
                return
            # 2. Prompt for storage folder (copy)
            storage_dir = filedialog.askdirectory(title="Select Storage Folder (copy)")
            if not storage_dir:
                return
            storage_path = os.path.join(storage_dir, new_name)
            try:
                shutil.copy2(file.path, storage_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy to storage: {e}")
                return
            # 3. Delete from scans
            try:
                os.remove(file.path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file from scans: {e}")
            # 4. Optionally open both folders for user
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

        tk.Button(btn_frame, text="Delete Scan", width=18, command=do_delete).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Retain Scan", width=18, command=do_retain).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Retain Scan in storage", width=22, command=do_storage).pack(side=tk.LEFT, padx=5)
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
        # Remove 'NEW' flag and color immediately when mouse hovers over a new file
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
                            # Update the display name and remove tag immediately
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
        new_name = tk.simpledialog.askstring("Rename File", "Enter new file name:", initialvalue=file.name)
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
    app = FileManagerUI()
    app.mainloop()