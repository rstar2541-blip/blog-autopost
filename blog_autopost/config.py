"""config.toml 읽기."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PLATFORMS = {"naver", "wordpress"}
ENGINES = {"template", "claude"}
ALIGNS = {"left", "center"}


@dataclass
class TopicConfig:
    key: str
    name: str
    csv: Path
    persona: str
    audience: str
    platform: str = "naver"
    max_per_day: int = 1
    disclaimer: str = ""
    wp_env_prefix: str = ""
    label: str = ""      # 화면에 쓰는 짧은 이름 (비우면 name)
    voice: str = ""      # 문체 가이드 파일 경로 (style/voice_*.md)
    greeting: str = ""   # 첫 줄 인사 (비우면 [author] greeting)
    voice_text: str = field(default="", repr=False)


@dataclass
class VoiceConfig:
    """글공방 화면의 '화자' 버튼 하나."""
    key: str
    label: str
    file: str
    greeting: str = ""   # 본문 첫 줄 인사. 빈 문자열이면 인사 없이 시작
    center: bool = True  # 붙여넣기용 미리보기를 가운데 정렬할지
    note: str = ""       # 운영자 소개 뒤에 덧붙일 말 (예: 이번 글은 아빠가 화자)
    text: str = field(default="", repr=False)


DEFAULT_TAGLINE = "키워드 고르기 → 경험 메모 → Claude 초안 → 네이버에 붙여넣기"


@dataclass
class SiteConfig:
    """글공방 웹페이지 한 개의 이름·모양·파일 위치 ([site])."""
    name: str = "글공방"
    tagline: str = DEFAULT_TAGLINE
    web_out: str = "web/blog-writer.html"
    trends: str = "keywords/trends.csv"
    brand_font: str = "Gaegu"            # 제목 글꼴 (Google Fonts 이름)
    brand_weight: int = 700              # 제목 글꼴 굵기 (그 글꼴에 있는 굵기여야 함)
    memo_example: str = ""               # 경험 메모 칸의 예시 문구
    own_example: str = ""                # '직접 쓰기' 키워드 칸의 예시
    own_title_example: str = ""          # '직접 쓰기' 제목 칸의 예시
    blog_id: str = ""                    # 네이버 블로그 아이디 (발행 주소 예시에 사용)
    colors: dict = field(default_factory=dict)       # 밝은 화면 색 덮어쓰기 (예: leaf = "#1f5fa8")
    colors_dark: dict = field(default_factory=dict)  # 어두운 화면 색 덮어쓰기
    voices: list[VoiceConfig] = field(default_factory=list)


@dataclass
class GeneratorConfig:
    engine: str = "template"
    model: str = "claude-opus-5-5"
    effort: str = "medium"
    max_tokens: int = 16000
    lookahead_months: int = 1


@dataclass
class Config:
    root: Path
    region: str
    drafts_dir: Path
    generator: GeneratorConfig
    topics: dict[str, TopicConfig] = field(default_factory=dict)
    align: str = "left"   # 붙여넣기용 HTML 정렬 (left | center)
    datalab: dict = field(default_factory=dict)   # [datalab] anchor, years
    site: SiteConfig = field(default_factory=SiteConfig)

    @property
    def trends_path(self) -> Path:
        return self.root / self.site.trends

    @property
    def web_out(self) -> Path:
        return self.root / self.site.web_out

    def topic(self, key: str) -> TopicConfig:
        if key not in self.topics:
            known = ", ".join(self.topics)
            raise KeyError(f"알 수 없는 주제 '{key}' (사용 가능: {known})")
        return self.topics[key]


def load_dotenv(path: Path) -> None:
    """.env 파일의 KEY=VALUE를 환경변수로 읽는다 (이미 설정된 값은 유지)."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        if key.strip() and value:
            os.environ.setdefault(key.strip(), value)


def load_config(path: str | Path = "config.toml") -> Config:
    path = Path(path).resolve()
    with open(path, "rb") as f:
        data = tomllib.load(f)
    root = path.parent
    load_dotenv(root / ".env")

    author = data.get("author", {})
    gen = GeneratorConfig(**data.get("generator", {}))
    if gen.engine not in ENGINES:
        raise ValueError(f"generator.engine은 {sorted(ENGINES)} 중 하나여야 합니다: {gen.engine}")

    render = data.get("render", {})
    align = render.get("align", "left")
    if align not in ALIGNS:
        raise ValueError(f"render.align은 {sorted(ALIGNS)} 중 하나여야 합니다: {align}")

    topics: dict[str, TopicConfig] = {}
    for key, raw in data.get("topics", {}).items():
        raw = dict(raw)
        raw["csv"] = root / raw["csv"]
        topic = TopicConfig(key=key, **raw)
        topic.greeting = topic.greeting or author.get("greeting", "")
        topic.label = topic.label or topic.name
        if topic.voice:
            voice_path = root / topic.voice
            if not voice_path.is_file():
                raise ValueError(f"topics.{key}.voice 파일이 없습니다: {topic.voice}")
            topic.voice_text = voice_path.read_text(encoding="utf-8").strip()
        if topic.platform not in PLATFORMS:
            raise ValueError(f"topics.{key}.platform은 {sorted(PLATFORMS)} 중 하나여야 합니다")
        if topic.platform == "wordpress" and not topic.wp_env_prefix:
            raise ValueError(f"topics.{key}: wordpress 플랫폼은 wp_env_prefix가 필요합니다")
        topics[key] = topic

    site = _load_site(data.get("site", {}), root, author, topics)

    return Config(
        root=root,
        region=author.get("region", ""),
        drafts_dir=root / data.get("drafts_dir", "drafts"),
        generator=gen,
        topics=topics,
        align=align,
        datalab=data.get("datalab", {}),
        site=site,
    )


def _load_site(raw: dict, root: Path, author: dict, topics: dict[str, TopicConfig]) -> SiteConfig:
    raw = dict(raw)
    voices_raw = raw.pop("voices", None)
    site = SiteConfig(**raw)
    if voices_raw is None:  # [site] 화자를 안 적었으면 첫 주제의 문체 파일 하나만 사용
        first = next((t for t in topics.values() if t.voice), None)
        voices_raw = [{"key": "default", "label": author.get("nickname", "기본"), "file": first.voice}] if first else []
    for v in voices_raw:
        v = dict(v)
        v.setdefault("greeting", author.get("greeting", ""))
        voice = VoiceConfig(**v)
        path = root / voice.file
        if not path.is_file():
            raise ValueError(f"site.voices '{voice.key}'의 문체 파일이 없습니다: {voice.file}")
        voice.text = path.read_text(encoding="utf-8").strip()
        site.voices.append(voice)
    keys = [v.key for v in site.voices]
    if len(keys) != len(set(keys)):
        raise ValueError(f"site.voices의 key가 겹칩니다: {keys}")
    return site
