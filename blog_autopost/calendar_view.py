"""키워드 캘린더 전체를 한 장의 HTML로 보기."""
from __future__ import annotations

import html
from datetime import date

from .keywords import Keyword

STATUS_LABEL = {"todo": "예정", "draft": "초안", "published": "발행", "skip": "건너뜀"}


def render_calendar(topics: list[tuple[str, str, list[Keyword]]], today: date) -> str:
    """topics: [(key, 주제 이름, 키워드 목록)]"""
    esc = html.escape
    months = [((today.month - 1 + i) % 12) + 1 for i in range(12)]

    summary = []
    for key, name, rows in topics:
        done = sum(r.status == "published" for r in rows)
        drafted = sum(r.status == "draft" for r in rows)
        summary.append(
            f'<div class="stat"><b>{esc(name)}</b><span>{len(rows)}개 · 초안 {drafted} · 발행 {done}</span></div>'
        )

    sections = []
    for m in months:
        cols = []
        for key, name, rows in topics:
            items = [r for r in rows if r.month == m]
            items.sort(key=lambda r: (r.week, r.id))
            lis = "".join(
                f'<li class="s-{r.status}"><span class="wk">{r.week}주</span>'
                f'<span class="pr p{r.priority}">{r.priority}</span>'
                f'<b>{esc(r.keyword)}</b><small>{esc(r.title)}</small>'
                f'<em>{STATUS_LABEL.get(r.status, r.status)}</em></li>'
                for r in items
            )
            cols.append(f'<div class="col"><h3>{esc(name)} <span>{len(items)}</span></h3><ul>{lis}</ul></div>')
        badge = ' <span class="now">이번 달</span>' if m == today.month else ""
        sections.append(f'<section><h2>{m}월{badge}</h2><div class="grid">{"".join(cols)}</div></section>')

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>블로그 키워드 캘린더</title>
<style>
  :root {{ --bg:#fafaf8; --card:#fff; --line:#e6e4df; --text:#1f1f1c; --muted:#6b6a65; --accent:#2f7d4f;
          --todo:#fff; --draft:#fff7e0; --published:#e7f5ec; --skip:#f0f0f0; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#141413; --card:#1e1e1c; --line:#33322f; --text:#ecebe6; --muted:#a3a29c; --accent:#6cc28f;
            --todo:#1e1e1c; --draft:#3a3220; --published:#1f3527; --skip:#262624; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:24px 16px 48px; background:var(--bg); color:var(--text);
         font-family:-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif; line-height:1.5; }}
  header, section {{ max-width:1280px; margin:0 auto; }}
  h1 {{ font-size:22px; margin:0 0 4px; }}
  header p {{ color:var(--muted); margin:0 0 16px; font-size:14px; }}
  .stats {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:24px; }}
  .stat {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:8px 12px; font-size:13px; }}
  .stat span {{ display:block; color:var(--muted); }}
  h2 {{ font-size:18px; margin:28px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--line); }}
  .now {{ font-size:12px; background:var(--accent); color:#fff; padding:2px 8px; border-radius:99px; vertical-align:middle; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:12px; }}
  .col {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:10px; min-width:0; }}
  .col h3 {{ font-size:14px; margin:2px 4px 8px; }}
  .col h3 span {{ color:var(--muted); font-weight:400; }}
  ul {{ list-style:none; margin:0; padding:0; display:grid; gap:6px; }}
  li {{ border:1px solid var(--line); border-radius:6px; padding:6px 8px; font-size:13px; position:relative; }}
  li b {{ display:block; padding-right:40px; }}
  li small {{ display:block; color:var(--muted); }}
  li em {{ position:absolute; right:8px; top:6px; font-style:normal; font-size:11px; color:var(--muted); }}
  .wk, .pr {{ font-size:11px; margin-right:4px; color:var(--muted); }}
  .pA {{ color:#c2410c; font-weight:700; }}
  .s-todo {{ background:var(--todo); }} .s-draft {{ background:var(--draft); }}
  .s-published {{ background:var(--published); }} .s-skip {{ background:var(--skip); opacity:.6; }}
</style>
</head>
<body>
<header>
  <h1>블로그 키워드 캘린더</h1>
  <p>{today.isoformat()} 기준 · 이번 달부터 12개월 · 우선순위 A가 가장 중요</p>
  <div class="stats">{"".join(summary)}</div>
</header>
{"".join(sections)}
</body>
</html>
"""
