"""GitHub Actions용 요약·PR 코멘트 생성기 (표준 라이브러리만 사용).

`take_a_look audit`가 남긴 report.json을 읽어
- $GITHUB_STEP_SUMMARY에 보기 좋은 마크다운을 추가하고
- PR 컨텍스트에서는 같은 내용을 코멘트로 게시하거나 기존 코멘트를 갱신한다.

코멘트는 숨은 마커(<!-- take-a-look-pr-comment -->)로 찾으므로 커밋마다 새 코멘트가
쌓이지 않는다. 토큰이 없거나 PR 이벤트가 아니면(예: push) 요약만 남기고 조용히 끝난다.
외부 패키지를 쓰지 않으며, 비밀값은 출력하지 않는다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MARKER = "<!-- take-a-look-pr-comment -->"
GUIDE_URL = "https://github.com/sooyun79-droid/take-a-look/blob/main/docs/github-action.md"
API_VERSION = "2022-11-28"
USER_AGENT = "take-a-look-action"
MAX_ITEMS = 20
MAX_COMMENT_CHARS = 60000
STATUS_ORDER = ("CONFIRMED", "UNCONFIRMED", "REFUTED", "NEEDS_HUMAN")
STATUS_LABELS = {
    "CONFIRMED": ("🔴", "실제로 확인된 문제"),
    "UNCONFIRMED": ("🟡", "아직 확인하지 못한 의심"),
    "REFUTED": ("⚪", "문제가 아니었던 의심"),
    "NEEDS_HUMAN": ("👤", "사람이 판단할 항목"),
}


def _one_line(value, limit=400):
    """마크다운을 깨뜨리는 줄바꿈을 없애고 길이를 제한한다."""
    text = " ".join(str(value if value is not None else "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _code(value):
    """경로처럼 그대로 보여줄 값을 인라인 코드로 감싼다."""
    return "`" + str(value if value is not None else "?").replace("`", "'").replace("\n", " ") + "`"


def _clip(text, limit):
    return text if len(text) <= limit else text[: limit - 60] + "\n\n… (내용이 길어 일부만 표시했습니다)"


def find_report(location):
    """report.json 파일 또는 검사 결과 폴더에서 가장 최근 report.json을 찾는다."""
    path = Path(location).expanduser()
    if path.is_file():
        return path
    if not path.is_dir():
        return None
    candidates = [item for item in path.rglob("report.json") if item.is_file()]
    candidates = [item for item in candidates if not item.parent.name.startswith("failed-")]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.stat().st_mtime, len(item.parts)))


def load_report(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("verdicts"), list):
        raise ValueError("report.json 형식이 아닙니다")
    return data


def counts(report):
    result = {status: 0 for status in STATUS_ORDER}
    for verdict in report.get("verdicts") or []:
        status = str(verdict.get("status", "")).upper()
        if status in result:
            result[status] += 1
    return result


def findings(report):
    """claim과 verdict를 합쳐 보고용 항목으로 만든다."""
    claims = {}
    for claim in report.get("claims") or []:
        key = claim.get("id") or claim.get("claim_id")
        if key:
            claims[key] = claim
    rows = []
    for verdict in report.get("verdicts") or []:
        claim = claims.get(verdict.get("claim_id"), {})
        line = claim.get("line") or (claim.get("suspected_lines") or ["?"])[0]
        rows.append({
            "status": str(verdict.get("status", "")).upper(),
            "title": _one_line(claim.get("title") or "제목 없음", 200),
            "location": _code(f"{claim.get('file') or '?'}:{line}"),
            "method": _one_line(claim.get("method") or "", 200),
            "explanation": _one_line(verdict.get("explanation") or "", 400),
        })
    order = {status: index for index, status in enumerate(STATUS_ORDER)}
    rows.sort(key=lambda row: order.get(row["status"], len(order)))
    return rows


def decide_exit_code(report, audit_exit_code=0, fail_on_confirmed=False):
    """0 통과, 1 정책에 따른 결함 발견, 2 검사 미완료."""
    if report is None or audit_exit_code not in (0, 1) or (report.get('project') or {}).get('verification_status') == 'INCOMPLETE':
        return 2
    confirmed = counts(report)["CONFIRMED"]
    if audit_exit_code == 1 and not confirmed:
        return 2
    if confirmed:
        return 1 if fail_on_confirmed else 0
    return 0


def run_url(environ):
    server = (environ.get("GITHUB_SERVER_URL") or "").rstrip("/")
    repo = environ.get("GITHUB_REPOSITORY") or ""
    run_id = environ.get("GITHUB_RUN_ID") or ""
    if not (server and repo and run_id):
        return ""
    return f"{server}/{repo}/actions/runs/{run_id}"


def render_summary(report, limit=MAX_ITEMS):
    """Step Summary와 PR 코멘트에 함께 쓰는 마크다운 본문."""
    total = counts(report)
    rows = findings(report)
    claim_count = len(report.get("claims") or [])
    integrity = str((report.get("integrity") or {}).get("status") or "")

    lines = ["## 🐱 떼껄룩 검사 결과", "", "| 판정 | 개수 |", "| --- | ---: |"]
    for status in STATUS_ORDER:
        emoji, label = STATUS_LABELS[status]
        lines.append(f"| {emoji} {label} ({status}) | {total[status]} |")
    lines.append("")
    if total["CONFIRMED"]:
        lines.append(f"의심 {claim_count}건 가운데 {total['CONFIRMED']}건이 지원 범위에서 실제 문제로 확인됐습니다.")
    else:
        lines.append("현재 검사 범위에서는 실제 문제로 확인된 항목이 없습니다.")
    lines.append("")
    lines.append("의심 개수는 실제 문제 개수와 다릅니다. 확인된 문제가 0건이어도 전체 검증을 통과했다는 뜻이 아닙니다.")
    if integrity and integrity != "UNCHANGED":
        lines.append("")
        lines.append(f"⚠️ 검사 중 원본 파일 무결성 상태가 `{integrity}`로 바뀌었습니다. 결과를 신뢰하기 전에 확인하세요.")
    if (report.get('project') or {}).get('verification_status') == 'INCOMPLETE':
        lines.append("")
        lines.append("⚠️ 검사 미완료: Node/TypeScript 분석기가 없거나 실패했습니다. 아래 판정은 완료된 범위에만 해당하며 이 실행은 실패 코드 2로 끝납니다.")
    lines.append("")

    confirmed = [row for row in rows if row["status"] == "CONFIRMED"]
    if confirmed:
        lines.append(f"### 🔴 확인된 문제 {len(confirmed)}건")
        lines.append("")
        for index, row in enumerate(confirmed[:limit], start=1):
            lines.append(f"**{index}. {row['title']}**")
            lines.append("")
            detail = row["location"]
            if row["method"]:
                detail += f" · 검증 방법: {row['method']}"
            lines.append(detail)
            if row["explanation"]:
                lines.append("")
                lines.append(f"> {row['explanation']}")
            lines.append("")
        if len(confirmed) > limit:
            lines.append(f"나머지 {len(confirmed) - limit}건은 검사 실행의 report.html에서 확인하세요.")
            lines.append("")

    others = [row for row in rows if row["status"] != "CONFIRMED"]
    if others:
        hidden = [row for row in others if row["status"] != "REFUTED"]
        shown = (hidden + [row for row in others if row["status"] == "REFUTED"])[:limit]
        rest = len(others) - len(shown)
        summary_bits = " · ".join(
            f"{STATUS_LABELS[status][0]} {STATUS_LABELS[status][1]} {total[status]}건"
            for status in ("UNCONFIRMED", "REFUTED", "NEEDS_HUMAN") if total[status]
        )
        lines.append("<details><summary>그 밖의 판정 보기 — " + summary_bits + "</summary>")
        lines.append("")
        for row in shown:
            emoji = STATUS_LABELS.get(row["status"], ("·", ""))[0]
            lines.append(f"- {emoji} **{row['title']}** — {row['location']}")
            if row["explanation"]:
                lines.append(f"  - {row['explanation']}")
        if rest > 0:
            lines.append(f"- 그 밖에 {rest}건은 검사 실행의 report.html에서 확인하세요.")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    project = report.get("project") or {}
    coverage = _one_line(project.get("coverage") or "", 500)
    if coverage:
        lines.append("<details><summary>검사 범위와 실행 방식</summary>")
        lines.append("")
        lines.append(coverage)
        lines.append("")
        lines.append(f"실행 방식: `{project.get('execution_mode') or 'NO_EXECUTION'}`")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append(f"<sub>떼껄룩은 원본 코드를 수정하지 않습니다. 판정 기준은 [안내 문서]({GUIDE_URL})에 있습니다.</sub>")
    return "\n".join(lines)


def render_comment(report, environ):
    parts = [render_summary(report), ""]
    link = run_url(environ)
    if link:
        parts.append(f"[검사 실행 로그]({link}) · [떼껄룩 사용 안내]({GUIDE_URL})")
    else:
        parts.append(f"[떼껄룩 사용 안내]({GUIDE_URL})")
    parts.append(MARKER)
    return _clip("\n".join(parts), MAX_COMMENT_CHARS)


def _pr_number(environ):
    event_path = environ.get("GITHUB_EVENT_PATH") or ""
    payload = {}
    if event_path:
        try:
            payload = json.loads(Path(event_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = {}
    if isinstance(payload, dict):
        request = payload.get("pull_request")
        if isinstance(request, dict) and request.get("number"):
            return int(request["number"])
        issue = payload.get("issue")
        if isinstance(issue, dict) and issue.get("pull_request") and issue.get("number"):
            return int(issue["number"])
    ref = environ.get("GITHUB_REF") or ""
    if ref.startswith("refs/pull/"):
        head = ref.split("/")[2]
        if head.isdigit():
            return int(head)
    return None


def github_context(environ):
    """코멘트를 남길 수 있는 환경이면 필요한 값만 모아 돌려준다."""
    token = environ.get("GITHUB_TOKEN") or ""
    repo = environ.get("GITHUB_REPOSITORY") or ""
    number = _pr_number(environ)
    if not (token and repo and number and "/" in repo):
        return None
    return {
        "token": token,
        "repo": repo,
        "pr_number": number,
        "api_url": environ.get("GITHUB_API_URL") or "https://api.github.com",
    }


def _request(method, url, token, payload=None, timeout=20):
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", API_VERSION)
    request.add_header("User-Agent", USER_AGENT)
    if data is not None:
        request.add_header("Content-Type", "application/json; charset=utf-8")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw.strip() else {}


def upsert_comment(body, context, request=_request):
    """같은 마커를 가진 기존 코멘트가 있으면 갱신하고, 없으면 새로 만든다."""
    base = context["api_url"].rstrip("/")
    repo = context["repo"]
    number = context["pr_number"]
    token = context["token"]
    existing = None
    for page in range(1, 6):
        url = f"{base}/repos/{repo}/issues/{number}/comments?per_page=100&page={page}"
        items = request("GET", url, token)
        if not isinstance(items, list):
            break
        existing = next((item for item in items if MARKER in str(item.get("body") or "")), None)
        if existing or len(items) < 100:
            break
    if existing:
        request("PATCH", f"{base}/repos/{repo}/issues/comments/{existing['id']}", token, {"body": body})
        return "updated"
    request("POST", f"{base}/repos/{repo}/issues/{number}/comments", token, {"body": body})
    return "created"


def write_step_summary(text, environ):
    target = environ.get("GITHUB_STEP_SUMMARY") or ""
    if not target:
        return False
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(text.rstrip("\n") + "\n")
    except OSError:
        return False
    return True


def write_outputs(report_path, report, environ):
    target = environ.get("GITHUB_OUTPUT") or ""
    if not target:
        return False
    lines = [f"report-path={report_path}", f"confirmed={counts(report)['CONFIRMED']}"]
    try:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError:
        return False
    return True


def _flag(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


def _warn(message):
    print(f"::warning::{message}", file=sys.stderr)


def main(argv=None, environ=None):
    environ = dict(os.environ if environ is None else environ)
    parser = argparse.ArgumentParser(
        prog="take-a-look-reporter",
        description="떼껄룩 report.json을 GitHub Step Summary와 PR 코멘트로 내보냅니다.",
    )
    parser.add_argument("report", nargs="?", default=".", help="report.json 파일 또는 검사 결과 폴더")
    parser.add_argument("--audit-exit-code", type=int, default=0, help="검사 단계의 종료 코드 (0 정상, 1 결함, 2 미완료)")
    parser.add_argument("--comment-pr", default="true", help="PR 코멘트 작성 여부")
    parser.add_argument("--fail-on-confirmed", default="false", help="CONFIRMED가 있으면 실패로 처리할지 여부")
    args = parser.parse_args(argv)

    path = find_report(args.report)
    report = None
    if path is not None:
        try:
            report = load_report(path)
        except (OSError, ValueError):
            report = None

    if report is None:
        message = "떼껄룩 검사 결과(report.json)를 찾지 못했습니다. 검사 단계 로그를 확인하세요."
        write_step_summary(f"## 🐱 떼껄룩 검사 결과\n\n{message}\n", environ)
        print(message, file=sys.stderr)
        return 2

    summary = render_summary(report)
    write_step_summary(summary, environ)
    write_outputs(path, report, environ)
    print(summary)

    if _flag(args.comment_pr):
        context = github_context(environ)
        if context is None:
            print("PR 컨텍스트가 아니어서 코멘트는 남기지 않습니다.")
        else:
            try:
                state = upsert_comment(render_comment(report, environ), context)
                print(f"PR 코멘트를 {state}했습니다. (#{context['pr_number']})")
            except urllib.error.HTTPError as exc:
                _warn(f"PR 코멘트를 남기지 못했습니다 (HTTP {exc.code}). 포크 PR의 읽기 전용 토큰일 수 있습니다.")
            except (urllib.error.URLError, OSError, ValueError) as exc:
                _warn(f"PR 코멘트를 남기지 못했습니다 ({type(exc).__name__}).")

    code = decide_exit_code(report, audit_exit_code=args.audit_exit_code, fail_on_confirmed=_flag(args.fail_on_confirmed))
    if code == 1:
        print("CONFIRMED 판정이 있어 실패로 처리합니다. (fail-on-confirmed=true)", file=sys.stderr)
    elif code == 2:
        print("떼껄룩이 검사를 정상적으로 끝내지 못했습니다.", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
