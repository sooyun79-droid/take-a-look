"""Explicit public allowlist; never export development history or private audits."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
TOP={'README.md','README.en.md','LICENSE','THIRD_PARTY_NOTICES.md','CONTRIBUTING.md','SECURITY.md','.gitignore','pyproject.toml','package.json','package-lock.json','tsconfig.json','Start-TakeALook.cmd'}
DIRS={'take_a_look','tests','tests-node','fixtures','docs','.github'}
TOOLS={'build.py','check.py','public_export.py'}
SYNTHETIC={'sk-SYNTHETIC_FIXTURE','sk-SYNTHETIC_FIXTURE_NOT_A_REAL_KEY_123456','sk-abcdefghijklmnopqrst','ghp_abcdefghijklmnop','sk-SYNTHETIC_FIXTURE_NOT_A_REAL_CREDENTIAL','sk-SYNTHETIC_FIXTURE_DO_NOT_USE','sk-SYNTHETIC_FIXTURE_NOT_REAL','sk-DO_NOT_SEND_THIS'}


def inspect_text(text):
    findings=[]
    if re.search(r'(?i)[a-z]:[\\/]+Users[\\/]|/Us'+r'ers/|/home/(?!me/)[a-z0-9_-]+/|\.chatgpt'+r'-projects|\.codex[\\/]|searchlens'+r'-dashboard|src/lib/'+r'search-market',text):findings.append('PRIVATE_PATH_OR_SOURCE')
    for token in re.findall(r'(?:sk-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}',text):
        if token not in SYNTHETIC:findings.append('TOKEN_CANDIDATE')
    if re.search(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=]{40}',text):findings.append('PRIVATE_KEY')
    if re.search(r'https?://[^\s/@:]+:[^\s/@]+@(?!example\.test)',text):findings.append('URL_CREDENTIAL')
    return sorted(set(findings))


def selected(root=ROOT):
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink():continue
        relative=p.relative_to(root)
        if any(x in {'__pycache__','node_modules','.git','.cache','.release','.venv'} for x in relative.parts):continue
        if len(relative.parts)==1 and p.name in TOP or relative.parts[0] in DIRS or relative.parts[0]=='tools' and p.name in TOOLS:
            if p.suffix=='.pyc' or p.name.startswith('.env') and p.name!='.env.example':continue
            yield relative,p


def audit_files(root):
    failures=[];manifest={}
    for relative,p in selected(root):
        data=p.read_bytes()
        try:issues=inspect_text(data.decode('utf8'))
        except UnicodeDecodeError:issues=['BINARY_REQUIRES_REVIEW']
        if issues:failures.append({'file':relative.as_posix(),'reasons':issues})
        manifest[relative.as_posix()]=hashlib.sha256(data).hexdigest()
    return {'pass':not failures,'files':len(manifest),'findings':failures,'sha256':manifest}


def history_audit(root):
    # Inspect every reachable commit/tree blob, reporting only IDs and reason codes.
    result=subprocess.run(['git','rev-list','--objects','--all'],cwd=root,capture_output=True,text=True,check=True)
    failures=[];checked=0
    for row in result.stdout.splitlines():
        oid=row.split(' ',1)[0]
        kind=subprocess.run(['git','cat-file','-t',oid],cwd=root,capture_output=True,text=True,check=True).stdout.strip()
        if kind not in {'blob','commit'}:continue
        raw=subprocess.run(['git','cat-file','-p',oid],cwd=root,capture_output=True,check=True).stdout
        checked+=1
        try:issues=inspect_text(raw.decode('utf8'))
        except UnicodeDecodeError:issues=['BINARY_REQUIRES_REVIEW']
        if issues:failures.append({'object':oid,'reasons':issues})
    return {'pass':not failures,'objects_checked':checked,'findings':failures}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--destination');ap.add_argument('--history',action='store_true');args=ap.parse_args()
    if args.history:
        result=history_audit(ROOT);print(json.dumps(result,indent=2));return 0 if result['pass'] else 2
    result=audit_files(ROOT)
    if not result['pass']:print(json.dumps(result,indent=2));return 2
    if args.destination:
        dest=Path(args.destination).resolve()
        if dest.exists():raise ValueError('EXPORT_DESTINATION_MUST_BE_NEW')
        if not dest.is_relative_to(ROOT/'.release'):raise ValueError('EXPORT_OUTSIDE_RELEASE_DIRECTORY')
        dest.mkdir(parents=True)
        for relative,p in selected():
            target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
        (dest.parent/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'pass':True,'files':result['files']}));return 0


if __name__=='__main__':raise SystemExit(main())
