"""全局浅色主题 QSS：白卡片 + 蓝主色 + 深色导航，见 06_GUI_DESIGN.md。"""
from __future__ import annotations

from pathlib import Path

_CHEVRON = (Path(__file__).resolve().parent.parent
            / "resources" / "icons" / "chevron-down.svg").as_posix()
_CHEVRON_UP = (Path(__file__).resolve().parent.parent
               / "resources" / "icons" / "chevron-up.svg").as_posix()
_CHECK = (Path(__file__).resolve().parent.parent
          / "resources" / "icons" / "check-white.svg").as_posix()

THEME = """
QWidget { font-family:"Microsoft YaHei","Segoe UI",sans-serif; font-size:13px; color:#1f2937; }
QMainWindow, QDialog { background:#f5f6f8; }

QFrame#card { background:#ffffff; border:1px solid #e3e8ee; border-radius:10px; }
QFrame#group { background:#fbfcfe; border:1px solid #e8edf3; border-radius:8px; }
QLabel#card_title { font-size:14px; font-weight:600; }
QLabel#muted { color:#8a94a0; }
QLabel#big_blue { color:#2563eb; font-size:22px; font-weight:700; }

QPushButton { background:#ffffff; border:1px solid #d7dee8; border-radius:6px; padding:6px 14px; }
QPushButton:hover { background:#f0f4fa; border-color:#c3cede; }
QPushButton:disabled { color:#9aa4b2; background:#f3f4f6; border-color:#e3e8ee; }
QPushButton#primary { background:#2563eb; border:none; color:#ffffff; font-weight:600; }
QPushButton#primary:hover { background:#1d4ed8; }
QPushButton#primary:disabled { background:#a9c3f5; }
QPushButton#danger { color:#c0392b; }
QPushButton#flat { border:none; background:transparent; }
QPushButton#flat:hover { background:#eef2f7; }

QLineEdit, QComboBox, QSpinBox { background:#ffffff; border:1px solid #d7dee8; border-radius:6px; padding:5px 8px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color:#2563eb; }
QComboBox::drop-down { border:none; width:18px; }

QCheckBox { spacing:8px; }
QCheckBox::indicator { width:16px; height:16px; border-radius:4px; border:1px solid #c3cede; background:#ffffff; }
QCheckBox::indicator:hover { border-color:#2563eb; }
QCheckBox::indicator:checked { background:#2563eb; border-color:#2563eb; }
QCheckBox::indicator:checked:disabled { background:#a9c3f5; border-color:#a9c3f5; }
QCheckBox::indicator:disabled { border-color:#e3e8ee; background:#f3f4f6; }
QTableWidget, QListWidget#plainlist { background:#ffffff; border:1px solid #e8edf3; border-radius:6px; gridline-color:#eef1f5; }
QTableWidget::item:selected { background:#e8f0fe; color:#1f2937; }
QHeaderView::section { background:#f8fafc; border:none; border-bottom:1px solid #e3e8ee; padding:6px 8px; font-weight:600; color:#475569; }

QTabWidget::pane { border:none; }
QTabBar::tab { padding:8px 18px; border:none; color:#64748b; }
QTabBar::tab:selected { color:#2563eb; font-weight:600; border-bottom:2px solid #2563eb; }
QTabBar::tab:hover { color:#2563eb; }

QProgressBar { background:#e5e9f0; border:none; border-radius:5px; height:10px; }
QProgressBar::chunk { background:#2563eb; border-radius:5px; }

QStatusBar { background:#ffffff; border-top:1px solid #e3e8ee; }
QScrollBar:vertical { background:transparent; width:10px; }
QScrollBar::handle:vertical { background:#c9d2dd; border-radius:5px; min-height:24px; }
QScrollBar:horizontal { background:transparent; height:10px; }
QScrollBar::handle:horizontal { background:#c9d2dd; border-radius:5px; min-width:24px; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; width:0; }

QListWidget#tasklist, QListWidget#connlist { background:transparent; border:none; }
QListWidget#tasklist::item, QListWidget#connlist::item { background:transparent; border:none; padding:4px; }
QListWidget#tasklist::item:selected, QListWidget#connlist::item:selected { background:transparent; }

QFrame#listitem { background:#ffffff; border:1px solid #e8edf3; border-radius:8px; }
QFrame#listitem[selected="true"] { background:#e8f0fe; border-color:#bcd3f7; }
QLabel#badge_on { color:#16a34a; border:1px solid #bbe5c8; background:#eafaf0; border-radius:4px; padding:2px 8px; font-size:12px; }
QLabel#badge_off { color:#6b7280; border:1px solid #d7dee8; background:#f3f4f6; border-radius:4px; padding:2px 8px; font-size:12px; }
QLabel#pill { background:#2563eb; color:#ffffff; border-radius:5px; padding:4px 12px; font-weight:600; }
"""

# QSS 主题化后 Qt 不再绘制默认下拉箭头，需显式提供图标
THEME += f"""
QComboBox::down-arrow {{ image: url("{_CHEVRON}"); width:12px; height:12px; }}

QCheckBox::indicator:checked {{ image: url("{_CHECK}"); width:12px; height:12px; }}

QSpinBox::up-button, QSpinBox::down-button {{ subcontrol-origin:border; width:20px; border:none; background:transparent; }}
QSpinBox::up-button {{ subcontrol-position:top right; }}
QSpinBox::down-button {{ subcontrol-position:bottom right; }}
QSpinBox::up-arrow {{ image: url("{_CHEVRON_UP}"); width:10px; height:10px; }}
QSpinBox::down-arrow {{ image: url("{_CHEVRON}"); width:10px; height:10px; }}
"""


def apply_theme(app) -> None:
    app.setStyleSheet(THEME)
