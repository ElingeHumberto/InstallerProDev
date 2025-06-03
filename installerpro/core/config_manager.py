# installerpro/core/config_manager.py
import os
import json
import logging
import platform

try:
    import appdirs
    HAS_APPDIRS = True
except ImportError:
    HAS_APPDIRS = False

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Gestiona la carga, guardado y acceso a la configuración de la aplicación,
    incluyendo la carpeta base de los proyectos y el idioma.
    Utiliza directorios de usuario estándar del sistema operativo para la persistencia.
    """
    APP_NAME = "InstallerPro"
    APP_AUTHOR = "ElingeHumberto"
    CONFIG_FILE_NAME = "config.json"
    PROJECTS_FILE_NAME = "projects.json"

    def __init__(self, config_file_path, initial_app_config):
        self.config_file_path = config_file_path
        self._config_data = initial_app_config

        if HAS_APPDIRS:
            self.user_config_dir = appdirs.user_config_dir(self.APP_NAME, self.APP_AUTHOR)
            self.user_data_dir = appdirs.user_data_dir(self.APP_NAME, self.APP_AUTHOR)
        else:
            if platform.system() == "Windows":
                self.user_config_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), self.APP_NAME)
                self.user_data_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser("~")), self.APP_NAME)
            else: # Linux/macOS
                self.user_config_dir = os.path.join(os.path.expanduser("~"), f".config/{self.APP_NAME}")
                self.user_data_dir = os.path.join(os.path.expanduser("~"), f".local/share/{self.APP_NAME}")

        os.makedirs(self.user_config_dir, exist_ok=True)
        os.makedirs(self.user_data_dir, exist_ok=True)

        self._load_config()

    def _get_default_config(self):
        """Devuelve una configuración por defecto."""
        default_base_folder = os.path.join(os.path.expanduser("~"), 'Documents', self.APP_NAME, 'Projects')
        if not os.path.exists(default_base_folder):
             default_base_folder = os.path.join(os.path.expanduser("~"), self.APP_NAME, 'Projects')
        
        return {
            'base_folder': os.path.abspath(os.path.normpath(default_base_folder)),
            'language': 'en',
        }

    def _load_config(self):
        """Carga la configuración desde el archivo JSON o inicializa con valores por defecto."""
        if os.path.exists(self.config_file_path):
            try:
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    self._config_data = json.load(f)
                logger.info(f"Configuration loaded from: {self.config_file_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding config.json: {e}. Reinitializing config with defaults.")
                self._config_data = self._get_default_config()
                self._save_config()
            except Exception as e:
                logger.error(f"Unexpected error loading config.json: {e}. Reinitializing config with defaults.")
                self._config_data = self._get_default_config()
                self._save_config()
        else:
            self._config_data = self._get_default_config()
            self._save_config()
            logger.info(f"Config file not found. Created default config at {self.config_file_path}")

    def _save_config(self):
        """Guarda la configuración actual en el archivo JSON."""
        try:
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=4)
            logger.info(f"Configuration saved to: {self.config_file_path}")
        except Exception as e:
            logger.error(f"Error saving config.json to {self.config_file_path}: {e}")

    def get_setting(self, key, default=None):
        """Devuelve un valor de configuración por clave."""
        return self._config_data.get(key, default)

    def set_setting(self, key, value):
        """Establece un valor de configuración por clave y lo guarda."""
        if self._config_data.get(key) != value:
            self._config_data[key] = value
            self._save_config()
            logger.info(f"Config setting '{key}' updated to '{value}'.")
            return True
        return False

    def get_base_folder(self):
        """Devuelve la carpeta base actual para los proyectos."""
        folder = self.get_setting('base_folder', self._get_default_config()['base_folder'])
        return os.path.abspath(os.path.normpath(folder))

    def set_base_folder(self, folder_path):
        """Establece y guarda la nueva carpeta base para los proyectos."""
        normalized_path = os.path.abspath(os.path.normpath(folder_path))
        if not os.path.isdir(normalized_path):
            try:
                os.makedirs(normalized_path, exist_ok=True)
                logger.info(f"Created new base folder directory: {normalized_path}")
            except OSError as e:
                logger.error(f"Failed to create base folder directory '{normalized_path}': {e}")
                return False
        return self.set_setting('base_folder', normalized_path)

    def get_language(self):
        """Devuelve el código del idioma actual."""
        return self.get_setting('language', self._get_default_config()['language'])

    def set_language(self, lang_code):
        """Establece y guarda el nuevo idioma de la interfaz."""
        from installerpro import i18n 
        if lang_code in i18n.get_available_languages(): 
            return self.set_setting('language', lang_code)
        else:
            logger.warning(f"Attempted to set unavailable language: {lang_code}. Not saving.")
            return False
