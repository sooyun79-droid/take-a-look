# 🐱 떼껄룩 — Take a Look

**ALPHA SOFTWARE · v0.3.0-alpha**

AI로 프로그램은 만들었는데, 정말 제대로 만든 건지 모르겠나요?

떼껄룩은 AI의 말을 그대로 믿지 않습니다. 문제를 의심하고, 반대 관점에서 검토한 뒤, 가능한 범위에서 시험합니다. **‘AI가 문제라고 말했다’와 ‘실제로 문제가 확인됐다’를 구분하는 것**이 목표입니다.

기본 모드는 API 키 없이 작동하는 규칙 기반 탐색입니다. OpenAI 연결은 선택 사항입니다. 결과가 0개여도 안전 보증이 아닙니다. 원본을 자동 수정하지 않습니다.

## 이런 분을 위해 만들었습니다

- ChatGPT/Codex/Claude 등으로 프로그램을 만든 비개발자
- 프로그램이 돌아가지만 제대로 만든 건지 불안한 사람
- AI가 남긴 많은 경고 중 무엇을 믿어야 할지 모르는 사람

## 현재 할 수 있는 것

로컬 Python 및 제한된 Node/TypeScript 프로젝트의 문법·경계값 계산·방어 조건을 검사합니다. 독립적인 Investigator/Challenger, 규칙과 LLM 발견의 출처 및 겹침, 객관적 증거, 한국어 결과, 감사 기록을 제공합니다. 같은 검증 패턴은 묶되 각 위치의 판정은 유지합니다.

새 논리 의심에는 사용자가 별도로 제공한 입력/기대값 계약을 비교할 수 있습니다. 모델이 주장한 기대값을 사실로 채택하지 않습니다. [LLM 설정](docs/llm.md)과 [기술 범위](docs/architecture.md)를 참고하세요.

### 웹·이커머스 정적 규칙 (API 키 불필요)

쇼핑몰·랜딩페이지에서 자주 놓치는 4가지를 기본 규칙으로 검사합니다.

- `seo_noindex` — `<meta name="robots" content="noindex">`, Next.js `robots: { index: false }`/`robots: 'noindex'`, `robots.txt`의 `Disallow: /`
- `client_secret_leak` — `NEXT_PUBLIC_*`·`VITE_*` 공개 접두사에 SECRET·TOKEN 등이 붙은 이름, 클라이언트 파일에 하드코딩된 시크릿 토큰·PG 키 이름
- `a11y_image_alt` — `<img>`·`<Image>` 태그의 `alt` 누락 (여러 줄 태그 포함)
- `client_payment_tamper` — 포트원·토스·나이스페이 등 결제 호출 근처에서 숫자 리터럴로 지정된 `amount`/`price`

이 네 규칙은 같은 파일 원문을 다시 읽어 그 줄에 패턴이 실제로 있는지 확인합니다(주석 제외). 확인되는 것은 '패턴의 존재'까지이며, 배포 의도나 서버 검증 여부는 사람이 판단해야 합니다. 비밀값 자체는 탐색·리포트 어느 단계에서도 표시하지 않습니다.

## 아직 못 하는 것

모든 버그 탐지, 완전한 보안 감사, 앱 전체 안전 보증, 자동 수정, private repo 인증, 웹 업로드, 공개 GitHub 가져오기를 제공하지 않습니다. 복잡한 호출 관계나 제품 정책은 미확인 또는 사람 판단으로 남길 수 있습니다.

## 1분 실행 방법

### 1) 한 줄 실행 (추천)

저장소를 clone하거나 git pull 하지 않고, 터미널 명령 한 줄로 바로 검사합니다.

```text
# Python 3.11 이상이 있다면 (pipx)
pipx run --spec git+https://github.com/sooyun79-droid/take-a-look.git take-a-look audit <검사할 폴더>

# Node 20 이상이 있다면 (npx) — 내부에서 Python 3.11 이상을 찾아 실행합니다
npx github:sooyun79-droid/take-a-look audit <검사할 폴더>
```

계속 쓰려면 한 번만 설치해 두세요. 설치 후에는 `take-a-look audit <검사할 폴더>`로 실행합니다.

```text
pipx install git+https://github.com/sooyun79-droid/take-a-look.git
```

