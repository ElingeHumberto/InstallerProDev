import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QListWidget,
    QTextEdit,
    QListWidgetItem,
    QPushButton,
    QFileDialog,
    QDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt

# ───────────────────────────────────────────────────────────────
#  Dependencias internas
# ───────────────────────────────────────────────────────────────
from installerpro.core import Core
from installerpro.i18n import set_language, t, available_langs, I18n


# ───────────────────────────────────────────────────────────────
#  Ventana principal
# ───────────────────────────────────────────────────────────────
class InstallerProWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.core = Core()
        self.i18n = I18n("es")  # idioma inicial

        self._setup_ui()
        self._setup_connections()
        self.load_projects_from()  # precarga lista

    # ───────────────────────────── UI
    def _setup_ui(self) -> None:
        self.setWindowTitle("InstallerPro")
        central = QWidget()
        self.setCentralWidget(central)
        main = QVBoxLayout(central)

        # ─── selector de idioma ──────────────────────────────
        top = QHBoxLayout()
        self.lang_lbl = QLabel(t("label.language"))
        self.lang_cmb = QComboBox()
        self.lang_cmb.addItems(available_langs())
        self.lang_cmb.setCurrentText("es")
        top.addWidget(self.lang_lbl)
        top.addWidget(self.lang_cmb, 1)
        main.addLayout(top)

        # ─── lista de proyectos ──────────────────────────────
        self.lst = QListWidget()
        main.addWidget(self.lst)

        # ─── panel de log ────────────────────────────────────
        self.log = QTextEdit(readOnly=True)
        main.addWidget(self.log, 1)

        # ─── botones básicos ─────────────────────────────────
        row1 = QHBoxLayout()
        self.btn_add = QPushButton(t("button.add"))
        self.btn_remove = QPushButton(t("button.remove"))
        self.btn_update = QPushButton(t("button.update"))
        self.btn_default = QPushButton(t("button.default_folder"))
        self.btn_help = QPushButton(t("button.help"))
        for b in (
            self.btn_add,
            self.btn_remove,
            self.btn_update,
            self.btn_default,
            self.btn_help,
        ):
            row1.addWidget(b)
        main.addLayout(row1)

        # ─── botones Git avanzados ───────────────────────────
        row2 = QHBoxLayout()
        self.btn_push = QPushButton(t("button.push"))
        self.btn_history = QPushButton(t("button.history"))
        self.btn_status = QPushButton(t("button.status"))
        self.btn_branch_new = QPushButton(t("button.branch_new"))
        self.btn_branch_sw = QPushButton(t("button.branch_switch"))
        self.btn_merge = QPushButton(t("button.merge_main"))
        for b in (
            self.btn_push,
            self.btn_history,
            self.btn_status,
            self.btn_branch_new,
            self.btn_branch_sw,
            self.btn_merge,
        ):
            row2.addWidget(b)
        main.addLayout(row2)

        # tooltips (se actualizan en cambio de idioma)
        self._refresh_tooltips()

        # ─── diálogo de ayuda ────────────────────────────────
        self.dlg_help = QDialog(self)
        self.dlg_help.setWindowTitle(t("help.title"))
        dlg_lay = QVBoxLayout(self.dlg_help)
        self.help_txt = QTextEdit(readOnly=True)
        dlg_lay.addWidget(self.help_txt)

    # ───────────────────────────── señales
    def _setup_connections(self) -> None:
        self.lang_cmb.currentTextChanged.connect(self._on_lang)
        self.btn_default.clicked.connect(self._on_set_default)
        self.btn_update.clicked.connect(self._on_update_selected)
        self.btn_help.clicked.connect(self._show_help)
        self.btn_add.clicked.connect(self._on_add)
        self.btn_remove.clicked.connect(self._on_remove)

        # git
        self.btn_push.clicked.connect(self._on_push)
        self.btn_history.clicked.connect(self._on_history)
        self.btn_status.clicked.connect(self._on_status)
        self.btn_branch_new.clicked.connect(self._on_branch_new)
        self.btn_branch_sw.clicked.connect(self._on_branch_switch)
        self.btn_merge.clicked.connect(self._on_merge_main)

    # ───────────────────────────── callbacks
    def _on_lang(self, lang: str) -> None:
        set_language(lang)  # cambia global
        self.lang_lbl.setText(t("label.language"))
        self.btn_add.setText(t("button.add"))
        self.btn_remove.setText(t("button.remove"))
        self.btn_update.setText(t("button.update"))
        self.btn_default.setText(t("button.default_folder"))
        self.btn_help.setText(t("button.help"))
        self.btn_push.setText(t("button.push"))
        self.btn_history.setText(t("button.history"))
        self.btn_status.setText(t("button.status"))
        self.btn_branch_new.setText(t("button.branch_new"))
        self.btn_branch_sw.setText(t("button.branch_switch"))
        self.btn_merge.setText(t("button.merge_main"))
        self.dlg_help.setWindowTitle(t("help.title"))
        self._refresh_tooltips()
        self._log(f"{t('log.lang_changed')}: {lang}")

    # ─── carpeta por defecto
    def _on_set_default(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            t("dlg_default_path.title"),
            self.core.get_default_path() or str(Path.home()),
        )
        if not folder:
            return
        self.core.set_default_path(folder)
        self.load_projects_from(folder)
        self._log(t("log.default_path_set").format(folder=folder))

    # ─── añadir proyecto
    def _on_add(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            t("dlg_add.browse_title"),
            self.core.get_default_path() or str(Path.home()),
        )
        if not folder:
            return
        try:
            self.core.add_project(folder)
            self.load_projects_from()
            self._log(t("log.added"))
        except Exception as e:
            QMessageBox.critical(self, t("error.generic"), t("error.add_error"))
            self._log(f"{e}")

    # ─── eliminar proyecto
    def _on_remove(self) -> None:
        idxs = list(self.lst.selectedIndexes())
        if not idxs:
            return
        names = [self.lst.item(i.row()).text() for i in idxs]
        if (
            QMessageBox.question(
                self,
                t("confirm.confirm"),
                t("confirm.delete").format(name=", ".join(names)),
            )
            != QMessageBox.Yes
        ):
            return
        for i in reversed(idxs):
            name = self.lst.item(i.row()).text()
            self.core.remove_project(name)
        self.load_projects_from()
        self._log(t("log.removed"))

    # ─── actualizar (pull/clone)
    def _on_update_selected(self) -> None:
        sel = list(self.lst.selectedIndexes())
        if not sel:
            return
        for i in sel:
            name = self.lst.item(i.row()).text()
            self._log(t("log.updating").format(name=name))
            try:
                self.core.update_project(name)
                self._log(t("log.updated").format(name=name))
            except Exception as e:
                self._log(f"{t('error.update_error')}: {e}")

    # ─── mostrar ayuda
    def _show_help(self) -> None:
        lang = self.i18n._lang
        md_path = Path(__file__).resolve().parent.parent / "Docs" / f"ayuda_{lang}.md"
        if not md_path.exists():
            self.help_txt.setPlainText(t("help.not_found"))
        else:
            self.help_txt.setPlainText(md_path.read_text(encoding="utf-8"))
        self.dlg_help.exec_()

    # ───────────────────────────── Git helpers
    def _git(self, args, cwd=None) -> tuple[bool, str]:
        try:
            out = subprocess.check_output(
                ["git"] + args,
                cwd=cwd,
                stderr=subprocess.STDOUT,
                text=True,
                shell=False,
            )
            return True, out.strip()
        except subprocess.CalledProcessError as e:
            return False, e.output.strip()

    def _selected_repo_path(self) -> Path | None:
        items = self.lst.selectedItems()
        if not items:
            return None
        name = items[0].text()
        return Path(self.core.get_default_path()) / name

    # push
    def _on_push(self) -> None:
        repo = self._selected_repo_path()
        if not repo:
            return
        ok, out = self._git(["push"], cwd=repo)
        if ok:
            self._log(t("log.pushed"))
        else:
            self._log(f"{t('error.push')}: {out}")

    # commit history
    def _on_history(self) -> None:
        repo = self._selected_repo_path()
        if not repo:
            return
        hist_file = repo / "commit_history.txt"
        ok, out = self._git(
            ["log", "--pretty=format:%h %ad %s", "--date=short"], cwd=repo
        )
        if ok:
            hist_file.write_text(out, encoding="utf-8")
            self._log(t("log.history_saved").format(path=hist_file))
        else:
            self._log(f"{t('error.history')}: {out}")

    # status
    def _on_status(self) -> None:
        repo = self._selected_repo_path()
        if not repo:
            return
        ok, out = self._git(["status", "-s"], cwd=repo)
        if ok:
            QMessageBox.information(self, "Git Status", out or t("status.ok"))
        else:
            QMessageBox.critical(self, "Git", out)

    # crear rama
    def _on_branch_new(self) -> None:
        repo = self._selected_repo_path()
        if not repo:
            return
        branch, ok = QInputDialog.getText(
            self, t("branch.new_title"), t("branch.new_prompt")
        )
        if not ok or not branch:
            return
        ok, out = self._git(["checkout", "-b", branch], cwd=repo)
        self._log(out if ok else f"Git: {out}")

    # cambiar rama
    def _on_branch_switch(self) -> None:
        repo = self._selected_repo_path()
        if not repo:
            return
        branch, ok = QInputDialog.getText(
            self, t("branch.sw_title"), t("branch.sw_prompt")
        )
        if not ok or not branch:
            return
        ok, out = self._git(["checkout", branch], cwd=repo)
        self._log(out if ok else f"Git: {out}")

    # merge a main
    def _on_merge_main(self) -> None:
        repo = self._selected_repo_path()
        if not repo:
            return
        ok, out = self._git(["checkout", "main"], cwd=repo)
        if not ok:
            self._log(out)
            return
        branch, ok2 = QInputDialog.getText(self, t("merge.title"), t("merge.prompt"))
        if not ok2 or not branch:
            return
        ok, out = self._git(["merge", branch], cwd=repo)
        self._log(out if ok else f"Git: {out}")

    # ───────────────────────────── utilidades
    def _refresh_tooltips(self) -> None:
        self.btn_add.setToolTip(t("tooltip.add"))
        self.btn_remove.setToolTip(t("tooltip.remove"))
        self.btn_update.setToolTip(t("tooltip.update"))
        self.btn_default.setToolTip(t("tooltip.default_folder"))
        self.btn_help.setToolTip(t("tooltip.help"))
        self.btn_push.setToolTip(t("tooltip.push"))
        self.btn_history.setToolTip(t("tooltip.history"))
        self.btn_status.setToolTip(t("tooltip.status"))
        self.btn_branch_new.setToolTip(t("tooltip.branch_new"))
        self.btn_branch_sw.setToolTip(t("tooltip.branch_switch"))
        self.btn_merge.setToolTip(t("tooltip.merge_main"))

    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("[%H:%M:%S]")
        self.log.append(f"{ts} {msg}")

    # carga proyectos
    def load_projects_from(self, base: str | None = None) -> None:
        path = Path(base) if base else Path(self.core.get_default_path() or "")
        self.lst.clear()
        if path.is_dir():
            for p in sorted(path.iterdir()):
                if (p / ".git").is_dir():
                    self.lst.addItem(QListWidgetItem(p.name))
        self._log(t("log.refreshed"))


# ───────────────────────────────────────────────────────────────
#  Bootstrap
# ───────────────────────────────────────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    win = InstallerProWindow()
    win.resize(800, 600)
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
