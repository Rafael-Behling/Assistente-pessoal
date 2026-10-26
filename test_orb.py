import sys
from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import Qt

app = QApplication(sys.argv)
label = QLabel("OK")
label.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
label.show()
print("shown")
sys.exit(app.exec())
