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

    return Config(
        root=root,
        region=author.get("region", ""),
        drafts_dir=root / data.get("drafts_dir", "drafts"),
        generator=gen,
        topics=topics,
        align=align,
    )
