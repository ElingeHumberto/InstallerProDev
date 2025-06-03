# installerpro/i18n.py
import json
import os
import logging

logger = logging.getLogger(__name__)

# Variables globales para el estado de la internacionalización
_current_language = "en"
_translations = {}
_default_language = "en"
_locales_dir = None # Esta variable debe ser establecida por la aplicación principal

def _load_translations(lang_code):
    """
    Carga las traducciones para un código de idioma específico en la variable global _translations.
    Asume que _locales_dir ya ha sido establecido.
    """
    global _translations
    
    if not _locales_dir or not os.path.exists(_locales_dir):
        logger.error(f"Translation directory not set or does not exist: {_locales_dir}. Cannot load translations.")
        _translations = {}
        return False # Fallo al cargar

    lang_file = os.path.normpath(os.path.join(_locales_dir, f'{lang_code}.json'))
    
    logger.debug(f"Attempting to load translations from: {lang_file}")

    if not os.path.exists(lang_file):
        logger.warning(f"Language file '{lang_file}' not found.")
        _translations = {} # Limpiar traducciones si el archivo no existe
        return False # Fallo al cargar

    try:
        with open(lang_file, 'r', encoding='utf-8') as f:
            _translations = json.load(f)
        logger.info(f"Translations loaded for '{lang_code}' from '{lang_file}'.")
        return True # Éxito al cargar
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {lang_file}. Invalid format. Error: {e}")
        _translations = {}
        return False # Fallo al cargar
    except Exception as e:
        logger.error(f"An unexpected error occurred loading translation from {lang_file}: {e}")
        _translations = {}
        return False # Fallo al cargar

def t(key, **kwargs):
    """
    Traduce una clave dada, con interpolación de variables opcional.
    Usa la traducción cargada para el idioma actual (_translations).
    """
    # Si no hay traducciones cargadas, o la clave no existe, devolver la clave sin traducir.
    if not _translations or key not in _translations:
        return key
    
    translated_text = _translations.get(key, key)

    if kwargs:
        try:
            return translated_text.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing placeholder '{e}' in translation for key '{key}' (lang: {_current_language}). Original: '{translated_text}'")
            return translated_text
        except Exception as e:
            logger.error(f"Error formatting translation for key '{key}' (lang: {_current_language}): {e}. Original: '{translated_text}'")
            return translated_text
    return translated_text

def get_available_languages():
    """
    Retorna una lista de códigos de idioma disponibles basándose en los archivos .json en _locales_dir.
    """
    if not _locales_dir or not os.path.exists(_locales_dir):
        logger.warning(f"Locales directory not set or does not exist: {_locales_dir}. Cannot get available languages.")
        return [_default_language] # Fallback a solo el idioma por defecto

    available_langs = []
    try:
        for f_name in os.listdir(_locales_dir):
            if f_name.endswith('.json'):
                lang_code = f_name[:-5]
                # Opcional: Validar JSON antes de añadirlo a la lista de disponibles
                try:
                    with open(os.path.join(_locales_dir, f_name), 'r', encoding='utf-8') as f:
                        json.load(f) # Intentar cargar para validar
                    available_langs.append(lang_code)
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed translation file: {f_name}")
                except Exception as e:
                    logger.warning(f"Error reading translation file {f_name} during scan: {e}")
        if _default_language not in available_langs:
            available_langs.append(_default_language)
        return sorted(list(set(available_langs)))
    except Exception as e:
        logger.error(f"An unexpected error occurred while listing available languages in {_locales_dir}: {e}")
        return [_default_language] # Fallback en caso de error inesperado

def set_language(lang_code):
    """
    Establece el idioma actual de la aplicación y recarga las traducciones.
    Esta función es llamada por la aplicación principal.
    """
    global _current_language
    global _locales_dir

    # Si el directorio de locales no está establecido, no podemos cargar nada
    if not _locales_dir or not os.path.exists(_locales_dir):
        logger.error(f"Locales directory not set or does not exist: {_locales_dir}. Cannot set language.")
        _current_language = _default_language # Forzar a default si no hay locales
        _translations.clear() # Limpiar traducciones
        return False # Falló

    # Verificar si el idioma solicitado está disponible
    if lang_code not in get_available_languages():
        logger.warning(f"Attempted to set unsupported language: '{lang_code}'. Falling back to default: '{_default_language}'.")
        lang_code = _default_language # Usar el idioma por defecto si el solicitado no está disponible
    
    # Solo recargar si el idioma es diferente o si las traducciones no están cargadas
    if _current_language != lang_code or not _translations:
        _current_language = lang_code
        if _load_translations(_current_language): # Intentar cargar las traducciones
            logger.info(f"Application language set to: {_current_language}.")
            return True # Idioma cambiado/cargado con éxito
        else:
            logger.error(f"Failed to load translations for '{_current_language}'. Falling back to default.")
            _current_language = _default_language # Forzar a default si la carga falla
            _translations.clear() # Limpiar traducciones
            return False # Falló la carga
    
    logger.debug(f"Language already set to {lang_code}. No reload needed.")
    return False # No hubo cambio efectivo o ya estaba cargado

def get_current_language():
    """Retorna el código del idioma actual."""
    return _current_language

def set_locales_dir(path):
    """
    Establece el directorio de locales donde se encuentran los archivos de traducción.
    Esta función debe ser llamada por la aplicación principal al inicio.
    """
    global _locales_dir
    _locales_dir = os.path.normpath(path)
    logger.debug(f"Locales directory set to: {_locales_dir}")

def get_locales_dir():
    """Retorna el directorio de locales actual."""
    return _locales_dir
