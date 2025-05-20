# ─── installerpro/core/main.py ──────────────────────────────────────────────
from __future__ import annotations
import json
import shutil
import subprocess
from pathlib import Path


class Core:
    """
    Lógica de negocio:
      - Guardar/cargar carpeta por defecto
      - Listar proyectos (subdirectorios)
      - Añadir/quitar proyectos
      - Git pull / push
      - Exportar log de commits
    """

    _CONFIG_FILE = Path.home() / ".installerpro.json"

    def get_default_path(self) -> str:
        cfg = self._load_config()
        path = Path(cfg.get("default_folder", Path.home() / "Projects"))
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    def set_default_path(self, new_path: str) -> None:
        cfg = self._load_config()
        cfg["default_folder"] = new_path
        self._save_config(cfg)

    def list_projects(self, folder: str | None = None) -> list[dict]:
        base = Path(folder or self.get_default_path())
        if not base.is_dir():
            return []
        result: list[dict] = []
        for p in sorted(base.iterdir()):
            if p.is_dir():
                result.append({"name": p.name, "path": str(p)})
        return result

    def add_project(self, path: str) -> None:
        """
        Para nuestro caso, no movemos nada: simplemente
        cambiamos la carpeta por defecto a la ruta elegida.
        """
        self.set_default_path(path)

    def remove_project(self, path: str) -> None:
        """
        Borra completamente la carpeta de un proyecto.
        """
        shutil.rmtree(path, ignore_errors=True)

    def update_project(self, repo_path: str) -> None:
        repo = Path(repo_path)
        if not (repo / ".git").is_dir():
            raise RuntimeError(f"{repo} no es un repositorio Git")
        cp = subprocess.run(
            ["git", "-C", str(repo), "pull", "--ff-only"],
            capture_output=True, text=True, check=False
        )
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or "git pull falló")

    def push(self, repo_path: str) -> None:
        repo = Path(repo_path)
        if not (repo / ".git").is_dir():
            raise RuntimeError(f"{repo} no es un repositorio Git")
        cp = subprocess.run(
            ["git", "-C", str(repo), "push"],
            capture_output=True, text=True, check=False
        )
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or "git push falló")

    def export_log(self) -> str:
        """
        Crea un fichero con el git log --oneline de la carpeta actual
        o de default_path, lo pone en ~/Projects/logs/commit_history_YYYYMMDD_HHMM.txt
        """
        base = Path(self.get_default_path()) / "logs"
        base.mkdir(parents=True, exist_ok=True)
        fname = base / f"commit_history_{Path().resolve().stem}_{Path().name}.txt"
        cp = subprocess.run(
            ["git", "-C", self.get_default_path(), "log", "--oneline"],
            capture_output=True, text=True, check=False
        )
        if cp.returncode != 0:
            raise RuntimeError(cp.stderr.strip() or "Error al ejecutar git log")
        fname.write_text(cp.stdout, encoding="utf-8")
        return str(fname)

    @classmethod
    def _load_config(cls) -> dict:
        if cls._CONFIG_FILE.is_file():
            try:
                return json.loads(cls._CONFIG_FILE.read_text("utf-8"))
            except Exception:
                pass
        return {}

    @classmethod
    def _save_config(cls, data: dict) -> None:
        cls._CONFIG_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
