"""图标加载：resources/icons/*.svg，按名称缓存，支持整体换色。"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_DIR = Path(__file__).resolve().parent.parent / "resources" / "icons"


@lru_cache(maxsize=None)
def icon(name: str, color: str = "") -> QIcon:
    """加载图标；color 非空时把 svg 内所有十六进制颜色替换为该色（如白图标配蓝底按钮）。"""
    path = _DIR / f"{name}.svg"
    if not color:
        return QIcon(str(path))
    data = re.sub(r"#[0-9a-fA-F]{6}", color, path.read_text(encoding="utf-8"))
    renderer = QSvgRenderer(QByteArray(data.encode("utf-8")))
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
