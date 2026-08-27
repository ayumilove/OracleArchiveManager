from datetime import date

from oracle_archive_manager.utils.time import compute_cutoff


def test_cutoff_month_start_alignment():
    # 与 04 §6 示例一致：2026-08-27、keep 24 → 2024-08-01
    assert compute_cutoff(date(2026, 8, 27), 24) == date(2024, 8, 1)


def test_cutoff_zero_months():
    assert compute_cutoff(date(2026, 8, 27), 0) == date(2026, 8, 1)


def test_cutoff_cross_year():
    assert compute_cutoff(date(2026, 2, 15), 3) == date(2025, 11, 1)
