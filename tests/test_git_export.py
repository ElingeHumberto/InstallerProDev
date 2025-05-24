import git
import pytest
from pathlib import Path
from installerpro.core import Core
from installerpro.installerpro_qt import InstallerProWindow

class DummyRepo:
    def __init__(self, path): pass
    @property
    def git(self):
        class G:
            def log(self, *args, **kwargs):
                return "abc123 2025-01-01 Commit message"
        return G()

@pytest.fixture(autouse=True)
def fake_repo(monkeypatch, tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.setattr(Core, "get_default_path", lambda self: str(project_dir))
    monkeypatch.setattr(git, "Repo", lambda path: DummyRepo(path))
    return project_dir

def test_handle_export_log_creates_file(fake_repo):
    win = InstallerProWindow()
    win.handle_export_log()
    out = Path(fake_repo) / "logs" / "commit_history.txt"
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "abc123 2025-01-01 Commit message" in content
    log = win.log_text.toPlainText().lower()
    assert "history exported" in log or "historial exportado" in log
