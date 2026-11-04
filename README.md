# blog-autopost

4개 블로그 주제의 **월별 키워드 캘린더(주제당 100개, 총 400개)** 와, 캘린더를 따라 매일 **글 초안을 자동으로 만들어 주는 도구**입니다.

| 주제 | 파일 | 키워드 | 수익 연결 |
|---|---|---|---|
| 육묘장 사장이 알려주는 모종·텃밭 | `keywords/01_seedling_garden.csv` | 100 | 쿠팡 파트너스(상토·비료·모종), 애드포스트 |
| 마당·전원주택 조경 가이드 | `keywords/02_landscaping.csv` | 100 | **시공 문의(본업)**, 쿠팡, 애드센스 |
| 여성 대표의 관급공사·여성기업 실전기 | `keywords/03_women_biz_public.csv` | 100 | 세무·금융 계열 고단가 광고 |
| BMW 오너의 실사용 관리 기록 | `keywords/04_bmw.csv` | 100 | 보험·리스 고단가 광고, 차량용품 |

캘린더는 **11월부터 시작해 1년(12개월)** 을 돌고, 해마다 같은 달에 다시 쓸 수 있습니다. 검색 성수기보다 1~2달 **먼저 발행**하도록 배치했습니다. 예를 들어 "고추 모종 심는 시기"는 검색이 5월에 가장 많아서 4월에 발행하도록 넣었습니다.

## 키워드 캘린더 보는 법

CSV 파일은 엑셀이나 구글 시트에서 바로 열립니다. GitHub에서 열어도 표로 보입니다.

| 열 | 뜻 |
|---|---|
| `id` | 키워드 번호 (SG=모종, LS=조경, WB=여성기업, BM=BMW) |
| `month`, `week` | 발행할 달과 주차 (1~4주) |
| `keyword` / `title` | 핵심 검색어 / 제목 아이디어 |
| `intent` | 검색 의도: 정보·문제해결·비교·구매·비용·경험 (초안 구조가 달라짐) |
| `peak_month` | 검색이 가장 많은 달 |
| `priority` | A(꼭 쓸 것) / B / C |
| `monetize` | 수익 연결 (`쿠팡:상품`이면 쿠팡 파트너스 고지 문구가 자동으로 붙음) |
| `status` | `todo`(예정) → `draft`(초안) → `published`(발행), `skip`(건너뜀) |
| `memo` | **내 경험 메모.** 여기에 쓴 내용이 초안에 들어갑니다. 예: "작년 4월 20일 심었다가 냉해, 사진 있음" |
| `post_url` | 발행한 글 주소 |

키워드는 자유롭게 고치거나 줄을 추가해도 됩니다. 엑셀에서 저장할 때는 **CSV UTF-8** 형식을 선택하세요.

`{지역}`이 들어간 키워드(조경 4개)는 `config.toml`의 `region`에 적은 지역명으로 바뀝니다.

## 처음 설정 (한 번만)

Python 3.11 이상이 필요합니다.

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

그다음 `config.toml`을 열어 `region`(지역명)과 주제별 `persona`(나를 소개하는 문장)를 내 상황에 맞게 고치세요. 초안의 목소리가 여기서 정해집니다.

## 매일 쓰는 법

```bash
python -m blog_autopost daily
```

캘린더에서 **이번 주까지 예정된 키워드**를 주제마다 1개씩 골라 초안을 만듭니다. 지난달에 못 쓴 글은 검색 시즌이 아직 남은 것만 이어서 고릅니다. 초안은 `drafts/<주제>/` 폴더에 두 파일로 저장됩니다.

- `.html`: 브라우저로 열어 **[본문 복사하기]** 를 누른 뒤 네이버 블로그 에디터에 붙여넣으세요.
- `.md`: 원문 기록용이자 워드프레스 발행용입니다.

초안에는 색깔로 표시된 자리가 있습니다. **발행 전에 모두 채우거나 지우세요.**

| 표시 | 할 일 |
|---|---|
| 📷 사진 | 직접 찍은 사진 넣기 |
| ✍️ 경험 추가 | 내 경험 쓰기 (검색 상위 노출의 핵심) |
| ⚠️ 확인 필요 | 가격·제도·날짜를 확인해서 쓰기 |
| 🔗 제휴 | 쿠팡 파트너스 링크 넣기 |

