"""Oracle 元数据获取与结构比对，见 05 §6/§7。只读，不修改任何对象。

注意：oracledb 的 Connection.execute()/fetchone() 便捷方法仅 Thin 模式可用，
Thick 模式（Oracle 11g 必需）下必须显式使用 cursor。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnMeta:
    name: str
    data_type: str
    data_length: int
    data_precision: int | None
    data_scale: int | None
    char_length: int
    nullable: bool


def _up(s: str) -> str:
    return s.upper()


def _fetchall(conn, sql: str, params: dict | None = None):
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        return cur.fetchall()


def _fetchone(conn, sql: str, params: dict | None = None):
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        return cur.fetchone()


def list_schemas(conn) -> list[str]:
    rows = _fetchall(conn, "SELECT DISTINCT owner FROM all_tables ORDER BY owner")
    return [r[0] for r in rows]


def list_tables(conn, schema: str) -> list[str]:
    rows = _fetchall(
        conn,
        "SELECT table_name FROM all_tables WHERE owner = :s ORDER BY table_name",
        {"s": _up(schema)},
    )
    return [r[0] for r in rows]


def get_columns(conn, schema: str, table: str) -> list[ColumnMeta]:
    rows = _fetchall(
        conn,
        """SELECT column_name, data_type, data_length, data_precision,
                  data_scale, char_length, nullable
           FROM all_tab_columns
           WHERE owner = :s AND table_name = :t
           ORDER BY column_id""",
        {"s": _up(schema), "t": _up(table)},
    )
    return [
        ColumnMeta(r[0], r[1], r[2], r[3], r[4], r[5], r[6] == "Y") for r in rows
    ]


def get_primary_key(conn, schema: str, table: str) -> list[str]:
    rows = _fetchall(
        conn,
        """SELECT cols.column_name
           FROM all_constraints c
           JOIN all_cons_columns cols
             ON c.owner = cols.owner AND c.constraint_name = cols.constraint_name
           WHERE c.owner = :s AND c.table_name = :t AND c.constraint_type = 'P'
           ORDER BY cols.position""",
        {"s": _up(schema), "t": _up(table)},
    )
    return [r[0] for r in rows]


def get_unique_keys(conn, schema: str, table: str) -> dict[str, list[str]]:
    rows = _fetchall(
        conn,
        """SELECT c.constraint_name, cols.position, cols.column_name
           FROM all_constraints c
           JOIN all_cons_columns cols
             ON c.owner = cols.owner AND c.constraint_name = cols.constraint_name
           WHERE c.owner = :s AND c.table_name = :t AND c.constraint_type = 'U'
           ORDER BY c.constraint_name, cols.position""",
        {"s": _up(schema), "t": _up(table)},
    )
    keys: dict[str, list[str]] = {}
    for name, _pos, col in rows:
        keys.setdefault(name, []).append(col)
    return keys


def table_exists(conn, schema: str, table: str) -> bool:
    row = _fetchone(
        conn,
        "SELECT 1 FROM all_tables WHERE owner = :s AND table_name = :t",
        {"s": _up(schema), "t": _up(table)},
    )
    return row is not None


def get_table_bytes(conn, schema: str, table: str) -> int:
    row = _fetchone(
        conn,
        """SELECT NVL(SUM(bytes), 0) FROM all_segments
           WHERE owner = :s AND segment_name = :t
             AND segment_type IN ('TABLE', 'TABLE PARTITION', 'TABLE SUBPARTITION')""",
        {"s": _up(schema), "t": _up(table)},
    )
    return int(row[0])


def get_index_bytes(conn, schema: str, table: str) -> int:
    row = _fetchone(
        conn,
        """SELECT NVL(SUM(s.bytes), 0)
           FROM all_indexes i
           JOIN all_segments s ON i.owner = s.owner AND i.index_name = s.segment_name
           WHERE i.owner = :s AND i.table_name = :t""",
        {"s": _up(schema), "t": _up(table)},
    )
    return int(row[0])


def count_rows(
    conn, schema: str, table: str, where: str | None = None, params: dict | None = None
) -> int:
    sql = f'SELECT COUNT(*) FROM "{_up(schema)}"."{_up(table)}"'
    if where:
        sql += f" WHERE {where}"
    row = _fetchone(conn, sql, params or {})
    return int(row[0])


def compare_columns(source: list[ColumnMeta], target: list[ColumnMeta]) -> list[str]:
    """按 05 §7 比较属性，返回不一致描述列表（空 = 一致）。

    字符类型以 CHAR_LENGTH（字符容量）为准：DATA_LENGTH 是物理字节数，
    随字符集与 BYTE/CHAR 语义变化，跨库比较必然误报。
    可空性：源非空→目标可空对复制无风险（放宽）；
    源可空→目标非空插入 NULL 必失败（拒绝）。
    """
    char_types = {"VARCHAR2", "CHAR", "NVARCHAR2", "NCHAR"}
    msgs: list[str] = []
    tgt = {c.name: c for c in target}
    src_names = {c.name for c in source}
    for s in source:
        t = tgt.get(s.name)
        if t is None:
            msgs.append(f"目标缺少列 {s.name}")
            continue
        for attr in (
            "data_type", "data_length", "data_precision",
            "data_scale", "char_length", "nullable",
        ):
            if attr == "data_length" and s.data_type in char_types:
                continue
            sv, tv = getattr(s, attr), getattr(t, attr)
            if sv == tv:
                continue
            if attr == "nullable" and not s.nullable and t.nullable:
                continue  # 源更严格，复制到更宽松的目标无风险（05 §7）
            msgs.append(f"列 {s.name} {attr} 源={sv} 目标={tv}")
    for name in (t.name for t in target if t.name not in src_names):
        msgs.append(f"源缺少列 {name}（目标多出）")
    return msgs
