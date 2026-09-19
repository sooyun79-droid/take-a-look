import http.client
import json
import re
import tempfile
import threading
import time
import unittest
from pathlib import Path

from take_a_look.web import create_server

ROOT = Path(__file__).resolve().parents[1]


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = create_server(0, cls.temp.name)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.read().decode(), dict(response.getheaders())
        finally:
            conn.close()

    def token(self):
        status, html, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        return re.search("const token='([^']+)'", html)[1]

    def test_ui_end_to_end_api(self):
        token = self.token()
        headers = {"Content-Type": "application/json", "X-TakeALook-Token": token}
        status, text, _ = self.request("POST", "/api/audit", json.dumps({"path": str(ROOT / "fixtures/b_safe")}), headers)
        self.assertEqual(status, 202)
        key = json.loads(text)["job_id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            status, text, _ = self.request("GET", "/api/jobs/" + key, headers=headers)
            data = json.loads(text)
            if data["status"] != "running":
                break
            time.sleep(0.02)
        self.assertEqual(data["status"], "done")
        self.assertEqual(data["summary"]["REFUTED"], 1)
        self.assertIn("반대 검토는 무엇이었나", data["html"])

    def test_csrf_host_and_origin_protection(self):
        body = json.dumps({"path": str(ROOT)})
        status, _, _ = self.request("POST", "/api/audit", body, {"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("GET", "/", headers={"Host": "evil.test"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/api/audit", body, {"Content-Type": "application/json", "Origin": "https://evil.test", "X-TakeALook-Token": self.token()})
        self.assertEqual(status, 403)

    def test_invalid_and_oversized_input(self):
        headers = {"Content-Type": "application/json", "X-TakeALook-Token": self.token()}
        for body in ("[]", '{"path": 42}', '{"path":"x", "command":"deploy"}', "x" * 4097):
            status, _, _ = self.request("POST", "/api/audit", body, headers)
            self.assertEqual(status, 400)

    def test_security_headers_and_no_source_serving(self):
        _, _, headers = self.request("GET", "/")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        status, _, _ = self.request("GET", "/../take_a_look/pipeline.py")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
