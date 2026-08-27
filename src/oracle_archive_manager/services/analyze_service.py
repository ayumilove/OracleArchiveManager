"""Analyze / Dry Run 编排，见 04 §1 与 08 Phase 1。只读，不具备 DELETE 能力。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..domain.task import ArchiveTask
from ..oracle import metadata as md
from ..utils.time import compute_cutoff

# 仅用于 Dry Run 预计耗时的粗略估算（行/秒）
ASSUMED_ROWS_PER_SEC = 3000


@dataclass
class AnalyzeReport:
    source_rows: int = 0
    eligible_rows: int = 0
    cutoff: str = ""
    archive_condition: str = ""
    source_bytes: int = 0
    index_bytes: int = 0
    target_exists: bool = False
    schema_match: bool = False
    mismatches: list[str] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    unique_keys: dict[str, list[str]] = field(default_factory=dict)
    has_unique_key: bool = False
    estimated_batches: int = 0
    estimated_seconds: int = 0
    risks: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """结构一致且目标表存在才允许进入 Copy。"""
        return self.schema_match and self.target_exists


def build_condition(task: ArchiveTask, cutoff: date | None) -> tuple[str | None, dict]:
    """归档条件三种模式（04 §6）：日期字段 / 仅附加 WHERE / 全表。

    返回 (None, {}) 表示全表归档（无 WHERE）。
    """
    parts: list[str] = []
    params: dict = {}
    if task.archive_column:
        parts.append(f"{task.archive_column} < :cutoff")
        params["cutoff"] = cutoff
    if task.extra_where:
        parts.append(f"({task.extra_where})")
    if not parts:
        return None, {}
    return " AND ".join(parts), params


def _describe(exc: Exception, step: str, schema: str, table: str) -> str:
    """带步骤定位的错误描述；ORA-00942 追加权限提示。"""
    msg = f"[{step} {schema}.{table}] {exc}"
    if "ORA-00942" in str(exc):
        msg += "（对象不存在，或连接用户对其无 SELECT 权限）"
    return msg


def _count(conn, task: ArchiveTask, step: str, cond: str | None, params: dict) -> int:
    try:
        return md.count_rows(conn, task.source_schema, task.source_table, cond, params)
    except Exception as exc:
        raise RuntimeError(
            _describe(exc, step, task.source_schema, task.source_table)
        ) from exc


def analyze(task: ArchiveTask, source_conn, target_conn) -> AnalyzeReport:
    rep = AnalyzeReport()

    try:
        src_cols = md.get_columns(source_conn, task.source_schema, task.source_table)
    except Exception as exc:
        raise RuntimeError(
            _describe(exc, "获取源表列", task.source_schema, task.source_table)
        ) from exc
    if not src_cols:
        raise ValueError(f"源表不存在或无列：{task.source_schema}.{task.source_table}")

    rep.primary_key = md.get_primary_key(source_conn, task.source_schema, task.source_table)
    rep.unique_keys = md.get_unique_keys(source_conn, task.source_schema, task.source_table)
    rep.has_unique_key = bool(rep.primary_key or rep.unique_keys)

    # 归档边界在分析时计算；Run 创建时冻结（04 §6）；无日期字段则不涉及 cutoff
    cutoff: date | None = None
    if task.archive_column:
        cutoff = compute_cutoff(date.today(), task.keep_months)
        rep.cutoff = cutoff.isoformat()
    else:
        rep.cutoff = "N/A（无日期字段）"
    cond, params = build_condition(task, cutoff)
    rep.archive_condition = cond or "（全表归档，无 WHERE）"

    rep.source_rows = _count(source_conn, task, "统计源表行数", None, None)
    rep.eligible_rows = _count(source_conn, task, "统计可归档行数", cond, params)

    try:
        rep.source_bytes = md.get_table_bytes(source_conn, task.source_schema, task.source_table)
        rep.index_bytes = md.get_index_bytes(source_conn, task.source_schema, task.source_table)
    except Exception:
        # 受限账号可能无 all_segments/all_indexes 权限，尺寸统计软失败
        rep.risks.append("无法读取段/索引尺寸统计（all_segments/all_indexes 无权限），已跳过")

    rep.target_exists = md.table_exists(target_conn, task.target_schema, task.target_table)
    if rep.target_exists:
        tgt_cols = md.get_columns(target_conn, task.target_schema, task.target_table)
        rep.mismatches = md.compare_columns(src_cols, tgt_cols)
    else:
        rep.mismatches = ["目标表不存在"]
    rep.schema_match = not rep.mismatches

    rep.estimated_batches = -(-rep.eligible_rows // max(task.batch_size, 1))
    rep.estimated_seconds = int(rep.eligible_rows / ASSUMED_ROWS_PER_SEC)

    if not rep.has_unique_key:
        rep.risks.append("无主键/唯一键：V1 禁止清理，仅允许只复制（不删除源数据）（05 §5）")
    if not task.archive_column:
        if task.extra_where:
            rep.risks.append("无日期字段：仅按附加 WHERE 条件归档，不涉及 cutoff")
        else:
            rep.risks.append("全表归档：将复制源表全部数据；Purge 会清空源表，请人工复核")
    if not rep.target_exists:
        rep.risks.append("目标表不存在：需先创建（或启用“如果不存在则创建”，05 §11）")
    if not rep.schema_match and rep.target_exists:
        rep.risks.append("源/目标结构不一致：禁止执行（01 验收标准）")
    return rep
