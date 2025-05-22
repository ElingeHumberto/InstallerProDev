"""Punto de entrada `python -m installerpro`."""

from __future__ import annotations

import argparse
import sys
from typing import Iterable

from installerpro import __version__


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="installerpro",
        # Descripción sin emojis, para no romper en PowerShell/CP1252
        description="InstallerPro  Automatic multi-project Git environment installer",
        add_help=False,
    )


def _print_help(parser: argparse.ArgumentParser) -> None:
    # Cabecera ASCII‐only para que PowerShell no lance UnicodeEncodeError
    print("InstallerPro  Automatic multi-project Git environment installer\n")
    parser.print_help(sys.stdout)

    # luego el help estándar
    parser.print_help(sys.stdout)


def main(argv: Iterable[str] | None = None) -> None:
    parser = _build_parser()

    # definimos -h/--help y --version
    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Show this help and exit",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s " + __version__,
    )

    # parseamos
    args = parser.parse_args(list(argv) if argv is not None else None)

    # si pidieron ayuda, la mostramos y salimos
    if args.help:
        _print_help(parser)
        return

    # si pidieron versión, argparse ya salió con exit(0)
    # sólo queda arrancar la GUI
    from installerpro.ui.gui import run_gui

    run_gui()


if __name__ == "__main__":
    main()
