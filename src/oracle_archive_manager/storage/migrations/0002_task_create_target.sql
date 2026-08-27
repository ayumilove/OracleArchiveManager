-- 0002：任务增加“如果不存在则创建目标表”开关，见 05 §11 / ADR-009
ALTER TABLE archive_task ADD COLUMN create_target_if_missing INTEGER NOT NULL DEFAULT 0;
