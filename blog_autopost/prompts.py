"""Claude에게 보낼 프롬프트와 응답 형식."""
from __future__ import annotations

from .config import TopicConfig
from .keywords import Keyword

COUPANG_DISCLOSURE = (
    "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
)

INTENT_GUIDE = {
    "정보": "검색한 사람이 바로 따라 할 수 있게 시기·방법·순서를 구체적으로 정리한다.",
    "문제해결": "증상 → 원인 → 지금 할 수 있는 대처 → 예방 순서로 쓴다.",
    "비교": "첫머리에 비교표를 두고, 어떤 사람에게 어느 쪽이 맞는지 결론을 분명히 낸다.",
    "구매": "고르는 기준과 사기 전 체크리스트를 중심으로 쓰고, 특정 상품을 과장해 추천하지 않는다.",
    "비용": "비용을 좌우하는 요소를 나눠 설명하고, 금액은 범위로만 쓰되 확실하지 않으면 확인 필요로 표시한다.",
    "경험": "운영자의 경험 메모를 중심으로 이야기처럼 쓰고, 독자가 가져갈 교훈으로 마무리한다.",
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "블로그 글 제목 (40자 이내, 키워드 포함)"},
        "meta_description": {"type": "string", "description": "검색 결과에 보일 요약 (80~150자)"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "태그 5~10개"},
        "body_markdown": {"type": "string", "description": "본문 (마크다운, 제목 제외)"},
        "checklist": {
            "type": "array",
            "items": {"type": "string"},
            "description": "발행 전에 운영자가 확인하거나 채워야 할 항목",
        },
    },
    "required": ["title", "meta_description", "tags", "body_markdown", "checklist"],
    "additionalProperties": False,
}


def system_prompt(topic: TopicConfig) -> str:
    return f"""당신은 아래 운영자를 대신해 블로그 글 초안을 쓰는 작가입니다. 운영자가 초안을 검토하고 사진과 경험을 더해 발행합니다.

[운영자] {topic.persona}
[블로그 주제] {topic.name}
[주요 독자] {topic.audience}

글쓰기 원칙
- 운영자의 1인칭 목소리로, 친근하지만 정확하게 씁니다. 존댓말(~습니다/~요)을 섞어 자연스럽게 씁니다.
- 첫 문단에서 검색한 사람이 가장 궁금해할 답을 먼저 줍니다.
- 소제목(##) 4~6개, 필요하면 하위 소제목(###), 목록과 표를 씁니다. 한 문단은 3~4문장 이내로 짧게 씁니다.
- 본문 분량은 공백 포함 2,000~3,000자입니다.
- 키워드는 제목, 첫 문단, 소제목 1~2곳에 자연스럽게 넣고 억지로 반복하지 않습니다.
- 끝에 '자주 묻는 질문' 소제목과 질문 3개, 짧은 마무리 문단을 둡니다.

지어내지 말 것 (가장 중요)
- 경험 메모에 없는 구체적 경험(날짜, 수량, 매출, 사건, 고객 이야기)을 만들어내지 않습니다. 경험이 들어가면 좋은 자리에는 [경험 추가: 무엇을 쓰면 좋은지]라고 표시합니다.
- 가격, 비율, 법령, 제도 요건, 한도, 신고 기한, 차량 사양처럼 바뀌거나 틀리기 쉬운 사실은 확실하지 않으면 단정하지 말고 [확인 필요: 무엇을 확인할지]라고 표시합니다.
- 사진이 들어가면 좋은 자리에 [사진: 찍을 장면] 표시를 6~10개 넣습니다.
- 제휴 상품을 소개하기 좋은 자리가 있으면 [제휴: 상품 종류] 표시를 1~2개 넣습니다. 상품명이나 링크는 쓰지 않습니다.
- 본문에 광고 문구, 고지 문구, 면책 문구는 넣지 않습니다. 필요한 문구는 프로그램이 따로 붙입니다.

checklist에는 본문에 넣은 [확인 필요]와 [경험 추가] 항목을 요약하고, 발행 전에 운영자가 해야 할 일을 적습니다."""


def user_prompt(kw: Keyword, topic: TopicConfig) -> str:
    guide = INTENT_GUIDE.get(kw.intent, INTENT_GUIDE["정보"])
    memo = kw.memo.strip() or "(없음: 경험이 필요한 자리는 [경험 추가] 표시로 남겨 주세요)"
    return f"""다음 키워드로 블로그 글 초안을 써 주세요.

- 핵심 키워드: {kw.keyword}
- 제목 아이디어: {kw.title}
- 분류: {kw.category}
- 검색 의도: {kw.intent} → {guide}
- 발행 예정: {kw.month}월 {kw.week}주차 (검색이 가장 많은 달: {kw.peak_month}월)
- 수익 연결: {kw.monetize}
- 운영자 경험 메모: {memo}"""
