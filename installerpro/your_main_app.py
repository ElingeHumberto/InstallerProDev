# installerpro/your_main_app.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import os
import sys # Necesario para manipular sys.path
import threading
from queue import Queue
import logging

# --- GESTIÓN DE SYS.PATH PARA IMPORTACIONES DE PAQUETES ---
current_script_dir = os.path.abspath(os.path.dirname(__file__))
project_root_dir = os.path.abspath(os.path.join(current_script_dir, '..'))
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)
# --- FIN GESTIÓN DE SYS.PATH ---

# Importa tus módulos personalizados actualizados
import installerpro.core.logging_config as logging_config
import installerpro.i18n as i18n
from installerpro.config import ConfigManager
from installerpro.core.git_operations import GitOperationError # Ahora se usa la excepción de git_operations
from installerpro.core.project_manager import ProjectManager, ProjectNotFoundError

# Configura el logging al inicio de la aplicación
logger = logging_config.setup_logging() 

# Variable global para la función de traducción, para conveniencia en toda la aplicación
_ = None

class TextHandler(logging.Handler):
    """
    Un manejador de logging que envía registros a un widget Text o ScrolledText de Tkinter.
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.configure(state='disabled') # Deshabilitar edición directa por el usuario

        _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        _PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..')) # Esto te da C:\Workspace\InstallerProDev

    def emit(self, record):
        msg = self.format(record)
        # Usar after para asegurar que la actualización de la UI se haga en el hilo principal
        self.text_widget.after(0, self.update_text_widget, msg)

    def update_text_widget(self, msg):
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END) # Auto-scroll
        self.text_widget.configure(state='disabled')


class InstallerProApp:
    def __init__(self, master):
        self.master = master
        self.master.withdraw() # Oculta la ventana principal hasta que todo esté listo

        self.logger = logging.getLogger(__name__)

        # 1. Calcular rutas del proyecto y locales AHORA que el logger está configurado
        _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) # C:\Workspace\InstallerProDev\installerpro
        _PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..')) # C:\Workspace\InstallerProDev
        # --- RUTA DE LOCALES AHORA QUE 'utils' ESTÁ DENTRO DE 'InstallerProDev' ---
        self.locales_dir = os.path.join(_PROJECT_ROOT, 'utils', 'locales') # C:\Workspace\InstallerProDev\utils\locales
        # --- FIN RUTA DE LOCALES ---
        # --- FIN MODIFICACIÓN ---
        self.logger.debug(f"Calculated locales_dir in InstallerProApp: {self.locales_dir}")

        # 2. Inicializar el gestor de configuración
        self.config_manager = ConfigManager()

        # Cola para comunicación entre hilos (para operaciones asíncronas)
        self.task_queue = Queue() 

        # 3. Configurar el traductor global (tu i18n)
        global _
        _ = i18n.t # Asignamos la función de traducción para un uso más cómodo

        # Pasar la ruta de locales al módulo i18n
        i18n.set_locales_dir(self.locales_dir)

        # Cargar el idioma desde la configuración y aplicarlo
        initial_lang = self.config_manager.get_language() or i18n.get_current_language()
        i18n.set_language(initial_lang, self.locales_dir) # Pasar self.locales_dir aquí

        # Obtener la carpeta base después de configurar el idioma para posibles mensajes
        initial_base_folder = self.config_manager.get_base_folder()
        os.makedirs(initial_base_folder, exist_ok=True) # Asegura que la carpeta base exista
        self.logger.info(_("Base folder created: {folder}", folder=initial_base_folder)) # Traducido

        # 4. Inicializar el ProjectManager
        self.project_manager = ProjectManager(initial_base_folder, config_manager=self.config_manager) 
        
        # Configurar y mostrar UI
        self._setup_ui()
        self.update_ui_texts() # Llama a esta función para establecer todos los textos iniciales
        self._load_projects_into_treeview() # Carga los proyectos al inicio

        # Iniciar el procesamiento de la cola de tareas (ahora es una función callable)
        self.master.after(100, self._process_task_queue)

        self.logger.info(_("App Title") + _(" started.")) 
        self.master.deiconify() # Muestra la ventana principal una vez que todo esté listo


    def _populate_language_menu(self):
        """Popula el menú de idiomas con las opciones disponibles y maneja la selección única."""
        self.lang_menu.delete(0, tk.END) # Limpia el menú actual

        # Crea UNA StringVar para que todos los radio buttons compartan
        if not hasattr(self, 'selected_language_var'):
            self.selected_language_var = tk.StringVar()
        
        # OBTENEMOS LOS LENGUAJES USANDO LA RUTA DE LOCALES CONFIGURADA EN I18N
        available_lang_codes = i18n.get_available_languages() 
        
        for lang_code in available_lang_codes:
            lang_name_key = f"language_option.{lang_code}"
            display_name = i18n.t(lang_name_key, lang=lang_code) 
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
        # <--- ESTAS LÍNEAS DEBEN ESTAR INDENTADAS CON 4 ESPACIOS (o un tab) RESPECTO A 'def update_ui_texts'
        self.master.title(_("App Title"))

        # Eliminar y recrear las entradas del menú principal para asegurar la actualización de texto
        self.menubar.delete(0, tk.END) # Eliminar todas las entradas existentes
        self.menubar.add_cascade(menu=self.view_menu, label=_("View Menu"))

        # Eliminar y recrear las entradas del submenú de vista
        self.view_menu.delete(0, tk.END)
        self.view_menu.add_cascade(menu=self.lang_menu, label=_("Language Menu"))
        self._populate_language_menu() # Esto repopulará el menú de idioma con los nuevos textos

        # Actualizar textos de las pestañas
        self.notebook.tab(self.projects_tab, text=_("Projects Tab Title"))
        self.notebook.tab(self.logs_tab, text=_("Logs Tab Title"))

        self.tree.heading("name", text=_("Project Name Column"))
        self.tree.heading("path", text=_("Local Path Column"))
        self.tree.heading("url", text=_("Repository URL Column"))
        self.tree.heading("branch", text=_("Branch Column"))
        self.tree.heading("status", text=_("Status Column"))

        self.add_button.config(text=_("button.add"))
        self.edit_button.config(text=_("button.edit"))
        self.remove_button.config(text=_("button.remove"))
        self.update_button.config(text=_("button.update"))
        self.scan_button.config(text=_("button.scan_base_folder"))
        self.push_button.config(text=_("button.push"))
        self.refresh_status_button.config(text=_("button.refresh_status"))
        self.help_button.config(text=_("button.help"))

        self.update_base_folder_label()
        self._load_projects_into_treeview()
        logger.info("UI texts updated successfully.")


    def change_language(self, lang_code):
        """Cambia el idioma de la aplicación."""
        # <--- ESTAS LÍNEAS TAMBIÉN DEBEN ESTAR INDENTADAS CON 4 ESPACIOS RESPECTO A 'def change_language'
        old_lang = i18n.get_current_language()
        if self.config_manager.set_language(lang_code):
            i18n.set_language(lang_code, self.locales_dir)
            self.update_ui_texts()
            self.selected_language_var.set(lang_code)
            messagebox.showinfo(
                _("Language Changed"),
                _("Application language changed to: {lang}", lang=i18n.t(f"language_option.{lang_code}", lang=lang_code))
            )
            logger.info(f"Language changed from {old_lang} to {lang_code}.")
        else:
            messagebox.showerror(
                _("Error"),
                _("Language '{lang}' not found in loaded translations.", lang=lang_code)
            )
            logger.error(f"Failed to change language to {lang_code}.")

    def _setup_ui(self):
        """Configura los elementos estáticos de la interfaz de usuario."""
        self.master.geometry("1024x768")
        self.master.minsize(600, 400) # Establecer un tamaño mínimo

        # Inicializar menubar y submenús. No los configuramos aquí para que update_ui_texts los maneje.
        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)
        
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.lang_menu = tk.Menu(self.view_menu, tearoff=0)

        # Crear el Notebook (sistema de pestañas)
        self.notebook = ttk.Notebook(self.master)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Pestaña de Proyectos
        self.projects_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.projects_tab, text=_("Projects Tab Title")) # Texto inicial, se actualizará

        # Configuración del Treeview (ahora dentro de projects_tab)
        self.tree = ttk.Treeview(self.projects_tab, columns=("name", "path", "url", "branch", "status"), show="headings")
        self.tree.heading("name", text=_("Project Name Column"))
        self.tree.heading("path", text=_("Local Path Column"))
        self.tree.heading("url", text=_("Repository URL Column"))
        self.tree.heading("branch", text=_("Branch Column"))
        self.tree.heading("status", text=_("Status Column"))

        self.tree.column("name", width=150)
        self.tree.column("path", width=250)
        self.tree.column("url", width=250)
        self.tree.column("branch", width=100)
        self.tree.column("status", width=100)

        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=10)

        # Bind para doble clic en el Treeview para editar
        self.tree.bind("<Double-1>", self._edit_project_on_double_click)

        self.buttons_frame = ttk.Frame(self.projects_tab)
        self.buttons_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        self.add_button = ttk.Button(self.buttons_frame, text=_("button.add"), command=self._add_project)
        self.add_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.edit_button = ttk.Button(self.buttons_frame, text=_("button.edit"), command=self._edit_project)
        self.edit_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.remove_button = ttk.Button(self.buttons_frame, text=_("button.remove"), command=self._remove_project)
        self.remove_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.update_button = ttk.Button(self.buttons_frame, text=_("button.update"), command=self._update_project)
        self.update_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.scan_button = ttk.Button(self.buttons_frame, text=_("button.scan_base_folder"), command=self._scan_base_folder)
        self.scan_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.push_button = ttk.Button(self.buttons_frame, text=_("button.push"), command=self._push_project)
        self.push_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.refresh_status_button = ttk.Button(self.buttons_frame, text=_("button.refresh_status"), command=self._refresh_all_statuses)
        self.refresh_status_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.help_button = ttk.Button(self.buttons_frame, text=_("button.help"), command=self._show_help)
        self.help_button.pack(side=tk.RIGHT, padx=5, pady=5)

        self.base_folder_label = ttk.Label(self.projects_tab, text="")
        self.base_folder_label.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 5))
        self.update_base_folder_label()

        # Pestaña de Registros
        self.logs_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.logs_tab, text=_("Logs Tab Title")) # Texto inicial, se actualizará

        self.log_text_widget = scrolledtext.ScrolledText(self.logs_tab, wrap=tk.WORD, state='disabled', font=('Courier New', 9))
        self.log_text_widget.pack(fill=tk.BOTH, expand=True)

        # Conectar el manejador de logging al widget de texto
        self.log_handler = TextHandler(self.log_text_widget)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.log_handler.setFormatter(formatter)
        logger.addHandler(self.log_handler)
        # Asegurarse de que el logger raíz también envíe a nuestro manejador si queremos ver todo el log
        logging.getLogger().addHandler(self.log_handler) 
        # Establecer el nivel del manejador para capturar más logs
        self.log_handler.setLevel(logging.INFO) # Puedes cambiar a logging.DEBUG para más detalle

    def _populate_language_menu(self): # <--- ¡Asegúrate de que esta definición exista y esté aquí!
        """Popula el menú de idiomas con las opciones disponibles y maneja la selección única."""
        self.lang_menu.delete(0, tk.END) # Limpia el menú actual

        if not hasattr(self, 'selected_language_var'):
            self.selected_language_var = tk.StringVar()
        
        available_lang_codes = i18n.get_available_languages()
        
        for lang_code in available_lang_codes:
            lang_name_key = f"language_option.{lang_code}"
            display_name = i18n.t(lang_name_key, lang=lang_code) 
            if display_name == lang_name_key: # Fallback si no hay traducción
                display_name = lang_code.upper()

            self.lang_menu.add_radiobutton(
                label=display_name, 
                command=lambda lc=lang_code: self.change_language(lc),
                variable=self.selected_language_var, 
                value=lang_code 
            )
        
        self.selected_language_var.set(i18n.get_current_language())

    def update_ui_texts(self):
        """Actualiza todos los textos de la interfaz de usuario en el idioma actual."""
        self.master.title(_("App Title")) 

        # Eliminar y recrear las entradas del menú principal para asegurar la actualización de texto
        self.menubar.delete(0, tk.END) # Eliminar todas las entradas existentes
        self.menubar.add_cascade(menu=self.view_menu, label=_("View Menu")) 
        
        # Eliminar y recrear las entradas del submenú de vista
        self.view_menu.delete(0, tk.END)
        self.view_menu.add_cascade(menu=self.lang_menu, label=_("Language Menu")) 
        self._populate_language_menu() # Esto repopulará el menú de idioma con los nuevos textos

        # Actualizar textos de las pestañas
        # Importante: los textos de las pestañas se establecen al añadirlas, 
        # para actualizarlas se puede hacer así:
        self.notebook.tab(self.projects_tab, text=_("Projects Tab Title"))
        self.notebook.tab(self.logs_tab, text=_("Logs Tab Title"))

        self.tree.heading("name", text=_("Project Name Column"))
        self.tree.heading("path", text=_("Local Path Column"))
        self.tree.heading("url", text=_("Repository URL Column"))
        self.tree.heading("branch", text=_("Branch Column"))
        self.tree.heading("status", text=_("Status Column"))

        self.add_button.config(text=_("button.add"))
        self.edit_button.config(text=_("button.edit")) 
        self.remove_button.config(text=_("button.remove")) 
        self.update_button.config(text=_("button.update")) 
        self.scan_button.config(text=_("button.scan_base_folder")) 
        self.push_button.config(text=_("button.push")) 
        self.refresh_status_button.config(text=_("button.refresh_status")) 
        self.help_button.config(text=_("button.help")) 

        self.update_base_folder_label()
        self._load_projects_into_treeview() # Para que el texto "No projects found" se traduzca
        logger.info("UI texts updated successfully.")
        
    def _process_task_queue(self):
        """Procesa elementos de la cola de tareas."""
        try:
            while not self.task_queue.empty(): 
                callback, args, kwargs = self.task_queue.get_nowait() 
                callback(*args, **kwargs)
                self.task_queue.task_done()
        except Exception as e: 
            logger.error(f"Error processing task from queue: {e}")
            # No hay necesidad de pass, el error ya se loguea
        finally:
            self.master.after(100, self._process_task_queue) # Vuelve a programar la verificación

    def update_base_folder_label(self):
        """Actualiza la etiqueta que muestra la carpeta base actual."""
        current_base_folder = self.config_manager.get_base_folder()
        label_text = _("Base folder created: {path}", path=current_base_folder)
        self.base_folder_label.config(text=label_text)


    def change_language(self, lang_code):
        """Cambia el idioma de la aplicación."""
        old_lang = i18n.get_current_language()
        if self.config_manager.set_language(lang_code): # Guarda la preferencia de idioma
            i18n.set_language(lang_code) # Cambia el idioma en el traductor
            self.update_ui_texts()
            self.selected_language_var.set(lang_code) # Actualizar la StringVar compartida
            messagebox.showinfo(
                _("Language Changed"),
                _("Application language changed to: {lang}", lang=i18n.t(f"language_option.{lang_code}", lang=lang_code))
            )
            logger.info(f"Language changed from {old_lang} to {lang_code}.")
        else:
            messagebox.showerror(
                _("Error"),
                _("Language '{lang}' not found in loaded translations.", lang=lang_code)
            )
            logger.error(f"Failed to change language to {lang_code}.")


    def _load_projects_into_treeview(self):
        """Carga los proyectos desde el ProjectManager al Treeview."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        projects = self.project_manager.get_projects()
        if not projects:
            self.tree.insert("", tk.END, text="", values=(
                _("No Projects Found"), "", "", "", ""
            ))
            logger.info("No projects to display in treeview.")
            return

        for project in projects:
            status_display = _(project.get('status', 'Unknown Status Value')) # Traduce el estado
            self.tree.insert("", tk.END,
                                 values=(project['name'], project['local_path'], project['repo_url'], project['branch'], status_display),
                                 tags=("deleted" if project.get('deleted') else "normal",))
        self.tree.tag_configure("deleted", foreground="red")
        logger.info(f"Loaded {len(projects)} projects into treeview.")

    def _get_selected_project_path(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning(
                _("Selection Required"),
                _("Please select a project from the list.")
            )
            logger.warning("No project selected for operation.")
            return None
        return self.tree.item(selected_item, 'values')[1] # Retorna la ruta local (segunda columna)

    def _get_selected_project_data(self):
        selected_path = self._get_selected_project_path()
        if selected_path:
            return self.project_manager.get_project_by_path(selected_path)
        return None

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
        dialog = AddProjectDialog(self.master, t_func=_, base_folder=self.config_manager.get_base_folder()) # Pasar _ y base_folder
        if dialog.exec_():
            name = dialog.result['name']
            repo_url = dialog.result['repo_url']
            local_path_full = dialog.result['local_path_full'] 
            branch = dialog.result['branch']

            messagebox.showinfo(
                _("Adding Project"),
                _("Adding project progress", project=name)
            )
            logger.info(f"Starting async add project for '{name}'...")
            self._run_async_task(
                self.project_manager.add_project,
                name, repo_url, local_path_full, branch, # Posicionales ANTES de keyword arguments
                callback_on_success=self._on_project_added_success,
                callback_on_failure=lambda e: self._on_project_op_failure(e, _("Adding Project"))
            )

    def _edit_project(self):
        project_data = self._get_selected_project_data()
        if not project_data:
            return

        dialog = AddProjectDialog(self.master, t_func=_, base_folder=self.config_manager.get_base_folder(), project_data=project_data)
        if dialog.exec_():
            new_name = dialog.result['name']
            new_repo_url = dialog.result['repo_url']
            new_local_path_full = dialog.result['local_path_full'] 
            new_branch = dialog.result['branch']

            # Pasamos la ruta original para que el ProjectManager sepa qué proyecto actualizar
            original_path = project_data['local_path']

            messagebox.showinfo(
                _("Editing Project"),
                _("Editing project progress", project=new_name)
            )
            logger.info(f"Starting async edit project for '{new_name}' (original path: {original_path})...")
            self._run_async_task(
                self.project_manager.edit_project,
                original_path, new_name, new_repo_url, new_local_path_full, new_branch, # Posicionales ANTES de keyword arguments
                callback_on_success=self._on_project_edited_success,
                callback_on_failure=lambda e: self._on_project_op_failure(e, _("Editing Project"))
            )

    def _edit_project_on_double_click(self, event):
        """Handler para doble clic en el Treeview para editar un proyecto."""
        self._edit_project()


    def _remove_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project:
            messagebox.showerror(_("Error"), _("Selected project data not found in configuration."))
            logger.error(f"Attempted to remove project not found in manager: {selected_path}")
            return

        # Opciones para eliminar: soft delete o physical delete
        confirm_soft_delete = messagebox.askyesno(
            _("Confirm Remove"),
            _("Are you sure you want to mark this project as deleted? It will not be removed from disk. Select 'No' to physically remove it.")
        )
        
        if confirm_soft_delete:
            messagebox.showinfo(_("Removing Project"), _("Removing project progress", project=project.get('name', 'Unnamed Project')))
            logger.info(f"Starting async soft remove project for '{project.get('name')}'...")
            self._run_async_task(
                self.project_manager.remove_project,
                selected_path, permanent=False, # Posicionales ANTES de keyword arguments
                callback_on_success=lambda _: self._on_project_removed_success(project.get('name', 'Unnamed Project')),
                callback_on_failure=lambda e: self._on_project_op_failure(e, _("Removing Project"))
            )
        elif confirm_soft_delete is False: # El usuario seleccionó 'No' para soft delete, lo que implica physical delete
            confirm_physical_delete = messagebox.askyesno(
                _("Confirm Physical Remove"),
                _("WARNING: Are you absolutely sure you want to PERMANENTLY remove the project folder '{path}' from disk? This action cannot be undone.", path=selected_path)
            )
            if confirm_physical_delete:
                messagebox.showinfo(_("Removing Project"), _("Removing project progress", project=project.get('name', 'Unnamed Project')))
                logger.info(f"Starting async physical remove project for '{project.get('name')}'...")
                self._run_async_task(
                    self.project_manager.remove_project,
                    selected_path, permanent=True, # Posicionales ANTES de keyword arguments
                    callback_on_success=lambda _: self._on_project_physically_removed_success(project.get('name', 'Unnamed Project')),
                    callback_on_failure=lambda e: self._on_project_op_failure(e, _("Physical Removing Project"))
                )
        else: # El usuario canceló la primera pregunta
            logger.info("Project removal cancelled by user.")
            messagebox.showinfo(_("Action Cancelled"), _("Project removal cancelled."))

    def _update_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project:
            messagebox.showerror(_("Error"), _("Selected project data not found in configuration."))
            logger.error(f"Attempted to update project not found in manager: {selected_path}")
            return
        
        messagebox.showinfo(
            _("Updating Project Message"),
            _("Updating project progress", project=project.get('name', 'Unnamed Project'))
        )
        logger.info(f"Starting async update project for '{project.get('name')}' (pull)...")
        self._run_async_task(
            self.project_manager.update_project,
            selected_path, do_pull=True, # Posicionales ANTES de keyword arguments
            callback_on_success=self._on_project_updated_success, 
            callback_on_failure=lambda e: self._on_project_op_failure(e, _("Updating Project"))
        )

    def _scan_base_folder(self):
        current_base_folder = self.config_manager.get_base_folder()
        folder_selected = filedialog.askdirectory(
            parent=self.master,
            initialdir=current_base_folder,
            title=_("Select Base Folder Title")
        )
        if folder_selected:
            try:
                self.config_manager.set_base_folder(folder_selected)
                self.project_manager.set_base_folder(folder_selected) 
                self.update_base_folder_label()

                messagebox.showinfo(
                    _("Scanning Base Folder"),
                    _("Scanning base folder progress", folder=folder_selected)
                )
                logger.info(f"Starting async scan base folder for '{folder_selected}'...")
                self._run_async_task(
                    self.project_manager.scan_base_folder,
                    callback_on_success=self._on_scan_complete_success,
                    callback_on_failure=lambda e: self._on_project_op_failure(e, _("Scan Base Folder")),
                )
            except Exception as e:
                messagebox.showerror(
                    _("Scan Error"),
                    _("An unexpected error occurred during scanning: {error}", error=str(e))
                )
                logger.critical(f"Unexpected error during _scan_base_folder setup: {e}")
        else:
            messagebox.showinfo(
                _("Selection Canceled"),
                _("Base folder selection cancelled message")
            )
            logger.info("Base folder selection cancelled.")

    def _push_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project:
            messagebox.showerror(_("Error"), _("Selected project data not found in configuration."))
            logger.error(f"Attempted to push project not found in manager: {selected_path}")
            return
        
        messagebox.showinfo(
            _("Pushing Project Message"),
            _("Pushing project progress", project=project.get('name', 'Unnamed Project'))
        )
        logger.info(f"Starting async push project for '{project.get('name')}'...")
        self._run_async_task(
            self.project_manager.push_project,
            selected_path, # Posicional antes de keyword arguments
            callback_on_success=self._on_project_pushed_success, 
            callback_on_failure=lambda e: self._on_project_op_failure(e, _("Pushing Project"))
        )

    def _refresh_all_statuses(self):
        """Refreshes the Git status of all projects asynchronously."""
        messagebox.showinfo(
            _("Refreshing Statuses"),
            _("Refreshing all project statuses...")
        )
        logger.info("Starting async refresh of all project statuses.")
        self._run_async_task(
            self.project_manager.refresh_project_statuses,
            callback_on_success=self._on_refresh_status_complete_success, # No necesita argumentos si el ProjectManager maneja el conteo
            callback_on_failure=lambda e: self._on_project_op_failure(e, _("Refresh Statuses")),
        )

    def _show_help(self):
        help_title = _("help.title")
        help_content = _("help.content")
        messagebox.showinfo(help_title, help_content)
        logger.info("Help dialog shown.")

    # Callbacks para operaciones asíncronas
    def _on_project_added_success(self, project_data):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            _("Success"),
            _("Project Added And Cloned Success", project=project_data['name'], path=project_data['local_path'])
        )
        logger.info(f"Successfully added project '{project_data['name']}'.")

    def _on_project_edited_success(self, project_data):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            _("Success"),
            _("Project Edited Success", project=project_data['name'])
        )
        logger.info(f"Successfully edited project '{project_data['name']}'.")

    def _on_project_op_failure(self, error, op_name="Operation"):
        messagebox.showerror(
            _("Error"),
            _("An error occurred during {op_name}: {error_message}", op_name=op_name, error_message=str(error))
        )
        logger.error(f"Failed during {op_name}: {error}")
        self._load_projects_into_treeview() # Refrescar por si el estado cambió a Error

    def _on_project_removed_success(self, project_name):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            _("Project Marked as Deleted"),
            _("Project Marked as Deleted", project=project_name)
        )
        logger.info(f"Project '{project_name}' soft-deleted.")

    def _on_project_physically_removed_success(self, project_name):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            _("Project Physically Removed"),
            _("Project Physically Removed Success", project=project_name)
        )
        logger.info(f"Project '{project_name}' physically removed.")

    def _on_project_updated_success(self, pull_result):
        self._load_projects_into_treeview()
        if pull_result == "Up-to-date":
            messagebox.showinfo(
                _("Update Complete"),
                _("Project is already up-to-date.")
            )
        else:
            messagebox.showinfo(
                _("Update Complete"),
                _("Project Updated Success")
            )
        logger.info(f"Project updated (pulled) successfully. Result: {pull_result}")

    def _on_project_pushed_success(self, push_result):
        self._load_projects_into_treeview()
        if push_result == "Up-to-date (Push)":
            messagebox.showinfo(
                _("Push Complete"),
                _("Project is already up-to-date (no changes to push).")
            )
        else:
            messagebox.showinfo(
                _("Push Complete"),
                _("Project Pushed Success")
            )
        logger.info(f"Project pushed successfully. Result: {push_result}")

    def _on_scan_complete_success(self, new_projects_count):
        self._load_projects_into_treeview()
        messagebox.showinfo(
            _("Scan Complete"),
            _("Found {count} new projects.", count=new_projects_count)
        )
        logger.info(f"Scan complete. Found {new_projects_count} new projects.")
        
    def _on_refresh_status_complete_success(self, count=None): # Ajustar para aceptar argumento de conteo o None
        self._load_projects_into_treeview()
        messagebox.showinfo(
            _("Status Refresh Complete"),
            _("All project statuses have been refreshed.")
        )
        logger.info("All project statuses refreshed successfully.")

    def run(self):
        self.master.mainloop()


