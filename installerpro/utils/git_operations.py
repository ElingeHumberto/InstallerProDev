# installerpro/utils/git_operations.py
import subprocess
import os
import logging
import sys
import git

logger = logging.getLogger(__name__)

class GitOperationError(Exception):
    """Excepción personalizada para errores en operaciones Git."""
    pass

def _run_cmd_with_output(command, cwd=None):
    """
    Ejecuta un comando de shell leyendo bytes crudos y decodificando
    explícitamente a UTF-8 para evitar errores de codificación de la consola.
    """
    logger.debug(f"Ejecutando comando: {' '.join(command)} en {cwd or os.getcwd()}")
    
    # --- INICIO DE LA CORRECCIÓN DEFINITIVA ---
    # Ya no confiamos en la decodificación automática de text=True.
    # Leemos los bytes crudos y los decodificamos nosotros a UTF-8.
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1
    )

    stdout_lines = []
    stderr_lines = []

    # Leemos las líneas de bytes de stdout
    for line_bytes in process.stdout:
        line_str = line_bytes.decode('utf-8', errors='replace').strip()
        stdout_lines.append(line_str)
        logger.info(f"GIT_OUT: {line_str}")

    # Leemos las líneas de bytes de stderr
    for line_bytes in process.stderr:
        line_str = line_bytes.decode('utf-8', errors='replace').strip()
        stderr_lines.append(line_str)
        logger.error(f"GIT_ERR: {line_str}")
    # --- FIN DE LA CORRECCIÓN DEFINITIVA ---

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
    project_path = os.path.normpath(project_path)
    
    # Para 'clone', el directorio final no existirá, pero sí su padre.
    if operation_name == "clone":
        parent_dir = os.path.dirname(project_path)
        if not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            logger.info(f"Creado directorio padre para clonación: {parent_dir}")
        current_cwd = parent_dir
        # El último argumento del comando clone es el nombre de la carpeta final
        git_command = ["git"] + list(git_args[:-1]) + [os.path.basename(project_path)]
    else:
        if not os.path.isdir(project_path):
            logger.error(f"El directorio del proyecto no existe o no es un directorio: {project_path}")
            raise GitOperationError(f"El directorio '{project_path}' no existe para la operación '{operation_name}'.")
        current_cwd = project_path
        git_command = ["git"] + list(git_args)

    max_retries = 2
    for attempt in range(max_retries):
        if attempt > 0:
            logger.info(f"Reintentando operación Git '{operation_name}' (Intento {attempt}/{max_retries-1})...")

        stashed = False
        if operation_name in ["pull", "checkout", "switch"] and os.path.isdir(os.path.join(project_path, ".git")):
            logger.info(f"Intentando guardar cambios locales (git stash) antes de '{operation_name}'...")
            stash_return_code, stash_stdout, stash_stderr = _run_cmd_with_output(["git", "stash", "save", "--include-untracked", "InstallerPro auto-stash"], cwd=project_path)
            if stash_return_code == 0 or "No local changes to save" in stash_stdout: 
                stashed = True
                logger.info(f"Cambios locales guardados exitosamente o no había cambios para '{project_path}'.")
            else:
                logger.warning(f"No se pudieron guardar los cambios locales para '{project_path}'. Salida: {stash_stdout} {stash_stderr}")
                # Aquí podrías decidir si abortar o continuar. Por ahora, continuamos pero con advertencia.

        return_code, stdout, stderr = _run_cmd_with_output(git_command, cwd=current_cwd)

        if stashed and os.path.isdir(os.path.join(project_path, ".git")):
            logger.info("Intentando restaurar cambios locales guardados (git stash pop)...")
            pop_return_code, pop_stdout, pop_stderr = _run_cmd_with_output(["git", "stash", "pop"], cwd=project_path)
            if pop_return_code != 0 and "No stash entries found" not in pop_stdout:
                logger.warning(f"Fallo al restaurar cambios locales para '{project_path}'. Por favor, resuelve manualmente. Salida: {pop_stdout} {pop_stderr}")
            else:
                logger.info(f"Cambios locales restaurados exitosamente para '{project_path}' o no había nada que restaurar.")

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
                raise GitOperationError(f"Falló la operación Git '{operation_name}': {full_error_output}")
        else:
            logger.info(f"Operación Git '{operation_name}' completada exitosamente en '{project_path}'.")
            return stdout

    raise GitOperationError(f"La operación Git '{operation_name}' falló después de múltiples reintentos y correcciones.")

