# installerpro/your_main_app.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import sys # Necesario para manipular sys.path
import threading
from queue import Queue
import logging

# --- GESTIÓN DE SYS.PATH PARA IMPORTACIONES DE PAQUETES ---
# Obtener el directorio del script actual (ej. C:\Workspace\InstallerProDev\installerpro)
current_script_dir = os.path.abspath(os.path.dirname(__file__))

# Obtener el directorio padre, que es la raíz de tu proyecto (ej. C:\Workspace\InstallerProDev)
project_root_dir = os.path.abspath(os.path.join(current_script_dir, '..'))

# Añadir la raíz del proyecto a sys.path si no está ya presente.
# Esto permite que Python encuentre el paquete 'installerpro' al importar.
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)
# --- FIN GESTIÓN DE SYS.PATH ---


# Importa tus módulos personalizados
import installerpro.core.logging_config as logging_config
import installerpro.i18n as i18n
from installerpro.core.config_manager import ConfigManager
from installerpro.core.git_operations import GitOperationError
from installerpro.core.project_manager import ProjectManager, ProjectNotFoundError

# NOTA IMPORTANTE: La clase AddProjectDialog ahora está definida al final de este mismo archivo.
# Por lo tanto, NO NECESITAS importar AddProjectDialog desde otro archivo aquí.

# Configura el logging al inicio de la aplicación
logger = logging_config.setup_logging()

# Variable global para la función de traducción, para conveniencia en toda la aplicación
# Se asigna directamente aquí para que esté disponible globalmente si otros módulos la necesitan.
_ = i18n.t

