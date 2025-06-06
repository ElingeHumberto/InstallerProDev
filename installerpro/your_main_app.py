# installerpro/your_main_app.py (Versión Final Unificada)
import os
import sys
import logging
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import platform
from queue import Queue, Empty
import threading
import shutil
try:
    import git
except ImportError:
    print("ERROR: GitPython no está instalado. Por favor, ejecuta 'pip install GitPython'")
    sys.exit(1)


# --- CONFIGURACIÓN INICIAL ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- IMPORTACIONES LOCALES ---
# Asegurarse de que el directorio padre esté en el path para las importaciones
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from installerpro import i18n
from installerpro.utils import git_operations
from installerpro.ui_dialogs import AddProjectDialog, Tooltip


# ==============================================================================
# CLASE ConfigManager
# ==============================================================================
class ConfigManager:
    APP_NAME = "InstallerPro"
    APP_AUTHOR = "ElingeHumberto"
    
    def __init__(self):
        if platform.system() == "Windows":
            self.user_config_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), self.APP_NAME, "Config")
            self.user_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser("~")), self.APP_NAME, "Data")
        else:
            self.user_config_dir = os.path.join(os.path.expanduser("~"), f".config/{self.APP_NAME}")
            self.user_data_dir = os.path.join(os.path.expanduser("~"), f".local/share/{self.APP_NAME}")
        
        os.makedirs(self.user_config_dir, exist_ok=True)
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        self.config_file_path = os.path.join(self.user_config_dir, "config.json")
        self.projects_file_path = os.path.join(self.user_data_dir, "projects.json")
        self._config_data = {}
        self._load_config()

    def _get_default_config(self):
        default_base_folder = os.path.join(os.path.expanduser("~"), 'Workspace')
        return {'base_folder': os.path.abspath(os.path.normpath(default_base_folder)), 'language': 'system'}

    def _load_config(self):
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self._config_data = json.load(f)
                logger.info(f"Configuration loaded from: {self.config_file_path}")
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading config, using defaults: {e}")
                self._config_data = self._get_default_config()
                self._save_config()
        else:
            logger.info("Config file not found, creating default.")
            self._config_data = self._get_default_config()
            self._save_config()

    def _save_config(self):
        try:
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=4)
            logger.info(f"Configuration saved to: {self.config_file_path}")
        except IOError as e:
            logger.error(f"Error saving config: {e}")

    def get_setting(self, key, default=None):
        return self._config_data.get(key, default)

    def set_setting(self, key, value):
        if self.get_setting(key) != value:
            self._config_data[key] = value
            self._save_config()

    def get_base_folder(self):
        return self.get_setting('base_folder', self._get_default_config()['base_folder'])

    def set_base_folder(self, folder_path):
        normalized_path = os.path.abspath(os.path.normpath(folder_path))
        os.makedirs(normalized_path, exist_ok=True)
        self.set_setting('base_folder', normalized_path)

# ==============================================================================
# CLASE ProjectManager
# ==============================================================================
class ProjectNotFoundError(Exception):
    pass