# Funciones de alto nivel que project_manager.py usará
# Las funciones que aún dependen de la consola se mantienen
def clone_repository(repo_url, local_path, branch="main"):
    # Esta operación sigue siendo más fácil con subprocess
    return_code, stdout, stderr = _run_cmd_with_output(["git", "clone", "--branch", branch, repo_url, os.path.basename(local_path)], cwd=os.path.dirname(local_path))
    if return_code != 0: raise GitOperationError(f"Failed to clone repository. Error: {stderr}")
    return stdout

def pull_repository(local_path, branch="main"):
    return_code, stdout, stderr = _run_cmd_with_output(["git", "pull", "origin", branch], cwd=local_path)
    if return_code != 0: raise GitOperationError(f"Failed to pull repository. Error: {stderr}")
    return stdout
    
def push_repository(local_path):
    return_code, stdout, stderr = _run_cmd_with_output(["git", "push"], cwd=local_path)
    if return_code != 0: raise GitOperationError(f"Failed to push repository. Error: {stderr}")
    return stdout

def stage_files(local_path, files_to_stage):
    if not files_to_stage: return "No files to stage."
    repo = git.Repo(local_path)
    repo.index.add(files_to_stage)
    logger.info(f"Staged files in {local_path}: {', '.join(files_to_stage)}")
    return "Files staged successfully."

def commit_changes(local_path, commit_message):
    if not commit_message.strip(): raise GitOperationError("Commit message cannot be empty.")
    repo = git.Repo(local_path)
    repo.index.commit(commit_message)
    logger.info(f"Successfully committed in {local_path} with message: {commit_message}")
    return "Commit successful."

# Dentro de git_operations.py

def get_repo_status(local_path):
    """
    Analiza el estado del repositorio y devuelve una clave estandarizada.
    Ej: "clean", "modified", "local_commits", "needs_pull", "unknown"
    """
    try:
        # Obtenemos la salida de 'git status --porcelain --branch'
        stdout = run_git_operation(local_path, "status", "status", "--porcelain", "--branch")

        lines = stdout.strip().split('\n')

        if not lines or not lines[0]:
            return "unknown"

        branch_line = lines[0]
        status_lines = lines[1:]

        # Analizar el estado de la rama (si está adelantado o atrasado)
        if '...' in branch_line:
            if 'ahead' in branch_line:
                return "local_commits"
            if 'behind' in branch_line:
                return "needs_pull"

        # Analizar si hay archivos modificados, nuevos, etc.
        if any(line.strip() for line in status_lines):
            return "modified"

        # Si no hay nada de lo anterior, el repositorio está limpio
        return "clean"
    except GitOperationError:
        # Si la operación de git falla, el estado es desconocido
        return "unknown"

def is_git_repository(path):
    return os.path.isdir(os.path.join(path, ".git"))

def get_repo_current_branch(local_path):
    """Obtiene la rama actual del repositorio con logging detallado."""
    try:
        repo = git.Repo(local_path)
        branch_name = repo.active_branch.name
        logger.info(f"GitPython: Branch for {local_path} is '{branch_name}'")
        return branch_name
    except TypeError:
        logger.warning(f"GitPython: Detached HEAD detected for {local_path}")
        return "detached"
    except Exception as e:
        logger.error(f"GitPython: Could not get branch for {local_path}. ERROR: {e}")
        return "N/A"

def get_repo_remote_url(local_path):
    """Obtiene la URL del remoto 'origin' con logging detallado."""
    try:
        repo = git.Repo(local_path)
        if 'origin' in repo.remotes:
            remote_url = repo.remotes.origin.url
            logger.info(f"GitPython: Remote URL for {local_path} is '{remote_url}'")
            return remote_url
        else:
            logger.warning(f"GitPython: No remote named 'origin' found for {local_path}")
            return "no_remote"
    except Exception as e:
        logger.error(f"GitPython: Could not get remote URL for {local_path}. ERROR: {e}")
        return "N/A"

