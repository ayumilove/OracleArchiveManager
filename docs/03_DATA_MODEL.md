# SQLite 控制库数据模型

## 1. ARCHIVE_CONNECTION

```sql
CREATE TABLE archive_connection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,                 -- SOURCE / TARGET / BOTH
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 1521,
    service_name TEXT NOT NULL,
    username TEXT NOT NULL,
    credential_ref TEXT,
    oracle_version TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

## 2. ARCHIVE_TASK

```sql
CREATE TABLE archive_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL UNIQUE,

    source_connection_id INTEGER NOT NULL,
    source_schema TEXT NOT NULL,
    source_table TEXT NOT NULL,

    target_connection_id INTEGER NOT NULL,
    target_schema TEXT NOT NULL,
    target_table TEXT NOT NULL,

    archive_column TEXT NOT NULL,  -- 空串 = 无日期字段：按 extra_where 或全表归档（04 §6）
    keep_months INTEGER NOT NULL,

    extra_where TEXT,
    key_columns TEXT NOT NULL,          -- JSON array

    batch_size INTEGER NOT NULL DEFAULT 5000,
    max_rows_per_run INTEGER,

    verify_mode TEXT NOT NULL DEFAULT 'PK',
    purge_mode TEXT NOT NULL DEFAULT 'MANUAL',
    create_target_if_missing INTEGER NOT NULL DEFAULT 0,  -- 05 §11 / ADR-009

    enabled INTEGER NOT NULL DEFAULT 1,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

## 3. ARCHIVE_RUN

```sql
CREATE TABLE archive_run (
    run_id TEXT PRIMARY KEY,
    task_id INTEGER NOT NULL,

    task_snapshot TEXT NOT NULL,        -- JSON
    cutoff_value TEXT NOT NULL,
    archive_condition TEXT NOT NULL,

    expected_rows INTEGER DEFAULT 0,
    transferred_rows INTEGER DEFAULT 0,
    verified_rows INTEGER DEFAULT 0,
    deleted_rows INTEGER DEFAULT 0,

    total_batches INTEGER DEFAULT 0,
    success_batches INTEGER DEFAULT 0,
    failed_batches INTEGER DEFAULT 0,

    status TEXT NOT NULL,

    start_time TEXT,
    copy_end_time TEXT,
    verify_end_time TEXT,
    purge_start_time TEXT,
    end_time TEXT,

    error_message TEXT
);
```

## 4. ARCHIVE_BATCH

```sql
CREATE TABLE archive_batch (
    batch_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    batch_no INTEGER NOT NULL,

    selection_snapshot TEXT,            -- JSON
    selected_rows INTEGER DEFAULT 0,
    transferred_rows INTEGER DEFAULT 0,
    verified_rows INTEGER DEFAULT 0,
    deleted_rows INTEGER DEFAULT 0,

    status TEXT NOT NULL,

    start_time TEXT,
    copy_end_time TEXT,
    verify_end_time TEXT,
    purge_end_time TEXT,
    end_time TEXT,

    error_message TEXT,

    UNIQUE(run_id, batch_no)
);
```

## 5. ARCHIVE_LOG

```sql
CREATE TABLE archive_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    batch_id TEXT,
    operator TEXT,                  -- 操作人（审计，见 07 §6）
    log_time TEXT NOT NULL,
    level TEXT NOT NULL,
    stage TEXT,
    message TEXT NOT NULL,
    detail TEXT
);
```

## 6. 索引设计

```sql
CREATE INDEX idx_run_task     ON archive_run (task_id);
CREATE INDEX idx_run_status   ON archive_run (status);

-- UNIQUE(run_id, batch_no) 约束已覆盖按 run_id 的查询前缀，仅补状态索引
CREATE INDEX idx_batch_status ON archive_batch (status);

CREATE INDEX idx_log_run      ON archive_log (run_id);
CREATE INDEX idx_log_batch    ON archive_log (batch_id);
CREATE INDEX idx_log_time     ON archive_log (log_time);
```

并发：控制库使用 WAL 模式（连接时设置），支持多 Worker 线程并发读写。

## 7. max_rows_per_run 行为

`archive_task.max_rows_per_run` 用于限制单次 Run 的最大归档行数：

- 非空时，Copy 阶段 `transferred_rows` 达到上限后停止创建新批次；
- 该 Run 正常进入 COPY_COMPLETED（部分完成），剩余数据留待下次 Run；
- 限制仅作用于 Copy，不影响已复制批次的 Verify 与 Purge；
- 为 NULL 时表示不限制。

## 8. 为什么不做 ARCHIVE_BATCH_DETAIL

V1 不长期保存每一行 PK。

理由：

- 控制库保持轻量；
- 减少 SQLite 数据膨胀；
- Batch selection 应设计成可重复、可确定。

如遇无法通过范围稳定恢复的表，V2 可增加 temporary batch detail。
