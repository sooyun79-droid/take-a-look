import hashlib
import platform

from .probes import Unsupported, probe, tree
from .schema import Evidence


class DeterministicQA:
    def __init__(self):
        self.workspace = None
        self.contracts = {}

    def run(self, claim, plan, source):
        from .intents import validate_intent
        validate_intent(claim,plan)
        if claim.id != plan.claim_id:
            raise ValueError("plan mismatch")
        digest = hashlib.sha256(source.encode()).hexdigest()
        base = dict(id="E-" + claim.id, claim_id=claim.id, kind=plan.kind, description=plan.description, source_sha256=digest)
        if plan.kind == 'contract_check':
            from .contracts import check_contract
            try:
                details=check_contract(source,claim,self.contracts)
                return Evidence(**base,outcome='observed',repetitions=3,details=details)
            except (Unsupported,SyntaxError,ValueError,TypeError,ZeroDivisionError,KeyError,OverflowError):
                return Evidence(**base,outcome='not_run',details={'reason_code':'USER_CONTRACT_MISSING_OR_UNSUPPORTED'})
        if plan.kind == 'node_boundary':
            from .node_qa import node_probe
            if not claim.file.endswith(('.js','.jsx','.ts','.tsx')):
                return Evidence(**base,outcome='unsupported',details={'reason_code':'LANGUAGE_MISMATCH'})
            result=node_probe(source,claim.file,claim.line,self.workspace)
            return Evidence(**base,outcome=result['outcome'],exit_code=result.get('exit_code'),repetitions=result.get('repetitions',0),stdout='구조화된 JavaScript 실행 관찰은 details.cases를 확인하세요.',details=result)
        if plan.kind in {"python_parse", "bounded_ast"} and not claim.file.endswith(".py"):
            return Evidence(**base, outcome="unsupported", details={"reason_code": "LANGUAGE_MISMATCH"})
        if plan.kind == "human_review":
            return Evidence(**base, outcome="human_required")
        if plan.kind == "python_parse":
            try:
                tree(source)
                return Evidence(**base, outcome="parsed", repetitions=1, details={"python": platform.python_version()})
            except SyntaxError as exc:
                return Evidence(**base, outcome="syntax_error", repetitions=1, details={"line": exc.lineno, "python": platform.python_version(), "error_type": "SyntaxError"})
            except Unsupported:
                return Evidence(**base, outcome="unsupported")
        if plan.kind == "bounded_ast":
            try:
                result = probe(source, claim.symbol, claim.line)
                return Evidence(**base, outcome="observed", repetitions=3, details=result)
            except (Unsupported, SyntaxError, TypeError, ValueError, RecursionError, KeyError, OverflowError):
                return Evidence(**base, outcome="unsupported", details={"reason_code": "OUTSIDE_SAFE_SUBSET"})
        return Evidence(**base, outcome="not_run")
