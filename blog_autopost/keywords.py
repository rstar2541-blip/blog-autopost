"""키워드 캘린더 CSV 읽기/쓰기와 '오늘 쓸 키워드' 고르기."""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, fields
from datetime import date
from pathlib import Path

STATUSES = ("todo", "draft", "published", "skip")
PRIORITY_ORDER = {"A": 0, "B": 1, "C": 2}


@dataclass
class Keyword:
    id: str
    month: int
    week: int
    category: str
    keyword: str
    title: str
    intent: str
    peak_month: int
    priority: str
    monetize: str
    status: str = "todo"
    memo: str = ""
    post_url: str = ""

    def resolved(self, region: str) -> "Keyword":
        """{지역} 자리표시자를 설정한 지역명으로 바꾼 사본."""
        if "{지역}" not in self.keyword + self.title:
            return self
        name = region or "우리 지역"
        data = asdict(self)
        data["keyword"] = self.keyword.replace("{지역}", name)
        data["title"] = self.title.replace("{지역}", name)
        return Keyword(**data)


FIELDNAMES = [f.name for f in fields(Keyword)]


def load(path: str | Path) -> list[Keyword]:
    # utf-8-sig: 엑셀에서 저장한 BOM 있는 파일도 읽힘
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = []
        for raw in reader:
            raw = {k: (v or "").strip() for k, v in raw.items() if k in FIELDNAMES}
            raw["month"] = int(raw["month"])
            raw["week"] = int(raw["week"])
            raw["peak_month"] = int(raw["peak_month"])
            raw.setdefault("status", "todo")
            raw["status"] = raw["status"] or "todo"
            rows.append(Keyword(**raw))
    return rows


def save(path: str | Path, rows: list[Keyword]) -> None:
    # BOM을 붙여야 윈도우 엑셀에서 한글이 깨지지 않음
    tmp = Path(path).with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    tmp.replace(path)


def week_of_month(d: date) -> int:
    """1~7일=1주, 8~14일=2주, 15~21일=3주, 22일 이후=4주."""
    return min(4, (d.day - 1) // 7 + 1)


def month_offset(row_month: int, today_month: int) -> int:
    """이번 달 기준 몇 달 뒤인지 (0~11). 지난달은 11."""
    return (row_month - today_month) % 12


def _sort_key(row: Keyword, today: date) -> tuple:
    off = month_offset(row.month, today.month)
    # 지난달(11)에 남은 글을 이번 달보다 먼저 처리
    rank = -1 if off == 11 else off
    return (rank, row.week, PRIORITY_ORDER.get(row.priority, 9), row.id)


def _overdue_but_timely(row: Keyword, today: date) -> bool:
    """지난달 글이지만 검색 성수기가 이번 달~두 달 뒤라 아직 쓸 가치가 있는가."""
    return (month_offset(row.month, today.month) == 11
            and month_offset(row.peak_month, today.month) <= 2)


def due(rows: list[Keyword], today: date) -> list[Keyword]:
    """캘린더상 이번 주까지 써야 하는 todo 키워드.

    지난달에 못 쓴 글은 검색 시즌이 남은 것만 포함한다 (시즌이 지난 글은 내년 같은 달에 다시 나옴).
    """
    wom = week_of_month(today)
    out = []
    for row in rows:
        if row.status != "todo":
            continue
        off = month_offset(row.month, today.month)
        if _overdue_but_timely(row, today) or (off == 0 and row.week <= wom):
            out.append(row)
    return sorted(out, key=lambda r: _sort_key(r, today))


def upcoming(rows: list[Keyword], today: date, lookahead_months: int = 1) -> list[Keyword]:
    """밀린 글(시즌 남은 것) → 이번 달 남은 글 → 다음 달 글 순서의 todo 키워드."""
    out = []
    for row in rows:
        if row.status != "todo":
            continue
        off = month_offset(row.month, today.month)
        if _overdue_but_timely(row, today) or off <= lookahead_months:
            out.append(row)
    return sorted(out, key=lambda r: _sort_key(r, today))


def find(rows: list[Keyword], keyword_id: str) -> Keyword:
    for row in rows:
        if row.id == keyword_id:
            return row
    raise KeyError(f"키워드 ID를 찾을 수 없습니다: {keyword_id}")