class ProjectManager:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.projects_file_path = self.config_manager.projects_file_path
        self.base_folder = self.config_manager.get_base_folder()
        self.projects = []
        self._load_projects()
        logger.info(f"ProjectManager initialized with base folder: {self.base_folder}")

    def _load_projects(self):
        if os.path.exists(self.projects_file_path):
            try:
                with open(self.projects_file_path, 'r', encoding='utf-8') as f: self.projects = json.load(f)
            except json.JSONDecodeError: self.projects = []
        else: self.projects = []
        self.refresh_project_statuses()

    def _save_projects(self):
        with open(self.projects_file_path, 'w', encoding='utf-8') as f: json.dump(self.projects, f, indent=4)

    def get_projects(self):
        return [p for p in self.projects if not p.get('deleted', False)]

    def get_project_by_path(self, local_path):
        for p in self.projects:
            if os.path.normpath(p['local_path']) == os.path.normpath(local_path): return p
        return None

    def add_project(self, name, repo_url, local_path_full, branch):
        git_operations.clone_repository(repo_url, local_path_full, branch)
        new_project = {"name": name, "local_path": local_path_full, "repo_url": repo_url, "branch": branch, "status": "Clean", "deleted": False}
        self.projects.append(new_project)
        self._save_projects()
        self.refresh_project_statuses()
        return new_project

    def remove_project(self, local_path, permanent=False):
        project = self.get_project_by_path(local_path)
        if not project: raise ProjectNotFoundError(f"Project not found: {local_path}")
        if permanent:
            if os.path.exists(local_path): shutil.rmtree(local_path)
            self.projects = [p for p in self.projects if os.path.normpath(p['local_path']) != os.path.normpath(local_path)]
        else: project['deleted'] = True
        self._save_projects()

    def set_base_folder(self, folder_path):
        self.base_folder = os.path.abspath(folder_path)
        logger.info(f"ProjectManager base folder updated to: {self.base_folder}")

    def scan_base_folder(self):
        logger.info(f"Scanning base folder for new Git repositories: {self.base_folder}")
        found_count = 0
        existing_paths = {os.path.normpath(p['local_path']) for p in self.projects}
        for item in os.listdir(self.base_folder):
            repo_path = os.path.join(self.base_folder, item)
            if os.path.isdir(repo_path) and git_operations.is_git_repository(repo_path):
                if os.path.normpath(repo_path) not in existing_paths:
                    try:
                        name = os.path.basename(repo_path)
                        repo_url = git_operations.get_repo_remote_url(repo_path)
                        branch = git_operations.get_repo_current_branch(repo_path)
                        new_project = {"name": name, "local_path": repo_path, "repo_url": repo_url, "branch": branch, "status": "Unknown", "deleted": False}
                        self.projects.append(new_project)
                        found_count += 1
                    except Exception as e:
                        logger.warning(f"Could not process {repo_path} during scan: {e}", exc_info=True)
        if found_count > 0: self._save_projects()
        self.refresh_project_statuses()
        return found_count

    def refresh_project_statuses(self):
        """
        Refresca TODA la información de los proyectos: estado, rama y URL remota.
        """
        logger.info("Refreshing all project data...")
        something_changed = False
        for project in self.get_projects():
            old_status = project.get('status')
            old_branch = project.get('branch')
            old_url = project.get('repo_url')

            project['status'] = git_operations.get_repo_status(project['local_path'])
            project['branch'] = git_operations.get_repo_current_branch(project['local_path'])
            project['repo_url'] = git_operations.get_repo_remote_url(project['local_path'])

            if (project['status'] != old_status or 
                project['branch'] != old_branch or 
                project['repo_url'] != old_url):
                something_changed = True
    
        if something_changed:
            logger.info("Project data has changed, saving updates.")
            self._save_projects()
        else:
            logger.info("No changes in project data detected.")


    def get_changed_files_for_project(self, local_path):
        return git_operations.get_changed_files(local_path)
    
    def commit_project_changes(self, local_path, files_to_stage, commit_message):
        git_operations.stage_files(local_path, files_to_stage)
        commit_result = git_operations.commit_changes(local_path, commit_message)
        self.refresh_project_statuses()
        return commit_result
    
    def update_project(self, local_path, branch):
        return git_operations.pull_repository(local_path, branch)
        
    def push_project(self, local_path):
        return git_operations.push_repository(local_path)

