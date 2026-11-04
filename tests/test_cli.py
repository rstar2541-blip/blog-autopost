import shutil
from pathlib import Path

import pytest

from blog_autopost import cli
from blog_autopost import keywords as kw

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """실제 config.toml과 키워드 CSV를 임시 폴더에 복사해서 사용."""
    shutil.copy(ROOT / "config.toml", tmp_path / "config.toml")
    shutil.copytree(ROOT / "keywords", tmp_path / "keywords")
    shutil.copytree(ROOT / "style", tmp_path / "style")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(*args):
    return cli.main(["--config", "config.toml", *args])


def test_list_and_stats(workspace, capsys):
    assert run("--today", "2026-11-04", "list", "--topic", "seedling") == 0
    out = capsys.readouterr().out
    assert "SG-002" in out and "마늘 월동 관리" in out
    assert run("stats") == 0
    assert "seedling" in capsys.readouterr().out


def test_daily_makes_due_drafts_and_updates_csv(workspace, capsys):
    today = __import__("datetime").date(2026, 11, 4)
    csv_path = workspace / "keywords" / "01_seedling_garden.csv"
    expected = [r.id for r in kw.due(kw.load(csv_path), today)]
    # 10월 글 중 성수기가 11월인 '김장배추 수확 시기'가 먼저, 시즌 지난 '마늘 심는 시기'는 빠짐
    assert expected[0] == "SG-098" and "SG-096" not in expected and "SG-001" in expected

    assert run("--today", "2026-11-04", "daily", "--engine", "template") == 0
    assert "초안 4편 완료" in capsys.readouterr().out
    for topic in ["seedling", "landscaping", "women_biz", "bmw"]:
        assert len(list((workspace / "drafts" / topic).glob("*.html"))) == 1
    assert list((workspace / "drafts" / "seedling").glob("*_SG-098_*.html"))
    statuses = {r.id: r.status for r in kw.load(csv_path)}
    assert statuses["SG-098"] == "draft" and statuses[expected[1]] == "todo"

    # 같은 날 다시 돌리면 다음 예정 키워드로 넘어감
    assert run("--today", "2026-11-04", "daily", "--topic", "seedling", "--engine", "template") == 0
    assert {r.id: r.status for r in kw.load(csv_path)}[expected[1]] == "draft"


def test_next_by_id_and_force(workspace, capsys):
    assert run("next", "--id", "LS-021", "--engine", "template") == 0
    files = list((workspace / "drafts" / "landscaping").glob("*LS-021*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "{지역}" not in text and "울산 조경업체" in text  # config.toml의 region
    assert run("next", "--id", "LS-021", "--engine", "template") == 1
    assert run("next", "--id", "LS-021", "--engine", "template", "--force") == 0


def test_done_skip_and_unknown_id(workspace, capsys):
    assert run("done", "BM-005", "--url", "https://blog.naver.com/x/1") == 0
    assert run("skip", "BM-006") == 0
    rows = kw.load(workspace / "keywords" / "04_bmw.csv")
    assert rows[4].status == "published" and rows[4].post_url.endswith("/1")
    assert rows[5].status == "skip"
    assert run("done", "XX-999") == 1
    assert "찾을 수 없습니다" in capsys.readouterr().out


def test_calendar_html(workspace):
    assert run("--today", "2026-11-04", "calendar", "--out", "cal.html") == 0
    page = (workspace / "cal.html").read_text(encoding="utf-8")
    assert page.count("<section>") == 12
    assert "11월 <span class=\"now\">이번 달</span>" in page
    assert "육묘장 사장이 알려주는 모종·텃밭" in page


def test_publish_requires_wordpress_and_blocks_unfilled(workspace, capsys, monkeypatch):
    assert run("next", "--id", "BM-001", "--engine", "template") == 0
    md = next((workspace / "drafts" / "bmw").glob("*BM-001*.md"))
    capsys.readouterr()

    # 네이버 주제는 복사·붙여넣기 안내
    assert run("publish", str(md)) == 1
    assert "붙여넣으세요" in capsys.readouterr().out

    # 워드프레스로 전환
    cfg = (workspace / "config.toml").read_text(encoding="utf-8")
    cfg = cfg.replace('platform = "naver"         # 워드프레스', 'platform = "wordpress"  # 워드프레스')
    cfg = cfg.replace('# wp_env_prefix = "WP_BMW"', 'wp_env_prefix = "WP_BMW"')
    (workspace / "config.toml").write_text(cfg, encoding="utf-8")

    posted = []

    class FakeWP:
        def create_post(self, title, content, **kw_):
            posted.append((title, content, kw_))
            return {"id": 5, "link": "https://wp.example/?p=5", "status": kw_["status"]}

    monkeypatch.setattr(cli.WordPressClient, "from_env", classmethod(lambda c, p: FakeWP()))

    # 채우지 않은 자리가 있으면 바로 발행은 막힘
    assert run("publish", str(md), "--status", "publish") == 1
    assert "멈췄습니다" in capsys.readouterr().out
    assert not posted

    # 임시글 업로드는 허용
    assert run("publish", str(md)) == 0
    assert posted[0][2]["status"] == "draft"
    assert "📷 사진" in posted[0][1]
    rows = kw.load(workspace / "keywords" / "04_bmw.csv")
    assert rows[0].post_url == "https://wp.example/?p=5" and rows[0].status == "draft"


def test_drafts_use_voice_greeting_and_center_align(workspace):
    assert run("next", "--id", "SG-041", "--engine", "template") == 0
    md = next((workspace / "drafts" / "seedling").glob("*SG-041*.md")).read_text(encoding="utf-8")
    assert "안녕하세요! 꼬몽맘입니다." in md
    page = next((workspace / "drafts" / "seedling").glob("*SG-041*.html")).read_text(encoding="utf-8")
    assert '<p style="text-align:center">' in page
    assert '<h1 style="text-align:center">' in page
