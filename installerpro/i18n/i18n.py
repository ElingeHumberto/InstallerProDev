import os
import json

# Estado global para las funciones t()/set_language()
_global_translations = {}

def available_langs() -> list[str]:
    base = os.path.dirname(__file__)
    return [f[:-5] for f in os.listdir(base) if f.endswith(".json")]

def _flatten(d: dict, parent: str = "") -> dict:
    items = {}
    for k, v in d.items():
        key = f"{parent}.{k}" if parent else k
        if isinstance(v, dict):
            items.update(_flatten(v, key))
        else:
            items[key] = v
    return items

def _load(lang: str) -> dict:
    path = os.path.join(os.path.dirname(__file__), f"{lang}.json")
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return _flatten(raw)

def set_language(lang: str) -> None:
    global _global_translations
    _global_translations = _load(lang)

def t(key: str) -> str:
    return _global_translations.get(key, key)

class I18n:
    """
    Instancias independientes de traductor.
    i18n = I18n("es")
    print(i18n("button.add"))  # → "Añadir"
    """
    def __init__(self, lang: str):
        self._lang = None
        self._translations = {}
        self.set_language(lang)

    @property
    def current_lang(self) -> str:
        return self._lang

    def set_language(self, lang: str) -> None:
        self._lang = lang
        self._translations = _load(lang)

    def __call__(self, key: str) -> str:
        return self._translations.get(key, key)
