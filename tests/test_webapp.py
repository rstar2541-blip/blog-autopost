import json
import re
from pathlib import Path

from blog_autopost.config import load_config
from blog_autopost.webapp import PLACEHOLDER, build_data, build_web, render_page

ROOT = Path(__file__).resolve().parents[1]


def test_build_data_shape():
    data = build_data(load_config(ROOT / "config.toml"))
    assert [t["label"] for t in data["topics"]] == ["모종·텃밭", "조경", "여성기업·관급", "BMW"]
    assert len(data["keywords"]) >= 400
    ids = [r[0] for r in data["keywords"]]
    assert len(ids) == len(set(ids))
    assert all(len(r) == 12 for r in data["keywords"])
    assert not any("{지역}" in r[5] or "{지역}" in r[6] for r in data["keywords"])
    voices = {v["key"]: v for v in data["voices"]}
    assert list(voices) == ["kkomongmom", "grandpa"]  # 첫 번째가 기본 화자
    assert voices["kkomongmom"]["text"].startswith("# 꼬몽맘 목소리")
    assert voices["kkomongmom"]["greeting"] == "안녕하세요! 꼬몽맘입니다."
    assert voices["kkomongmom"]["center"] is True
    assert voices["grandpa"]["text"].startswith("# 꼬몽할배 목소리")
    assert voices["grandpa"]["greeting"] == "안녕하세요, 꼬몽할배입니다."
    assert voices["grandpa"]["center"] is False
    assert data["site"]["blogId"] == "samil5240"


def test_build_web_embeds_data_safely(tmp_path):
    cfg = load_config(ROOT / "config.toml")
    out = build_web(cfg, out=tmp_path / "page.html")
    html = out.read_text(encoding="utf-8")
    assert PLACEHOLDER not in html
    assert html.startswith("<title>꼬몽맘 글공방</title>")
    assert "<h1>꼬몽맘 글공방</h1>" in html
    assert "__SITE_" not in html and "/*__THEME__*/" not in html
    assert "family=Gaegu:wght@700&" in html
    script = re.search(r"<script>([\s\S]*)</script>", html).group(1)
    assert "</script" not in script  # 데이터 속 문자열이 스크립트를 끊지 않음
    payload = re.search(r"const DATA = (\{.*?\});\n", script).group(1)
    data = json.loads(payload.replace("<\\/", "</"))
    assert len(data["keywords"]) >= 400


def test_committed_page_is_up_to_date():
    """web/blog-writer.html 은 build-web 결과와 같아야 함 (날짜 제외)."""
    cfg = load_config(ROOT / "config.toml")
    committed = cfg.web_out.read_text(encoding="utf-8")
    fresh = render_page(cfg)
    strip = lambda s: re.sub(r'"built":"[0-9-]+"', '"built":""', s)
    assert strip(committed) == strip(fresh), "python -m blog_autopost build-web 을 실행하세요"


def test_carso_site():
    cfg = load_config(ROOT / "config_carso.toml")
    data = build_data(cfg)
    assert data["site"]["name"] == "카쏘 글공방" and data["site"]["blogId"] == "efgm3"
    voices = {v["key"]: v for v in data["voices"]}
    assert list(voices) == ["carso", "info"]
    assert voices["carso"]["greeting"] == "안녕하세요! 카쏘입니다."
    assert voices["info"]["greeting"] == "" and voices["info"]["center"] is False
    # 주제마다 기본 화자: 관리·꿀팁은 카쏘, 제원·지원금은 정보형
    assert {t["key"]: t["voice"] for t in data["topics"]} == {
        "bmw": "carso", "car_review": "info", "life": "carso", "benefits": "info"}
    assert len(data["keywords"]) == 400
    assert cfg.trends_path == ROOT / "keywords" / "carso" / "trends.csv"


def test_carso_page_has_its_own_name_and_colors(tmp_path):
    cfg = load_config(ROOT / "config_carso.toml")
    html = build_web(cfg, out=tmp_path / "carso.html").read_text(encoding="utf-8")
    assert html.startswith("<title>카쏘 글공방</title>")
    assert "꼬몽맘" not in html.split("<script>")[0]
    assert "family=Black+Han+Sans:wght@400&" in html
    assert "--leaf: #1f5fae;" in html and ':root[data-theme="dark"] {' in html


def test_committed_carso_page_is_up_to_date():
    cfg = load_config(ROOT / "config_carso.toml")
    strip = lambda s: re.sub(r'"built":"[0-9-]+"', '"built":""', s)
    assert strip(cfg.web_out.read_text(encoding="utf-8")) == strip(render_page(cfg)), \
        "python -m blog_autopost --config config_carso.toml build-web 을 실행하세요"


def test_bad_color_is_rejected(tmp_path):
    import pytest
    from blog_autopost.webapp import theme_css

    cfg = load_config(ROOT / "config_carso.toml")
    cfg.site.colors = {"leaf": "red; } body { display:none"}
    with pytest.raises(ValueError):
        theme_css(cfg)
