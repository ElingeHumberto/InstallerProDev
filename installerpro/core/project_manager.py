# installerpro/core/project_manager.py
import os
import json
import logging
from installerpro.core import git_operations # Importa el módulo de operaciones Git

logger = logging.getLogger(__name__)

class ProjectNotFoundError(Exception):
    """Excepción personalizada cuando un proyecto no se encuentra."""
    pass

class ProjectManager:
    def __init__(self, initial_base_folder, config_manager):
        self.config_manager = config_manager
        self._base_folder = initial_base_folder # Usar la carpeta base inicial
        self.projects_file = os.path.join(self.config_manager.config_dir, "projects.json")
        self._projects = self._load_projects()
        logger.info("ProjectManager initialized.")

    def _load_projects(self):
        """Carga la lista de proyectos desde el archivo JSON."""
        if os.path.exists(self.projects_file):
            try:
                with open(self.projects_file, "r", encoding="utf-8") as f:
                    projects = json.load(f)
                    # Asegurarse de que cada proyecto tenga un 'status' por defecto si no lo tiene
                    for project in projects:
                        project.setdefault('status', 'Unknown')
                        project.setdefault('deleted', False) # Añadir campo 'deleted'
                    logger.info(f"Loaded {len(projects)} projects from {self.projects_file}")
                    return projects
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding projects file {self.projects_file}: {e}. Starting with empty list.")
            except Exception as e:
                logger.error(f"Error loading projects file {self.projects_file}: {e}. Starting with empty list.")
        logger.info("No existing projects file found. Starting with empty project list.")
        return []

    def _save_projects(self):
        """Guarda la lista actual de proyectos en el archivo JSON."""
        try:
            with open(self.projects_file, "w", encoding="utf-8") as f:
                json.dump(self._projects, f, indent=4)
            logger.info(f"Projects saved to {self.projects_file}")
        except Exception as e:
            logger.error(f"Error saving projects file {self.projects_file}: {e}")

    def get_projects(self):
        """Devuelve la lista actual de proyectos."""
        return self._projects

    def get_project_by_path(self, local_path):
        """Busca un proyecto por su ruta local."""
        for project in self._projects:
            if project['local_path'] == local_path:
                return project
        return None

    def add_project(self, name, repo_url, local_path_full, branch=None):
        """Añade un nuevo proyecto clonando el repositorio."""
        if self.get_project_by_path(local_path_full):
            logger.warning(f"Project already exists at {local_path_full}. Skipping add.")
            raise ValueError(f"Project already exists at {local_path_full}")

        # Asegura que la carpeta padre exista para el clonado
        parent_dir = os.path.dirname(local_path_full)
        os.makedirs(parent_dir, exist_ok=True)

        try:
            git_operations.clone_repository(repo_url, local_path_full, branch)
            new_project = {
                "name": name,
                "repo_url": repo_url,
                "local_path": local_path_full,
                "branch": branch if branch else "master", # O la rama por defecto del repo
                "status": "Cloned",
                "deleted": False # Por defecto no eliminado
            }
            self._projects.append(new_project)
            self._save_projects()
            logger.info(f"Project '{name}' added and cloned successfully.")
            return new_project # Devuelve el proyecto añadido para el callback
        except git_operations.GitOperationError as e:
            logger.error(f"Failed to add project '{name}' due to Git error: {e}")
            raise # Re-lanza la excepción para que el UI la maneje
        except Exception as e:
            logger.error(f"An unexpected error occurred while adding project '{name}': {e}")
            raise

    def remove_project(self, local_path, permanent=False):
        """
        Elimina un proyecto. Por defecto, lo marca como eliminado (soft delete).
        Si permanent=True, lo elimina completamente del disco y de la configuración.
        """
        project_found = False
        for i, project in enumerate(self._projects):
            if project['local_path'] == local_path:
                project_found = True
                if permanent:
                    # Eliminar físicamente la carpeta del proyecto
                    if os.path.exists(local_path):
                        try:
                            import shutil
                            shutil.rmtree(local_path)
                            logger.info(f"Physically removed project folder: {local_path}")
                        except Exception as e:
                            logger.error(f"Failed to physically remove folder {local_path}: {e}")
                            raise git_operations.GitOperationError(f"Failed to remove folder: {e}")
                    self._projects.pop(i) # Eliminar de la lista de proyectos
                    logger.info(f"Project '{project['name']}' permanently removed.")
                else:
                    project['deleted'] = True # Marcar como eliminado
                    project['status'] = 'Deleted'
                    logger.info(f"Project '{project['name']}' marked as deleted.")
                self._save_projects()
                return # Salir después de encontrar y procesar el proyecto
        
        if not project_found:
            logger.warning(f"Attempted to remove non-existent project at path: {local_path}")
            raise ProjectNotFoundError(f"Project not found at path: {local_path}")


    def update_project(self, local_path, do_pull=True):
        """Actualiza un proyecto (realiza un pull)."""
        project = self.get_project_by_path(local_path)
        if not project:
            raise ProjectNotFoundError(f"Project not found at path: {local_path}")
        
        try:
            if do_pull:
                result = git_operations.pull_repository(local_path)
                project['status'] = git_operations.get_repo_status(local_path) # Actualiza el estado después del pull
                self._save_projects()
                logger.info(f"Project '{project['name']}' updated successfully.")
                return result # Devuelve el resultado del pull
            else:
                logger.info(f"Project '{project['name']}' update skipped (no pull requested).")
                return "No pull performed"
        except git_operations.GitOperationError as e:
            project['status'] = f"Error: {e}"
            self._save_projects()
            logger.error(f"Failed to update project '{project['name']}' due to Git error: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while updating project '{project['name']}': {e}")
            raise

    def push_project(self, local_path):
        """Empuja los cambios de un proyecto al remoto."""
        project = self.get_project_by_path(local_path)
        if not project:
            raise ProjectNotFoundError(f"Project not found at path: {local_path}")
        
        try:
            result = git_operations.push_repository(local_path)
            project['status'] = git_operations.get_repo_status(local_path) # Actualiza el estado después del push
            self._save_projects()
            logger.info(f"Project '{project['name']}' pushed successfully.")
            return result # Devuelve el resultado del push
        except git_operations.GitOperationError as e:
            project['status'] = f"Error: {e}"
            self._save_projects()
            logger.error(f"Failed to push project '{project['name']}' due to Git error: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while pushing project '{project['name']}': {e}")
            raise

    def scan_base_folder(self):
        """
        Escanea la carpeta base en busca de nuevos repositorios Git
        y los añade a la configuración si no están ya presentes.
        """
        new_projects_count = 0
        current_base_folder = self.config_manager.get_base_folder()
        
        if not os.path.exists(current_base_folder):
            logger.warning(f"Base folder '{current_base_folder}' does not exist. Skipping scan.")
            return new_projects_count

        for item_name in os.listdir(current_base_folder):
            item_path = os.path.join(current_base_folder, item_name)
            if os.path.isdir(item_path) and git_operations.is_git_repository(item_path):
                if not self.get_project_by_path(item_path):
                    # Este es un nuevo repositorio Git no configurado
                    # Intentar obtener la URL remota y la rama para una configuración más completa
                    repo_url = "Unknown"
                    branch = "master" # Asumir master si no se puede determinar
                    try:
                        repo_url = git_operations._run_git_command(["git", "config", "--get", "remote.origin.url"], item_path)
                        branch = git_operations._run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], item_path)
                    except git_operations.GitOperationError:
                        logger.warning(f"Could not determine repo URL or branch for new project at {item_path}. Using defaults.")
                    
                    new_project = {
                        "name": item_name,
                        "repo_url": repo_url,
                        "local_path": item_path,
                        "branch": branch,
                        "status": git_operations.get_repo_status(item_path), # Obtener el estado inicial
                        "deleted": False
                    }
                    self._projects.append(new_project)
                    new_projects_count += 1
                    logger.info(f"Found and added new project during scan: '{item_name}' at '{item_path}'")
                else:
                    logger.debug(f"Project at '{item_path}' already configured. Skipping.")
        
        self._save_projects()
        logger.info(f"Scan complete. Added {new_projects_count} new projects.")
        return new_projects_count

    def refresh_project_statuses(self):
        """Actualiza el estado Git de todos los proyectos configurados."""
        for project in self._projects:
            if not project.get('deleted', False): # Solo actualizar si no está marcado como eliminado
                try:
                    project['status'] = git_operations.get_repo_status(project['local_path'])
                    logger.debug(f"Status updated for '{project['name']}'.")
                except Exception as e:
                    project['status'] = f"Error: {e}"
                    logger.error(f"Failed to refresh status for '{project['name']}': {e}")
        self._save_projects()
        logger.info("All project statuses refreshed.")

    def set_base_folder(self, new_base_folder):
        """Actualiza la carpeta base del ProjectManager."""
        self._base_folder = new_base_folder
        self.config_manager.set_base_folder(new_base_folder) # Asegura que la configuración también se actualice
        logger.info(f"ProjectManager base folder updated to: {new_base_folder}")