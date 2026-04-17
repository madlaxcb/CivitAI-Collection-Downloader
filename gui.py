#!/usr/bin/env python3
"""
CivitAI Collection Downloader - GUI Application
A graphical user interface for downloading images and videos from CivitAI.
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
import requests
import io
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from pathlib import Path

# Import application modules
from config import config, init_config, setup_logging, Configuration, get_image_cdn_base, get_image_cdn_domain, VALID_DOMAINS
from api import CivitaiAPI, extract_metadata, create_collection_metadata, get_cdn_key
from downloader import create_download_directory, download_media, save_metadata, sanitize_filename
from cache import cache_manager
from tkVideoPlayer import TkinterVideo
from language_manager import i18n
from user_agreement import get_agreement

HAS_VIDEO_PLAYER = True



class TextHandler(logging.Handler):
    """Logging handler that writes to a Tkinter Text widget."""
    
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        
    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        self.text_widget.after(0, append)


class AgreementDialog:
    """Dialog for user agreement on first use."""
    
    def __init__(self, parent):
        self.accepted = False
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(i18n.get("about.user_agreement"))
        self.dialog.geometry("700x600")
        self.dialog.resizable(True, True)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 700) // 2
        y = (self.dialog.winfo_screenheight() - 600) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text=i18n.get("about.user_agreement"), font=('', 14, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Agreement text
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, font=('', 10))
        self.text.pack(fill=tk.BOTH, expand=True)
        # Load agreement based on current language
        self.text.insert(tk.END, get_agreement(i18n.current_language))
        self.text.configure(state='disabled')
        
        # Checkbox
        self.agree_var = tk.BooleanVar()
        agree_check = ttk.Checkbutton(main_frame, text=i18n.get("about.agreement_notice"), 
                                       variable=self.agree_var, command=self._toggle_button)
        agree_check.pack(pady=15)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        
        self.accept_btn = ttk.Button(btn_frame, text=i18n.get("dialogs.save"), command=self._accept, state=tk.DISABLED)
        self.accept_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text=i18n.get("dialogs.cancel"), command=self._reject).pack(side=tk.LEFT, padx=5)
        
        # Prevent closing without action
        self.dialog.protocol("WM_DELETE_WINDOW", self._reject)
        
    def _toggle_button(self):
        if self.agree_var.get():
            self.accept_btn.configure(state=tk.NORMAL)
        else:
            self.accept_btn.configure(state=tk.DISABLED)
            
    def _accept(self):
        self.accepted = True
        self.dialog.destroy()
        
    def _reject(self):
        self.accepted = False
        self.dialog.destroy()
        
    def show(self):
        # Ensure dialog is visible and on top
        self.dialog.deiconify()
        self.dialog.lift()
        self.dialog.focus_force()
        self.dialog.wait_window()
        return self.accepted


class CreateCollectionDialog:
    """Dialog to create or edit a collection."""
    
    def __init__(self, parent, initial_data=None):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        title = i18n.get("dialogs.edit_collection") if initial_data else i18n.get("dialogs.create_collection")
        self.dialog.title(title)
        self.dialog.geometry("400x450")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        try:
            x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
            y = parent.winfo_y() + (parent.winfo_height() - 450) // 2
            self.dialog.geometry(f"+{x}+{y}")
        except:
            pass
        
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Name
        ttk.Label(main_frame, text=i18n.get("dialogs.name")).pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.name_var).pack(fill=tk.X, pady=(0, 10))
        
        # Description
        ttk.Label(main_frame, text=i18n.get("dialogs.description")).pack(anchor=tk.W)
        self.desc_text = tk.Text(main_frame, height=5)
        self.desc_text.pack(fill=tk.X, pady=(0, 10))

        # Collection Type
        ttk.Label(main_frame, text=i18n.get("dialogs.type")).pack(anchor=tk.W, pady=(10, 5))
        self.type_var = tk.StringVar(value="Image")
        
        if initial_data:
            # Read-only display in Edit mode
            c_type = initial_data.get('type', 'Image')
            if c_type == "Collection": 
                c_type = "Image"
            self.type_var.set(c_type)
            ttk.Label(main_frame, text=f"{c_type} {i18n.get('dialogs.immutable')}", foreground="gray").pack(anchor=tk.W, padx=5)
        else:
            # Editable Radiobuttons in Create mode
            type_frame = ttk.Frame(main_frame)
            type_frame.pack(fill=tk.X, pady=2)
            types = ["Model", "Article", "Post", "Image"]
            for t in types:
                ttk.Radiobutton(type_frame, text=t, variable=self.type_var, value=t).pack(side=tk.LEFT, padx=5)
        
        # Privacy
        ttk.Label(main_frame, text=i18n.get("dialogs.privacy")).pack(anchor=tk.W, pady=(10, 5))
        
        self.read_var = tk.StringVar(value="Public")
        read_frame = ttk.Frame(main_frame)
        read_frame.pack(fill=tk.X, pady=2)
        ttk.Label(read_frame, text=i18n.get("dialogs.who_can_view")).pack(side=tk.LEFT)
        privacy_options = ["Private", "Public", "Unlisted"]
        for opt in privacy_options:
            ttk.Radiobutton(read_frame, text=opt, variable=self.read_var, value=opt).pack(side=tk.LEFT, padx=5)
        
        # NSFW Checkbox
        self.nsfw_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text=i18n.get("dialogs.nsfw"), 
                       variable=self.nsfw_var).pack(anchor=tk.W, pady=10)

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))
        ttk.Button(btn_frame, text=i18n.get("dialogs.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT)
        btn_text = i18n.get("dialogs.save") if initial_data else i18n.get("dialogs.create")
        ttk.Button(btn_frame, text=btn_text, command=self._save).pack(side=tk.RIGHT, padx=10)
        
        # Initialize data if provided
        if initial_data:
            self.name_var.set(initial_data.get('name', ''))
            self.desc_text.insert('1.0', initial_data.get('description', '') or '')
            
            # Type is already handled above
            
            self.read_var.set(initial_data.get('read', 'Private'))
            self.nsfw_var.set(initial_data.get('nsfw', False))

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.enter_name"))
            return
            
        self.result = {
            "name": name,
            "description": self.desc_text.get("1.0", tk.END).strip(),
            "read": self.read_var.get(),
            "write": "Private", # Default to Private as UI is removed
            "type": self.type_var.get(),
            "nsfw": self.nsfw_var.get()
        }
        self.dialog.destroy()
        
    def show(self):
        self.dialog.wait_window()
        return self.result


class CivitAIDownloaderGUI:
    """Main GUI application for CivitAI Downloader."""
    
    # Default config path
    DEFAULT_CONFIG_DIR = Path(os.path.expanduser('~'), '.civitai_downloader')
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(i18n.get("app_title"))
        self.root.geometry("850x750")
        self.root.minsize(750, 650)
        
        # State variables
        self.download_thread = None
        self.stop_requested = False
        self.config_file_path = None
        self._preview_timer = None
        self.current_preview_request_id = 0
        
        # Initialize config
        self._init_config_silent()

        # Setup base logging (File/Console) from config
        try:
            from config import setup_logging as config_setup_logging
            config_setup_logging()
        except Exception as e:
            print(f"Failed to setup base logging: {e}")
        
        # Check first run - show agreement
        # AGREEMENT DIALOG REMOVED PER USER REQUEST
        # if not self._check_agreement_accepted():
        #     # Update the window to ensure it exists before creating dialog
        #     self.root.update()
        #     self.root.withdraw()  # Hide main window
        #     
        #     # Show agreement dialog
        #     agreement = AgreementDialog(self.root)
        #     accepted = agreement.show()
        #     
        #     if not accepted:
        #         self.root.destroy()
        #         sys.exit(0)
        #     else:
        #         self._mark_agreement_accepted()
        #         self.root.deiconify()  # Show main window
        #         self.root.update()
        
        self.root.deiconify()  # Ensure window is shown
        
        # Build UI
        self._build_ui()
        
        # Load saved settings into UI
        self._load_settings_to_ui()
        
        # Setup logging to text widget
        self._setup_logging()
        
    def _check_agreement_accepted(self):
        """Check if user has previously accepted the agreement."""
        agreement_file = self.DEFAULT_CONFIG_DIR / '.agreement_accepted'
        return agreement_file.exists()
        
    def _mark_agreement_accepted(self):
        """Mark that user has accepted the agreement."""
        self.DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        agreement_file = self.DEFAULT_CONFIG_DIR / '.agreement_accepted'
        agreement_file.write_text("accepted")
        
    def _init_config_silent(self):
        """Initialize config without prompting user."""
        config_dir = self.DEFAULT_CONFIG_DIR
        config_file = config_dir / 'config.json'
        self.config_file_path = config_file
        config_dir.mkdir(parents=True, exist_ok=True)
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    if loaded_config:
                        config.update(loaded_config)
            except Exception:
                pass
                
        download_dir = config.get('download_dir')
        if not download_dir or not isinstance(download_dir, str):
            download_dir = os.path.join(os.path.expanduser('~'), 'Pictures', 'CivitAI')
            config['download_dir'] = download_dir
            
        log_dir = config.get('log_dir')
        if not log_dir or not isinstance(log_dir, str):
            log_dir = os.path.join(os.path.expanduser('~'), '.civitai_downloader', 'logs')
            config['log_dir'] = log_dir
            
        try:
            os.makedirs(download_dir, exist_ok=True)
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            logging.error(f"Failed to create directories: {e}")
        
    def _build_ui(self):
        """Build the user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Build tabs
        self._build_settings_tab()
        self._build_manager_tab()
        self._build_download_tab()
        self._build_about_tab()
        
    def _build_manager_tab(self):
        """Build the Collection Manager tab."""
        manager_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(manager_frame, text=i18n.get("tabs.manager"))
        
        # Top controls: Refresh and Status
        top_frame = ttk.Frame(manager_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(top_frame, text=i18n.get("manager.refresh"), command=self._refresh_collections).pack(side=tk.LEFT)
        ttk.Button(top_frame, text=i18n.get("manager.create"), command=self._create_collection).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text=i18n.get("manager.edit"), command=self._edit_collection).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text=i18n.get("manager.delete"), command=self._delete_collection).pack(side=tk.LEFT, padx=5)
        self.manager_status_var = tk.StringVar(value=i18n.get("manager.ready"))
        ttk.Label(top_frame, textvariable=self.manager_status_var).pack(side=tk.LEFT, padx=10)
        
        # Main content: PanedWindow
        paned = ttk.PanedWindow(manager_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)
        
        # Left Panel: Source Collection
        left_frame = ttk.LabelFrame(paned, text=i18n.get("manager.source_collection"), padding="5")
        paned.add(left_frame, weight=1)
        
        ttk.Label(left_frame, text=i18n.get("manager.select_source")).pack(anchor=tk.W)
        self.source_collection_var = tk.StringVar()
        self.source_combo = ttk.Combobox(left_frame, textvariable=self.source_collection_var, state="readonly")
        self.source_combo.pack(fill=tk.X, pady=(0, 5))
        self.source_combo.bind("<<ComboboxSelected>>", self._on_source_selected)
        
        # Image List
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.image_listbox = tk.Listbox(list_frame, selectmode=tk.EXTENDED, yscrollcommand=scrollbar.set)
        self.image_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.image_listbox.bind('<<ListboxSelect>>', self._on_image_list_select)
        scrollbar.config(command=self.image_listbox.yview)
        
        # Selection buttons
        sel_btn_frame = ttk.Frame(left_frame)
        sel_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(sel_btn_frame, text=i18n.get("manager.select_all"), command=self._select_all_images).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))
        ttk.Button(sel_btn_frame, text=i18n.get("manager.invert_selection"), command=self._invert_selection).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        
        # Right Panel: Target Collection & Actions
        right_frame = ttk.LabelFrame(paned, text=i18n.get("manager.target_collection_actions"), padding="5")
        paned.add(right_frame, weight=1)
        
        ttk.Label(right_frame, text=i18n.get("manager.select_target")).pack(anchor=tk.W)
        self.target_collection_var = tk.StringVar()
        self.target_combo = ttk.Combobox(right_frame, textvariable=self.target_collection_var, state="readonly")
        self.target_combo.pack(fill=tk.X, pady=(0, 20))
        
        # Action Buttons
        ttk.Button(right_frame, text=i18n.get("manager.move_selected"), command=self._move_selected_images).pack(fill=tk.X, pady=5)
        ttk.Button(right_frame, text=i18n.get("manager.copy_selected"), command=self._copy_selected_images).pack(fill=tk.X, pady=5)
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        ttk.Button(right_frame, text=i18n.get("manager.delete_from_source"), command=self._delete_selected_images).pack(fill=tk.X, pady=5)
        
        # Preview
        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)
        ttk.Label(right_frame, text=i18n.get("manager.preview")).pack(anchor=tk.W)
        
        self.preview_frame = ttk.Frame(right_frame)
        self.preview_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.preview_label = ttk.Label(self.preview_frame, text=i18n.get("manager.no_preview"))
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        
        self.video_player = None
        if HAS_VIDEO_PLAYER:
            try:
                self.video_player = TkinterVideo(master=self.preview_frame, scaled=True)
            except Exception as e:
                logging.error(f"Failed to initialize video player: {e}")
        
        # Data storage
        self.collections_data = [] # List of collection objects
        self.current_source_images = [] # List of image objects in current source
        
        # Context Menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        # self.context_menu.add_command(label=i18n.get("manager.context_menu.copy_link"), command=self._copy_link) # Removed per request
        self.context_menu.add_command(label=i18n.get("manager.context_menu.download_and_open"), command=self._download_and_open)
        self.context_menu.add_separator()
        self.context_menu.add_command(label=i18n.get("manager.context_menu.move_to_target"), command=self._move_selected_images)
        self.context_menu.add_command(label=i18n.get("manager.context_menu.copy_to_target"), command=self._copy_selected_images)
        self.context_menu.add_separator()
        self.context_menu.add_command(label=i18n.get("manager.context_menu.delete_from_collection"), command=self._delete_selected_images)
        
        self.image_listbox.bind("<Button-3>", self._show_context_menu)
        
        # Load from cache
        self.root.after(500, self._load_collections_from_cache)
        
    def _show_context_menu(self, event):
        """Show context menu on right click."""
        # Select item under mouse if not selected
        index = self.image_listbox.nearest(event.y)
        if index >= 0:
            if not self.image_listbox.selection_includes(index):
                self.image_listbox.selection_clear(0, tk.END)
                self.image_listbox.selection_set(index)
                self._on_image_list_select(None)
                
        self.context_menu.post(event.x_root, event.y_root)
        
    def _copy_link(self):
        """Copy image/video URL to clipboard."""
        images = self._get_selected_images()
        if images:
            img = images[0]
            url = img.get('url')
            if url:
                if not url.startswith('http'):
                    cdn_key = get_cdn_key()
                    # Check if video
                    is_video = img.get('type') == 'video' or \
                               img.get('metadata', {}).get('type') == 'video' or \
                               url.lower().endswith(('.mp4', '.mov', '.webm'))
                    
                    if is_video:
                         url = f"{get_image_cdn_base()}/{cdn_key}/{url}"
                    else:
                         url = f"{get_image_cdn_base()}/{cdn_key}/{url}/width=450"
                         
                self.root.clipboard_clear()
                self.root.clipboard_append(url)
                
    def _download_and_open(self):
        """Download selected item to cache and open it."""
        images = self._get_selected_images()
        if not images:
            return
            
        img = images[0]
        url = img.get('url')
        if not url:
            return

        # Save settings to ensure proxies are up to date
        self._save_settings_to_config()
            
        # Determine if it's likely a video
        is_video = img.get('type') == 'video' or img.get('metadata', {}).get('type') == 'video' or url.lower().endswith(('.mp4', '.mov', '.webm'))
        width = img.get('width')
        
        if not url.startswith('http'):
            cdn_key = get_cdn_key()
            if is_video and width:
                url = f"{get_image_cdn_base()}/{cdn_key}/{url}/width={width}"
            else:
                url = f"{get_image_cdn_base()}/{cdn_key}/{url}"

        def task():
            try:
                self.manager_status_var.set(i18n.get("status.downloading"))
                
                download_url = url
                
                # Ensure video URL has width or original=true
                if is_video and get_image_cdn_domain() in download_url:
                    if "width=" in download_url:
                        pass
                    elif "original=true" not in download_url:
                        if '?' in download_url:
                            download_url += "&original=true"
                        else:
                            download_url += "/original=true"
                elif not is_video:
                    if get_image_cdn_domain() in download_url and "width=" not in download_url and "original=" not in download_url:
                        if '?' in download_url:
                            download_url += "&original=true"
                        else:
                            download_url += "/original=true"
                
                if is_video:
                    path_str = cache_manager.get_cached_video_path(download_url)
                    path = Path(path_str) if path_str else None
                else:
                    # Ensure full quality for "Download and Open"
                    # Add timeout and proper error handling
                    response = requests.get(download_url, proxies=config.get_proxies(), timeout=30)
                    response.raise_for_status()
                    path_str = str(cache_manager.save_image(download_url, response.content))
                    path = Path(path_str) if path_str else None
                
                if path and path.exists():
                    os.startfile(path)
                    self.root.after(0, lambda: self.manager_status_var.set(i18n.get("messages.file_opened")))
                else:
                    self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.download_failed")))
            except Exception as e:
                 logging.error(f"Download and open failed: {e}")
                 self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.operation_failed", error=e)))
                 
        threading.Thread(target=task, daemon=True).start()

    def _refresh_collections(self):
        """Fetch user collections."""
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.configure_api_key"))
            return
            
        self.manager_status_var.set(i18n.get("status.fetching_list"))
        self.root.update_idletasks()
        
        def fetch():
            try:
                api = CivitaiAPI(api_key)
                collections = api.get_my_collections()
                
                # Save to cache
                if collections:
                    cache_manager.save_data('collections', collections)
                
                # Update UI in main thread
                self.root.after(0, lambda: self._update_collections_ui(collections))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.fetch_failed", error=e)))
                self.root.after(0, lambda: self.manager_status_var.set(i18n.get("status.fetch_failed")))
                
        threading.Thread(target=fetch, daemon=True).start()

    def _load_collections_from_cache(self):
        """Load collections from cache on startup."""
        collections = cache_manager.load_data('collections')
        if collections:
            self._update_collections_ui(collections)
            self.manager_status_var.set(i18n.get("status.loaded_from_cache", count=len(collections)))
        else:
            self.manager_status_var.set(i18n.get("status.ready_no_cache"))
        
    def _create_collection(self):
        """Show dialog to create a new collection."""
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.configure_api_key"))
            return
            
        dialog = CreateCollectionDialog(self.root)
        result = dialog.show()
        
        if result:
            self.manager_status_var.set(i18n.get("status.creating"))
            
            def create():
                try:
                    api = CivitaiAPI(api_key)
                    new_collection = api.create_collection(
                        result['name'],
                        result['description'],
                        result['read'],
                        result['write'],
                        result['type'],
                        result['nsfw']
                    )
                    
                    if new_collection:
                        self.root.after(0, lambda: messagebox.showinfo(i18n.get("messages.success"), i18n.get("messages.collection_created", name=result['name'])))
                        self.root.after(0, self._refresh_collections)
                    else:
                        self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.collection_create_failed")))
                        self.root.after(0, lambda: self.manager_status_var.set(i18n.get("status.create_failed")))
                        
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.collection_create_failed") + f": {e}"))
                    self.root.after(0, lambda: self.manager_status_var.set(i18n.get("status.create_failed")))
                    
            threading.Thread(target=create, daemon=True).start()

    def _edit_collection(self):
        """Edit selected collection."""
        collection_id = self._get_source_collection_id()
        if not collection_id:
            messagebox.showwarning(i18n.get("messages.warning"), i18n.get("messages.select_collection_to_edit"))
            return
            
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.configure_api_key"))
            return

        # Find collection data
        collection = next((c for c in self.collections_data if str(c.get('id')) == str(collection_id)), None)
        if not collection:
            # If not in cache, try to fetch it or just use basic info
            # For now, we rely on cache/list
            pass

        dialog = CreateCollectionDialog(self.root, initial_data=collection)
        result = dialog.show()
        
        if result:
            self.manager_status_var.set(i18n.get("status.updating"))
            
            def update():
                try:
                    api = CivitaiAPI(api_key)
                    updated_collection = api.create_collection(
                        result['name'],
                        result['description'],
                        result['read'],
                        result['write'],
                        result['type'],
                        result['nsfw'],
                        collection_id=collection_id
                    )
                    
                    if updated_collection:
                        self.root.after(0, lambda: messagebox.showinfo(i18n.get("messages.success"), i18n.get("messages.collection_updated", name=result['name'])))
                        self.root.after(0, self._refresh_collections)
                    else:
                        self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.collection_update_failed")))
                        self.root.after(0, lambda: self.manager_status_var.set(i18n.get("status.update_failed")))
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.collection_update_failed") + f": {e}"))
                    self.root.after(0, lambda: self.manager_status_var.set(i18n.get("status.update_failed")))
                    
            threading.Thread(target=update, daemon=True).start()
        
    def _delete_collection(self):
        """Delete selected collection with double confirmation."""
        collection_id = self._get_source_collection_id()
        if not collection_id:
            messagebox.showwarning(i18n.get("messages.warning"), i18n.get("messages.select_collection_to_delete"))
            return
            
        collection_name = self.source_collection_var.get()
        
        # First confirmation
        if not messagebox.askyesno(i18n.get("dialogs.confirm_delete"), i18n.get("dialogs.confirm_delete_msg", name=collection_name)):
            return
            
        # Second confirmation
        if not messagebox.askyesno(i18n.get("dialogs.confirm_delete"), i18n.get("dialogs.confirm_delete_again_msg", name=collection_name)):
            return
            
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.configure_api_key"))
            return
            
        self.manager_status_var.set(i18n.get("status.deleting_collection"))
        
        def delete():
            try:
                api = CivitaiAPI(api_key)
                if api.delete_collection(collection_id):
                    self.root.after(0, lambda: messagebox.showinfo(i18n.get("messages.success"), i18n.get("messages.collection_deleted", name=collection_name)))
                    self.root.after(0, self._refresh_collections)
                else:
                    self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.collection_delete_failed")))
                    self.root.after(0, lambda: self.manager_status_var.set(i18n.get("status.delete_failed")))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.collection_delete_failed") + f": {e}"))
                self.root.after(0, lambda: self.manager_status_var.set(i18n.get("status.delete_failed")))
                
        threading.Thread(target=delete, daemon=True).start()

    def _update_collections_ui(self, collections):
        self.collections_data = collections
        names = [f"{c.get('name')} (ID: {c.get('id')})" for c in collections]
        self.source_combo['values'] = names
        self.target_combo['values'] = names
        self.manager_status_var.set(i18n.get("status.loaded_count", count=len(collections)))
        
    def _on_image_list_select(self, event):
        """Handle image selection for preview with debounce."""
        # Cancel pending preview update
        if self._preview_timer:
            self.root.after_cancel(self._preview_timer)
            self._preview_timer = None
            
        # Schedule new update
        self._preview_timer = self.root.after(500, self._process_preview)

    def _process_preview(self):
        """Actual preview processing logic."""
        selection = self.image_listbox.curselection()
        if not selection:
            self.preview_label.configure(image='', text=i18n.get("manager.no_preview"))
            if self.video_player:
                self.video_player.stop()
                self.video_player.pack_forget()
                self.preview_label.pack(fill=tk.BOTH, expand=True)
            return
            
        # Only preview the first selected item
        index = selection[0]
        if index >= len(self.current_source_images):
            return
            
        image_data = self.current_source_images[index]
        image_url = image_data.get('preview_url') or image_data.get('url')
        
        if not image_url:
            self.preview_label.configure(image='', text=i18n.get("manager.no_image_url"))
            return

        # Check if video
        is_video = image_data.get('type') == 'video' or \
                   image_data.get('metadata', {}).get('type') == 'video' or \
                   image_url.lower().endswith(('.mp4', '.mov', '.webm'))

        if not image_url.startswith('http'):
            cdn_key = get_cdn_key()
            image_url = f"{get_image_cdn_base()}/{cdn_key}/{image_url}"
            
        if is_video and get_image_cdn_domain() in image_url and "original=true" not in image_url:
             if '?' in image_url:
                 image_url += "&original=true"
             else:
                 image_url += "/original=true"
            
        # Update request ID to invalidate previous pending threads
        import time
        request_id = time.time()
        self.current_preview_request_id = request_id
        
        # Download and display in thread
        def load_preview(req_id):
            try:
                # Check if request is still valid
                if req_id != self.current_preview_request_id:
                    return

                # Use WebP preview for videos as requested, or standard preview for images
                display_url = image_url
                
                if is_video and get_image_cdn_domain() in display_url:
                    if "original=true" not in display_url:
                        if '?' in display_url:
                            display_url += "&original=true"
                        else:
                            display_url = display_url.rstrip('/') + "/original=true"
                elif "/width=" not in display_url and get_image_cdn_domain() in display_url and not is_video:
                     # For images, use width=450 if constructed from UUID
                     display_url = f"{display_url}/width=450"

                # Use new method to get file and type to handle both WebP images and MP4 previews
                preview_path, file_type = cache_manager.get_preview_file(display_url)
                
                # Check validity again after potentially slow download
                if req_id != self.current_preview_request_id:
                    return
                
                if not preview_path:
                     raise Exception("Failed to download preview")

                if file_type == 'video' and self.video_player:
                     # Play video (likely a small preview clip)
                     def play_video():
                         # Final check before UI update
                         if req_id != self.current_preview_request_id:
                             return
                             
                         self.preview_label.pack_forget()
                         self.video_player.pack(fill=tk.BOTH, expand=True)
                         try:
                             self.video_player.load(preview_path)
                             self.video_player.play()
                         except Exception as e:
                             logging.error(f"Video player load error: {e}")
                             
                     self.root.after(0, play_video)
                     
                elif file_type == 'image':
                     # Display image (WebP or other format)
                     try:
                         img = Image.open(preview_path)
                         img.thumbnail((300, 300))
                         photo = ImageTk.PhotoImage(img)
                     except Exception as e:
                         raise Exception(f"Failed to open image: {e}")
                     
                     def show_image():
                         if req_id != self.current_preview_request_id:
                             return
                             
                         if self.video_player:
                             self.video_player.stop()
                             self.video_player.pack_forget()
                         self.preview_label.pack(fill=tk.BOTH, expand=True)
                         self.preview_label.configure(image=photo, text="")
                         self.preview_label.image = photo
                     self.root.after(0, show_image)
                     
                else:
                     raise Exception(f"Unknown preview format: {file_type}")
                    
            except Exception as e:
                if req_id != self.current_preview_request_id:
                    return
                    
                logging.error(f"Preview failed for {image_url}: {e}")
                def show_error():
                    if self.video_player:
                        self.video_player.pack_forget()
                    self.preview_label.pack(fill=tk.BOTH, expand=True)
                    self.preview_label.configure(image='', text=i18n.get("manager.preview_failed") + f"\n{str(e)[:50]}")
                self.root.after(0, show_error)
                
        threading.Thread(target=load_preview, args=(request_id,), daemon=True).start()

    def _on_source_selected(self, event):
        selection_idx = self.source_combo.current()
        if selection_idx < 0:
            return
            
        collection = self.collections_data[selection_idx]
        collection_id = collection.get('id')
        
        self.manager_status_var.set(i18n.get("status.loading_content", name=collection.get('name')))
        self.image_listbox.delete(0, tk.END)
        self.current_source_images = []
        
        api_key = self.api_key_var.get().strip()
        
        def fetch_images():
            try:
                api = CivitaiAPI(api_key)
                # Use get_all_images_in_collection (might take time for large collections)
                # Maybe just get first batch for UI responsiveness? 
                # For management, we probably want all, but let's stick to existing method
                images = api.get_all_images_in_collection(collection_id)
                self.root.after(0, lambda: self._update_images_list(images))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.load_failed", error=e)))
                self.root.after(0, lambda: self.manager_status_var.set(i18n.get("status.load_image_failed")))
        
        threading.Thread(target=fetch_images, daemon=True).start()
        
    def _update_images_list(self, images):
        self.current_source_images = images
        self.image_listbox.delete(0, tk.END)
        for img in images:
            self.image_listbox.insert(tk.END, f"{img.get('id')} - {img.get('name') or 'No Name'}")
        self.manager_status_var.set(i18n.get("status.loaded_files", count=len(images)))
        
    def _select_all_images(self):
        self.image_listbox.select_set(0, tk.END)
        
    def _invert_selection(self):
        for i in range(self.image_listbox.size()):
            if self.image_listbox.selection_includes(i):
                self.image_listbox.selection_clear(i)
            else:
                self.image_listbox.select_set(i)
                
    def _get_selected_images(self):
        selected_indices = self.image_listbox.curselection()
        return [self.current_source_images[i] for i in selected_indices]
        
    def _get_target_collection_id(self):
        idx = self.target_combo.current()
        if idx < 0:
            return None
        return self.collections_data[idx].get('id')
        
    def _get_source_collection_id(self):
        idx = self.source_combo.current()
        if idx < 0:
            return None
        return self.collections_data[idx].get('id')

    def _move_selected_images(self):
        images = self._get_selected_images()
        if not images:
            messagebox.showwarning(i18n.get("messages.tip"), i18n.get("messages.select_move_images"))
            return
            
        target_id = self._get_target_collection_id()
        source_id = self._get_source_collection_id()
        
        if not target_id:
            messagebox.showwarning(i18n.get("messages.tip"), i18n.get("messages.select_target_collection"))
            return
            
        if source_id == target_id:
            messagebox.showwarning(i18n.get("messages.tip"), i18n.get("messages.source_target_same"))
            return
            
        if not messagebox.askyesno(i18n.get("messages.confirm"), i18n.get("dialogs.confirm_move_msg", count=len(images))):
            return
            
        self._perform_file_operation(images, target_id, source_id, "move")

    def _copy_selected_images(self):
        images = self._get_selected_images()
        if not images:
            messagebox.showwarning(i18n.get("messages.tip"), i18n.get("messages.select_copy_images"))
            return
            
        target_id = self._get_target_collection_id()
        
        if not target_id:
            messagebox.showwarning(i18n.get("messages.tip"), i18n.get("messages.select_target_collection"))
            return
            
        if not messagebox.askyesno(i18n.get("messages.confirm"), i18n.get("dialogs.confirm_copy_msg", count=len(images))):
            return
            
        self._perform_file_operation(images, target_id, None, "copy")
        
    def _delete_selected_images(self):
        images = self._get_selected_images()
        if not images:
            messagebox.showwarning(i18n.get("messages.tip"), i18n.get("messages.select_delete_images"))
            return
            
        source_id = self._get_source_collection_id()
        
        if not messagebox.askyesno(i18n.get("messages.confirm"), i18n.get("dialogs.confirm_delete_files_msg", count=len(images))):
            return
            
        self._perform_file_operation(images, None, source_id, "delete")
        
    def _perform_file_operation(self, images, target_id, source_id, operation):
        api_key = self.api_key_var.get().strip()
        api = CivitaiAPI(api_key)
        
        total = len(images)
        self.manager_status_var.set(i18n.get("status.processing", current=0, total=total))
        
        def task():
            success_count = 0
            fail_count = 0
            
            for i, img in enumerate(images):
                img_id = img.get('id')
                success = True
                
                # Copy/Move (Add to target)
                if operation in ["move", "copy"] and target_id:
                    if not api.add_image_to_collection(img_id, target_id):
                        success = False
                        
                # Delete/Move (Remove from source)
                if operation in ["move", "delete"] and source_id and success:
                    if not api.remove_image_from_collection(img_id, source_id):
                        success = False
                        
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    
                self.root.after(0, lambda idx=i+1: self.manager_status_var.set(i18n.get("status.processing", current=idx, total=total)))
                
            msg = i18n.get("messages.operation_complete", success=success_count, fail=fail_count)
            self.root.after(0, lambda: messagebox.showinfo(i18n.get("messages.done"), msg))
            
            # Refresh source list if items were removed
            if operation in ["move", "delete"] and success_count > 0:
                self.root.after(0, lambda: self._on_source_selected(None)) # Reload list
                
        threading.Thread(target=task, daemon=True).start()

    def _build_settings_tab(self):
        """Build the Settings tab."""
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text=i18n.get("tabs.settings"))
        
        # Create a canvas with scrollbar for settings
        canvas = tk.Canvas(settings_frame)
        scrollbar = ttk.Scrollbar(settings_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        def _on_enter(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _on_leave(event):
            canvas.unbind_all("<MouseWheel>")
        
        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Language Selection
        language_frame = ttk.LabelFrame(scrollable_frame, text=i18n.get("settings.language"), padding="5")
        language_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        self.language_var = tk.StringVar(value=config.get('language', 'zh_CN'))
        self.language_combo = ttk.Combobox(language_frame, textvariable=self.language_var, 
                                           values=["zh_CN", "en"], state="readonly", width=15)
        self.language_combo.bind("<<ComboboxSelected>>", self._on_language_change)
        self.language_combo.pack(anchor=tk.W, padx=5, pady=5)

        # API Configuration
        api_frame = ttk.LabelFrame(scrollable_frame, text=i18n.get("settings.api_config"), padding="5")
        api_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        ttk.Label(api_frame, text=i18n.get("settings.site_domain_label")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.site_domain_var = tk.StringVar(value='civitai.com')
        self.site_domain_combo = ttk.Combobox(api_frame, textvariable=self.site_domain_var, 
                                               values=VALID_DOMAINS, state="readonly", width=25)
        self.site_domain_combo.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        
        ttk.Label(api_frame, text=i18n.get("settings.api_key_label")).grid(row=1, column=0, sticky=tk.W, padx=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.grid(row=1, column=1, padx=5, pady=2, sticky=tk.EW)

        ttk.Label(api_frame, text=i18n.get("settings.cdn_key_label")).grid(row=2, column=0, sticky=tk.W, padx=5)
        self.cdn_key_var = tk.StringVar()
        ttk.Entry(api_frame, textvariable=self.cdn_key_var, width=50).grid(row=2, column=1, padx=5, pady=2, sticky=tk.EW)
        
        ttk.Label(api_frame, text=i18n.get("settings.download_dir")).grid(row=3, column=0, sticky=tk.W, padx=5)
        self.download_dir_var = tk.StringVar()
        dir_frame = ttk.Frame(api_frame)
        dir_frame.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)
        ttk.Entry(dir_frame, textvariable=self.download_dir_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text=i18n.get("settings.browse"), command=self._browse_directory).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(dir_frame, text=i18n.get("settings.open_folder"), command=self._open_download_dir).pack(side=tk.LEFT, padx=(5, 0))
        
        api_frame.columnconfigure(1, weight=1)
        
        # Config File Location
        config_frame = ttk.LabelFrame(scrollable_frame, text=i18n.get("settings.config_file"), padding="5")
        config_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        ttk.Label(config_frame, text=i18n.get("settings.current_config")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.config_path_var = tk.StringVar(value=str(self.config_file_path))
        ttk.Entry(config_frame, textvariable=self.config_path_var, width=50, state='readonly').grid(row=0, column=1, padx=5, pady=2, sticky=tk.EW)
        
        cfg_btn_frame = ttk.Frame(config_frame)
        cfg_btn_frame.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(cfg_btn_frame, text=i18n.get("settings.export_config"), command=self._export_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(cfg_btn_frame, text=i18n.get("settings.import_config"), command=self._import_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(cfg_btn_frame, text=i18n.get("settings.open_config_dir"), command=self._open_config_dir).pack(side=tk.LEFT, padx=5)
        
        config_frame.columnconfigure(1, weight=1)
        
        # File Type Selection
        filetype_frame = ttk.LabelFrame(scrollable_frame, text=i18n.get("settings.download_types"), padding="5")
        filetype_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        self.download_images_var = tk.BooleanVar(value=True)
        self.download_videos_var = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(filetype_frame, text=i18n.get("settings.download_images"), 
                        variable=self.download_images_var).pack(anchor=tk.W, padx=5)
        ttk.Checkbutton(filetype_frame, text=i18n.get("settings.download_videos"), 
                        variable=self.download_videos_var).pack(anchor=tk.W, padx=5)
        
        # Proxy Configuration
        proxy_frame = ttk.LabelFrame(scrollable_frame, text=i18n.get("settings.proxy_settings"), padding="5")
        proxy_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        self.proxy_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(proxy_frame, text=i18n.get("settings.enable_proxy"), variable=self.proxy_enabled_var, 
                        command=self._toggle_proxy_fields).pack(anchor=tk.W, padx=5, pady=2)
        
        # Container for proxy details
        self.proxy_details_frame = ttk.Frame(proxy_frame)
        self.proxy_details_frame.pack(fill=tk.X, expand=True)
        
        ttk.Label(self.proxy_details_frame, text=i18n.get("settings.proxy_type")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.proxy_type_var = tk.StringVar(value="HTTP")
        self.proxy_type_combo = ttk.Combobox(self.proxy_details_frame, textvariable=self.proxy_type_var, 
                                              values=["HTTP", "SOCKS5"], state="readonly", width=15)
        self.proxy_type_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(self.proxy_details_frame, text=i18n.get("settings.host")).grid(row=1, column=0, sticky=tk.W, padx=5)
        self.proxy_host_var = tk.StringVar()
        self.proxy_host_entry = ttk.Entry(self.proxy_details_frame, textvariable=self.proxy_host_var, width=30)
        self.proxy_host_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(self.proxy_details_frame, text=i18n.get("settings.port")).grid(row=1, column=2, sticky=tk.W, padx=5)
        self.proxy_port_var = tk.StringVar()
        self.proxy_port_entry = ttk.Entry(self.proxy_details_frame, textvariable=self.proxy_port_var, width=10)
        self.proxy_port_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)
        
        self.proxy_auth_var = tk.BooleanVar()
        ttk.Checkbutton(self.proxy_details_frame, text=i18n.get("settings.auth_required"), variable=self.proxy_auth_var,
                        command=self._toggle_proxy_auth).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(5, 0))
        
        ttk.Label(self.proxy_details_frame, text=i18n.get("settings.username")).grid(row=3, column=0, sticky=tk.W, padx=5)
        self.proxy_username_var = tk.StringVar()
        self.proxy_username_entry = ttk.Entry(self.proxy_details_frame, textvariable=self.proxy_username_var, width=20)
        self.proxy_username_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(self.proxy_details_frame, text=i18n.get("settings.password")).grid(row=3, column=2, sticky=tk.W, padx=5)
        self.proxy_password_var = tk.StringVar()
        self.proxy_password_entry = ttk.Entry(self.proxy_details_frame, textvariable=self.proxy_password_var, width=20, show="*")
        self.proxy_password_entry.grid(row=3, column=3, sticky=tk.W, padx=5, pady=2)
        
        # Pause/Rate Limit Configuration
        pause_frame = ttk.LabelFrame(scrollable_frame, text=i18n.get("settings.pause_settings"), padding="5")
        pause_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        self.pause_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(pause_frame, text=i18n.get("settings.enable_pause"), variable=self.pause_enabled_var,
                        command=self._toggle_pause_fields).grid(row=0, column=0, columnspan=4, sticky=tk.W, padx=5)
        
        ttk.Label(pause_frame, text=i18n.get("settings.pause_every")).grid(row=1, column=0, sticky=tk.W, padx=5)
        self.pause_after_files_var = tk.StringVar(value="10")
        self.pause_after_files_entry = ttk.Entry(pause_frame, textvariable=self.pause_after_files_var, width=8)
        self.pause_after_files_entry.grid(row=1, column=1, sticky=tk.W, padx=2, pady=2)
        ttk.Label(pause_frame, text=i18n.get("settings.files_pause")).grid(row=1, column=2, sticky=tk.W, padx=2)
        
        self.pause_duration_var = tk.StringVar(value="5")
        self.pause_duration_entry = ttk.Entry(pause_frame, textvariable=self.pause_duration_var, width=8)
        self.pause_duration_entry.grid(row=1, column=3, sticky=tk.W, padx=2, pady=2)
        ttk.Label(pause_frame, text=i18n.get("settings.seconds")).grid(row=1, column=4, sticky=tk.W, padx=2)
        
        # Cache Configuration
        cache_frame = ttk.LabelFrame(scrollable_frame, text=i18n.get("settings.cache_settings"), padding="5")
        cache_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        ttk.Label(cache_frame, text=i18n.get("settings.cache_dir")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.cache_dir_var = tk.StringVar()
        cache_dir_entry_frame = ttk.Frame(cache_frame)
        cache_dir_entry_frame.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        ttk.Entry(cache_dir_entry_frame, textvariable=self.cache_dir_var, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(cache_dir_entry_frame, text=i18n.get("settings.browse"), command=self._browse_cache_directory).pack(side=tk.LEFT, padx=(5, 0))
        
        ttk.Label(cache_frame, text=i18n.get("settings.max_size_mb")).grid(row=1, column=0, sticky=tk.W, padx=5)
        self.max_cache_size_var = tk.StringVar()
        ttk.Entry(cache_frame, textvariable=self.max_cache_size_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        
        cache_action_frame = ttk.Frame(cache_frame)
        cache_action_frame.grid(row=2, column=0, columnspan=2, pady=5, sticky=tk.W)
        self.cache_size_label = ttk.Label(cache_action_frame, text=i18n.get("settings.calculating"))
        self.cache_size_label.pack(side=tk.LEFT, padx=5)
        ttk.Button(cache_action_frame, text=i18n.get("settings.clear_cache"), command=self._clear_cache).pack(side=tk.LEFT, padx=15)
        ttk.Button(cache_action_frame, text=i18n.get("settings.refresh_size"), command=self._refresh_cache_size).pack(side=tk.LEFT, padx=5)
        
        cache_frame.columnconfigure(1, weight=1)

        # Post-Download Actions
        action_frame = ttk.LabelFrame(scrollable_frame, text=i18n.get("settings.post_download"), padding="5")
        action_frame.pack(fill=tk.X, pady=(0, 10), padx=5)
        
        self.post_action_var = tk.StringVar(value="none")
        self.post_action_combo = ttk.Combobox(action_frame, textvariable=self.post_action_var, 
                                               values=[i18n.get("settings.actions.none"), i18n.get("settings.actions.close"), i18n.get("settings.actions.shutdown"), i18n.get("settings.actions.hibernate"), i18n.get("settings.actions.sleep")],
                                               state="readonly", width=15)
        # Map display values to config values
        self.post_action_map = {
            i18n.get("settings.actions.none"): "none",
            i18n.get("settings.actions.close"): "close",
            i18n.get("settings.actions.shutdown"): "shutdown",
            i18n.get("settings.actions.hibernate"): "hibernate",
            i18n.get("settings.actions.sleep"): "sleep"
        }
        self.post_action_map_rev = {v: k for k, v in self.post_action_map.items()}
        self.post_action_combo.set(self.post_action_map_rev.get("none", i18n.get("settings.actions.none")))
        self.post_action_combo.pack(anchor=tk.W, padx=5, pady=5)
        
        # Save Settings Button
        ttk.Button(scrollable_frame, text=i18n.get("settings.save_settings"), command=self._save_settings).pack(pady=10)
        
    def _build_download_tab(self):
        """Build the Download tab."""
        download_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(download_frame, text=i18n.get("tabs.download"))
        
        # Task Type Selection
        task_frame = ttk.LabelFrame(download_frame, text=i18n.get("download.task_type"), padding="5")
        task_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.task_type_var = tk.StringVar(value="collection")
        ttk.Radiobutton(task_frame, text=i18n.get("download.collection"), variable=self.task_type_var, 
                        value="collection").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Radiobutton(task_frame, text=i18n.get("download.post"), variable=self.task_type_var, 
                        value="post").grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Radiobutton(task_frame, text=i18n.get("download.user"), variable=self.task_type_var, 
                        value="user").grid(row=0, column=2, sticky=tk.W, padx=5)
        
        ttk.Label(task_frame, text=i18n.get("download.id_label")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=(10, 0))
        self.ids_var = tk.StringVar()
        ttk.Entry(task_frame, textvariable=self.ids_var, width=50).grid(row=2, column=0, columnspan=3, 
                                                                         sticky=tk.EW, padx=5, pady=5)
        task_frame.columnconfigure(2, weight=1)
        
        # Options
        options_frame = ttk.LabelFrame(download_frame, text=i18n.get("download.options"), padding="5")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.dry_run_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text=i18n.get("download.dry_run"), variable=self.dry_run_var).pack(side=tk.LEFT, padx=10)
        
        self.no_metadata_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text=i18n.get("download.no_metadata"), variable=self.no_metadata_var).pack(side=tk.LEFT, padx=10)
        
        # Control Buttons
        btn_frame = ttk.Frame(download_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        self.start_btn = ttk.Button(btn_frame, text=i18n.get("download.start"), command=self._start_download)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text=i18n.get("download.stop"), command=self._stop_download, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text=i18n.get("download.open_folder"), command=self._open_download_dir).pack(side=tk.LEFT, padx=5)
        
        # Progress
        progress_frame = ttk.Frame(download_frame)
        progress_frame.pack(fill=tk.X, pady=5)
        
        self.progress_var = tk.StringVar(value=i18n.get("download.ready"))
        ttk.Label(progress_frame, textvariable=self.progress_var).pack(side=tk.LEFT)
        
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))
        
        # Log Output
        log_frame = ttk.LabelFrame(download_frame, text=i18n.get("download.log"), padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, state='disabled', wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Clear Log Button
        ttk.Button(log_frame, text=i18n.get("download.clear_log"), command=self._clear_log).pack(pady=5)
        
    def _build_about_tab(self):
        """Build the About tab."""
        about_frame = ttk.Frame(self.notebook, padding="20")
        self.notebook.add(about_frame, text=i18n.get("tabs.about"))
        
        # Title
        title_label = ttk.Label(about_frame, text=i18n.get("app_title"), font=('', 18, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # Version
        version_label = ttk.Label(about_frame, text=i18n.get("about.version_label", version="1.3.0"), font=('', 12))
        version_label.pack(pady=(0, 20))
        
        # Links
        links_frame = ttk.Frame(about_frame)
        links_frame.pack(pady=10)
        
        ttk.Label(links_frame, text=i18n.get("about.project_url")).grid(row=0, column=0, sticky=tk.E, padx=5)
        link1 = ttk.Label(links_frame, text="https://github.com/madlaxcb/CivitAI-Collection-Downloader", 
                          foreground="blue", cursor="hand2")
        link1.grid(row=0, column=1, sticky=tk.W, padx=5)
        link1.bind("<Button-1>", lambda e: self._open_url("https://github.com/madlaxcb/CivitAI-Collection-Downloader"))
        
        ttk.Label(links_frame, text=i18n.get("about.modified_from")).grid(row=1, column=0, sticky=tk.E, padx=5, pady=5)
        link2 = ttk.Label(links_frame, text="https://github.com/Ratione/CivitAI-Collection-Downloader", 
                          foreground="blue", cursor="hand2")
        link2.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        link2.bind("<Button-1>", lambda e: self._open_url("https://github.com/Ratione/CivitAI-Collection-Downloader"))
        
        # Agreement
        agreement_frame = ttk.LabelFrame(about_frame, text=i18n.get("about.user_agreement"), padding="5")
        agreement_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        agreement_text = scrolledtext.ScrolledText(agreement_frame, wrap=tk.WORD, font=('', 9))
        agreement_text.pack(fill=tk.BOTH, expand=True)
        agreement_text.insert(tk.END, get_agreement(i18n.current_language))
        agreement_text.configure(state='disabled')
        
        # Notice
        notice_label = ttk.Label(about_frame, text=i18n.get("about.agreement_notice"), 
                                  foreground="red", font=('', 10, 'bold'))
        notice_label.pack(pady=10)
        
    def _open_url(self, url):
        """Open URL in default browser."""
        import webbrowser
        webbrowser.open(url)
        
    def _export_config(self):
        """Export config to a user-selected file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="civitai_downloader_config.json"
        )
        if filepath:
            try:
                self._save_settings_to_config()
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(config._data, f, indent=4, ensure_ascii=False)
                messagebox.showinfo(i18n.get("messages.success"), i18n.get("messages.export_success", path=filepath))
            except Exception as e:
                messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.export_failed", error=e))
                
    def _import_config(self):
        """Import config from a user-selected file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                config.update(loaded_config)
                self._load_settings_to_ui()
                messagebox.showinfo(i18n.get("messages.success"), i18n.get("messages.import_success", path=filepath))
            except Exception as e:
                messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.import_failed", error=e))
                
    def _open_config_dir(self):
        """Open the config directory in file explorer."""
        config_dir = self.DEFAULT_CONFIG_DIR
        if sys.platform == 'win32':
            os.startfile(config_dir)
        elif sys.platform == 'darwin':
            subprocess.run(['open', config_dir])
        else:
            subprocess.run(['xdg-open', config_dir])
        
    def _load_settings_to_ui(self):
        """Load configuration values into UI fields."""
        self.language_var.set(config.get('language', 'zh_CN'))
        self.site_domain_var.set(config.get('site_domain', 'civitai.com'))
        self.api_key_var.set(config.get('api_key', ''))
        self.cdn_key_var.set(config.get('cdn_key', ''))
        self.download_dir_var.set(config.get('download_dir', ''))
        
        # File type settings
        self.download_images_var.set(config.get('download_images', True))
        self.download_videos_var.set(config.get('download_videos', True))
        
        # Proxy settings
        self.proxy_enabled_var.set(config.get('proxy_enabled', False))
        self.proxy_type_var.set(config.get('proxy_type', 'HTTP'))
        self.proxy_host_var.set(config.get('proxy_host', ''))
        self.proxy_port_var.set(config.get('proxy_port', ''))
        self.proxy_auth_var.set(config.get('proxy_auth', False))
        self.proxy_username_var.set(config.get('proxy_username', ''))
        self.proxy_password_var.set(config.get('proxy_password', ''))
        
        # Pause settings
        self.pause_enabled_var.set(config.get('pause_enabled', False))
        self.pause_after_files_var.set(str(config.get('pause_after_files', 10)))
        self.pause_duration_var.set(str(config.get('pause_duration', 5)))
        
        # Cache settings
        self.cache_dir_var.set(config.get('cache_dir', ''))
        self.max_cache_size_var.set(str(config.get('max_cache_size', 500)))
        self.root.after(100, self._refresh_cache_size)
        
        # Post-download action
        action_code = config.get('post_action', 'none')
        self.post_action_combo.set(self.post_action_map_rev.get(action_code, i18n.get("settings.actions.none")))
        
        # Update field states
        self._toggle_proxy_fields()
        self._toggle_proxy_auth()
        self._toggle_pause_fields()
        
    def _save_settings(self):
        """Save settings from UI to config and file."""
        self._save_settings_to_config()
        
        # Save to file
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(config._data, f, indent=4, ensure_ascii=False)
            messagebox.showinfo(i18n.get("messages.success"), i18n.get("messages.settings_saved"))
        except Exception as e:
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.save_failed", error=e))
            
    def _save_settings_to_config(self):
        """Save current UI settings to config object (without saving to file)."""
        config['language'] = self.language_var.get()
        config['site_domain'] = self.site_domain_var.get()
        config['api_key'] = self.api_key_var.get()
        
        import api as api_module
        api_module._CACHED_CDN_KEY = None
        config['cdn_key'] = self.cdn_key_var.get()
        config['download_dir'] = self.download_dir_var.get()
        
        # File type settings
        config['download_images'] = self.download_images_var.get()
        config['download_videos'] = self.download_videos_var.get()
        
        # Proxy settings
        config['proxy_enabled'] = self.proxy_enabled_var.get()
        config['proxy_type'] = self.proxy_type_var.get()
        config['proxy_host'] = self.proxy_host_var.get()
        config['proxy_port'] = self.proxy_port_var.get()
        config['proxy_auth'] = self.proxy_auth_var.get()
        config['proxy_username'] = self.proxy_username_var.get()
        config['proxy_password'] = self.proxy_password_var.get()
        
        # Pause settings
        try:
            config['pause_enabled'] = self.pause_enabled_var.get()
            config['pause_after_files'] = int(self.pause_after_files_var.get() or 10)
            config['pause_duration'] = int(self.pause_duration_var.get() or 5)
        except ValueError:
            pass
        
        # Cache settings
        config['cache_dir'] = self.cache_dir_var.get()
        try:
            config['max_cache_size'] = int(self.max_cache_size_var.get() or 500)
        except ValueError:
            pass
            
        # Post-download action
        display_value = self.post_action_combo.get()
        config['post_action'] = self.post_action_map.get(display_value, "none")
            
    def _on_language_change(self, event):
        """Handle language change."""
        selected_lang = self.language_var.get()
        if selected_lang != i18n.current_language:
            # Update language
            i18n.load_language(selected_lang)
            # Update window title
            self.root.title(i18n.get("app_title"))
            
            # Save settings
            self._save_settings_to_config() 
            
            # Rebuild UI
            self._rebuild_ui()
            
            # Save to file to persist preference
            self._save_settings()
            
    def _rebuild_ui(self):
        """Rebuild the UI to apply language changes."""
        # Save current tab index
        try:
            current_tab_idx = self.notebook.index(self.notebook.select())
        except Exception:
            current_tab_idx = 0
        
        # Destroy all tabs
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
            widget = self.notebook.nametowidget(tab_id)
            widget.destroy()
            
        # Rebuild tabs in order
        self._build_settings_tab()
        self._build_manager_tab()
        self._build_download_tab()
        self._build_about_tab()
        
        # Load settings back into UI (populates new widgets)
        self._load_settings_to_ui()
        
        # Restore selected tab
        if current_tab_idx < len(self.notebook.tabs()):
            self.notebook.select(current_tab_idx)

    def _open_download_dir(self):
        """Open the download directory in explorer."""
        path = self.download_dir_var.get()
        if path and os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning(i18n.get("messages.warning"), i18n.get("messages.dir_not_exist"))

    def _browse_directory(self):
        """Open directory browser dialog."""
        directory = filedialog.askdirectory(initialdir=self.download_dir_var.get())
        if directory:
            self.download_dir_var.set(directory)

    def _browse_cache_directory(self):
        """Open directory browser dialog for cache."""
        directory = filedialog.askdirectory(initialdir=self.cache_dir_var.get())
        if directory:
            self.cache_dir_var.set(directory)
            
    def _clear_cache(self):
        """Clear the cache."""
        if messagebox.askyesno(i18n.get("dialogs.confirm_clear_cache"), i18n.get("dialogs.confirm_clear_cache_msg")):
            if cache_manager.clear_cache():
                messagebox.showinfo(i18n.get("messages.success"), i18n.get("messages.cache_cleared"))
                self._refresh_cache_size()
            else:
                messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.cache_clear_failed"))
                
    def _refresh_cache_size(self):
        """Refresh cache size display."""
        size = cache_manager.get_cache_size()
        self.cache_size_label.configure(text=i18n.get("settings.current_size", size=f"{size:.2f}"))
            
    def _toggle_proxy_fields(self):
        """Show/hide proxy fields based on checkbox."""
        if self.proxy_enabled_var.get():
            self.proxy_details_frame.pack(fill=tk.X, expand=True)
            self._toggle_proxy_auth()
        else:
            self.proxy_details_frame.pack_forget()
        
    def _toggle_proxy_auth(self):
        """Enable/disable proxy auth fields."""
        can_edit = self.proxy_enabled_var.get() and self.proxy_auth_var.get()
        state = tk.NORMAL if can_edit else tk.DISABLED
        self.proxy_username_entry.configure(state=state)
        self.proxy_password_entry.configure(state=state)
        
    def _toggle_pause_fields(self):
        """Enable/disable pause fields based on checkbox."""
        state = tk.NORMAL if self.pause_enabled_var.get() else tk.DISABLED
        self.pause_after_files_entry.configure(state=state)
        self.pause_duration_entry.configure(state=state)
        
    def _setup_logging(self):
        """Setup logging to text widget."""
        logger = logging.getLogger()
        # Ensure we don't clear file handlers set by config.setup_logging
        
        # Remove existing TextHandlers to avoid duplicates
        for handler in logger.handlers[:]:
            if isinstance(handler, TextHandler):
                logger.removeHandler(handler)
        
        # Add text widget handler
        text_handler = TextHandler(self.log_text)
        text_handler.setLevel(logging.INFO)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S'))
        logger.addHandler(text_handler)
        
    def _clear_log(self):
        """Clear the log text widget."""
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        
    def _open_download_dir(self):
        """Open the download directory in file explorer."""
        download_dir = config.get('download_dir')
        if not download_dir or not os.path.exists(download_dir):
             messagebox.showwarning(i18n.get("messages.warning"), i18n.get("messages.dir_not_exist"))
             return
             
        if sys.platform == 'win32':
            os.startfile(download_dir)
        elif sys.platform == 'darwin':
            subprocess.run(['open', download_dir])
        else:
            subprocess.run(['xdg-open', download_dir])
        
    def _start_download(self):
        """Start the download process in a separate thread."""
        # Validate inputs
        ids_str = self.ids_var.get().strip()
        if not ids_str:
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.enter_id"))
            return
            
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.configure_api_key"))
            return
            
        # Check file type selection
        if not self.download_images_var.get() and not self.download_videos_var.get():
            messagebox.showerror(i18n.get("messages.error"), i18n.get("messages.select_file_type"))
            return
            
        # Apply current settings to config
        self._save_settings_to_config()
        
        # Parse IDs
        ids = [id.strip() for id in ids_str.split(',') if id.strip()]
        
        # Update UI state
        self.start_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.stop_requested = False
        self.progress_bar.start()
        
        # Start download thread
        self.download_thread = threading.Thread(target=self._download_worker, args=(ids,), daemon=True)
        self.download_thread.start()
        
    def _should_download_file(self, mime_type):
        """Check if file should be downloaded based on type settings."""
        if not mime_type:
            return True
            
        is_image = mime_type.startswith('image/')
        is_video = mime_type.startswith('video/')
        
        if is_image and self.download_images_var.get():
            return True
        if is_video and self.download_videos_var.get():
            return True
        if not is_image and not is_video:
            return True  # Download unknown types
            
        return False
        
    def _download_worker(self, ids):
        """Worker function for download thread."""
        logger = logging.getLogger()
        task_type = self.task_type_var.get()
        dry_run = self.dry_run_var.get()
        skip_metadata = self.no_metadata_var.get()
        api_key = config.get('api_key')
        
        api = CivitaiAPI(api_key)
        
        total_files_downloaded = 0
        pause_enabled = config.get('pause_enabled', False)
        pause_after = config.get('pause_after_files', 10)
        pause_duration = config.get('pause_duration', 5)
        
        try:
            for task_id in ids:
                if self.stop_requested:
                    logger.info(i18n.get("download.stopped"))
                    break
                    
                self._update_progress(i18n.get("download.processing_task", type=task_type, id=task_id))
                
                if task_type == "collection":
                    success = self._process_collection(api, task_id, dry_run, skip_metadata, api_key,
                                                        total_files_downloaded, pause_enabled, pause_after, pause_duration)
                elif task_type == "user":
                    success = self._process_user(api, task_id, dry_run, skip_metadata, api_key,
                                                  total_files_downloaded, pause_enabled, pause_after, pause_duration)
                else:
                    success = self._process_post(api, task_id, dry_run, skip_metadata, api_key,
                                                  total_files_downloaded, pause_enabled, pause_after, pause_duration)
                    
                if not success:
                    logger.error(i18n.get("download.error_process", type=task_type, id=task_id, error="Failed"))
                    
            self._update_progress(i18n.get("download.completed"))
            
        except Exception as e:
            logger.exception(i18n.get("download.error_prefix", error=e))
            self._update_progress(i18n.get("download.error_prefix", error=e))
            
        finally:
            self.root.after(0, self._download_finished)
            
    def _process_user(self, api, username, dry_run, skip_metadata, api_key,
                      files_counter, pause_enabled, pause_after, pause_duration):
        """Process a user download."""
        logger = logging.getLogger()
        
        try:
            # Handle full URL input
            current_domain = config.get('site_domain', 'civitai.com')
            if f"{current_domain}/user/" in username:
                username = username.split(f"{current_domain}/user/")[1].split("/")[0]
            
            download_dir = create_download_directory({"collection": {"id": f"user-{username}", "name": username}})
            media_items = api.get_all_images_by_username(username)
            
            if not media_items:
                logger.error(i18n.get("download.no_media_found", type="User", id=username))
                return False
                
            logger.info(i18n.get("download.media_found", count=len(media_items), type="User", id=username))
            
            downloaded_items = []
            
            for i, item in enumerate(media_items):
                if self.stop_requested:
                    logger.info(i18n.get("download.stopped"))
                    break
                    
                # Pause logic
                if pause_enabled and files_counter > 0 and files_counter % pause_after == 0:
                    logger.info(i18n.get("download.paused_after", count=files_counter, seconds=pause_duration))
                    time.sleep(pause_duration)
                
                # Check mime type
                if not self._should_download_file(item.get('mimeType')):
                    continue
                    
                self._update_progress(i18n.get("download.processing_item", current=i+1, total=len(media_items), id=item.get('id')))
                
                if dry_run:
                    logger.info(i18n.get("download.preview_download", id=item.get('id'), url=item.get('url')))
                    downloaded_items.append(item)
                    files_counter += 1
                else:
                    file_path = download_media(item, download_dir, api_key)
                    if file_path:
                        files_counter += 1
                        
                        # Handle metadata
                        if not skip_metadata:
                            metadata = extract_metadata(api, item)
                            json_path = file_path.with_suffix('.json')
                            save_metadata(metadata, json_path)
                            
                        downloaded_items.append(item)
            
            # Save collection metadata for user
            if not skip_metadata and not dry_run:
                # Mock collection object for user
                user_meta = {
                    "id": f"user-{username}",
                    "name": username,
                    "type": "user",
                    "media_count": len(downloaded_items),
                    "media": downloaded_items
                }
                save_metadata(user_meta, download_dir / "user_metadata.json")
                
            return True
            
        except Exception as e:
            logger.exception(i18n.get("download.error_process", type="User", id=username, error=e))
            return False

    def _process_collection(self, api, collection_id, dry_run, skip_metadata, api_key,
                            files_counter, pause_enabled, pause_after, pause_duration):
        """Process a collection download."""
        logger = logging.getLogger()
        
        try:
            download_dir = create_download_directory(collection_id)
            media_items = api.get_all_images_in_collection(collection_id)
            
            if not media_items:
                logger.error(i18n.get("download.no_media_found", type="Collection", id=collection_id))
                return False
                
            logger.info(i18n.get("download.media_found", count=len(media_items), type="Collection", id=collection_id))
            
            downloaded_items = []
            items_metadata = []
            files_in_batch = 0
            
            for i, item in enumerate(media_items):
                if self.stop_requested:
                    break
                    
                item_id = item.get("id")
                mime_type = item.get("mimeType", "image/jpeg")
                
                # Check file type filter
                if not self._should_download_file(mime_type):
                    logger.info(i18n.get("download.skipping_item", id=item_id, type=mime_type))
                    continue
                    
                self._update_progress(i18n.get("download.processing_item", current=i+1, total=len(media_items), id=item_id))
                
                item_details = api.get_image_details(item_id) or item
                metadata = extract_metadata(api, item_details)
                items_metadata.append(metadata)
                
                if not dry_run:
                    downloaded_file = download_media(item_details, download_dir, api_key)
                    if downloaded_file:
                        downloaded_items.append(downloaded_file)
                        files_in_batch += 1
                        
                        if not skip_metadata:
                            base_name = downloaded_file.stem
                            meta_path = download_dir / f"{base_name}_metadata.json"
                            save_metadata(metadata, meta_path)
                            
                        # Check pause condition
                        if pause_enabled and files_in_batch >= pause_after:
                            logger.info(i18n.get("download.paused_after", count=pause_after, seconds=pause_duration))
                            self._update_progress(i18n.get("download.pausing", seconds=pause_duration))
                            time.sleep(pause_duration)
                            files_in_batch = 0
                            
            if not skip_metadata and not dry_run and items_metadata:
                collection_data = api.get_collection_by_id(collection_id)
                if collection_data:
                    collection_metadata = create_collection_metadata(api, collection_id, items_metadata)
                else:
                    collection_metadata = {
                        "id": collection_id,
                        "name": f"Collection-{collection_id}",
                        "media_count": len(items_metadata),
                        "media": items_metadata
                    }
                metadata_path = download_dir / "collection_metadata.json"
                save_metadata(collection_metadata, metadata_path)
                
            logger.info(i18n.get("download.success_process", processed=len(downloaded_items) if not dry_run else len(items_metadata), total=len(media_items), type="Collection", id=collection_id))
            return True
            
        except Exception as e:
            logger.error(i18n.get("download.error_process", type="Collection", id=collection_id, error=e))
            return False
            
    def _process_post(self, api, post_id, dry_run, skip_metadata, api_key,
                      files_counter, pause_enabled, pause_after, pause_duration):
        """Process a post download."""
        logger = logging.getLogger()
        
        try:
            post = api.get_post_by_id(post_id)
            if not post:
                logger.error(i18n.get("download.error_process", type="Post", id=post_id, error="Not found"))
                return False
                
            download_dir_base = config.get('download_dir')
            if not download_dir_base:
                download_dir_base = os.path.join(os.path.expanduser('~'), 'Pictures', 'CivitAI')
                
            post_title = post.get("title", "") if post else ""
            if post_title:
                download_dir = Path(download_dir_base) / f"{post_id}-{sanitize_filename(post_title)}"
            else:
                download_dir = Path(download_dir_base) / f"{post_id}"
            download_dir.mkdir(parents=True, exist_ok=True)
            
            media_items = api.get_all_images_in_post(post_id)
            if not media_items:
                logger.error(i18n.get("download.no_media_found", type="Post", id=post_id))
                return False
                
            logger.info(i18n.get("download.media_found", count=len(media_items), type="Post", id=post_id))
            
            downloaded_items = []
            items_metadata = []
            files_in_batch = 0
            
            for i, item in enumerate(media_items):
                if self.stop_requested:
                    break
                    
                item_id = item.get("id")
                mime_type = item.get("mimeType", "image/jpeg")
                
                # Check file type filter
                if not self._should_download_file(mime_type):
                    logger.info(i18n.get("download.skipping_item", id=item_id, type=mime_type))
                    continue
                    
                self._update_progress(i18n.get("download.processing_item", current=i+1, total=len(media_items), id=item_id))
                
                item_details = api.get_image_details(item_id) or item
                metadata = extract_metadata(api, item_details)
                items_metadata.append(metadata)
                
                if not dry_run:
                    downloaded_file = download_media(item_details, download_dir, api_key)
                    if downloaded_file:
                        downloaded_items.append(downloaded_file)
                        files_in_batch += 1
                        
                        if not skip_metadata:
                            base_name = downloaded_file.stem
                            meta_path = download_dir / f"{base_name}_metadata.json"
                            save_metadata(metadata, meta_path)
                            
                        # Check pause condition
                        if pause_enabled and files_in_batch >= pause_after:
                            logger.info(i18n.get("download.paused_after", count=pause_after, seconds=pause_duration))
                            self._update_progress(i18n.get("download.pausing", seconds=pause_duration))
                            time.sleep(pause_duration)
                            files_in_batch = 0
                            
            if not skip_metadata and not dry_run:
                post_metadata = {
                    "id": post_id,
                    "title": post_title,
                    "media_count": len(items_metadata),
                    "media": items_metadata
                }
                metadata_path = download_dir / "post_metadata.json"
                save_metadata(post_metadata, metadata_path)
                
            logger.info(i18n.get("download.success_process", processed=len(downloaded_items), total=len(media_items), type="Post", id=post_id))
            return True
            
        except Exception as e:
            logger.error(i18n.get("download.error_process", type="Post", id=post_id, error=e))
            return False
            
    def _update_progress(self, message):
        """Update progress label (thread-safe)."""
        self.root.after(0, lambda: self.progress_var.set(message))
        
    def _download_finished(self):
        """Called when download thread finishes."""
        self.start_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)
        self.progress_bar.stop()
        
        # Execute post-download action
        if not self.stop_requested:
            self._execute_post_action()
        
    def _execute_post_action(self):
        """Execute the configured post-download action."""
        action = self.post_action_var.get()
        logger = logging.getLogger()
        
        if action == "none":
            return
        elif action == "close":
            logger.info(i18n.get("download.closing_app"))
            self.root.after(2000, self.root.destroy)
        elif action == "shutdown":
            logger.info(i18n.get("download.shutdown_msg"))
            self.root.after(3000, lambda: self._system_action("shutdown"))
        elif action == "hibernate":
            logger.info(i18n.get("download.hibernate_msg"))
            self.root.after(3000, lambda: self._system_action("hibernate"))
        elif action == "sleep":
            logger.info(i18n.get("download.sleep_msg"))
            self.root.after(3000, lambda: self._system_action("sleep"))
            
    def _system_action(self, action):
        """Execute system action (shutdown/hibernate/sleep)."""
        try:
            if sys.platform == 'win32':
                if action == "shutdown":
                    subprocess.run(["shutdown", "/s", "/t", "30"], check=True)
                elif action == "hibernate":
                    subprocess.run(["shutdown", "/h"], check=True)
                elif action == "sleep":
                    subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"], check=True)
            else:
                if action == "shutdown":
                    subprocess.run(["shutdown", "-h", "now"], check=True)
                elif action in ["hibernate", "sleep"]:
                    subprocess.run(["systemctl", "suspend"], check=True)
        except Exception as e:
            logging.getLogger().error(i18n.get("download.system_op_failed", error=e))
        finally:
            self.root.destroy()
        
    def _stop_download(self):
        """Request download to stop."""
        self.stop_requested = True
        self.progress_var.set(i18n.get("download.stopping"))
        
    def run(self):
        """Run the application."""
        self.root.mainloop()


def main():
    """Main entry point."""
    try:
        app = CivitAIDownloaderGUI()
        app.run()
    except Exception as e:
        import traceback
        # Print to console (for debug build)
        print("CRITICAL ERROR CAUGHT:")
        traceback.print_exc()
        print(f"\nError details: {e}")
        
        # Write to log file
        try:
            with open("crash_log.txt", "w") as f:
                f.write(traceback.format_exc())
                f.write(f"\nError: {e}")
        except:
            print("Failed to write to crash_log.txt")
            
        # Try to show message box
        try:
            import tkinter.messagebox
            tkinter.messagebox.showerror("Critical Error", f"Application crashed:\n{e}\n\nSee console or crash_log.txt for details.")
        except:
            pass
            
        print("\nPress Enter to exit...")
        input()
        sys.exit(1)


if __name__ == "__main__":
    main()
