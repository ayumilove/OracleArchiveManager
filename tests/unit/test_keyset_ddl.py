from oracle_archive_manager.oracle.copy import build_select_sql, keyset_gt, keyset_le
from oracle_archive_manager.oracle.ddl import column_ddl, create_table_sql
from oracle_archive_manager.oracle.metadata import ColumnMeta
from oracle_archive_manager.services.run_worker import is_retryable


def _col(name, dtype="NUMBER", **kw):
    base = dict(data_length=22, data_precision=10, data_scale=0, char_length=0, nullable=False)
    base.update(kw)
    return ColumnMeta(name=name, data_type=dtype, **base)


def test_keyset_gt_single():
    sql, params = keyset_gt(["ID"], [100])
    assert sql == '("ID" > :lk0)'
    assert params == {"lk0": 100}


def test_keyset_gt_composite_expansion():
    sql, params = keyset_gt(["A", "B"], [1, "x"])
    assert sql == '("A" > :lk0) OR ("A" = :lk0 AND "B" > :lk1)'
    assert params == {"lk0": 1, "lk1": "x"}


def test_keyset_le_includes_equality():
    sql, params = keyset_le(["A", "B"], [1, 2])
    assert '"A" = :uk0 AND "B" = :uk1' in sql
    assert params["uk1"] == 2


def test_select_sql_11g_pattern():
    sql = build_select_sql("S", "T", ["ID", "A"], "A < :cutoff", ["ID"], [5])
    assert "ROWNUM <= :batch_size" in sql
    assert "OFFSET" not in sql.upper()
    assert 'ORDER BY t."ID"' in sql
    assert '"ID" > :lk0' in sql


def test_select_sql_full_table_first_batch():
    sql = build_select_sql("S", "T", ["ID"], None, ["ID"], None)
    assert "WHERE ROWNUM" in sql
    assert ":cutoff" not in sql


def test_column_ddl_varchar_char_semantics():
    assert column_ddl(_col("N", "VARCHAR2", char_length=50)) == '"N" VARCHAR2(50 CHAR)'


def test_column_ddl_number_precision():
    assert column_ddl(_col("N", "NUMBER", data_precision=12, data_scale=2)) == '"N" NUMBER(12,2)'


def test_create_table_sql_pk_and_uk():
    sql = create_table_sql("A", "T", [_col("ID"), _col("C", "VARCHAR2", char_length=1)],
                           ["ID"], {"UK1": ["C"]})
    assert 'PRIMARY KEY ("ID")' in sql
    assert 'UNIQUE ("C")' in sql
    assert "CREATE INDEX" not in sql


def test_retryable_classification():
    assert is_retryable(Exception("ORA-03113: end-of-file on communication channel"))
    assert is_retryable(Exception("ORA-03114: not connected to ORACLE"))
    assert not is_retryable(Exception("ORA-00001: unique constraint violated"))
    assert not is_retryable(Exception("ORA-00942: table or view does not exist"))
