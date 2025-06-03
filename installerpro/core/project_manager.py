# installerpro/core/project_manager.py
import os
import json
import logging
import shutil
import re

# Importaciones desde utils/git_operations
from ..utils.git_operations import clone_repository, pull_repository, push_repository, get_repo_status, is_git_repository, GitOperationError, get_repo_current_branch, get_repo_remote_url

logger = logging.getLogger(__name__)

class ProjectNotFoundError(Exception):
    """Excepción lanzada cuando un proyecto no se encuentra en la configuración."""
    pass

class ProjectManager:
    def __init__(self, base_folder, config_manager, projects_file_path):
        self.base_folder = os.path.abspath(base_folder)
        self.config_manager = config_manager
        self.projects_file_path = projects_file_path
        self.projects = []  # Asegura que 'projects' siempre sea una lista.
        self._load_projects()
        logger.info(f"ProjectManager initialized with base folder: {self.base_folder}")
        logger.info(f"Projects file path: {self.projects_file_path}")

    def _load_projects(self):
        if os.path.exists(self.projects_file_path):
            try:
                with open(self.projects_file_path, 'r', encoding='utf-8') as f:
                    self.projects = json.load(f)
                logger.info(f"Loaded {len(self.projects)} projects from {self.projects_file_path}")
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding projects.json: {e}. Resetting project list.")
                self.projects = []
        else:
            self.projects = []
            logger.info("projects.json not found. Starting with empty project list.")

        self._cleanup_deleted_projects()
        self.refresh_project_statuses()

    def _save_projects(self):
        try:
            os.makedirs(os.path.dirname(self.projects_file_path), exist_ok=True)
            with open(self.projects_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.projects, f, indent=4)
            logger.info(f"Saved {len(self.projects)} projects to {self.projects_file_path}")
        except IOError as e:
            logger.error(f"Error saving projects to {self.projects_file_path}: {e}")

    def get_projects(self):
        return [p for p in self.projects if not p.get('deleted', False)]

    def get_all_projects_including_deleted(self):
        return self.projects

    def get_project_by_path(self, local_path):
        for project in self.projects:
            if project['local_path'] == local_path:
                return project
        return None

    def add_project(self, name, repo_url, local_path_full, branch="main"):
        normalized_local_path = os.path.abspath(local_path_full)

        for p in self.projects:
            if p['local_path'] == normalized_local_path and not p.get('deleted', False):
                logger.warning(f"Project already exists at {normalized_local_path}. Not adding.")
                raise ValueError(f"Project already exists at this path: {normalized_local_path}")
            if p['name'] == name and not p.get('deleted', False):
                logger.warning(f"Project with name '{name}' already exists. Not adding.")
                raise ValueError(f"Project with this name already exists: {name}")

        for p in self.projects:
            if p['local_path'] == normalized_local_path or p['name'] == name:
                if p.get('deleted', False):
                    p['deleted'] = False
                    p['repo_url'] = repo_url
                    p['branch'] = branch
                    logger.info(f"Undeleted existing project: {name}")
                    if not os.path.isdir(normalized_local_path) or not is_git_repository(normalized_local_path):
                        logger.info(f"Attempting to re-clone or initialize for undeleted project: {name}")
                        try:
                            clone_repository(repo_url, normalized_local_path, branch)
                        except GitOperationError as e:
                            logger.error(f"Failed to re-clone for undeleted project '{name}': {e}")
                            raise
                    else:
                        try:
                            pull_repository(normalized_local_path, branch) # Pasar la rama aquí
                        except GitOperationError as e:
                            logger.warning(f"Failed to pull for undeleted project '{name}': {e}. Continuing anyway.")
                    self._save_projects()
                    self.refresh_project_statuses()
                    return p

        try:
            os.makedirs(os.path.dirname(normalized_local_path), exist_ok=True)
            
            if os.path.exists(normalized_local_path) and len(os.listdir(normalized_local_path)) > 0:
                logger.warning(f"Target directory '{normalized_local_path}' exists and is not empty. Skipping clone.")
                if is_git_repository(normalized_local_path):
                    status = get_repo_status(normalized_local_path)
                    if status == "Needs Pull" or status == "Modified":
                        logger.info(f"Existing directory '{normalized_local_path}' is a Git repo. Attempting pull.")
                        pull_repository(normalized_local_path, branch) # Pasar la rama aquí
                    elif status == "Local Commits":
                        logger.info(f"Existing directory '{normalized_local_path}' is a Git repo with local commits. Status: {status}")
                    else:
                        logger.info(f"Existing directory '{normalized_local_path}' is a Git repo and clean. Status: {status}")
                else:
                    raise FileExistsError(f"Directory '{normalized_local_path}' exists and is not empty. Cannot clone into it.")
            else:
                clone_repository(repo_url, normalized_local_path, branch)

            new_project = {
                "name": name,
                "local_path": normalized_local_path,
                "repo_url": repo_url,
                "branch": branch,
                "status": "Clean",
                "deleted": False
            }
            self.projects.append(new_project)
            self._save_projects()
            self.refresh_project_statuses()
            logger.info(f"Project '{name}' added and cloned successfully.")
            return new_project
        except GitOperationError as e:
            logger.error(f"Git operation failed for project '{name}': {e}")
            raise
        except FileExistsError as e:
            logger.error(f"Cannot add project '{name}': {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred while adding project '{name}': {e}")
            raise

    def remove_project(self, local_path, permanent=False):
        project_found = False
        for i, project in enumerate(self.projects):
            if project['local_path'] == local_path:
                if permanent:
                    if os.path.exists(local_path):
                        try:
                            shutil.rmtree(local_path)
                            logger.info(f"Physically removed project folder: {local_path}")
                        except OSError as e:
                            logger.error(f"Error physically removing project folder {local_path}: {e}")
                            raise
                    else:
                        logger.warning(f"Attempted physical removal of non-existent folder: {local_path}")
                    
                    self.projects.pop(i)
                    logger.info(f"Project permanently removed from configuration: {local_path}")
                else:
                    project['deleted'] = True
                    project['status'] = "Deleted"
                    logger.info(f"Project marked as deleted: {local_path}")
                
                project_found = True
                break
        
        if project_found:
            self._save_projects()
            if permanent:
                self.refresh_project_statuses()
            return True
        else:
            logger.warning(f"Project not found for removal: {local_path}")
            return False

    def _cleanup_deleted_projects(self):
        """Removes projects marked as deleted from the internal list if their folder is already gone."""
        initial_count = len(self.projects)
        self.projects = [p for p in self.projects if not (p.get('deleted', False) and not os.path.exists(p['local_path']))]
        if len(self.projects) < initial_count:
            self._save_projects()
            logger.info(f"Cleaned up {initial_count - len(self.projects)} deleted projects that no longer exist on disk.")

    def update_project(self, local_path, do_pull=True):
        project = self.get_project_by_path(local_path)
        if not project:
            logger.error(f"Project not found for update: {local_path}")
            raise ValueError(f"Project not found: {local_path}")
        
        if not is_git_repository(local_path):
            logger.warning(f"Directory '{local_path}' is not a Git repository. Cannot update.")
            raise ValueError(f"'{project['name']}' is not a Git repository.")

        if do_pull:
            try:
                output = pull_repository(local_path, project['branch']) # Pasar la rama aquí
                status = get_repo_status(local_path)
                project['status'] = status
                self._save_projects()
                logger.info(f"Project '{project['name']}' updated. Status: {status}")
                return "Up-to-date" if "Already up to date." in output else output
            except GitOperationError as e:
                logger.error(f"Failed to pull for project '{project['name']}': {e}")
                raise
        return "No action"

    def push_project(self, local_path):
        project = self.get_project_by_path(local_path)
        if not project:
            logger.error(f"Project not found for push: {local_path}")
            raise ValueError(f"Project not found: {local_path}")
        
        if not is_git_repository(local_path):
            logger.warning(f"Directory '{local_path}' is not a Git repository. Cannot push.")
            raise ValueError(f"'{project['name']}' is not a Git repository.")

        try:
            output = push_repository(local_path)
            status = get_repo_status(local_path)
            project['status'] = status
            self._save_projects()
            logger.info(f"Project '{project['name']}' pushed. Status: {status}")
            return "Up-to-date (Push)" if "Everything up-to-date" in output else output
        except GitOperationError as e:
            logger.error(f"Failed to push for project '{project['name']}': {e}")
            raise

    def set_base_folder(self, new_base_folder):
        self.base_folder = os.path.abspath(new_base_folder)
        logger.info(f"Base folder updated to: {self.base_folder}")
        self._save_projects()

    def scan_base_folder(self):
        logger.info(f"Scanning base folder for new Git repositories: {self.base_folder}")
        found_count = 0
        existing_paths = {p['local_path'] for p in self.get_all_projects_including_deleted()}

        for root, dirs, files in os.walk(self.base_folder):
            if ".git" in dirs:
                repo_path = root
                if repo_path not in existing_paths:
                    try:
                        name = os.path.basename(repo_path)
                        repo_url = self._get_repo_remote_url(repo_path)
                        branch = self._get_repo_current_branch(repo_path)

                        existing_deleted_project = None
                        for p in self.projects:
                            if p['local_path'] == repo_path and p.get('deleted', False):
                                existing_deleted_project = p
                                break
                        
                        if existing_deleted_project:
                            existing_deleted_project['deleted'] = False
                            existing_deleted_project['repo_url'] = repo_url
                            existing_deleted_project['branch'] = branch
                            logger.info(f"Undeleted existing Git project found: {name} at {repo_path}")
                        else:
                            new_project = {
                                "name": name,
                                "local_path": repo_path,
                                "repo_url": repo_url,
                                "branch": branch,
                                "status": get_repo_status(repo_path),
                                "deleted": False
                            }
                            self.projects.append(new_project)
                            found_count += 1
                            logger.info(f"New Git project found: {name} at {repo_path}")
                    except GitOperationError as e:
                        logger.warning(f"Could not add {repo_path} during scan due to Git error: {e}")
                    except Exception as e:
                        logger.warning(f"Could not add {repo_path} during scan due to unexpected error: {e}")
                dirs[:] = [d for d in dirs if d != ".git"] # Don't recurse into found Git repos
        
        self._save_projects()
        self.refresh_project_statuses()
        logger.info(f"Scan complete. Found {found_count} new Git repositories.")
        return found_count

    def _get_repo_remote_url(self, local_path):
        try:
            from git import Repo
            repo = Repo(local_path)
            if repo.remotes:
                return repo.remotes.origin.url
            return "N/A (no remote)"
        except Exception:
            return "N/A (no remote or error)"

    def _get_repo_current_branch(self, local_path):
        try:
            from git import Repo
            repo = Repo(local_path)
            return repo.active_branch.name
        except Exception:
            return "N/A (detached HEAD or error)"

    def refresh_project_statuses(self):
        logger.info("Refreshing statuses for all projects...")
        for project in self.projects:
            if not project.get('deleted', False):
                local_path = project['local_path']
                if os.path.isdir(local_path) and is_git_repository(local_path):
                    try:
                        project['status'] = get_repo_status(local_path)
                    except Exception as e:
                        project['status'] = f"Error: {e}"
                        logger.error(f"Failed to refresh status for '{project['name']}': {e}")
                else:
                    project['status'] = "Missing/Not a Repo"
                    logger.warning(f"Project folder for '{project['name']}' not found or not a repo: {local_path}")
            else:
                project['status'] = "Deleted"
        self._save_projects()
        logger.info("All project statuses refreshed.")
