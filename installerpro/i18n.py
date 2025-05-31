# installerpro/i18n.py
import json
import os
import logging

logger = logging.getLogger(__name__)

_translations = {}
_current_language = "en" # Idioma por defecto

def load_translations(lang_code):
    """
    Carga las traducciones para un código de idioma específico.
    """
    global _translations
    # La carpeta 'locales' está dentro de 'utils', y 'i18n.py' está en 'installerpro'
    # Así que necesitamos construir la ruta a la carpeta locales:
    # C:\Workspace\InstallerProDev\installerpro\utils\locales
    current_i18n_dir = os.path.abspath(os.path.dirname(__file__))
    locales_dir = os.path.join(current_i18n_dir, "utils", "locales")

    lang_file = os.path.join(locales_dir, f'{lang_code}.json')

    if os.path.exists(lang_file):
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                _translations = json.load(f)
            logger.info(f"Translations loaded for language: {lang_code} from {lang_file}")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {lang_file}: {e}")
            _translations = {} # Reset translations on error
            return False
        except Exception as e:
            logger.error(f"Unexpected error loading translations from {lang_file}: {e}")
            _translations = {}
            return False
    else:
        logger.warning(f"Translation file not found: {lang_file}")
        _translations = {} # Reset translations if file not found
        return False

def t(key, lang=None, **kwargs):
    """
    Traduce una clave dada al idioma actual o especificado.
    Permite el formato de cadena usando kwargs.
    Ej: t("greeting", name="World")
    """
    language_to_use = lang if lang else _current_language

    # Si no hay traducciones cargadas O si las traducciones cargadas no corresponden al idioma deseado,
    # intenta cargarlas.
    # Nota: `list(_translations.keys())` podría estar vacío si _translations está vacío.
    # Se debe verificar que _translations no esté vacío antes de intentar acceder a sus claves.
    current_loaded_lang = None
    if _translations:
        # Intentamos obtener la primera clave si _translations no está vacío.
        # Esto es un proxy para saber qué idioma está cargado actualmente.
        # Una mejor práctica sería almacenar el idioma cargado en una variable global.
        # Por ahora, nos basamos en que la primera clave del JSON cargado a menudo indica el idioma.
        # Sin embargo, para mayor robustez, es mejor simplemente recargar si el idioma actual no coincide.
        pass # La lógica de load_translations ya maneja esto.

    # Siempre intentar cargar las traducciones para el idioma deseado si no están ya cargadas o si el idioma no coincide.
    # La función `load_translations` ya gestiona si el archivo existe y lo carga.
    if not _translations or _current_language != language_to_use:
        if not load_translations(language_to_use):
             logger.warning(f"No translations available for '{language_to_use}' when trying to translate key '{key}'. Attempting fallback to 'en'.")
             # Fallback: intentar con inglés si falló el idioma deseado
             if language_to_use != "en":
                 if load_translations("en"): # Intenta cargar inglés como fallback
                     if key in _translations:
                         try:
                             return _translations[key].format(**kwargs)
                         except KeyError as e:
                             logger.error(f"Missing format key '{e}' in English fallback translation for '{key}'. Translated text: '{_translations[key]}'")
                             return _translations[key]
                 else:
                     logger.warning("Failed to load English translations as fallback.")
             return key # Si no se pudo traducir ni con el idioma deseado ni con el fallback, devuelve la clave.


    translated_text = _translations.get(key, key) # Devuelve la clave si no se encuentra la traducción
    try:
        return translated_text.format(**kwargs)
    except KeyError as e:
        logger.error(f"Missing format key '{e}' in translation for '{key}' in language '{language_to_use}'. Translated text: '{translated_text}'")
        return translated_text # Devuelve el texto sin formato si falta una clave
    except Exception as e:
        logger.error(f"Unexpected error formatting translation for '{key}' in language '{language_to_use}': {e}. Translated text: '{translated_text}'")
        return translated_text


def set_language(lang_code):
    """
    Establece el idioma global de la aplicación y carga sus traducciones.
    """
    global _current_language
    if load_translations(lang_code):
        _current_language = lang_code
        logger.info(f"Application language set to: {_current_language}")
        return True
    else:
        logger.warning(f"Could not set language to {lang_code}. Translations not found or invalid. Current language remains {_current_language}.")
        return False

def get_current_language():
    """
    Devuelve el código del idioma actual.
    """
    return _current_language

def get_available_languages():
    """
    Devuelve una lista de códigos de idiomas disponibles (basado en archivos JSON).
    """
    # Construir la ruta a la carpeta locales:
    current_i18n_dir = os.path.abspath(os.path.dirname(__file__))
    locales_dir = os.path.join(current_i18n_dir, "utils", "locales")

    if not os.path.exists(locales_dir):
        logger.warning(f"Locales directory not found: {locales_dir}")
        return []
    
    languages = []
    try:
        for filename in os.listdir(locales_dir):
            if filename.endswith('.json'):
                lang_code = filename.replace('.json', '')
                languages.append(lang_code)
    except Exception as e:
        logger.error(f"Error listing files in locales directory {locales_dir}: {e}")
    return sorted(languages)

# Cargar el idioma por defecto al inicio
# Esto solo se ejecuta si i18n.py se ejecuta directamente.
# Para la aplicación principal, la carga inicial se maneja en InstallerProApp.
if __name__ == "__main__":
    print(f"Available languages: {get_available_languages()}")
    set_language("es")
    print(f"Current language: {get_current_language()}")
    print(f"Translated 'App Title': {t('App Title')}")
    print(f"Translated 'greeting' with name: {t('greeting', name='Mundo')}")
    set_language("en")
    print(f"Current language: {get_current_language()}")
    print(f"Translated 'App Title': {t('App Title')}")
