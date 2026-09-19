"""No repository instructions, credentials or shell strings cross trust boundaries."""

import hashlib
import os
import re
import stat
from pathlib import Path

IGNORED_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build", ".next", ".cache"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml", ".txt", ".ini", ".cfg", ".sql", ".lock", '.mjs', '.cjs'}
MAX_FILES = 1500
MAX_FILE_BYTES = 256_000
MAX_TOTAL_BYTES = 12_000_000


def sensitive(path: Path) -> bool:
    name = path.name.lower()
    return (name.startswith(".env") or name in {".npmrc", ".pypirc", "id_rsa", "id_ed25519"}
            or any(s in name for s in ("credential", "secret", "token", "private_key"))
            or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".keystore"})


def redact(value: str) -> str:
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)", "[비밀키 숨김]", value)
    value = re.sub(r"(?im)^.*(?:password|passwd|api[_-]?key|access[_-]?token|secret|authorization)\s*[:=].*$", "[민감한 값이 포함된 줄 숨김]", value)
    value = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16})\b", "[토큰 숨김]", value)
    value = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[토큰 숨김]", value)
    value = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://[인증 숨김]@", value)
    return value


def safe_label(value: str) -> str:
    """Repository-controlled names are metadata too; cap and redact them."""
    return redact(value)[:240]


def is_link(path: Path) -> bool:
    info = path.lstat()
    return path.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def collect(root: Path) -> tuple[dict[str, bytes], list[str]]:
    """Bounded snapshot. No symlinks, junctions, hidden config, or secret files."""
    files: dict[str, bytes] = {}
    skipped: set[str] = set()
    total = 0
    walked = 0
    for current, dirs, names in os.walk(root, followlinks=False):
        walked += len(dirs) + len(names)
        if walked > 30_000:
            raise ValueError("폴더 항목이 너무 많습니다. 더 작은 소스 폴더를 선택하세요.")
        kept = []
        for name in sorted(dirs):
            p = Path(current) / name
            if name in IGNORED_DIRS or name.startswith(".") or sensitive(p) or is_link(p):
                skipped.add("제외 폴더/링크")
            else:
                kept.append(name)
        dirs[:] = kept
        for name in sorted(names):
            p = Path(current) / name
            if name.startswith(".") or sensitive(p) or is_link(p):
                skipped.add("숨김·민감 파일/링크")
                continue
            if p.suffix.lower() not in SOURCE_SUFFIXES and name not in {"Dockerfile", "Makefile", "uv.lock", "yarn.lock"}:
                skipped.add("지원하지 않는 파일 형식")
                continue
            if not stat.S_ISREG(p.stat().st_mode):
                skipped.add("일반 파일이 아님")
                continue
            if p.stat().st_size > MAX_FILE_BYTES:
                skipped.add("개별 파일 크기 제한")
                continue
            with p.open("rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("검사 중 파일 크기가 변경되었습니다.")
            total += len(data)
            if total > MAX_TOTAL_BYTES or len(files) >= MAX_FILES:
                raise ValueError("검사 용량 제한을 넘었습니다. 더 작은 소스 폴더를 선택하세요.")
            files[p.relative_to(root).as_posix()] = data
    return files, sorted(skipped)


def hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


def text_sources(files: dict[str, bytes]) -> dict[str, str]:
    sources = {}
    for name, raw in files.items():
        try:
            sources[name] = raw.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError:
            # Never turn a decoding replacement character into a false syntax proof.
            continue
    return sources


def outside_target(target: Path, output: Path) -> None:
    if output == target or output.is_relative_to(target):
        raise ValueError("보고서 위치는 검증 대상 폴더 밖이어야 합니다.")
