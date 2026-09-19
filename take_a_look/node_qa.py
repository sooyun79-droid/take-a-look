"""Fixed Node worker, own pinned parser, empty environment, no target imports."""
import json
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from uuid import uuid4


def toolchain_root():
    if '.pyz' in str(__file__):
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parents[1]


def node_probe(source, file, line, workspace=None):
    node = shutil.which('node')
    root = toolchain_root()
    compiler = root / 'node_modules/typescript/lib/typescript.js'
    if not node or not compiler.is_file():
        return {'outcome': 'unsupported', 'reason_code': 'NODE_TOOLCHAIN_UNAVAILABLE', 'cases': []}
    work = Path(workspace) if workspace else root / '.takealook-work'
    directory = work / uuid4().hex
    directory.mkdir(parents=True)
    worker = directory / 'worker.mjs'
    worker.write_text(files('take_a_look').joinpath('node_worker.mjs').read_text(encoding='utf8'), encoding='utf8')
    env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP'}}
    argv = [node, '--max-old-space-size=128', '--disable-proto=throw', str(worker), str(compiler)]
    try:
        result = subprocess.run(argv, input=json.dumps({'source': source, 'file': file, 'line': line}), text=True, encoding='utf8', capture_output=True, env=env, cwd=directory, timeout=10, shell=False)
        if result.returncode != 0 or len(result.stdout)>100000:
            return {'outcome': 'unsupported', 'reason_code': 'NODE_WORKER_FAILED', 'cases': [], 'exit_code': result.returncode}
        data = json.loads(result.stdout)
        data['exit_code'] = result.returncode
        data['command'] = ['node', '--max-old-space-size=128', '--disable-proto=throw', '<trusted-worker>', '<own-typescript-parser>']
        return data
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'outcome': 'unsupported', 'reason_code': 'NODE_WORKER_UNAVAILABLE', 'cases': []}
    finally:
        worker.unlink(missing_ok=True)
        directory.rmdir()
