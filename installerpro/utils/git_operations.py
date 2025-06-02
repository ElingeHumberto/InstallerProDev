# installerpro/core/git_operations.py
import subprocess
import os
import logging

logger = logging.getLogger(__name__)

class GitOperationError(Exception):
    """Excepción personalizada para errores en operaciones Git."""
    pass

def _run_git_command(command, cwd):
    """
    Ejecuta un comando Git y captura su salida y errores.
    Lanza GitOperationError si el comando falla.
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True, # Lanza CalledProcessError si el código de salida no es 0
            encoding='utf-8'
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        error_message = f"Git command failed: {e.cmd}\nStdout: {e.stdout}\nStderr: {e.stderr}"
        logger.error(error_message)
        raise GitOperationError(f"Git command failed: {e.stderr.strip() or e.stdout.strip()}")
    except FileNotFoundError:
        logger.error("Git executable not found. Please ensure Git is installed and in your PATH.")
        raise GitOperationError("Git executable not found. Please install Git.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during Git operation: {e}")
        raise GitOperationError(f"An unexpected error occurred: {e}")

def clone_repository(repo_url, local_path, branch=None):
    """Clona un repositorio Git."""
    logger.info(f"Cloning '{repo_url}' into '{local_path}'...")
    command = ["git", "clone", repo_url, local_path]
    if branch:
        command.extend(["--branch", branch])
    _run_git_command(command, os.path.dirname(local_path) if os.path.exists(local_path) else os.getcwd())
    logger.info(f"Repository '{repo_url}' cloned successfully.")

def pull_repository(local_path):
    """Realiza un 'git pull' en un repositorio existente."""
    logger.info(f"Pulling changes for repository in '{local_path}'...")
    output = _run_git_command(["git", "pull"], local_path)
    logger.info(f"Pull complete for '{local_path}': {output}")
    return output

def push_repository(local_path):
    """Realiza un 'git push' en un repositorio existente."""
    logger.info(f"Pushing changes for repository in '{local_path}'...")
    output = _run_git_command(["git", "push"], local_path)
    logger.info(f"Push complete for '{local_path}': {output}")
    return output

def get_repo_status(local_path):
    """Obtiene el estado de un repositorio (limpio, modificado, etc.)."""
    try:
        # Verifica si hay cambios sin commit
        status_output = _run_git_command(["git", "status", "--porcelain"], local_path)
        if status_output:
            return "Modified" # Hay cambios sin commit
        
        # Verifica si hay commits locales no empujados
        local_ahead_output = _run_git_command(["git", "rev-list", "@{u}..HEAD"], local_path)
        if local_ahead_output:
            return "Local Commits" # Hay commits locales no empujados

        # Verifica si hay cambios remotos no pullados
        _run_git_command(["git", "remote", "update"], local_path) # Actualiza la información del remoto
        remote_ahead_output = _run_git_command(["git", "rev-list", "HEAD..@{u}"], local_path)
        if remote_ahead_output:
            return "Needs Pull" # Hay cambios remotos no pullados

        return "Clean" # No hay cambios locales ni remotos pendientes
    except GitOperationError as e:
        logger.warning(f"Could not get Git status for '{local_path}': {e}")
        return f"Error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error getting Git status for '{local_path}': {e}")
        return f"Error: {e}"

def is_git_repository(path):
    """Verifica si una ruta es un repositorio Git válido."""
    return os.path.isdir(os.path.join(path, ".git"))