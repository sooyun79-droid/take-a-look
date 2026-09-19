"""Versioned, serializable contracts across all pipeline boundaries."""

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Status(StrEnum):
    CONFIRMED = "CONFIRMED"
    REFUTED = "REFUTED"
    UNCONFIRMED = "UNCONFIRMED"
    NEEDS_HUMAN = "NEEDS_HUMAN"


@dataclass(frozen=True)
class Claim:
    id: str
    rule: str
    file: str
    line: int
    title: str
    reason: str
    impact: str
    method: str
    symbol: str = ""
    category: str = ""
    reasoning_summary: str = ""
    confidence: float | None = None
    evidence_refs: list[str] = field(default_factory=list)
    origin: str = "mock"
    provider_claim_id: str = ""
    suspected_lines: list[int] = field(default_factory=list)
    discovery_source: str = 'RULE'


@dataclass(frozen=True)
class Challenge:
    claim_id: str
    counterargument: str
    defense_locations: list[str] = field(default_factory=list)
    limitations: str = "반박 의견만으로 의심을 기각하지 않습니다."
    counter_evidence: list[str] = field(default_factory=list)
    verdict_recommendation: str = "UNCONFIRMED"
    verification_still_needed: list[str] = field(default_factory=list)
    checks: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Plan:
    claim_id: str
    kind: str
    description: str
    intent: str = 'NO_EXECUTION'


@dataclass(frozen=True)
class Evidence:
    id: str
    claim_id: str | None
    kind: str
    outcome: str
    description: str
    source_sha256: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    repetitions: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Verdict:
    claim_id: str
    status: Status
    explanation: str
    evidence_ids: list[str]
    developer_note: str
    manual_review: dict[str, str] = field(default_factory=lambda: {'status':'pending','note':''})


@dataclass
class Report:
    run_id: str
    project: dict[str, Any]
    claims: list[Claim]
    challenges: list[Challenge]
    plans: list[Plan]
    evidence: list[Evidence]
    verdicts: list[Verdict]
    audit: list[dict[str, Any]]
    integrity: dict[str, Any]
    regression_candidates: list[dict[str, Any]]
    schema_version: str = "3.0"
    groups: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result=asdict(self)
        for c in result['claims']:
            c.update(claim_id=c['id'],suspected_file=c['file'],suspected_lines=c['suspected_lines'] or [c['line']],explanation=c['reason'],possible_impact=c['impact'],proposed_verification=c['method'])
        for c in result['challenges']:
            c['challenge_summary']=c['counterargument']
        return result

    @property
    def summary(self) -> dict[str, int]:
        return {s.value: sum(v.status == s for v in self.verdicts) for s in Status}
