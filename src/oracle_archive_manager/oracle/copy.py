"""批次选择 / 复制 / 验证 SQL，见 04 §2/§3 与 05 §4/§5。

Thick 兼容：一律显式 cursor；11g 分页仅用 ROWNUM 截断单批，定位靠 Keyset。
CLOB/BLOB 在 Thick 模式默认返回 LOB locator，其生命周期绑定源会话，
跨连接作为 INSERT 绑定值会报 ORA-00942；故取批时一律内联读取为 str/bytes。
"""
from __future__ import annotations

import oracledb

from .metadata import _fetchall, _fetchone

#: LOB 类列（取批内联读取；含此类列的表建议小批次）
LOB_TYPES = ("CLOB", "NCLOB", "BLOB", "BFILE")


def _q(name: str) -> str:
    return f'"{name}"'


def keyset_gt(keys: list[str], last: list, prefix: str = "lk") -> tuple[str, dict]:
    """复合键展开的严格大于条件（05 §5），返回 (sql, params)。"""
    clauses, params = [], {}
    for i, k in enumerate(keys):
        eq = " AND ".join(f"{_q(keys[j])} = :{prefix}{j}" for j in range(i))
        gt = f"{_q(k)} > :{prefix}{i}"
        clauses.append(f"({eq} AND {gt})" if eq else f"({gt})")
        params[f"{prefix}{i}"] = last[i]
    return " OR ".join(clauses), params


def keyset_le(keys: list[str], last: list, prefix: str = "uk") -> tuple[str, dict]:
    """复合键展开的小于等于条件，用于验证区间 (prev, last]。"""
    clauses, params = [], {}
    for i, k in enumerate(keys):
        eq = " AND ".join(f"{_q(keys[j])} = :{prefix}{j}" for j in range(i))
        lt = f"{_q(k)} < :{prefix}{i}"
        clauses.append(f"({eq} AND {lt})" if eq else f"({lt})")
        params[f"{prefix}{i}"] = last[i]
    # 加上全等
    clauses.append(" AND ".join(f"{_q(k)} = :{prefix}{i}" for i, k in enumerate(keys)))
    return " OR ".join(clauses), params


def _range_cond(keys: list[str], prev: list | None, last: list,
                cond: str | None = None, params: dict | None = None) -> tuple[str, dict]:
    """验证区间 (prev, last] 的条件与参数；可叠加归档条件（源端排除交错行）。"""
    le_sql, ps = keyset_le(keys, last)
    parts = [f"({le_sql})"]
    if prev is not None:
        gt_sql, gt_params = keyset_gt(keys, prev)
        parts.append(f"({gt_sql})")
        ps.update(gt_params)
    if cond:
        parts.append(f"({cond})")
        ps.update(params or {})
    return " AND ".join(parts), ps


def build_select_sql(
    schema: str, table: str, columns: list[str],
    cond: str | None, keys: list[str], last: list | None,
) -> str:
    """05 §4 基础模式：内层 Keyset 定位 + 外层 ROWNUM 截断。"""
    where = []
    if cond:
        where.append(f"({cond})")
    if last is not None:
        gt_sql, _ = keyset_gt(keys, last)
        where.append(f"({gt_sql})")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    cols = ", ".join(f"t.{_q(c)}" for c in columns)
    order = ", ".join(f"t.{_q(k)}" for k in keys)
    return (
        f"SELECT * FROM (SELECT {cols} FROM {_q(schema)}.{_q(table)} t "
        f"{where_sql} ORDER BY {order}) WHERE ROWNUM <= :batch_size"
    )


def select_batch(conn, sql: str, params: dict, batch_size: int) -> list[tuple]:
    """05 §2：arraysize + fetchmany，禁止一次性 fetchall。

    LOB 内联读取：CLOB/NCLOB/BFILE→str，BLOB→bytes，避免 locator 跨会话使用。
    """
    def _handler(cursor, metadata):
        if metadata.type_code in (oracledb.DB_TYPE_CLOB, oracledb.DB_TYPE_NCLOB,
                                  oracledb.DB_TYPE_BFILE):
            return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)
        if metadata.type_code == oracledb.DB_TYPE_BLOB:
            return cursor.var(oracledb.DB_TYPE_LONG_RAW, arraysize=cursor.arraysize)
        return None

    with conn.cursor() as cur:
        cur.arraysize = batch_size
        cur.outputtypehandler = _handler
        cur.execute(sql, params)
        return cur.fetchmany(batch_size)


def _merge_sql(schema: str, table: str, columns: list[str], keys: list[str]) -> str:
    """幂等写入：按 key 判重，仅插入目标不存在的行（重跑补洞不报主键冲突）。"""
    sel = ", ".join(f":{i + 1} AS {_q(c)}" for i, c in enumerate(columns))
    on = " AND ".join(f"t.{_q(k)} = s.{_q(k)}" for k in keys)
    ins_cols = ", ".join(_q(c) for c in columns)
    ins_vals = ", ".join(f"s.{_q(c)}" for c in columns)
    return (f"MERGE INTO {_q(schema)}.{_q(table)} t "
            f"USING (SELECT {sel} FROM dual) s ON ({on}) "
            f"WHEN NOT MATCHED THEN INSERT ({ins_cols}) VALUES ({ins_vals})")


