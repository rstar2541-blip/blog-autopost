"""워드프레스 REST API로 글 올리기 (응용 프로그램 비밀번호 인증)."""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests


class PublishError(RuntimeError):
    pass


@dataclass
class WordPressClient:
    base_url: str
    user: str
    app_password: str
    timeout: float = 30.0
    session: requests.Session | None = None

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        self.session = self.session or requests.Session()
        self.session.auth = (self.user, self.app_password)

    @classmethod
    def from_env(cls, prefix: str) -> "WordPressClient":
        """예: prefix='WP_BMW' → WP_BMW_URL, WP_BMW_USER, WP_BMW_APP_PASSWORD"""
        names = [f"{prefix}_URL", f"{prefix}_USER", f"{prefix}_APP_PASSWORD"]
        values = [os.environ.get(n, "").strip() for n in names]
        missing = [n for n, v in zip(names, values) if not v]
        if missing:
            raise PublishError(f"환경변수가 없습니다: {', '.join(missing)} (.env.example 참고)")
        return cls(*values)

    def _api(self, path: str) -> str:
        return f"{self.base_url}/wp-json/wp/v2/{path}"

    def _check(self, resp: requests.Response) -> dict | list:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("message", resp.text)
            except ValueError:
                detail = resp.text
            raise PublishError(f"워드프레스 오류 {resp.status_code}: {detail[:300]}")
        return resp.json()

    def tag_ids(self, names: list[str]) -> list[int]:
        ids = []
        for name in names:
            found = self._check(self.session.get(
                self._api("tags"), params={"search": name, "per_page": 20}, timeout=self.timeout))
            match = next((t for t in found if t.get("name") == name), None)
            if match is None:
                match = self._check(self.session.post(
                    self._api("tags"), json={"name": name}, timeout=self.timeout))
            ids.append(int(match["id"]))
        return ids

    def create_post(self, title: str, content: str, *, status: str = "draft",
                    excerpt: str = "", tags: list[str] | None = None,
                    date: str | None = None) -> dict:
        """status: draft(임시글) | publish(바로 발행) | future(예약, date 필요)"""
        if status not in {"draft", "publish", "future", "pending", "private"}:
            raise PublishError(f"지원하지 않는 status: {status}")
        if status == "future" and not date:
            raise PublishError("예약 발행(future)에는 date(예: 2026-11-10T07:00:00)가 필요합니다.")
        payload: dict = {"title": title, "content": content, "status": status, "excerpt": excerpt}
        if tags:
            payload["tags"] = self.tag_ids(tags)
        if date:
            payload["date"] = date
        post = self._check(self.session.post(self._api("posts"), json=payload, timeout=self.timeout))
        return {"id": post["id"], "link": post.get("link", ""), "status": post.get("status", status)}
