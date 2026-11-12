"""SearchLens 연계 웹·이커머스 정적 규칙 4종의 검출·검증·리포트 경로 테스트."""

import json
import tempfile
import unittest
from pathlib import Path

from take_a_look import webrules
from take_a_look.pipeline import Auditor
from take_a_look.providers import FunctionAdapter, MockProvider
from take_a_look.qa import DeterministicQA
from take_a_look.roles import EvidenceBuilder, EvidenceJudge, Investigator
from take_a_look.schema import Challenge, Claim, Evidence, Plan, Status

ROOT = Path(__file__).resolve().parents[1]
WEB_RULES = set(webrules.WEB_RULES)


def detect(sources):
    return Investigator(MockProvider()).investigate(sources)


def rules_found(claims):
    return {(c.rule, c.file, c.line) for c in claims}


class DetectionTests(unittest.TestCase):
    def test_seo_noindex_finds_meta_next_metadata_and_robots_txt(self):
        sources = {
            "site/index.html": '<!doctype html>\n<html><head>\n<meta name="robots" content="noindex, nofollow">\n</head></html>\n',
            "app/layout.tsx": "export const metadata = {\n  title: 'shop',\n  robots: { index: false, follow: false },\n};\n",
            "app/about.tsx": "export const metadata: Metadata = { robots: 'noindex' };\n",
            "public/robots.txt": "User-agent: *\nDisallow: /\n",
        }
        claims = detect(sources)
        self.assertEqual(rules_found(claims), {
            ("seo_noindex", "site/index.html", 3),
            ("seo_noindex", "app/layout.tsx", 3),
            ("seo_noindex", "app/about.tsx", 1),
            ("seo_noindex", "public/robots.txt", 2),
        })
        self.assertTrue(all(c.title == webrules.TITLES["seo_noindex"] for c in claims))
        self.assertTrue(all(c.method == webrules.METHODS["seo_noindex"] for c in claims))

    def test_seo_noindex_ignores_indexable_pages_and_partial_robots(self):
        sources = {
            "site/page.html": '<html><head>\n<meta name="robots" content="index, follow">\n</head></html>\n',
            "app/ok.tsx": "export const metadata = { robots: { index: true, follow: true } };\n",
            "public/robots.txt": "User-agent: *\nDisallow: /admin\nAllow: /\n",
            "public/robots-backup.txt": "User-agent: *\nDisallow: /\n",
        }
        self.assertEqual([c for c in detect(sources) if c.rule == "seo_noindex"], [])

    def test_client_secret_leak_finds_public_env_token_and_pg_key(self):
        token = "ghp_" + "A" * 36
        sources = {
            "lib/stripe.ts": "export const cfg = { key: process.env.NEXT_PUBLIC_STRIPE_SECRET };\n",
            "lib/vite.ts": "export const pay = import.meta.env.VITE_PAYMENT_TOKEN;\n",
            "lib/token.ts": f'const leaked = "{token}";\n',
            "lib/nicepay.ts": "export const NICEPAY_SECRET_KEY = " + '"' + "b" * 32 + '";\n',
        }
        claims = [c for c in detect(sources) if c.rule == "client_secret_leak"]
        self.assertEqual(rules_found(claims), {
            ("client_secret_leak", "lib/stripe.ts", 1),
            ("client_secret_leak", "lib/vite.ts", 1),
            ("client_secret_leak", "lib/token.ts", 1),
            ("client_secret_leak", "lib/nicepay.ts", 1),
        })
        self.assertIn("NEXT_PUBLIC_STRIPE_SECRET", {c.symbol for c in claims})

    def test_client_secret_leak_never_echoes_the_secret_value(self):
        token = "sk-" + "c" * 24
        claims = detect({"app/config.ts": f'const k = "{token}";\n'})
        self.assertEqual([c.rule for c in claims], ["client_secret_leak"])
        dumped = json.dumps([c.__dict__ for c in claims], ensure_ascii=False)
        self.assertNotIn(token, dumped)

    def test_client_secret_leak_ignores_server_files_and_public_values(self):
        sources = {
            "server/settings.py": 'KEY = "NEXT_PUBLIC_API_SECRET"\n',
            "lib/public.ts": "export const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;\nexport const price = 49000;\n",
        }
        self.assertEqual([c for c in detect(sources) if c.rule == "client_secret_leak"], [])

    def test_image_alt_rule_finds_single_and_multiline_tags(self):
        sources = {
            "components/Hero.tsx": (
                "export const Hero = () => (\n"
                "  <section>\n"
                "    <Image\n"
                '      src="/hero.png"\n'
                "      width={1200}\n"
                "    />\n"
                '    <Image src="/banner.png" alt="봄 배너" />\n'
                "  </section>\n"
                ");\n"
            ),
            "site/detail.html": '<div>\n  <img src="/detail-1.jpg">\n  <img src="/detail-2.jpg" alt="상세 1">\n</div>\n',
        }
        claims = [c for c in detect(sources) if c.rule == "a11y_image_alt"]
        self.assertEqual(rules_found(claims), {
            ("a11y_image_alt", "components/Hero.tsx", 3),
            ("a11y_image_alt", "site/detail.html", 2),
        })

    def test_image_alt_rule_ignores_present_alt_spread_and_comments(self):
        sources = {
            "components/Safe.tsx": (
                '<img src="/a.png" alt="" />\n'
                "<Image {...props} />\n"
                "// <img src=\"/legacy.png\">\n"
                "/* <Image src=\"/old.png\" /> */\n"
            ),
            "site/safe.html": '<!-- <img src="/old.png"> -->\n<img src="/b.png" alt="설명">\n',
        }
        self.assertEqual([c for c in detect(sources) if c.rule == "a11y_image_alt"], [])

    def test_payment_tamper_finds_literal_amount_near_pg_call(self):
        sources = {
            "checkout.ts": (
                "const IMP = window.IMP;\n"
                "IMP.request_pay({\n"
                "  pg: 'nicepay',\n"
                "  amount: 49000,\n"
                "  name: 'full audit',\n"
                "});\n"
            ),
            "toss.ts": (
                "const payment = await loadTossPayments(CLIENT_KEY);\n"
                "await payment.requestPayment({\n"
                "  amount: 49500,\n"
                "  orderId: order.id,\n"
                "});\n"
            ),
        }
        claims = [c for c in detect(sources) if c.rule == "client_payment_tamper"]
        self.assertEqual(rules_found(claims), {
            ("client_payment_tamper", "checkout.ts", 4),
            ("client_payment_tamper", "toss.ts", 3),
        })
        self.assertIn("IMP.request_pay", {c.symbol for c in claims})

    def test_payment_tamper_ignores_server_amounts_and_distant_literals(self):
        far = "\n" * 20
        sources = {
            "safe.ts": (
                "const payment = await loadTossPayments(CLIENT_KEY);\n"
                "await payment.requestPayment({ amount: order.totalAmount });\n"
            ),
            "unrelated.ts": "const invoice = { amount: 1000, price: 2000 };\n",
            "far.ts": "const amount = 49000;\n" + far + "loadTossPayments(CLIENT_KEY);\n",
        }
        self.assertEqual([c for c in detect(sources) if c.rule == "client_payment_tamper"], [])

    def test_payment_strings_and_comments_are_not_executable_calls(self):
        sources = {
            "docs.ts": 'const docs = "IMP.request_pay({ amount: 49000 })";\n',
            "comment.ts": 'const ready = true;// IMP.request_pay({ amount: 49000 })\n',
        }
        self.assertEqual([c for c in detect(sources) if c.rule == "client_payment_tamper"], [])

    def test_web_rules_do_not_fire_on_python_sources(self):
        sources = {
            "calc.py": (
                "def display_amount(amount, price):\n"
                "    # <img src=\"x.png\"> robots: { index: false }\n"
                "    return round(amount), price\n"
            ),
        }
        self.assertEqual([c for c in detect(sources) if c.rule in WEB_RULES], [])

    def test_provider_cannot_rewrite_standard_web_titles(self):
        def callback(request):
            return {"claims": [MockProvider.item("seo_noindex", "index.html", 1, "전체 고객 데이터 유출", "maybe", "ALL USERS HACKED", "deploy", "x")]}

        claim = Investigator(FunctionAdapter("scripted", callback)).investigate({"index.html": '<meta name="robots" content="noindex">\n'})[0]
        self.assertEqual(claim.title, webrules.TITLES["seo_noindex"])
        self.assertEqual(claim.impact, webrules.IMPACTS["seo_noindex"])
        self.assertEqual(claim.method, webrules.METHODS["seo_noindex"])


