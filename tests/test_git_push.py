import git
import pytest
from installerpro.core import Core
from installerpro.installerpro_qt import InstallerProWindow

class DummyRepo:
    def __init__(self, path): pass
    def remote(self, name):
        class R:
            def push(self): pass
        return R()

@pytest.fixture(autouse=True)
def fake_repo(monkeypatch, tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    monkeypatch.setattr(Core, "get_default_path", lambda self: str(project_dir))
    monkeypatch.setattr(git, "Repo", lambda path: DummyRepo(path))
    return project_dir

def test_handle_push_no_exception(fake_repo):
    win = InstallerProWindow()
    win.handle_push()  # no debe lanzar
    log = win.log_text.toPlainText().lower()
    assert "pushed" in log or "sincronizado" in log
