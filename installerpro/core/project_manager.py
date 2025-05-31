import os
import json
import logging
from installerpro.config import ConfigManager
from installerpro.core.git_operations import git_clone_project, git_pull_project, git_push_project, git_get_status, git_get_current_branch, git_is_repo, GitOperationError

logger = logging.getLogger(__name__)

class ProjectNotFoundError(Exception):
    """Excepción lanzada cuando un proyecto no se encuentra en la configuración."""
    pass

class ProjectManager:
    def __init__(self, base_folder, config_manager: ConfigManager):
        self.base_folder = os.path.normpath(base_folder)
        self.config_manager = config_manager
        self.projects_data = self._load_projects_data() # Cargar proyectos al inicio

    def set_base_folder(self, new_base_folder):
        """Cambia la carpeta base y recarga los proyectos."""
        self.base_folder = os.path.normpath(new_base_folder)
        os.makedirs(self.base_folder, exist_ok=True)
        self.projects_data = self._load_projects_data() # Recargar proyectos después de cambiar la base
        logger.info(f"ProjectManager base folder updated to: {self.base_folder}")

    def _load_projects_data(self):
        """Carga los datos de los proyectos desde el archivo de configuración."""
        projects = self.config_manager.get_projects()
        # Asegurarse de que todos los proyectos tienen un estado y que la ruta sea normalizada
        for p in projects:
            p['local_path'] = os.path.normpath(p['local_path'])
            if 'status' not in p:
                p['status'] = 'Unknown' # Estado inicial si no existe
            if 'deleted' not in p:
                p['deleted'] = False # Asegurarse de que el flag 'deleted' exista
        logger.info(f"Loaded {len(projects)} projects from config.")
        return projects

    def _save_projects_data(self):
        """Guarda los datos de los proyectos en el archivo de configuración."""
        self.config_manager.set_projects(self.projects_data)
        logger.info(f"Saved {len(self.projects_data)} projects to config.")

    def get_projects(self):
        """Devuelve la lista actual de proyectos, excluyendo los marcados como eliminados."""
        return [p for p in self.projects_data if not p.get('deleted', False)]

    def get_project_by_path(self, local_path):
        """Busca un proyecto por su ruta local."""
        normalized_path = os.path.normpath(local_path)
        for project in self.projects_data:
            # Incluye proyectos marcados como borrados para poder re-activarlos si se escanean
            if os.path.normpath(project['local_path']) == normalized_path: 
                return project
        return None
    
    def get_active_project_by_path(self, local_path):
        """Busca un proyecto por su ruta local, solo si NO está marcado como eliminado."""
        project = self.get_project_by_path(local_path)
        if project and not project.get('deleted', False):
            return project
        return None

    def add_project(self, name, repo_url, local_path, branch="main"):
        """Añade un nuevo proyecto y lo clona."""
        normalized_local_path = os.path.normpath(local_path)
        
        # Verificar si ya existe un proyecto ACTIVO con esa ruta
        if self.get_active_project_by_path(normalized_local_path):
            logger.warning(f"Project at {normalized_local_path} already exists and is active.")
            raise GitOperationError("Project already exists and is active at this path.")
        
        # Si existe un proyecto borrado con esa ruta, lo reactivamos
        existing_project = self.get_project_by_path(normalized_local_path)
        if existing_project and existing_project.get('deleted', False):
            logger.info(f"Reactivating deleted project at {normalized_local_path}.")
            existing_project.update({
                'name': name,
                'repo_url': repo_url,
                'local_path': normalized_local_path,
                'branch': branch,
                'status': 'Cloning/Updating (Reactivated)...',
                'deleted': False # Reactivar
            })
            project_data = existing_project
        else:
            project_data = {
                'name': name,
                'repo_url': repo_url,
                'local_path': normalized_local_path,
                'branch': branch,
                'status': 'Cloning...', # Estado inicial mientras se clona
                'deleted': False # Asegurarse de que sea un proyecto activo
            }
            self.projects_data.append(project_data)
        
        self._save_projects_data() # Guardar inmediatamente para que la GUI refleje el estado

        try:
            logger.info(f"Cloning project '{name}' from {repo_url} to {normalized_local_path} on branch {branch}...")
            # git_clone_project maneja la creación del directorio final si no existe
            git_clone_project(repo_url, normalized_local_path, branch)
            project_data['status'] = 'Clean'
            logger.info(f"Project '{name}' cloned successfully.")
        except GitOperationError as e:
            project_data['status'] = f'Failed: {e}'
            logger.error(f"Failed to clone project '{name}': {e}")
            raise # Relanzar para que el callback de fallo en la GUI lo capture
        finally:
            self._save_projects_data() # Guardar el estado final

        return project_data # Devolver los datos del proyecto actualizado

    def edit_project_metadata(self, original_local_path, new_name, new_repo_url, new_local_path, new_branch): # <--- ¡MÉTODO AÑADIDO!
        """
        Edita los metadatos de un proyecto existente.
        No realiza operaciones Git, solo actualiza los datos almacenados.
        """
        original_normalized_path = os.path.normpath(original_local_path)
        new_normalized_path = os.path.normpath(new_local_path)

        project = self.get_project_by_path(original_normalized_path)
        if not project:
            raise ProjectNotFoundError(f"Project at {original_local_path} not found for editing.")
        
        # Si la ruta local ha cambiado, verificar si la nueva ruta ya existe y está activa
        if original_normalized_path != new_normalized_path:
            if self.get_active_project_by_path(new_normalized_path):
                raise GitOperationError(f"Cannot change path to '{new_local_path}' because another active project already exists there.")
            
            # Si el proyecto se movió físicamente, actualizamos la ruta
            # Nota: Esto no mueve la carpeta en disco, solo actualiza el registro
            logger.info(f"Project path changed from '{original_normalized_path}' to '{new_normalized_path}'.")
            project['local_path'] = new_normalized_path
            
        # Actualizar otros campos
        project['name'] = new_name
        project['repo_url'] = new_repo_url
        project['branch'] = new_branch
        project['status'] = 'Metadata Updated' # Nuevo estado para indicar solo cambio de datos

        self._save_projects_data()
        logger.info(f"Project '{new_name}' metadata updated successfully.")
        return project


    def remove_project(self, local_path, permanent=False):
        """Elimina un proyecto (marcado o físico)."""
        project = self.get_project_by_path(local_path) # Usar get_project_by_path para encontrar incluso borrados
        if not project:
            raise ProjectNotFoundError(f"Project at {local_path} not found for removal.")

        if permanent:
            try:
                if os.path.exists(project['local_path']):
                    import shutil
                    shutil.rmtree(project['local_path'])
                    logger.info(f"Physically removed project folder: {project['local_path']}")
                # Eliminar el proyecto de la lista de datos
                self.projects_data = [p for p in self.projects_data if os.path.normpath(p['local_path']) != os.path.normpath(local_path)]
                logger.info(f"Project '{project['name']}' physically removed from config.")
            except Exception as e:
                logger.error(f"Failed to physically remove project '{project['name']}': {e}")
                raise GitOperationError(f"Failed to physically remove folder: {e}")
        else:
            project['deleted'] = True
            project['status'] = 'Deleted'
            logger.info(f"Project '{project['name']}' marked as deleted.")
        
        self._save_projects_data()
        return True

    def update_project(self, local_path, do_pull=True):
        """Actualiza un proyecto Git (realiza pull)."""
        project = self.get_active_project_by_path(local_path) # Solo actualizar proyectos activos
        if not project:
            raise ProjectNotFoundError(f"Active project at {local_path} not found for update.")
        
        # Si no es un repo Git o la carpeta no existe, intentar clonar
        if not os.path.exists(local_path) or not git_is_repo(local_path):
            logger.warning(f"'{local_path}' no es un repositorio Git válido o no existe. Intentando clonar en su lugar.")
            # Si el proyecto ya existe en la lista pero la carpeta no, lo tratamos como un re-clon
            return self.add_project(project['name'], project['repo_url'], project['local_path'], project['branch'])


        original_status = project.get('status', 'Unknown')
        project['status'] = 'Updating...'
        self._save_projects_data()
        logger.info(f"Updating project '{project['name']}' at {local_path} (pull)...")
        
        try:
            if do_pull:
                git_pull_project(local_path, project['branch'])
                project['status'] = 'Clean'
                logger.info(f"Project '{project['name']}' updated successfully.")
                return "Up-to-date" # O parsear el output de git pull para más detalles
            else:
                project['status'] = 'Clean' # No se hizo pull, solo se marca como limpio
                return "No pull performed"
        except GitOperationError as e:
            project['status'] = f'Failed: {e}'
            logger.error(f"Failed to update project '{project['name']}': {e}")
            raise
        finally:
            self._save_projects_data()

    def push_project(self, local_path):
        """Empuja cambios de un proyecto Git al remoto."""
        project = self.get_active_project_by_path(local_path) # Solo empujar proyectos activos
        if not project:
            raise ProjectNotFoundError(f"Active project at {local_path} not found for push.")

        if not git_is_repo(local_path):
            raise GitOperationError(f"'{local_path}' is not a Git repository. Cannot push.")

        original_status = project.get('status', 'Unknown')
        project['status'] = 'Pushing...'
        self._save_projects_data()
        logger.info(f"Pushing project '{project['name']}' from {local_path}...")

        try:
            git_push_project(local_path)
            project['status'] = 'Clean' # Asumimos clean después de push
            logger.info(f"Project '{project['name']}' pushed successfully.")
            return "Pushed" # O parsear el output de git push
        except GitOperationError as e:
            project['status'] = f'Failed: {e}'
            logger.error(f"Failed to push project '{project['name']}': {e}")
            raise
        finally:
            self._save_projects_data()

    def refresh_project_statuses(self):
        """Refreshes the Git status of all tracked projects."""
        logger.info("Refreshing statuses for all projects...")
        updated_count = 0
        for project in self.projects_data:
            if project.get('deleted', False):
                continue # No refrescar estado de proyectos eliminados
            
            try:
                if git_is_repo(project['local_path']):
                    status_output = git_get_status(project['local_path'])
                    # Aquí puedes parsear status_output para un estado más detallado
                    # Por simplicidad, si no hay salida, asumimos "Clean"
                    if status_output.strip() == "":
                        project['status'] = 'Clean'
                    else:
                        project['status'] = 'Modified' # O 'Needs Commit', etc.
                    current_branch = git_get_current_branch(project['local_path'])
                    # Actualiza la rama del proyecto en los datos si ha cambiado en disco
                    if current_branch and current_branch != project['branch']:
                        project['branch'] = current_branch
                        project['status'] = f"Modified (Branch: {current_branch})" # Indicar cambio de rama
                    elif current_branch:
                        project['status'] = 'Clean' if status_output.strip() == "" else 'Modified'
                else:
                    project['status'] = 'Not Found' # Si la carpeta del repo no existe o no es Git
            except GitOperationError as e:
                project['status'] = f'Error: {e}'
                logger.error(f"Failed to get status for '{project['name']}': {e}")
            
            updated_count += 1 # Contar los proyectos procesados
        
        self._save_projects_data()
        logger.info(f"Refreshed status for {updated_count} projects.")
        return updated_count

    def scan_base_folder(self):
        """Escanea la carpeta base en busca de nuevos repositorios Git."""
        new_projects_found = 0
        logger.info(f"Scanning base folder '{self.base_folder}' for new Git repositories...")
        
        for item_name in os.listdir(self.base_folder):
            item_path = os.path.normpath(os.path.join(self.base_folder, item_name))
            if os.path.isdir(item_path) and git_is_repo(item_path):
                # Verificar si ya está en la lista de proyectos (activos o eliminados)
                existing_project = self.get_project_by_path(item_path)
                if not existing_project:
                    try:
                        temp_url = ""
                        _return_code, _stdout, _stderr = git_get_status(item_path, "config", "--get", "remote.origin.url") # git_get_status no es para esto
                        if _return_code == 0:
                            temp_url = _stdout.strip()
                        
                        current_branch = git_get_current_branch(item_path)
                        
                        new_project = {
                            'name': item_name,
                            'repo_url': temp_url if temp_url else "Unknown",
                            'local_path': item_path,
                            'branch': current_branch,
                            'status': 'Existing Local', # Nuevo estado para proyectos encontrados localmente
                            'deleted': False # Asegurarse de que sea un proyecto activo
                        }
                        self.projects_data.append(new_project)
                        new_projects_found += 1
                        logger.info(f"Found new Git repository: {item_name} at {item_path}")
                    except Exception as e:
                        logger.warning(f"Could not read Git info for '{item_name}': {e}. Skipping.")
                elif existing_project.get('deleted', False):
                    # Si el proyecto existía pero estaba marcado como borrado, lo reactivamos
                    logger.info(f"Reactivating previously deleted project found during scan: {item_name}")
                    existing_project['deleted'] = False
                    existing_project['status'] = 'Existing Local (Reactivated)'
                    new_projects_found += 1 # Contar como "nuevo" reactivado
        
        if new_projects_found > 0:
            self._save_projects_data()
            logger.info(f"Scan complete. Added {new_projects_found} new repositories.")
        else:
            logger.info("Scan complete. No new Git repositories found.")

        return new_projects_found