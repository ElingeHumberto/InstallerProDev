"""
Subpaquete *installerpro.core*.

Reexporta:
    Core, config, logger
"""

from .main import Core          # ← único import necesario
from . import config, logger

# Alias opcional sólo para main (mantiene compatibilidad)
import sys as _sys
from importlib import import_module
_sys.modules.setdefault(__name__ + ".main",
                        import_module(".main", __name__))

__all__ = ["Core", "config", "logger"]
