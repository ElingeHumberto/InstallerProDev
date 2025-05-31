# C:\Workspace\InstallerProDev\test_i18n.py
import sys
import os

# Añadir la raíz del proyecto a sys.path para que pueda encontrar 'installerpro'
project_root_dir = os.path.abspath(os.path.dirname(__file__))
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

try:
    # Importar el módulo i18n
    import installerpro.i18n as i18n
    print("Módulo installerpro.i18n importado exitosamente.")

    # Intentar acceder a la función 't'
    if hasattr(i18n, 't'):
        print("La función 't' existe en installerpro.i18n.")

        # Intentar usar la función 't'
        print(f"Idiomas disponibles: {i18n.get_available_languages()}")

        # Asegurarse de que los archivos JSON existen antes de intentar cargar
        if "en" in i18n.get_available_languages():
            i18n.set_language("en")
            translated_text = i18n.t("App Title")
            print(f"Traducción de 'App Title' (en): {translated_text}")
        else:
            print("Advertencia: 'en.json' no encontrado o no listado en idiomas disponibles.")

        if "es" in i18n.get_available_languages():
            i18n.set_language("es")
            translated_text_es = i18n.t("App Title")
            print(f"Traducción de 'App Title' (es): {translated_text_es}")
        else:
            print("Advertencia: 'es.json' no encontrado o no listado en idiomas disponibles.")

        print("Prueba de i18n.t completada exitosamente.")
    else:
        print("ERROR: La función 't' NO se encontró en installerpro.i18n.")
        print(f"Contenido de dir(i18n): {dir(i18n)}") # Muestra qué hay en el módulo
except ImportError as e:
    print(f"ERROR: No se pudo importar installerpro.i18n. Asegúrate de que la estructura de carpetas y los __init__.py sean correctos. Error: {e}")
    print(f"sys.path actual: {sys.path}")
except Exception as e:
    print(f"ERROR inesperado durante la prueba de i18n: {e}")