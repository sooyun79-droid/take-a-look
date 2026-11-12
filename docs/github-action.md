# GitHub Action — PR 자동 검증

Cursor·Claude Code 같은 AI 도구로 만든 PR이 올라올 때, 떼껄룩이 CI 단계에서 한 번 더 봅니다. 결과는 워크플로의 **Step Summary**와 **PR 코멘트**에 남고, 사람이 읽기 전에 "이건 실제로 확인된 문제인지"를 먼저 알려줍니다.

- 판정은 떼껄룩과 같습니다: 🔴 CONFIRMED · 🟡 UNCONFIRMED · ⚪ REFUTED · 👤 NEEDS_HUMAN
- 원본 코드를 고치지 않습니다. 검사 중 파일을 바꾸지 않습니다.
- 별도 API 키나 pip 패키지가 필요 없습니다. 검사는 저장소 안에서만, 표준 라이브러리로 돕니다.

## 1. 워크플로 추가

내 저장소에 `.github/workflows/take-a-look.yml` 파일을 만들고 아래를 붙여넣습니다.

```yaml
name: Take a Look Audit
on: [pull_request]
permissions:
  contents: read
  pull-requests: write
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: sooyun79-droid/take-a-look@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

`permissions`의 `pull-requests: write`는 결과 코멘트를 남기는 데만 씁니다. 코멘트가 필요 없으면 이 줄과 `with:`를 지워도 됩니다(요약은 Step Summary에 그대로 남습니다).

안정적인 운영을 위해 `@main` 대신 커밋 SHA로 고정하는 편이 좋습니다. `@main`은 항상 최신 코드를 따라갑니다.

## 2. 무엇이 일어나나

1. `actions/setup-python`이 입력한 파이썬 버전(기본 3.11)을 준비합니다.
2. `python -B -m take_a_look audit <path> --output $RUNNER_TEMP/take-a-look-reports`를 실행합니다. 보고서는 체크아웃한 저장소 밖(러너 임시 폴더)에 만들어 원본 폴더를 건드리지 않습니다.
3. `tools/github_action_reporter.py`가 `report.json`을 읽어 Step Summary 마크다운을 쓰고, PR 이벤트면 코멘트를 남깁니다.
4. 같은 PR에서 다시 돌면 **같은 코멘트를 갱신**합니다(본문 끝의 숨은 표식으로 찾음). 커밋마다 코멘트가 쌓이지 않습니다.
5. `fail-on-confirmed` 정책에 따라 액션의 성공·실패를 정합니다.

코멘트에는 판정별 개수, 확인된 문제의 제목·파일:줄·검증 근거, 나머지 판정의 접은 목록, 검사 범위와 실행 로그 링크가 들어갑니다.

## 3. 입력값

| 이름 | 기본값 | 설명 |
| --- | --- | --- |
| `path` | `.` | 검사할 경로. 저장소 루트 기준 |
| `python-version` | `'3.11'` | 검사에 쓸 파이썬 버전 (3.11 이상) |
| `comment-pr` | `'true'` | PR 코멘트 작성 여부. `false`면 Step Summary만 남김 |
| `fail-on-confirmed` | `'true'` | 🔴 CONFIRMED가 있으면 액션 실패(종료 코드 1) |
| `github-token` | `${{ github.token }}` | 코멘트 API 호출용 토큰. 비밀값을 출력하지 않음 |

## 4. 출력값

| 이름 | 설명 |
| --- | --- |
| `report-path` | 생성된 `report.json`의 경로 |
| `confirmed` | CONFIRMED 판정 개수 |

```yaml
      - uses: sooyun79-droid/take-a-look@main
        id: take-a-look
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
      - run: echo "확인된 문제 ${{ steps.take-a-look.outputs.confirmed }}건"
```

보고서 HTML을 PR 산출물로 남기고 싶다면 `report-path`가 있는 폴더를 `actions/upload-artifact`로 올리면 됩니다.

## 5. 실패 정책과 종료 코드

| 상황 | 액션 결과 |
| --- | --- |
| CONFIRMED 0건 | 성공 (0) |
| CONFIRMED 1건 이상, `fail-on-confirmed: true` | 실패 (1) |
| CONFIRMED 1건 이상, `fail-on-confirmed: false` | 성공 (0), 코멘트에 결과만 기록 |
| 검사 미완료(경로 오류·무결성 변화 등) | 실패 (2) — 정책과 무관하게 실패 |

처음 도입할 때는 `fail-on-confirmed: false`로 결과만 보다가, 오탐이 없다고 확인되면 `true`로 바꾸는 편이 안전합니다.

```yaml
        with:
          fail-on-confirmed: false
```

검사가 끝나지 않은 경우(종료 코드 2)는 통과로 넘기지 않습니다. 검증을 못 한 것을 성공으로 표시하지 않는다는 떼껄룩의 원칙과 같습니다.

## 6. 알아둘 제한

- **포크에서 온 PR**: GitHub은 이 경우 `GITHUB_TOKEN`을 읽기 전용으로 줍니다. 코멘트 작성은 실패하고 워크플로 로그에 경고만 남기며, 검사 결과와 Step Summary는 정상입니다. 코멘트가 꼭 필요하면 `pull_request_target`을 검토해야 하는데, 그때는 체크아웃할 코드를 신뢰할 수 있는지 먼저 확인하세요.
- **검사 범위**: 떼껄룩은 Python 및 제한된 Node/TypeScript의 문법·경계값·방어 조건과 웹/이커머스 정적 규칙을 봅니다. 앱 전체 실행, 완전한 보안 감사, 자동 수정은 하지 않습니다. CONFIRMED 0건은 "이 범위에서 문제를 못 찾았다"는 뜻이며 전체 통과 보증이 아닙니다.
- **첫 실행 시간**: 파이썬 준비와 검사에 몇십 초가 걸립니다. 큰 저장소는 `path`로 폴더를 좁히면 빨라집니다.
- **비공개 저장소**: 공개 저장소의 액션을 그대로 쓸 수 있습니다. 액션 저장소가 비공개라면 해당 저장소에도 접근 권한이 있는 토큰이 필요합니다.

## 7. 직접 확인하기

액션 없이 같은 검사를 로컬에서 하려면 저장소 안에서 다음을 실행합니다.

```text
python -B -m take_a_look audit . --output ../take-a-look-reports
```

결과는 `../take-a-look-reports/<검사번호>/report.html`에 저장됩니다. 판정 기준과 보안 모델은 [README](../README.md)와 [기술 범위](architecture.md)를 참고하세요.
