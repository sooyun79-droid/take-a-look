"""Closed verification vocabulary. A provider can never specify executable argv."""
from pathlib import PurePosixPath

INTENTS={'python_parse':'CHECK_SYNTAX','bounded_ast':'CHECK_BOUNDARY','node_boundary':'CHECK_BOUNDARY','contract_check':'CHECK_CONTRACT','human_review':'HUMAN_REVIEW','unsupported':'NO_EXECUTION'}


def validate_intent(claim,plan):
    path=PurePosixPath(claim.file.replace('\\','/'))
    if path.is_absolute() or '..' in path.parts or ':' in claim.file:
        raise ValueError('INTENT_TARGET_INVALID')
    expected=INTENTS.get(plan.kind)
    if expected is None or plan.intent not in {'NO_EXECUTION',expected}:
        raise ValueError('INTENT_NOT_ALLOWED')
    if claim.id!=plan.claim_id:
        raise ValueError('INTENT_CLAIM_MISMATCH')


def execution_mode(evidence):
    if any(e.kind=='isolated_suite' and e.details.get('container_started') for e in evidence):
        return 'DOCKER_SANDBOX'
    if any(e.claim_id and (e.repetitions>0 or e.outcome=='syntax_error') for e in evidence):
        return 'SAFE_LOCAL_LIMITED'
    return 'NO_EXECUTION'
