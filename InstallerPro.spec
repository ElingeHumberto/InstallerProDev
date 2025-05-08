# -*- mode: python ; coding: utf-8 -*-

# ------------------------------------------------------------------------------
#  InstallerPro.spec
#  Incluye el paquete local "installerpro" en el bundle
#  (datas, submódulos, hooks) y genera InstallerPro.exe
# ------------------------------------------------------------------------------

from pathlib import Path
from PyInstaller.utils.hooks import collect_all

# --- rutas --------------------------------------------------------------------
SRC_MAIN  = Path("installerpro") / "installerpro_qt.py"    # script de arranque
PKG_NAME  = "installerpro"                                 # paquete a incluir
ICON_FILE = None  # Ej: Path("Docs") / "logo.ico"          # icono opcional

# --- recopila todo el paquete -------------------------------------------------
pkg_datas, pkg_bins, pkg_hidden = collect_all(PKG_NAME)

# --- análisis -----------------------------------------------------------------
a = Analysis(
    [str(SRC_MAIN)],
    pathex=[],
    binaries=pkg_bins,
    datas=pkg_datas,
    hiddenimports=pkg_hidden,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# --- ejecutable ---------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="InstallerPro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,                  # ← sin consola
    icon=str(ICON_FILE) if ICON_FILE else None,
)

