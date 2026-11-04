import json
from types import SimpleNamespace

import pytest

from blog_autopost.config import GeneratorConfig, TopicConfig
from blog_autopost.generator import GenerationError, generate, generate_claude
from blog_autopost.keywords import Keyword
from blog_autopost.prompts import COUPANG_DISCLOSURE, DRAFT_SCHEMA
from blog_autopost.render import count_placeholders


def make_topic(**over):
    data = dict(key="seedling", name="모종·텃밭", csv=None, persona="육묘장 대표",
                audience="텃밭 초보", disclaimer="")
    data.update(over)
    return TopicConfig(**data)


def make_kw(**over):
    data = dict(id="SG-016", month=1, week=3, category="육묘·파종", keyword="고추 씨앗 파종 시기",
                title="고추 씨앗 파종 시기, 거꾸로 계산하는 법", intent="정보", peak_month=2,
                priority="A", monetize="쿠팡:고추씨앗")
    data.update(over)
    return Keyword(**data)


def test_template_draft_has_placeholders_and_disclosure():
    draft = generate(make_kw(), make_topic(), GeneratorConfig(), engine="template")
    body = draft.body_markdown
    assert body.startswith(f"> {COUPANG_DISCLOSURE}")
    counts = count_placeholders(body)
    assert counts["사진"] >= 5 and counts["경험 추가"] >= 5 and counts["제휴"] == 1
    assert "## 자주 묻는 질문" in body
    assert draft.title == make_kw().title


@pytest.mark.parametrize("intent", ["정보", "문제해결", "비교", "구매", "비용", "경험"])
def test_template_every_intent(intent):
    draft = generate(make_kw(intent=intent, monetize="애드포스트"), make_topic(), GeneratorConfig(),
                     engine="template")
    assert COUPANG_DISCLOSURE not in draft.body_markdown
    assert draft.body_markdown.count("## ") >= 6


def test_disclaimer_appended():
    draft = generate(make_kw(), make_topic(disclaimer="전문가에게 확인하세요."), GeneratorConfig(),
                     engine="template")
    assert draft.body_markdown.rstrip().endswith("*전문가에게 확인하세요.*")


def test_memo_is_included_in_template():
    draft = generate(make_kw(memo="작년 1월 25일 파종, 발아율 90%"), make_topic(), GeneratorConfig(),
                     engine="template")
    assert "작년 1월 25일 파종" in draft.body_markdown


class FakeMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def fake_client(payload=None, stop_reason="end_turn"):
    text = json.dumps(payload or {
        "title": "고추 씨앗 파종 시기 총정리",
        "meta_description": "아주심기 날짜에서 거꾸로 계산하면 파종일이 나옵니다.",
        "tags": ["#고추파종", "고추 육묘", " "],
        "body_markdown": "첫 문단.\n\n## 파종일 계산\n\n[사진: 육묘 트레이]\n",
        "checklist": ["지역 늦서리 날짜 확인", ""],
    }, ensure_ascii=False)
    response = SimpleNamespace(stop_reason=stop_reason,
                               content=[SimpleNamespace(type="thinking", thinking=""),
                                        SimpleNamespace(type="text", text=text)])
    messages = FakeMessages(response)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def test_claude_request_shape_and_parsing():
    client, messages = fake_client()
    cfg = GeneratorConfig(model="claude-opus-5-5", effort="medium", max_tokens=16000)
    draft = generate_claude(make_kw(memo="발아 사진 있음"), make_topic(), cfg, client=client)

    call = messages.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["max_tokens"] == 16000
    assert call["fallbacks"] == "default"
    assert call["betas"] == ["server-side-fallback-2026-07-01"]
    assert call["output_config"] == {"effort": "medium",
                                     "format": {"type": "json_schema", "schema": DRAFT_SCHEMA}}
    assert "육묘장 대표" in call["system"]
    assert "고추 씨앗 파종 시기" in call["messages"][0]["content"]
    assert "발아 사진 있음" in call["messages"][0]["content"]
    assert "thinking" not in call and "temperature" not in call

    assert draft.title == "고추 씨앗 파종 시기 총정리"
    assert draft.tags == ["고추파종", "고추 육묘"]
    assert draft.checklist == ["지역 늦서리 날짜 확인"]
    assert draft.body_markdown.startswith(f"> {COUPANG_DISCLOSURE}")
    assert draft.engine == "claude:claude-opus-5-5"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_claude_bad_stop_reasons_raise(stop_reason):
    client, _ = fake_client(stop_reason=stop_reason)
    with pytest.raises(GenerationError):
        generate_claude(make_kw(), make_topic(), GeneratorConfig(), client=client)


def test_schema_is_strict():
    assert DRAFT_SCHEMA["additionalProperties"] is False
    assert set(DRAFT_SCHEMA["required"]) == set(DRAFT_SCHEMA["properties"])
