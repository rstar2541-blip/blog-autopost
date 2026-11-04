from pathlib import Path

from blog_autopost.config import load_config
from blog_autopost.naver_reader import parse_post_html, post_text, summarize
from blog_autopost.prompts import system_prompt
from blog_autopost.render import body_html

ROOT = Path(__file__).resolve().parents[1]


def test_style_files_exist_and_are_wired():
    for name in ["README.md", "voice_kkomongmom.md", "voice_kkomong_grandpa.md"]:
        assert (ROOT / "style" / name).is_file()
    cfg = load_config(ROOT / "config.toml")
    assert cfg.align == "center"
    assert cfg.region == "울산"
    for topic in cfg.topics.values():
        assert topic.voice_text.startswith("# 꼬몽맘 목소리")
        assert topic.greeting == "안녕하세요! 꼬몽맘입니다."


def test_system_prompt_carries_voice_and_greeting():
    cfg = load_config(ROOT / "config.toml")
    prompt = system_prompt(cfg.topic("seedling"))
    assert '본문 첫 줄은 "안녕하세요! 꼬몽맘입니다."로 시작합니다.' in prompt
    assert "[문체 가이드]" in prompt and "한 줄은 15~25자" in prompt
    assert "지어내지 말 것" in prompt
    # 지어내지 말 것 규칙이 문체 가이드보다 앞에 오고, 우선한다고 명시
    assert prompt.index("지어내지 말 것") < prompt.index("[문체 가이드]")


def test_short_lines_and_center_alignment():
    md = "첫 줄입니다\n둘째 줄이에요\n\n1. 하나\n2. 둘"
    left = body_html(md)
    assert "첫 줄입니다<br />\n둘째 줄이에요" in left
    assert "text-align" not in left
    center = body_html(md, "center")
    assert '<p style="text-align:center">' in center
    assert 'list-style-position:inside' in center


SE_ONE_HTML = """
<div class="se-main-container">
  <div class="se-component se-text"><div class="se-component-content">
    <p class="se-text-paragraph se-text-paragraph-align-center"><span class="se-fs-fs16">안녕하세요! 꼬몽맘입니다.</span></p>
    <p class="se-text-paragraph se-text-paragraph-align-center"><b>꼭 장갑을 껴 주세요</b></p>
    <p class="se-text-paragraph se-text-paragraph-align-center">​</p>
  </div></div>
  <div class="se-component se-image"><img src="a.jpg"></div>
  <div class="se-component se-sticker"><img src="s.png"></div>
  <div class="se-component se-placesMap"><div class="se-map-title">청연</div></div>
</div>
"""


def test_parse_naver_se_one():
    editor, blocks = parse_post_html(SE_ONE_HTML)
    assert editor == "se1"
    assert [b["type"] for b in blocks] == ["p", "p", "p", "image", "sticker", "map"]
    assert blocks[0]["align"] == "center" and blocks[0]["size"] == "fs16"
    assert blocks[1]["bold"] is True
    assert blocks[2]["text"] == ""
    assert blocks[5]["text"] == "청연"

    post = dict(logNo="1", title="t", date="2021. 1. 8.", comments="3", blocks=blocks)
    text = post_text(post)
    assert "^ 안녕하세요! 꼬몽맘입니다." in text and "^* 꼭 장갑을 껴 주세요" in text
    summary = summarize([post])
    assert summary["center_ratio"] == 1.0
    assert summary["posts_with_map"] == 1 and summary["posts_with_sticker"] == 1
    assert summary["top_first_lines"][0][0].startswith("안녕하세요")


def test_parse_naver_old_editor():
    editor, blocks = parse_post_html('<div id="viewTypeSelector">첫 줄<br>둘째 줄<img src="x.jpg"></div>')
    assert editor == "old"
    assert any(b["type"] == "image" for b in blocks)
    assert [b["text"] for b in blocks if b["type"] == "p" and b["text"]] == ["첫 줄", "둘째 줄"]