class InstallerProApp:
    def __init__(self, master):
        self.master = master
        self.logger = logging.getLogger(__name__) # Logger específico para esta instancia de la aplicación

        self.master.withdraw() # Oculta la ventana principal hasta que todo esté listo

        # MUEVE LA ASIGNACIÓN DE self.t AQUÍ, ANTES DE SU PRIMER USO
        self.t = i18n.t # ¡Esto es lo que debes mover!

        # 1. Inicializar el gestor de configuración
        # La configuración se carga automáticamente en el constructor de ConfigManager
        self.config_manager = ConfigManager()

        # Obtener la carpeta base y asegurar su existencia
        initial_base_folder = os.path.abspath(self.config_manager.get_base_folder())
        os.makedirs(initial_base_folder, exist_ok=True) # Asegura que la carpeta base exista
        self.logger.info(self.t("Base folder created: {folder}", folder=initial_base_folder)) # Ahora self.t EXISTE aquí

        # 2. Inicializar el ProjectManager
        self.project_manager = ProjectManager(initial_base_folder, config_manager=self.config_manager)
        # Carga los proyectos al inicio del ProjectManager (ya se hace en su constructor)
        # self.project_manager._load_projects() # Ya se llama en el constructor de ProjectManager

        # 3. Configurar el traductor (i18n) y establecer el idioma inicial
        # La función de traducción global '_' ya está asignada arriba.
        # Ahora solo necesitas establecer el idioma inicial, self.t ya está asignado
        initial_lang_code = self.config_manager.get_language() or i18n.get_current_language()
        if not i18n.set_language(initial_lang_code): # Esto cargará las traducciones
            self.logger.warning(f"Could not set initial language to {initial_lang_code}. Defaulting to 'en'.")
            i18n.set_language("en") # Fallback a inglés si el idioma inicial falla

        # Cola para comunicación entre hilos (para operaciones asíncronas)
        self.task_queue = Queue()

        # 4. Configurar y mostrar UI
        self._setup_ui() # Configura todos los widgets de la interfaz
        self.update_ui_texts() # Actualiza los textos de todos los widgets con el idioma actual
        self._load_projects_into_treeview() # Carga los proyectos en el Treeview

        # Iniciar el procesamiento de la cola de tareas
        self.master.after(100, self._process_task_queue)

        self.logger.info(self.t("App Title") + self.t(" started."))
        self.master.deiconify() # Muestra la ventana principal una vez que todo esté listo


    def _setup_ui(self):
        """Configura los elementos estáticos de la interfaz de usuario."""
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)

        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(menu=self.view_menu, label=self.t("View Menu"))

        self.lang_menu = tk.Menu(self.view_menu, tearoff=0)
        self.view_menu.add_cascade(menu=self.lang_menu, label=self.t("Language Menu"))
        self._populate_language_menu()

        # Configuración del Treeview
        self.tree = ttk.Treeview(self.main_frame, columns=("name", "path", "url", "branch", "status"), show="headings")
        self.tree.heading("name", text=self.t("Project Name Column"))
        self.tree.heading("path", text=self.t("Local Path Column"))
        self.tree.heading("url", text=self.t("Repository URL Column"))
        self.tree.heading("branch", text=self.t("Branch Column"))
        self.tree.heading("status", text=self.t("Status Column"))

        self.tree.column("name", width=150)
        self.tree.column("path", width=250)
        self.tree.column("url", width=250)
        self.tree.column("branch", width=100)
        self.tree.column("status", width=100)

        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=10)

        self.buttons_frame = ttk.Frame(self.main_frame)
        self.buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        self.add_button = ttk.Button(self.buttons_frame, text=self.t("button.add"), command=self._add_project)
        self.add_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.remove_button = ttk.Button(self.buttons_frame, text=self.t("button.remove"), command=self._remove_project)
        self.remove_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.update_button = ttk.Button(self.buttons_frame, text=self.t("button.update"), command=self._update_project)
        self.update_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.scan_button = ttk.Button(self.buttons_frame, text=self.t("button.scan_base_folder"), command=self._scan_base_folder)
        self.scan_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.push_button = ttk.Button(self.buttons_frame, text=self.t("button.push"), command=self._push_project)
        self.push_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.refresh_status_button = ttk.Button(self.buttons_frame, text=self.t("button.refresh_status"), command=self._refresh_all_statuses)
        self.refresh_status_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.help_button = ttk.Button(self.buttons_frame, text=self.t("button.help"), command=self._show_help)
        self.help_button.pack(side=tk.RIGHT, padx=5, pady=5)

        self.base_folder_label = ttk.Label(self.main_frame, text="")
        self.base_folder_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        self.update_base_folder_label()

    def _populate_language_menu(self):
        """Popula el menú de idiomas con las opciones disponibles y maneja la selección única."""
        self.lang_menu.delete(0, tk.END) # Limpia el menú actual

        # Crea UNA StringVar para que todos los radio buttons compartan
        if not hasattr(self, 'selected_language_var'):
            self.selected_language_var = tk.StringVar()

        available_lang_codes = i18n.get_available_languages()

        for lang_code in available_lang_codes:
            lang_name_key = f"language_option.{lang_code}"
            display_name = self.t(lang_name_key, lang=lang_code)
            if display_name == lang_name_key: # Fallback si no hay traducción
                display_name = lang_code.upper()

            self.lang_menu.add_radiobutton(
                label=display_name,
                command=lambda lc=lang_code: self.change_language(lc),
                variable=self.selected_language_var, # Todos los radio buttons comparten esta variable
                value=lang_code # El valor que esta variable tomará si este botón es seleccionado
            )

        # Establece el valor inicial de la variable compartida al idioma actual
        self.selected_language_var.set(i18n.get_current_language())

    def update_ui_texts(self):
        """Actualiza todos los textos de la interfaz de usuario en el idioma actual."""
        self.master.title(self.t("App Title"))

        try:
            if hasattr(self, 'menubar') and self.menubar is not None:
                self.menubar.entryconfig(0, label=self.t("View Menu"))

                if hasattr(self, 'view_menu') and self.view_menu is not None:
                    self.view_menu.entryconfig(0, label=self.t("Language Menu"))
                else:
                    self.logger.warning("view_menu attribute not found or is None. Cannot update Language Menu text.")
            else:
                self.logger.warning("menubar attribute not found or is None. Cannot update main menu texts.")

        except Exception as e:
            self.logger.error(f"Error updating menu texts: {e}")
            # print(f"DEBUG: Tipo de excepción: {type(e).__name__}, Mensaje: '{e}'") # Comentado para limpiar la salida

        self.tree.heading("name", text=self.t("Project Name Column"))
        self.tree.heading("path", text=self.t("Local Path Column"))
        self.tree.heading("url", text=self.t("Repository URL Column"))
        self.tree.heading("branch", text=self.t("Branch Column"))
        self.tree.heading("status", text=self.t("Status Column"))

        self.add_button.config(text=self.t("button.add"))
        self.remove_button.config(text=self.t("button.remove"))
        self.update_button.config(text=self.t("button.update"))
        self.scan_button.config(text=self.t("button.scan_base_folder"))
        self.push_button.config(text=self.t("button.push"))
        self.refresh_status_button.config(text=self.t("button.refresh_status"))
        self.help_button.config(text=self.t("button.help"))

        self.update_base_folder_label()
        self._load_projects_into_treeview()
        self.logger.info("UI texts updated successfully.")

    def _process_task_queue(self):
        """Procesa elementos de la cola de tareas."""
        try:
            while not self.task_queue.empty():
                callback, args, kwargs = self.task_queue.get_nowait()
                callback(*args, **kwargs)
                self.task_queue.task_done()
        except Exception as e:
            self.logger.error(f"Error processing task from queue: {e}")
            pass
        finally:
            self.master.after(100, self._process_task_queue)

    def update_base_folder_label(self):
        """Actualiza la etiqueta que muestra la carpeta base actual."""
        current_base_folder = self.config_manager.get_base_folder()
        label_text = self.t("Base folder created: {path}", path=current_base_folder)
        self.base_folder_label.config(text=label_text)


    def change_language(self, lang_code):
        """Cambia el idioma de la aplicación."""
        old_lang = i18n.get_current_language()
        if self.config_manager.set_language(lang_code): # Guarda la preferencia de idioma
            i18n.set_language(lang_code) # Cambia el idioma en el traductor
            self.update_ui_texts()
            self.selected_language_var.set(lang_code) # Actualizar la StringVar compartida
            messagebox.showinfo(
                self.t("Language Changed"),
                self.t("Application language changed to: {lang}", lang=i18n.t(f"language_option.{lang_code}", lang=lang_code))
            )
            self.logger.info(f"Language changed from {old_lang} to {lang_code}.")
        else:
            messagebox.showerror(
                self.t("Error"),
                self.t("Language '{lang}' not found in loaded translations.", lang=lang_code)
            )
            self.logger.error(f"Failed to change language to {lang_code}.")


    def _load_projects_into_treeview(self):
        """Carga los proyectos desde el ProjectManager al Treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        projects = self.project_manager.get_projects()
        if not projects:
            self.tree.insert("", tk.END, text="", values=(
                self.t("No Projects Found"), "", "", "", ""
            ))
            self.logger.info("No projects to display in treeview.")
            return

        for project in projects:
            status_display = self.t(project.get('status', 'Unknown Status Value')) # Traduce el estado
            self.tree.insert("", tk.END,
                                values=(project['name'], project['local_path'], project['repo_url'], project['branch'], status_display),
                                tags=("deleted" if project.get('deleted') else "normal",))
        self.tree.tag_configure("deleted", foreground="red")
        self.logger.info(f"Loaded {len(projects)} projects into treeview.")

    def _get_selected_project_path(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning(
                self.t("Selection Required"),
                self.t("Please select a project from the list.")
            )
            self.logger.warning("No project selected for operation.")
            return None
        return self.tree.item(selected_item, 'values')[1]


    def _process_queue(self): # Esta función ya no se usa, la reemplaza _process_task_queue
        """Procesa los resultados de las tareas de los hilos de fondo."""
        pass

    def _run_async_task(self, target_function, *args, callback_on_success=None, callback_on_failure=None, **kwargs):
        """
        Ejecuta una función en un hilo separado y maneja los resultados/errores.
        Los args y kwargs son para la target_function.
        """
        def task_wrapper():
            try:
                result = target_function(*args, **kwargs)
                if callback_on_success:
                    self.task_queue.put((callback_on_success, (result,), {}))
            except Exception as e:
                if callback_on_failure:
                    self.task_queue.put((callback_on_failure, (e,), {}))

        thread = threading.Thread(target=task_wrapper)
        thread.daemon = True
        thread.start()

    # Métodos de acción de la UI
    def _add_project(self):
        dialog = AddProjectDialog(self, t_func=self.t, base_folder=self.config_manager.get_base_folder()) # Pasar self.t
        if dialog.exec_():
            name = dialog.result['name']
            repo_url = dialog.result['repo_url']
            local_path_full = dialog.result['local_path_full']
            branch = dialog.result['branch']

            messagebox.showinfo(
                self.t("Adding Project"),
                self.t("Adding project progress", project=name)
            )
            self.logger.info(f"Starting async add project for '{name}'...")
            self._run_async_task(
                self.project_manager.add_project,
                name, repo_url, local_path_full, branch, # Posicionales ANTES de keyword arguments
                callback_on_success=self._on_project_added_success,
                callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Adding Project"))
            )

    def _remove_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project:
            messagebox.showerror(self.t("Error"), self.t("Selected project data not found in configuration."))
            self.logger.error(f"Attempted to remove project not found in manager: {selected_path}")
            return

        confirm_soft_delete = messagebox.askyesno(
            self.t("Confirm Remove"),
            self.t("Are you sure you want to mark this project as deleted? It will not be removed from disk. Select 'No' to physically remove it.")
        )

        if confirm_soft_delete:
            messagebox.showinfo(self.t("Removing Project"), self.t("Removing project progress", project=project.get('name', 'Unnamed Project')))
            self.logger.info(f"Starting async soft remove project for '{project.get('name')}'...")
            self._run_async_task(
                self.project_manager.remove_project,
                selected_path, permanent=False,
                callback_on_success=lambda _: self._on_project_removed_success(project.get('name', 'Unnamed Project')),
                callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Removing Project"))
            )
        elif confirm_soft_delete is False:
            confirm_physical_delete = messagebox.askyesno(
                self.t("Confirm Physical Remove"),
                self.t("WARNING: Are you absolutely sure you want to PERMANENTLY remove the project folder '{path}' from disk? This action cannot be undone.", path=selected_path)
            )
            if confirm_physical_delete:
                messagebox.showinfo(self.t("Removing Project"), self.t("Removing project progress", project=project.get('name', 'Unnamed Project')))
                self.logger.info(f"Starting async physical remove project for '{project.get('name')}'...")
                self._run_async_task(
                    self.project_manager.remove_project,
                    selected_path, permanent=True,
                    callback_on_success=lambda _: self._on_project_physically_removed_success(project.get('name', 'Unnamed Project')),
                    callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Physical Removing Project"))
                )
        else:
            self.logger.info("Project removal cancelled by user.")
            messagebox.showinfo(self.t("Action Cancelled"), self.t("Project removal cancelled."))

    def _update_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project:
            messagebox.showerror(self.t("Error"), self.t("Selected project data not found in configuration."))
            self.logger.error(f"Attempted to update project not found in manager: {selected_path}")
            return

        messagebox.showinfo(
            self.t("Updating Project Message"),
            self.t("Updating project progress", project=project.get('name', 'Unnamed Project'))
        )
        self.logger.info(f"Starting async update project for '{project.get('name')}' (pull)...")
        self._run_async_task(
            self.project_manager.update_project,
            selected_path, do_pull=True,
            callback_on_success=self._on_project_updated_success,
            callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Updating Project"))
        )

    def _scan_base_folder(self):
        current_base_folder = self.config_manager.get_base_folder()
        folder_selected = filedialog.askdirectory(
            parent=self.master,
            initialdir=current_base_folder,
            title=self.t("Select Base Folder Title")
        )
        if folder_selected:
            try:
                self.config_manager.set_base_folder(folder_selected)
                self.project_manager.set_base_folder(folder_selected)
                self.update_base_folder_label()

                messagebox.showinfo(
                    self.t("Scanning Base Folder"),
                    self.t("Scanning base folder progress", folder=folder_selected)
                )
                self.logger.info(f"Starting async scan base folder for '{folder_selected}'...")
                self._run_async_task(
                    self.project_manager.scan_base_folder,
                    callback_on_success=self._on_scan_complete_success,
                    callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Scan Base Folder")),
                )
            except Exception as e:
                messagebox.showerror(
                    self.t("Scan Error"),
                    self.t("An unexpected error occurred during scanning: {error}", error=str(e))
                )
                self.logger.critical(f"Unexpected error during _scan_base_folder setup: {e}")
        else:
            messagebox.showinfo(
                self.t("Selection Canceled"),
                self.t("Base folder selection cancelled message")
            )
            self.logger.info("Base folder selection cancelled.")

    def _push_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project:
            messagebox.showerror(self.t("Error"), self.t("Selected project data not found in configuration."))
            self.logger.error(f"Attempted to push project not found in manager: {selected_path}")
            return

        messagebox.showinfo(
            self.t("Pushing Project Message"),
            self.t("Pushing project progress", project=project.get('name', 'Unnamed Project'))
        )
        self.logger.info(f"Starting async push project for '{project.get('name')}'...")
        self._run_async_task(
            self.project_manager.push_project,
            selected_path,
            callback_on_success=self._on_project_pushed_success,
            callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Pushing Project"))
        )

    def _refresh_all_statuses(self):
        """Refreshes the Git status of all projects asynchronously."""
        messagebox.showinfo(
            self.t("Refreshing Statuses"),
            self.t("Refreshing all project statuses...")
        )
        self.logger.info("Starting async refresh of all project statuses.")
        self._run_async_task(
            self.project_manager.refresh_project_statuses,
            callback_on_success=lambda _: self._on_refresh_status_complete_success(None),
            callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Refresh Statuses")),
        )

    def _show_help(self):
        help_title = self.t("help.title")
        help_content = self.t("help.content")
        messagebox.showinfo(help_title, help_content)
        self.logger.info("Help dialog shown.")

    # Callbacks para operaciones asíncronas
    def _on_project_added_success(self, project_data):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Success"),
            self.t("Project Added And Cloned Success", project=project_data['name'], path=project_data['local_path'])
        )
        self.logger.info(f"Successfully added project '{project_data['name']}'.")

    def _on_project_op_failure(self, error, op_name="Operation"):
        messagebox.showerror(
            self.t("Error"),
            self.t("An error occurred during {op_name}: {error_message}", op_name=op_name, error_message=str(error))
        )
        self.logger.error(f"Failed during {op_name}: {error}")
        self._load_projects_into_treeview()

    def _on_project_removed_success(self, project_name):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Project Marked as Deleted"),
            self.t("Project Marked as Deleted", project=project_name)
        )
        self.logger.info(f"Project '{project_name}' soft-deleted.")

    def _on_project_physically_removed_success(self, project_name):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Project Physically Removed"),
            self.t("Project Physically Removed Success", project=project_name)
        )
        self.logger.info(f"Project '{project_name}' physically removed.")

    def _on_project_updated_success(self, pull_result):
        self._load_projects_into_treeview()
        if pull_result == "Up-to-date":
            messagebox.showinfo(
                self.t("Update Complete"),
                self.t("Project is already up-to-date.")
            )
        else:
            messagebox.showinfo(
                self.t("Update Complete"),
                self.t("Project Updated Success")
            )
        self.logger.info(f"Project updated (pulled) successfully. Result: {pull_result}")

    def _on_project_pushed_success(self, push_result):
        self._load_projects_into_treeview()
        if push_result == "Up-to-date (Push)":
            messagebox.showinfo(
                self.t("Push Complete"),
                self.t("Project is already up-to-date (no changes to push).")
            )
        else:
            messagebox.showinfo(
                self.t("Push Complete"),
                self.t("Project Pushed Success")
            )
        self.logger.info(f"Project pushed successfully. Result: {push_result}")

    def _on_scan_complete_success(self, new_projects_count):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Scan Complete"),
            self.t("Found {count} new projects.", count=new_projects_count)
        )
        self.logger.info(f"Scan complete. Found {new_projects_count} new projects.")

    def _on_refresh_status_complete_success(self, *args):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Status Refresh Complete"),
            self.t("All project statuses have been refreshed.")
        )
        self.logger.info("All project statuses refreshed successfully.")

    def run(self):
        self.master.mainloop()


# --- CLASE ADDPROJECTDIALOG (AHORA AUTOCONTENIDA EN ESTE ARCHIVO) ---
class AddProjectDialog(tk.Toplevel):
    def __init__(self, parent, t_func, base_folder):
        super().__init__(parent)
        self.parent = parent
        self.t = t_func
        self.base_folder = base_folder
        self.transient(parent)
        self.grab_set()
        self.title(self.t("Add Project Title"))
        self.result = None

        self._create_widgets()
        self._center_window()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _create_widgets(self):
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=self.t("Project Name")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.name_entry = ttk.Entry(frame, width=40)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.local_path_var = tk.StringVar()
        ttk.Label(frame, text=self.t("Local Path Label")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.local_path_entry = ttk.Entry(frame, textvariable=self.local_path_var, width=40)
        self.local_path_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(frame, text=self.t("Browse Button"), command=self._browse_local_path).grid(row=1, column=2, padx=5, pady=5)
        self.local_path_var.set(os.path.join(self.base_folder, self.name_entry.get() or self.t("New Project Default Name")))
        self.name_entry.bind("<KeyRelease>", self._update_local_path_on_name_change)

        ttk.Label(frame, text=self.t("Repository URL Label")).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.repo_url_entry = ttk.Entry(frame, width=40)
        self.repo_url_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        ttk.Label(frame, text=self.t("Branch Optional Label")).grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.branch_entry = ttk.Entry(frame, width=40)
        self.branch_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        ttk.Button(button_frame, text=self.t("Add Button"), command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=self.t("Cancel Button"), command=self._on_cancel).pack(side=tk.LEFT, padx=5)

    def _update_local_path_on_name_change(self, event=None):
        project_name = self.name_entry.get().strip()
        if project_name:
            self.local_path_var.set(os.path.join(self.base_folder, project_name))
        else:
            self.local_path_var.set(os.path.join(self.base_folder, self.t("New Project Default Name")))

    def _browse_local_path(self):
        suggested_path = self.local_path_var.get() if self.local_path_var.get() else self.base_folder
        folder_selected = filedialog.askdirectory(
            parent=self,
            initialdir=suggested_path,
            title=self.t("Select Local Path Title")
        )
        if folder_selected:
            self.local_path_var.set(folder_selected)

    def _on_ok(self):
        name = self.name_entry.get().strip()
        repo_url = self.repo_url_entry.get().strip()
        local_path_full = self.local_path_var.get().strip()
        branch = self.branch_entry.get().strip()

        if not name or not repo_url or not local_path_full:
            messagebox.showerror(self.t("Input Error"), self.t("All fields except branch are required."))
            return

        self.result = {
            'name': name,
            'repo_url': repo_url,
            'local_path_full': local_path_full,
            'branch': branch if branch else 'main'
        }
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _center_window(self):
        self.update_idletasks()
        x = self.parent.winfo_x() + (self.parent.winfo_width() / 2) - (self.winfo_width() / 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() / 2) - (self.winfo_height() / 2)
        self.geometry(f"+{int(x)}+{int(y)}")

    def exec_(self):
        """Bloquea hasta que el diálogo se cierra y devuelve el resultado."""
        self.parent.wait_window(self)
        return self.result


# --- PUNTO DE ENTRADA PRINCIPAL ---
if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = InstallerProApp(root) # Pasar 'root' al constructor
        app.run() # Iniciar el bucle principal de Tkinter
    except Exception as e:
        logger.critical(f"Unhandled exception during application startup: {e}", exc_info=True)
        messagebox.showerror("Error de Inicio Crítico", f"Un error crítico ocurrió durante el inicio de la aplicación: {e}")
