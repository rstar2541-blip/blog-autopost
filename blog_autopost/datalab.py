"""네이버 데이터랩 검색어 트렌드 API로 글감의 검색 추이를 받아 온다.

데이터랩은 검색 '횟수'가 아니라, 한 번의 요청 안에서 가장 많이 검색된 시점을 100으로 둔
'상대 비율'을 돌려준다. 그래서 요청마다 같은 기준 키워드(anchor)를 함께 넣고,
기준 키워드의 평균이 100이 되도록 환산해서 서로 다른 요청의 키워드끼리 비교한다.
"""
from __future__ import annotations

import csv
import os
import statistics as st
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import requests

# 2026년 여름부터 검색어 트렌드 API는 NAVER API HUB(네이버 클라우드 콘솔)에서 발급한 키로 쓴다.
# 예전 네이버 개발자센터 키(openapi.naver.com)도 한시적으로 동작한다.
PROVIDERS = {
    "hub": {"url": "https://naverapihub.apigw.ntruss.com/search-trend/v1/search",
            "id_header": "X-NCP-APIGW-API-KEY-ID", "secret_header": "X-NCP-APIGW-API-KEY"},
    "developers": {"url": "https://openapi.naver.com/v1/datalab/search",
                   "id_header": "X-Naver-Client-Id", "secret_header": "X-Naver-Client-Secret"},
}
MAX_GROUPS = 5          # 한 요청에 넣을 수 있는 키워드 그룹 수 (API 제한)
SPARK = "▁▂▃▄▅▆▇█"


class DataLabError(RuntimeError):
    pass


@dataclass
class DataLabClient:
    client_id: str
    client_secret: str
    provider: str = "hub"
    timeout: float = 20.0
    session: requests.Session | None = None
    calls: int = 0

    def __post_init__(self) -> None:
        if self.provider not in PROVIDERS:
            raise DataLabError(f"provider는 {sorted(PROVIDERS)} 중 하나여야 합니다: {self.provider}")
        self.session = self.session or requests.Session()

    @classmethod
    def from_env(cls, provider: str = "hub") -> "DataLabClient":
        cid = os.environ.get("NAVER_CLIENT_ID", "").strip()
        secret = os.environ.get("NAVER_CLIENT_SECRET", "").strip()
        missing = [n for n, v in (("NAVER_CLIENT_ID", cid), ("NAVER_CLIENT_SECRET", secret)) if not v]
        if missing:
            raise DataLabError(
                f"환경변수가 없습니다: {', '.join(missing)} — .env 파일에 NAVER API HUB 앱의 Client ID와 Client Secret을 적어 주세요.")
        return cls(cid, secret, provider)

    def search(self, groups: list[tuple[str, list[str]]], start: str, end: str, time_unit: str = "month",
               device: str | None = None, gender: str | None = None, ages: list[str] | None = None) -> dict:
        """groups: [(그룹 이름, [검색어, ...]), ...] 최대 5개. 응답 JSON을 그대로 돌려준다."""
        if not 1 <= len(groups) <= MAX_GROUPS:
            raise ValueError(f"키워드 그룹은 1~{MAX_GROUPS}개여야 합니다: {len(groups)}")
        body: dict = {
            "startDate": start, "endDate": end, "timeUnit": time_unit,
            "keywordGroups": [{"groupName": name, "keywords": kws[:20]} for name, kws in groups],
        }
        if device:
            body["device"] = device
        if gender:
            body["gender"] = gender
        if ages:
            body["ages"] = ages
        api = PROVIDERS[self.provider]
        resp = self.session.post(api["url"], json=body, timeout=self.timeout, headers={
            api["id_header"]: self.client_id,
            api["secret_header"]: self.client_secret,
        })
        self.calls += 1
        if resp.status_code != 200:
            code = ""
            try:
                err = resp.json()
                inner = err.get("error", err)   # HUB: {"error": {...}}, 개발자센터: {...}
                code = str(inner.get("errorCode", ""))
                detail = " ".join(str(x) for x in (inner.get("message") or inner.get("errorMessage", ""),
                                                    inner.get("details", "")) if x) + f" (코드 {code or '?'})"
            except ValueError:
                detail = resp.text[:200]
            if code == "210":
                raise DataLabError("이 키로는 검색어 트렌드 API를 쓸 수 없습니다. 네이버 클라우드 콘솔의 "
                                   f"NAVER API HUB에서 Search Trend 이용을 신청했는지 확인하세요. {detail}")
            if resp.status_code == 401:
                raise DataLabError(f"인증 실패: Client ID/Secret을 확인하세요. {detail}")
            if resp.status_code == 429:
                raise DataLabError(f"호출 한도를 넘었습니다. 한도가 풀린 뒤 다시 실행하세요. {detail}")
            raise DataLabError(f"데이터랩 오류 {resp.status_code}: {detail}")
        return resp.json()


# ------------------------------------------------------------------ 기간·계산 도우미

