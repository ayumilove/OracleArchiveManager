"""通用 UI 组件：卡片 / 键值行 / 五步进度条，样式对齐 06 设计稿。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .icons import icon

GREEN, BLUE, GRAY = "#16a34a", "#2563eb", "#c9d2dd"

# 状态胶囊配色：(文字, 边框, 底色)——柔和底 + 深色字，刺眼度低且清晰
STATUS_PILL = {
    "RUNNING": ("#2563eb", "#bfdbfe", "#eff6ff"),
    "PAUSING": ("#b45309", "#fde68a", "#fffbeb"),
    "PAUSED": ("#b45309", "#fde68a", "#fffbeb"),
    "VERIFIED": ("#15803d", "#bbf7d0", "#f0fdf4"),
    "COMPLETED": ("#15803d", "#bbf7d0", "#f0fdf4"),
    "FAILED": ("#b91c1c", "#fecaca", "#fef2f2"),
    "CANCELED": ("#4b5563", "#e5e7eb", "#f9fafb"),
}


def apply_pill(lbl, status: str) -> None:
    """给 QLabel 套上状态胶囊样式；未知状态用中性灰。"""
    fg, bd, bg = STATUS_PILL.get(status, ("#4b5563", "#e5e7eb", "#f9fafb"))
    lbl.setStyleSheet(
        f"color:{fg}; border:1px solid {bd}; background:{bg}; "
        "border-radius:5px; padding:3px 12px; font-size:12px; font-weight:600;"
    )


def card(title: str = "", action_text: str = "", action_icon: str = "") -> tuple[QFrame, QVBoxLayout, QPushButton | None]:
    """白卡片容器，返回 (frame, body_layout, action_button)。"""
    frame = QFrame()
    frame.setObjectName("card")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(14, 12, 14, 12)
    outer.setSpacing(10)

    btn = None
    if title or action_text:
        head = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setObjectName("card_title")
        head.addWidget(lbl)
        head.addStretch(1)
        if action_text:
            btn = QPushButton(action_text)
            if action_icon:
                btn.setIcon(icon(action_icon))
            head.addWidget(btn)
        outer.addLayout(head)
    return frame, outer, btn


def kv_grid() -> tuple[QWidget, dict]:
    """键值对网格；返回 (widget, {row: (label, value_label)}) 的构造辅助。"""
    w = QWidget()
    grid = QGridLayout(w)
    grid.setContentsMargins(12, 10, 12, 10)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(8)
    state = {"grid": grid, "row": 0}

    def add_row(key: str, value: str = "—", value_color: str = "") -> QLabel:
        k = QLabel(key)
        k.setObjectName("muted")
        v = QLabel(value)
        if value_color:
            v.setStyleSheet(f"color:{value_color}; font-weight:600;")
        grid.addWidget(k, state["row"], 0, Qt.AlignTop)
        grid.addWidget(v, state["row"], 1, Qt.AlignTop)
        state["row"] += 1
        return v

    state["add_row"] = add_row
    return w, state


class Stepper(QWidget):
    """五步进度：分析 → 复制 → 校验 → 清理预览 → 清理生产库。"""

    STEPS = ["分析", "复制数据", "校验数据", "清理预览", "清理生产库"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 14, 12, 4)
        lay.setSpacing(0)
        self._circles: list[QLabel] = []
        self._bars: list[QWidget] = []
        self._titles: list[QLabel] = []
        self._subs: list[QLabel] = []
        for i, name in enumerate(self.STEPS):
            col = QVBoxLayout()
            col.setSpacing(6)
            c = QLabel("")
            c.setFixedSize(30, 30)
            c.setAlignment(Qt.AlignCenter)
            col.addWidget(c, 0, Qt.AlignHCenter)
            t = QLabel(name)
            t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet("font-weight:600;")
            col.addWidget(t)
            s = QLabel("")
            s.setAlignment(Qt.AlignCenter)
            s.setObjectName("muted")
            s.setWordWrap(True)
            col.addWidget(s)
            step = QWidget()
            step.setLayout(col)
            lay.addWidget(step)
            self._circles.append(c)
            self._titles.append(t)
            self._subs.append(s)
            if i < len(self.STEPS) - 1:
                wrap = QWidget()
                wl = QVBoxLayout(wrap)
                wl.setContentsMargins(-6, 14, -6, 0)
                bar = QWidget()
                bar.setFixedHeight(3)
                wl.addWidget(bar)
                lay.addWidget(wrap, 1)
                self._bars.append(bar)

    def set_state(self, states: list[tuple[str, str]]) -> None:
        """states: 每步 (status, sub_text)；status ∈ done/active/pending/fail。"""
        for i, (st, sub) in enumerate(states):
            c = self._circles[i]
            if st == "done":
                c.setText("✓")
                c.setStyleSheet(
                    f"background:{GREEN}; color:white; border-radius:15px; font-weight:700;")
            elif st == "active":
                c.setText("●")
                c.setStyleSheet(
                    f"background:{BLUE}; color:white; border-radius:15px; font-size:11px;")
            elif st == "fail":
                c.setText("✕")
                c.setStyleSheet("background:#dc2626; color:white; border-radius:15px;")
            else:
                c.setText(str(i + 1))
                c.setStyleSheet(
                    f"background:#e5e9f0; color:#9aa4b2; border-radius:15px; font-weight:600;")
            self._subs[i].setText(sub)
            if i < len(self._bars):
                self._bars[i].setStyleSheet(
                    f"background:{GREEN if st == 'done' else '#e5e9f0'}; border-radius:2px;")
