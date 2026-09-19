import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from take_a_look.pipeline import Auditor
from take_a_look.probes import Unsupported, probe
from take_a_look.providers import FunctionAdapter, MockProvider
from take_a_look.roles import Challenger, EvidenceJudge, Investigator
from take_a_look.schema import Claim, Evidence, Status

ROOT = Path(__file__).resolve().parents[1]


def all_hashes(path):
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob("*") if p.is_file()}


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / "reports"

    def audit(self, name):
        return Auditor().run(ROOT / "fixtures" / name, self.output)

    def test_a_confirmed_b_refuted_c_blindspot_and_no_modification(self):
        before = all_hashes(ROOT / "fixtures")
        expected = {"a_bug": Status.CONFIRMED, "b_safe": Status.REFUTED, "c_blindspot": Status.CONFIRMED}
        for name, status in expected.items():
            with self.subTest(name=name):
                report, directory = self.audit(name)
                self.assertEqual([v.status for v in report.verdicts], [status])
                self.assertEqual(report.integrity["status"], "UNCHANGED")
                self.assertEqual(report.evidence[0].repetitions, 3)
                self.assertEqual(report.evidence[-1].outcome, "skipped")
                data = json.loads((directory / "report.json").read_text(encoding="utf-8"))
                self.assertEqual(data["claims"][0]["id"], data["challenges"][0]["claim_id"])
                self.assertEqual(data["verdicts"][0]["evidence_ids"], [data["evidence"][0]["id"]])
        self.assertEqual(before, all_hashes(ROOT / "fixtures"))

    def test_c_existing_authored_tests_pass_but_auditor_finds_gap(self):
        # Development-only execution of OUR authored fixture, never a user repository.
        result = subprocess.run([sys.executable, "-I", "-B", "-m", "unittest", "discover", "-v"], cwd=ROOT / "fixtures/c_blindspot", capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Ran 2 tests", result.stderr)
        report, _ = self.audit("c_blindspot")
        self.assertEqual(report.summary["CONFIRMED"], 1)
        self.assertEqual(report.regression_candidates[0]["inputs"], {"values": []})

    def test_all_four_statuses(self):
        report, _ = self.audit("d_review")
        self.assertEqual({v.status for v in report.verdicts}, {Status.NEEDS_HUMAN, Status.UNCONFIRMED})

    def test_node_is_mapped_and_v02_reproduces_numeric_failure(self):
        report, _ = self.audit("node_example")
        self.assertIn("Node/TypeScript", report.project["languages"])
        self.assertTrue(report.project["typecheck"])
        self.assertEqual(report.verdicts[0].status, Status.CONFIRMED)
        self.assertEqual(report.evidence[0].repetitions, 5)
        self.assertEqual(report.evidence[0].details['cases'][0]['observations'][0]['output'], 'NaN')
        self.assertEqual(len(report.project["suggested_scripts"]), 3)

    def test_syntax_failure_has_objective_evidence(self):
        target = Path(self.temp.name) / "syntax"
        target.mkdir()
        (target / "bad.py").write_text("def broken(:\n", encoding="utf-8")
        report, _ = Auditor().run(target, self.output)
        self.assertEqual(report.verdicts[0].status, Status.CONFIRMED)
        self.assertEqual(report.evidence[0].details["error_type"], "SyntaxError")

    def test_non_utf8_source_does_not_become_false_syntax_error(self):
        target = Path(self.temp.name) / "legacy"
        target.mkdir()
        (target / "legacy.py").write_bytes(b"# coding: latin-1\nname = '\xe9'\n")
        report, _ = Auditor().run(target, self.output)
        self.assertEqual(report.summary["CONFIRMED"], 0)
        self.assertIn("UTF-8이 아닌 파일은 분석에서 제외", report.project["skipped"])

    def test_scope_syntax_error_is_detected_without_execution(self):
        target = Path(self.temp.name) / "scope"
        target.mkdir()
        (target / "invalid.py").write_text("return 1\n")
        report, _ = Auditor().run(target, self.output)
        self.assertEqual(report.summary["CONFIRMED"], 1)

    def test_provider_confidence_is_not_evidence(self):
        claim = Claim("C-test", "general", "a.py", 1, "100% confirmed!", "certain", "bad", "run rm -rf")
        judge = EvidenceJudge()
        self.assertEqual(judge.judge(claim, []).status, Status.UNCONFIRMED)
        fabricated = Evidence("E-fake", claim.id, "llm_opinion", "confirmed", "100%", repetitions=3)
        self.assertEqual(judge.judge(claim, [fabricated]).status, Status.UNCONFIRMED)
        unrelated = Evidence("E-other", "C-other", "python_parse", "syntax_error", "", source_sha256="123")
        self.assertEqual(judge.judge(claim, [unrelated]).status, Status.UNCONFIRMED)

    def test_provable_rule_cannot_smuggle_a_different_allegation(self):
        def callback(request):
            return {"claims": [MockProvider.item("boundary_division", "a.py", 2, "ALL CUSTOMER DATA LEAKED", "maybe", "ALL USERS HACKED", "deploy", "f")]}

        claim = Investigator(FunctionAdapter("test", callback)).investigate({"a.py": "def f(xs):\n return sum(xs)/len(xs)"})[0]
        self.assertNotIn("LEAKED", claim.title)
        self.assertNotIn("HACKED", claim.impact)
        self.assertNotEqual(claim.method, "deploy")

    def test_python_evidence_cannot_be_used_for_javascript(self):
        from take_a_look.qa import DeterministicQA
        from take_a_look.schema import Plan
        claim = Claim("C-js", "syntax", "x.js", 1, "x", "x", "x", "x")
        evidence = DeterministicQA().run(claim, Plan(claim.id, "python_parse", "parse"), "const x = 1;")
        self.assertEqual(EvidenceJudge().judge(claim, [evidence]).status, Status.UNCONFIRMED)

    def test_separate_contexts_and_adapter(self):
        requests = []

        def callback(request):
            requests.append(request)
            return MockProvider().complete(request)

        sources = {"a.py": "def f(xs):\n    return sum(xs)/len(xs)\n"}
        investigator = Investigator(FunctionAdapter("provider-A", callback))
        challenger = Challenger(FunctionAdapter("provider-B", callback))
        claim = investigator.investigate(sources)[0]
        challenger.challenge(claim, sources["a.py"])
        self.assertEqual([r.role for r in requests], ["investigator", "challenger"])
        self.assertNotIn("reason", requests[1].data["claim"])
        self.assertNotIn("history", requests[1].data)
        self.assertIn("untrusted DATA", requests[0].instructions)

    def test_provider_schema_rejects_commands_and_outside_references(self):
        for extra in ({"command": "curl evil"}, {"file": "../secret.py"}, {"line": -1}):
            def callback(request, extra=extra):
                item = MockProvider.item("general", "a.py", 1, "x", "x", "x", "x")
                item.update(extra)
                return {"claims": [item]}
            with self.assertRaises(ValueError):
                Investigator(FunctionAdapter("bad", callback)).investigate({"a.py": "pass"})

    def test_unsupported_code_fails_closed(self):
        variants = [
            "@decorator\ndef f(xs):\n    return sum(xs)/len(xs)\n",
            "def f(xs):\n    import os\n    return sum(xs)/len(xs)\n",
            "def f(xs):\n    open('danger', 'w')\n    return sum(xs)/len(xs)\n",
            "def f(xs):\n    while True: pass\n    return sum(xs)/len(xs)\n",
            "def f(xs):\n    return global_value/len(xs)\n",
            "def f(xs):\n    return sum(xs)/len(xs)\nlen = replacement\n",
        ]
        for source in variants:
            with self.subTest(source=source):
                line = next(i for i, text in enumerate(source.splitlines(), 1) if "/len" in text)
                with self.assertRaises(Unsupported):
                    probe(source, "f", line)

    def test_probe_is_specific_to_claim_location(self):
        with self.assertRaises(Unsupported):
            probe("def f(xs):\n return sum(xs)/len(xs)", "f", 99)

    def test_baseline_suite_pass_cannot_refute_a_claim(self):
        claim = Claim("C-test", "boundary_division", "a.py", 1, "x", "x", "x", "x", "f")
        suite = Evidence("E-suite", None, "isolated_suite", "passed", "all tests pass", exit_code=0)
        self.assertEqual(EvidenceJudge().judge(claim, [suite]).status, Status.UNCONFIRMED)

    def test_no_findings_is_not_full_pass(self):
        target = Path(self.temp.name) / "empty"
        target.mkdir()
        report, directory = Auditor().run(target, self.output)
        self.assertEqual(len(report.claims), 0)
        self.assertIn("전체 검증 통과를 뜻하지", (directory / "report.html").read_text(encoding="utf-8"))

    def test_audit_sequence_and_regression_export(self):
        report, directory = self.audit("a_bug")
        self.assertEqual([event["sequence"] for event in report.audit], list(range(1, len(report.audit) + 1)))
        for stage in ("Investigator", "Challenger", "Evidence Builder", "Deterministic QA", "Evidence Judge"):
            self.assertIn(stage, [e["stage"] for e in report.audit])
        regression = json.loads((directory / "regression-candidates.json").read_text(encoding="utf-8"))
        self.assertEqual(len(regression), 1)
        self.assertEqual(regression[0]["claim_id"], report.claims[0].id)


if __name__ == "__main__":
    unittest.main()
