from oracle_archive_manager.oracle.metadata import ColumnMeta, compare_columns


def _col(name, **kw):
    base = dict(
        data_type="NUMBER", data_length=22, data_precision=10,
        data_scale=0, char_length=0, nullable=False,
    )
    base.update(kw)
    return ColumnMeta(name=name, **base)


def test_identical():
    assert compare_columns([_col("ID"), _col("A")], [_col("ID"), _col("A")]) == []


def test_missing_column():
    msgs = compare_columns([_col("ID"), _col("A")], [_col("ID")])
    assert any("目标缺少列 A" in m for m in msgs)


def test_type_mismatch():
    msgs = compare_columns(
        [_col("A", data_type="VARCHAR2", data_length=50, char_length=50)],
        [_col("A", data_type="VARCHAR2", data_length=100, char_length=100)],
    )
    assert any("char_length" in m for m in msgs)


def test_char_byte_semantics_not_false_positive():
    # 源 BYTE 语义 data_length=50，目标 CHAR 语义 data_length=100；字符容量同为 50 → 一致
    msgs = compare_columns(
        [_col("A", data_type="VARCHAR2", data_length=50, char_length=50)],
        [_col("A", data_type="VARCHAR2", data_length=100, char_length=50)],
    )
    assert msgs == []


def test_nullable_mismatch():
    msgs = compare_columns([_col("ID", nullable=True)], [_col("ID", nullable=False)])
    assert any("nullable" in m for m in msgs)


def test_target_extra_column():
    msgs = compare_columns([_col("ID")], [_col("ID"), _col("X")])
    assert any("源缺少列 X" in m for m in msgs)
