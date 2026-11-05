"""키워드 캘린더·문체 가이드를 넣어 '꼬몽맘 글공방' 웹페이지(web/blog-writer.html)를 만든다."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import keywords as kwmod
from .config import Config

PLACEHOLDER = "/*__DATA__*/null"
VOICES = {
    "kkomongmom": "style/voice_kkomongmom.md",
    "grandpa": "style/voice_kkomong_grandpa.md",
}


def build_data(cfg: Config) -> dict:
    topics, rows = [], []
    for t in cfg.topics.values():
        topics.append({
            "key": t.key, "name": t.name, "label": t.label,
            "persona": t.persona, "audience": t.audience, "disclaimer": t.disclaimer,
        })
        for r in kwmod.load(t.csv):
            k = r.resolved(cfg.region)
            rows.append([k.id, t.key, k.month, k.week, k.category, k.keyword, k.title, k.intent,
                         k.peak_month, k.priority, k.monetize, k.status])
    greeting = next((t.greeting for t in cfg.topics.values() if t.greeting), "")
    voices = {key: (cfg.root / path).read_text(encoding="utf-8").strip() for key, path in VOICES.items()}
    return {"built": date.today().isoformat(), "greeting": greeting, "topics": topics,
            "keywords": rows, "voices": voices}


def build_web(cfg: Config, template: Path | None = None, out: Path | None = None) -> Path:
    template = template or cfg.root / "web" / "template.html"
    out = out or cfg.root / "web" / "blog-writer.html"
    html = template.read_text(encoding="utf-8")
    if PLACEHOLDER not in html:
        raise ValueError(f"템플릿에 데이터 자리({PLACEHOLDER})가 없습니다: {template}")
    payload = json.dumps(build_data(cfg), ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # </script> 로 스크립트가 끊기지 않게
    out.write_text(html.replace(PLACEHOLDER, payload), encoding="utf-8")
    return out
