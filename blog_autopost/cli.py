"""명령줄 도구: python -m blog_autopost <명령>"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import keywords as kwmod
from .calendar_view import render_calendar
from .config import Config, TopicConfig, load_config
from .generator import GenerationError, generate
from .keywords import Keyword
from .render import body_html, count_placeholders, load_draft, save_draft
from .datalab import DataLabError
from .wordpress import PublishError, WordPressClient


def _today(args) -> date:
    return date.fromisoformat(args.today) if args.today else date.today()


def _topics(cfg: Config, key: str | None) -> list[TopicConfig]:
    return [cfg.topic(key)] if key else list(cfg.topics.values())


def _find_anywhere(cfg: Config, keyword_id: str) -> tuple[TopicConfig, list[Keyword], Keyword]:
    for topic in cfg.topics.values():
        rows = kwmod.load(topic.csv)
        for row in rows:
            if row.id == keyword_id:
                return topic, rows, row
    raise KeyError(f"키워드 ID를 찾을 수 없습니다: {keyword_id}")


def _make_drafts(cfg: Config, topic: TopicConfig, rows: list[Keyword], targets: list[Keyword],
                 engine: str | None, upload: bool) -> int:
    made = 0
    wp = None
    if upload and topic.platform == "wordpress":
        wp = WordPressClient.from_env(topic.wp_env_prefix)
    for kw in targets:
        resolved = kw.resolved(cfg.region)
        print(f"  · {kw.id} {resolved.keyword} … ", end="", flush=True)
        try:
            draft = generate(resolved, topic, cfg.generator, engine=engine)
        except GenerationError as e:
            print(f"실패: {e}")
            continue
        md_path, html_path = save_draft(draft, cfg.drafts_dir, cfg.align)
        kw.status = "draft"
        note = ""
        if wp is not None:
            try:
                post = wp.create_post(draft.title, body_html(draft.body_markdown, cfg.align),
                                      status="draft", excerpt=draft.meta_description, tags=draft.tags)
                kw.post_url = post["link"]
                note = f" / 워드프레스 임시글 #{post['id']}"
            except PublishError as e:
                note = f" / 워드프레스 업로드 실패: {e}"
        kwmod.save(topic.csv, rows)  # 한 편씩 저장해서 중간에 멈춰도 진행 상황 유지
        made += 1
        print(f"완료 → {html_path.relative_to(cfg.root)}{note}")
    return made


# ------------------------------------------------------------------ commands

def cmd_list(cfg: Config, args) -> int:
    today = _today(args)
    for topic in _topics(cfg, args.topic):
        rows = kwmod.load(topic.csv)
        month = args.month or today.month
        shown = [r for r in rows if r.month == month and (not args.status or r.status == args.status)]
        print(f"\n[{topic.key}] {topic.name} · {month}월 · {len(shown)}개")
        for r in shown:
            kw = r.resolved(cfg.region)
            print(f"  {r.id}  {r.week}주  {r.priority}  {r.status:<9} {kw.keyword}  —  {kw.title}")
    return 0


def cmd_stats(cfg: Config, args) -> int:
    print(f"{'주제':<14}{'전체':>5}{'예정':>5}{'초안':>5}{'발행':>5}{'건너뜀':>6}")
    for topic in cfg.topics.values():
        rows = kwmod.load(topic.csv)
        c = {s: sum(r.status == s for r in rows) for s in kwmod.STATUSES}
        print(f"{topic.key:<14}{len(rows):>5}{c['todo']:>5}{c['draft']:>5}{c['published']:>5}{c['skip']:>6}")
    return 0


def cmd_next(cfg: Config, args) -> int:
    today = _today(args)
    if args.id:
        topic, rows, row = _find_anywhere(cfg, args.id)
        if row.status != "todo" and not args.force:
            print(f"{row.id}는 이미 '{row.status}' 상태입니다. 다시 만들려면 --force를 붙이세요.")
            return 1
        made = _make_drafts(cfg, topic, rows, [row], args.engine, args.upload)
        return 0 if made else 1
    total = 0
    for topic in _topics(cfg, args.topic):
        rows = kwmod.load(topic.csv)
        targets = kwmod.upcoming(rows, today, cfg.generator.lookahead_months)[: args.n]
        if not targets:
            print(f"[{topic.key}] 지금 쓸 예정 키워드가 없습니다.")
            continue
        print(f"[{topic.key}] {topic.name}")
        total += _make_drafts(cfg, topic, rows, targets, args.engine, args.upload)
    print(f"\n초안 {total}편을 만들었습니다.")
    return 0


def cmd_daily(cfg: Config, args) -> int:
    today = _today(args)
    total = 0
    for topic in _topics(cfg, args.topic):
        if topic.max_per_day <= 0:
            continue
        rows = kwmod.load(topic.csv)
        targets = kwmod.due(rows, today)[: topic.max_per_day]
        if not targets:
            print(f"[{topic.key}] 오늘 예정된 키워드 없음")
            continue
        print(f"[{topic.key}] {topic.name}")
        total += _make_drafts(cfg, topic, rows, targets, args.engine, args.upload)
    print(f"\n{today.isoformat()} 초안 {total}편 완료.")
    return 0


def cmd_publish(cfg: Config, args) -> int:
    md_path = Path(args.draft)
    from .render import parse_markdown

    meta, body = parse_markdown(md_path.read_text(encoding="utf-8"))
    topic, rows, row = _find_anywhere(cfg, meta["id"])
    if topic.platform != "wordpress":
        print(f"'{topic.key}' 주제는 {topic.platform} 플랫폼입니다. "
              f"{md_path.with_suffix('.html').name} 파일을 열어 본문을 복사해 붙여넣으세요.")
        return 1
    left = {k: v for k, v in count_placeholders(body).items() if v}
    if left and args.status != "draft" and not args.force:
        print("아직 채우지 않은 자리가 있어 발행을 멈췄습니다: "
              + ", ".join(f"{k} {v}곳" for k, v in left.items()))
        print("임시글로 올리려면 --status draft, 그래도 발행하려면 --force를 붙이세요.")
        return 1
    draft = load_draft(md_path, row)
    try:
        wp = WordPressClient.from_env(topic.wp_env_prefix)
        post = wp.create_post(draft.title, body_html(draft.body_markdown, cfg.align), status=args.status,
                              excerpt=draft.meta_description, tags=draft.tags, date=args.date)
    except PublishError as e:
        print(f"발행 실패: {e}")
        return 1
    row.post_url = post["link"]
    row.status = "published" if post["status"] in {"publish", "future"} else "draft"
    kwmod.save(topic.csv, rows)
    print(f"워드프레스 글 #{post['id']} ({post['status']}) {post['link']}")
    return 0


def cmd_mark(cfg: Config, args, status: str) -> int:
    topic, rows, row = _find_anywhere(cfg, args.id)
    row.status = status
    if getattr(args, "url", None):
        row.post_url = args.url
    kwmod.save(topic.csv, rows)
    print(f"{row.id} {row.keyword} → {status}")
    return 0


def cmd_analyze_blog(cfg: Config, args) -> int:
    from .naver_reader import analyze

    out = cfg.root / args.out
    print(f"{args.blog_id} 블로그 글을 읽는 중입니다 (처음엔 글 수 x 1초 정도 걸려요)…")
    summary = analyze(args.blog_id, out, delay=args.delay)
    years = ", ".join(f"{y}년 {n}" for y, n in summary["years"].items())
    print(f"\n글 {summary['posts']}편 ({years})")
    print(f"글자 수 중앙값 {summary['median_chars']}, 사진 중앙값 {summary['median_images']}장, "
          f"한 줄 {summary['median_line_length']}자, 가운데 정렬 {summary['center_ratio']:.0%}")
    top = sorted(summary["expressions_per_post"].items(), key=lambda kv: -kv[1])[:8]
    print("글당 자주 쓰는 표현: " + ", ".join(f"{w} {n}" for w, n in top))
    print(f"\n결과 폴더: {out.relative_to(cfg.root)} (text/ 에 글별 텍스트, summary.json 에 요약)")
    return 0


MONTHS_KO = "1월 2월 3월 4월 5월 6월 7월 8월 9월 10월 11월 12월".split()


def _trend_line(name: str, st_, width: int = 22) -> str:
    from .datalab import sparkline

    yoy = "" if st_.yoy is None else f"  작년 대비 {st_.yoy:+.0f}%"
    if not st_.has_data:
        return f"  {name[:width]:<{width}}  검색 데이터 없음"
    return (f"  {name[:width]:<{width}}  지수 {st_.volume:>6.1f}  {sparkline(st_.by_month)}  "
            f"최다 {st_.peak_month:>2}월{yoy}")


def cmd_trends_update(cfg: Config, args) -> int:
    from .datalab import DataLabClient, analyze, fetch_relative, month_range, read_trends, write_trends

    today = _today(args)
    anchor = args.anchor or cfg.datalab.get("anchor", "텃밭")
    years = args.years or int(cfg.datalab.get("years", 3))
    start, end, periods = month_range(today, years * 12)
    client = DataLabClient.from_env()

    topics = _topics(cfg, args.topic)
    rows_by_topic = {t.key: kwmod.load(t.csv) for t in topics}
    terms = [r.resolved(cfg.region).keyword for rows in rows_by_topic.values() for r in rows]
    print(f"데이터랩에서 {len(set(terms))}개 검색어의 {start} ~ {end} 월별 추이를 받는 중 (기준: '{anchor}')…")
    series = fetch_relative(client, terms, start, end, periods, anchor,
                            progress=lambda d, n: print(f"\r  {d}/{n}", end="", flush=True))
    print(f"\n  API 호출 {client.calls}회 (하루 한도 1,000회)")

    out_path = cfg.root / "keywords" / "trends.csv"
    existing = read_trends(out_path)
    rows_out, stats = [], {}
    keep_ids = {r.id for rows in rows_by_topic.values() for r in rows}
    for topic_key, rows in rows_by_topic.items():
        for r in rows:
            kw = r.resolved(cfg.region)
            st_ = analyze(kw.keyword, series.get(kw.keyword, [0.0] * len(periods)), periods, today)
            stats[r.id] = (topic_key, r, kw, st_)
            rows_out.append({"id": r.id, "topic": topic_key, "keyword": kw.keyword, "volume": st_.volume,
                             "peak_month": st_.peak_month, "planned_peak": r.peak_month,
                             "seasonality": st_.seasonality, "yoy": st_.yoy, "next2": st_.next2,
                             "by_month": st_.by_month, "anchor": anchor, "fetched": today.isoformat()})
    # 다른 주제의 기존 결과는 유지
    for kid, old in existing.items():
        if kid not in keep_ids:
            rows_out.append({"id": kid, **old})
    write_trends(out_path, rows_out)

    todo = [v for v in stats.values() if v[1].status == "todo" and v[3].has_data]
    print("\n[지금 쓰면 좋은 글감] 다음 두 달 예상 검색 지수 순")
    for _, r, kw, st_ in sorted(todo, key=lambda v: -v[3].next2)[:args.top]:
        print(_trend_line(f"{r.id} {kw.keyword}", st_, 26) + f"  → 다음 두 달 {st_.next2:.1f}")

    empty = [v for v in stats.values() if not v[3].has_data or v[3].volume < args.min_volume]
    print(f"\n[검색이 거의 없는 키워드] {len(empty)}개 — 다른 검색어로 바꾸는 걸 고려하세요")
    for _, r, kw, st_ in sorted(empty, key=lambda v: v[3].volume)[:10]:
        print(f"  {r.id} {kw.keyword}  (지수 {st_.volume:.2f})")

    off = [v for v in stats.values() if v[3].has_data and v[3].seasonality >= 1.3
           and min((v[3].peak_month - v[1].peak_month) % 12, (v[1].peak_month - v[3].peak_month) % 12) >= 2]
    print(f"\n[성수기 예상이 실제와 2달 이상 다른 키워드] {len(off)}개")
    for _, r, kw, st_ in off[:10]:
        print(f"  {r.id} {kw.keyword}  예상 {r.peak_month}월 → 실제 {st_.peak_month}월")

    if args.apply_peaks:
        changed = 0
        for t in topics:
            rows = rows_by_topic[t.key]
            for r in rows:
                st_ = stats[r.id][3]
                if st_.has_data and st_.seasonality >= 1.3 and r.peak_month != st_.peak_month:
                    r.peak_month = st_.peak_month
                    changed += 1
            kwmod.save(t.csv, rows)
        print(f"\n캘린더의 '검색 성수기' 칸 {changed}개를 실제 데이터로 바꿨습니다 (계절성이 뚜렷한 키워드만).")
    print(f"\n결과: {out_path.relative_to(cfg.root)} (엑셀로 열 수 있어요)")
    return 0


def cmd_trends_compare(cfg: Config, args) -> int:
    from .datalab import DataLabClient, analyze, month_range, series_from, sparkline

    if not 1 <= len(args.terms) <= 5:
        print("비교할 검색어는 1~5개입니다.")
        return 1
    today = _today(args)
    years = args.years or int(cfg.datalab.get("years", 3))
    start, end, periods = month_range(today, years * 12)
    client = DataLabClient.from_env()
    data = client.search([(t, [x.strip() for x in t.split(",") if x.strip()]) for t in args.terms], start, end)
    results = {r["title"]: r for r in data.get("results", [])}
    print(f"{start} ~ {end} · 숫자는 이 비교 안에서 가장 많이 검색된 달 = 100\n")
    print(f"  {'검색어':<20}  최근12달  {'최근 12개월 흐름':<12}  1~12월 평균")
    for t in args.terms:
        values = series_from(results.get(t, {}), periods)
        st_ = analyze(t, values, periods, today)
        yoy = "" if st_.yoy is None else f"  작년 대비 {st_.yoy:+.0f}%"
        print(f"  {t[:20]:<20}  {st_.volume:>7.1f}  {sparkline(values[-12:])}  {sparkline(st_.by_month)}"
              f"  최다 {st_.peak_month}월{yoy}" if st_.has_data else f"  {t[:20]:<20}  검색 데이터 없음")
    return 0


def cmd_build_web(cfg: Config, args) -> int:
    from .webapp import build_web

    out = build_web(cfg)
    print(f"웹페이지를 만들었습니다: {out.relative_to(cfg.root)}")
    return 0


def cmd_calendar(cfg: Config, args) -> int:
    today = _today(args)
    data = [(t.key, t.name, [r.resolved(cfg.region) for r in kwmod.load(t.csv)]) for t in cfg.topics.values()]
    out = Path(args.out)
    out.write_text(render_calendar(data, today), encoding="utf-8")
    print(f"캘린더를 만들었습니다: {out}")
    return 0


# --------------------------------------------------------------------- main

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="blog_autopost", description="블로그 키워드 캘린더와 초안 자동 생성")
    p.add_argument("--config", default="config.toml", help="설정 파일 (기본: config.toml)")
    p.add_argument("--today", help="기준 날짜 YYYY-MM-DD (미리 계획할 때)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("list", help="이번 달(또는 지정 달) 키워드 보기")
    s.add_argument("--topic")
    s.add_argument("--month", type=int)
    s.add_argument("--status", choices=kwmod.STATUSES)

    sub.add_parser("stats", help="주제별 진행 현황")

    def gen_opts(s):
        s.add_argument("--engine", choices=["template", "claude"], help="config.toml 설정 대신 사용할 방식")
        s.add_argument("--upload", action="store_true", help="워드프레스 주제는 임시글로 업로드")

    s = sub.add_parser("next", help="다음 키워드로 초안 만들기")
    s.add_argument("--topic")
    s.add_argument("-n", type=int, default=1, help="주제당 만들 개수 (기본 1)")
    s.add_argument("--id", help="특정 키워드 ID (예: SG-016)")
    s.add_argument("--force", action="store_true", help="이미 초안이 있어도 다시 만들기")
    gen_opts(s)

    s = sub.add_parser("daily", help="캘린더상 이번 주까지 예정된 키워드로 초안 만들기")
    s.add_argument("--topic")
    gen_opts(s)

    s = sub.add_parser("publish", help="초안(.md)을 워드프레스에 올리기")
    s.add_argument("draft", help="drafts/ 안의 .md 파일")
    s.add_argument("--status", default="draft", choices=["draft", "publish", "future"])
    s.add_argument("--date", help="예약 발행 시각 (예: 2026-11-10T07:00:00)")
    s.add_argument("--force", action="store_true", help="채우지 않은 자리가 있어도 발행")

    s = sub.add_parser("done", help="발행 완료로 표시 (네이버 등 직접 올린 글)")
    s.add_argument("id")
    s.add_argument("--url", help="발행한 글 주소")

    s = sub.add_parser("skip", help="이 키워드는 건너뛰기")
    s.add_argument("id")

    s = sub.add_parser("calendar", help="전체 캘린더를 HTML로 만들기")
    s.add_argument("--out", default="calendar.html")

    s = sub.add_parser("trends", help="네이버 데이터랩 검색어 트렌드")
    tsub = s.add_subparsers(dest="trends_command", required=True)
    t = tsub.add_parser("update", help="캘린더 키워드 전체의 검색 추이 받기 → keywords/trends.csv")
    t.add_argument("--topic")
    t.add_argument("--anchor", help="기준 검색어 (기본: config.toml [datalab] anchor)")
    t.add_argument("--years", type=int, help="몇 년치 (기본 3)")
    t.add_argument("--top", type=int, default=10, help="추천 글감 몇 개 보여줄지")
    t.add_argument("--min-volume", type=float, default=1.0, help="이보다 작으면 '검색 거의 없음'")
    t.add_argument("--apply-peaks", action="store_true", help="캘린더의 검색 성수기 칸을 실제 데이터로 바꾸기")
    t = tsub.add_parser("compare", help="검색어 1~5개 추이 비교 (쉼표로 묶으면 한 그룹)")
    t.add_argument("terms", nargs="+")
    t.add_argument("--years", type=int)

    sub.add_parser("build-web", help="글공방 웹페이지(web/blog-writer.html) 다시 만들기")

    s = sub.add_parser("analyze-blog", help="내 네이버 블로그 글을 읽어 문체 다시 분석")
    s.add_argument("blog_id", help="네이버 블로그 아이디 (예: samil5240)")
    s.add_argument("--out", default="style/raw", help="결과 폴더 (기본 style/raw)")
    s.add_argument("--delay", type=float, default=0.6, help="요청 사이 대기 초 (기본 0.6)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
    except FileNotFoundError:
        print(f"설정 파일을 찾을 수 없습니다: {args.config}")
        return 1
    try:
        if args.command == "list":
            return cmd_list(cfg, args)
        if args.command == "stats":
            return cmd_stats(cfg, args)
        if args.command == "next":
            return cmd_next(cfg, args)
        if args.command == "daily":
            return cmd_daily(cfg, args)
        if args.command == "publish":
            return cmd_publish(cfg, args)
        if args.command == "done":
            return cmd_mark(cfg, args, "published")
        if args.command == "skip":
            return cmd_mark(cfg, args, "skip")
        if args.command == "calendar":
            return cmd_calendar(cfg, args)
        if args.command == "trends":
            return cmd_trends_update(cfg, args) if args.trends_command == "update" else cmd_trends_compare(cfg, args)
        if args.command == "build-web":
            return cmd_build_web(cfg, args)
        if args.command == "analyze-blog":
            return cmd_analyze_blog(cfg, args)
    except (KeyError, PublishError, DataLabError) as e:
        print(e.args[0] if e.args else e)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
