# main.py
import sys

from PySide6.QtWidgets import QApplication

from app.container import Container
from gui.shell import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AI Content Factory")
    container = Container()
    container.bootstrap()
    win = MainWindow(container=container)
    win.dashboard.refresh()
    win.show()
    code = app.exec()
    container.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
