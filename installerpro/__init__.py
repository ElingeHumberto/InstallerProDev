"""Paquete principal de InstallerPro."""

from importlib.metadata import PackageNotFoundError, version as _version

try:  # instalación normal (pip / git-tag)
    __version__ = _version(__name__)
except PackageNotFoundError:  # modo editable durante el dev
    __version__ = "4.0.1-dev"

import sys as _sys
from importlib import import_module

from .core.main import Core
core = import_module(".core", __name__)

# alias opcional para compatibilidad antigua: installerpro.main
_sys.modules.setdefault(
    __name__ + ".main",
    import_module(".main", __name__),
)

__all__ = ["__version__", "Core", "core"]
