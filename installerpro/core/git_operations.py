import subprocess
import os
import logging
import sys

logger = logging.getLogger(__name__)

class GitOperationError(Exception):
    """Excepción personalizada para errores de operaciones Git."""
    pass

def _run_cmd_with_output(command, cwd=None):
    """
    Ejecuta un comando de shell y devuelve la salida y el código de retorno.
    Captura stdout y stderr en tiempo real.
    """
    logger.debug(f"Ejecutando comando: {' '.join(command)} en {cwd or os.getcwd()}")
    
    # Usar cp1252 para Windows por problemas de codificación comunes
    encoding_to_use = 'cp1252' if sys.platform == "win32" else 'utf-8'

    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding=encoding_to_use, 
        errors='replace',  # Reemplazar caracteres no decodificables
        bufsize=1
    )

    stdout_lines = []
    stderr_lines = []

    # Leer stdout y stderr en tiempo real
    while True:
        stdout_line = process.stdout.readline()
        stderr_line = process.stderr.readline()

        if stdout_line:
            stdout_lines.append(stdout_line.strip())
            # Solo logear INFO en _run_cmd_with_output, el logger principal del App mostrará al usuario
            logger.info(f"GIT_OUT: {stdout_line.strip()}") 
        if stderr_line:
            stderr_lines.append(stderr_line.strip())
            logger.error(f"GIT_ERR: {stderr_line.strip()}") 

        # Si ambos están vacíos y el proceso terminó, salir
        if not stdout_line and not stderr_line and process.poll() is not None:
            break

    return_code = process.wait()
    return return_code, "\n".join(stdout_lines), "\n".join(stderr_lines)

def _add_safe_directory(path):
    """Añade una ruta al listado de directorios seguros de Git globalmente."""
    logger.info(f"Intentando añadir '{path}' a la lista de directorios seguros de Git.")
    command = ["git", "config", "--global", "--add", "safe.directory", os.path.normpath(path)]
    return_code, stdout, stderr = _run_cmd_with_output(command)
    if return_code == 0:
        logger.info(f"'{path}' añadido a directorios seguros de Git.")
        return True
    else:
        logger.error(f"Fallo al añadir '{path}' a directorios seguros. Error: {stderr}")
        return False