def get_repo_status(local_path):
    """Analiza el estado del repositorio usando GitPython."""
    try:
        repo = git.Repo(local_path)
        if repo.is_dirty(untracked_files=True):
            return "modified"
        
        # Comprobar commits locales vs remotos
        repo.remotes.origin.fetch()
        commits_ahead = repo.iter_commits('origin/main..main')
        commits_behind = repo.iter_commits('main..origin/main')
        
        if sum(1 for c in commits_ahead):
            return "local_commits"
        if sum(1 for c in commits_behind):
            return "needs_pull"

        return "clean"
    except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError):
        return "missing_not_a_repo"
    except Exception as e:
        logger.error(f"Error getting repo status for {local_path}: {e}")
        return "unknown"

def get_changed_files(local_path):
    """
    Obtiene una lista de archivos con cambios, respetando las reglas de .gitignore.
    """
    try:
        repo = git.Repo(local_path)
        changed_files = []

        # Obtenemos todos los diffs (modificados, eliminados, renombrados, etc.)
        all_diffs = repo.index.diff(None)
        
        # Obtenemos los archivos no rastreados
        untracked_files_list = repo.untracked_files

        # Combinamos y procesamos todas las rutas de archivo
        all_paths_to_check = [diff.a_path for diff in all_diffs] + untracked_files_list
        
        # --- ¡LA MAGIA OCURRE AQUÍ! ---
        # GitPython nos da una lista de archivos ignorados.
        # Usamos 'set' para una comprobación más rápida.
        ignored_files = set(repo.ignored(all_paths_to_check))
        
        # Ahora construimos la lista final, solo con los archivos NO ignorados.
        
        # Archivos modificados/eliminados/etc.
        for diff_item in all_diffs:
            if diff_item.a_path not in ignored_files:
                # Determinamos el tipo de cambio
                change_type_map = {'A': 'added', 'D': 'deleted', 'R': 'renamed', 'M': 'modified', 'T': 'modified'}
                status_keyword = change_type_map.get(diff_item.change_type, 'modified')
                changed_files.append({'status': status_keyword, 'path': diff_item.a_path})

        # Archivos no rastreados
        for untracked_file in untracked_files_list:
             if untracked_file not in ignored_files:
                changed_files.append({'status': 'untracked', 'path': untracked_file})

        logger.info(f"GitPython found {len(changed_files)} relevant changed files (after .gitignore filter).")
        return changed_files
    except Exception as e:
        logger.error(f"Error getting changed files with GitPython for {local_path}: {e}", exc_info=True)
        return []

def is_git_repository(path):
    return os.path.isdir(os.path.join(path, ".git"))

def get_repo_current_branch(local_path):
    try:
        return git.Repo(local_path).active_branch.name
    except Exception: return "N/A"

def get_repo_remote_url(local_path):
    try:
        return git.Repo(local_path).remotes.origin.url
    except Exception: return "N/A"

def stage_files(local_path, files_to_stage):
    """
    Añade una lista de archivos al staging area de Git.
    """
    if not files_to_stage:
        logger.warning("No files provided to stage.")
        return "No files to stage."

    # El comando 'git add --' es una forma segura de manejar nombres de archivo que podrían
    # parecerse a opciones de línea de comandos.
    command = ["git", "add", "--"] + files_to_stage
    return_code, stdout, stderr = _run_cmd_with_output(command, cwd=local_path)

    if return_code != 0:
        raise GitOperationError(f"Failed to stage files. Error: {stderr}")

    logger.info(f"Staged files in {local_path}: {', '.join(files_to_stage)}")
    return "Files staged successfully."

def commit_changes(local_path, commit_message):
    """
    Realiza un commit con el mensaje proporcionado.
    """
    if not commit_message.strip():
        raise GitOperationError("Commit message cannot be empty.")

    command = ["git", "commit", "-m", commit_message]
    return_code, stdout, stderr = _run_cmd_with_output(command, cwd=local_path)

    if return_code != 0:
        # Un código de retorno no cero aquí puede significar que no había nada para hacer commit.
        if "nothing to commit" in stdout or "nothing to commit" in stderr:
            logger.warning(f"Attempted to commit in {local_path} but there were no staged changes.")
            # Lanzamos una excepción personalizada para que la UI pueda manejar este caso.
            raise GitOperationError("No changes staged for commit.")

        raise GitOperationError(f"Failed to commit changes. Error: {stderr}")

    logger.info(f"Successfully committed in {local_path} with message: {commit_message}")
    return stdout