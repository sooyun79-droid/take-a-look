import json
from pathlib import PurePosixPath
from .command_policy import classify


class ProjectMapper:
    def map(self, sources: dict[str, str], skipped: list[str]) -> dict:
        names = set(sources)
        python = any(n.endswith(".py") for n in names)
        node = "package.json" in names or any(n.endswith((".js", ".ts", ".tsx", ".jsx")) for n in names)
        deps: set[str] = set()
        scripts = []
        invalid = []
        classified = []
        if "package.json" in sources:
            try:
                package = json.loads(sources["package.json"])
                if not isinstance(package, dict):
                    raise ValueError()
                for key in ("dependencies", "devDependencies"):
                    part = package.get(key, {})
                    if isinstance(part, dict):
                        deps.update(part)
                raw_scripts = package.get("scripts", {})
                if isinstance(raw_scripts, dict):
                    scripts = [s for s in ("test", "build", "lint", "typecheck") if isinstance(raw_scripts.get(s), str)]
                    classified = [classify(s, value, raw_scripts) for s,value in raw_scripts.items()]
            except (ValueError, TypeError):
                invalid.append("package.json 형식을 읽지 못했습니다.")
        py_config = "\n".join(sources.get(n, "") for n in ("pyproject.toml", "requirements.txt", "setup.cfg"))
        return {
            "languages": (["Python"] if python else []) + (["Node/TypeScript"] if node else []),
            "frameworks": sorted(deps & {"next", "react", "vue", "express", "fastify", "nestjs"}) + [f for f in ("django", "flask", "fastapi") if f in py_config.lower()],
            "package_managers": [v for k, v in (("package-lock.json", "npm"), ("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("uv.lock", "uv"), ("poetry.lock", "poetry"), ("requirements.txt", "pip"), ("pyproject.toml", "Python project")) if k in names],
            "test_frameworks": sorted(deps & {"jest", "vitest", "mocha"}) + (["node:test"] if any('node:test' in t for n,t in sources.items() if n.endswith(('.ts','.js','.mjs'))) else []) + (["pytest"] if "pytest" in py_config else []) + (["unittest (추정)"] if any("unittest" in t for n, t in sources.items() if n.endswith(".py")) else []),
            "database": sorted(deps & {"prisma", "pg", "mysql2", "mongoose", "sqlite3"}) + [f for f in ("sqlalchemy", "sqlite3", "psycopg") if f in py_config],
            "docker": any(PurePosixPath(n).name == "Dockerfile" or "compose" in PurePosixPath(n).name for n in names),
            "file_count": len(sources),
            "commands": [{"id": "python-unittest", "display": "python -B -m unittest discover -v", "execution": "격리 실행을 켠 경우에만"}] if python else [],
            "suggested_scripts": [{"name": s, "execution": "임의 package script는 자동 실행 금지"} for s in scripts],
            "typecheck": "tsconfig.json" in names or "mypy" in py_config or "pyright" in py_config,
            'command_safety': classified,
            'source_structure': {'src_files':sum(n.startswith('src/') for n in names),'test_files':sum('.test.' in n or '.spec.' in n or n.startswith('tests/') for n in names)},
            'tsconfig_files': sorted(n for n in names if PurePosixPath(n).name.startswith('tsconfig') and n.endswith('.json')),
            'build': 'build' in scripts,
            "lint": bool(deps & {"eslint", "biome"}) or "ruff" in py_config,
            "skipped": skipped,
            "warnings": invalid,
            "coverage": "Python 제한 검사 + Node/TypeScript AST 방어 분기·순수 함수 경계값 재현. 실제 앱 전체 실행/입력 계약은 별도 확인이 필요합니다.",
        }
