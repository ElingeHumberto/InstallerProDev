import sys
from PySide6.QtWidgets import QApplication, QLabel

app = QApplication(sys.argv)
label = QLabel("¡Hola, InstallerPro!")
label.resize(260, 80)
label.show()
sys.exit(app.exec())
