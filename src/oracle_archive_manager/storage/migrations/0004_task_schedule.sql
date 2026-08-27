-- Migration 0004: 任务级每日定时调度（P2 调度任务）
ALTER TABLE archive_task ADD COLUMN schedule_enabled INTEGER NOT NULL DEFAULT 0;
ALTER TABLE archive_task ADD COLUMN schedule_time TEXT NOT NULL DEFAULT '02:00';