def month_range(end: date, months: int) -> tuple[str, str, list[str]]:
    """end가 속한 달의 '직전 달'까지 완전한 months개월. (시작일, 종료일, ['YYYY-MM', ...])"""
    y, m = end.year, end.month - 1
    if m == 0:
        y, m = y - 1, 12
    periods = []
    for _ in range(months):
        periods.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    periods.reverse()
    last_y, last_m = map(int, periods[-1].split("-"))
    nm_y, nm_m = (last_y + 1, 1) if last_m == 12 else (last_y, last_m + 1)
    last_day = (date(nm_y, nm_m, 1).toordinal() - 1)
    return f"{periods[0]}-01", date.fromordinal(last_day).isoformat(), periods


def series_from(result: dict, periods: list[str]) -> list[float]:
    """API 결과 한 그룹의 data를 periods 순서의 값 목록으로 (데이터 없는 달은 0)."""
    by_month = {d["period"][:7]: float(d["ratio"]) for d in result.get("data", [])}
    return [by_month.get(p, 0.0) for p in periods]


def sparkline(values: list[float]) -> str:
    top = max(values) if values else 0
    if top <= 0:
        return "·" * len(values)
    return "".join(SPARK[min(len(SPARK) - 1, int(v / top * (len(SPARK) - 1) + 0.5))] for v in values)


def fetch_relative(client: DataLabClient, terms: list[str], start: str, end: str, periods: list[str],
                   anchor: str, progress=None) -> dict[str, list[float]]:
    """여러 검색어의 월별 추이를, 기준 키워드 평균=100 으로 환산해 돌려준다."""
    per_call = MAX_GROUPS - 1
    unique = list(dict.fromkeys(t for t in terms if t != anchor))
    out: dict[str, list[float]] = {}
    for i in range(0, len(unique), per_call):
        batch = unique[i:i + per_call]
        data = client.search([(anchor, [anchor])] + [(t, [t]) for t in batch], start, end)
        results = {r["title"]: r for r in data.get("results", [])}
        anchor_series = series_from(results.get(anchor, {}), periods)
        base = st.mean(anchor_series) if anchor_series else 0
        if base <= 0:
            raise DataLabError(f"기준 키워드 '{anchor}'의 검색 데이터가 없습니다. 다른 기준 키워드를 쓰세요.")
        for t in batch:
            out[t] = [round(v / base * 100, 2) for v in series_from(results.get(t, {}), periods)]
        if progress:
            progress(min(i + per_call, len(unique)), len(unique))
    return out


@dataclass
class TrendStats:
    term: str
    volume: float                  # 최근 12개월 평균 (기준 키워드 평균 = 100)
    by_month: list[float]          # 1~12월 평균 (여러 해 평균)
    peak_month: int                # 검색이 가장 많은 달 (0 = 데이터 없음)
    seasonality: float             # 가장 많은 달 / 월평균 (1이면 계절 없음)
    yoy: float | None              # 최근 3개월이 1년 전 같은 3개월보다 몇 % 늘었는지
    next2: float = 0.0             # 앞으로 두 달 예상 검색 지수
    extra: dict = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return self.volume > 0


def analyze(term: str, values: list[float], periods: list[str], today: date) -> TrendStats:
    months = [int(p[5:7]) for p in periods]
    by_month = []
    for m in range(1, 13):
        vals = [v for v, pm in zip(values, months) if pm == m]
        by_month.append(round(st.mean(vals), 2) if vals else 0.0)
    recent = values[-12:]
    volume = round(st.mean(recent), 2) if recent else 0.0
    mean_all = st.mean(by_month)
    peak = (by_month.index(max(by_month)) + 1) if mean_all > 0 else 0
    seasonality = round(max(by_month) / mean_all, 2) if mean_all > 0 else 0.0
    yoy = None
    if len(values) >= 15:
        now3, before3 = sum(values[-3:]), sum(values[-15:-12])
        if before3 > 0:
            yoy = round((now3 / before3 - 1) * 100, 1)
    nxt = [((today.month - 1 + k) % 12) for k in (1, 2)]   # 다음 달, 다다음 달 (0-index)
    next2 = round(st.mean(by_month[i] for i in nxt), 2)
    return TrendStats(term, volume, by_month, peak, seasonality, yoy, next2)


# ------------------------------------------------------------------ 결과 파일

TREND_FIELDS = ["id", "topic", "keyword", "volume", "peak_month", "planned_peak", "seasonality",
                "yoy", "next2", "by_month", "anchor", "fetched"]


def write_trends(path: Path, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TREND_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({**r, "by_month": ";".join(f"{v:g}" for v in r["by_month"]),
                        "yoy": "" if r["yoy"] is None else r["yoy"]})


def read_trends(path: Path) -> dict[str, dict]:
    if not path.is_file():
        return {}
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            out[r["id"]] = {
                "topic": r["topic"], "keyword": r["keyword"], "planned_peak": r["planned_peak"],
                "volume": float(r["volume"] or 0), "peak_month": int(r["peak_month"] or 0),
                "seasonality": float(r["seasonality"] or 0), "next2": float(r["next2"] or 0),
                "yoy": float(r["yoy"]) if r["yoy"] not in ("", None) else None,
                "by_month": [float(x) for x in r["by_month"].split(";")] if r["by_month"] else [],
                "anchor": r["anchor"], "fetched": r["fetched"],
            }
    return out
