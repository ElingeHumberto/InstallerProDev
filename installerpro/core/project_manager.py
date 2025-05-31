# installerpro/core/project_manager.py
import json
import os
import shutil # Necesario para eliminar directorios
import logging
from git import Repo, GitCommandError # Asegúrate de que 'git' esté instalado (pip install GitPython)

logger = logging.getLogger(__name__)

class ProjectManager:
    def __init__(self, base_folder, config_manager):
        self.base_folder = base_folder
        self.config_manager = config_manager
        # ESTA ES LA LÍNEA MODIFICADA (antes self.config_manager.config_dir)
        self.projects_file = os.path.join(os.path.dirname(self.config_manager.config_path), 'projects.json')
        self.projects = []
        self._load_projects()

    def _load_projects(self):
        """Carga la lista de proyectos desde el archivo JSON."""
        if os.path.exists(self.projects_file):
            try:
                with open(self.projects_file, 'r', encoding='utf-8') as f:
                    self.projects = json.load(f)
                logger.info(f"Projects loaded from {self.projects_file}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding projects.json: {e}. Starting with empty project list.")
                self.projects = [] # Reiniciar si el JSON está corrupto
                self._save_projects() # Guardar un archivo vacío/correcto
            except Exception as e:
                logger.error(f"Unexpected error loading projects.json: {e}. Starting with empty project list.")
                self.projects = []
                self._save_projects()
        else:
            self.projects = []
            self._save_projects() # Crea el archivo vacío si no existe
            logger.info(f"projects.json not found. Initialized with empty project list at {self.projects_file}")

    def _save_projects(self):
        """Guarda la lista actual de proyectos en el archivo JSON."""
        try:
            os.makedirs(os.path.dirname(self.projects_file), exist_ok=True)
            with open(self.projects_file, 'w', encoding='utf-8') as f:
                json.dump(self.projects, f, indent=4)
            logger.info(f"Projects saved to {self.projects_file}")
        except Exception as e:
            logger.error(f"Error saving projects.json: {e}")

    def add_project(self, name, repo_url, local_path_full, branch='main'):
        """
        Clona un nuevo repositorio y lo añade a la lista de proyectos.
        Retorna los datos del proyecto añadido.
        """
        # Verificar si el proyecto ya existe (por ruta local o nombre)
        for p in self.projects:
            if p['local_path'].lower() == os.path.abspath(local_path_full).lower() or p['name'].lower() == name.lower():
                logger.warning(f"Project with name '{name}' or path '{local_path_full}' already exists.")
                raise ValueError(f"Project with name '{name}' or path '{local_path_full}' already exists.")

        try:
            logger.info(f"Cloning {repo_url} into {local_path_full} (branch: {branch})...")
            repo = Repo.clone_from(repo_url, local_path_full, branch=branch)
            status = self._get_git_status(local_path_full)
            logger.info(f"Cloning of '{name}' complete.")
        except GitCommandError as e:
            logger.error(f"Git cloning failed for {name}: {e}")
            raise GitOperationError(f"Failed to clone repository: {e.stderr if e.stderr else str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during cloning {name}: {e}")
            raise GitOperationError(f"An unexpected error occurred during cloning: {e}")

        project_data = {
            'name': name,
            'repo_url': repo_url,
            'local_path': os.path.abspath(local_path_full),
            'branch': branch,
            'status': status, # Inicializa el estado después de la clonación
            'deleted': False # Por defecto no está marcado como borrado
        }
        self.projects.append(project_data)
        self._save_projects()
        return project_data

    def remove_project(self, local_path, permanent=False):
        """
        Elimina un proyecto de la lista.
        Si 'permanent' es True, también borra la carpeta del disco.
        """
        project_found = False
        new_projects = []
        for project in self.projects:
            if project['local_path'].lower() == os.path.abspath(local_path).lower():
                project_found = True
                if permanent:
                    if os.path.exists(project['local_path']):
                        try:
                            shutil.rmtree(project['local_path'])
                            logger.info(f"Physically removed project folder: {project['local_path']}")
                        except OSError as e:
                            logger.error(f"Error removing project folder {project['local_path']}: {e}")
                            raise IOError(f"Failed to physically remove folder: {e}")
                    else:
                        logger.warning(f"Attempted physical removal, but folder not found: {project['local_path']}")
                    # Si es permanente, no lo añadimos a la nueva lista
                else:
                    # Marcado como borrado "suave" (soft delete)
                    project['deleted'] = True
                    project['status'] = 'Marked as Deleted' # Actualizar estado para UI
                    new_projects.append(project)
            else:
                new_projects.append(project)

        if not project_found:
            raise ProjectNotFoundError(f"Project not found at path: {local_path}")

        self.projects = new_projects
        self._save_projects()
        logger.info(f"Project '{local_path}' removed (permanent: {permanent}).")


    def update_project(self, local_path, do_pull=True):
        """
        Actualiza el estado de un proyecto Git, y opcionalmente hace un pull.
        """
        project = self.get_project_by_path(local_path)
        if not project:
            raise ProjectNotFoundError(f"Project not found at path: {local_path}")

        try:
            repo = Repo(project['local_path'])
            original_commit = repo.head.commit
            pull_info = "No pull performed."

            if do_pull:
                logger.info(f"Pulling latest changes for '{project['name']}'...")
                # Fetch all and then pull current branch
                for remote in repo.remotes:
                    remote.fetch()
                
                # Check if there are updates on the remote for the current branch
                current_branch = repo.active_branch
                remote_branch = repo.remotes.origin.refs[current_branch.name]
                if remote_branch.commit != current_branch.commit:
                    pull_info = repo.remotes.origin.pull()[0].summary # pull the current branch
                    logger.info(f"Pull result for '{project['name']}': {pull_info}")
                else:
                    pull_info = "Up-to-date"
                    logger.info(f"Project '{project['name']}' is already up-to-date.")

            new_status = self._get_git_status(project['local_path'])
            if new_status == 'Up-to-date' and pull_info == 'Up-to-date':
                project['status'] = 'Up-to-date'
            elif new_status == 'Clean':
                project['status'] = 'Clean'
            else:
                 project['status'] = new_status # Keep more specific status if not clean

            self._save_projects()
            logger.info(f"Project '{project['name']}' updated. New status: {project['status']}")
            return pull_info # Devuelve el resultado del pull

        except GitCommandError as e:
            project['status'] = f"Git Error: {e.status}"
            self._save_projects()
            logger.error(f"Git operation failed for {project['name']}: {e}")
            raise GitOperationError(f"Git error during update: {e.stderr if e.stderr else str(e)}")
        except Exception as e:
            project['status'] = "Error"
            self._save_projects()
            logger.error(f"An unexpected error occurred during update for {project['name']}: {e}")
            raise GitOperationError(f"An unexpected error occurred during update: {e}")

    def scan_base_folder(self):
        """
        Escanea la carpeta base en busca de nuevos repositorios Git y los añade.
        """
        new_projects_count = 0
        existing_paths = {p['local_path'].lower() for p in self.projects}

        logger.info(f"Scanning base folder: {self.base_folder}")
        for item_name in os.listdir(self.base_folder):
            item_path = os.path.join(self.base_folder, item_name)
            if os.path.isdir(item_path) and item_path.lower() not in existing_paths:
                # Comprobar si es un repositorio Git
                if os.path.isdir(os.path.join(item_path, '.git')):
                    try:
                        repo = Repo(item_path)
                        # Intenta obtener la URL remota
                        repo_url = next(iter(repo.remotes.origin.urls), 'N/A')
                        # Intenta obtener la rama actual
                        branch = repo.active_branch.name
                        status = self._get_git_status(item_path)

                        new_project_data = {
                            'name': item_name,
                            'repo_url': repo_url,
                            'local_path': os.path.abspath(item_path),
                            'branch': branch,
                            'status': status,
                            'deleted': False
                        }
                        self.projects.append(new_project_data)
                        existing_paths.add(item_path.lower()) # Añadir al set para evitar duplicados en el mismo escaneo
                        new_projects_count += 1
                        logger.info(f"Found and added new project during scan: {item_name}")
                    except GitCommandError as e:
                        logger.warning(f"Directory {item_name} appears to be a Git repo but has issues: {e}")
                    except Exception as e:
                        logger.warning(f"Could not process potential Git repo {item_name}: {e}")
        self._save_projects()
        logger.info(f"Scan complete. Added {new_projects_count} new projects.")
        return new_projects_count

    def push_project(self, local_path):
        """
        Realiza un 'git push' para el proyecto especificado.
        """
        project = self.get_project_by_path(local_path)
        if not project:
            raise ProjectNotFoundError(f"Project not found at path: {local_path}")

        try:
            repo = Repo(project['local_path'])
            # Asegúrate de que haya un remoto configurado
            if not repo.remotes:
                raise GitOperationError("No remote configured for this repository.")

            # Realiza el push a la rama actual en el remoto 'origin'
            # (o el remoto predeterminado si hay varios y no se especifica)
            # pull_info = repo.remotes.origin.push()[0].summary
            # push_info = repo.git.push() # esto devuelve la salida completa del comando push

            # Para obtener un resultado más limpio, podemos comprobar el estado antes de push
            if not repo.is_dirty(untracked_files=True) and len(repo.remotes.origin.fetch()) == 0:
                 # Check if there are local commits not yet pushed
                local_branch = repo.active_branch
                remote_branch = repo.remotes.origin.refs[local_branch.name] if local_branch.name in repo.remotes.origin.refs else None

                if remote_branch and local_branch.commit == remote_branch.commit:
                    push_info = "Up-to-date (Push)"
                else:
                    # There are local commits to push or remote branch not tracking
                    push_info = repo.remotes.origin.push()[0].summary

            elif repo.is_dirty(untracked_files=True): # Check if there are local changes
                raise GitOperationError("Cannot push: There are uncommitted changes or untracked files.")
            else:
                 push_info = repo.remotes.origin.push()[0].summary # Perform the push

            # Después del push, refresca el estado del proyecto
            project['status'] = self._get_git_status(project['local_path'])
            self._save_projects()
            logger.info(f"Project '{project['name']}' pushed successfully. Result: {push_info}")
            return push_info

        except GitCommandError as e:
            project['status'] = f"Git Error: {e.status}"
            self._save_projects()
            logger.error(f"Git push failed for {project['name']}: {e}")
            raise GitOperationError(f"Git push failed: {e.stderr if e.stderr else str(e)}")
        except Exception as e:
            project['status'] = "Error"
            self._save_projects()
            logger.error(f"An unexpected error occurred during push for {project['name']}: {e}")
            raise GitOperationError(f"An unexpected error occurred during push: {e}")


    def refresh_project_statuses(self):
        """Refresca el estado de Git de todos los proyectos."""
        logger.info("Refreshing statuses for all projects...")
        updated_count = 0
        for project in self.projects:
            if not project.get('deleted', False):
                try:
                    project['status'] = self._get_git_status(project['local_path'])
                    updated_count += 1
                except Exception as e:
                    project['status'] = f"Error: {e}"
                    logger.error(f"Could not refresh status for {project['name']}: {e}")
        self._save_projects()
        logger.info(f"Refreshed status for {updated_count} projects.")
        return updated_count

    def get_projects(self):
        """Devuelve la lista actual de proyectos."""
        # Filtra proyectos no eliminados para la UI principal, pero devuelve todos para persistencia.
        return [p for p in self.projects if not p.get('deleted', False)]

    def get_project_by_path(self, local_path):
        """Busca un proyecto por su ruta local."""
        for project in self.projects:
            if project['local_path'].lower() == os.path.abspath(local_path).lower():
                return project
        return None

    def set_base_folder(self, new_base_folder):
        """Actualiza la carpeta base y escanea en busca de proyectos."""
        # Se asume que config_manager ya guardó la nueva base_folder
        self.base_folder = os.path.abspath(new_base_folder)
        logger.info(f"ProjectManager base folder updated to: {self.base_folder}")
        # Opcionalmente, podrías escanear la nueva carpeta aquí si quieres
        # self.scan_base_folder()

    def _get_git_status(self, repo_path):
        """Obtiene un estado legible de un repositorio Git."""
        try:
            repo = Repo(repo_path)
            if repo.is_dirty(untracked_files=True):
                # Check for untracked files
                if repo.untracked_files:
                    return 'Untracked changes'
                return 'Uncommitted changes'
            else:
                # Check if local branch is behind remote
                try:
                    # Fetch to update remote references
                    for remote in repo.remotes:
                        remote.fetch()

                    # Compare current branch with its remote tracking branch
                    local_branch = repo.active_branch
                    if local_branch.tracking_branch():
                        if local_branch.commit != local_branch.tracking_branch().commit:
                            # Check if local is ahead or behind
                            ahead = len(list(repo.iter_commits(f'{local_branch.name}@{{u}}..{local_branch.name}')))
                            behind = len(list(repo.iter_commits(f'{local_branch.name}..{local_branch.name}@{{u}}')))

                            if ahead > 0 and behind == 0:
                                return 'Local Ahead'
                            elif behind > 0 and ahead == 0:
                                return 'Needs Pull'
                            elif ahead > 0 and behind > 0:
                                return 'Diverged'
                        else:
                            return 'Up-to-date'
                    else:
                        return 'No tracking branch' # Or 'Clean, no remote' if no remote
                except GitCommandError as e:
                    logger.warning(f"Git status check failed for {repo_path} (remote check): {e}")
                    return 'Error Status'
                except Exception as e:
                    logger.warning(f"Error checking tracking branch for {repo_path}: {e}")
                    return 'Error Status'
            return 'Clean' # Fallback for no changes and tracking branch not found/behind
        except GitCommandError as e:
            logger.error(f"Failed to get Git status for {repo_path}: {e}")
            return 'Not a Git Repo or Error'
        except Exception as e:
            logger.error(f"Unexpected error getting Git status for {repo_path}: {e}")
            return 'Error Status'

class GitOperationError(Exception):
    """Excepción personalizada para errores de operaciones Git."""
    pass

class ProjectNotFoundError(Exception):
    """Excepción personalizada cuando un proyecto no se encuentra."""
    pass