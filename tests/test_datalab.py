import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from blog_autopost import cli
from blog_autopost import keywords as kw
from blog_autopost.datalab import (DataLabClient, DataLabError, analyze, fetch_relative, month_range,
                                   read_trends, sparkline)

ROOT = Path(__file__).resolve().parents[1]


class FakeResp:
    def __init__(self, status, data):
        self.status_code, self._data, self.text = status, data, json.dumps(data)

    def json(self):
        return self._data


class FakeSession:
    """검색어마다 정해 둔 월별 값으로, 실제 API처럼 요청 안 최댓값 = 100 비율을 돌려준다."""

    def __init__(self, table, status=200):
        self.table, self.status, self.bodies, self.headers = table, status, [], []

    def post(self, url, json=None, timeout=None, headers=None):
        self.bodies.append(json)
        self.headers.append(headers)
        if self.status != 200:
            return FakeResp(self.status, {"errorMessage": "fail", "errorCode": "024"})
        groups = json["keywordGroups"]
        raw = {g["groupName"]: self.table.get(g["keywords"][0], {}) for g in groups}
        top = max([v for vals in raw.values() for v in vals.values()] or [1])
        results = [{"title": g["groupName"], "keywords": g["keywords"],
                    "data": [{"period": p + "-01", "ratio": v / top * 100} for p, v in sorted(raw[g["groupName"]].items()) if v]}
                   for g in groups]
        return FakeResp(200, {"startDate": json["startDate"], "endDate": json["endDate"],
                              "timeUnit": "month", "results": results})


def test_month_range_uses_complete_months():
    start, end, periods = month_range(date(2026, 11, 9), 36)
    assert (start, end) == ("2023-11-01", "2026-10-31")
    assert periods[0] == "2023-11" and periods[-1] == "2026-10" and len(periods) == 36
    assert month_range(date(2026, 1, 5), 12)[1] == "2025-12-31"


def _periods():
    return month_range(date(2026, 11, 9), 24)


def test_fetch_relative_is_comparable_across_batches():
    start, end, periods = _periods()
    # 기준(텃밭) 매달 50, a 는 기준의 2배, f 는 기준의 절반 — 서로 다른 요청에 들어가도 비교돼야 함
    table = {"텃밭": {p: 50 for p in periods}, "a": {p: 100 for p in periods},
             "b": {p: 10 for p in periods}, "c": {p: 5 for p in periods}, "d": {p: 1 for p in periods},
             "f": {p: 25 for p in periods}}
    session = FakeSession(table)
    client = DataLabClient("id", "secret", session=session)
    out = fetch_relative(client, ["a", "b", "c", "d", "f", "a"], start, end, periods, "텃밭")
    assert client.calls == 2  # 5개 = 4개 + 1개, 기준은 매번 포함
    assert all(len(b["keywordGroups"]) <= 5 and b["keywordGroups"][0]["groupName"] == "텃밭" for b in session.bodies)
    assert out["a"][0] == pytest.approx(200) and out["f"][0] == pytest.approx(50)
    assert session.headers[0] == {"X-Naver-Client-Id": "id", "X-Naver-Client-Secret": "secret"}


def test_analyze_finds_peak_yoy_and_next_months():
    start, end, periods = month_range(date(2026, 11, 9), 36)
    # 4월에 몰리는 키워드, 올해가 작년보다 2배
    values = []
    for p in periods:
        y, m = int(p[:4]), int(p[5:])
        base = 100 if m == 4 else (40 if m in (3, 5) else 5)
        values.append(base * (2 if (y, m) >= (2026, 8) else 1))
    s = analyze("고추 모종", values, periods, date(2026, 11, 9))
    assert s.peak_month == 4 and s.seasonality > 3
    assert s.yoy == pytest.approx(100.0)
    assert s.next2 == pytest.approx(5.0)  # 12월·1월은 비수기
    flat = analyze("없음", [0.0] * 36, periods, date(2026, 11, 9))
    assert not flat.has_data and flat.peak_month == 0


def test_errors_are_readable():
    start, end, periods = _periods()
    client = DataLabClient("id", "bad", session=FakeSession({}, status=401))
    with pytest.raises(DataLabError, match="인증 실패"):
        client.search([("a", ["a"])], start, end)
    client = DataLabClient("id", "s", session=FakeSession({"a": {periods[0]: 3}}))
    with pytest.raises(DataLabError, match="기준 키워드"):
        fetch_relative(client, ["a"], start, end, periods, "없는기준")


def test_from_env(monkeypatch):
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    monkeypatch.delenv("NAVER_CLIENT_SECRET", raising=False)
    with pytest.raises(DataLabError, match="NAVER_CLIENT_ID, NAVER_CLIENT_SECRET"):
        DataLabClient.from_env()


def test_sparkline():
    assert sparkline([0, 50, 100]) == "▁▅█"
    assert sparkline([0, 0]) == "··"


def test_cli_trends_update_writes_report_and_applies_peaks(tmp_path, monkeypatch, capsys):
    shutil.copy(ROOT / "config.toml", tmp_path / "config.toml")
    shutil.copytree(ROOT / "keywords", tmp_path / "keywords")
    shutil.copytree(ROOT / "style", tmp_path / "style")
    (tmp_path / "keywords" / "trends.csv").unlink(missing_ok=True)
    monkeypatch.chdir(tmp_path)
    start, end, periods = month_range(date(2026, 11, 9), 36)
    rows = kw.load(tmp_path / "keywords" / "01_seedling_garden.csv")
    table = {"텃밭": {p: 50 for p in periods}}
    for i, r in enumerate(rows):
        # 키워드마다 다른 달에 몰리게
        table[r.keyword] = {p: (90 if int(p[5:]) == (i % 12) + 1 else 3) for p in periods} if i % 10 else {}
    session = FakeSession(table)
    monkeypatch.setattr(DataLabClient, "from_env", classmethod(lambda c: DataLabClient("id", "s", session=session)))
    assert cli.main(["--config", "config.toml", "--today", "2026-11-09", "trends", "update",
                     "--topic", "seedling", "--apply-peaks"]) == 0
    out = capsys.readouterr().out
    assert "지금 쓰면 좋은 글감" in out and "검색이 거의 없는 키워드" in out and "API 호출 25회" in out
    report = read_trends(tmp_path / "keywords" / "trends.csv")
    assert len(report) == len(rows)
    first = rows[1]  # i=1 → 2월에 몰림
    assert report[first.id]["peak_month"] == 2
    assert report[rows[0].id]["volume"] == 0  # 데이터 없음
    after = {r.id: r for r in kw.load(tmp_path / "keywords" / "01_seedling_garden.csv")}
    assert after[first.id].peak_month == 2
    assert after[rows[0].id].peak_month == rows[0].peak_month  # 데이터 없으면 그대로


def test_cli_trends_compare(tmp_path, monkeypatch, capsys):
    start, end, periods = month_range(date(2026, 11, 9), 36)
    session = FakeSession({"고추모종": {p: (100 if p.endswith("-04") else 10) for p in periods},
                           "토마토모종": {p: 20 for p in periods}})
    monkeypatch.setattr(DataLabClient, "from_env", classmethod(lambda c: DataLabClient("id", "s", session=session)))
    assert cli.main(["--config", str(ROOT / "config.toml"), "--today", "2026-11-09", "trends", "compare",
                     "고추모종", "토마토모종"]) == 0
    out = capsys.readouterr().out
    assert "고추모종" in out and "최다 4월" in out and len(session.bodies) == 1
