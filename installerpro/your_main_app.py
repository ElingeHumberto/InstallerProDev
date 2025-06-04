# installerpro/your_main_app.py
import os
import sys
import logging
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk # Aunque no se usa explícitamente en este fragmento, lo mantengo si estaba en tu original
from git import Repo, GitCommandError # Mantenido por si acaso, aunque no se usa directamente en InstallerProApp
import platform
from queue import Queue, Empty
import threading

# Asegurarse de que el directorio padre de 'installerpro' esté en sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Importaciones de los módulos de tu propio proyecto
from . import i18n
from .core.config_manager import ConfigManager
from .core.project_manager import ProjectManager, ProjectNotFoundError
from .utils.git_operations import GitOperationError, is_git_repository, clone_repository, pull_repository, push_repository, get_repo_status

# --- Configuración del Logger ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Logger a nivel de módulo

# --- CONFIGURACIÓN DE RUTAS ---
base_dir = os.path.dirname(os.path.abspath(__file__)) # Directorio de your_main_app.py

try:
    import appdirs
    APP_NAME = "InstallerPro"
    APP_AUTHOR = "ElingeHumberto"
    user_config_dir = appdirs.user_config_dir(APP_NAME, APP_AUTHOR)
    user_data_dir = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
except ImportError:
    logger.warning("appdirs not installed. Falling back to simple user directories. Consider 'pip install appdirs'.")
    APP_NAME = "InstallerPro" # Asegurar que APP_NAME esté definido
    if platform.system() == "Windows":
        user_config_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), APP_NAME)
        user_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser("~")), APP_NAME)
    else:  # Linux/macOS
        user_config_dir = os.path.join(os.path.expanduser("~"), f".config/{APP_NAME}")
        user_data_dir = os.path.join(os.path.expanduser("~"), f".local/share/{APP_NAME}")

os.makedirs(user_config_dir, exist_ok=True)
os.makedirs(user_data_dir, exist_ok=True)

config_file_path = os.path.join(user_config_dir, "config.json")
projects_file_path = os.path.join(user_data_dir, "projects.json")

# --- Cargar/Crear Configuración y Proyectos ---
# Esta lógica global de carga parece ser para una configuración inicial o por defecto
# antes de que ConfigManager la tome. ConfigManager luego maneja su propio archivo.
# Voy a asumir que esta parte es para establecer los defaults que ConfigManager podría usar
# si el archivo no existe, aunque ConfigManager también tiene su propia lógica de defaults.
# Por ahora, la mantengo como en tu original.
app_config_initial_check = {"language": "en", "base_folder": ""}
if os.path.exists(config_file_path):
    try:
        with open(config_file_path, 'r', encoding='utf-8') as f:
            app_config_initial_check = json.load(f)
        logger.info(f"Initial configuration check loaded from: {config_file_path}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding config.json during initial check: {e}. Using default initial configuration.")
        app_config_initial_check = {"language": "en", "base_folder": ""} # Default
else:
    logger.info(f"Config file not found during initial check. Default initial config will be used by ConfigManager if needed.")
    # No se crea aquí, se deja a ConfigManager

project_data_initial_check = []
if os.path.exists(projects_file_path):
    try:
        with open(projects_file_path, 'r', encoding='utf-8') as f:
            project_data_initial_check = json.load(f)
        logger.info(f"Initial check: Loaded {len(project_data_initial_check)} projects structure.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding projects.json during initial check: {e}. ProjectManager will handle.")
        project_data_initial_check = []
else:
    logger.info(f"Projects file not found during initial check. ProjectManager will handle.")


# --- INICIALIZACIÓN DE INTERNACIONALIZACIÓN (i18n) ---
# Asegúrate que 'base_dir' apunte a 'installerpro/your_main_app.py'
# y 'locales' esté en 'installerpro/utils/locales'
# El project_root es 'installerpro', así que utils está en project_root/utils
locales_path = os.path.join(project_root, 'utils', 'locales') # Corregido para usar project_root si es necesario
# O si 'utils' está al mismo nivel que 'your_main_app.py' y 'core' dentro de 'installerpro':
# locales_path = os.path.join(os.path.dirname(base_dir), 'utils', 'locales')
# Según tu estructura original: from . import i18n -> 'utils' está al mismo nivel que el __init__.py de installerpro
# y 'your_main_app.py' está dentro de 'installerpro'.
# Por lo tanto, si base_dir es installerpro/your_main_app.py, entonces:
# os.path.dirname(base_dir) es installerpro/
# La ruta correcta para locales es installerpro/utils/locales
# base_dir = os.path.dirname(os.path.abspath(__file__)) # Esto es installerpro/
locales_path_corrected = os.path.join(base_dir, 'utils', 'locales') # Asume que 'utils' está dentro de 'installerpro'

i18n.set_locales_dir(locales_path_corrected)

# El idioma inicial se tomará de ConfigManager dentro de InstallerProApp.__init__
# Esta línea es un fallback o configuración muy temprana.
initial_language_early_check = app_config_initial_check.get("language", "es")
i18n.set_language(initial_language_early_check)

_ = i18n.t # Alias para la función de traducción

