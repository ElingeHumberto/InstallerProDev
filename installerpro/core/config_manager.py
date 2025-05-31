# installerpro/core/config_manager.py
import json
import os
import logging

logger = logging.getLogger(__name__)

class ConfigManager:
    """
    Gestiona la carga, guardado y acceso a la configuración de la aplicación,
    incluyendo la carpeta base de los proyectos y el idioma.
    """
    def __init__(self, config_file='config.json'):
        # Obtener el directorio del script actual (installerpro/core/)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # La carpeta 'installerpro' es el padre de 'installerpro/core'
        installerpro_dir = os.path.dirname(current_dir)
        # El archivo de configuración se guarda en la raíz del paquete installerpro
        self.config_path = os.path.join(installerpro_dir, config_file)
        self.config = {}
        self._load_config()

    def _load_config(self):
        """Carga la configuración desde el archivo JSON o inicializa con valores por defecto."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"Configuration loaded from {self.config_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding config.json: {e}. Reinitializing config.")
                self.config = self._get_default_config()
                self._save_config() # Guarda la configuración por defecto
            except Exception as e:
                logger.error(f"Unexpected error loading config.json: {e}. Reinitializing config.")
                self.config = self._get_default_config()
                self._save_config() # Guarda la configuración por defecto
        else:
            self.config = self._get_default_config()
            self._save_config() # Guarda la configuración por defecto al crearla
            logger.info(f"config.json not found. Created default config at {self.config_path}")

    def _save_config(self):
        """Guarda la configuración actual en el archivo JSON."""
        try:
            # Asegura que el directorio exista
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving config.json: {e}")

    def _get_default_config(self):
        """Devuelve una configuración por defecto."""
        # Define una carpeta base por defecto (ej. 'Projects' dentro de la raíz del proyecto)
        # La raíz del proyecto es dos niveles por encima del directorio actual del script.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        default_base_folder = os.path.join(project_root, 'Projects')
        return {
            'base_folder': default_base_folder,
            'language': 'en', # Idioma por defecto
        }

    def get_base_folder(self):
        """Devuelve la carpeta base actual para los proyectos."""
        folder = self.config.get('base_folder')
        if folder is None:
            # Si 'base_folder' no está en el archivo, vuelve a los valores por defecto
            self.config['base_folder'] = self._get_default_config()['base_folder']
            self._save_config()
            logger.warning("Base folder not found in config, set to default.")
        return self.config['base_folder']

    def set_base_folder(self, folder_path):
        """Establece y guarda la nueva carpeta base para los proyectos."""
        if not os.path.isdir(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
                logger.info(f"Created new base folder directory: {folder_path}")
            except OSError as e:
                logger.error(f"Failed to create base folder directory '{folder_path}': {e}")
                return False
        self.config['base_folder'] = os.path.abspath(folder_path)
        self._save_config()
        logger.info(f"Base folder set to: {folder_path}")
        return True

    def get_language(self):
        """Devuelve el código del idioma actual."""
        lang = self.config.get('language')
        if lang is None:
            self.config['language'] = self._get_default_config()['language']
            self._save_config()
            logger.warning("Language not found in config, set to default 'en'.")
        return self.config['language']

    def set_language(self, lang_code):
        """
        Establece y guarda el nuevo idioma de la interfaz.
        Retorna True si el idioma fue establecido, False en caso contrario.
        """
        # Nota: Aquí no verificamos si el lang_code existe en i18n,
        # esa lógica debería estar en la aplicación principal si es necesario.
        # Solo guardamos la preferencia.
        if lang_code != self.config.get('language'):
            self.config['language'] = lang_code
            self._save_config()
            logger.info(f"Language preference set to: {lang_code}")
            return True
        return False