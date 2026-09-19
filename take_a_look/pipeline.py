from datetime import datetime, timezone
import time
from .discovery import HybridInvestigator, discovery_metrics
from .intents import execution_mode
from dataclasses import replace
import json
from pathlib import Path
from typing import Callable
from uuid import uuid4

from .mapper import ProjectMapper
from .providers import MockProvider
from .qa import DeterministicQA
from .report import save
from .roles import Challenger, EvidenceBuilder, EvidenceJudge, Investigator
from .runner import run_suite
from .safety import collect, hashes, is_link, outside_target, text_sources
from .schema import Report, Status
from .llm import configured_provider
from .grouping import group_claims, metrics
from .safety import redact
from .context import review_context


class Auditor:
    def __init__(self, investigator=None, challenger=None, builder=None, qa=None, judge=None, contracts=None):
        self.investigator = investigator or HybridInvestigator(configured_provider('investigator'))
        self.challenger = challenger or Challenger(configured_provider('challenger'))
        self.builder = builder or EvidenceBuilder()
        self.qa = qa or DeterministicQA()
        self.judge = judge or EvidenceJudge()
        if isinstance(self.qa,DeterministicQA):self.qa.contracts=contracts or {}

    def run(self, project: str | Path, output: str | Path, progress: Callable | None = None, sandbox_image=None, suite="python-unittest") -> tuple[Report, Path]:
        root = Path(project).expanduser().resolve()
        destination = Path(output).expanduser().resolve()
        outside_target(root, destination)
        audit = []
        started=time.monotonic()
        try:
            return self._run(project, output, progress, sandbox_image, suite, audit, started)
        except Exception as exc:
            audit.append({"sequence": len(audit) + 1, "time": datetime.now(timezone.utc).isoformat(), "stage": "Run failed", "reason_code": type(exc).__name__})
            # No raw exception, target path, source or provider response is logged.
            try:
                failure_dir = destination / ("failed-" + uuid4().hex)
                failure_dir.mkdir(parents=True, exist_ok=False)
                (failure_dir / "audit.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in audit) + "\n", encoding="utf-8")
            except OSError:
                pass
            raise

    def _run(self, project, output, progress, sandbox_image, suite, audit, started):
        original = Path(project).expanduser().absolute()
        if not original.is_dir() or is_link(original):
            raise ValueError("실제 로컬 프로젝트 폴더를 입력하세요. 링크 폴더는 지원하지 않습니다.")
        root, destination = original.resolve(), Path(output).expanduser().resolve()
        outside_target(root, destination)
        run_id = uuid4().hex
        directory = destination / run_id

        def event(stage, **detail):
            audit.append({"sequence": len(audit) + 1, "time": datetime.now(timezone.utc).isoformat(), "stage": stage, **detail})
            if progress:
                progress(stage)

        event("Project Mapper")
        files, skipped = collect(root)
        before = hashes(files)
        sources = text_sources(files)
        analysis_skipped = skipped + (["UTF-8이 아닌 파일은 분석에서 제외"] if len(sources) != len(files) else [])
        project_map = ProjectMapper().map(sources, analysis_skipped)
        for lock,manager in [('package-lock.json','npm'),('pnpm-lock.yaml','pnpm'),('yarn.lock','yarn')]:
            if (root/lock).is_file() and manager not in project_map['package_managers']:
                project_map['package_managers'].append(manager)
        project_map['dependencies_present']=(root/'node_modules').is_dir()
        project_map["providers"] = {role: getattr(getattr(obj, "provider", None), "name", "custom-role") for role, obj in (("investigator", self.investigator), ("challenger", self.challenger))}
        project_map["offline_mock"] = all(isinstance(getattr(obj, "provider", None), MockProvider) for obj in (self.investigator, self.challenger))
        project_map['provider_fallbacks'] = {role:getattr(getattr(obj,'provider',None),'fallback_reason',None) for role,obj in [('investigator',self.investigator),('challenger',self.challenger)]}
        event("Snapshot", files=len(files), skipped_categories=len(skipped))
        event("Investigator")
        claims = self.investigator.investigate(sources)
        challenges, plans, evidence, verdicts = [], [], [], []
        event("Challenger", claims=len(claims))
        context_reviews={}
        for claim in claims:
            context_reviews[claim.id]=review_context(claim,sources)
            related=context_reviews[claim.id]['references']
            if isinstance(self.challenger,Challenger):
                challenges.append(self.challenger.challenge(claim, sources[claim.file],related))
            else:
                challenges.append(self.challenger.challenge(claim, sources[claim.file]))
            event("Challenge recorded", claim_id=claim.id)
        event("Evidence Builder")
        for claim, challenge in zip(claims, challenges):
            plan = self.builder.build(claim, challenge)
            plans.append(plan)
            event("Plan recorded", claim_id=claim.id, kind=plan.kind)
        event("Deterministic QA")
        if isinstance(self.qa,DeterministicQA):
            self.qa.workspace=destination/'.work'
        for claim, plan in zip(claims, plans):
            item = self.qa.run(claim, plan, sources[claim.file])
            source_lines=sources[claim.file].splitlines()
            excerpt='\n'.join(f'{i+1}: {redact(source_lines[i])}' for i in range(max(0,claim.line-3),min(len(source_lines),claim.line+2)))
            item=replace(item,details={**item.details,'source_excerpt':excerpt[:3000],'context_review':context_reviews[claim.id],'evidence_note':'소스 참조는 의심 위치를 설명하며, 그 자체가 버그 증거는 아닙니다.'})
            evidence.append(item)
            event("Evidence recorded", evidence_id=item.id, claim_id=claim.id, outcome=item.outcome)
        evidence.append(run_suite(files, sandbox_image, suite, target_root=root))
        event("Suite recorded", outcome=evidence[-1].outcome, exit_code=evidence[-1].exit_code)
        event("Evidence Judge")
        for claim in claims:
            verdict = self.judge.judge(claim, evidence)
            verdicts.append(verdict)
            event("Verdict recorded", claim_id=claim.id, status=verdict.status.value, evidence_ids=verdict.evidence_ids)
        after_files, after_skipped = collect(root)
        unchanged = before == hashes(after_files) and skipped == after_skipped
        integrity = {"status": "UNCHANGED" if unchanged else "CHANGED_DURING_AUDIT", "checked_files": len(before), "scope": "included regular file contents only; excluded secrets/binaries/dependencies not read", "target_code_executed_on_host": False}
        if not unchanged:
            # Snapshot findings must not be mistaken for findings about the new project state.
            project_map["warnings"].append("검사 중 원본이 변경되었습니다. 결과는 시작 시점 스냅샷에만 해당합니다. 다시 검사하세요.")
        event("Integrity checked", status=integrity["status"])
        regressions = []
        for claim, verdict in zip(claims, verdicts):
            if verdict.status == Status.CONFIRMED:
                e = next(e for e in evidence if e.claim_id == claim.id)
                node_cases=[case for case in e.details.get('cases',[]) if case.get('outcome')=='invalid_output']
                regressions.append({"claim_id": claim.id, "file": claim.file, "line": claim.line, "symbol": claim.symbol, "source_sha256": e.source_sha256, "inputs": e.details.get("inputs") or [o['input'] for case in node_cases for o in case.get('observations',[])], "observed": e.details.get("observations") or [o for case in node_cases for o in case.get('observations',[])], "next_action": "개발자가 입력 계약과 기대 결과를 정한 뒤 회귀 테스트로 옮기세요. 원본 테스트는 자동 변경하지 않습니다."})
        event("Human-readable Report")
        project_map['llm_usage']={role:{'attempted_calls':getattr(getattr(obj,'provider',None),'calls',0),'completed_calls':getattr(getattr(obj,'provider',None),'completed_calls',0),'fallback_calls':getattr(getattr(obj,'provider',None),'fallback_calls',0),'context_truncated':getattr(getattr(obj,'provider',None),'context_truncated',False)} for role,obj in [('investigator',self.investigator),('challenger',self.challenger)]}
        project_map['provider_fallbacks']={role:getattr(getattr(obj,'provider',None),'fallback_reason',None) for role,obj in [('investigator',self.investigator),('challenger',self.challenger)]}
        event('Provider usage',roles=project_map['llm_usage'],fallbacks=project_map['provider_fallbacks'])
        report = Report(run_id, project_map, claims, challenges, plans, evidence, verdicts, audit, integrity, regressions)
        report.groups=group_claims(claims,plans,verdicts)
        project_map['execution_mode']=execution_mode(evidence)
        project_map['duration_seconds']=round(time.monotonic()-started,3)
        project_map['token_usage']={role:getattr(getattr(obj,'provider',None),'usage',None) for role,obj in [('investigator',self.investigator),('challenger',self.challenger)]}
        project_map['estimated_api_cost']=None
        report.metrics={**metrics(verdicts,evidence,report.groups),**discovery_metrics(claims,verdicts)}
        save(report, directory)
        return report, directory
