import json
import re
from pathlib import Path

from blog_autopost.config import load_config
from blog_autopost.webapp import PLACEHOLDER, build_data, build_web

ROOT = Path(__file__).resolve().parents[1]


def test_build_data_shape():
    data = build_data(load_config(ROOT / "config.toml"))
    assert [t["label"] for t in data["topics"]] == ["모종·텃밭", "조경", "여성기업·관급", "BMW"]
    assert len(data["keywords"]) >= 400
    ids = [r[0] for r in data["keywords"]]
    assert len(ids) == len(set(ids))
    assert all(len(r) == 12 for r in data["keywords"])
    assert not any("{지역}" in r[5] or "{지역}" in r[6] for r in data["keywords"])
    assert data["voices"]["kkomongmom"].startswith("# 꼬몽맘 목소리")
    assert data["voices"]["grandpa"].startswith("# 꼬몽할배 목소리")
    assert data["greeting"] == "안녕하세요! 꼬몽맘입니다."


def test_build_web_embeds_data_safely(tmp_path):
    cfg = load_config(ROOT / "config.toml")
    out = build_web(cfg, out=tmp_path / "page.html")
    html = out.read_text(encoding="utf-8")
    assert PLACEHOLDER not in html
    assert html.startswith("<title>꼬몽맘 글공방</title>")
    script = re.search(r"<script>([\s\S]*)</script>", html).group(1)
    assert "</script" not in script  # 데이터 속 문자열이 스크립트를 끊지 않음
    payload = re.search(r"const DATA = (\{.*?\});\n", script).group(1)
    data = json.loads(payload.replace("<\\/", "</"))
    assert len(data["keywords"]) >= 400


def test_committed_page_is_up_to_date():
    """web/blog-writer.html 은 build-web 결과와 같아야 함 (날짜 제외)."""
    cfg = load_config(ROOT / "config.toml")
    committed = (ROOT / "web" / "blog-writer.html").read_text(encoding="utf-8")
    template = (ROOT / "web" / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(build_data(cfg), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    fresh = template.replace(PLACEHOLDER, payload)
    strip = lambda s: re.sub(r'"built":"[0-9-]+"', '"built":""', s)
    assert strip(committed) == strip(fresh), "python -m blog_autopost build-web 을 실행하세요"
