"""초안을 파일(마크다운/HTML)로 저장하고 다시 읽기."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import markdown as md

from .generator import Draft
from .keywords import Keyword

PLACEHOLDER_RE = re.compile(r"\[(사진|경험 추가|확인 필요|제휴):\s*([^\]]+)\]")
PLACEHOLDER_STYLE = {
    "사진": ("#e8f1ff", "#1d4ed8", "📷"),
    "경험 추가": ("#fff4e5", "#b45309", "✍️"),
    "확인 필요": ("#fde8e8", "#b91c1c", "⚠️"),
    "제휴": ("#eafaf0", "#047857", "🔗"),
}
FRONT_KEYS = ["id", "topic", "keyword", "title", "meta_description", "tags", "checklist", "engine", "created"]


def slugify(text: str, limit: int = 40) -> str:
    text = re.sub(r"[^\w\s가-힣-]", "", text).strip()
    text = re.sub(r"[\s_]+", "-", text)
    return text[:limit].strip("-") or "post"


def draft_basename(draft: Draft) -> str:
    return f"{draft.created}_{draft.keyword.id}_{slugify(draft.keyword.keyword)}"


def count_placeholders(text: str) -> dict[str, int]:
    counts = {k: 0 for k in PLACEHOLDER_STYLE}
    for m in PLACEHOLDER_RE.finditer(text):
        counts[m.group(1)] += 1
    return counts


# ------------------------------------------------------------ markdown file

def to_markdown(draft: Draft) -> str:
    values = {
        "id": draft.keyword.id,
        "topic": draft.topic_key,
        "keyword": draft.keyword.keyword,
        "title": draft.title,
        "meta_description": draft.meta_description,
        "tags": draft.tags,
        "checklist": draft.checklist,
        "engine": draft.engine,
        "created": draft.created,
    }
    front = "\n".join(f"{k}: {json.dumps(values[k], ensure_ascii=False)}" for k in FRONT_KEYS)
    return f"---\n{front}\n---\n\n{draft.body_markdown.strip()}\n"


def parse_markdown(text: str) -> tuple[dict, str]:
    """to_markdown()으로 쓴 파일을 (front matter, 본문)으로 나눈다."""
    if not text.startswith("---\n"):
        raise ValueError("초안 파일 맨 위에 --- 로 시작하는 정보 영역이 없습니다.")
    end = text.index("\n---\n", 4)
    meta = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, _, raw = line.partition(": ")
        meta[key.strip()] = json.loads(raw)
    body = text[end + 5:].lstrip("\n")
    return meta, body


# --------------------------------------------------------------------- html

def _style_placeholders(body_html: str) -> str:
    def repl(m: re.Match) -> str:
        bg, fg, icon = PLACEHOLDER_STYLE[m.group(1)]
        return (
            f'<span style="background:{bg};color:{fg};padding:2px 6px;border-radius:4px;'
            f'font-weight:600">{icon} {m.group(1)}: {m.group(2)}</span>'
        )

    return PLACEHOLDER_RE.sub(repl, body_html)


def body_html(body_markdown: str) -> str:
    converted = md.markdown(body_markdown, extensions=["tables", "sane_lists"])
    return _style_placeholders(converted)


def to_html(draft: Draft) -> str:
    """네이버 블로그 등 에디터에 복사해 붙여넣기 좋은 HTML 문서."""
    esc = html.escape
    counts = count_placeholders(draft.body_markdown)
    count_text = " · ".join(f"{k} {v}곳" for k, v in counts.items() if v)
    checklist = "".join(f"<li>{esc(c)}</li>" for c in draft.checklist)
    tags = " ".join(f"#{esc(t.replace(' ', ''))}" for t in draft.tags)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(draft.title)}</title>
<style>
  body {{ font-family: -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif;
         max-width: 760px; margin: 0 auto; padding: 24px 16px; line-height: 1.8; color: #222; background: #fff; }}
  .guide {{ background: #f6f7f9; border: 1px solid #e3e5e8; border-radius: 10px; padding: 16px 18px; margin-bottom: 28px; font-size: 14px; }}
  .guide h2 {{ font-size: 15px; margin: 0 0 8px; }}
  .guide ul {{ margin: 6px 0 0; padding-left: 20px; }}
  .guide button {{ margin-top: 12px; padding: 8px 14px; border: 0; border-radius: 6px; background: #03c75a; color: #fff; font-weight: 700; cursor: pointer; }}
  #post table {{ border-collapse: collapse; width: 100%; }}
  #post th, #post td {{ border: 1px solid #ddd; padding: 6px 10px; }}
  #post blockquote {{ margin: 0; padding: 8px 14px; border-left: 4px solid #ccc; color: #555; background: #fafafa; }}
</style>
</head>
<body>
<div class="guide">
  <h2>발행 전 확인</h2>
  <div>키워드: <b>{esc(draft.keyword.keyword)}</b> · 초안 방식: {esc(draft.engine)}</div>
  <div>채울 자리: {esc(count_text) or "없음"}</div>
  <div>요약(검색 설명): {esc(draft.meta_description)}</div>
  <div>태그: {tags}</div>
  <ul>{checklist}</ul>
  <button type="button" onclick="copyPost()">본문 복사하기</button>
  <span id="copied" style="margin-left:8px;color:#03a14c"></span>
</div>
<article id="post">
<h1>{esc(draft.title)}</h1>
{body_html(draft.body_markdown)}
</article>
<script>
function copyPost() {{
  const range = document.createRange();
  range.selectNodeContents(document.getElementById("post"));
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  let ok = false;
  try {{ ok = document.execCommand("copy"); }} catch (e) {{}}
  document.getElementById("copied").textContent = ok
    ? "복사됐습니다. 블로그 에디터에 붙여넣으세요."
    : "본문이 선택됐습니다. Ctrl+C(⌘+C)로 복사하세요.";
}}
</script>
</body>
</html>
"""


# --------------------------------------------------------------------- save

def save_draft(draft: Draft, drafts_dir: Path) -> tuple[Path, Path]:
    folder = drafts_dir / draft.topic_key
    folder.mkdir(parents=True, exist_ok=True)
    base = draft_basename(draft)
    md_path = folder / f"{base}.md"
    html_path = folder / f"{base}.html"
    md_path.write_text(to_markdown(draft), encoding="utf-8")
    html_path.write_text(to_html(draft), encoding="utf-8")
    return md_path, html_path


def load_draft(md_path: Path, keyword: Keyword) -> Draft:
    """수정한 마크다운 초안을 다시 Draft로 읽는다 (발행용)."""
    meta, body = parse_markdown(Path(md_path).read_text(encoding="utf-8"))
    return Draft(
        keyword=keyword,
        topic_key=meta["topic"],
        title=meta["title"],
        meta_description=meta.get("meta_description", ""),
        body_markdown=body,
        tags=meta.get("tags", []),
        checklist=meta.get("checklist", []),
        engine=meta.get("engine", ""),
        created=meta.get("created", ""),
    )
