import {test} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
process.argv[2]=resolve('node_modules/typescript/lib/typescript.js');
process.argv[3]='library';
const {analyze}=await import('../take_a_look/node_worker.mjs');
const check=source=>analyze({source,file:'sample.ts',line:1});
test('empty reduce mean really yields NaN in native JS too',()=>{
 const actual=(values)=>values.reduce((a,b)=>a+b,0)/values.length;
 assert(Number.isNaN(actual([])));
 const r=check('function f(x:number[]) { return x.reduce((a,b)=>a+b,0)/x.length; }');
 assert.equal(r.outcome,'invalid_output');assert.equal(r.cases[0].observations.length,5);
 assert(r.cases[0].observations.every(x=>x.output==='NaN'));
});
test('ternary, early return and compound numeric guards refute',()=>{
 for(const s of ['function f(x:number[]){if(!x.length)return 0;return 0/x.length;}','const f=(x:number[])=>x.length ? 0/x.length : null;','const f=(x:number[])=>x.length>=3 ? 0/x.length : null;','function f(x:number[]){if(x.length===0)return null;return 1/x.length;}'])assert.equal(check(s).outcome,'refuted');
});
test('weak guard does not refute real NaN',()=>assert.equal(check('function f(x:number[]){if(x.length<0)return 0;return 0/x.length;}').outcome,'invalid_output'));
test('strings, comments and template text are not executable evidence',()=>{
 for(const s of ['// return 0 / values.length;','const s="0 / values.length";','const s=`0 / values.length`;'])assert.equal(check(s).outcome,'non_code');
});
test('external effects, loops, and object contracts fail closed',()=>{
 for(const s of ['function f(x:number[]){fetch("https://invalid");return 0/x.length;}','function f(x:number[]){while(true){}return 0/x.length;}','function f(x:{length:number}){return 0/x.length;}'])assert.equal(check(s).outcome,'unsupported');
});
test('all divisions on the same line are accounted for',()=>{
 const r=check('const f=(a:number[],b:number[])=>a.length ? 0/a.length : 0/b.length;');
 assert.equal(r.cases.length,2);assert.equal(r.outcome,'unsupported');
});
test('unrelated guard and inner shadow do not refute',()=>{
 assert.equal(check('function f(x:number[]){if(!x.length)return 0;{const x=[];return 0/x.length;}}').outcome,'unsupported');
 assert.equal(check('function f(x:number[],y:number[]){if(!y.length)return 0;return 0/x.length;}').outcome,'unsupported');
});
test('null-safe branch still has length proof',()=>assert.equal(check('const f=(x:number[])=>x.length > 0 && 0/x.length;').outcome,'refuted'));
test('a completed if block without return continues the function',()=>{
 assert.equal(check('function f(x:number[]){if(!x.length){const y=1;}return 0/x.length;}').outcome,'invalid_output');
});
test('unknown calls and alias mutations invalidate an earlier guard proof',()=>{
 for(const s of ['function f(x:number[]){if(!x.length)return 0;clear(x);return 0/x.length;}', 'function f(x:number[]){const y=x;if(!x.length)return 0;y.length=0;return 0/x.length;}', 'function f(x:number[]){if(!x.length)return 0;return clear(x)/x.length;}'])assert.equal(check(s).outcome,'unsupported');
});
test('shadowed Math is not treated as the trusted builtin',()=>{
 assert.equal(check('const Math={round:()=>0};function f(x:number[]){return Math.round(0/x.length);}').outcome,'unsupported');
});
