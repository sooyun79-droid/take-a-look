"""Loopback-only UI with per-session CSRF token and bounded single-job execution."""

import hmac
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from .pipeline import Auditor


def create_server(port=8765, output="reports"):
    token, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(20)
    jobs = {}
    lock = threading.Lock()
    busy = threading.Semaphore(1)
    output = Path(output).resolve()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Never log paths, submitted bodies or bearer tokens.

        def send(self, status, payload, content_type="application/json; charset=utf-8"):
            raw = payload.encode("utf-8") if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'unsafe-inline'; connect-src 'self'; frame-src 'self' about:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(raw)

        def local_request(self):
            hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            return self.headers.get("Host") in hosts and self.headers.get("Origin") in {None, *("http://" + host for host in hosts)}

        def authorized(self):
            return self.local_request() and hmac.compare_digest(self.headers.get("X-TakeALook-Token", ""), token)

        def do_GET(self):
            if not self.local_request():
                return self.send(403, {"error": "로컬 화면에서만 사용할 수 있습니다."})
            path = urlsplit(self.path).path
            if path == "/":
                page = files("take_a_look").joinpath("web.html").read_text(encoding="utf-8")
                return self.send(200, page.replace("__TOKEN__", token).replace("__NONCE__", nonce), "text/html; charset=utf-8")
            if path.startswith("/api/jobs/") and self.authorized():
                key = path.rsplit("/", 1)[-1]
                with lock:
                    job = dict(jobs.get(key, {}))
                return self.send(200 if job else 404, job or {"error": "결과를 찾지 못했습니다."})
            self.send(404, {"error": "페이지를 찾지 못했습니다."})

        def do_POST(self):
            def discard_small_body():
                # On Windows, closing with unread request bytes can reset the
                # connection before a rejection response reaches the browser.
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if 0<size<=8192:
                        self.connection.settimeout(2)
                        self.rfile.read(size)
                except (ValueError,OSError):
                    pass
            if self.path != "/api/audit" or not self.authorized():
                discard_small_body()
                return self.send(403, {"error": "로컬 화면에서 검증을 시작하세요."})
            if self.headers.get_content_type() != "application/json":
                discard_small_body()
                return self.send(415, {"error": "JSON 입력이 필요합니다."})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 4096:
                    discard_small_body()
                    raise ValueError()
                self.connection.settimeout(5)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or set(payload) != {"path"} or not isinstance(payload["path"], str) or not payload["path"].strip():
                    raise ValueError()
            except (ValueError, OSError):
                return self.send(400, {"error": "프로젝트 폴더 경로를 입력하세요."})
            if not busy.acquire(blocking=False):
                return self.send(409, {"error": "이미 검사 중입니다. 현재 검사가 끝나면 시작하세요."})
            key = uuid4().hex
            with lock:
                while len(jobs) >= 20:
                    del jobs[next(iter(jobs))]
                jobs[key] = {"status": "running", "stage": "준비 중"}

            def update(stage):
                with lock:
                    jobs[key]["stage"] = stage

            def work():
                try:
                    report, directory = Auditor().run(payload["path"].strip(), output, progress=update)
                    with lock:
                        jobs[key] = {"status": "done", "stage": "완료", "summary": report.summary, "html": (directory / "report.html").read_text(encoding="utf-8")}
                except Exception:
                    with lock:
                        jobs[key] = {"status": "failed", "error": "검사를 완료하지 못했습니다. 실제 폴더인지, 접근 권한이 있는지, 보고서 위치가 대상 폴더 밖인지 확인하세요. 파일 수·크기 제한도 적용됩니다."}
                finally:
                    busy.release()

            threading.Thread(target=work, daemon=True).start()
            self.send(202, {"job_id": key})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def serve(port=8765, output="reports", open_browser=False):
    server = create_server(port, output)
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"떼껄룩: {url}\n종료하려면 Ctrl+C를 누르세요.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
