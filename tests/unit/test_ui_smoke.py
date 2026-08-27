import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from oracle_archive_manager.app.controller import AppController
from oracle_archive_manager.storage.sqlite import ControlDB
from oracle_archive_manager.ui.main_window import MainWindow


def test_main_window_smoke(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = ControlDB(tmp_path / "c.db")
    db.migrate()
    window = MainWindow(AppController(db))
    window.show()
    assert window.windowTitle().startswith("Oracle Archive Manager")
    window.close()
    assert app is not None
