import importlib
import subprocess
import sys
from pathlib import Path


def test_package_import():
    """El paquete se importa sin excepciones."""
    mod = importlib.import_module("installerpro")
    assert mod.__version__  # opcional: que exponga una versión


def test_cli_help():
    """El script `installerpro` responde con --help."""
    exe = Path(sys.executable)  # intérprete actual

    result = subprocess.run(
        [exe, "-m", "installerpro", "--help"],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0
    assert "InstallerPro" in result.stdout
