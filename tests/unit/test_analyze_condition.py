from datetime import date

from oracle_archive_manager.domain.task import ArchiveTask
from oracle_archive_manager.services.analyze_service import build_condition


def _task(**kw) -> ArchiveTask:
    base = dict(
        task_name="T",
        source_connection_id=1,
        source_schema="S",
        source_table="T1",
        target_connection_id=1,
        target_schema="A",
        target_table="T1",
        archive_column="CREATION_DATE",
        keep_months=24,
    )
    base.update(kw)
    return ArchiveTask(**base)


def test_date_only():
    cond, params = build_condition(_task(), date(2024, 8, 1))
    assert cond == "CREATION_DATE < :cutoff"
    assert params == {"cutoff": date(2024, 8, 1)}


def test_date_plus_where():
    cond, params = build_condition(_task(extra_where="STATUS = 9"), date(2024, 8, 1))
    assert cond == "CREATION_DATE < :cutoff AND (STATUS = 9)"
    assert "cutoff" in params


def test_where_only_no_date_column():
    cond, params = build_condition(_task(archive_column=None, extra_where="STATUS = 9"), None)
    assert cond == "(STATUS = 9)"
    assert params == {}


def test_full_table():
    cond, params = build_condition(_task(archive_column=None), None)
    assert cond is None
    assert params == {}
