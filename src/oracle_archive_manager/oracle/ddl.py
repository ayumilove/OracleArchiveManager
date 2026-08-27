"""目标表 DDL 生成与创建，见 05 §11 / ADR-009。仅归档库执行，绝不碰生产库。"""
from __future__ import annotations

from .metadata import ColumnMeta, _fetchone


def column_ddl(c: ColumnMeta) -> str:
    """单列 DDL 片段：VARCHAR2 用 CHAR 语义，NUMBER 带精度。"""
    t = c.data_type
    if t in ("VARCHAR2", "CHAR", "NVARCHAR2", "NCHAR"):
        return f'"{c.name}" {t}({max(c.char_length, 1)} CHAR)'
    if t == "NUMBER":
        if c.data_precision is not None:
            return f'"{c.name}" NUMBER({c.data_precision},{c.data_scale or 0})'
        return f'"{c.name}" NUMBER'
    if t == "FLOAT":
        return f'"{c.name}" FLOAT({c.data_precision or 126})'
    if t == "RAW":
        return f'"{c.name}" RAW({c.data_length})'
    # DATE / TIMESTAMP(x) / CLOB / BLOB 等原样保留
    return f'"{c.name}" {t}'


def create_table_sql(
    schema: str, table: str, columns: list[ColumnMeta],
    primary_key: list[str], unique_keys: dict[str, list[str]],
) -> str:
    """仅表结构 + 主键/唯一键，不创建普通索引与注释（05 §11）。"""
    parts = [column_ddl(c) for c in columns]
    if primary_key:
        parts.append(f"PRIMARY KEY ({', '.join(f'\"{k}\"' for k in primary_key)})")
    for cols in unique_keys.values():
        parts.append(f"UNIQUE ({', '.join(f'\"{k}\"' for k in cols)})")
    body = ",\n    ".join(parts)
    return f'CREATE TABLE "{schema}"."{table}" (\n    {body}\n)'


def table_exists(conn, schema: str, table: str) -> bool:
    row = _fetchone(
        conn,
        "SELECT 1 FROM all_tables WHERE owner = :s AND table_name = :t",
        {"s": schema.upper(), "t": table.upper()},
    )
    return row is not None


def ensure_target_table(
    conn, schema: str, table: str, columns: list[ColumnMeta],
    primary_key: list[str], unique_keys: dict[str, list[str]],
) -> bool:
    """不存在则创建；返回是否新建。调用方负责 commit。"""
    if table_exists(conn, schema, table):
        return False
    sql = create_table_sql(schema, table, columns, primary_key, unique_keys)
    with conn.cursor() as cur:
        cur.execute(sql)
    return True
