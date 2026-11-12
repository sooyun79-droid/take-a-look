"""2단계 GitHub Action용 요약·PR 코멘트 리포트와 action.yml 구성 테스트."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import github_action_reporter as reporter

ROOT = Path(__file__).resolve().parents[1]


def make_report(confirmed=1, refuted=0, unconfirmed=0, needs_human=0):
    counts = {
        "CONFIRMED": confirmed,
        "REFUTED": refuted,
        "UNCONFIRMED": unconfirmed,
        "NEEDS_HUMAN": needs_human,
    }
    claims, verdicts = [], []
    for status, count in counts.items():
        for index in range(count):
            claim_id = f"C-{status.lower()}-{index}"
            claims.append({
                "id": claim_id,
                "rule": "boundary_division",
                "file": f"src/{status.lower()}_{index}.py",
                "line": 7 + index,
                "title": f"{status} 항목 {index}",
                "method": "지정 경계값에 대한 함수 본문 계산",
            })
            verdicts.append({
                "claim_id": claim_id,
                "status": status,
                "explanation": f"{status} 근거 {index}: 3회 모두 같은 결과였습니다.",
                "evidence_ids": [f"E-{claim_id}"],
            })
    return {
        "run_id": "run-fixture",
        "project": {"coverage": "Python 제한 검사", "execution_mode": "SAFE_LOCAL_LIMITED"},
        "claims": claims,
        "verdicts": verdicts,
        "integrity": {"status": "UNCHANGED"},
    }


class SummaryTests(unittest.TestCase):
    def test_summary_shows_every_count_and_confirmed_details(self):
        text = reporter.render_summary(make_report(confirmed=2, refuted=1, needs_human=1))
        for status in ("CONFIRMED", "UNCONFIRMED", "REFUTED", "NEEDS_HUMAN"):
            self.assertIn(f"({status})", text)
        self.assertIn("🔴 실제로 확인된 문제 (CONFIRMED) | 2", text)
        self.assertIn("⚪ 문제가 아니었던 의심 (REFUTED) | 1", text)
        self.assertIn("👤 사람이 판단할 항목 (NEEDS_HUMAN) | 1", text)
        self.assertIn("### 🔴 확인된 문제 2건", text)
        self.assertIn("**1. CONFIRMED 항목 0**", text)
        self.assertIn("`src/confirmed_0.py:7`", text)
        self.assertIn("검증 방법: 지정 경계값에 대한 함수 본문 계산", text)
        self.assertIn("> CONFIRMED 근거 0: 3회 모두 같은 결과였습니다.", text)
        self.assertIn("의심 4건 가운데 2건이 지원 범위에서 실제 문제로 확인됐습니다.", text)

    def test_summary_without_confirmed_states_there_is_none(self):
        text = reporter.render_summary(make_report(confirmed=0, refuted=2, unconfirmed=1))
        self.assertIn("현재 검사 범위에서는 실제 문제로 확인된 항목이 없습니다.", text)
        self.assertNotIn("### 🔴", text)
        self.assertIn("🔴 실제로 확인된 문제 (CONFIRMED) | 0", text)
        self.assertIn("그 밖의 판정 보기", text)

    def test_summary_on_empty_report_has_no_details_blocks(self):
        report = make_report(confirmed=0)
        report["claims"], report["verdicts"] = [], []
        text = reporter.render_summary(report)
        self.assertIn("현재 검사 범위에서는 실제 문제로 확인된 항목이 없습니다.", text)
        self.assertNotIn("<details><summary>그 밖의 판정 보기", text)

    def test_summary_warns_when_integrity_changed(self):
        report = make_report()
        report["integrity"] = {"status": "CHANGED"}
        self.assertIn("무결성 상태가 `CHANGED`", reporter.render_summary(report))

    def test_long_confirmed_list_is_capped(self):
        text = reporter.render_summary(make_report(confirmed=25), limit=20)
        self.assertIn("나머지 5건은", text)
        self.assertNotIn("**21.", text)


class CommentTests(unittest.TestCase):
    environ = {
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "sooyun79-droid/take-a-look",
        "GITHUB_RUN_ID": "123456",
    }

    def test_comment_body_has_hidden_marker_and_run_link(self):
        body = reporter.render_comment(make_report(), self.environ)
        self.assertTrue(body.rstrip().endswith(reporter.MARKER))
        self.assertIn("[검사 실행 로그](https://github.com/sooyun79-droid/take-a-look/actions/runs/123456)", body)
        self.assertIn(reporter.GUIDE_URL, body)
        self.assertIn("### 🔴 확인된 문제 1건", body)

    def test_comment_without_run_context_keeps_guide_link_only(self):
        body = reporter.render_comment(make_report(), {})
        self.assertNotIn("검사 실행 로그", body)
        self.assertIn(reporter.GUIDE_URL, body)

    def test_comment_is_length_limited(self):
        body = reporter.render_comment(make_report(confirmed=40), self.environ)
        self.assertLessEqual(len(body), reporter.MAX_COMMENT_CHARS)


class ExitCodeTests(unittest.TestCase):
    def test_confirmed_fails_when_policy_is_true(self):
        self.assertEqual(reporter.decide_exit_code(make_report(confirmed=1)), 1)
        self.assertEqual(reporter.decide_exit_code(make_report(confirmed=1), fail_on_confirmed=False), 0)

    def test_clean_report_passes(self):
        self.assertEqual(reporter.decide_exit_code(make_report(confirmed=0, refuted=1)), 0)
        self.assertEqual(reporter.decide_exit_code(make_report(confirmed=1), fail_on_confirmed=False), 0)

    def test_incomplete_audit_always_fails(self):
        self.assertEqual(reporter.decide_exit_code(make_report(confirmed=0), audit_exit_code=2), 2)
        self.assertEqual(reporter.decide_exit_code(None), 2)
        self.assertEqual(reporter.decide_exit_code(make_report(confirmed=0), audit_exit_code=1, fail_on_confirmed=False), 0)


class ReportLocationTests(unittest.TestCase):
    def test_find_report_picks_newest_run_folder_and_skips_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            older = root / "aaa"
            newer = root / "bbb"
            failed = root / "failed-ccc"
            for index, folder in enumerate((older, newer, failed)):
                folder.mkdir()
                path = folder / "report.json"
                path.write_text(json.dumps(make_report()), encoding="utf-8")
            os.utime(older / "report.json", (1_700_000_000, 1_700_000_000))
            os.utime(newer / "report.json", (1_700_000_500, 1_700_000_500))
            os.utime(failed / "report.json", (1_700_000_900, 1_700_000_900))
            self.assertEqual(reporter.find_report(newer / "report.json"), newer / "report.json")
            self.assertEqual(reporter.find_report(root), newer / "report.json")

    def test_find_report_returns_none_when_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(reporter.find_report(Path(directory)))
            self.assertIsNone(reporter.find_report(Path(directory) / "nope"))


class ContextTests(unittest.TestCase):
    def test_pull_request_event_gives_pr_number(self):
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory) / "event.json"
            event.write_text(json.dumps({"pull_request": {"number": 42}}), encoding="utf-8")
            environ = {
                "GITHUB_TOKEN": "token-value",
                "GITHUB_REPOSITORY": "sooyun79-droid/take-a-look",
                "GITHUB_EVENT_PATH": str(event),
            }
            context = reporter.github_context(environ)
        self.assertEqual(context["pr_number"], 42)
        self.assertEqual(context["api_url"], "https://api.github.com")
        self.assertEqual(context["token"], "token-value")

    def test_issue_comment_event_counts_only_on_pull_request(self):
        with tempfile.TemporaryDirectory() as directory:
            event = Path(directory) / "event.json"
            event.write_text(json.dumps({"issue": {"number": 9}}), encoding="utf-8")
            plain = {
                "GITHUB_TOKEN": "t",
                "GITHUB_REPOSITORY": "o/r",
                "GITHUB_EVENT_PATH": str(event),
            }
            self.assertIsNone(reporter.github_context(plain))
            event.write_text(json.dumps({"issue": {"number": 9, "pull_request": {"url": "x"}}}), encoding="utf-8")
            self.assertEqual(reporter.github_context(plain)["pr_number"], 9)

    def test_push_event_without_token_has_no_context(self):
        self.assertIsNone(reporter.github_context({"GITHUB_REF": "refs/heads/main", "GITHUB_TOKEN": "t"}))
        self.assertIsNone(reporter.github_context({"GITHUB_REF": "refs/pull/5/merge"}))
        self.assertEqual(
            reporter.github_context({"GITHUB_REF": "refs/pull/5/merge", "GITHUB_TOKEN": "t", "GITHUB_REPOSITORY": "o/r"})["pr_number"],
            5,
        )


class UpsertTests(unittest.TestCase):
    context = {
        "token": "secret-token",
        "repo": "sooyun79-droid/take-a-look",
        "pr_number": 12,
        "api_url": "https://api.github.com",
    }

    def test_existing_comment_is_updated(self):
        calls = []

        def fake(method, url, token, payload=None):
            calls.append((method, url, payload))
            if method == "GET":
                return [{"id": 1, "body": "무관한 코멘트"}, {"id": 99, "body": "이전 결과\n" + reporter.MARKER}]
            return {}

        state = reporter.upsert_comment("새 본문", self.context, request=fake)
        self.assertEqual(state, "updated")
        self.assertEqual(calls[-1][0], "PATCH")
        self.assertTrue(calls[-1][1].endswith("/repos/sooyun79-droid/take-a-look/issues/comments/99"))
        self.assertEqual(calls[-1][2], {"body": "새 본문"})
        self.assertNotIn("secret-token", calls[-1][1])

    def test_comment_is_created_when_marker_absent(self):
        calls = []

        def fake(method, url, token, payload=None):
            calls.append((method, url, payload))
            return [{"id": 1, "body": "무관한 코멘트"}] if method == "GET" else {}

        state = reporter.upsert_comment("새 본문", self.context, request=fake)
        self.assertEqual(state, "created")
        self.assertEqual(calls[-1][0], "POST")
        self.assertTrue(calls[-1][1].endswith("/repos/sooyun79-droid/take-a-look/issues/12/comments"))
        self.assertEqual(calls[-1][2], {"body": "새 본문"})


class MainTests(unittest.TestCase):
    def test_main_writes_step_summary_and_returns_policy_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "reports" / "run1"
            run.mkdir(parents=True)
            (run / "report.json").write_text(json.dumps(make_report()), encoding="utf-8")
            summary = root / "summary.md"
            output = root / "output.txt"
            environ = {
                "GITHUB_STEP_SUMMARY": str(summary),
                "GITHUB_OUTPUT": str(output),
                "GITHUB_REF": "refs/heads/main",
            }
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = reporter.main([str(root / "reports")], environ=environ)
            text = summary.read_text(encoding="utf-8")
            outputs = output.read_text(encoding="utf-8")
        self.assertEqual(code, 1)
        self.assertIn("떼껄룩 검사 결과", text)
        self.assertIn("### 🔴 확인된 문제 1건", text)
        self.assertIn("report-path=", outputs)
        self.assertIn("confirmed=1", outputs)

    def test_main_passes_when_policy_allows_confirmed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "report.json").write_text(json.dumps(make_report()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = reporter.main([str(root / "report.json"), "--fail-on-confirmed", "false"], environ={})
        self.assertEqual(code, 0)

    def test_main_reports_missing_report_as_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary.md"
            environ = {"GITHUB_STEP_SUMMARY": str(summary)}
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = reporter.main([directory], environ=environ)
            text = summary.read_text(encoding="utf-8")
        self.assertEqual(code, 2)
        self.assertIn("찾지 못했습니다", text)

    def test_comment_failure_does_not_hide_audit_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "report.json").write_text(json.dumps(make_report(confirmed=0)), encoding="utf-8")
            environ = {
                "GITHUB_TOKEN": "t",
                "GITHUB_REPOSITORY": "o/r",
                "GITHUB_REF": "refs/pull/3/merge",
            }
            with patch.object(reporter, "upsert_comment", side_effect=OSError("network down")), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                code = reporter.main([str(root)], environ=environ)
        self.assertEqual(code, 0)


class ActionManifestTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "action.yml").read_text(encoding="utf-8")

    def test_identity_and_composite_runs(self):
        self.assertIn("name: Take a Look - AI Code Verifier", self.text)
        self.assertIn(
            "description: Proves or refutes suspected bugs in AI-generated code before human review",
            self.text,
        )
        self.assertIn("using: composite", self.text)
        self.assertIn("actions/setup-python@v5", self.text)
        self.assertIn("python -B -m take_a_look audit", self.text)
        self.assertIn("tools/github_action_reporter.py", self.text)

    def test_inputs_have_required_defaults(self):
        for line in (
            "  path:\n",
            "  python-version:\n",
            "  comment-pr:\n",
            "  fail-on-confirmed:\n",
            "  github-token:\n",
        ):
            self.assertIn(line, self.text)
        for default in ("default: .", "default: '3.11'", "default: 'true'", "default: ${{ github.token }}"):
            self.assertIn(default, self.text)

    def test_every_referenced_input_is_declared(self):
        declared = {"path", "python-version", "comment-pr", "fail-on-confirmed", "github-token"}
        for token in self.text.split("${{ inputs.")[1:]:
            self.assertIn(token.split(" }}")[0], declared)

    def test_audit_step_keeps_going_so_summary_is_always_written(self):
        self.assertIn('echo "exit-code=$status" >> "$GITHUB_OUTPUT"', self.text)
        self.assertNotIn("set -e", self.text)


if __name__ == "__main__":
    unittest.main()
