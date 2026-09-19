import html
import json
from pathlib import Path

from .safety import redact
from .schema import Report

LABELS={'CONFIRMED':'🔴 실제로 확인된 문제','UNCONFIRMED':'🟡 아직 확인하지 못한 의심','REFUTED':'⚪ 검사해보니 문제가 아니었던 의심','NEEDS_HUMAN':'👤 사람이 판단해야 하는 항목'}


def sanitize(value):
    if isinstance(value,str):return redact(value)
    if isinstance(value,dict):return {redact(str(k)):sanitize(v) for k,v in value.items()}
    if isinstance(value,list):return [sanitize(v) for v in value]
    return value


def render(report:Report)->str:
    esc=lambda x:html.escape(redact(str(x)))
    cards={}
    for c,ch,p,v in zip(report.claims,report.challenges,report.plans,report.verdicts):
        evidence=[sanitize(e.__dict__) for e in report.evidence if e.claim_id==c.id]
        proof='<p>객관적 증거 없음 — 안전하게 입증하지 못했습니다.</p>' if v.status=='UNCONFIRMED' else ''
        technical='<pre>'+esc(json.dumps(evidence,ensure_ascii=False,indent=2))+'</pre>' if evidence else '<p>객관적 증거 없음</p>'
        card=f'''<article><p class="tag">{esc(LABELS[v.status])} · {esc(v.status)}</p><h3>{esc(c.title)}</h3><p class="muted">{esc(c.file)}:{c.line} · {esc(c.id)}</p>
<h4>무슨 문제인가</h4><p>{esc(c.impact)}</p><h4>왜 처음 의심했나</h4><p>{esc(c.reason)}</p>
<h4>반대 검토는 무엇이었나</h4><p>{esc(ch.counterargument)}</p><p>{esc(', '.join(ch.defense_locations))}</p>
<h4>어떻게 실제로 검사했나</h4><p>{esc(p.description)}</p><h4>무슨 결과가 나왔나 · 왜 이 판정인가</h4><p>{esc(v.explanation)}</p>{proof}
<h4>개발자에게 전달할 내용</h4><textarea readonly aria-label="개발자에게 전달할 내용">{esc(v.developer_note)}</textarea>
<details><summary>기술 증거 펼치기</summary>{technical}</details></article>'''
        cards[c.id]=(v.status,card)
    sections=[]
    groups=report.groups or [{'title':'개별 검토','claim_ids':list(cards),'locations':{},'statuses':report.summary,'note':''}]
    for g in groups:
        confirmed=''.join(cards[c][1] for c in g['claim_ids'] if cards[c][0]=='CONFIRMED')
        refuted=''.join(cards[c][1] for c in g['claim_ids'] if cards[c][0]=='REFUTED')
        other=''.join(cards[c][1] for c in g['claim_ids'] if cards[c][0] not in {'CONFIRMED','REFUTED'})
        locations=' · '.join(f'{file}: {count}곳' for file,count in g['locations'].items())
        counts=' · '.join(f'{key} {value}' for key,value in g['statuses'].items())
        sections.append(f'''<section><h2>{esc(g['title'])} — {len(g['claim_ids'])}곳</h2><p>{esc(counts)}</p><p class="muted">{esc(locations)}</p><p class="muted">{esc(g['note'])}</p>{confirmed}
{f'<details><summary>⚪ 반증된 의심 {g["statuses"].get("REFUTED",0)}건 보기</summary>{refuted}</details>' if refuted else ''}
{f'<details><summary>남은 의심·사람 검토 세부 보기</summary>{other}</details>' if other else ''}</section>''')
    summary=''.join(f'<span>{label} <b>{report.summary[key]}</b>개</span>' for key,label in LABELS.items())
    real_calls=sum(x.get('completed_calls',0) for x in report.project.get('llm_usage',{}).values())
    origin='AI와 구조 탐색' if real_calls else '오프라인 구조 탐색'
    narrative=f'{origin}에서 처음 {len(report.claims)}개를 의심했습니다. 반박과 객관적 검사를 거친 뒤 {report.summary["CONFIRMED"]}개가 지원 범위에서 문제로 확인되었습니다.'
    if not report.summary['CONFIRMED']:
        narrative+=' 현재 검사 범위에서는 실제 문제로 확인된 항목이 없습니다.'
    suite=[sanitize(e.__dict__) for e in report.evidence if e.claim_id is None]
    details={'project':report.project,'suite':suite,'metrics':report.metrics}
    return f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>떼껄룩 검사 결과</title>
<style>body{{font:16px/1.7 system-ui,sans-serif;max-width:960px;margin:32px auto;padding:0 20px;color:#202932;background:#f8fafb}}h1{{font-size:30px}}h2{{font-size:21px}}h3{{font-size:18px}}h4{{margin-bottom:0}}section,.summary{{background:white;border:1px solid #dce3e8;border-radius:12px;padding:22px;margin:20px 0}}article{{border-top:1px solid #dce3e8;padding:18px 0}}.summary span{{display:inline-block;margin:8px 20px 8px 0}}.muted{{color:#526472;font-size:14px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef2f5;padding:15px}}details{{margin:14px 0}}summary{{cursor:pointer;font-weight:650}}textarea{{width:100%;min-height:100px;box-sizing:border-box;font:14px/1.6 system-ui;padding:10px}}p{{overflow-wrap:anywhere}}.tag{{font-weight:700}}</style>
<h1>떼껄룩 검사 결과 <small>Take a Look v0.3 Alpha</small></h1><div class="summary">{summary}<p>{esc(narrative)}</p></div>
<p>의심 개수는 실제 문제 개수가 아닙니다. 문제가 0개여도 전체 검증 통과를 뜻하지 않습니다.</p><p>{esc(report.project['coverage'])}</p>
<p>실행 방식: {esc(report.project.get("execution_mode","NO_EXECUTION"))}</p><p>발견 출처: 규칙 {report.metrics.get("rule_initial_claims",0)} · LLM {report.metrics.get("llm_initial_claims",0)} · 겹침 {report.metrics.get("overlap",0)}</p><p>실제 LLM 완료 호출: {real_calls}회 · 원본 보존: {esc(report.integrity['status'])}</p>
{''.join(sections) if report.claims else '<section>지원 범위에서 의심을 찾지 못했습니다. 전체 검증 통과를 뜻하지 않습니다.</section>'}
<details><summary>기존 테스트·검사 범위·품질 지표</summary><pre>{esc(json.dumps(details,ensure_ascii=False,indent=2))}</pre></details><details><summary>감사 기록</summary><pre>{esc(json.dumps(report.audit,ensure_ascii=False,indent=2))}</pre></details></html>'''


def save(report:Report,directory:Path):
    directory.mkdir(parents=True,exist_ok=False)
    (directory/'report.json').write_text(json.dumps(sanitize(report.to_dict()),ensure_ascii=False,indent=2),encoding='utf8')
    (directory/'report.html').write_text(render(report),encoding='utf8')
    (directory/'audit.jsonl').write_text('\n'.join(json.dumps(sanitize(e),ensure_ascii=False) for e in report.audit)+'\n',encoding='utf8')
    (directory/'regression-candidates.json').write_text(json.dumps(sanitize(report.regression_candidates),ensure_ascii=False,indent=2),encoding='utf8')
