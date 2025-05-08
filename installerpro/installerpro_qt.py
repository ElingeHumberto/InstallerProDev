from pathlib import Path
import sys, json, asyncio
from urllib.parse import urlparse

from PySide6.QtCore    import Qt, QSettings, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QListWidget, QPushButton,
    QFileDialog, QDialog, QLineEdit, QFormLayout, QVBoxLayout,
    QHBoxLayout, QMessageBox, QProgressBar, QMenuBar, QMenu, QAction
)
from qasync           import QEventLoop, asyncSlot
from installerpro     import core

APP_DIR   = Path(__file__).resolve().parent
I18N_DIR  = APP_DIR / "i18n"
SETTINGS  = QSettings("InstallerPro", "InstallerPro")

def load_strings(lang):
    fn = I18N_DIR / f"{lang}.json"
    return json.loads(fn.read_text(encoding="utf-8"))

LANG = SETTINGS.value("lang", "es")
TXT  = load_strings(LANG)

# ---------- diálogo Añadir ---------------------------------------------------
class AddDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(TXT["dlg_add"]["title"])
        self.le_name   = QLineEdit()
        self.le_url    = QLineEdit()
        self.le_branch = QLineEdit("main")
        self.le_path   = QLineEdit(f"C:/Workspace/")
        btn_browse     = QPushButton(TXT["dlg_add"]["browse"])
        btn_browse.clicked.connect(self.on_browse)

        form = QFormLayout()
        form.addRow(TXT["dlg_add"]["name"],   self.le_name)
        form.addRow(TXT["dlg_add"]["url"],    self.le_url)
        form.addRow(TXT["dlg_add"]["branch"], self.le_branch)

        h = QHBoxLayout()
        h.addWidget(self.le_path, 1)
        h.addWidget(btn_browse)

        form.addRow(TXT["dlg_add"]["path"], h)

        btn_ok = QPushButton(TXT["dlg_add"]["ok"])
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton(TXT["dlg_add"]["cancel"])
        btn_cancel.clicked.connect(self.reject)

        b = QHBoxLayout()
        b.addStretch()
        b.addWidget(btn_ok)
        b.addWidget(btn_cancel)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addLayout(b)

    def on_browse(self):
        path = QFileDialog.getExistingDirectory(self, TXT["dlg_add"]["browse"])
        if path:
            self.le_path.setText(path)

# ---------- hilo de actualización -------------------------------------------
class Worker(QThread):
    progress = Signal(int, str)
    finished = Signal()

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs

    def run(self):
        total = len(self.jobs)
        for i, name in enumerate(self.jobs, 1):
            try:
                core.update_project(name)
                self.progress.emit(int(i/total*100), f"{name} ✔")
            except Exception as e:
                self.progress.emit(int(i/total*100), f"{name}: {e}")
        self.finished.emit()

# ---------- ventana principal ------------------------------------------------
class MainWin(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(TXT["title"])
        self.resize(520, 320)

        # --- menú idioma -----------------------------------------------------
        menubar = QMenuBar()
        menu_lang = QMenu(TXT["menu_lang"])
        act_es = QAction("Español", self, checkable=True, checked=LANG=="es")
        act_en = QAction("English", self, checkable=True, checked=LANG=="en")

        act_es.triggered.connect(lambda: self.set_lang("es"))
        act_en.triggered.connect(lambda: self.set_lang("en"))
        menu_lang.addActions([act_es, act_en])
        menubar.addMenu(menu_lang)

        # --- widgets principales --------------------------------------------
        self.list   = QListWidget()
        self.btn_add= QPushButton(TXT["btn_add"])
        self.btn_del= QPushButton(TXT["btn_del"])
        self.btn_upd= QPushButton(TXT["btn_upd"])
        self.progress = QProgressBar()
        self.status   = QLabel(TXT["status_ok"])

        h = QHBoxLayout()
        h.addWidget(self.btn_add)
        h.addWidget(self.btn_del)
        h.addWidget(self.btn_upd)

        lay = QVBoxLayout(self)
        lay.setMenuBar(menubar)
        lay.addWidget(self.list, 1)
        lay.addLayout(h)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)

        # conexiones
        self.btn_add.clicked.connect(self.on_add)
        self.btn_del.clicked.connect(self.on_del)
        self.btn_upd.clicked.connect(self.on_update)

        self.refresh_list()

    # ------- idioma ---------------------------------------------------------
    def set_lang(self, lang):
        SETTINGS.setValue("lang", lang)
        QMessageBox.information(self, "InstallerPro",
                                "Reinicia la aplicación para cambiar idioma.")
    # ------------------------------------------------------------------------
    def refresh_list(self):
        self.list.clear()
        for p in core._load():
            self.list.addItem(p["name"])

    def on_add(self):
        dlg = AddDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        name   = dlg.le_name.text().strip()
        url    = dlg.le_url.text().strip()
        branch = dlg.le_branch.text().strip() or "main"
        path   = dlg.le_path.text().strip() or f"C:/Workspace/{name}"

        # validaciones básicas
        if not name or not urlparse(url).scheme.startswith("http"):
            QMessageBox.warning(self, "Error", "Datos inválidos.")
            return
        try:
            core.add_project(name, url, branch, path)
            self.refresh_list()
        except ValueError:
            QMessageBox.warning(self, TXT["msg_exists"], TXT["msg_exists"])

    def on_del(self):
        item = self.list.currentItem()
        if item:
            core.remove_project(item.text())
            self.refresh_list()

    @asyncSlot()
    async def on_update(self):
        items = self.list.selectedItems() or self.list.findItems("*", Qt.MatchWildcard)
        jobs  = [i.text() for i in items]
        if not jobs:
            return
        self.progress.setValue(0)
        self.status.setText(TXT["status_run"])
        worker = Worker(jobs)
        worker.progress.connect(lambda p,m: (self.progress.setValue(p),
                                             self.status.setText(m)))
        worker.finished.connect(lambda: self.status.setText(TXT["status_ok"]))
        worker.start()

# ---------- main -------------------------------------------------------------
def main():
    app  = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    win = MainWin()
    win.show()
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()
