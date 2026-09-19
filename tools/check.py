"""Dependency-free syntax/config validation, not a full lint/type checker."""

import ast
import json
import subprocess
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
count = 0
for folder in ("take_a_look", "tests", "tools", "fixtures"):
    for file in (ROOT / folder).rglob("*.py"):
        source = file.read_text(encoding="utf-8")
        ast.parse(source, filename=str(file))
        compile(source, str(file), "exec")  # Compile only. Never execute fixtures.
        count += 1
for file in (ROOT / "fixtures").rglob("*.json"):
    json.loads(file.read_text(encoding="utf-8"))
for name in ('package.json','package-lock.json','tsconfig.json'):
    json.loads((ROOT/name).read_text(encoding='utf8'))
tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
page = (ROOT / "take_a_look/web.html").read_text(encoding="utf-8")
script = page.split('<script nonce="__NONCE__">', 1)[1].split("</script>", 1)[0]
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "ui.js"
    path.write_text(script, encoding="utf-8")
    subprocess.run(["node", "--check", str(path)], check=True, timeout=10)
subprocess.run(['node','--check',str(ROOT/'take_a_look/node_worker.mjs')],check=True,timeout=10)
print(f"PASS: {count} Python files compiled; JSON/TOML parsed; UI JavaScript syntax checked")
