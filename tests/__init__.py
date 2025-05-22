"""Paquete principal de InstallerPro."""

from importlib.metadata import PackageNotFoundError, version as _version

try:  # cuando esté instalado desde PyPI / git tag
    __version__ = _version(__name__)
except PackageNotFoundError:  # instalación editable durante el dev
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]
