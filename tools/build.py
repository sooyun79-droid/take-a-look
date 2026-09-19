"""Build an offline, dependency-free zipapp with Python's standard library."""

import shutil
import tempfile
import zipapp
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
destination = ROOT / "dist" / "take-a-look.pyz"
destination.parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory)
    shutil.copytree(ROOT / "take_a_look", source / "take_a_look", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (source / "__main__.py").write_text("from take_a_look.__main__ import main\nraise SystemExit(main())\n", encoding="utf-8")
    zipapp.create_archive(source, destination, compressed=True)
compiler=ROOT/'node_modules/typescript'
if compiler.is_dir():
    shutil.copytree(compiler, destination.parent/'node_modules/typescript', dirs_exist_ok=True)
archive=destination.parent/'take-a-look-v0.3.0-alpha.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as bundle:
    bundle.write(destination,destination.name)
    for name in ['README.md','LICENSE','THIRD_PARTY_NOTICES.md']:
        bundle.write(ROOT/name,name)
    for path in (ROOT/'docs').rglob('*'):
        if path.is_file():bundle.write(path,path.relative_to(ROOT).as_posix())
    bundle.writestr('Start-TakeALook.cmd','@echo off\r\ncd /d "%~dp0"\r\npython -B take-a-look.pyz web --open\r\npause\r\n')
    if compiler.is_dir():
        for path in (destination.parent/'node_modules/typescript').rglob('*'):
            if path.is_file():bundle.write(path,path.relative_to(destination.parent).as_posix())
print(destination)
print(archive)
