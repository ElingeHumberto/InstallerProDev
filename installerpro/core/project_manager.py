# installerpro/core/project_manager.py
import os
import json
import logging
import shutil
import re

# Importaciones desde utils/git_operations
from ..utils.git_operations import clone_repository, pull_repository, push_repository, get_repo_status, is_git_repository, GitOperationError

logger = logging.getLogger(__name__)

class ProjectManager:
    def __init__(self, base_folder, config_manager, projects_file_path):
        self.base_folder = os.path.abspath(base_folder)
        self.config_manager = config_manager
        self.projects_file_path = projects_file_path
        self.projects = []  # <--- ¡ESTA LÍNEA ES CRÍTICA! Se asegura que 'projects' siempre sea una lista.
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
                logger.error(f"Error decoding projects.json: {e}. Starting with empty project list.")
                self.projects = []  # Si hay un error, resetea la lista a vacía
        else:
            self.projects = []  # Si no existe el archivo, asegúrate que la lista esté vacía
            logger.info("projects.json not found. Starting with empty project list.")
        self._cleanup_deleted_projects()  # Clean up any truly deleted projects on load
        self.refresh_project_statuses()  # Refresh statuses on load

    def _save_projects(self):
        try:
            os.makedirs(os.path.dirname(self.projects_file_path), exist_ok=True)
            with open(self.projects_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.projects, f, indent=4)
            logger.info(f"Saved {len(self.projects)} projects to {self.projects_file_path}")
        except IOError as e:
            logger.error(f"Error saving projects to {self.projects_file_path}: {e}")

    def get_projects(self):
        # Filter out logically deleted projects for most UI displays, unless explicitly needed
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

        # Check if project already exists (by local path or name)
        for p in self.projects:
            if p['local_path'] == normalized_local_path and not p.get('deleted', False):
                logger.warning(f"Project already exists at {normalized_local_path}. Not adding.")
                raise ValueError(f"Project already exists at this path: {normalized_local_path}")
            if p['name'] == name and not p.get('deleted', False):
                logger.warning(f"Project with name '{name}' already exists. Not adding.")
                raise ValueError(f"Project with this name already exists: {name}")

        # If a deleted project with the same path/name exists, undelete it
        for p in self.projects:
            if p['local_path'] == normalized_local_path or p['name'] == name:
                if p.get('deleted', False):
                    p['deleted'] = False
                    p['repo_url'] = repo_url
                    p['branch'] = branch
                    logger.info(f"Undeleted existing project: {name}")
                    # Attempt to clone/pull if the folder doesn't exist or is not a repo
                    if not os.path.isdir(normalized_local_path) or not is_git_repository(normalized_local_path):
                        logger.info(f"Attempting to re-clone or initialize for undeleted project: {name}")
                        try:
                            clone_repository(repo_url, normalized_local_path, branch)
                        except GitOperationError as e:
                            logger.error(f"Failed to re-clone for undeleted project '{name}': {e}")
                            raise
                    else:
                        try:
                            pull_repository(normalized_local_path)
                        except GitOperationError as e:
                            logger.warning(f"Failed to pull for undeleted project '{name}': {e}. Continuing anyway.")
                    self._save_projects()
                    self.refresh_project_statuses()
                    return p  # Return the updated project

        try:
            # Ensure the parent directory exists for cloning
            os.makedirs(os.path.dirname(normalized_local_path), exist_ok=True)

            # Check if the target directory already exists and is not empty
            if os.path.exists(normalized_local_path) and len(os.listdir(normalized_local_path)) > 0:
                logger.warning(f"Target directory '{normalized_local_path}' exists and is not empty. Skipping clone.")
                # If it's an existing repo, try to update it; otherwise, raise an error
                if is_git_repository(normalized_local_path):
                    status = get_repo_status(normalized_local_path)
                    if status == "Needs Pull" or status == "Modified":
                        logger.info(f"Existing directory '{normalized_local_path}' is a Git repo. Attempting pull.")
                        pull_repository(normalized_local_path)
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
                "status": "Clean",  # Initial status
                "deleted": False
            }
            self.projects.append(new_project)
            self._save_projects()
            self.refresh_project_statuses()  # Update status immediately after adding
            logger.info(f"Project '{name}' added and cloned successfully.")
            return new_project
        except GitOperationError as e:
            logger.error(f"Git operation failed for project '{name}': {e}")
            raise  # Re-raise to be caught by UI
        except FileExistsError as e:
            logger.error(f"Cannot add project '{name}': {e}")
            raise  # Re-raise to be caught by UI
        except Exception as e:
            logger.error(f"An unexpected error occurred while adding project '{name}': {e}")
            raise  # Re-raise to be caught by UI

    def remove_project(self, local_path, permanent=False):
        project_found = False
        for i, project in enumerate(self.projects):
            if project['local_path'] == local_path:
                if permanent:
                    # Physical deletion
                    if os.path.exists(local_path):
                        try:
                            shutil.rmtree(local_path)
                            logger.info(f"Physically removed project folder: {local_path}")
                        except OSError as e:
                            logger.error(f"Error physically removing project folder {local_path}: {e}")
                            raise  # Re-raise to be caught by UI
                    else:
                        logger.warning(f"Attempted physical removal of non-existent folder: {local_path}")

                    self.projects.pop(i)  # Remove from list
                    logger.info(f"Project permanently removed from configuration: {local_path}")
                else:
                    # Soft deletion (mark as deleted)
                    project['deleted'] = True
                    project['status'] = "Deleted"
                    logger.info(f"Project marked as deleted: {local_path}")

                project_found = True
                break

        if project_found:
            self._save_projects()
            # If permanently deleted, also remove from UI list by reloading
            if permanent:
                self.refresh_project_statuses()  # Re-evaluate statuses if items were removed
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
                output = pull_repository(local_path)
                status = get_repo_status(local_path)
                project['status'] = status
                self._save_projects()
                logger.info(f"Project '{project['name']}' updated. Status: {status}")
                return "Up-to-date" if "Already up to date." in output else output
            except GitOperationError as e:
                logger.error(f"Failed to pull for project '{project['name']}': {e}")
                raise  # Re-raise to be caught by UI
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
            raise  # Re-raise to be caught by UI

    def set_base_folder(self, new_base_folder):
        self.base_folder = os.path.abspath(new_base_folder)
        logger.info(f"Base folder updated to: {self.base_folder}")
        # Consider updating paths for existing projects if they are children of the old base folder
        # For simplicity, we'll just update the base folder here and rely on scan_base_folder to resync
        self._save_projects()  # Save the config which contains the base folder

    def scan_base_folder(self):
        logger.info(f"Scanning base folder for new Git repositories: {self.base_folder}")
        found_count = 0
        existing_paths = {p['local_path'] for p in self.get_all_projects_including_deleted()}

        for root, dirs, files in os.walk(self.base_folder):
            if ".git" in dirs:
                repo_path = root
                if repo_path not in existing_paths:
                    try:
                        # Attempt to get name from folder, if not present, use a default
                        name = os.path.basename(repo_path)
                        # Try to get remote URL and branch
                        repo_url = self._get_repo_remote_url(repo_path)
                        branch = self._get_repo_current_branch(repo_path)

                        # Check for existing deleted projects to "undelete" them
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
                # Don't recurse into found Git repos
                dirs[:] = []
                continue
            # Remove .git directories from traversal to avoid re-processing or issues
            if ".git" in dirs:
                dirs.remove(".git")

        self._save_projects()
        self.refresh_project_statuses()  # Refresh all after scan
        logger.info(f"Scan complete. Found {found_count} new Git repositories.")
        return found_count

    def _get_repo_remote_url(self, local_path):
        """Helper to get the remote URL of a Git repository."""
        try:
            # Reemplazar _run_git_command con la función directa de git_operations
            # asumiendo que esa función está accesible o la implementas aquí.
            # Por ahora, usaré una simulación o la función de git_operations si existe.
            # Si _run_git_command es una función global en utils/git_operations, debe importarse.
            # Para este caso, asumo que `GitCommandError` viene de `git` (GitPython) y que
            # esta función se llama a través de `git.Repo(local_path).remotes.origin.url` o similar.
            # Si tienes una función auxiliar `_run_git_command` en `git_operations`, asegúrate de importarla.
            # Por simplicidad y para evitar circular dependencies, usaremos la lógica de GitPython aquí.
            from git import Repo
            repo = Repo(local_path)
            if repo.remotes:
                return repo.remotes.origin.url
            return "N/A (no remote)"
        except Exception: # Capturar cualquier error de GitPython
            return "N/A (no remote or error)"

    def _get_repo_current_branch(self, local_path):
        """Helper to get the current branch name of a Git repository."""
        try:
            from git import Repo
            repo = Repo(local_path)
            return repo.active_branch.name
        except Exception:
            return "N/A (detached HEAD or error)"

    def refresh_project_statuses(self):
        """Refreshes the status of all tracked projects."""
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
                project['status'] = "Deleted"  # Ensure deleted projects explicitly show "Deleted"
        self._save_projects()
        logger.info("All project statuses refreshed.")