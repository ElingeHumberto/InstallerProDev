"""Paquete principal de InstallerPro."""

from importlib.metadata import PackageNotFoundError, version as _version

try:  # instalación normal (pipy / git-tag)
    __version__ = _version(__name__)
except PackageNotFoundError:  # modo editable durante el dev
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]
