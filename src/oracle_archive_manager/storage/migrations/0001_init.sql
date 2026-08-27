-- 0001_init.sql：控制库初始 schema，见 03_DATA_MODEL.md

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

CREATE TABLE archive_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name TEXT NOT NULL UNIQUE,

    source_connection_id INTEGER NOT NULL,
    source_schema TEXT NOT NULL,
    source_table TEXT NOT NULL,

    target_connection_id INTEGER NOT NULL,
    target_schema TEXT NOT NULL,
    target_table TEXT NOT NULL,

    archive_column TEXT NOT NULL,
    keep_months INTEGER NOT NULL,

    extra_where TEXT,
    key_columns TEXT NOT NULL,          -- JSON array

    batch_size INTEGER NOT NULL DEFAULT 5000,
    max_rows_per_run INTEGER,

    verify_mode TEXT NOT NULL DEFAULT 'PK',
    purge_mode TEXT NOT NULL DEFAULT 'MANUAL',

    enabled INTEGER NOT NULL DEFAULT 1,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

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

CREATE TABLE archive_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    batch_id TEXT,
    operator TEXT,                      -- 操作人（审计，见 07 §6）
    log_time TEXT NOT NULL,
    level TEXT NOT NULL,
    stage TEXT,
    message TEXT NOT NULL,
    detail TEXT
);

-- 索引设计，见 03 §6
CREATE INDEX idx_run_task     ON archive_run (task_id);
CREATE INDEX idx_run_status   ON archive_run (status);
CREATE INDEX idx_batch_status ON archive_batch (status);
CREATE INDEX idx_log_run      ON archive_log (run_id);
CREATE INDEX idx_log_batch    ON archive_log (batch_id);
CREATE INDEX idx_log_time     ON archive_log (log_time);
