import pytest

from blog_autopost.config import GeneratorConfig
from blog_autopost.generator import generate
from blog_autopost.render import (body_html, load_draft, parse_markdown, save_draft, slugify,
                                  to_html, to_markdown)
from blog_autopost.wordpress import PublishError, WordPressClient

from test_generator import make_kw, make_topic


def test_markdown_roundtrip(tmp_path):
    draft = generate(make_kw(), make_topic(), GeneratorConfig(), engine="template")
    draft.title = '따옴표 "있는" 제목: 콜론도'
    md_path, html_path = save_draft(draft, tmp_path)
    assert md_path.parent.name == "seedling"
    assert md_path.name.startswith(f"{draft.created}_SG-016_")
    assert html_path.exists()

    meta, body = parse_markdown(md_path.read_text(encoding="utf-8"))
    assert meta["id"] == "SG-016" and meta["title"] == draft.title
    assert body.strip() == draft.body_markdown.strip()

    again = load_draft(md_path, make_kw())
    assert again.title == draft.title and again.tags == draft.tags


def test_html_highlights_placeholders_and_tables():
    body = "| A | B |\n|---|---|\n| 1 | 2 |\n\n[사진: 모종] [확인 필요: 가격]"
    out = body_html(body)
    assert "<table>" in out
    assert "📷 사진: 모종" in out and "⚠️ 확인 필요: 가격" in out
    assert "[사진:" not in out


def test_full_html_document():
    draft = generate(make_kw(), make_topic(), GeneratorConfig(), engine="template")
    page = to_html(draft)
    assert page.startswith("<!doctype html>")
    assert "본문 복사하기" in page and 'id="post"' in page
    assert to_markdown(draft).startswith("---\nid: ")


def test_slugify():
    assert slugify("고추 씨앗, 파종 시기?") == "고추-씨앗-파종-시기"
    assert slugify("!!!") == "post"


class FakeResp:
    def __init__(self, status, data):
        self.status_code, self._data, self.text = status, data, str(data)

    def json(self):
        return self._data


class FakeSession:
    def __init__(self):
        self.calls = []
        self.auth = None

    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        if params["search"] == "고추":
            return FakeResp(200, [{"id": 7, "name": "고추"}, {"id": 8, "name": "고추모종"}])
        return FakeResp(200, [])

    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        if url.endswith("/tags"):
            return FakeResp(201, {"id": 99, "name": json["name"]})
        return FakeResp(201, {"id": 123, "link": "https://blog.example.com/?p=123", "status": json["status"]})


def test_wordpress_create_post_with_tags():
    session = FakeSession()
    wp = WordPressClient("https://blog.example.com/", "me", "app pass", session=session)
    post = wp.create_post("제목", "<p>본문</p>", status="draft", excerpt="요약", tags=["고추", "육묘"])
    assert post == {"id": 123, "link": "https://blog.example.com/?p=123", "status": "draft"}
    assert session.auth == ("me", "app pass")
    method, url, payload = session.calls[-1]
    assert url == "https://blog.example.com/wp-json/wp/v2/posts"
    assert payload["tags"] == [7, 99]
    assert ("POST", "https://blog.example.com/wp-json/wp/v2/tags", {"name": "육묘"}) in session.calls


def test_wordpress_errors():
    wp = WordPressClient("https://x", "u", "p", session=FakeSession())
    with pytest.raises(PublishError):
        wp.create_post("t", "c", status="future")
    with pytest.raises(PublishError):
        wp.create_post("t", "c", status="weird")


def test_wordpress_from_env(monkeypatch):
    monkeypatch.delenv("WP_T_URL", raising=False)
    with pytest.raises(PublishError, match="WP_T_URL"):
        WordPressClient.from_env("WP_T")
    monkeypatch.setenv("WP_T_URL", "https://x")
    monkeypatch.setenv("WP_T_USER", "u")
    monkeypatch.setenv("WP_T_APP_PASSWORD", "p")
    assert WordPressClient.from_env("WP_T").base_url == "https://x"
