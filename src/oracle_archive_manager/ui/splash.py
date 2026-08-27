"""启动画面（Splash）：深色渐变 + 光晕 + 品牌细节，主窗体就绪前展示启动进度。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPen,
                            QPixmap, QRadialGradient)
from PySide6.QtWidgets import QApplication, QSplashScreen

from .icons import icon

_W, _H = 560, 400


def _render_pixmap(version: str) -> QPixmap:
    dpr = 2  # 2x 渲染，高分屏不糊
    pm = QPixmap(_W * dpr, _H * dpr)
    pm.setDevicePixelRatio(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)

    # 底色：深海军蓝对角渐变
    bg = QLinearGradient(0, 0, _W, _H)
    bg.setColorAt(0.0, QColor("#0a1024"))
    bg.setColorAt(0.55, QColor("#101b36"))
    bg.setColorAt(1.0, QColor("#162541"))
    p.fillRect(0, 0, _W, _H, bg)

    # 光晕：左上主光 + 右下辅光
    glow = QRadialGradient(150, 130, 330)
    glow.setColorAt(0, QColor(59, 130, 246, 66))
    glow.setColorAt(1, QColor(59, 130, 246, 0))
    p.fillRect(0, 0, _W, _H, glow)
    glow2 = QRadialGradient(_W - 70, _H + 10, 300)
    glow2.setColorAt(0, QColor(96, 165, 250, 40))
    glow2.setColorAt(1, QColor(96, 165, 250, 0))
    p.fillRect(0, 0, _W, _H, glow2)

    # 装饰轨道环（数据库圆柱意象），右下出血构图
    c = QPointF(_W - 56, _H - 24)
    for r, a, w in ((190, 46, 1.4), (262, 30, 1.2), (336, 20, 1.0)):
        p.setPen(QPen(QColor(96, 165, 250, a), w))
        p.drawEllipse(c, r, r)

    # 顶部品牌渐变细条
    bar = QLinearGradient(0, 0, _W, 0)
    bar.setColorAt(0, QColor("#2563eb"))
    bar.setColorAt(1, QColor("#60a5fa"))
    p.fillRect(0, 0, _W, 4, bar)

    # 版本徽标（右上胶囊）
    p.setBrush(QColor(59, 130, 246, 34))
    p.setPen(QPen(QColor(96, 165, 250, 92), 1))
    p.drawRoundedRect(_W - 122, 30, 92, 26, 13, 13)
    f = QFont("Microsoft YaHei")
    f.setPixelSize(12)
    p.setFont(f)
    p.setPen(QColor("#93c5fd"))
    p.drawText(QRectF(_W - 122, 30, 92, 26), Qt.AlignCenter, f"v{version}")

    # 图标玻璃底座 + 图标
    p.setBrush(QColor(255, 255, 255, 18))
    p.setPen(QPen(QColor(255, 255, 255, 40), 1))
    p.drawRoundedRect(56, 138, 96, 96, 22, 22)
    p.drawPixmap(68, 150, 72, 72, icon("app").pixmap(72, 72))

    # 标题（宽字距）
    f = QFont("Microsoft YaHei")
    f.setPixelSize(27)
    f.setBold(True)
    f.setLetterSpacing(QFont.PercentageSpacing, 104)
    p.setFont(f)
    p.setPen(QColor("#f5f8ff"))
    p.drawText(180, 176, "Oracle Archive Manager")

    # 副标题
    f.setPixelSize(14)
    f.setBold(False)
    f.setLetterSpacing(QFont.PercentageSpacing, 110)
    p.setFont(f)
    p.setPen(QColor("#93a8cc"))
    p.drawText(181, 206, "Oracle 历史数据归档管理工具")

    # 渐变分隔线
    line = QLinearGradient(181, 0, 476, 0)
    line.setColorAt(0, QColor(59, 130, 246, 170))
    line.setColorAt(1, QColor(59, 130, 246, 0))
    p.fillRect(181, 222, 295, 1, line)

    # 标语
    f.setLetterSpacing(QFont.PercentageSpacing, 106)
    f.setPixelSize(13)
    p.setFont(f)
    p.setPen(QColor("#64748b"))
    p.drawText(181, 248, "复制 · 校验 · 人工确认后清理，全程可暂停可恢复")

    # 版权（右下）
    f.setPixelSize(11)
    p.setFont(f)
    p.setPen(QColor("#5d6f96"))
    p.drawText(QRectF(0, 266, _W - 30, 20), Qt.AlignRight | Qt.AlignVCenter,
               "© xcode.im")

    p.end()
    return pm


def create_splash(app: QApplication, version: str = "0.1.0") -> QSplashScreen:
    splash = QSplashScreen(_render_pixmap(version))
    splash.setWindowTitle("Oracle Archive Manager")
    splash.show()
    splash_msg(splash, "正在启动…")
    app.processEvents()
    return splash


def splash_msg(splash: QSplashScreen | None, text: str) -> None:
    """更新启动进度文案并立即重绘（启动期无事件循环）。"""
    if splash is None:
        return
    splash.showMessage(text, Qt.AlignBottom | Qt.AlignHCenter, QColor("#7d93bd"))
    QApplication.processEvents()
