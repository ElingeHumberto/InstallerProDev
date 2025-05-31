# installerpro/core/logging_config.py
import logging
import os
import sys 
from datetime import datetime

def setup_logging(log_file="installerpro.log", level=logging.INFO):
    """
    Configura el sistema de logging para la aplicación.
    Los logs se escribirán en un archivo y también se mostrarán en la consola.
    """
    # Crear el directorio de logs si no existe
    log_dir = os.path.join(os.path.expanduser("~"), ".installerpro_logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    # Configuración básica del logger
    # Asegúrate de que el logger raíz no tenga ya handlers para evitar duplicados
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout) # Salida a consola
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Logging configured.")
    return logger

# Si este módulo se importa, el logging se configurará automáticamente.
# Puedes llamar a setup_logging() explícitamente si necesitas cambiar la configuración en tiempo de ejecución.