"""Bounded context references are leads for review, not objective proof."""
import re
from .safety import redact


def review_context(claim,sources):
    source=sources[claim.file]
    prefix='\n'.join(source.splitlines()[:claim.line])
    names=re.findall(r'(?:function\s+|(?:const|let)\s+)([A-Za-z_$][\w$]*)',prefix)
    symbol=claim.symbol or (names[-1] if names else '')
    refs=[]
    if symbol:
        for file,text in sources.items():
            if file==claim.file:continue
            for i,line in enumerate(text.splitlines(),1):
                if re.search(r'\b'+re.escape(symbol)+r'\b',line):
                    refs.append({'file':file,'line':i,'text':redact(line)[:240],'kind':'test_reference' if any(s in file for s in ('test','spec','fixture')) else 'possible_caller_or_type_reference'})
                if len(refs)>=8:break
            if len(refs)>=8:break
    return {'symbol_hint':symbol,'references':refs,'input_contract':'not_proven','dead_code':'not_proven','runtime_scope':'JS primitive AST subset only','note':'문자열 검색으로 찾은 후보 문맥입니다. 호출 관계·테스트 커버리지의 증거로 쓰지 않습니다.'}
