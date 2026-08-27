"""Markdown 报告导出与 Purge 后维护建议（P1）。"""
from __future__ import annotations

from ..domain.run import ArchiveBatch, ArchiveRun
from ..domain.task import ArchiveTask
from ..utils.time import now_iso, to_local
from .analyze_service import AnalyzeReport


def _gb(n: int) -> str:
    return f"{n / 1024 ** 3:.2f} GB"


def maintenance_advice(task: ArchiveTask) -> list[str]:
    """Purge 后维护建议 SQL：统计信息刷新 + 表空间回收（05）。"""
    s, t = task.source_schema, task.source_table
    return [
        "-- 1) 刷新统计信息：Purge 后行数变化大，避免执行计划劣化",
        f"BEGIN DBMS_STATS.GATHER_TABLE_STATS(ownname => '{s}', tabname => '{t}', "
        "estimate_percent => DBMS_STATS.AUTO_SAMPLE_SIZE, cascade => TRUE); END;",
        "",
        "-- 2) 回收高水位（ASSM 表空间；SHRINK 在线但产生 redo，建议低峰执行）",
        f'ALTER TABLE "{s}"."{t}" ENABLE ROW MOVEMENT;',
        f'ALTER TABLE "{s}"."{t}" SHRINK SPACE CASCADE;',
        "",
        "-- 3) 非 ASSM 或需彻底整理时的替代方案（MOVE 会锁表并使索引失效）",
        f'ALTER TABLE "{s}"."{t}" MOVE;',
        '--    MOVE 后重建该表全部索引：ALTER INDEX "<IDX>" REBUILD;',
    ]


def analyze_report_md(task: ArchiveTask, rep: AnalyzeReport) -> str:
    """Analyze / Dry Run 结果导出为 Markdown。"""
    uk = "; ".join(f"{k}: {','.join(v)}" for k, v in rep.unique_keys.items())
    lines = [
        f"# Analyze Report — {task.source_schema}.{task.source_table}",
        "",
        f"生成时间：{to_local(now_iso())}",
        "",
        "## 任务配置",
        "",
        f"- 源：连接 {task.source_connection_id} / {task.source_schema}.{task.source_table}",
        f"- 目标：连接 {task.target_connection_id} / {task.target_schema}.{task.target_table}",
        f"- 归档日期字段：{task.archive_column or '（无，按附加 WHERE / 全表）'}",
        f"- 保留月份：{task.keep_months}　批次：{task.batch_size:,}　"
        f"校验：{task.verify_mode.value}　允许 Purge：{'是' if task.allow_purge else '否'}",
        "",
        "## 分析结果",
        "",
        "| 指标 | 值 |",
        "| --- | --- |",
        f"| 源表行数 | {rep.source_rows:,} |",
        f"| 可归档行数 | {rep.eligible_rows:,} |",
        f"| Cutoff | {rep.cutoff} |",
        f"| 归档条件 | {rep.archive_condition} |",
        f"| 表尺寸 | {_gb(rep.source_bytes)} |",
        f"| 索引尺寸 | {_gb(rep.index_bytes)} |",
        f"| 目标表存在 | {'是' if rep.target_exists else '否'} |",
        f"| 结构一致 | {'是' if rep.schema_match else '否'} |",
        f"| 主键 | {', '.join(rep.primary_key) or '（无）'} |",
        f"| 唯一键 | {uk or '（无）'} |",
        f"| 预计批次 | {rep.estimated_batches} |",
        f"| 预计耗时 | ~{rep.estimated_seconds // 60} 分钟 |",
    ]
    if rep.mismatches:
        lines += ["", "## 结构差异", ""] + [f"- {m}" for m in rep.mismatches]
    if rep.risks:
        lines += ["", "## 风险提醒", ""] + [f"- {r}" for r in rep.risks]
    lines += ["", "## Purge 后维护建议", "", "```sql"] + maintenance_advice(task) + ["```", ""]
    return "\n".join(lines)


def run_report_md(run: ArchiveRun, batches: list[ArchiveBatch],
                  logs: list[dict], task: ArchiveTask) -> str:
    """Run 全量报告：概览 + 批次明细 + 日志尾部 + 维护建议。"""
    lines = [
        f"# Run Report — {run.run_id}",
        "",
        f"生成时间：{to_local(now_iso())}",
        "",
        "## 概览",
        "",
        f"- 任务：{task.task_name}（{task.source_schema}.{task.source_table} → "
        f"{task.target_schema}.{task.target_table}）",
        f"- 状态：**{run.status.value}**",
        f"- Cutoff：{run.cutoff_value or 'N/A'}　归档条件：{run.archive_condition or '（全表）'}",
        f"- 开始：{to_local(run.start_time)}　结束：{to_local(run.end_time)}",
        f"- 预计 {run.expected_rows:,} 行 / 已复制 {run.transferred_rows:,} 行 / "
        f"已验证 {run.verified_rows:,} 行 / 已删除 {run.deleted_rows:,} 行",
        f"- 批次：成功 {run.success_batches} / 失败 {run.failed_batches} / 共 {run.total_batches}",
    ]
    if run.error_message:
        lines += ["", f"> 错误：{run.error_message}"]
    lines += ["", "## 批次明细", "",
              "| # | 状态 | 选取 | 复制 | 验证 | 删除 | 开始 | 结束 |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for b in batches:
        lines.append(
            f"| {b.batch_no} | {b.status.value} | {b.selected_rows:,} | "
            f"{b.transferred_rows:,} | {b.verified_rows:,} | {b.deleted_rows:,} | "
            f"{to_local(b.start_time)[11:19]} | {to_local(b.end_time)[11:19]} |")
    lines += ["", "## 日志（最新 50 条）", "", "```"]
    for l in logs[-50:]:
        lines.append(f"{to_local(l['log_time'])} {l['level']:5} [{l['stage']}] {l['message']}")
    lines += ["```", "", "## Purge 后维护建议", "", "```sql"]
    lines += maintenance_advice(task) + ["```", ""]
    return "\n".join(lines)
