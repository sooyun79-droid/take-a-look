"""Optional tests in a disposable container; never run project code on the host."""

import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .schema import Evidence

SUITES = {
    "python-unittest": ("python", ["-I", "-B", "-m", "unittest", "discover", "-v"]),
    "node-test": ("node", ["--test"]),
    'ts-typecheck': ('tsc', ['--noEmit', '--incremental', 'false']),
    'node-lint': ('eslint', ['src', '--no-cache']),
}


def command(docker: str, image: str, snapshot: Path, name: str, suite: str) -> list[str]:
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image) or suite not in SUITES:
        raise ValueError("로컬 이미지의 sha256 ID와 허용된 검사 종류가 필요합니다.")
    if "," in str(snapshot):
        raise ValueError("격리 경로에는 쉼표를 사용할 수 없습니다.")
    entry, args = SUITES[suite]
    return [docker, "run", "--rm", "--name", name, "--pull=never", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64", "--memory=256m", "--memory-swap=256m", "--cpus=1", "--user=65534:65534", "--ipc=none", "--tmpfs=/tmp:rw,noexec,nosuid,size=32m", "--mount", f"type=bind,src={snapshot},dst=/project,readonly", "--workdir=/project", "--entrypoint", entry, image, *args]


def run_suite(files: dict[str, bytes], image: str | None = None, suite="python-unittest", timeout=45, target_root: Path | None = None) -> Evidence:
    base = dict(id="E-suite", claim_id=None, kind="isolated_suite", description="기존 테스트는 개별 Claim 판정과 별도로 기록합니다.")
    if not image:
        return Evidence(**base, outcome="skipped", details={"reason_code": "SANDBOX_NOT_ENABLED", "message": "격리 실행이 꺼져 있어 기존 테스트를 실행하지 않았습니다."})
    if target_root and Path(tempfile.gettempdir()).resolve().is_relative_to(target_root.resolve()):
        return Evidence(**base, outcome="skipped", details={"reason_code": "TEMP_WITHIN_TARGET"})
    docker = shutil.which("docker")
    if not docker:
        return Evidence(**base, outcome="skipped", details={"reason_code": "DOCKER_NOT_FOUND"})
    with tempfile.TemporaryDirectory(prefix="takealook-sandbox-") as temp:
        root = Path(temp)
        snapshot = root / "snapshot"
        snapshot.mkdir()
        for name, data in files.items():
            target = snapshot / name
            if not target.resolve().is_relative_to(snapshot.resolve()):
                raise ValueError("invalid snapshot path")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        config = root / "docker-config"
        config.mkdir()
        name = "takealook-" + uuid.uuid4().hex
        argv = command(docker, image, snapshot, name, suite)
        cid_file=root/'container-id'
        argv[2:2]=['--cidfile',str(cid_file),'--log-driver=none','--ulimit=nofile=256:256','--stop-timeout=1','--tmpfs=/work:rw,noexec,nosuid,size=32m']
        env = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE"}}
        env["DOCKER_CONFIG"] = str(config)
        stopped = None
        try:
            with (root / "stdout").open("w+b") as out, (root / "stderr").open("w+b") as err:
                process = subprocess.Popen(argv, stdout=out, stderr=err, env=env, shell=False)
                started = time.monotonic()
                while process.poll() is None:
                    if time.monotonic() - started > timeout:
                        stopped = "TIMEOUT"
                    elif os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > 1_000_000:
                        stopped = "OUTPUT_LIMIT"
                    if stopped:
                        process.kill()
                        break
                    time.sleep(0.1)
                process.wait(timeout=5)
                out.seek(0)
                err.seek(0)
                stdout = out.read(1_000_000).decode(errors="replace")
                stderr = err.read(1_000_000).decode(errors="replace")
            content = stdout + "\n" + stderr
            count_match = re.search(r"(?m)^Ran (\d{1,8}) tests? in ", content) if suite == "python-unittest" else re.search(r"(?m)^# tests (\d{1,8})\s*$", content)
            count = int(count_match[1]) if count_match else None
            non_test = suite in {'ts-typecheck','node-lint'}
            container_started=cid_file.is_file() and bool(re.fullmatch(r'[0-9a-f]{64}',cid_file.read_text().strip()))
            outcome = "stopped" if stopped else "passed" if process.returncode == 0 and (non_test or count and count > 0) else "failed" if process.returncode != 0 else "no_tests"
            return Evidence(**base, outcome=outcome, exit_code=process.returncode, stdout="[대상 출력은 비밀값 유출 방지를 위해 저장하지 않습니다.]", stderr="[대상 오류 출력은 저장하지 않습니다. 구조화된 결과를 확인하세요.]", repetitions=1, details={"suite": suite, "test_count": count, "reason_code": stopped, "image": image, "network": "none", "mount": "snapshot-readonly", "container_started":container_started,"output_policy": "structural_only", "note": "테스트 수와 결과는 대상 프로그램 출력에서 읽은 값입니다. 개별 버그 판정의 증거로 사용하지 않습니다."})
        except (OSError, subprocess.SubprocessError):
            return Evidence(**base, outcome="unavailable", details={"reason_code": "SANDBOX_UNAVAILABLE"})
        finally:
            # Kill the container as well as its client on timeout; never leave work running.
            try:
                subprocess.run([docker, "rm", "-f", name], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
            except (OSError, subprocess.SubprocessError):
                pass
