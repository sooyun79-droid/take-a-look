// Trusted worker: parse untrusted code, never import/eval/execute it.
// All calculations dispatch through a closed AST interpreter using JS primitives.
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
const require = createRequire(import.meta.url);
const ts = require(process.argv[2]); // caller pins OUR toolchain, never the target's.
const K = ts.SyntaxKind;
const UNKNOWN = Symbol('unknown');
class Unsupported extends Error {}
const unwrap = n => {
  while (ts.isParenthesizedExpression(n) || ts.isAsExpression(n) || ts.isNonNullExpression(n) || ts.isTypeAssertionExpression(n)) n = n.expression;
  return n;
};
function expr(n, env, state, symbolic = false) {
  if (++state.steps > 3000) throw new Unsupported('STEP_LIMIT');
  n = unwrap(n);
  if (ts.isNumericLiteral(n)) {const x=Number(n.text); if(!Number.isFinite(x)||Math.abs(x)>1e10)throw new Unsupported('NUMBER_LIMIT'); return x;}
  if (n.kind === K.NullKeyword) return null;
  if (n.kind === K.TrueKeyword) return true;
  if (n.kind === K.FalseKeyword) return false;
  if (ts.isIdentifier(n)) return Object.hasOwn(env,n.text) ? env[n.text] : UNKNOWN;
  if (ts.isStringLiteral(n)) return symbolic ? UNKNOWN : n.text;
  if (ts.isPropertyAccessExpression(n)) {
    const key=n.getText(state.sf);
    if(Object.hasOwn(env,key))return env[key];
    const obj=expr(n.expression,env,state,symbolic);
    if(n.name.text==='length' && Array.isArray(obj))return obj.length;
    return UNKNOWN;
  }
  if (ts.isArrayLiteralExpression(n)) {
    if(n.elements.length>32)throw new Unsupported('ARRAY_LIMIT');
    return n.elements.map(x=>expr(x,env,state,symbolic));
  }
  if (ts.isPrefixUnaryExpression(n)) {
    const v=expr(n.operand,env,state,symbolic); if(v===UNKNOWN)return UNKNOWN;
    if(n.operator===K.ExclamationToken)return !v;
    if(typeof v!=='number')return UNKNOWN;
    if(n.operator===K.MinusToken)return -v;
    if(n.operator===K.PlusToken)return +v;
    throw new Unsupported('UNARY_UNSUPPORTED');
  }
  if (ts.isConditionalExpression(n)) {
    const c=expr(n.condition,env,state,symbolic);
    if(c===UNKNOWN)return UNKNOWN;
    return expr(c?n.whenTrue:n.whenFalse,env,state,symbolic);
  }
  if (ts.isBinaryExpression(n)) {
    const op=n.operatorToken.kind, a=expr(n.left,env,state,symbolic);
    if(op===K.AmpersandAmpersandToken){if(a!==UNKNOWN&&!a)return a;const b=expr(n.right,env,state,symbolic);return a===UNKNOWN?(b!==UNKNOWN&&!b?b:UNKNOWN):b;}
    if(op===K.BarBarToken){if(a!==UNKNOWN&&a)return a;const b=expr(n.right,env,state,symbolic);return a===UNKNOWN?(b!==UNKNOWN&&b?b:UNKNOWN):b;}
    const b=expr(n.right,env,state,symbolic); if(a===UNKNOWN||b===UNKNOWN)return UNKNOWN;
    let v;
    switch(op){
      case K.EqualsEqualsEqualsToken:v=a===b;break;
      case K.ExclamationEqualsEqualsToken:v=a!==b;break;
      case K.GreaterThanToken:v=a>b;break;
      case K.GreaterThanEqualsToken:v=a>=b;break;
      case K.LessThanToken:v=a<b;break;
      case K.LessThanEqualsToken:v=a<=b;break;
      default:
        if(typeof a!=='number'||typeof b!=='number')return UNKNOWN;
        switch(op){case K.PlusToken:v=a+b;break;case K.MinusToken:v=a-b;break;case K.AsteriskToken:v=a*b;break;case K.SlashToken:v=a/b;break;case K.PercentToken:v=a%b;break;default:throw new Unsupported('OPERATOR_UNSUPPORTED');}
    }
    if(n===state.target)state.trace.push({numerator:a,denominator:b,output:encode(v)});
    if(typeof v==='number'&&Number.isFinite(v)&&Math.abs(v)>1e12)throw new Unsupported('RESULT_LIMIT');
    return v;
  }
  if (!symbolic && ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression)) {
    const method=n.expression.name.text;
    if(ts.isIdentifier(n.expression.expression)&&n.expression.expression.text==='Math'&&['round','min','max','abs','floor','ceil'].includes(method)){
      const values=n.arguments.map(x=>expr(x,env,state));
      if(values.length>8||values.some(v=>typeof v!=='number'))return UNKNOWN;
      return Math[method](...values);
    }
    const values=expr(n.expression.expression,env,state);
    if(!Array.isArray(values)||values.length>32||!['reduce','filter','map'].includes(method))throw new Unsupported('CALL_UNSUPPORTED');
    const fn=n.arguments[0];
    if(!fn||!ts.isArrowFunction(fn)||ts.isBlock(fn.body)||fn.parameters.some(p=>!ts.isIdentifier(p.name)))throw new Unsupported('CALLBACK_UNSUPPORTED');
    const invoke=(...args)=>{const local={...env};fn.parameters.forEach((p,i)=>local[p.name.text]=args[i]);return expr(fn.body,local,state);};
    if(method==='filter')return values.filter(v=>{const r=invoke(v);if(r===UNKNOWN)throw new Unsupported('UNKNOWN_CALLBACK');return r;});
    if(method==='map')return values.map(v=>invoke(v));
    if(n.arguments.length!==2)throw new Unsupported('REDUCE_WITHOUT_INITIAL');
    return values.reduce((a,b)=>invoke(a,b),expr(n.arguments[1],env,state));
  }
  throw new Unsupported('EXPRESSION_UNSUPPORTED');
}
function block(body,env,state){
  for(const s of body.statements){
    if(ts.isReturnStatement(s))return {done:true,value:s.expression?expr(s.expression,env,state):null};
    if(ts.isIfStatement(s)){
      const c=expr(s.expression,env,state);if(c===UNKNOWN)throw new Unsupported('UNKNOWN_CONDITION');
      const branch=c?s.thenStatement:s.elseStatement;
      if(branch){const r=ts.isBlock(branch)?block(branch,env,state):block({statements:[branch]},env,state);if(r.done)return r;}
    }else if(ts.isVariableStatement(s)){
      for(const d of s.declarationList.declarations){if(!ts.isIdentifier(d.name)||!d.initializer)throw new Unsupported('DECLARATION_UNSUPPORTED');const v=expr(d.initializer,env,state);if(v===UNKNOWN)throw new Unsupported('UNKNOWN_VALUE');env[d.name.text]=v;}
    }else throw new Unsupported('STATEMENT_UNSUPPORTED');
  }
  return {done:false,value:null};
}
function encode(v){if(v===UNKNOWN)return 'UNKNOWN';if(typeof v==='number'&&!Number.isFinite(v))return String(v);if(typeof v==='string')return '[string omitted]';if(Array.isArray(v))return '[array]';return v;}
function within(n,parent){return n.pos>=parent.pos&&n.end<=parent.end;}
function functionOf(n){for(let p=n.parent;p;p=p.parent)if(ts.isFunctionDeclaration(p)||ts.isArrowFunction(p)||ts.isFunctionExpression(p)||ts.isMethodDeclaration(p))return p;return null;}
function exits(n){return ts.isReturnStatement(n)||ts.isThrowStatement(n)||ts.isBlock(n)&&n.statements.length>0&&exits(n.statements[n.statements.length-1]);}
function mutationBetween(node,base,from,to){
  let bad=false;
  function visit(n){
    if(n.getStart()<from||n.end>to){ts.forEachChild(n,visit);return;}
    // Unknown calls and alias writes can mutate the same array indirectly.
    if(ts.isBinaryExpression(n)&&n.operatorToken.kind>=K.FirstAssignment&&n.operatorToken.kind<=K.LastAssignment)bad=true;
    if(ts.isCallExpression(n))bad=true;
    if((ts.isPrefixUnaryExpression(n)||ts.isPostfixUnaryExpression(n))&&[K.PlusPlusToken,K.MinusMinusToken].includes(n.operator)&&n.operand.getText().includes(base))bad=true;
    ts.forEachChild(n,visit);
  }visit(node);return bad;
}
function guards(n,base,sf){
  const found=[],fn=functionOf(n);
  let bindings=0;
  function countBindings(p){if((ts.isVariableDeclaration(p)||ts.isParameter(p))&&ts.isIdentifier(p.name)&&p.name.text===base)bindings++;ts.forEachChild(p,countBindings);}
  countBindings(fn??sf);
  if(bindings>1)return found;
  const evaluate=c=>{try{return expr(c,{[base+'.length']:0},{steps:0,sf,trace:[]},true);}catch{return UNKNOWN;}};
  const add=(condition,excluded,kind)=>{
    const v=evaluate(condition);
    if(v!==UNKNOWN&&excluded(Boolean(v))&&!mutationBetween(fn??sf,base,condition.end,n.right.getStart()))found.push({line:sf.getLineAndCharacterOfPosition(condition.getStart()).line+1,condition:condition.getText(sf),observed:Boolean(v),kind});
  };
  for(let p=n.parent;p && p!==fn;p=p.parent){
    if(ts.isConditionalExpression(p))add(p.condition,v=>v?!within(n,p.whenTrue):!within(n,p.whenFalse),'conditional_branch');
    if(ts.isBinaryExpression(p)&&within(n,p.right)&&[K.AmpersandAmpersandToken,K.BarBarToken].includes(p.operatorToken.kind))add(p.left,v=>p.operatorToken.kind===K.AmpersandAmpersandToken?!v:v,'short_circuit');
    if(ts.isIfStatement(p))add(p.expression,v=>v?!within(n,p.thenStatement):!p.elseStatement||!within(n,p.elseStatement),'if_branch');
    if(ts.isBlock(p)){
      const containing=p.statements.find(s=>within(n,s));
      for(const s of p.statements){if(s===containing)break;if(ts.isIfStatement(s)&&exits(s.thenStatement))add(s.expression,v=>v,'earlier_return');}
    }
  }
  return found;
}
function one(n,sf){
  const rhs=unwrap(n.right),base=rhs.expression.getText(sf),fn=functionOf(n);
  let bindings=0;
  function count(p){if((ts.isVariableDeclaration(p)||ts.isParameter(p))&&ts.isIdentifier(p.name)&&p.name.text===base)bindings++;ts.forEachChild(p,count);}
  count(fn??sf);
  if(bindings>1)return {outcome:'unsupported',reason_code:'AMBIGUOUS_BINDING',line:sf.getLineAndCharacterOfPosition(n.getStart()).line+1};
  const guardsFound=guards(n,base,sf);
  const info={line:sf.getLineAndCharacterOfPosition(n.getStart()).line+1,column:sf.getLineAndCharacterOfPosition(n.getStart()).character+1,denominator:base+'.length',guards:guardsFound};
  if(guardsFound.length)return {...info,outcome:'guard_refuted',observations:Array.from({length:5},()=>({length:0,guard_result:guardsFound[0].observed,division_executed:false})),scope:'AST 지배 조건의 길이 0 분기 증명. 전체 함수 출력이나 앱 동작을 실행한 결과가 아닙니다.'};
  if(!fn||!fn.body||fn.parameters.length!==1||!ts.isIdentifier(fn.parameters[0].name)||fn.parameters[0].initializer||fn.parameters[0].dotDotDotToken)return {...info,outcome:'unsupported',reason_code:'FUNCTION_ISOLATION_UNSUPPORTED'};
  const param=fn.parameters[0],arrayType=param.type&&(ts.isArrayTypeNode(param.type)||ts.isTypeReferenceNode(param.type)&&param.type.typeName.getText()==='Array');
  if(param.type&&!arrayType)return {...info,outcome:'unsupported',reason_code:'INPUT_CONTRACT_UNKNOWN'};
  if(!arrayType&&param.name.text!==base)return {...info,outcome:'unsupported',reason_code:'INPUT_CONTRACT_UNKNOWN'};
  let unsafe=false,shadowedMath=false;
  function checkMath(p){
    if((ts.isVariableDeclaration(p)||ts.isParameter(p)||ts.isFunctionDeclaration(p)||ts.isImportClause(p)||ts.isImportSpecifier(p))&&p.name?.getText()==='Math')shadowedMath=true;
    if(ts.isBinaryExpression(p)&&p.operatorToken.kind>=K.FirstAssignment&&p.operatorToken.kind<=K.LastAssignment&&p.left.getText().startsWith('Math'))shadowedMath=true;
    ts.forEachChild(p,checkMath);
  }
  checkMath(sf);
  function preflight(p){
    if(ts.isBinaryExpression(p)&&p.operatorToken.kind>=K.FirstAssignment&&p.operatorToken.kind<=K.LastAssignment)unsafe=true;
    if(ts.isCallExpression(p)){
      const c=p.expression;
      if(!ts.isPropertyAccessExpression(c)||!['reduce','filter','map'].includes(c.name.text)&&!(c.expression.getText()==='Math'&&!shadowedMath&&['round','min','max','abs','floor','ceil'].includes(c.name.text)))unsafe=true;
    }
    ts.forEachChild(p,preflight);
  }
  preflight(fn.body);
  if(unsafe)return {...info,outcome:'unsupported',reason_code:'UNSUPPORTED_EFFECT_OR_BINDING'};
  const observations=[];
  try{
    for(let i=0;i<5;i++){
      const state={steps:0,sf,target:n,trace:[]},env={[param.name.text]:[]};
      const r=ts.isBlock(fn.body)?block(fn.body,env,state):{done:true,value:expr(fn.body,env,state)};
      if(r.value===UNKNOWN)throw new Unsupported('UNKNOWN_OUTPUT');
      observations.push({input:{[param.name.text]:[]},output:encode(r.value),division:state.trace});
    }
    const invalid=observations.every(o=>o.division.some(d=>['NaN','Infinity','-Infinity'].includes(d.output))&&['NaN','Infinity','-Infinity'].includes(o.output));
    const skipped=observations.every(o=>o.division.length===0);
    return {...info,outcome:invalid?'invalid_output':skipped?'boundary_refuted':'unsupported',observations,reason_code:invalid||skipped?null:'INVALID_OUTPUT_NOT_OBSERVED',scope:'허용된 함수 본문 AST를 JavaScript 연산으로 해석한 빈 배열 5회 결과. 원본 module import 및 앱 전체 실행은 하지 않습니다.'};
  }catch(e){return {...info,outcome:'unsupported',reason_code:e instanceof Unsupported?e.message:'INTERPRETER_ERROR'};}
}
export function analyze(request){
  if(typeof request.source!=='string'||request.source.length>256000||!Number.isInteger(request.line))throw new Unsupported('INVALID_REQUEST');
  const sf=ts.createSourceFile(request.file??'target.ts',request.source,ts.ScriptTarget.Latest,true,(request.file??'').endsWith('tsx')?ts.ScriptKind.TSX:ts.ScriptKind.TS);
  if(sf.parseDiagnostics.length)return {outcome:'unsupported',reason_code:'TS_PARSE_ERROR',cases:[]};
  const nodes=[];
  function walk(n){if(ts.isBinaryExpression(n)&&n.operatorToken.kind===K.SlashToken){const rhs=unwrap(n.right);if(ts.isPropertyAccessExpression(rhs)&&rhs.name.text==='length'&&ts.isIdentifier(rhs.expression)&&sf.getLineAndCharacterOfPosition(n.operatorToken.getStart()).line+1===request.line)nodes.push(n);}ts.forEachChild(n,walk);}walk(sf);
  if(!nodes.length)return {outcome:'non_code',reason_code:'NO_EXECUTABLE_LENGTH_DIVISION_AT_LINE',cases:[]};
  const cases=nodes.map(n=>one(n,sf));
  return {outcome:cases.some(c=>c.outcome==='invalid_output')?'invalid_output':cases.every(c=>['guard_refuted','boundary_refuted'].includes(c.outcome))?'refuted':'unsupported',cases,engine:'typescript-ast-js-interpreter-v2',typescript:ts.version,repetitions:cases.some(c=>c.observations?.length===5)?5:0};
}
if(process.argv[3]!=='library'){
  try{const input=readFileSync(0,'utf8');if(input.length>300000)throw new Unsupported('INPUT_LIMIT');process.stdout.write(JSON.stringify(analyze(JSON.parse(input))));}
  catch{process.stdout.write(JSON.stringify({outcome:'unsupported',reason_code:'WORKER_ERROR',cases:[]}));}
}
