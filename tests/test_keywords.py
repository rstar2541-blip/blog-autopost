from datetime import date
from pathlib import Path

import pytest

from blog_autopost import keywords as kw
from blog_autopost.config import load_config

ROOT = Path(__file__).resolve().parents[1]
CSVS = sorted((ROOT / "keywords").glob("0*.csv"))  # trends.csv 는 캘린더가 아님


def test_four_calendars_exist():
    assert [p.name for p in CSVS] == [
        "01_seedling_garden.csv",
        "02_landscaping.csv",
        "03_women_biz_public.csv",
        "04_bmw.csv",
    ]


@pytest.mark.parametrize("path", CSVS, ids=lambda p: p.stem)
def test_calendar_is_complete(path):
    rows = kw.load(path)
    assert len(rows) >= 100  # 처음 100개 + 직접 추가한 키워드
    assert len({r.id for r in rows}) == len(rows)
    assert len({r.keyword for r in rows}) == len(rows)
    assert {r.month for r in rows} == set(range(1, 13))
    for r in rows:
        assert 1 <= r.week <= 4
        assert 1 <= r.peak_month <= 12
        assert r.priority in {"A", "B", "C"}
        assert r.intent in {"정보", "문제해결", "비교", "구매", "비용", "경험"}
        assert r.status in kw.STATUSES
        assert r.title and r.keyword and r.category and r.monetize


def test_csv_has_bom_for_excel():
    for path in CSVS:
        assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_config_points_at_calendars():
    cfg = load_config(ROOT / "config.toml")
    assert set(cfg.topics) == {"seedling", "landscaping", "women_biz", "bmw"}
    for topic in cfg.topics.values():
        assert topic.csv.is_file()


def _row(i, month, week, status="todo", priority="B", peak=None):
    return kw.Keyword(id=f"T-{i:03d}", month=month, week=week, category="c", keyword=f"k{i}",
                      title=f"t{i}", intent="정보", peak_month=peak or month, priority=priority,
                      monetize="애드포스트", status=status)


def test_save_load_roundtrip(tmp_path):
    rows = [_row(1, 11, 1), _row(2, 12, 3, status="draft")]
    rows[0].memo = "작년에 냉해 입음, 사진 있음"
    path = tmp_path / "k.csv"
    kw.save(path, rows)
    assert kw.load(path) == rows


def test_week_of_month():
    assert kw.week_of_month(date(2026, 11, 1)) == 1
    assert kw.week_of_month(date(2026, 11, 8)) == 2
    assert kw.week_of_month(date(2026, 11, 21)) == 3
    assert kw.week_of_month(date(2026, 11, 30)) == 4


def test_due_includes_this_week_and_timely_leftovers():
    rows = [
        _row(1, 10, 4, peak=11),         # 지난달 글, 성수기는 이번 달 → 포함, 가장 먼저
        _row(2, 11, 1),                  # 이번 달 1주 → 포함
        _row(3, 11, 2),                  # 이번 달 2주 → 아직 아님 (오늘은 1주)
        _row(4, 11, 1, status="draft"),  # 이미 초안 → 제외
        _row(5, 9, 1),                   # 두 달 전 → 제외 (내년에 다시)
        _row(6, 12, 1),                  # 다음 달 → 제외
        _row(7, 10, 1, peak=10),         # 지난달 글인데 성수기도 지남 → 제외
    ]
    due = kw.due(rows, date(2026, 11, 4))
    assert [r.id for r in due] == ["T-001", "T-002"]


def test_upcoming_orders_overdue_then_current_then_next():
    rows = [_row(1, 12, 1), _row(2, 11, 3, priority="A"), _row(3, 11, 3, priority="C"),
            _row(4, 10, 2, peak=12), _row(5, 1, 1), _row(6, 10, 1)]
    up = kw.upcoming(rows, date(2026, 11, 4), lookahead_months=1)
    assert [r.id for r in up] == ["T-004", "T-002", "T-003", "T-001"]


def test_month_wraps_around_year_end():
    rows = [_row(1, 12, 4, peak=1), _row(2, 1, 1)]
    assert [r.id for r in kw.due(rows, date(2027, 1, 3))] == ["T-001", "T-002"]


def test_region_placeholder():
    row = _row(1, 1, 1)
    row.keyword, row.title = "{지역} 조경업체", "{지역} 조경업체 고르는 법"
    resolved = row.resolved("경기 용인")
    assert resolved.keyword == "경기 용인 조경업체"
    assert resolved.title.startswith("경기 용인")
    assert row.keyword == "{지역} 조경업체"  # 원본은 그대로