# --- CLASE ADDPROJECTDIALOG (AHORA AUTOCONTENIDA EN ESTE ARCHIVO) ---
class AddProjectDialog(tk.Toplevel):
    def __init__(self, parent, t_func, base_folder, project_data=None):
        super().__init__(parent)
        self.parent = parent
        self.t = t_func 
        self.base_folder = base_folder # Carpeta base del InstallerPro
        self.project_data = project_data # Diccionario si estamos editando
        self.transient(parent)
        self.grab_set()
        
        self.result = None

        self._create_widgets()
        if self.project_data:
            self.title(self.t("Edit Project Title"))
            self._populate_fields()
            self.ok_button.config(text=self.t("Save Button")) # Cambiar texto del botón
        else:
            self.title(self.t("Add Project Title"))
            self.ok_button.config(text=self.t("Add Button")) # Reafirmar texto del botón

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
        # Si no estamos editando, pre-llenar con la carpeta base + nombre por defecto
        if not self.project_data:
            self.local_path_var.set(os.path.join(self.base_folder, self.t("New Project Default Name"))) 
        self.name_entry.bind("<KeyRelease>", self._update_local_path_on_name_change)


        ttk.Label(frame, text=self.t("Repository URL Label")).grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.repo_url_entry = ttk.Entry(frame, width=40)
        self.repo_url_entry.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        ttk.Label(frame, text=self.t("Branch Optional Label")).grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.branch_entry = ttk.Entry(frame, width=40)
        self.branch_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        self.ok_button = ttk.Button(button_frame, command=self._on_ok) # El texto se asignará en __init__
        self.ok_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=self.t("Cancel Button"), command=self._on_cancel).pack(side=tk.LEFT, padx=5)

    def _populate_fields(self):
        """Pre-llena los campos del formulario con los datos del proyecto existente."""
        self.name_entry.insert(0, self.project_data.get('name', ''))
        self.local_path_var.set(self.project_data.get('local_path', ''))
        self.repo_url_entry.insert(0, self.project_data.get('repo_url', ''))
        self.branch_entry.insert(0, self.project_data.get('branch', 'main')) # Default a 'main' si no está
        
        # Deshabilitar edición de ruta local si estamos editando
        # self.local_path_entry.config(state='disabled') # Opcional: si no quieres que cambie la ruta local al editar


    def _update_local_path_on_name_change(self, event=None):
        # Solo actualizar la ruta si no estamos editando un proyecto existente o si el campo de ruta local está vacío
        if not self.project_data or not self.local_path_var.get():
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
            'branch': branch if branch else 'main' # Default a 'main' si no se especifica
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
    root = tk.Tk()
    app = InstallerProApp(root)
    app.run()