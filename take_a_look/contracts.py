"""Explicit caller-supplied oracles, never expectations invented by an LLM."""
import ast
import math
from .probes import tree,validate,Evaluator,Unsupported


def bounded(value):
    if type(value) in (bool,int,float):
        return math.isfinite(value) and abs(value)<=1e6
    return isinstance(value,list) and len(value)<=16 and all(type(x) in (bool,int,float) and math.isfinite(x) and abs(x)<=1e6 for x in value)


def check_contract(source,claim,contracts):
    entry=contracts.get(claim.file+'::'+claim.symbol)
    if not isinstance(entry,dict) or set(entry)!={'inputs','expected'}:
        raise Unsupported('USER_CONTRACT_REQUIRED')
    env=entry['inputs'];expected=entry['expected']
    if not isinstance(env,dict) or len(env)>4 or not all(isinstance(k,str) and bounded(v) for k,v in env.items()) or not bounded(expected):
        raise Unsupported('CONTRACT_INVALID')
    module=tree(source)
    # Full module execution is not modeled: reject effects and global rebinding.
    if any(not isinstance(n,ast.FunctionDef) for n in module.body):
        raise Unsupported('MODULE_EFFECT_UNSUPPORTED')
    if len({n.name for n in module.body})!=len(module.body) or any(n.name in {'sum','len'} for n in module.body):
        raise Unsupported('REBINDING_UNSUPPORTED')
    functions=[n for n in module.body if n.name==claim.symbol and n.lineno<=claim.line<=n.end_lineno]
    if len(functions)!=1:raise Unsupported('CONTRACT_TARGET_MISMATCH')
    fn=functions[0];validate(fn)
    if set(env)!={a.arg for a in fn.args.args}:raise Unsupported('CONTRACT_ARGUMENT_MISMATCH')
    observed=[Evaluator(env).block(fn.body)[1] for _ in range(3)]
    if not all(bounded(v) for v in observed):raise Unsupported('CONTRACT_RESULT_UNSUPPORTED')
    return {'engine':'user-contract-python-ast-v1','oracle_source':'EXPLICIT_USER_CONTRACT','inputs':env,'expected':expected,'observations':observed,'scope':'명시적으로 제공한 입력/기대값 계약에 한정된 함수 본문 계산. 앱 전체의 제품 의도를 입증하지 않습니다.'}
