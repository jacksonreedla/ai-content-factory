# main.py
import sys

from PySide6.QtWidgets import QApplication

from app.container import Container
from gui.shell import MainWindow


def _needs_wizard(container) -> bool:
    return not container.paths.secrets_path.exists()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AI Content Factory")
    container = Container()
    container.bootstrap()

    # First-run wizard.
    if _needs_wizard(container):
        from gui.wizard import FirstRunWizard
        wizard = FirstRunWizard(container)
        if wizard.exec():
            wizard.persist()
            # Re-register plugins now that secrets may exist.
            container._register_plugins()

    win = MainWindow(container=container)
    win.dashboard.refresh()
    # Attach the logs view as the GUI log sink.
    win.logs.attach()
    # Start hourly analytics pull.
    container.start_analytics_scheduler()
    win.show()
    code = app.exec()
    container.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
