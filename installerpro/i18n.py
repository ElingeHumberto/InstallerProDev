# installerpro/i18n.py
import json
import os
import logging
import locale # Importar locale

logger = logging.getLogger(__name__)

_current_language = "en"
_translations = {}
_default_language = "en"
_locales_dir = None

def _load_translations(lang_code_to_load):
    global _translations
    if not _locales_dir or not os.path.exists(_locales_dir):
        logger.error(f"Translation directory not set or does not exist: {_locales_dir}. Cannot load translations.")
        _translations = {}
        return False

    lang_file = os.path.normpath(os.path.join(_locales_dir, f'{lang_code_to_load}.json'))
    logger.debug(f"Attempting to load translations from: {lang_file}")

    if not os.path.exists(lang_file):
        logger.warning(f"Language file '{lang_file}' not found for lang_code '{lang_code_to_load}'.")
        _translations = {}
        return False

    try:
        with open(lang_file, 'r', encoding='utf-8') as f:
            _translations = json.load(f)
        logger.info(f"Translations loaded for '{lang_code_to_load}' from '{lang_file}'.")
        return True
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {lang_file}. Invalid format. Error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred loading translation from {lang_file}: {e}")
    
    _translations = {} # Clear on any error during load
    return False

def t(key, **kwargs):
    if not _translations or key not in _translations:
        return key
    
    translated_text = _translations.get(key, key)

    if kwargs:
        try:
            return translated_text.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing placeholder '{e}' in translation for key '{key}' (lang: {_current_language}). Original: '{translated_text}'")
        except Exception as e:
            logger.error(f"Error formatting translation for key '{key}' (lang: {_current_language}): {e}. Original: '{translated_text}'")
        return translated_text # Return unformatted on error
    return translated_text

def get_available_languages():
    if not _locales_dir or not os.path.exists(_locales_dir):
        logger.warning(f"Locales directory not set or does not exist: {_locales_dir}. Cannot get available languages.")
        return [_default_language] 

    available_langs = []
    try:
        for f_name in os.listdir(_locales_dir):
            if f_name.endswith('.json'):
                lang_code = f_name[:-5]
                try:
                    # Validate JSON structure lightly by trying to load it
                    with open(os.path.join(_locales_dir, f_name), 'r', encoding='utf-8') as f_val:
                        json.load(f_val)
                    available_langs.append(lang_code)
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed translation file: {f_name}")
                except Exception as e_read:
                    logger.warning(f"Error reading translation file {f_name} during scan: {e_read}")
        
        # Ensure default language is always considered "available" conceptually,
        # even if its file is missing (load will fail later, but it should be an option).
        if _default_language not in available_langs:
            # This might be misleading if en.json is truly missing.
            # get_available_languages should reflect files truly present and valid.
            # For now, let's assume _default_language file should exist.
            # Or, filter here based on os.path.exists for the default lang file if strictness is needed.
            pass # Let's not add it if its file isn't found/valid.

        return sorted(list(set(available_langs))) if available_langs else [_default_language]
    except Exception as e:
        logger.error(f"An unexpected error occurred while listing available languages in {_locales_dir}: {e}")
        return [_default_language]

def set_language(lang_code_to_set):
    global _current_language, _translations

    if not _locales_dir: # Basic check
        logger.error("Locales directory not set. Cannot change language.")
        return False

    available_languages = get_available_languages()
    logger.debug(f"Setting language to '{lang_code_to_set}'. Available: {available_languages}")

    target_lang = lang_code_to_set
    if target_lang not in available_languages:
        logger.warning(f"Language '{target_lang}' not in available languages {available_languages}. Attempting to fall back to default '{_default_language}'.")
        target_lang = _default_language
        if target_lang not in available_languages: # If default itself is not found (e.g. en.json missing)
            logger.error(f"Default language '{_default_language}' also not available. Cannot set language.")
            _translations.clear() # No valid language can be loaded
            # _current_language remains what it was, or becomes _default_language (but without translations)
            _current_language = _default_language # Set to default code, even if not loadable
            return False 

    # If target language is already current and translations are loaded, it's a success.
    if _current_language == target_lang and _translations:
        logger.info(f"Language already set to '{target_lang}' and translations loaded.")
        return True

    # Attempt to load the target language
    if _load_translations(target_lang):
        _current_language = target_lang
        logger.info(f"Application language successfully set to: {_current_language}.")
        return True
    else:
        # Failed to load target_lang, try to load default language if it's different
        logger.error(f"Failed to load translations for '{target_lang}'.")
        if target_lang != _default_language: # Avoid re-trying default if target_lang was already default
            logger.warning(f"Attempting to fall back to default language: '{_default_language}'.")
            if _default_language in available_languages and _load_translations(_default_language):
                _current_language = _default_language
                logger.info(f"Application language successfully fell back to default: '{_current_language}'.")
                return True
        
        # All attempts failed (target, and default if different)
        logger.error(f"CRITICAL: Could not load translations for '{target_lang}' or the default language.")
        _current_language = _default_language # Set to default code, even if not loadable
        _translations.clear()
        return False

def get_current_language():
    return _current_language

def set_locales_dir(path):
    global _locales_dir
    _locales_dir = os.path.normpath(path)
    logger.debug(f"Locales directory set to: {_locales_dir}")
    # It might be good to call _load_translations(_current_language) here
    # or ensure an initial language is set after this path is confirmed.
    # However, your main app calls i18n.set_language after this.

def get_system_language_code():
    try:
        sys_locale_full, _ = locale.getdefaultlocale()
        if sys_locale_full:
            lang_part = sys_locale_full.split('_')[0].lower()
            logger.debug(f"Detected system language code: {lang_part} from {sys_locale_full}")
            return lang_part
    except Exception as e:
        logger.warning(f"Could not detect system language: {e}. Falling back.")
    return None # Return None to indicate detection failure or undetermined