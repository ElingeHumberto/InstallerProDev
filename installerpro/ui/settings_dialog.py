# ─── installerpro/ui/settings_dialog.py ────────────────────────────────────
import json
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox,
    QPushButton, QFileDialog, QHBoxLayout, QLabel
)

# config.json estará al mismo nivel que installerpro_qt.py
SETTINGS_FILE = Path(__file__).resolve().parent.parent / "config.json"

def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Default folder + Browse
        self.default_folder = QLineEdit()
        browse = QPushButton(self.tr("Browse…"))
        browse.clicked.connect(self._browse_folder)
        h = QHBoxLayout()
        h.addWidget(self.default_folder)
        h.addWidget(browse)
        form.addRow(self.tr("Default folder:"), h)

        # Dark mode
        self.dark_mode = QCheckBox(self.tr("Dark mode"))
        form.addRow("", self.dark_mode)

        # Git user.name / email
        self.git_name  = QLineEdit()
        self.git_email = QLineEdit()
        form.addRow(self.tr("Git user.name:"),  self.git_name)
        form.addRow(self.tr("Git user.email:"), self.git_email)

        layout.addLayout(form)

        # Cancel / Save
        btns = QHBoxLayout()
        self.btn_cancel = QPushButton(self.tr("Cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save   = QPushButton(self.tr("Save"))
        self.btn_save.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_save)
        layout.addLayout(btns)

        # Cargo valores previos
        data = load_settings()
        self.default_folder.setText(data.get("default_folder", ""))
        self.dark_mode.setChecked(data.get("dark_mode", False))
        git = data.get("git", {})
        self.git_name.setText(git.get("name", ""))
        self.git_email.setText(git.get("email", ""))

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, self.tr("Select default folder"))
        if path:
            self.default_folder.setText(path)

    def accept(self):
        # 1) Guardar config.json
        cfg = {
            "default_folder": self.default_folder.text(),
            "dark_mode":      self.dark_mode.isChecked(),
            "git": {
                "name":  self.git_name.text(),
                "email": self.git_email.text()
            }
        }
        SETTINGS_FILE.write_text(
            json.dumps(cfg, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        # 2) Configurar Git si hay valores
        name  = cfg["git"]["name"]
        email = cfg["git"]["email"]
        if name:
            subprocess.run(["git", "config", "--global", "user.name", name], check=False)
        if email:
            subprocess.run(["git", "config", "--global", "user.email", email], check=False)

        super().accept()
