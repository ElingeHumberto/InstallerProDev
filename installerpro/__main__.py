"""Punto de entrada para `python -m installerpro`."""

from installerpro.ui.gui import main as _main


def main() -> None:  # pragma: no cover
    """Delegar en `installerpro.ui.gui.main` (mismo comportamiento)."""
    _main()


if __name__ == "__main__":
    main()
