"""程序入口。"""
from __future__ import annotations

import sys

from loguru import logger
from PySide6.QtWidgets import QApplication

from . import __version__
from .app.controller import AppController
from .services.scheduler import Scheduler
from .storage.sqlite import ControlDB
from .ui.icons import icon
from .ui.main_window import MainWindow
from .ui.splash import create_splash, splash_msg
from .ui.theme import apply_theme
from .ui.update_dialog import start_background_check
from .utils.config import AppConfig
from .utils.logging import app_data_dir, setup_logging


def main() -> int:
    cfg = AppConfig()
    setup_logging(int(cfg.get("log_retention_days")))

    app = QApplication(sys.argv)
    apply_theme(app)
    app.setApplicationName("Oracle Archive Manager")
    app.setApplicationVersion(__version__)
    app.setWindowIcon(icon("app"))

    splash = create_splash(app, app.applicationVersion())
    try:
        splash_msg(splash, "正在初始化控制库…")
        db = ControlDB(app_data_dir() / "archive_manager.db")
        db.migrate()
        splash_msg(splash, "正在加载配置与任务…")
        controller = AppController(db, cfg)
        pruned = controller.runs.prune_logs(int(cfg.get("db_log_retention_days")))
        if pruned:
            logger.info(f"已清理控制库过期日志 {pruned} 条（P1 自动清理）")
        splash_msg(splash, "正在构建主界面…")
        window = MainWindow(controller)
        splash_msg(splash, "就绪")
        window.show()
        splash.finish(window)
        Scheduler(controller, parent=window).start()  # P2：应用内每日定时调度
        if cfg.get("check_updates"):  # 启动后台检查 GitHub 最新版本（OTA 引导）
            start_background_check(window, silent=True)
    except Exception:
        splash.close()
        raise
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
