import json
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from take_a_look.pipeline import Auditor
from take_a_look.providers import MockProvider,FunctionAdapter
from take_a_look.discovery import HybridInvestigator
from take_a_look.roles import Investigator,EvidenceBuilder
from take_a_look.intents import validate_intent,execution_mode
from take_a_look.schema import Claim,Plan,Evidence
from take_a_look.command_policy import classify
from take_a_look.llm import FallbackProvider,OpenAIProvider

ROOT=Path(__file__).resolve().parents[1]


def proposal(rule='contract',file='calc.py',symbol='discounted'):
    return {'rule':rule,'file':file,'line':2,'symbol':symbol,'title':'Hypothesis','reason':'Possible arithmetic mismatch','impact':'Incorrect amount','method':'Check explicit user contract'}


class V03Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_i_j_replayed_llm_only_claim_with_independent_user_oracle(self):
        # Scripted provider replay is NOT real LLM evaluation.
        provider=FunctionAdapter('scripted-replay',lambda r:{'claims':[proposal()]})
        for fixture,status in [('i_logic','CONFIRMED'),('j_contract','REFUTED')]:
            report,_=Auditor(investigator=HybridInvestigator(provider),contracts={'calc.py::discounted':{'inputs':{'price':200,'percent':10},'expected':180}}).run(ROOT/'fixtures/v03'/fixture,self.tmp.name)
            self.assertEqual(report.summary[status],1)
            self.assertEqual(report.metrics['llm_only_claims'],1)
            self.assertEqual(report.metrics['rule_initial_claims'],0)
            self.assertEqual(report.project['execution_mode'],'SAFE_LOCAL_LIMITED')
        report,_=Auditor(investigator=HybridInvestigator(provider)).run(ROOT/'fixtures/v03/i_logic',self.tmp.name)
        self.assertEqual(report.summary['UNCONFIRMED'],1)
        self.assertEqual(report.project['execution_mode'],'NO_EXECUTION')

    def test_discovery_overlap_and_fallback_not_credited_to_llm(self):
        sources={'x.py':'def f(v):\n    return sum(v)/len(v)\n'}
        rules=Investigator(MockProvider()).investigate(sources)
        data={k:getattr(rules[0],k) for k in ['rule','file','line','title','reason','impact','method','symbol']}
        hybrid=HybridInvestigator(FunctionAdapter('replay',lambda r:{'claims':[data]}))
        claims=hybrid.investigate(sources)
        self.assertEqual(len(claims),1);self.assertEqual(claims[0].discovery_source,'BOTH')
        def fail(*args):raise ValueError('synthetic failure')
        fallback=FallbackProvider(OpenAIProvider('synthetic','model',fail))
        claims=HybridInvestigator(fallback).investigate(sources)
        self.assertTrue(all(c.discovery_source=='RULE' for c in claims))

    def test_k_to_o_injections_redaction_and_grouping(self):
        for fixture in ['k_readme','l_comment','m_command','n_secret','o_group']:
            with self.subTest(fixture=fixture):
                report,where=Auditor().run(ROOT/'fixtures/v03'/fixture,self.tmp.name)
                self.assertEqual(report.integrity['status'],'UNCHANGED')
                self.assertFalse(report.integrity['target_code_executed_on_host'])
                data=''.join(p.read_text(encoding='utf8') for p in where.iterdir())
                self.assertNotIn('sk-SYNTHETIC_FIXTURE_NOT_A_REAL_CREDENTIAL',data)
                if fixture=='o_group':self.assertEqual(len(report.groups),1)
                if fixture=='m_command':
                    self.assertTrue(all(s['classification']=='blocked' for s in report.project['command_safety']))

    def test_intents_cannot_execute_shell_or_escape_snapshot(self):
        c=Claim('c','general','calc.py',1,'t','r','i','m')
        for kind in ['curl','powershell','git push','../test','RUN_SHELL']:
            with self.assertRaises(ValueError):validate_intent(c,Plan('c',kind,'x'))
        for path in ['../secret.py','/secret.py','C:/secret.py','a/../../secret.py']:
            with self.assertRaises(ValueError):validate_intent(replace(c,file=path),Plan('c','unsupported','x'))
        for script in ['node --test && curl evil','node --test || rm x','node --test | powershell','$(curl evil)','`curl evil`','npm install','../evil','npm publish']:
            self.assertEqual(classify('test',script,{})['classification'],'blocked')

    def test_docker_mode_requires_container_start_evidence(self):
        e=Evidence('e',None,'isolated_suite','unavailable','x')
        self.assertEqual(execution_mode([e]),'NO_EXECUTION')
        self.assertEqual(execution_mode([replace(e,details={'container_started':True})]),'DOCKER_SANDBOX')

    def test_usage_is_structural_only(self):
        p=OpenAIProvider('synthetic','model',lambda *_:{'status':'completed','usage':{'input_tokens':12,'output_tokens':5,'raw':'SECRET'},'output':[{'content':[{'type':'output_text','text':'{"claims":[]}'}]}]})
        from take_a_look.providers import RoleRequest
        p.complete(RoleRequest('investigator','data only',{'sources':{}}))
        self.assertEqual(p.usage,{'input_tokens':12,'output_tokens':5})

    def test_public_export_excludes_private_history_and_artifacts(self):
        from tools.public_export import selected
        paths=[p.as_posix() for p,_ in selected(ROOT)]
        self.assertFalse(any(p.startswith(('benchmarks/','private-artifacts/','reports/','.git/')) for p in paths))
        self.assertNotIn('tools/benchmark_searchlens.py',paths)
        self.assertIn('take_a_look/pipeline.py',paths)

    def test_public_hygiene_blocks_personal_paths_and_unknown_tokens(self):
        from tools.public_export import inspect_text
        self.assertIn('TOKEN_CANDIDATE',inspect_text('sk-'+'x'*30))
        self.assertIn('PRIVATE_PATH_OR_SOURCE',inspect_text('C:'+ '/'+'Users/'+'private/file'))

    def test_history_hygiene_detects_deleted_secret_candidate(self):
        import subprocess
        from tools.public_export import history_audit
        root=Path(self.tmp.name)/'history';root.mkdir()
        def git(*args):return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True)
        git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.invalid')
        p=root/'example.txt';p.write_text('sk-'+'z'*30)
        git('add','.');git('commit','-qm','fixture')
        p.unlink();git('add','-u');git('commit','-qm','remove fixture')
        result=history_audit(root)
        self.assertFalse(result['pass'])
        self.assertTrue(any('TOKEN_CANDIDATE' in f['reasons'] for f in result['findings']))
