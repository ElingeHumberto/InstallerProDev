import logging
import os
import sys
from datetime import datetime

def setup_logging():
    log_file_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'InstallerPro', 'installerpro.log')
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    root_logger = logging.getLogger()
    # root_logger.setLevel(logging.INFO) # Comenta o cambia a DEBUG para ver todos los mensajes
    root_logger.setLevel(logging.DEBUG) # <--- ASEGÚRATE QUE ESTÉ ASÍ (o al menos INFO)

    # Configuración básica del logger
    logging.basicConfig(
        level=logging.INFO, # Nivel mínimo de log
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file_path, encoding='utf-8'),
            logging.StreamHandler(sys.stdout) # También imprime en consola
        ]
    )
    # Establecer niveles de log específicos para módulos para controlar la verbosidad
    logging.getLogger('installerpro.core.git_operations').setLevel(logging.INFO) # Para ver info de Git
    logging.getLogger('installerpro.core.project_manager').setLevel(logging.INFO) # Para ver info del ProjectManager
    logging.getLogger('installerpro.i18n').setLevel(logging.INFO) # Para ver info de i18n
    
    return logging.getLogger('installerpro') # Devuelve el logger principal de la app