# ==============================================================================
# CLASE PRINCIPAL DE LA APLICACIÓN
# ==============================================================================
class InstallerProApp:
    def __init__(self, master):
        self.master = master
        self.logger = logging.getLogger(__name__)
        self.master.withdraw()
        
        self.config_manager = ConfigManager()
        self.project_manager = ProjectManager(self.config_manager)

        base_dir = os.path.dirname(os.path.abspath(__file__))
        locales_path = os.path.join(base_dir, 'utils', 'locales')
        i18n.set_locales_dir(locales_path)
        self._initialize_language()
        self.t = i18n.t
        
        self.staged_files = {}
        self.task_queue = Queue()
        self._setup_ui() # <- La llamada que fallaba antes
        self.update_ui_texts()
        self.master.after(100, self._process_task_queue)
        
        self.logger.info("InstallerPro - Git Project Manager started.")
        self.master.deiconify()

    def _initialize_language(self):
        lang_from_config = self.config_manager.get_setting('language', 'system')
        logger.info(f"Language from config: {lang_from_config}")
        effective_lang = lang_from_config
        if lang_from_config == "system":
            system_lang = i18n.get_system_language_code()
            available_langs = i18n.get_available_languages()
            if system_lang and system_lang in available_langs:
                effective_lang = system_lang
            else:
                effective_lang = 'en'
        if not i18n.set_language(effective_lang):
            logger.error(f"Failed to set language to {effective_lang}")
        else:
            logger.info(f"Effective application language set to: {i18n.get_current_language()}")

    def _recreate_menubar(self):
        if hasattr(self, 'menubar') and self.menubar.winfo_exists():
            try: self.menubar.destroy()
            except tk.TclError: pass
        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)
        view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(menu=view_menu, label=self.t("View Menu"))
        self.lang_menu = tk.Menu(view_menu, tearoff=0)
        view_menu.add_cascade(menu=self.lang_menu, label=self.t("Language Menu"))
        self._populate_language_menu()

    def _setup_ui(self):
        self.master.geometry("900x700")
        self.master.title(self.t("App Title"))
        style = ttk.Style(self.master)
        if 'clam' in style.theme_names(): style.theme_use('clam')
        
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.rowconfigure(0, weight=1)
        
        self._recreate_menubar()
        
        self.main_paned_window = ttk.PanedWindow(self.main_frame, orient=tk.VERTICAL)
        self.main_paned_window.grid(row=0, column=0, sticky="nsew", pady=5)

        top_pane = ttk.Frame(self.main_paned_window)
        top_pane.columnconfigure(0, weight=1); top_pane.rowconfigure(0, weight=1)
        self.main_paned_window.add(top_pane, weight=2)
        
        tree_scrollbar_y = ttk.Scrollbar(top_pane, orient="vertical")
        columns = ("name", "path", "url", "branch", "status")
        self.tree = ttk.Treeview(top_pane, columns=columns, show="headings", yscrollcommand=tree_scrollbar_y.set)
        tree_scrollbar_y.config(command=self.tree.yview)
        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.tree.bind('<<TreeviewSelect>>', self._on_project_select)

        self.commit_pane = ttk.Frame(self.main_paned_window, padding=5)
        self.commit_pane.columnconfigure(0, weight=1); self.commit_pane.rowconfigure(1, weight=1)
        self.main_paned_window.add(self.commit_pane, weight=3)
        self.files_tree_label = ttk.Label(self.commit_pane, font=("tahoma", 10, "bold"))
        self.files_tree_label.grid(row=0, column=0, sticky="w", pady=(0, 5))
        
        files_frame = ttk.Frame(self.commit_pane)
        files_frame.grid(row=1, column=0, sticky='nsew')
        files_frame.rowconfigure(0, weight=1); files_frame.columnconfigure(0, weight=1)
        
        file_columns = ("status", "path"); self.files_tree = ttk.Treeview(files_frame, columns=file_columns, show="tree headings")
        files_tree_scrollbar_y = ttk.Scrollbar(files_frame, orient="vertical", command=self.files_tree.yview)
        files_tree_scrollbar_x = ttk.Scrollbar(files_frame, orient="horizontal", command=self.files_tree.xview)
        self.files_tree.configure(yscrollcommand=files_tree_scrollbar_y.set, xscrollcommand=files_tree_scrollbar_x.set)
        self.files_tree.grid(row=0, column=0, sticky='nsew'); files_tree_scrollbar_y.grid(row=0, column=1, sticky='ns'); files_tree_scrollbar_x.grid(row=1, column=0, sticky='ew')
        
        self.files_tree.column("#0", width=50, anchor="center", stretch=False)
        self.files_tree.column("status", width=100, anchor="w", stretch=False)
        self.files_tree.column("path", width=450, anchor="w")
        self.files_tree.tag_configure('unchecked', foreground='gray', font=('Segoe UI Symbol', 11))
        self.files_tree.tag_configure('checked', foreground='#007ACC', font=('Segoe UI Symbol', 11))
        self.files_tree.bind('<Button-1>', self._toggle_file_stage_status)
        
        self.commit_action_frame = ttk.Frame(self.commit_pane); self.commit_action_frame.grid(row=2, column=0, sticky='ew', pady=(5, 0)); self.commit_action_frame.columnconfigure(0, weight=1)
        commit_message_container = ttk.LabelFrame(self.commit_action_frame); commit_message_container.grid(row=0, column=0, sticky='nsew', padx=(0, 5)); commit_message_container.columnconfigure(0, weight=1)
        self.commit_message_text = tk.Text(commit_message_container, height=4, wrap=tk.WORD, relief=tk.FLAT); self.commit_message_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        commit_buttons_frame = ttk.Frame(self.commit_action_frame); commit_buttons_frame.grid(row=0, column=1, sticky='ns')
        self.stage_all_button = ttk.Button(commit_buttons_frame, command=self._toggle_stage_all); self.stage_all_button.pack(fill=tk.X, padx=5, pady=2)
        self.commit_button = ttk.Button(commit_buttons_frame, command=self._perform_commit); self.commit_button.pack(fill=tk.X, padx=5, pady=2)

        self.buttons_frame = ttk.Frame(self.main_frame); self.buttons_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        button_map = {"add": self._add_project, "remove": self._remove_project, "update": self._update_project, "scan_base_folder": self._scan_base_folder, "push": self._push_project, "refresh_status": self._refresh_all_statuses}
        for key, command in button_map.items():
            button = ttk.Button(self.buttons_frame, command=command); button.pack(side=tk.LEFT, padx=5, pady=5); setattr(self, f"{key}_button", button)
        self.help_button = ttk.Button(self.buttons_frame, command=self._show_help); self.help_button.pack(side=tk.RIGHT, padx=5, pady=5)
        self.base_folder_label = ttk.Label(self.main_frame, text=""); self.base_folder_label.grid(row=2, column=0, sticky="ew", padx=5, pady=(5,0))

    def _populate_language_menu(self):
        # ... (código existente)
        self.lang_menu.delete(0, tk.END)
        self.selected_language_var = tk.StringVar(value=self.config_manager.get_setting('language'))
        self.lang_menu.add_radiobutton(label=self.t("language_option.system"), command=lambda: self.change_language("system"), variable=self.selected_language_var, value="system")
        self.lang_menu.add_separator()
        for lang_code in i18n.get_available_languages():
            self.lang_menu.add_radiobutton(label=self.t(f"language_option.{lang_code}", fallback=lang_code.upper()), command=lambda lc=lang_code: self.change_language(lc), variable=self.selected_language_var, value=lang_code)

    def update_ui_texts(self):
        # ... (código existente)
        self.master.title(self.t("App Title"))
        self._recreate_menubar()
        column_map = {"name": ("Project Name Column", 150), "path": ("Local Path Column", 300), "url": ("Repository URL Column", 300), "branch": ("Branch Column", 100), "status": ("Status Column", 100)}
        for col, (key, width) in column_map.items():
            self.tree.heading(col, text=self.t(key)); self.tree.column(col, width=width, minwidth=int(width*0.5))
        button_map_texts = {"add": "add_button", "remove": "remove_button", "update": "update_button", "scan_base_folder": "scan_base_folder_button", "push": "push_button", "refresh_status": "refresh_status_button", "help": "help_button"}
        for key, attr_name in button_map_texts.items():
            if hasattr(self, attr_name): getattr(self, attr_name).config(text=self.t(f"button.{key}"))
        if hasattr(self, 'files_tree_label'): self.files_tree_label.config(text=self.t("Changed files title"))
        if hasattr(self, 'files_tree'):
            self.files_tree.heading("#0", text=self.t("Staged Column")); self.files_tree.heading("status", text=self.t("File Status Column")); self.files_tree.heading("path", text=self.t("File Path Column"))
        if hasattr(self, 'commit_message_container'): self.commit_message_container.config(text=self.t("Commit Message Title"))
        if hasattr(self, 'stage_all_button'): self.stage_all_button.config(text=self.t("Stage All Button"))
        if hasattr(self, 'commit_button'): self.commit_button.config(text=self.t("Commit Button"))
        self.update_base_folder_label()
        self._load_projects_into_treeview()

    def _process_task_queue(self):
        try:
            while not self.task_queue.empty():
                callback, args, kwargs = self.task_queue.get_nowait()
                callback(*args, **kwargs)
        except Empty: pass
        finally:
            self.master.after(100, self._process_task_queue)

    def update_base_folder_label(self):
        self.base_folder_label.config(text=self.t("base_folder_status_label", path=self.config_manager.get_base_folder()))

    def change_language(self, lang_code):
        """Cambia el idioma, actualiza la configuración y refresca toda la UI."""
        current_lang = self.config_manager.get_setting('language')
        if current_lang == lang_code:
            if lang_code != "system" or (lang_code == "system" and current_lang == "system"):
                logger.info(f"Language already set to '{lang_code}'. No change needed.")
                return

        # Guardamos la nueva preferencia del usuario
        self.config_manager.set_setting('language', lang_code)
    
        # Aplicamos el idioma y actualizamos la interfaz
        self._initialize_language()
        self.t = i18n.t
        self.update_ui_texts()
    
        messagebox.showinfo(
            self.t("Language Changed Title"), 
            self.t("Language changed message", lang=i18n.get_current_language())
        )

    def _load_projects_into_treeview(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        projects = self.project_manager.get_projects()
        for project in projects:
            status_key = f"status.{project.get('status', 'unknown').lower()}"
            status_display = self.t(status_key, fallback=project.get('status', "Unknown"))
            self.tree.insert("", tk.END, values=(project['name'], project['local_path'], project['repo_url'], project['branch'], status_display))

    def _get_selected_project_path(self):
        selected_item = self.tree.focus()
        if not selected_item: return None
        return self.tree.item(selected_item, 'values')[1]

    def _on_project_select(self, event=None):
        for item in self.files_tree.get_children(): self.files_tree.delete(item)
        self.staged_files.clear()
        selected_path = self._get_selected_project_path()
        if not selected_path:
            self.files_tree_label.config(text="")
            return
        project = self.project_manager.get_project_by_path(selected_path)
        if project and project.get('status') == 'modified':
            self.files_tree_label.config(text=self.t("Changed files title"))
            try:
                changed_files = self.project_manager.get_changed_files_for_project(selected_path)
                for file_info in changed_files:
                    status_key = f"status.file.{file_info['status']}"
                    status_display = self.t(status_key, fallback=file_info['status'].capitalize())
                    self.files_tree.insert("", tk.END, text='☐', values=(status_display, file_info['path']), tags=('unchecked',))
            except ProjectNotFoundError as e:
                logger.error(f"Error getting changed files: {e}")
        else:
            self.files_tree_label.config(text=self.t("Commit panel placeholder clean"))

    def _toggle_file_stage_status(self, event):
        row_id = self.files_tree.identify_row(event.y)
        if not row_id or self.files_tree.identify_column(event.x) != '#0': return
        try:
            file_path = self.files_tree.item(row_id, 'values')[1]
            is_staged = not self.staged_files.get(file_path, False)
            self.staged_files[file_path] = is_staged
            self.files_tree.item(row_id, text='☑' if is_staged else '☐', tags=('checked' if is_staged else 'unchecked',))
        except IndexError: pass
        
    def _toggle_stage_all(self):
        """Prepara o desprepara todos los archivos de la lista."""
        item_ids = self.files_tree.get_children()
        if not item_ids:
            return

        # Lógica simplificada: si hay algo preparado, las quitamos todas.
        # Si no hay nada preparado, las preparamos todas.
        staged_count = sum(self.staged_files.values())
        new_stage_status = staged_count == 0

        # Determinamos el estado visual y el texto del botón para la siguiente acción
        new_tag = 'checked' if new_stage_status else 'unchecked'
        new_text = '☑' if new_stage_status else '☐'
        next_action_key = "Unstage All Button" if new_stage_status else "Stage All Button"

        # Iteramos sobre todos los archivos para actualizar tanto el estado lógico como la UI
        for item_id in item_ids:
            values = self.files_tree.item(item_id, 'values')
            if not values:
                continue
        
            # --- CORRECCIÓN PRINCIPAL ---
            # La ruta del archivo ahora está en la posición 1 de los valores, no en la 2.
            try:
                file_path = values[1]
                self.staged_files[file_path] = new_stage_status
                self.files_tree.item(item_id, text=new_text, tags=(new_tag,))
            except IndexError:
                logger.warning(f"Could not process item {item_id} during toggle all.")
    
        # Actualizamos el texto del botón para que refleje la siguiente acción posible
        self.stage_all_button.config(text=self.t(next_action_key))


    def _run_async_task(self, target, *args, on_success=None, on_failure=None):
        def task_wrapper():
            try:
                result = target(*args)
                if on_success: self.task_queue.put((on_success, (result,), {}))
            except Exception as e:
                logger.error(f"Task exception for {target.__name__}: {e}", exc_info=True)
                if on_failure: self.task_queue.put((on_failure, (e,), {}))
        threading.Thread(target=task_wrapper, daemon=True).start()

    def _add_project(self):
        dialog = AddProjectDialog(self.master, self.t, self.config_manager.get_base_folder())
        result = dialog.result
        if result:
            self._run_async_task(self.project_manager.add_project, result['name'], result['repo_url'], result['local_path_full'], result['branch'],
                                 on_success=self._on_project_added_success,
                                 on_failure=lambda e: self._on_project_op_failure(e, "Adding Project"))

    def _remove_project(self):
        path = self._get_selected_project_path()
        if not path: return
        # ... (código existente) ...
        pass
        
    def _update_project(self):
        path = self._get_selected_project_path()
        if not path:
            return  # Si no hay ruta, no hacemos nada.

        project = self.project_manager.get_project_by_path(path)
        if project:
            self._run_async_task(
                self.project_manager.update_project,
                path,
                project['branch'],
                on_success=self._on_project_updated_success,
                on_failure=lambda e: self._on_project_op_failure(e, self.t("Updating Project Operation Name"))
            )

    def _scan_base_folder(self):
        folder = filedialog.askdirectory(parent=self.master, initialdir=self.config_manager.get_base_folder())
        if folder:
            self.config_manager.set_base_folder(folder)
            self.project_manager.set_base_folder(folder)
            self.update_base_folder_label()
            self._run_async_task(self.project_manager.scan_base_folder,
                                 on_success=self._on_scan_complete_success,
                                 on_failure=lambda e: self._on_project_op_failure(e, "Scanning Folder"))

    def _push_project(self):
        path = self._get_selected_project_path()
        if path: self._run_async_task(self.project_manager.push_project, path, on_success=self._on_project_pushed_success, on_failure=lambda e: self._on_project_op_failure(e, "Pushing Project"))

    def _refresh_all_statuses(self):
        self._run_async_task(self.project_manager.refresh_project_statuses, on_success=self._on_refresh_status_complete_success, on_failure=lambda e: self._on_project_op_failure(e, "Refreshing Statuses"))

    def _show_help(self):
        messagebox.showinfo("Help", "Help content will be added here.")
    
    def _perform_commit(self):
        from installerpro.core import security_analyzer
        selected_path = self._get_selected_project_path()
        if not selected_path: return
        files_to_commit = [path for path, staged in self.staged_files.items() if staged]
        if not files_to_commit:
            messagebox.showwarning(self.t("Commit Warning Title"), self.t("No files staged for commit message"))
            return
        commit_message = self.commit_message_text.get("1.0", tk.END).strip()
        if not commit_message:
            messagebox.showwarning(self.t("Commit Warning Title"), self.t("Commit message cannot be empty message"))
            return

        findings = security_analyzer.scan_files_for_secrets(files_to_commit, selected_path)
        if findings:
            details = "\n".join([f"- {f['file']}:{f['line']} ({f['type']})" for f in findings])
        
            # --- LÍNEAS CORREGIDAS CON TRADUCCIÓN ---
            title = self.t("Security Warning Title", fallback="Security Warning")
            message = self.t("Security warning message", details=details, fallback=f"Potential secrets detected:\n{details}\n\nProceed anyway?")
        
            if not messagebox.askyesno(title, message, parent=self.master):
                return
        
        self._run_async_task(self.project_manager.commit_project_changes, selected_path, files_to_commit, commit_message,
            on_success=self._on_commit_success,
            on_failure=lambda e: self._on_project_op_failure(e, "Commit"))

    def _on_commit_success(self, result):
        messagebox.showinfo("Success", "Commit successful.")
        self.commit_message_text.delete("1.0", tk.END)
        self._on_project_select()
    
    def _on_project_added_success(self, new_project):
        self._load_projects_into_treeview()

    def _on_project_op_failure(self, error, op_name):
        messagebox.showerror("Error", f"Error during {op_name}:\n{error}")
        self._load_projects_into_treeview()
        
    def _on_project_updated_success(self, result):
        self._load_projects_into_treeview()
    
    def _on_project_pushed_success(self, result):
        self._load_projects_into_treeview()
        
    def _on_scan_complete_success(self, count):
        self._load_projects_into_treeview()
        messagebox.showinfo("Scan Complete", f"Found {count} new projects.")
        
    def _on_refresh_status_complete_success(self, _):
        self._load_projects_into_treeview()

    def run(self):
        self.master.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = InstallerProApp(root)
    app.run()