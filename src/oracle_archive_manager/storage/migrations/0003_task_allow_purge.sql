-- Migration 0003: 任务级 Purge 开关（04 §4 扩展，默认允许；置 0 禁止删除源数据）
ALTER TABLE archive_task ADD COLUMN allow_purge INTEGER NOT NULL DEFAULT 1;
