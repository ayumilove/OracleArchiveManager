# Python 项目结构

```text
oracle-archive-manager/
├── pyproject.toml
├── README.md
├── src/
│   └── oracle_archive_manager/
│       ├── main.py
│       │
│       ├── app/
│       │   ├── controller.py
│       │   └── state_machine.py
│       │
│       ├── domain/
│       │   ├── connection.py
│       │   ├── task.py
│       │   ├── run.py
│       │   └── batch.py
│       │
│       ├── services/
│       │   ├── analyze_service.py
│       │   ├── archive_service.py
│       │   ├── verify_service.py
│       │   ├── purge_service.py
│       │   └── recovery_service.py
│       │
│       ├── repositories/
│       │   ├── oracle_repository.py
│       │   ├── control_repository.py
│       │   └── credential_repository.py
│       │
│       ├── oracle/
│       │   ├── connection.py
│       │   ├── metadata.py
│       │   ├── sql_builder.py
│       │   └── datatype.py
│       │
│       ├── workers/
│       │   ├── analyze_worker.py
│       │   ├── archive_worker.py
│       │   ├── verify_worker.py
│       │   └── purge_worker.py
│       │
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── pages/
│       │   ├── dialogs/
│       │   └── widgets/
│       │
│       ├── storage/
│       │   ├── sqlite.py
│       │   └── migrations/
│       │
│       ├── security/
│       │   ├── credential.py
│       │   └── license.py
│       │
│       └── utils/
│           ├── logging.py
│           ├── ids.py
│           └── time.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── recovery/
│
├── scripts/
└── docs/
```

## 核心职责

### `sql_builder.py`

只负责构造 SQL，不负责执行。

### `oracle_repository.py`

执行 Oracle 操作。

### `archive_service.py`

编排：

```text
select → insert → commit → verify
```

### `purge_service.py`

只接受 VERIFIED Batch。

### `recovery_service.py`

根据 SQLite 状态 + Oracle 实际状态决定恢复动作。

### `workers/`

只解决 GUI 多线程，不包含业务规则。
