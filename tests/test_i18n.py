import os
import json
import pytest
import installerpro.i18n as i18n_mod
from installerpro.i18n import available_langs, set_language, t, I18n

def test_json_files_well_formed():
    base = os.path.dirname(i18n_mod.__file__)
    for lang in ("en", "es"):
        path = os.path.join(base, f"{lang}.json")
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict)

def test_available_langs_lists_all():
    langs = available_langs()
    assert "en" in langs and "es" in langs

def test_set_language_and_translate():
    set_language("es")
    assert t("button.add") == "Añadir"
    set_language("en")
    assert t("button.add") == "Add"

def test_i18n_class_independent_state():
    es_trans = I18n("es")
    en_trans = I18n("en")
    # Cada instancia arranca con su propio idioma
    assert es_trans("button.add") == "Añadir"
    assert en_trans("button.add") == "Add"
    # Cambiar es_trans no afecta a en_trans
    es_trans.set_language("en")
    assert es_trans("button.add") == "Add"
    assert en_trans("button.add") == "Add"
