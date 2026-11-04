"""내 네이버 블로그 글을 읽어 문체를 다시 분석하기 (python -m blog_autopost analyze-blog 아이디)."""
from __future__ import annotations

import json
import re
import statistics as st
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import requests
from bs4 import BeautifulSoup, NavigableString

LIST_URL = "https://blog.naver.com/PostTitleListAsync.naver"
POST_URL = "https://m.blog.naver.com/{blog}/{log_no}"
MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = MOBILE_UA
    return s


# ---------------------------------------------------------------- 글 목록

def list_posts(blog_id: str, session: requests.Session | None = None, delay: float = 0.4) -> list[dict]:
    s = session or _session()
    posts: list[dict] = []
    seen: set[str] = set()
    page = 1
    while True:
        r = s.get(LIST_URL, params=dict(blogId=blog_id, viewdate="", currentPage=page, categoryNo=0,
                                        parentCategoryNo=0, countPerPage=30), timeout=20)
        data = json.loads(r.text.replace("\\'", "'"))
        new = [p for p in data.get("postList", []) if p["logNo"] not in seen]
        if not new:
            break
        for p in new:
            seen.add(p["logNo"])
            posts.append(dict(logNo=p["logNo"], title=urllib.parse.unquote_plus(p["title"]),
                              categoryNo=str(p.get("categoryNo", "")), date=p.get("addDate", ""),
                              comments=str(p.get("commentCount", ""))))
        page += 1
        time.sleep(delay)
    return posts


# ---------------------------------------------------------------- 본문 해석

def _cls(el) -> str:
    return " ".join(el.get("class", []))


def _paragraph(p) -> dict:
    inner = " ".join(_cls(x) for x in p.find_all(True)) + " " + _cls(p)
    align = re.search(r"align-(\w+)", _cls(p))
    size = re.search(r"se-fs-(\w+)", inner)
    styled = [x.get("style", "") for x in p.find_all("span") if x.get("style")]
    return dict(
        type="p",
        text=p.get_text("").replace("​", "").strip(),
        align=align.group(1) if align else "left",
        size=size.group(1) if size else "",
        bold=bool(p.find(["b", "strong"])) or any("bold" in st_ for st_ in styled),
    )


def _parse_se_one(main) -> list[dict]:
    blocks: list[dict] = []
    for comp in main.select(".se-component"):
        c = _cls(comp)
        m = re.search(r"se-component se-(\w+)", c) or re.search(r"se-(\w+)", c)
        kind = m.group(1) if m else "unknown"
        if kind == "text":
            blocks += [_paragraph(p) for p in comp.select("p.se-text-paragraph")]
        elif kind in ("image", "imageStrip", "imageGroup", "imageSlide"):
            blocks.append(dict(type="image", count=len(comp.select("img")) or 1))
        elif kind == "sticker":
            blocks.append(dict(type="sticker"))
        elif kind == "quotation":
            blocks.append(dict(type="quote", text=comp.get_text("\n", strip=True)))
        elif kind == "sectionTitle":
            blocks.append(dict(type="heading", text=comp.get_text(" ", strip=True)))
        elif kind in ("placesMap", "map"):
            t = comp.select_one(".se-map-title")
            blocks.append(dict(type="map", text=t.get_text(strip=True) if t else ""))
        else:
            blocks.append(dict(type=kind, text=comp.get_text(" ", strip=True)[:200]))
    return blocks


def _parse_old_editor(area) -> list[dict]:
    for img in area.find_all("img"):
        img.replace_with(NavigableString("\n[[IMG]]\n"))
    blocks = []
    for line in area.get_text("\n").split("\n"):
        line = line.replace("​", "").strip()
        if line == "[[IMG]]":
            blocks.append(dict(type="image", count=1))
        else:
            blocks.append(dict(type="p", text=line, align="", size="", bold=False))
    return blocks


