# installerpro/i18n.py
import os
import json
import logging

logger = logging.getLogger(__name__)

_translations = {}
_current_language = 'en' # Idioma predeterminado
_default_language = 'en' # Idioma de fallback si no se encuentra el actual
_locales_dir = None # Directorio donde se encuentran los archivos .json de traducción


def load_translations(lang_code, locales_dir):
    """Carga las traducciones para un código de idioma específico."""
    global _translations
    lang_file = os.path.normpath(os.path.join(locales_dir, f'{lang_code}.json'))

    logger.debug(f"Attempting to load translations from: {lang_file}") 

    if not os.path.exists(locales_dir): 
        logger.error(f"Translation directory not found: {locales_dir}. Translations will not be loaded.")
        _translations = {}
        return

    if not os.path.exists(lang_file): 
        logger.warning(f"Language file '{lang_file}' not found. Falling back to default: '{_default_language}'.")
        if lang_code != _default_language:
            load_translations(_default_language, locales_dir) # Intentar cargar el idioma predeterminado
            return

    try:
        with open(lang_file, 'r', encoding='utf-8') as f:
            _translations = json.load(f)
        logger.info(f"Translations loaded for '{lang_code}' from '{lang_file}'.")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {lang_file}. Invalid format. Falling back to default language. Error: {e}")
        _translations = {}
        if lang_code != _default_language:
            set_language(_default_language, locales_dir) # Volver a establecer para cargar default
    except Exception as e:
        logger.error(f"An unexpected error occurred loading translation from {lang_file}: {e}")
        _translations = {}
        if lang_code != _default_language:
            set_language(_default_language, locales_dir) # Volver a establecer para cargar default

def t(key, **kwargs):
    """Traduce una clave dada, con interpolación de variables opcional.
    Usa la traducción cargada para el idioma actual.
    """
    global _translations

    # Si no hay traducciones cargadas, o la clave no existe, devolver la clave sin traducir.
    # Esto asegura que siempre haya un valor de retorno.
    if not _translations or key not in _translations:
        return key

    translated_text = _translations.get(key, key) # Si no la encuentra, devuelve la clave

    # Si hay argumentos adicionales, hacer la interpolación
    if kwargs:
        try:
            # Usa f-strings para la interpolación si todas las claves son válidas en la cadena
            # Esto es más flexible que .format() si las claves no son siempre positional
            return translated_text.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing placeholder in translation for key '{key}'. Error: {e}")
            return translated_text # Devuelve el texto sin interpolar si hay un error
        except IndexError as e:
            logger.error(f"Positional placeholder error in translation for key '{key}'. Error: {e}")
            return translated_text # Devuelve el texto sin interpolar si hay un error
        except Exception as e:
            logger.error(f"An unexpected error occurred formatting translation for key '{key}': {e}")
            return translated_text # Fallback general si ocurre otro error de formato

    return translated_text # Si no hay kwargs, devuelve el texto traducido directamente

def get_available_languages():
    """Retorna una lista de códigos de idioma disponibles."""
    if _locales_dir and os.path.exists(_locales_dir):
        return [f.replace('.json', '') for f in os.listdir(_locales_dir) if f.endswith('.json')]
    return [_default_language]

def set_language(lang_code, locales_dir=None):
    """Establece el idioma actual y carga sus traducciones.
    Si locales_dir no se proporciona, usa el _locales_dir previamente establecido.
    """
    global _current_language

    # Si se proporciona un nuevo locales_dir, actualiza la variable global.
    if locales_dir:
        set_locales_dir(locales_dir)

    if _locales_dir: # Procede solo si _locales_dir está definido
        if lang_code in get_available_languages():
            _current_language = lang_code
            load_translations(lang_code, _locales_dir)
            logger.info(f"Language set to: {_current_language}")
        else:
            logger.warning(f"Language '{lang_code}' not available. Keeping current language: {_current_language}. Available: {get_available_languages()}")
            # Intentar cargar el idioma predeterminado si el solicitado no está disponible
            if _current_language != _default_language: # Previene loop infinito
                set_language(_default_language, _locales_dir)
    else:
        logger.error("Locales directory not set. Cannot set language.")


def get_current_language():
    """Retorna el código del idioma actual."""
    return _current_language

def set_locales_dir(path):
    """Establece el directorio de locales donde se encuentran los archivos de traducción."""
    global _locales_dir
    _locales_dir = os.path.normpath(path)
    logger.debug(f"Locales directory set to: {_locales_dir}")

def get_locales_dir():
    """Retorna el directorio de locales actual."""
    return _locales_dir