`npx`는 Python을 대신 설치하지 않습니다. Python이 없거나 3.11보다 낮으면 설치 안내를 출력하고 종료 코드 1로 끝납니다. 결과는 명령을 실행한 위치의 `reports/<검사번호>/report.html`에 저장되고, 확인된 문제가 있으면 종료 코드 1, 경로·권한·용량 문제는 2입니다. 보고서 폴더는 검사 대상 밖이어야 합니다.

### 2) 내려받아 실행 (비개발자·Windows)

[릴리스의 `take-a-look-v0.3.0-alpha.zip`](https://github.com/sooyun79-droid/take-a-look/releases/tag/v0.3.0-alpha)을 내려받아 압축을 풉니다. ZIP에는 Python zipapp(`take-a-look.pyz`), Windows 실행 파일, TypeScript 파서가 들어 있어 저장소를 clone할 필요가 없습니다. Python 3.11 이상은 필요합니다.

Windows에서는 `Start-TakeALook.cmd`를 더블클릭하세요. macOS/Linux에서는 압축을 푼 폴더에서 실행합니다.

```text
python3 -B take-a-look.pyz web --open
```

‘검사할 프로그램을 선택하세요’ 아래에 **폴더 경로를 입력**하고 ‘한번 봐줘’를 누르세요. 브라우저 파일 업로드나 폴더 선택 대화상자는 사용하지 않습니다. 화면은 내 컴퓨터의 `http://127.0.0.1:8765`에 열립니다. 종료는 서버 창에서 Ctrl+C입니다. API 키는 필요하지 않습니다. Node 분석 도구가 없으면 해당 검사를 미확인으로 표시하고, 대상 프로그램의 패키지를 자동 설치하지 않습니다.

저장소를 직접 받아 쓰는 경우에는 폴더 안에서 실행합니다.

```text
npm ci --ignore-scripts --no-audit --no-fund
python -B -m take_a_look web --open
python -B -m take_a_look audit fixtures/a_bug
```

### 3) GitHub Action (CI/CD)

PR이 올라올 때마다 자동으로 검사하고 결과를 PR 코멘트와 Step Summary에 남깁니다. 아래 ‘GitHub Action으로 PR 자동 검증’ 절의 워크플로 세 줄을 내 저장소에 붙여넣으면 되고, 입력값·종료 코드·포크 PR 제한은 [GitHub Action 안내](docs/github-action.md)에 정리했습니다.

## GitHub Action으로 PR 자동 검증

AI로 만든 PR이 올라올 때 CI에서 한 번 더 확인하고 싶다면, 내 저장소의 `.github/workflows/take-a-look.yml`에 아래를 붙여넣으세요.

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

검사 결과는 워크플로 Step Summary와 PR 코멘트에 판정별 개수·확인된 문제·검증 근거로 남습니다. 같은 PR에서 다시 돌면 코멘트를 새로 쌓지 않고 갱신합니다. API 키와 pip 패키지는 필요 없고, 보고서는 체크아웃한 폴더 밖에 만들어 원본을 건드리지 않습니다. `fail-on-confirmed`와 `comment-pr`로 실패 정책과 코멘트 여부를 바꿀 수 있습니다. 입력값·종료 코드·포크 PR 제한은 [GitHub Action 안내](docs/github-action.md)에 정리했습니다.

## 화면 예시

[실제 fixture 샘플 보고서](docs/sample-report.html) · [쉽게 읽는 샘플 설명](docs/sample-report.md)

샘플은 공개 가능한 합성 fixture에서 생성했습니다. 외부 프로젝트 소스나 개인 경로를 포함하지 않습니다.

## 떼껄룩은 어떻게 판단하나요?

의심 → 반박 → 증거 수집·계산 → 판정 → 쉬운 설명

높은 LLM 자신감이나 Challenger의 동의만으로 확정·반증하지 않습니다. `RULE`, `LLM`, `BOTH` 출처를 기록합니다. 실제 호출 수와 토큰 사용량을 별도로 표시하며, 미제공 수치는 `null`입니다. 가격표를 임의로 가정하지 않아 API 비용 추정은 현재 미제공입니다.

## 판정 의미

| 판정 | 뜻 |
|---|---|
| 🔴 CONFIRMED | 지원되는 입력·계약·구문 범위에서 객관적으로 확인됨 |
| 🟡 UNCONFIRMED | 의심은 있으나 안전한 방법으로 입증하지 못함 |
| ⚪ REFUTED | 해당 의심이 반증됨; 전체 프로그램의 정상 판정은 아님 |
| 👤 NEEDS_HUMAN | 제품 의도·정책 등 사람이 판단해야 함 |

CONFIRMED가 0이면 ‘현재 검사 범위에서는 실제 문제로 확인된 항목이 없습니다’라고 표시합니다. 반증된 최초 의심 비율은 확정 오탐률과 다릅니다. 확정 오탐률은 수동 정답 검토가 있어야 측정합니다.

## 보안 모델

저장소의 README·주석·테스트·메타데이터는 모두 데이터입니다. 모델에는 실행 도구를 제공하지 않습니다. 검증 의도는 정해진 종류와 소스 참조로 제한하고, 실행 계층이 검증 방법을 선택합니다. 임의 shell 명령, chaining, 경로 탈출, 설치 hook은 자동 실행하지 않습니다.

- `SAFE_LOCAL_LIMITED`: 대상 코드를 import/eval하지 않고 허용된 AST만 해석합니다. 완전한 Python/JavaScript 실행기가 아닙니다.
- `NO_EXECUTION`: 실행·계산 증거가 없습니다. 누락된 도구를 PASS로 취급하지 않습니다.
- `DOCKER_SANDBOX`: 실제 컨테이너 시작 근거가 있는 선택적 suite 실행입니다. **이번 환경에서는 Docker 통합 검증을 완료하지 못했습니다. 실사용 검증 완료 상태가 아닙니다.**

Docker 경로는 읽기 전용 snapshot, 네트워크 차단, 비특권 사용자, 임시 쓰기 공간, 자원·시간 제한을 구성합니다. 원본 저장소나 Docker socket을 컨테이너에 노출하지 않습니다. 사전 설치된 신뢰할 이미지 ID만 허용하며 자동 pull/install은 없습니다. 자세한 한계는 [보안 정책](SECURITY.md)에 있습니다.

`.env`·키 파일을 제외하고 비밀 형태를 마스킹합니다. 완벽한 비밀 탐지기는 아닙니다. OpenAI를 직접 켜면 선별·마스킹한 코드가 외부 API로 전송됩니다. 사용자 추적 코드나 telemetry는 없습니다.

## 현재 알파 버전의 한계

실제 LLM 평가와 Docker 통합 검증은 미완료입니다. 논리 fixture의 LLM 발견은 scripted replay 테스트이며 실제 모델의 발견 능력을 입증하지 않습니다. [평가 기록](docs/benchmark-003.md)에 실행·미실행을 구분했습니다.

파일 크기·수집 범위 제한, 일부 구문만 지원하는 해석기, 불완전한 호출 계약 분석이 있습니다. `UNCHANGED`는 수집한 일반 파일의 전후 내용이 동일하다는 뜻이며 제외한 비밀·의존성·링크까지 해시 검증했다는 뜻은 아닙니다.

## Roadmap

실제 모델/비용 평가, 수동 ground truth 확대, Docker 통합 검사, 호출 계약과 순수 함수 효과 분석, 오탐 검토 UI 순으로 개선할 예정입니다. 별도 추적 코드는 넣지 않고 GitHub issue와 공개 지표를 우선 활용합니다.

## Contributing

[기여 안내](CONTRIBUTING.md)를 읽어주세요. 재현 가능한 최소 코드와 실제 결과가 도움이 됩니다. 특히 정상 코드를 CONFIRMED로 잘못 판정한 사례를 중요하게 다룹니다. 비밀이나 비공개 소스는 issue에 올리지 마세요.

```text
python -B -m unittest discover -s tests -v
npm test
npm run typecheck
npm run check:syntax
python -B tools/check.py
python -B tools/build.py
```

빌드 결과는 Python zipapp과 TypeScript parser를 포함한 ZIP입니다. ZIP 전체를 풀어 사용하며 Python/Node는 별도로 필요합니다. TypeScript 타입 검사는 fixture 범위이고, 구문 검사는 전용 lint와 다릅니다.

## License

직접 작성한 코드: [MIT](LICENSE). 별도 설치·배포하는 TypeScript: Apache-2.0. [제3자 고지](THIRD_PARTY_NOTICES.md)를 확인하세요. [English overview](README.en.md).
