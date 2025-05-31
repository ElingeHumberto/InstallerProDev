import os
import threading
import time
import pytest

pytest.importorskip("tkinter")  # si Tk no está disponible, salta

DISPLAY = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
CI = os.environ.get("CI") == "true"


@pytest.mark.skipif(CI and not DISPLAY, reason="No display in CI runner")
def test_window_opens_and_closes():
    """Crea la ventana y la cierra enseguida para comprobar que no lanza excepciones."""

    import installerpro.ui.gui as gui

    # Arranca la GUI en un thread para no bloquear pytest
    th = threading.Thread(target=gui.run_gui, daemon=True)
    th.start()

    time.sleep(1)  # espera a que se cree la ventana

    # Termina la app limpiamente
    gui.root.after(0, gui.root.destroy)
    th.join(timeout=3)

    assert not th.is_alive()
