"""连接管理页：卡片式 CRUD + 后台连接测试，见 06_GUI_DESIGN.md §4。"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...app.controller import AppController
from ...domain.connection import ArchiveConnection, ConnectionRole
from ...oracle import connection as oracle_conn
from ..icons import icon
from ..widgets import card

ROLE_COLOR = {"SOURCE": "#16a34a", "TARGET": "#2563eb", "BOTH": "#7c3aed"}
ROLE_TEXT = {"SOURCE": "生产库", "TARGET": "归档库", "BOTH": "双角色"}


class _TestWorker(QThread):
    """后台执行连接测试，避免阻塞 UI。"""

    finished = Signal(object, object)

    def __init__(self, params: dict, parent=None) -> None:
        super().__init__(parent)
        self.params = params

    def run(self) -> None:
        try:
            self.finished.emit(oracle_conn.test_connection(**self.params), None)
        except Exception as exc:  # 连接类错误统一在 UI 展示
            self.finished.emit(None, str(exc))


class ConnectionPage(QWidget):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self._worker: _TestWorker | None = None
        self._editing_id: int | None = None
        self._sig: tuple = ()

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ---- 左：连接列表卡片 ----
        left_frame, left_body, btn_new = card("数据库连接", "新建", "plus")
        btn_new.clicked.connect(self._on_new)
        self.list = QListWidget()
        self.list.setObjectName("connlist")
        self.list.currentRowChanged.connect(self._on_select)
        left_body.addWidget(self.list, 1)
        left_frame.setFixedWidth(360)
        root.addWidget(left_frame)

        # ---- 右：连接配置卡片 ----
        right_frame, right_body, _ = card("连接配置")

        grid = QGridLayout()
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(12)

        self.ed_name = QLineEdit()
        self.cb_role = QComboBox()
        for r in ConnectionRole:
            self.cb_role.addItem(ROLE_TEXT[r.value], r.value)
        self.ed_host = QLineEdit()
        self.ed_host.setPlaceholderText("主机名或 IP")
        self.sp_port = QSpinBox()
        self.sp_port.setRange(1, 65535)
        self.sp_port.setValue(1521)
        self.ed_service = QLineEdit()
        self.ed_service.setPlaceholderText("如：orcl")
        self.ed_user = QLineEdit()
        self.ed_password = QLineEdit()
        self.ed_password.setEchoMode(QLineEdit.Password)
        self.ed_password.setPlaceholderText("留空 = 保持原密码")

        fields = [
            ("名称", self.ed_name), ("角色", self.cb_role),
            ("主机", self.ed_host), ("端口", self.sp_port),
            ("服务名", self.ed_service), ("用户名", self.ed_user),
            ("密码", self.ed_password),
        ]
        for i, (label, w) in enumerate(fields):
            row, col = divmod(i, 2)
            k = QLabel(label)
            k.setObjectName("muted")
            grid.addWidget(k, row, col * 3, Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(w, row, col * 3 + 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(4, 1)
        right_body.addLayout(grid)

        # 操作按钮行：测试 / 保存 / 删除 + 结果提示
        foot = QHBoxLayout()
        foot.setSpacing(10)
        self.btn_test = QPushButton("测试连接")
        self.btn_test.setIcon(icon("analyze"))
        self.btn_save = QPushButton("保存")
        self.btn_save.setObjectName("primary")
        self.btn_save.setIcon(icon("save", "#ffffff"))
        self.btn_delete = QPushButton("删除")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.setIcon(icon("trash-red"))
        self.lbl_result = QLabel("")
        self.lbl_result.setWordWrap(True)
        foot.addWidget(self.btn_test)
        foot.addWidget(self.btn_save)
        foot.addWidget(self.btn_delete)
        foot.addSpacing(16)
        foot.addWidget(self.lbl_result, 1)
        right_body.addLayout(foot)
        right_body.addStretch(1)
        root.addWidget(right_frame, 1)

        self.btn_test.clicked.connect(self._on_test)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_delete.clicked.connect(self._on_delete)

        self.refresh()

    # ---- 视图 ----
    def refresh(self) -> None:
        conns = self.controller.list_connections()
        sig = tuple((c.id, c.name, c.role.value, c.host, c.port, c.service_name)
                    for c in conns)
        if sig == self._sig:
            return
        self._sig = sig
        self.list.blockSignals(True)
        self.list.clear()
        for c in conns:
            color = ROLE_COLOR.get(c.role.value, "#2563eb")
            item = QListWidgetItem()
            w = QFrame()
            w.setObjectName("listitem")
            w.setProperty("selected", c.id == self._editing_id)
            w.setMinimumHeight(64)
            w.setStyleSheet(f"border-left:3px solid {color};")
            lay = QVBoxLayout(w)
            lay.setContentsMargins(10, 6, 10, 6)
            top = QHBoxLayout()
            name = QLabel(f"{c.name}（{ROLE_TEXT.get(c.role.value, c.role.value)}）")
            name.setStyleSheet(f"color:{color}; font-weight:600;")
            top.addWidget(name)
            top.addStretch(1)
            lay.addLayout(top)
            dsn = QLabel(f"{c.host}:{c.port}/{c.service_name}")
            dsn.setObjectName("muted")
            lay.addWidget(dsn)
            lay.addWidget(QLabel(c.username))
            item.setData(Qt.UserRole, c.id)
            item.setSizeHint(QSize(0, 72))
            self.list.addItem(item)
            self.list.setItemWidget(item, w)
        # 保持选中
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.UserRole) == self._editing_id:
                self.list.setCurrentRow(i)
                break
        self.list.blockSignals(False)

    def _on_select(self, row: int) -> None:
        item = self.list.item(row)
        if item is None:
            return
        c = self.controller.connections.get(item.data(Qt.UserRole))
        if c is None:
            return
        self._editing_id = c.id
        self._sig = ()  # 重建列表以刷新选中高亮
        self.ed_name.setText(c.name)
        self.cb_role.setCurrentIndex(self.cb_role.findData(c.role.value))
        self.ed_host.setText(c.host)
        self.sp_port.setValue(c.port)
        self.ed_service.setText(c.service_name)
        self.ed_user.setText(c.username)
        self.ed_password.clear()
        self.lbl_result.setText("")
        self.refresh()

    def _on_new(self) -> None:
        self._editing_id = None
        self._sig = ()
        self.list.clearSelection()
        for w in (self.ed_name, self.ed_host, self.ed_service, self.ed_user, self.ed_password):
            w.clear()
        self.sp_port.setValue(1521)
        self.cb_role.setCurrentIndex(0)
        self.lbl_result.setText("")
        self.refresh()

    def _collect(self) -> ArchiveConnection:
        return ArchiveConnection(
            id=self._editing_id,
            name=self.ed_name.text().strip(),
            role=ConnectionRole(self.cb_role.currentData()),
            host=self.ed_host.text().strip(),
            port=self.sp_port.value(),
            service_name=self.ed_service.text().strip(),
            username=self.ed_user.text().strip(),
        )

    # ---- 动作 ----
    def _on_save(self) -> None:
        c = self._collect()
        password = self.ed_password.text() or None
        try:
            saved = self.controller.save_connection(c, password)
        except Exception as exc:
            QMessageBox.warning(self, "保存失败", str(exc))
            return
        self._editing_id = saved.id if saved.id else self._editing_id
        self.ed_password.clear()
        self._sig = ()
        self.refresh()
        self.lbl_result.setStyleSheet("color:#16a34a;")
        self.lbl_result.setText("已保存")

    def _on_delete(self) -> None:
        if self._editing_id is None:
            return
        if QMessageBox.question(
            self, "删除连接", "删除该连接及其本地凭据？"
        ) != QMessageBox.Yes:
            return
        self.controller.delete_connection(self._editing_id)
        self._editing_id = None
        self._sig = ()
        self.refresh()

    def _on_test(self) -> None:
        c = self._collect()
        password = self.ed_password.text()
        if not password and c.id is not None:
            password = self.controller.get_password(c) or ""
        self.lbl_result.setStyleSheet("color:#8a94a0;")
        self.lbl_result.setText("测试中…")
        self._worker = _TestWorker(
            {
                "host": c.host,
                "port": c.port,
                "service_name": c.service_name,
                "username": c.username,
                "password": password,
                "thick": bool(self.controller.config.get("thick_mode")),
            }
        )
        self._worker.finished.connect(self._on_test_done)
        self._worker.start()

    def _on_test_done(self, version, error) -> None:
        if error is None:
            self.lbl_result.setStyleSheet("color:#16a34a; font-weight:600;")
            self.lbl_result.setText(f"● 连接成功，Oracle {version}")
        else:
            self.lbl_result.setStyleSheet("color:#dc2626;")
            self.lbl_result.setText(f"连接失败：{error}")