def run_git_operation(project_path, operation_name, *git_args):
    """
    Ejecuta una operación Git en un hilo seguro, con manejo de stash y dubious ownership.
    project_path: Ruta local del repositorio.
    operation_name: Nombre de la operación (ej. "pull", "clone", "checkout").
    git_args: Argumentos específicos del comando Git (ej. ["pull", "origin", "main"]).
    """
    # Validar que el directorio existe para la mayoría de operaciones excepto clone
    if not os.path.isdir(project_path) and operation_name != "clone":
        # Para 'clone', el directorio final no existirá, pero sí su padre.
        # Si el padre no existe, lo creamos.
        if operation_name == "clone":
            parent_dir = os.path.dirname(project_path)
            if not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                logger.info(f"Creado directorio padre para clonación: {parent_dir}")
        else:
            logger.error(f"El directorio del proyecto no existe o no es un directorio: {project_path}")
            raise GitOperationError(f"El directorio '{project_path}' no existe para la operación '{operation_name}'.")

    # Asegurarse de que project_path sea una ruta absoluta y normalizada
    project_path = os.path.normpath(project_path)

    max_retries = 2
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Reintentando operación Git '{operation_name}' (Intento {attempt}/{max_retries-1})...")

        # --- Manejo de Stash (solo para operaciones que pueden tener conflictos como pull/checkout) ---
        # Asegúrate de que solo se haga stash si el directorio es un repo Git
        stashed = False
        if operation_name in ["pull", "checkout", "switch"] and os.path.isdir(os.path.join(project_path, ".git")):
            logger.info(f"Intentando guardar cambios locales (git stash) antes de '{operation_name}'...")
            stash_return_code, stash_stdout, stash_stderr = _run_cmd_with_output(["git", "stash", "save", "--include-untracked", "InstallerPro auto-stash"], cwd=project_path)
            # Un código de retorno 0 significa éxito, o el mensaje "No local changes to save" también es un éxito.
            if stash_return_code == 0 or "No local changes to save" in stash_stdout: 
                stashed = True
                logger.info(f"Cambios locales guardados exitosamente o no había cambios para '{project_path}'.")
            else:
                logger.warning(f"No se pudieron guardar los cambios locales para '{project_path}'. Salida: {stash_stdout} {stash_stderr}")
                # Aquí podrías decidir si abortar o continuar. Por ahora, continuamos pero con advertencia.

        # --- Ejecución del comando Git principal ---
        git_command = ["git"] + list(git_args)
        current_cwd = project_path # Para la mayoría de comandos, el cwd es la ruta del proyecto
        if operation_name == "clone":
            # Para 'clone', el cwd debe ser el directorio padre donde se clonará
            current_cwd = os.path.dirname(project_path) 
            # Y el último argumento del comando clone es el nombre de la carpeta final
            git_command[-1] = os.path.basename(project_path)

        return_code, stdout, stderr = _run_cmd_with_output(git_command, cwd=current_cwd)

        # --- Post-operación (stash pop) ---
        if stashed and os.path.isdir(os.path.join(project_path, ".git")): # Solo si se hizo un stash y sigue siendo un repo
            logger.info("Intentando restaurar cambios locales guardados (git stash pop)...")
            pop_return_code, pop_stdout, pop_stderr = _run_cmd_with_output(["git", "stash", "pop"], cwd=project_path)
            if pop_return_code != 0 and "No stash entries found" not in pop_stdout:
                logger.warning(f"Fallo al restaurar cambios locales para '{project_path}'. Por favor, resuelve manualmente. Salida: {pop_stdout} {pop_stderr}")
            else:
                logger.info(f"Cambios locales restaurados exitosamente para '{project_path}' o no había nada que restaurar.")

        # --- Verificación de errores ---
        if return_code != 0:
            full_error_output = f"stdout: {stdout}\nstderr: {stderr}"
            logger.error(f"Operación Git '{operation_name}' falló con código {return_code}. Detalles:\n{full_error_output}")

            if "fatal: detected dubious ownership" in full_error_output:
                if _add_safe_directory(project_path):
                    logger.info(f"Directorio añadido a seguros, reintentando operación '{operation_name}'.")
                    continue # Reintentar la operación después de añadir el directorio seguro
                else:
                    raise GitOperationError(f"Falló la operación Git '{operation_name}' y no se pudo añadir el directorio a la lista de seguros: {full_error_output}")
            else:
                # Si el error es de "pathspec 'main' did not match" durante checkout,
                # ProjectManager decidirá qué hacer (ej. intentar otra rama o marcar como error).
                raise GitOperationError(f"Falló la operación Git '{operation_name}': {full_error_output}")
        else:
            logger.info(f"Operación Git '{operation_name}' completada exitosamente en '{project_path}'.")
            return stdout # Devuelve la salida estándar del comando Git

    # Si llegamos aquí después de los reintentos y aún falló
    raise GitOperationError(f"La operación Git '{operation_name}' falló después de múltiples reintentos y correcciones.")


# Funciones de alto nivel para ProjectManager que usarán run_git_operation
def git_clone_project(repo_url, local_path, branch="main"):
    """Clona un repositorio Git."""
    # Asegúrate de que local_path sea el directorio final donde estará el repo
    return run_git_operation(local_path, "clone", "clone", "--branch", branch, repo_url, local_path)

def git_pull_project(local_path, branch="main"):
    """Realiza un pull en un repositorio Git."""
    # Asegúrate de que local_path sea el directorio del repo
    run_git_operation(local_path, "fetch", "fetch", "origin") # Primero fetch para obtener la rama remota
    run_git_operation(local_path, "checkout", "checkout", branch) # Asegurarse de estar en la rama correcta
    return run_git_operation(local_path, "pull", "pull", "origin", branch) # Luego pull

def git_push_project(local_path):
    """Realiza un push en un repositorio Git."""
    return run_git_operation(local_path, "push", "push", "origin")

def git_get_status(local_path):
    """Obtiene el estado de un repositorio Git."""
    # --porcelain para salida fácil de parsear por programa
    return run_git_operation(local_path, "status", "status", "--porcelain", "--branch") 

def git_get_current_branch(local_path):
    """Obtiene la rama actual de un repositorio Git."""
    # rev-parse --abbrev-ref HEAD es la forma de obtener la rama actual
    output = run_git_operation(local_path, "branch_name", "rev-parse", "--abbrev-ref", "HEAD")
    return output.strip() if output else "unknown"

def git_is_repo(path):
    """Verifica si una ruta es un repositorio Git."""
    return os.path.isdir(os.path.join(path, ".git"))