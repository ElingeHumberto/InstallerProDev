# installerpro/i18n.py

import os
import json
import logging

logger = logging.getLogger(__name__)

_current_language = "en"
_translations = {}
_default_language = "en"

# Las variables _PROJECT_ROOT y _LOCALES_DIR serán pasadas/calculadas desde InstallerProApp.__init__
# ya que necesitamos que el logger esté completamente configurado antes de usarlas.


def load_translations(lang_code, locales_dir): # AHORA RECIBE locales_dir
    """Carga las traducciones para un código de idioma específico."""
    global _translations
    lang_file = os.path.normpath(os.path.join(locales_dir, f'{lang_code}.json')) # Usa locales_dir
    logger.debug(f"Attempting to load translations from: {lang_file}") 

    if not os.path.exists(locales_dir): 
        logger.error(f"Translation directory not found: {locales_dir}. Translations will not be loaded.")
        _translations = {}
        return

    if not os.path.exists(lang_file): 
        logger.warning(f"Language file '{lang_file}' not found. Falling back to default: '{_default_language}'.")
        if lang_code != _default_language:
            load_translations(_default_language, locales_dir) 
            return

    try:
        with open(lang_file, 'r', encoding='utf-8') as f:
            _translations = json.load(f)
        logger.info(f"Translations loaded for '{lang_code}' from '{lang_file}'.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {lang_file}. Invalid format. Falling back to default language. Error: {e}")
        _translations = {}
        if lang_code != _default_language:
            set_language(_default_language, locales_dir) 
    except Exception as e:
        logger.error(f"An unexpected error occurred loading translation from {lang_file}: {e}")
        _translations = {}
        if lang_code != _default_language:
            set_language(_default_language, locales_dir) 

def t(key, **kwargs):
    """Obtiene una traducción por clave, con soporte para f-string like formatting."""
    translated_text = _translations.get(key, key) # Devuelve la clave si no se encuentra la traducción
    try:
        return translated_text.format(**kwargs)
    except KeyError:
        logger.warning(f"Missing format key in translation for '{key}': '{translated_text}' with kwargs {kwargs}")
        return translated_text # Devuelve sin formatear si faltan claves

def get_available_languages():
    """Devuelve una lista de los códigos de idioma disponibles (nombres de archivo sin .json)."""
    if not os.path.exists(get_locales_dir()): # Usa la nueva get_locales_dir
        logger.warning(f"Locales directory does not exist: {get_locales_dir()}")
        return [_default_language]
    
    languages = [f.split('.')[0] for f in os.listdir(get_locales_dir()) if f.endswith('.json')]
    return sorted(list(set(languages)))

def set_language(lang_code, locales_dir=None): # Ahora puede recibir locales_dir
    """Establece el idioma actual y carga las traducciones."""
    global _current_language
    if locales_dir: # Si se proporciona, actualiza la variable global interna
        _current_language = lang_code
        load_translations(lang_code, locales_dir)
        # Una vez que el idioma se ha establecido y cargado, persistir
        # Esta lógica de guardar se moverá a ConfigManager.
    else: # Si no se proporciona, asume que ya se configuró al inicio
        logger.warning("set_language called without locales_dir. Translations might not be loaded correctly if called too early.")
        if _current_language != lang_code:
            _current_language = lang_code
            # No se puede cargar aquí sin locales_dir, asume que ya se hizo


def get_current_language():
    """Obtiene el idioma actual."""
    return _current_language

# Esto ya no es necesario aquí, la ruta se gestionará en InstallerProApp
_locales_dir_cached = None 
def set_locales_dir(path): # Función para establecer la ruta desde fuera
    global _locales_dir_cached
    _locales_dir_cached = path

def get_locales_dir(): # Función para obtener la ruta
    return _locales_dir_cached if _locales_dir_cached else ""