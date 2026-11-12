import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

const wrapper=resolve('bin/take-a-look.mjs');
const run=(args,cwd=tmpdir())=>spawnSync(process.execPath,[wrapper,...args],{cwd,encoding:'utf8'});

test('one-line wrapper forwards arguments to the python auditor',()=>{
  const r=run(['--help']);
  assert.equal(r.status,0);
  assert.match(r.stdout,/usage: take-a-look/);
  assert.match(r.stdout,/audit/);
});

test('one-line wrapper keeps the auditor exit code and the caller folder',()=>{
  const cwd=mkdtempSync(join(tmpdir(),'take-a-look-'));
  const r=run(['audit',resolve('fixtures/a_bug')],cwd);
  assert.equal(r.status,1);                       // CONFIRMED finding in the fixture
  assert.match(r.stdout,/CONFIRMED: 1/);
  assert.ok(r.stdout.includes(join(cwd,'reports')));  // reports stay in the caller folder
});

test('one-line wrapper reports an unusable target with exit code 2',()=>{
  const r=run(['audit',join(tmpdir(),'take-a-look-missing-target')]);
  assert.equal(r.status,2);
  assert.match(r.stderr,/검증을 완료하지 못했습니다/);
});