class VerificationTests(unittest.TestCase):
    def test_static_pattern_verification_keeps_unproven_signals_unconfirmed(self):
        source = '<html>\n<meta name="robots" content="noindex">\n</html>\n'
        claim = Claim("C-1", "seo_noindex", "index.html", 2, "t", "r", "i", "m", "meta-robots")
        plan = Plan(claim.id, "static_pattern", "재확인", "CHECK_STATIC_PATTERN")
        found = DeterministicQA().run(claim, plan, source)
        self.assertEqual(found.outcome, "found")
        self.assertEqual(EvidenceJudge().judge(claim, [found]).status, Status.UNCONFIRMED)

        moved = DeterministicQA().run(Claim("C-2", "seo_noindex", "index.html", 3, "t", "r", "i", "m"), Plan("C-2", "static_pattern", "재확인", "CHECK_STATIC_PATTERN"), source)
        self.assertEqual(moved.outcome, "absent")
        self.assertEqual(EvidenceJudge().judge(Claim("C-2", "seo_noindex", "index.html", 3, "t", "r", "i", "m"), [moved]).status, Status.REFUTED)

    def test_evidence_from_another_rule_cannot_confirm(self):
        claim = Claim("C-3", "a11y_image_alt", "page.html", 1, "t", "r", "i", "m")
        evidence = Evidence("E-C-3", "C-3", "static_pattern", "found", "x", source_sha256="abc", details={"engine": "web-static-pattern-v1", "rule": "seo_noindex", "line": 1})
        self.assertEqual(EvidenceJudge().judge(claim, [evidence]).status, Status.UNCONFIRMED)

    def test_web_rule_evidence_kind_is_closed_to_static_pattern(self):
        claim = Claim("C-4", "client_secret_leak", "app.ts", 1, "t", "r", "i", "m")
        plan = EvidenceBuilder().build(claim, Challenge(claim.id, "공개되어도 되는 값일 수 있습니다."))
        self.assertEqual(plan.kind, "static_pattern")
        self.assertEqual(plan.intent, "CHECK_STATIC_PATTERN")

    def test_all_web_rule_patterns_need_more_than_a_matching_line(self):
        cases = {
            'seo_noindex': ('page.html', '<meta name="robots" content="noindex">'),
            'client_secret_leak': ('client.ts', 'const x = process.env.NEXT_PUBLIC_STRIPE_SECRET;'),
            'a11y_image_alt': ('page.html', '<img src="/banner.png">'),
            'client_payment_tamper': ('checkout.ts', 'IMP.request_pay({ amount: 49000 });'),
        }
        for rule, (file, source) in cases.items():
            with self.subTest(rule=rule):
                claim = Claim('C-' + rule, rule, file, 1, 't', 'r', 'i', 'm')
                plan = Plan(claim.id, 'static_pattern', '재확인', 'CHECK_STATIC_PATTERN')
                evidence = DeterministicQA().run(claim, plan, source)
                self.assertEqual(evidence.outcome, 'found')
                self.assertEqual(EvidenceJudge().judge(claim, [evidence]).status, Status.UNCONFIRMED)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "shop"
        self.output = Path(self.temp.name) / "reports"

    def write(self, relative, text):
        path = self.target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def build_shop(self):
        self.write("site/index.html", '<!doctype html>\n<html>\n<head>\n<meta name="robots" content="noindex, nofollow">\n</head>\n<body>\n<img src="/hero.png">\n</body>\n</html>\n')
        self.write("lib/config.ts", "export const cfg = process.env.NEXT_PUBLIC_STRIPE_SECRET\n")
        self.write("public/robots.txt", "User-agent: *\nDisallow: /\n")
        self.write("checkout.ts", "IMP.request_pay({\n  pg: 'nicepay',\n  amount: 49000,\n  name: 'full audit',\n});\n")

    def test_end_to_end_report_does_not_confirm_static_signals(self):
        self.build_shop()
        report, directory = Auditor().run(self.target, self.output)
        self.assertEqual(report.summary["CONFIRMED"], 0)
        self.assertEqual(report.summary["UNCONFIRMED"], len(report.claims))
        self.assertEqual({c.rule for c in report.claims}, WEB_RULES)
        self.assertEqual(len(report.groups), 4)
        self.assertEqual(report.integrity["status"], "UNCHANGED")
        self.assertEqual(report.project["execution_mode"], "NO_EXECUTION")
        self.assertTrue(all(c.title in webrules.TITLES.values() for c in report.claims))
        page = (directory / "report.html").read_text(encoding="utf-8")
        self.assertIn("검색 인덱싱 차단(noindex) 관련 의심", page)
        self.assertIn("검색엔진 및 AI 크롤러에서 페이지 노출이 완전히 제외될 수 있습니다.", page)
        regression = json.loads((directory / "regression-candidates.json").read_text(encoding="utf-8"))
        self.assertEqual(regression, [])

    def test_report_never_contains_client_secret_value(self):
        token = "sk-" + "d" * 24
        self.write("app/client.ts", f'const leaked = "{token}";\n')
        report, directory = Auditor().run(self.target, self.output)
        self.assertEqual(report.summary["UNCONFIRMED"], 1)
        for path in directory.iterdir():
            self.assertNotIn(token, path.read_text(encoding="utf-8"), path.name)

    def test_payment_text_in_strings_and_comments_is_not_confirmed(self):
        self.write("docs.ts", 'const docs = "IMP.request_pay({ amount: 49000 })";\n')
        self.write("comment.ts", '// IMP.request_pay({ amount: 49000 })\n')
        report, _ = Auditor().run(self.target, self.output)
        self.assertEqual(report.summary["CONFIRMED"], 0)
        self.assertFalse(any(c.rule == "client_payment_tamper" for c in report.claims))

    def test_payment_call_with_literal_amount_stays_unconfirmed(self):
        self.write("checkout.ts", "IMP.request_pay({ amount: 49000 });\n")
        report, _ = Auditor().run(self.target, self.output)
        payment = [v for c, v in zip(report.claims, report.verdicts) if c.rule == "client_payment_tamper"]
        self.assertEqual(len(payment), 1)
        self.assertEqual(payment[0].status, Status.UNCONFIRMED)

    def test_clean_shop_has_no_web_claims(self):
        self.write("site/index.html", '<html>\n<meta name="robots" content="index, follow">\n<img src="/a.png" alt="상품">\n</html>\n')
        self.write("public/robots.txt", "User-agent: *\nDisallow: /admin\n")
        self.write("checkout.ts", "await pay({ amount: order.total });\n")
        report, _ = Auditor().run(self.target, self.output)
        self.assertEqual([c for c in report.claims if c.rule in WEB_RULES], [])

    def test_real_python_boundary_failure_stays_confirmed(self):
        report, _ = Auditor().run(ROOT / 'fixtures/a_bug', self.output)
        self.assertEqual(report.summary['CONFIRMED'], 1)


if __name__ == "__main__":
    unittest.main()