# --- CLASE TEXTHANDLER ---
class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.configure(state='disabled')
        self.setFormatter(logging.Formatter('%(asctime)s %(levelname)s - %(name)s - %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.after(0, self.update_text_widget, msg)

    def update_text_widget(self, msg):
        self.text_widget.configure(state='normal')
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END)
        self.text_widget.configure(state='disabled')

# --- CLASE TOOLTIP ---
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text # El texto ya debe estar traducido al pasarlo aquí
        self.tooltip_window = None
        self.id = None
        self.x = 0
        self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(500, self.show)

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def show(self):
        if self.tooltip_window or not self.text:
            return

        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + self.widget.winfo_height() + 2

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.text, background="#FFFFEA", relief="solid", borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(padx=1, pady=1)

    def hide(self):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class HelpPopup:
    """
    Muestra una pequeña ventana emergente (popup) no modal con texto de ayuda,
    activada por un clic y posicionada junto a un widget ancla.
    Se cierra con la tecla Escape o haciendo clic en su botón de cierre.
    """
    def __init__(self, anchor_widget, title, text_to_display):
        print(f"DEBUG: HelpPopup.__init__ - Ancla: {anchor_widget}, Título: '{title}', Texto: '{text_to_display[:50]}...'") # DEBUG (muestra solo parte del texto)
        self.anchor_widget = anchor_widget
        self.title = title 
        self.help_text = text_to_display
        self.popup_window = None
        if not self.help_text or not self.help_text.strip(): # Si el texto está vacío o solo espacios
            print("DEBUG: HelpPopup.__init__ - Texto de ayuda vacío. No se creará el popup.") #DEBUG
            return # No crear el popup si no hay texto que mostrar
        self._create_popup()

    # Dentro de la clase HelpPopup, reemplaza el método _create_popup con este:
    def _create_popup(self):
        print("DEBUG: HelpPopup._create_popup (ESTILO REFINADO)") # DEBUG
        if self.popup_window:
            print("DEBUG: HelpPopup._create_popup - popup_window ya existe, retornando.") # DEBUG
            return

        # --- Configuración de Estilo y Color ---
        INFO_BG_COLOR = "#F0F0F0"      # Un gris claro, sofisticado y neutro
        INFO_TEXT_COLOR = "#202020"    # Texto oscuro para buena legibilidad
        INFO_BORDER_COLOR = "#B0B0B0"  # Un borde gris medio, sutil
        CLOSE_BUTTON_FG = "#606060"    # Color del icono "X"
        CLOSE_BUTTON_ACTIVE_BG = "#DCDCDC" # Color de fondo del botón "X" al pasar el cursor/hacer clic

        x = self.anchor_widget.winfo_rootx() + self.anchor_widget.winfo_width() + 5
        y = self.anchor_widget.winfo_rooty()

        self.popup_window = tk.Toplevel(self.anchor_widget)
        print(f"DEBUG: HelpPopup._create_popup - Toplevel creado: {self.popup_window}") #DEBUG
        
        self.popup_window.wm_overrideredirect(True)
        self.popup_window.wm_geometry(f"+{x}+{y}")
        self.popup_window.attributes("-topmost", True)

        # Estilo para el frame principal del popup
        # Para el borde, en tk.Frame (no ttk) podríamos usar highlightbackground y highlightthickness
        # pero con ttk.Frame, relief y borderwidth es lo estándar.
        # El color del borde con ttk.Frame es más dependiente del tema del OS.
        s = ttk.Style()
        s.configure("InfoPopup.TFrame", background=INFO_BG_COLOR, borderwidth=1, relief="solid") 
        # Para un borde más notorio con color específico, podríamos usar un tk.Frame exterior
        # y un ttk.Frame interior, o dibujar el borde manualmente (más complejo).
        # Por ahora, mantenemos el borde simple de ttk.Frame.

        # Frame principal que contendrá todo
        main_frame = ttk.Frame(self.popup_window, style="InfoPopup.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # --- Cabecera Minimalista para el Botón de Cierre ---
        # Este frame tendrá el mismo fondo que el contenido para integrarse.
        header_bar = ttk.Frame(main_frame, style="InfoPopup.TFrame") 
        # Padding interno mínimo para esta barra, solo para que el botón no esté pegado a los bordes del popup.
        header_bar.pack(side=tk.TOP, fill=tk.X, padx=1, pady=1) 

        close_button = tk.Button(header_bar, text="\u2715", command=self.close, 
                                 relief=tk.FLAT, font=("DejaVu Sans", 9, "normal"), # Tamaño de fuente ajustado
                                 fg=CLOSE_BUTTON_FG, bg=INFO_BG_COLOR, # Fondo igual al de la cabecera
                                 activebackground=CLOSE_BUTTON_ACTIVE_BG, activeforeground="black",
                                 bd=0, highlightthickness=0, 
                                 padx=4, pady=0) # Padding horizontal para el botón en sí
        close_button.pack(side=tk.RIGHT)

        # --- Contenido del Mensaje con Más Espacio Interno ---
        content_message = tk.Message(main_frame, text=self.help_text, 
                                 background=INFO_BG_COLOR,
                                 fg=INFO_TEXT_COLOR,
                                 width=280,
                                 justify=tk.LEFT, font=("tahoma", 8, "normal"),
                                 padx=15) # << QUITA pady=(5, 15) DE AQUÍ

        # Aplica el pady en el método pack()
        content_message.pack(fill=tk.BOTH, expand=True, pady=(5, 15)) # << AÑADE pady=(5, 15) AQUÍ

        # Forzar actualización para obtener geometría y visibilidad correctas
        if self.popup_window:
            self.popup_window.update_idletasks() 
            geom = self.popup_window.winfo_geometry()
            visible = self.popup_window.winfo_viewable()
            pos_x = self.popup_window.winfo_x()
            pos_y = self.popup_window.winfo_y()
            print(f"DEBUG: HelpPopup._create_popup (REFINADO) - Geometría: {geom}, Visible: {visible}, Pos: ({pos_x},{pos_y})") # DEBUG
        
        self.popup_window.bind("<Escape>", lambda e: self.close())
        # El foco se gestiona desde _show_field_help a través de self.current_help_popup.focus()

        print("DEBUG: HelpPopup._create_popup (REFINADO) - Finalizado.") # DEBUG

    def close(self):
        print("DEBUG: HelpPopup.close - Intentando cerrar.") # DEBUG
        if self.popup_window:
            print(f"DEBUG: HelpPopup.close - Destruyendo ventana: {self.popup_window}") # DEBUG
            self.popup_window.destroy()
            self.popup_window = None
        else:
            print("DEBUG: HelpPopup.close - No hay popup_window para destruir.") # DEBUG

    def focus(self):
        """Establece el foco en la ventana emergente."""
        print("DEBUG: HelpPopup.focus - Intentando establecer foco en self.popup_window") # DEBUG
        if self.popup_window:
            self.popup_window.focus_set()
            print("DEBUG: HelpPopup.focus - self.popup_window.focus_set() llamado.") # DEBUG
        else:
            print("DEBUG: HelpPopup.focus - self.popup_window es None, no se puede establecer foco.") # DEBUG

# --- CLASE ADDPROJECTDIALOG ---
class AddProjectDialog(tk.Toplevel):
    def __init__(self, master_window, t_func, base_folder): # t_func es self.t de la app principal
        super().__init__(master_window)

        self.master_window = master_window
        self.t = t_func 
        self.base_folder = base_folder

        self.title(self.t("Add Project Title"))

        self.transient(self.master_window)
        self.grab_set()

        self._create_widgets()
        self._center_window()

        self.name_entry.focus_set()
        self.result = None

        self.bind("<Escape>", lambda e: self.destroy())
        self.name_entry.bind("<KeyRelease>", self._update_local_path_on_name_change)

    def _create_widgets(self):
        frame = ttk.Frame(self, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # --- Configuración de las Columnas del Frame ---
        # Columna 0: Etiquetas (sin expansión)
        # Columna 1: Campos de entrada (se expandirán con el peso)
        # Columna 2: Botones de información (sin expansión)
        # Columna 3: Botón "Examinar" (sin expansión, solo para la fila de Ruta Local)
        frame.columnconfigure(0, weight=0) 
        frame.columnconfigure(1, weight=1) # Esta columna (campos de entrada) se expandirá
        frame.columnconfigure(2, weight=0) 
        frame.columnconfigure(3, weight=0)


        # --- Nombre del Proyecto ---
        name_label = ttk.Label(frame, text=self.t("Project Name"))
        name_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.name_entry = ttk.Entry(frame, width=40) 
        self.name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # ---- NUEVO: Botón de información para Nombre del Proyecto ----
        # Usamos el carácter "ⓘ" (SMALL CIRCLED i)
        # El command llama a _show_field_help, pasando el propio botón como ancla
        # y la clave de traducción para el texto de ayuda (reutilizamos la del tooltip del entry).
        name_info_button = ttk.Button(frame, text="ⓘ", width=2, # width=2 para un botón pequeño
                                      command=lambda: self._show_field_help(name_info_button, "tooltip.project_name_entry")) 
                                      # Nota: pasamos name_info_button como ancla
        name_info_button.grid(row=0, column=2, padx=(0, 5), pady=5, sticky="w")
        
        # ---- COMENTAR O ELIMINAR LOS TOOLTIPS ANTERIORES PARA ESTE CAMPO ----
        # Tooltip(name_label, self.t("tooltip.project_name_label")) 
        # Tooltip(self.name_entry, self.t("tooltip.project_name_entry")) 


        # --- Ruta Local ---
        local_path_label = ttk.Label(frame, text=self.t("Local Path Label"))
        local_path_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        
        self.local_path_var = tk.StringVar()
        self.local_path_entry = ttk.Entry(frame, textvariable=self.local_path_var, width=40)
        self.local_path_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        # (Aquí añadiremos el botón "ⓘ" para Ruta Local en el siguiente paso,
        #  después de probar que el primero funciona)
        # local_path_info_button = ttk.Button(frame, text="ⓘ", ...)
        # local_path_info_button.grid(row=1, column=2, ...)

        browse_button = ttk.Button(frame, text=self.t("Browse Button"), command=self._browse_local_path)
        # El botón Examinar ahora va en la columna 3 para dejar espacio al botón de info en la columna 2
        browse_button.grid(row=1, column=3, padx=5, pady=5, sticky="w") 
        
        # ---- COMENTAR O ELIMINAR TOOLTIPS ANTERIORES PARA RUTA LOCAL ----
        # Tooltip(local_path_label, self.t("tooltip.local_path_label"))
        # Tooltip(self.local_path_entry, self.t("tooltip.local_path_entry"))
        # Tooltip(browse_button, self.t("tooltip.browse_button")) # Puedes decidir si este se queda o también se va


        # Inicializar local_path_var (sin cambios aquí)
        default_name_placeholder = self.name_entry.get() or self.t("New Project Default Name")
        self.local_path_var.set(os.path.join(self.base_folder, default_name_placeholder))

        # --- URL del Repositorio ---
        repo_url_label = ttk.Label(frame, text=self.t("Repository URL Label"))
        repo_url_label.grid(row=2, column=0, padx=5, pady=5, sticky="w")
        
        self.repo_url_entry = ttk.Entry(frame, width=40)
        # El columnspan ya no es necesario si la columna 2 es para el botón de info y la 1 se expande.
        self.repo_url_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew") 
        
        # (Aquí añadiremos el botón "ⓘ" para URL del Repositorio después)
        # ---- COMENTAR O ELIMINAR TOOLTIPS ANTERIORES ----
        # Tooltip(repo_url_label, self.t("tooltip.repo_url_label")) 
        # Tooltip(self.repo_url_entry, self.t("tooltip.repo_url_entry")) 

        # --- Rama (Opcional) ---
        branch_label = ttk.Label(frame, text=self.t("Branch Optional Label"))
        branch_label.grid(row=3, column=0, padx=5, pady=5, sticky="w")
        
        self.branch_entry = ttk.Entry(frame, width=40)
        self.branch_entry.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        # (Aquí añadiremos el botón "ⓘ" para Rama después)
        # ---- COMENTAR O ELIMINAR TOOLTIPS ANTERIORES ----
        # Tooltip(branch_label, self.t("tooltip.branch_label")) 
        # Tooltip(self.branch_entry, self.t("tooltip.branch_entry")) 

        # --- Botones de Acción (Añadir, Cancelar) ---
        button_frame = ttk.Frame(frame)
        # Ajustar columnspan para que el frame de botones ocupe las 4 columnas (0, 1, 2, 3)
        button_frame.grid(row=4, column=0, columnspan=4, pady=10) 

        ttk.Button(button_frame, text=self.t("Add Button"), command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=self.t("Cancel Button"), command=self._on_cancel).pack(side=tk.LEFT, padx=5)

    def _update_local_path_on_name_change(self, event=None):
        project_name = self.name_entry.get().strip()
        if project_name:
            self.local_path_var.set(os.path.join(self.base_folder, project_name))
        else:
            self.local_path_var.set(os.path.join(self.base_folder, self.t("New Project Default Name")))

    def _browse_local_path(self):
        folder_selected = filedialog.askdirectory(
            parent=self, # Asegurar que el diálogo sea modal a este Toplevel
            initialdir=self.base_folder,
            title=self.t("Select Local Path Title")
        )
        if folder_selected:
            self.local_path_var.set(folder_selected)

    def _on_dialog_destroy(self, event):
        # Asegurarse de que el evento es para este widget (evitar cierres por hijos)
        if event.widget == self:
            if self.current_help_popup:
                self.current_help_popup.close()
                self.current_help_popup = None

    def _show_field_help(self, anchor_widget, help_text_key):
        print(f"DEBUG: _show_field_help llamado para clave: '{help_text_key}', ancla: {anchor_widget}") # DEBUG
        if self.current_help_popup:
            print("DEBUG: Cerrando HelpPopup existente.") # DEBUG
            self.current_help_popup.close()
            self.current_help_popup = None
        
        help_text = self.t(help_text_key)
        popup_title = self.t("help.popup_title") 
        print(f"DEBUG: _show_field_help - Título traducido: '{popup_title}'") # DEBUG
        print(f"DEBUG: _show_field_help - Texto de ayuda original de t(): '{help_text}'") # DEBUG

        if help_text == help_text_key: # Si la traducción devolvió la clave misma
            print(f"DEBUG: _show_field_help - Clave '{help_text_key}' no encontrada en JSON, usando placeholder.") # DEBUG
            help_text = self.t("help.not_available_placeholder")
            print(f"DEBUG: _show_field_help - Texto de ayuda placeholder: '{help_text}'") # DEBUG

        if not help_text: # Comprobar si el texto de ayuda es vacío o None
            print("DEBUG: _show_field_help - Texto de ayuda final es vacío o None. No se creará el popup.") #DEBUG
            return

        print("DEBUG: _show_field_help - Creando instancia de HelpPopup...") #DEBUG
        self.current_help_popup = HelpPopup(anchor_widget, popup_title, help_text)
        print(f"DEBUG: _show_field_help - Instancia de HelpPopup creada: {self.current_help_popup}") # DEBUG
        
        if self.current_help_popup and self.current_help_popup.popup_window:
            print("DEBUG: _show_field_help - Llamando focus() en la ventana del popup.") # DEBUG
            self.current_help_popup.focus()
        else:
            print("DEBUG: _show_field_help - HelpPopup o su popup_window es None después de la creación.") # DEBUG

    def _on_ok(self):
        name = self.name_entry.get().strip()
        local_path_full = self.local_path_var.get().strip()
        repo_url = self.repo_url_entry.get().strip()
        branch = self.branch_entry.get().strip()

        if not name or not local_path_full or not repo_url: # Repo URL también es requerido
            messagebox.showerror(self.t("Input Error"), self.t("Please fill in all required fields: Name, Local Path, Repository URL."))
            return

        self.result = {
            'name': name,
            'local_path_full': local_path_full,
            'repo_url': repo_url,
            'branch': branch if branch else 'main' # Default a 'main' si está vacío
        }
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def exec_(self): # Para compatibilidad si se llama así desde fuera
        self.master_window.wait_window(self)
        return self.result

    def _center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        # Asegurar que master_window es la ventana principal para centrar correctamente
        master_x = self.master_window.winfo_x()
        master_y = self.master_window.winfo_y()
        master_width = self.master_window.winfo_width()
        master_height = self.master_window.winfo_height()
        
        x = master_x + (master_width // 2) - (width // 2)
        y = master_y + (master_height // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')

    def __init__(self, master_window, t_func, base_folder):
        super().__init__(master_window)

        self.master_window = master_window
        self.t = t_func
        self.base_folder = base_folder
        self.current_help_popup = None # <<<< AÑADE ESTA LÍNEA

        self.title(self.t("Add Project Title"))

        self.transient(self.master_window)
        self.grab_set()

        self._create_widgets()
        self._center_window()

        self.name_entry.focus_set()
        self.result = None

        self.bind("<Escape>", lambda e: self.destroy())
        self.name_entry.bind("<KeyRelease>", self._update_local_path_on_name_change)
        # Asegúrate de cerrar el help popup si el diálogo se destruye
        self.bind("<Destroy>", self._on_dialog_destroy, add='+') 

# --- CLASE INSTALLERPROAPP (CON MODIFICACIONES) ---
class InstallerProApp:
    def __init__(self, master):
        self.master = master
        self.logger = logging.getLogger(__name__) # Logger específico para la instancia

        self.master.withdraw() # Ocultar ventana principal hasta que todo esté listo

        self.t = i18n.t # Alias a la función de traducción del módulo i18n

        # 1. Inicializar el gestor de configuración
        # Pasa app_config_initial_check como configuración inicial que ConfigManager puede usar o sobreescribir
        self.config_manager = ConfigManager(config_file_path, app_config_initial_check)

        # Obtener la carpeta base DESPUÉS de que ConfigManager la haya cargado o establecido por defecto
        initial_base_folder = os.path.abspath(self.config_manager.get_base_folder())
        os.makedirs(initial_base_folder, exist_ok=True) # Asegurar que exista
        self.logger.info(self.t("Base folder configured: {folder}", folder=initial_base_folder))


        # 2. Inicializar el ProjectManager
        self.project_manager = ProjectManager(
            base_folder=initial_base_folder, # Usar la carpeta base ya validada
            config_manager=self.config_manager, # Pasar la instancia de config_manager
            projects_file_path=projects_file_path
        )

        # 3. Configurar el traductor (i18n) y establecer el idioma inicial desde ConfigManager
        initial_lang_code = self.config_manager.get_language() # Obtener idioma de config
        if not i18n.set_language(initial_lang_code): # Intentar establecerlo en el módulo i18n
            self.logger.warning(self.t("Could not set initial language to {lang} from config. Defaulting to 'en'.", lang=initial_lang_code))
            i18n.set_language("en") # Fallback a 'en'
            self.config_manager.set_language("en") # Actualizar config si hubo fallback

        self.task_queue = Queue() # Cola para tareas asíncronas

        # 4. Configurar y mostrar UI
        self._setup_ui() # Esto llamará a _recreate_menubar internamente
        self.update_ui_texts() # Esto actualizará todos los textos, incluyendo el menú recreado
        
        # _load_projects_into_treeview() es llamado por update_ui_texts(),
        # así que no es estrictamente necesario aquí, pero no hace daño para el primer llenado.
        self._load_projects_into_treeview() 

        self.master.after(100, self._process_task_queue) # Iniciar el procesador de la cola de tareas

        self.logger.info(self.t("App Title") + " " + self.t("started.")) # Ejemplo de log traducido
        self.master.deiconify() # Mostrar ventana principal

    # **** NUEVO MÉTODO: _recreate_menubar ****
    def _recreate_menubar(self):
        self.logger.debug("Recreando la barra de menú...")
        if hasattr(self, 'menubar') and self.menubar:
            try:
                self.menubar.destroy()
                self.logger.debug("Barra de menú anterior destruida.")
            except tk.TclError as e:
                self.logger.warning(f"No se pudo destruir la barra de menú anterior: {e}")

        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)

        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(menu=self.view_menu, label=self.t("View Menu"))

        self.lang_menu = tk.Menu(self.view_menu, tearoff=0)
        self.view_menu.add_cascade(menu=self.lang_menu, label=self.t("Language Menu"))
        
        self._populate_language_menu() # Llama a tu método existente para llenar las opciones de idioma
        
        self.logger.info("Barra de menú recreada y configurada exitosamente.")

    # **** MÉTODO MODIFICADO: _setup_ui ****
    def _setup_ui(self):
        self.main_frame = ttk.Frame(self.master, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # La creación del menubar se delega a _recreate_menubar
        self._recreate_menubar() # Llamada para la creación inicial

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
        # self.update_base_folder_label() # Será llamado en update_ui_texts

    # _populate_language_menu no necesita cambios, se mantiene como en tu archivo original
    def _populate_language_menu(self):
        self.lang_menu.delete(0, tk.END) # Limpiar opciones anteriores

        if not hasattr(self, 'selected_language_var'): # Crear si no existe
            self.selected_language_var = tk.StringVar()

        available_lang_codes = i18n.get_available_languages()

        for lang_code in available_lang_codes:
            lang_name_key = f"language_option.{lang_code}" # ej. language_option.en
            # Obtener el nombre legible del idioma usando la traducción actual
            # y especificando el 'lang' para la propia clave del nombre del idioma si es necesario
            display_name = self.t(lang_name_key, lang=lang_code) 
            if display_name == lang_name_key: # Fallback si la clave no está traducida
                display_name = lang_code.upper() 

            self.lang_menu.add_radiobutton(
                label=display_name,
                command=lambda lc=lang_code: self.change_language(lc), # Usar lambda para pasar el código
                variable=self.selected_language_var, # Variable para controlar selección
                value=lang_code # Valor asociado a esta opción
            )
        # Establecer la selección actual del radiobutton
        self.selected_language_var.set(i18n.get_current_language())

    # **** MÉTODO MODIFICADO: update_ui_texts ****
    def update_ui_texts(self):
        current_lang = i18n.get_current_language()
        self.logger.info(f"Actualizando textos de la UI al idioma: {current_lang}")
        self.master.title(self.t("App Title"))

        # --- INICIO DE LA CORRECCIÓN PRINCIPAL ---
        self._recreate_menubar() # Recrea toda la barra de menú con los textos actuales
        # --- FIN DE LA CORRECCIÓN PRINCIPAL ---

        # Actualizar otros elementos de la UI
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
        self._load_projects_into_treeview() # Para actualizar "No projects" o estados traducidos
        self.logger.info("Textos de la UI actualizados exitosamente.")

    def _process_task_queue(self):
        try:
            while not self.task_queue.empty(): # Procesar todas las tareas pendientes
                callback, args, kwargs = self.task_queue.get_nowait() # No bloquear
                callback(*args, **kwargs)
                self.task_queue.task_done() # Marcar tarea como completada
        except Empty: # Si la cola está vacía, no hacer nada
            pass
        except Exception as e:
            self.logger.error(f"Error procesando tarea de la cola: {e}")
        finally:
            # Reprogramar la revisión de la cola
            self.master.after(100, self._process_task_queue)

    def update_base_folder_label(self):
        current_base_folder = self.config_manager.get_base_folder()
        # Usar una clave de traducción para el formato de la etiqueta
        label_text = self.t("base_folder_status_label", path=current_base_folder) 
        self.base_folder_label.config(text=label_text)

    def change_language(self, lang_code):
        old_lang = i18n.get_current_language()
        # config_manager.set_language ahora valida si el idioma existe en i18n y guarda en config.json
        if self.config_manager.set_language(lang_code): 
            # i18n.set_language carga las traducciones para el nuevo idioma.
            if i18n.set_language(lang_code): # Importante llamar para cargar traducciones
                self.update_ui_texts() # Actualiza toda la UI, incluyendo el menú recreado
                self.selected_language_var.set(lang_code) # Actualiza el radiobutton seleccionado
                
                # Mostrar mensaje de confirmación
                lang_display_name_key = f"language_option.{lang_code}"
                lang_display_name = self.t(lang_display_name_key)
                if lang_display_name == lang_display_name_key: # Fallback
                    lang_display_name = lang_code.upper()

                messagebox.showinfo(
                    self.t("Language Changed Title"), # Título del messagebox
                    self.t("Language changed message", lang=lang_display_name) # Mensaje
                )
                self.logger.info(f"Idioma cambiado de {old_lang} a {lang_code}.")
            else:
                # Esto no debería ocurrir si config_manager.set_language tuvo éxito,
                # ya que ambos deberían usar la misma lista de idiomas disponibles de i18n.
                messagebox.showerror(
                    self.t("Error Changing Language Title"),
                    self.t("Error loading translations message", lang=lang_code)
                )
                self.logger.error(f"Fallo al cargar traducciones para {lang_code} después de que ConfigManager lo aceptara.")
                # Considerar revertir a old_lang en i18n y config_manager si la carga falla aquí.
        else:
            # Esto ocurre si lang_code no está en i18n.get_available_languages()
            # según la validación en config_manager.set_language
            messagebox.showerror(
                self.t("Error Changing Language Title"),
                self.t("Language not available message", lang=lang_code)
            )
            self.logger.error(f"Intento de cambiar a idioma no disponible: {lang_code}.")


    def _load_projects_into_treeview(self):
        for item in self.tree.get_children(): # Limpiar vista previa
            self.tree.delete(item)

        projects = self.project_manager.get_projects() # Obtener solo proyectos no marcados como 'deleted'
        if not projects:
            # Mostrar mensaje si no hay proyectos, usando traducción
            self.tree.insert("", tk.END, text="", values=(
                self.t("No Projects Found Message"), "", "", "", "" # Mensaje traducido
            ))
            self.logger.info("No hay proyectos para mostrar en la vista de árbol.")
            return

        for project in projects:
            # Traducir el estado del proyecto si es una clave de traducción
            # Asumiendo que 'status' puede ser una clave como "Clean", "Modified", etc.
            status_key = f"status.{project.get('status', 'Unknown').lower().replace(' ', '_')}" # ej. status.modified
            status_display = self.t(status_key)
            if status_display == status_key: # Si no hay traducción específica, usar el valor crudo
                status_display = project.get('status', self.t("status.unknown"))


            self.tree.insert("", tk.END,
                                values=(project['name'], project['local_path'], project['repo_url'], project['branch'], status_display),
                                tags=("deleted" if project.get('deleted') else "normal",)) # 'deleted' no debería aparecer aquí
        
        self.tree.tag_configure("deleted", foreground="red") # Aunque no se muestren, la configuración está
        self.logger.info(f"Cargados {len(projects)} proyectos en la vista de árbol.")


    def _get_selected_project_path(self):
        selected_item = self.tree.focus() # Obtener el item seleccionado (foco)
        if not selected_item:
            messagebox.showwarning(
                self.t("Selection Required Title"), # Título traducido
                self.t("Please select a project message") # Mensaje traducido
            )
            self.logger.warning("Ningún proyecto seleccionado para la operación.")
            return None
        # El índice 1 es 'path' según la definición de columnas en _setup_ui
        return self.tree.item(selected_item, 'values')[1] 

    def _process_queue(self): # Mantener este método aunque esté vacío si planeas usarlo
        pass

    def _run_async_task(self, target_function, *args, callback_on_success=None, callback_on_failure=None, **kwargs):
        def task_wrapper():
            try:
                result = target_function(*args, **kwargs)
                if callback_on_success:
                    # Poner en cola la tupla (función, tupla_de_args, dict_de_kwargs)
                    self.task_queue.put((callback_on_success, (result,), {})) 
            except Exception as e: # Capturar cualquier excepción de la tarea
                self.logger.error(f"Excepción en hilo de tarea para {target_function.__name__}: {e}", exc_info=True)
                if callback_on_failure:
                    self.task_queue.put((callback_on_failure, (e,), {}))

        thread = threading.Thread(target=task_wrapper)
        thread.daemon = True # Permitir que la app cierre aunque los hilos estén corriendo
        thread.start()

    def _add_project(self):
        # Pasar self.t (la función de traducción de la instancia) al diálogo
        dialog = AddProjectDialog(self.master, t_func=self.t, base_folder=self.config_manager.get_base_folder())
        # dialog.exec_() no es un método estándar de Toplevel. Usar wait_window.
        # El método exec_() que definiste en AddProjectDialog usa wait_window.
        if dialog.exec_(): # Esto llamará a tu wait_window y devolverá el resultado
            name = dialog.result['name']
            repo_url = dialog.result['repo_url']
            local_path_full = dialog.result['local_path_full']
            branch = dialog.result['branch']

            messagebox.showinfo( # Usar traducciones para el messagebox
                self.t("Adding Project Title"), 
                self.t("Adding project progress message", project=name) 
            )
            self.logger.info(f"Iniciando adición asíncrona del proyecto '{name}'...")
            self._run_async_task(
                self.project_manager.add_project, # Función a ejecutar
                name, repo_url, local_path_full, branch, # Args para add_project
                callback_on_success=self._on_project_added_success,
                callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Adding Project Operation Name")) # Nombre de operación traducido
            )

    def _remove_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project: # Esto no debería pasar si _get_selected_project_path devolvió algo y la lista está sincronizada
            messagebox.showerror(self.t("Error Title"), self.t("Selected project data not found error"))
            self.logger.error(f"Intento de eliminar proyecto no encontrado en el gestor: {selected_path}")
            return

        # Usar traducciones para los diálogos de confirmación
        confirm_soft_delete = messagebox.askyesno(
            self.t("Confirm Remove Title"),
            self.t("Confirm soft delete message")
        )

        project_name_display = project.get('name', self.t("Unnamed Project Default"))

        if confirm_soft_delete: # El usuario eligió "Sí" para borrado suave
            messagebox.showinfo(self.t("Removing Project Title"), self.t("Removing project progress message", project=project_name_display))
            self.logger.info(f"Iniciando borrado suave asíncrono del proyecto '{project_name_display}'...")
            self._run_async_task(
                self.project_manager.remove_project,
                selected_path, permanent=False, # Borrado suave
                callback_on_success=lambda result: self._on_project_removed_success(project_name_display), # Pasar nombre para mensaje
                callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Removing Project Operation Name"))
            )
        elif confirm_soft_delete is False: # El usuario eligió "No" (lo que significa que considerará el borrado físico)
            confirm_physical_delete = messagebox.askyesno(
                self.t("Confirm Physical Remove Title"),
                self.t("Confirm physical delete message", path=selected_path) # Mensaje de advertencia
            )
            if confirm_physical_delete:
                messagebox.showinfo(self.t("Removing Project Title"), self.t("Removing project progress message", project=project_name_display))
                self.logger.info(f"Iniciando borrado físico asíncrono del proyecto '{project_name_display}'...")
                self._run_async_task(
                    self.project_manager.remove_project,
                    selected_path, permanent=True, # Borrado físico
                    callback_on_success=lambda result: self._on_project_physically_removed_success(project_name_display), # Pasar nombre
                    callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Physical Removing Project Operation Name"))
                )
        # Si confirm_soft_delete es None (usuario cerró el diálogo), no hacer nada.
        else: 
            self.logger.info("Eliminación de proyecto cancelada por el usuario.")
            messagebox.showinfo(self.t("Action Cancelled Title"), self.t("Project removal cancelled message"))


    def _update_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project:
            messagebox.showerror(self.t("Error Title"), self.t("Selected project data not found error"))
            self.logger.error(f"Intento de actualizar proyecto no encontrado en el gestor: {selected_path}")
            return
        
        project_name_display = project.get('name', self.t("Unnamed Project Default"))
        messagebox.showinfo(
            self.t("Updating Project Title"), 
            self.t("Updating project progress message", project=project_name_display)
        )
        self.logger.info(f"Iniciando actualización asíncrona (pull) del proyecto '{project_name_display}'...")
        self._run_async_task(
            self.project_manager.update_project,
            selected_path, do_pull=True,
            callback_on_success=self._on_project_updated_success,
            callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Updating Project Operation Name"))
        )

    def _scan_base_folder(self):
        current_base_folder = self.config_manager.get_base_folder()
        folder_selected = filedialog.askdirectory(
            parent=self.master,
            initialdir=current_base_folder,
            title=self.t("Select Base Folder Title") # Título del diálogo traducido
        )
        if folder_selected:
            try:
                # Actualizar la carpeta base en config_manager y project_manager
                self.config_manager.set_base_folder(folder_selected)
                self.project_manager.set_base_folder(folder_selected) # Asegurar que project_manager también se actualice
                self.update_base_folder_label() # Actualizar etiqueta en la UI

                messagebox.showinfo(
                    self.t("Scanning Base Folder Title"), 
                    self.t("Scanning base folder progress message", folder=folder_selected)
                )
                self.logger.info(f"Iniciando escaneo asíncrono de la carpeta base '{folder_selected}'...")
                self._run_async_task(
                    self.project_manager.scan_base_folder, # No necesita args aquí
                    callback_on_success=self._on_scan_complete_success,
                    callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Scan Base Folder Operation Name")),
                )
            except Exception as e: # Capturar errores al establecer la carpeta base
                messagebox.showerror(
                    self.t("Scan Error Title"),
                    self.t("Unexpected error during scan setup message", error=str(e))
                )
                self.logger.critical(f"Error inesperado durante la configuración de _scan_base_folder: {e}", exc_info=True)
        else: # folder_selected es None o vacío
            messagebox.showinfo(
                self.t("Selection Canceled Title"), 
                self.t("Base folder selection cancelled info")
            )
            self.logger.info("Selección de carpeta base cancelada.")


    def _push_project(self):
        selected_path = self._get_selected_project_path()
        if not selected_path:
            return

        project = self.project_manager.get_project_by_path(selected_path)
        if not project:
            messagebox.showerror(self.t("Error Title"), self.t("Selected project data not found error"))
            self.logger.error(f"Intento de push a proyecto no encontrado en el gestor: {selected_path}")
            return
        
        project_name_display = project.get('name', self.t("Unnamed Project Default"))
        messagebox.showinfo(
            self.t("Pushing Project Title"), 
            self.t("Pushing project progress message", project=project_name_display)
        )
        self.logger.info(f"Iniciando push asíncrono del proyecto '{project_name_display}'...")
        self._run_async_task(
            self.project_manager.push_project,
            selected_path,
            callback_on_success=self._on_project_pushed_success,
            callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Pushing Project Operation Name"))
        )

    def _refresh_all_statuses(self):
        messagebox.showinfo(
            self.t("Refreshing Statuses Title"), 
            self.t("Refreshing all project statuses message")
        )
        self.logger.info("Iniciando actualización asíncrona de todos los estados de proyecto.")
        self._run_async_task(
            self.project_manager.refresh_project_statuses, # No necesita args
            callback_on_success=self._on_refresh_status_complete_success, # Modificado para no esperar args innecesarios
            callback_on_failure=lambda e: self._on_project_op_failure(e, self.t("Refresh Statuses Operation Name")),
        )

    def _show_help(self):
        help_title = self.t("help.title") # Clave para el título de ayuda
        help_content = self.t("help.content") # Clave para el contenido de ayuda
        messagebox.showinfo(help_title, help_content)
        self.logger.info("Diálogo de ayuda mostrado.")

    # Callbacks para operaciones asíncronas
    def _on_project_added_success(self, project_data): # project_data es el proyecto devuelto por project_manager.add_project
        self._load_projects_into_treeview() # Actualizar la lista en la UI
        messagebox.showinfo(
            self.t("Success Title"), 
            self.t("Project Added And Cloned Success message", project=project_data['name'], path=project_data['local_path'])
        )
        self.logger.info(f"Proyecto '{project_data['name']}' añadido y clonado exitosamente.")

    def _on_project_op_failure(self, error, op_name="Operation"): # op_name ya debería estar traducido al pasar aquí
        messagebox.showerror(
            self.t("Error Title"), 
            self.t("Generic error message", op_name=op_name, error_message=str(error))
        )
        self.logger.error(f"Fallo durante {op_name}: {error}", exc_info=True) # Log con traceback si es una excepción
        self._load_projects_into_treeview() # Refrescar vista por si algo cambió parcialmente

    def _on_project_removed_success(self, project_name): # project_name se pasa para el mensaje
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Project Marked as Deleted Title"), 
            self.t("Project Marked as Deleted message", project=project_name)
        )
        self.logger.info(f"Proyecto '{project_name}' marcado como eliminado (borrado suave).")

    def _on_project_physically_removed_success(self, project_name): # project_name se pasa
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Project Physically Removed Title"), 
            self.t("Project Physically Removed Success message", project=project_name)
        )
        self.logger.info(f"Proyecto '{project_name}' eliminado físicamente.")

    def _on_project_updated_success(self, pull_result_message): # pull_result_message es el stdout o mensaje de estado
        self._load_projects_into_treeview()
        # Asumir que pull_result_message ya es un texto legible o una clave que se puede usar.
        # Sería mejor si project_manager.update_project devuelve un código/clave de estado.
        if "Already up to date." in pull_result_message or "Up-to-date" == pull_result_message: # Comparación más robusta
            messagebox.showinfo(
                self.t("Update Complete Title"), 
                self.t("Project is already up-to-date message")
            )
        else:
            messagebox.showinfo(
                self.t("Update Complete Title"), 
                self.t("Project Updated Success message") # Mensaje genérico de éxito
            )
        self.logger.info(f"Proyecto actualizado (pull) exitosamente. Resultado: {pull_result_message}")


    def _on_project_pushed_success(self, push_result_message):
        self._load_projects_into_treeview()
        if "Everything up-to-date" in push_result_message or "Up-to-date (Push)" == push_result_message:
            messagebox.showinfo(
                self.t("Push Complete Title"), 
                self.t("Project is already up-to-date (no changes to push) message")
            )
        else:
            messagebox.showinfo(
                self.t("Push Complete Title"), 
                self.t("Project Pushed Success message")
            )
        self.logger.info(f"Proyecto 'pusheado' exitosamente. Resultado: {push_result_message}")

    def _on_scan_complete_success(self, new_projects_count): # new_projects_count es devuelto por scan_base_folder
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Scan Complete Title"), 
            self.t("Scan complete found new projects message", count=new_projects_count)
        )
        self.logger.info(f"Escaneo completo. Encontrados {new_projects_count} nuevos proyectos.")

    def _on_refresh_status_complete_success(self, *args): # Ignorar args si no se esperan
        self._load_projects_into_treeview()
        messagebox.showinfo(
            self.t("Status Refresh Complete Title"), 
            self.t("All project statuses refreshed message")
        )
        self.logger.info("Todos los estados de proyecto actualizados exitosamente.")


    def run(self):
        self.master.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    # No se necesita pasar instancias aquí, InstallerProApp las crea o usa las globales
    app = InstallerProApp(root) 
    app.run()