발행한 뒤에는 완료로 표시합니다.

```bash
python -m blog_autopost done SG-098 --url https://blog.naver.com/내아이디/글번호
```

### 그 밖의 명령

| 명령 | 하는 일 |
|---|---|
| `python -m blog_autopost list` | 이번 달 키워드 보기 (`--topic seedling`, `--month 4`) |
| `python -m blog_autopost stats` | 주제별 예정/초안/발행 개수 |
| `python -m blog_autopost next --topic bmw -n 3` | 시간이 남을 때 다음 키워드 3개를 미리 초안으로 |
| `python -m blog_autopost next --id WB-002` | 특정 키워드로 초안 만들기 |
| `python -m blog_autopost skip LS-055` | 이 키워드 건너뛰기 |
| `python -m blog_autopost calendar` | 1년 캘린더를 `calendar.html`로 만들기 |

주제 키: `seedling`(모종·텃밭), `landscaping`(조경), `women_biz`(여성기업·관급), `bmw`

## 초안 방식 두 가지

| 방식 | 설정 | 결과 | 비용 |
|---|---|---|---|
| `template` (기본) | 설정 없음 | 소제목·사진 자리·경험 자리·FAQ 뼈대. 내용은 직접 씀 | 무료 |
| `claude` | API 키 필요 | Claude가 2,000~3,000자 초안을 씀. 경험과 확인이 필요한 곳은 표시만 남김 | 사용량만큼 |

Claude 방식을 쓰려면 [Claude Console](https://platform.claude.com)에서 API 키를 발급받으세요. `.env.example`을 `.env`로 복사해 `ANTHROPIC_API_KEY`를 적고, `config.toml`의 `engine`을 `"claude"`로 바꾸면 됩니다. 한 번만 써 보려면 `--engine claude`를 붙여도 됩니다.

Claude 초안도 **반드시 검토 후 발행**하세요. 프롬프트에서 경험담이나 수치를 지어내지 말라고 지시해 두었지만, 사실 확인과 실제 사진·경험 추가는 사람이 해야 합니다. 검색엔진은 직접 겪은 내용이 담긴 글을 우대하고, 검토 없이 찍어낸 글은 노출이 떨어질 수 있습니다.

## 블로그 플랫폼별 발행

- **네이버 블로그:** 공식 글쓰기 API가 없어 자동 업로드는 하지 않습니다. `.html` 초안을 복사해 붙여넣으세요. 자동화 프로그램으로 네이버에 올리면 계정 제재 위험이 있습니다.
- **워드프레스:** 임시글로 자동 업로드할 수 있습니다.
  1. 워드프레스 관리자 > 사용자 > 프로필 > **응용 프로그램 비밀번호**를 발급합니다.
  2. `config.toml`의 해당 주제를 `platform = "wordpress"`, `wp_env_prefix = "WP_BMW"`처럼 바꿉니다.
  3. `.env`에 `WP_BMW_URL`, `WP_BMW_USER`, `WP_BMW_APP_PASSWORD`를 적습니다.
  4. `daily --upload`를 실행하면 초안이 워드프레스 **임시글**로 올라갑니다. 검토한 `.md`를 발행하려면 아래 명령을 씁니다.

     ```bash
     python -m blog_autopost publish drafts/bmw/파일이름.md --status publish
     ```

     채우지 않은 표시가 남아 있으면 발행을 멈춥니다. 예약 발행은 `--status future --date 2026-11-10T07:00:00`처럼 씁니다.

## GitHub에서 매일 자동 실행 (선택)

`.github/workflows/daily-drafts.yml`이 들어 있습니다. 처음에는 수동 실행만 켜져 있습니다.

1. 저장소 Settings > Secrets and variables > Actions에 `ANTHROPIC_API_KEY`를 등록합니다. 등록하지 않으면 무료 뼈대 초안을 만듭니다. 워드프레스를 쓴다면 `WP_BMW_*`도 등록합니다.
2. Actions > daily-drafts > Run workflow로 한 번 실행해 봅니다.
3. 매일 자동으로 돌리려면 워크플로 파일의 `schedule` 두 줄에서 주석(`#`)을 지웁니다. 매일 오전 6시 17분(한국 시간)에 실행됩니다.

## 개발

```bash
pip install -r requirements-dev.txt
```

```bash
python -m pytest
```
