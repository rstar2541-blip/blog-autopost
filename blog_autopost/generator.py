"""키워드로 글 초안 만들기: template(오프라인 뼈대) 또는 claude(Claude API)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

from .config import GeneratorConfig, TopicConfig
from .keywords import Keyword
from .prompts import COUPANG_DISCLOSURE, DRAFT_SCHEMA, system_prompt, user_prompt


class GenerationError(RuntimeError):
    pass


@dataclass
class Draft:
    keyword: Keyword
    topic_key: str
    title: str
    meta_description: str
    body_markdown: str
    tags: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    engine: str = "template"
    created: str = field(default_factory=lambda: date.today().isoformat())


def finalize_body(body: str, kw: Keyword, topic: TopicConfig) -> str:
    """본문 앞뒤에 제휴 고지와 면책 문구를 붙인다."""
    parts = []
    if kw.monetize.startswith("쿠팡"):
        parts.append(f"> {COUPANG_DISCLOSURE}")
    parts.append(body.strip())
    if topic.disclaimer:
        parts.append(f"---\n\n*{topic.disclaimer}*")
    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------- template

_SECTIONS = {
    "정보": [
        ("{kw}, 결론부터 말씀드리면", "검색한 분이 가장 궁금한 답을 2~3문장으로 먼저 정리"),
        ("왜 이게 중요할까요", "놓치면 생기는 문제, 현장에서 자주 본 실패"),
        ("단계별로 따라 하기", "순서대로 번호 목록, 단계마다 사진 1장"),
        ("자주 하는 실수", "초보가 많이 틀리는 부분 3가지"),
    ],
    "문제해결": [
        ("이런 증상이라면", "증상 사진과 함께 어떤 상태인지 구별법"),
        ("원인은 보통 이 세 가지", "원인별로 소제목, 각각 확인하는 법"),
        ("지금 바로 할 수 있는 대처", "오늘 할 일과 며칠 지켜볼 일 구분"),
        ("다음에 안 생기게 하려면", "예방 체크리스트"),
    ],
    "비교": [
        ("한눈에 비교", "비교표: 가격대, 장점, 단점, 추천 대상"),
        ("이런 분께는 앞쪽을 권해요", "상황 예시와 이유"),
        ("이런 분께는 뒤쪽이 맞아요", "상황 예시와 이유"),
        ("제가 실제로 고르는 기준", "운영자의 판단 기준과 경험"),
    ],
    "구매": [
        ("고르는 기준 4가지", "기준별로 짧게 설명"),
        ("상황별 추천 유형", "초보, 넓은 공간, 예산 적을 때 등"),
        ("사기 전 체크리스트", "체크 목록"),
        ("제가 실제로 쓰는 것", "사용 경험과 아쉬운 점"),
    ],
    "비용": [
        ("{kw}, 대략 이 정도 듭니다", "금액 범위와 그 범위가 나오는 조건"),
        ("비용을 좌우하는 요소", "면적, 자재, 인건비, 지역 등 항목별 설명"),
        ("견적 예시", "실제 견적서 항목 예시 표"),
        ("비용을 아끼는 방법", "직접 할 수 있는 것과 맡겨야 하는 것"),
    ],
    "경험": [
        ("이 이야기를 쓰는 이유", "독자가 공감할 상황"),
        ("실제로 겪은 과정", "시간 순서대로"),
        ("해 보고 알게 된 것", "교훈 3가지"),
        ("비슷한 상황이라면", "독자에게 드리는 조언"),
    ],
}


def generate_template(kw: Keyword, topic: TopicConfig) -> Draft:
    sections = _SECTIONS.get(kw.intent, _SECTIONS["정보"])
    lines = [topic.greeting, ""] if topic.greeting else []
    lines += [
        f"[경험 추가: '{kw.keyword}'를 검색한 독자에게 건넬 공감 한마디와, 이 주제를 직접 다뤄 본 계기 1~2문장]",
        "",
        f"이번 글에서는 **{kw.keyword}**에 대해 정리합니다. [확인 필요: 첫 문단에서 줄 핵심 답]",
        "",
        f"[사진: {kw.keyword} 대표 사진]",
        "",
    ]
    for heading, guide in sections:
        lines += [
            f"## {heading.format(kw=kw.keyword)}",
            "",
            f"[경험 추가: {guide}]",
            "",
            f"[사진: '{heading.format(kw=kw.keyword)}' 내용을 보여 주는 장면]",
            "",
        ]
    if kw.monetize.startswith("쿠팡"):
        product = kw.monetize.split(":", 1)[-1]
        lines += [f"[제휴: {product}]", ""]
    lines += [
        "## 자주 묻는 질문",
        "",
        "**Q. [확인 필요: 독자가 자주 묻는 질문 1]**",
        "",
        "A. [경험 추가: 답변]",
        "",
        "**Q. [확인 필요: 독자가 자주 묻는 질문 2]**",
        "",
        "A. [경험 추가: 답변]",
        "",
        "**Q. [확인 필요: 독자가 자주 묻는 질문 3]**",
        "",
        "A. [경험 추가: 답변]",
        "",
        "## 마무리",
        "",
        f"> [경험 추가: {kw.keyword} 총정리 3줄]",
        "",
        "[경험 추가: 응원 한마디와 다음 글 예고]",
        "",
        "궁금하신 점은 댓글로 남겨주세요!",
    ]
    if kw.memo:
        lines = [f"> 운영자 메모: {kw.memo}", ""] + lines
    return Draft(
        keyword=kw,
        topic_key=topic.key,
        title=kw.title,
        meta_description=f"{kw.keyword}, {topic.name} 블로그에서 직접 겪은 내용으로 정리했습니다.",
        body_markdown=finalize_body("\n".join(lines), kw, topic),
        tags=[kw.keyword, kw.category],
        checklist=[
            "모든 [경험 추가] 자리를 직접 채우기",
            "모든 [확인 필요] 자리를 확인해서 채우기",
            "[사진] 자리에 직접 찍은 사진 넣기",
        ],
        engine="template",
    )


# ------------------------------------------------------------------ claude

def generate_claude(kw: Keyword, topic: TopicConfig, cfg: GeneratorConfig, client=None) -> Draft:
    import anthropic

    client = client or anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=cfg.model,
            max_tokens=cfg.max_tokens,
            # 안전 분류기가 거절하면 서버가 대체 모델로 자동 재시도
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system_prompt(topic),
            output_config={
                "effort": cfg.effort,
                "format": {"type": "json_schema", "schema": DRAFT_SCHEMA},
            },
            messages=[{"role": "user", "content": user_prompt(kw, topic)}],
        )
    except anthropic.AuthenticationError as e:
        raise GenerationError("Anthropic API 키가 올바르지 않습니다 (ANTHROPIC_API_KEY 확인).") from e
    except anthropic.RateLimitError as e:
        raise GenerationError("요청 한도를 넘었습니다. 잠시 후 다시 실행하세요.") from e
    except anthropic.APIStatusError as e:
        raise GenerationError(f"Claude API 오류 ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise GenerationError("Claude API에 연결하지 못했습니다. 네트워크를 확인하세요.") from e

    if response.stop_reason == "refusal":
        raise GenerationError(f"Claude가 이 키워드의 글 작성을 거절했습니다: {kw.keyword}")
    if response.stop_reason == "max_tokens":
        raise GenerationError("응답이 길어서 잘렸습니다. config.toml의 max_tokens를 늘려 주세요.")

    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise GenerationError("Claude 응답을 해석하지 못했습니다.") from e

    return Draft(
        keyword=kw,
        topic_key=topic.key,
        title=data["title"].strip() or kw.title,
        meta_description=data["meta_description"].strip(),
        body_markdown=finalize_body(data["body_markdown"], kw, topic),
        tags=[t.strip().lstrip("#") for t in data["tags"] if t.strip()],
        checklist=[c.strip() for c in data["checklist"] if c.strip()],
        engine=f"claude:{cfg.model}",
    )


def generate(kw: Keyword, topic: TopicConfig, cfg: GeneratorConfig, engine: str | None = None, client=None) -> Draft:
    engine = engine or cfg.engine
    if engine == "template":
        return generate_template(kw, topic)
    if engine == "claude":
        return generate_claude(kw, topic, cfg, client=client)
    raise ValueError(f"알 수 없는 engine: {engine}")
