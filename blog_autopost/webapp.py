"""키워드 캘린더·문체 가이드를 넣어 글공방 웹페이지를 만든다.

어떤 블로그의 글공방인지는 설정 파일의 [site] 가 정한다.
config.toml → 꼬몽맘 글공방(web/blog-writer.html), config_carso.toml → 카쏘 글공방(web/carso-writer.html)
"""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from . import keywords as kwmod
from .config import Config

PLACEHOLDER = "/*__DATA__*/null"
THEME_PLACEHOLDER = "/*__THEME__*/"
TEXT_PLACEHOLDERS = ("__SITE_NAME__", "__SITE_TAGLINE__", "__BRAND_FONT__")
_TOKEN = re.compile(r"^[a-z][a-z0-9-]*$")
_COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def build_data(cfg: Config) -> dict:
    topics, rows = [], []
    voice_by_file = {Path(v.file).as_posix(): v.key for v in cfg.site.voices}
    for t in cfg.topics.values():
        topics.append({
            "key": t.key, "name": t.name, "label": t.label,
            "persona": t.persona, "audience": t.audience, "disclaimer": t.disclaimer,
            "voice": voice_by_file.get(Path(t.voice).as_posix(), "") if t.voice else "",  # 이 주제의 기본 화자
        })
        for r in kwmod.load(t.csv):
            k = r.resolved(cfg.region)
            rows.append([k.id, t.key, k.month, k.week, k.category, k.keyword, k.title, k.intent,
                         k.peak_month, k.priority, k.monetize, k.status])
    from .datalab import read_trends

    trends_raw = read_trends(cfg.trends_path)
    trends = {kid: [t["volume"], t["peak_month"], t["next2"], t["yoy"], t["by_month"]]
              for kid, t in trends_raw.items() if len(t["by_month"]) == 12}
    first = next(iter(trends_raw.values()), None)
    trend_meta = {"anchor": first["anchor"], "fetched": first["fetched"]} if first else None
    site = cfg.site
    voices = [{"key": v.key, "label": v.label, "greeting": v.greeting, "center": v.center,
               "note": v.note, "text": v.text} for v in site.voices]
    return {"built": date.today().isoformat(), "site": {"name": site.name, "memoExample": site.memo_example,
                                                        "ownExample": site.own_example,
                                                        "ownTitleExample": site.own_title_example,
                                                        "blogId": site.blog_id},
            "topics": topics, "keywords": rows, "voices": voices, "trends": trends, "trendMeta": trend_meta}


def theme_css(cfg: Config) -> str:
    """[site] colors / colors_dark 를 CSS 변수 덮어쓰기로 바꾼다 (템플릿 기본 색 위에 얹음)."""
    site = cfg.site

    def decls(colors: dict) -> str:
        out = []
        for name, value in colors.items():
            if not _TOKEN.match(name) or not _COLOR.match(str(value)):
                raise ValueError(f"site.colors 값이 이상합니다: {name} = {value!r} (예: leaf = \"#1f5fa8\")")
            out.append(f"--{name}: {value};")
        return " ".join(out)

    css = []
    font = f'--font-brand: "{site.brand_font}", "Nanum Gothic", sans-serif; --brand-weight: {int(site.brand_weight)};'
    css.append(f":root {{ {font} {decls(site.colors)} }}")
    if site.colors_dark:
        dark = decls(site.colors_dark)
        css.append(f'@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ {dark} }} }}')
        css.append(f':root[data-theme="dark"] {{ {dark} }}')
    return "\n".join(css)


def render_page(cfg: Config, template: Path | None = None) -> str:
    template = template or cfg.root / "web" / "template.html"
    page = template.read_text(encoding="utf-8")
    for token in (PLACEHOLDER, THEME_PLACEHOLDER, *TEXT_PLACEHOLDERS):
        if token not in page:
            raise ValueError(f"템플릿에 {token} 자리가 없습니다: {template}")
    payload = json.dumps(build_data(cfg), ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # </script> 로 스크립트가 끊기지 않게
    site = cfg.site
    page = (page.replace("__SITE_NAME__", html.escape(site.name))
                .replace("__SITE_TAGLINE__", html.escape(site.tagline))
                .replace("__BRAND_FONT__", f"{quote_plus(site.brand_font)}:wght@{int(site.brand_weight)}")
                .replace(THEME_PLACEHOLDER, theme_css(cfg).replace("</", "<\\/")))
    return page.replace(PLACEHOLDER, payload)


def build_web(cfg: Config, template: Path | None = None, out: Path | None = None) -> Path:
    out = out or cfg.web_out
    out.write_text(render_page(cfg, template), encoding="utf-8")
    return out
