# installerpro/core/security_analyzer.py
import re
import os
import logging

logger = logging.getLogger(__name__)

# Una lista inicial de patrones de secretos (expresiones regulares)
# La iremos expandiendo, pero esta es una buena base.
SECRET_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "Stripe Live Key": r"sk_live_[0-9a-zA-Z]{24}",
    "Generic API Key": r"(api|token|key|secret).{0,20}['\"_ ]{0,3}[0-9a-zA-Z]{32,}",
    "RSA Private Key": r"-----BEGIN RSA PRIVATE KEY-----",
}

def scan_files_for_secrets(file_paths, project_path):
    """
    Escanea una lista de archivos en busca de posibles secretos.
    Devuelve una lista de hallazgos. Cada hallazgo es un diccionario.
    """
    logger.info(f"Iniciando escaneo de seguridad en {len(file_paths)} archivos.")
    findings = []

    for file_path_relative in file_paths:
        # Construimos la ruta completa del archivo
        file_path_full = os.path.join(project_path, file_path_relative)

        try:
            if not os.path.exists(file_path_full):
                continue

            with open(file_path_full, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    for secret_name, pattern in SECRET_PATTERNS.items():
                        if re.search(pattern, line, re.IGNORECASE):
                            findings.append({
                                "file": file_path_relative,
                                "line": line_num,
                                "type": secret_name,
                            })
                            # Opcional: break para no reportar múltiples secretos en la misma línea
                            break 
        except Exception as e:
            logger.error(f"No se pudo escanear el archivo {file_path_full}: {e}")

    if findings:
        logger.warning(f"Se encontraron {len(findings)} posibles secretos.")
    else:
        logger.info("Escaneo de seguridad completado. No se encontraron secretos.")
        
    return findings