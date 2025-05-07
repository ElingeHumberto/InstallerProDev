# installerpro/installerpro_qt.py
import sys, asyncio
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QListWidget, QPushButton,
    QFileDialog, QMessageBox, QProgressBar, QLabel, QHBoxLayout
)
from PySide6.QtCore import Qt, QThread, Signal
from qasync import QEventLoop, asyncSlot
from installerpro import core

class Worker(QThread):
    progress = Signal(int, str)        # % , mensaje
    finished = Signal()

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs               # lista de nombres

    def run(self):
        total = len(self.jobs)
        for i, name in enumerate(self.jobs, 1):
            try:
                core.update_project(name)
                self.progress.emit(int(i/total*100), f"{name} listo")
            except Exception as e:
                self.progress.emit(int(i/total*100), f"Error {name}: {e}")
        self.finished.emit()

class MainWin(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("InstallerPro – Gestor de proyectos")
        self.resize(420, 300)

        self.list = QListWidget()
        self.btn_add     = QPushButton("Añadir")
        self.btn_del     = QPushButton("Eliminar")
        self.btn_update  = QPushButton("Actualizar seleccionados")
        self.progress    = QProgressBar()
        self.status      = QLabel("Listo")

        h = QHBoxLayout()
        h.addWidget(self.btn_add)
        h.addWidget(self.btn_del)
        h.addWidget(self.btn_update)

        lay = QVBoxLayout(self)
        lay.addWidget(self.list)
        lay.addLayout(h)
        lay.addWidget(self.progress)
        lay.addWidget(self.status)

        self.btn_add.clicked.connect(self.on_add)
        self.btn_del.clicked.connect(self.on_del)
        self.btn_update.clicked.connect(self.on_update)

        self.refresh_list()

    def refresh_list(self):
        self.list.clear()
        for p in core._load():
            self.list.addItem(p["name"])

    def on_add(self):
        url,_ = QFileDialog.getOpenFileName(self, "Pega o escribe URL Git", "", "")
        if not url:
            return
        name = Path(url).stem.replace(".git", "")
        try:
            core.add_project(name, url)
            self.refresh_list()
        except ValueError as e:
            QMessageBox.warning(self, "Ya existe", str(e))

    def on_del(self):
        item = self.list.currentItem()
        if not item:
            return
        core.remove_project(item.text())
        self.refresh_list()

    @asyncSlot()
    async def on_update(self):
        items = self.list.selectedItems() or self.list.findItems("*", Qt.MatchWrap | Qt.MatchWildcard)
        jobs  = [i.text() for i in items]
        self.progress.setValue(0)
        self.status.setText("Actualizando...")
        loop = asyncio.get_event_loop()
        worker = Worker(jobs)
        worker.progress.connect(lambda p,m: (self.progress.setValue(p), self.status.setText(m)))
        worker.finished.connect(lambda: self.status.setText("¡Todo listo!"))
        worker.start()

def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    win = MainWin()
    win.show()
    with loop:
        loop.run_forever()

if __name__ == "__main__":
    main()