def insert_batch(conn, schema: str, table: str, columns: list[str], rows: list[tuple],
                 col_types: dict[str, str] | None = None,
                 keys: list[str] | None = None) -> int:
    """05 §3：executemany 批量写入，调用方负责 commit，返回实际写入行数。

    提供 keys 时用 MERGE 幂等写入（重跑自动跳过已存在行）；否则普通 INSERT。
    LOB 列用 setinputsizes 显式绑定为 DB_TYPE_CLOB/BLOB（临时 LOB）：
    内联读取后的 str/bytes 否则默认走 LONG 流式绑定，而 Oracle 要求 LONG
    绑定位于语句末位，否则报 ORA-24816。
    """
    if not rows:
        return 0
    if keys:
        sql = _merge_sql(schema, table, columns, keys)
    else:
        binds = ", ".join(f":{i + 1}" for i in range(len(columns)))
        sql = f"INSERT INTO {_q(schema)}.{_q(table)} ({', '.join(_q(c) for c in columns)}) VALUES ({binds})"
    with conn.cursor() as cur:
        if col_types:
            sizes = []
            for c in columns:
                t = col_types.get(c, "")
                if t in ("CLOB", "NCLOB"):
                    sizes.append(oracledb.DB_TYPE_CLOB)
                elif t == "BLOB":
                    sizes.append(oracledb.DB_TYPE_BLOB)
                else:
                    sizes.append(None)
            if any(s is not None for s in sizes):
                cur.setinputsizes(*sizes)
        cur.executemany(sql, rows)
        return cur.rowcount


def count_range(
    conn, schema: str, table: str, keys: list[str],
    prev: list | None, last: list,
    cond: str | None = None, cond_params: dict | None = None,
) -> int:
    """目标/源在区间 (prev, last] 的行数（COUNT 验证）。

    源端传入归档条件，排除区间内不满足条件的交错行（它们本就不该归档）。
    """
    where, params = _range_cond(keys, prev, last, cond, cond_params)
    row = _fetchone(
        conn,
        f"SELECT COUNT(*) FROM {_q(schema)}.{_q(table)} WHERE {where}",
        params,
    )
    return int(row[0])


def fetch_keys_range(
    conn, schema: str, table: str, keys: list[str],
    prev: list | None, last: list,
) -> set[tuple]:
    """区间内主键集合（PK 验证）。"""
    where, params = _range_cond(keys, prev, last)
    cols = ", ".join(_q(k) for k in keys)
    rows = _fetchall(
        conn,
        f"SELECT {cols} FROM {_q(schema)}.{_q(table)} WHERE {where}",
        params,
    )
    return {tuple(r) for r in rows}


def _hash_expr(columns: list[str], col_types: dict[str, str]) -> str:
    """行级哈希表达式：显式 TO_CHAR 格式，避免 NLS 差异。"""
    parts = []
    for c in columns:
        t = col_types.get(c, "")
        if t == "DATE" or t.startswith("TIMESTAMP"):
            parts.append(f"NVL(TO_CHAR({_q(c)},'YYYY-MM-DD HH24:MI:SS'),'∅')")
        elif t == "NUMBER":
            parts.append(f"NVL(TO_CHAR({_q(c)},'TM9'),'∅')")
        elif t in ("CLOB", "NCLOB", "BLOB"):
            parts.append(f"NVL(DBMS_LOB.SUBSTR({_q(c)}, 4000, 1),'∅')")
        else:
            parts.append(f"NVL(TO_CHAR({_q(c)}),'∅')")
    return "ORA_HASH(" + " || '¦' || ".join(parts) + ")"


def delete_range(
    conn, schema: str, table: str, keys: list[str],
    prev: list | None, last: list,
    cond: str | None = None, cond_params: dict | None = None,
) -> int:
    """04 §4 / 05 §9：按已验证批次 selection 区间删除源数据，调用方负责 commit。

    DELETE 以 key 区间定位，重跑幂等；必须叠加归档条件，
    避免误删区间内不满足条件的交错行（未被归档，绝不能删）。
    """
    where, params = _range_cond(keys, prev, last, cond, cond_params)
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {_q(schema)}.{_q(table)} WHERE {where}", params)
        return cur.rowcount


def hash_sum_range(
    conn, schema: str, table: str, columns: list[str],
    col_types: dict[str, str], keys: list[str],
    prev: list | None, last: list,
    cond: str | None = None, cond_params: dict | None = None,
) -> float:
    """区间内行哈希之和（HASH 验证）。"""
    where, params = _range_cond(keys, prev, last, cond, cond_params)
    row = _fetchone(
        conn,
        f"SELECT NVL(SUM({_hash_expr(columns, col_types)}), 0) "
        f"FROM {_q(schema)}.{_q(table)} WHERE {where}",
        params,
    )
    return float(row[0])