def parse_post_html(html: str) -> tuple[str, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(".se-main-container")
    if main:
        return "se1", _parse_se_one(main)
    area = soup.select_one(".se_component_wrap") or soup.select_one("#viewTypeSelector") or soup.select_one(".post_ct")
    return "old", (_parse_old_editor(area) if area else [])


def post_text(post: dict) -> str:
    """사람이 읽기 좋은 텍스트. ^ = 가운데 정렬, * = 굵게."""
    out = [f"### {post['date']} | {post['title']}"]
    for b in post["blocks"]:
        if b["type"] == "p":
            if b["text"]:
                mark = ("^" if b.get("align") == "center" else "") + ("*" if b.get("bold") else "")
                out.append((mark + " " if mark else "") + b["text"])
        elif b["type"] == "image":
            out.append(f"[사진 x{b.get('count', 1)}]")
        else:
            out.append(f"[{b['type']}] {b.get('text', '')}".rstrip())
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 요약

EXPRESSIONS = ["넘나", "진짜", "엄청", "완전", "너무", "추천드", "솔직", "꼭", "뚜둔", "짜잔",
               "ㅋㅋ", "ㅎㅎ", "ㅠㅠ", ">.<", "^^", "~.~", "ㄷㄷ", "흑흑"]


def summarize(posts: list[dict]) -> dict:
    paras = [b for p in posts for b in p["blocks"] if b["type"] == "p" and b["text"]]
    texts = [b["text"] for b in paras]
    joined = "\n".join(texts)
    per_post_chars = [sum(len(b["text"]) for b in p["blocks"] if b["type"] == "p") for p in posts]
    per_post_imgs = [sum(b.get("count", 1) for b in p["blocks"] if b["type"] == "image") for p in posts]
    first_lines = Counter()
    for p in posts:
        first = next((b["text"] for b in p["blocks"] if b["type"] == "p" and b["text"]), "")
        if first:
            first_lines[first[:25]] += 1
    return {
        "posts": len(posts),
        "years": dict(sorted(Counter(p["date"][:4] for p in posts).items())),
        "median_chars": st.median(per_post_chars) if posts else 0,
        "median_images": st.median(per_post_imgs) if posts else 0,
        "median_line_length": st.median(len(t) for t in texts) if texts else 0,
        "center_ratio": round(sum(b.get("align") == "center" for b in paras) / len(paras), 2) if paras else 0,
        "posts_with_sticker": sum(any(b["type"] == "sticker" for b in p["blocks"]) for p in posts),
        "posts_with_map": sum(any(b["type"] == "map" for b in p["blocks"]) for p in posts),
        "expressions_per_post": {w: round(joined.count(w) / len(posts), 1) for w in EXPRESSIONS} if posts else {},
        "top_first_lines": first_lines.most_common(5),
        "top_commented": sorted(
            ({"title": p["title"], "comments": int(p["comments"])} for p in posts if p.get("comments", "").isdigit()),
            key=lambda x: -x["comments"])[:10],
    }


def analyze(blog_id: str, out_dir: Path, delay: float = 0.6, session: requests.Session | None = None) -> dict:
    """글 목록과 본문을 받아 out_dir에 저장하고 요약을 돌려준다. 이미 받은 글은 다시 받지 않는다."""
    s = session or _session()
    posts_dir = out_dir / "posts"
    text_dir = out_dir / "text"
    posts_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    posts = []
    for meta in list_posts(blog_id, s, delay=delay):
        cache = posts_dir / f"{meta['logNo']}.json"
        if cache.exists():
            post = json.loads(cache.read_text(encoding="utf-8"))
            post.update(meta)  # 댓글 수 등은 최신으로
        else:
            r = s.get(POST_URL.format(blog=blog_id, log_no=meta["logNo"]), timeout=20)
            editor, blocks = parse_post_html(r.text)
            post = dict(**meta, editor=editor, blocks=blocks)
            time.sleep(delay)
        cache.write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
        (text_dir / f"{meta['logNo']}.txt").write_text(post_text(post), encoding="utf-8")
        posts.append(post)

    summary = summarize(posts)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
