# installerpro/config.py
import os
import json
import logging
import sys # Asegúrate de que sys esté importado para sys.platform

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, app_name="InstallerPro"):
        self.app_name = app_name
        self.config_dir = self._get_config_directory()
        self.config_file = os.path.join(self.config_dir, "config.json")
        self._config_data = self._load_config()
        logger.info(f"Configuration loaded from {self.config_file}")

    def _get_config_directory(self):
        """
        Determina la ruta del directorio de configuración de la aplicación.
        Utiliza el directorio de datos de la aplicación específico del sistema operativo.
        """
        if sys.platform.startswith('win'):
            # Windows: C:\Users\<Username>\AppData\Roaming
            config_dir = os.path.join(os.environ['APPDATA'], self.app_name)
        elif sys.platform.startswith('darwin'):
            # macOS: ~/Library/Application Support
            config_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', self.app_name)
        else:
            # Linux/Unix: ~/.config o ~/.local/share
            config_dir = os.path.join(os.path.expanduser('~'), '.config', self.app_name)
            if not os.path.exists(config_dir):
                config_dir = os.path.join(os.path.expanduser('~'), '.local', 'share', self.app_name)

        os.makedirs(config_dir, exist_ok=True)
        return config_dir

    def _load_config(self):
        """Carga la configuración desde el archivo JSON o devuelve una configuración por defecto."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding config file {self.config_file}: {e}. Using default config.")
            except Exception as e:
                logger.error(f"Error loading config file {self.config_file}: {e}. Using default config.")
        
        # Configuración por defecto
        default_config = {
            "base_folder": os.path.join(os.path.expanduser("~"), "InstallerProProjects"),
            "language": "en" # Idioma por defecto
        }
        self._save_config(default_config) # Guarda la configuración por defecto si no existe o hay error
        return default_config

    def _save_config(self, config_data):
        """Guarda la configuración en el archivo JSON."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4)
            logger.info(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving config file {self.config_file}: {e}")

    def get_setting(self, key, default=None):
        """Obtiene un valor de configuración."""
        return self._config_data.get(key, default)

    def set_setting(self, key, value):
        """Establece un valor de configuración y lo guarda."""
        self._config_data[key] = value
        self._save_config(self._config_data)

    def get_base_folder(self):
        """Obtiene la carpeta base de los proyectos."""
        return self.get_setting("base_folder")

    def set_base_folder(self, path):
        """Establece la carpeta base de los proyectos y la guarda."""
        os.makedirs(path, exist_ok=True) # Asegura que la nueva carpeta base exista
        self.set_setting("base_folder", path)
        logger.info(f"Base folder set to: {path}")

    def get_language(self):
        """Obtiene el idioma configurado."""
        return self.get_setting("language")

    def set_language(self, lang_code):
        """Establece el idioma configurado y lo guarda."""
        # Puedes añadir una validación aquí para asegurar que el idioma es válido
        self.set_setting("language", lang_code)
        logger.info(f"Language set to: {lang_code}")
        return True # Asume éxito por ahora