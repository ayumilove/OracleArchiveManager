# 总体架构设计

## 1. 架构

```text
┌─────────────────────────────────────┐
│       Oracle Archive Manager        │
│           PySide6 GUI               │
├─────────────────────────────────────┤
│ Controller / Application Service    │
├──────────────┬──────────────┬───────┤
│ Analyze      │ Archive      │ Purge │
│ Service      │ Service      │Service│
├──────────────┴──────────────┴───────┤
│ Verify / Recovery / Audit Service   │
├─────────────────────────────────────┤
│ Oracle Repository  │ Control Repo   │
│ python-oracledb    │ SQLite         │
└─────────┬──────────┴───────┬────────┘
          │                  │
          ▼                  ▼
 Oracle Production      Oracle Archive
```

## 2. 设计原则

### 2.1 GUI 与核心逻辑分离

GUI 只能调用 Application Service，禁止在按钮事件中直接编写 SQL。

### 2.2 Oracle 层统一封装

OracleRepository 提供：

- connect
- inspect_table
- fetch_batch
- insert_batch
- verify_batch
- delete_batch
- count
- metadata
- stats

### 2.3 控制面与数据面分离

SQLite 仅记录：

- 连接；
- 任务；
- Run；
- Batch；
- Log。

Oracle 只保存业务数据。

### 2.4 每个 Run 冻结配置快照

任务配置后续被修改，不得影响已经运行中的 Run。

Run 创建时保存：

- cutoff；
- source/target；
- archive condition；
- key columns；
- batch size；
- verify mode。

## 3. 线程模型

```text
Main GUI Thread
     │
     ├── ArchiveWorker
     ├── AnalyzeWorker
     ├── VerifyWorker
     └── PurgeWorker
```

通过 Qt Signal 更新：

- progress；
- current batch；
- counters；
- logs；
- status。

禁止在后台线程直接修改 Widget。

## 4. 状态模型

任务状态：

- ENABLED
- DISABLED

Run 状态：

- CREATED
- ANALYZED
- RUNNING
- PAUSING
- PAUSED
- COPY_COMPLETED
- VERIFIED
- PURGING
- COMPLETED
- FAILED
- CANCELED

Batch 状态：

- CREATED
- COPYING
- COPIED
- VERIFYING
- VERIFIED
- PURGING
- COMPLETED
- FAILED

## 5. 可扩展性

V2 可增加：

- FastAPI Server；
- Web UI；
- Data Pump；
- DB Link Transfer Engine；
- Oracle Partition Archive；
- 多任务调度；
- 邮件/企业微信通知。
