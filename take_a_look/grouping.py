from collections import Counter
from hashlib import sha256


def group_claims(claims, plans, verdicts):
    groups={}
    for c,p,v in zip(claims,plans,verdicts):
        pattern={'js_boundary':'js:length-division','boundary_division':'python:zero-denominator','syntax':'python:syntax','swallowed_error':'python:swallowed-error','product_policy':'policy:rounding'}.get(c.rule,f'unclassified:{c.id}')
        fingerprint=sha256((pattern+'|'+p.kind).encode()).hexdigest()[:16]
        g=groups.setdefault(fingerprint,{'id':'G-'+fingerprint,'fingerprint':pattern+'|'+p.kind,'title':{'js_boundary':'빈 목록 계산 관련 의심','boundary_division':'경계값 나눗셈 관련 의심'}.get(c.rule,c.title),'claim_ids':[],'locations':{},'statuses':{},'note':'같은 검증 패턴을 묶었습니다. 서로 다른 위치가 같은 실제 원인이라는 뜻은 아닙니다.'})
        g['claim_ids'].append(c.id)
        g['locations'][c.file]=g['locations'].get(c.file,0)+1
        g['statuses'][v.status.value]=g['statuses'].get(v.status.value,0)+1
    return list(groups.values())


def metrics(verdicts,evidence,groups):
    counts=Counter(v.status.value for v in verdicts); total=len(verdicts)
    reviewed=[v for v in verdicts if v.status=='CONFIRMED' and v.manual_review.get('status') in {'correct','false_positive'}]
    false=sum(v.manual_review['status']=='false_positive' for v in reviewed)
    return {'total_claims':total,**{s.lower():counts[s] for s in ['CONFIRMED','REFUTED','UNCONFIRMED','NEEDS_HUMAN']},'confirmation_rate':counts['CONFIRMED']/total if total else None,'refutation_rate':counts['REFUTED']/total if total else None,'unresolved_rate':(counts['UNCONFIRMED']+counts['NEEDS_HUMAN'])/total if total else None,'grouped_issues':len(groups),'executable_evidence_claims':len({e.claim_id for e in evidence if e.kind=='node_boundary' and e.exit_code==0 and e.repetitions>0}),'guard_evaluation_claims':len({e.claim_id for e in evidence if any(c.get('outcome')=='guard_refuted' for c in e.details.get('cases',[]))}),'function_reproduction_claims':len({e.claim_id for e in evidence if any(c.get('outcome') in {'invalid_output','boundary_refuted'} for c in e.details.get('cases',[]))}),'auditor_false_positive':false if reviewed else None,'confirmed_reviewed':len(reviewed),'confirmed_review_pending':counts['CONFIRMED']-len(reviewed),'false_positive_rate':false/len(reviewed) if reviewed else None,'ground_truth_note':'반증된 최초 의심은 CONFIRMED 오탐과 다릅니다. Ground truth/사람 검토 전 오탐률은 미측정입니다.'}
