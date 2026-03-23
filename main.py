"""
filter_toolbox/__main__.py
==========================
Application entry point.

Run with:
    python -m filter_toolbox
or:
    python main.py
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from mainwindow import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Analog Filter Design Toolbox")
    app.setOrganizationName("ITESM – Circuits & Systems Lab")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
