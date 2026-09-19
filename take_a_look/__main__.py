import argparse
import sys
import json
from pathlib import Path

from .pipeline import Auditor
from .web import serve


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="take-a-look", description="떼껄룩: 근거 중심 읽기 전용 검증")
    sub = parser.add_subparsers(dest="action", required=True)
    audit = sub.add_parser("audit", help="로컬 프로젝트 검증")
    audit.add_argument("path")
    audit.add_argument("--contracts",help="별도 사용자 입력/기대값 JSON; 대상 폴더 밖의 파일만 허용")
    audit.add_argument("--output", default="reports")
    audit.add_argument("--sandbox-image", help="명시적으로 격리 실행 활성화. 미리 설치된 신뢰할 이미지의 sha256:... ID")
    audit.add_argument("--suite", choices=("python-unittest", "node-test", 'ts-typecheck', 'node-lint'), default="python-unittest")
    web = sub.add_parser("web", help="한국어 로컬 화면 열기")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--output", default="reports")
    web.add_argument("--open", action="store_true")
    args = parser.parse_args()
    try:
        if args.action == "web":
            serve(args.port, args.output, args.open)
            return 0
        contracts={}
        if args.contracts:
            contract_path=Path(args.contracts).resolve()
            if contract_path.is_relative_to(Path(args.path).resolve()) or contract_path.stat().st_size>100000:raise ValueError('INVALID_CONTRACT_FILE')
            contracts=json.loads(contract_path.read_text(encoding='utf8'))
            if not isinstance(contracts,dict):raise ValueError('INVALID_CONTRACT')
        report, directory = Auditor(contracts=contracts).run(args.path, args.output, progress=lambda stage: print(stage), sandbox_image=args.sandbox_image, suite=args.suite)
        print("\n떼껄룩 결과")
        for status, count in report.summary.items():
            print(f"{status}: {count}")
        print(f"보고서: {directory / 'report.html'}")
        print(f"원본: {report.integrity['status']}")
        return 2 if report.integrity["status"] != "UNCHANGED" else 1 if report.summary["CONFIRMED"] else 0
    except (OSError, ValueError):
        print("검증을 완료하지 못했습니다. 경로·권한·용량·격리 설정을 확인하세요. 보고서 위치는 대상 폴더 밖이어야 합니다.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
