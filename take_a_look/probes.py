"""A tiny, bounded Python AST evaluator. Never imports or executes target code.

Evidence is scoped to one function body and one input, not application behavior.
Unsupported syntax fails closed. This is deliberately NOT a Python sandbox.
"""

import ast
import math
import operator


class Unsupported(ValueError):
    pass


def tree(source: str) -> ast.Module:
    if len(source) > 256_000:
        raise Unsupported("source limit")
    try:
        result = ast.parse(source)
    except (RecursionError, MemoryError) as exc:
        raise Unsupported("parse limit") from exc
    if sum(1 for _ in ast.walk(result)) > 12_000:
        raise Unsupported("AST limit")
    try:
        compile(result, "<target-snapshot>", "exec")  # Syntax/scope validation only.
    except (RecursionError, MemoryError) as exc:
        raise Unsupported("compile limit") from exc
    return result


def candidates(module: ast.Module):
    for fn in module.body:
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
                rhs = node.right
                if isinstance(rhs, ast.Call) and isinstance(rhs.func, ast.Name) and rhs.func.id == "len" and len(rhs.args) == 1 and isinstance(rhs.args[0], ast.Name):
                    yield fn, node, rhs.args[0].id, []
                    break
                if isinstance(rhs, ast.Name):
                    yield fn, node, rhs.id, 0
                    break
                if isinstance(rhs, ast.Constant) and type(rhs.value) in (int, float) and rhs.value == 0:
                    yield fn, node, "", 0
                    break


BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}
ALLOWED = (ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.If, ast.Assign, ast.Name, ast.Load, ast.Store, ast.Constant, ast.Expr, ast.BinOp, ast.UnaryOp, ast.Not, ast.USub, ast.UAdd, ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.Call, ast.List, *BIN, *CMP)


def validate(fn: ast.FunctionDef):
    if fn.decorator_list or fn.returns or fn.type_comment or getattr(fn, "type_params", []):
        raise Unsupported("decorators/annotations")
    args = fn.args
    if args.vararg or args.kwarg or args.kwonlyargs or args.defaults or args.posonlyargs or any(a.annotation for a in args.args):
        raise Unsupported("complex arguments")
    if len(args.args) > 4:
        raise Unsupported("argument limit")
    names = {a.arg for a in args.args}
    if names & {"sum", "len"}:
        raise Unsupported("shadowed builtins")
    nodes = list(ast.walk(fn))
    if len(nodes) > 160:
        raise Unsupported("function limit")
    for n in nodes:
        if not isinstance(n, ALLOWED):
            raise Unsupported("unsupported syntax")
        if isinstance(n, ast.Constant):
            if isinstance(n.value, str):
                # Only a docstring may contain strings; never evaluate or publish it.
                if not (fn.body and isinstance(fn.body[0], ast.Expr) and fn.body[0].value is n):
                    raise Unsupported("string expression")
            elif n.value is not None and type(n.value) not in (int, float, bool):
                raise Unsupported("constant type")
            elif type(n.value) in (int, float) and (not math.isfinite(n.value) or abs(n.value) > 1e9):
                raise Unsupported("number limit")
        if isinstance(n, ast.Call) and (not isinstance(n.func, ast.Name) or n.func.id not in {"sum", "len"} or len(n.args) != 1 or n.keywords):
            raise Unsupported("call forbidden")
        if isinstance(n, ast.Assign):
            if len(n.targets) != 1 or not isinstance(n.targets[0], ast.Name) or n.targets[0].id in {"sum", "len"}:
                raise Unsupported("assignment forbidden")
            names.add(n.targets[0].id)
    if any(isinstance(n, ast.Name) and n.id not in names | {"sum", "len"} for n in nodes):
        raise Unsupported("global lookup forbidden")


class Evaluator:
    def __init__(self, env: dict):
        self.env = dict(env)
        self.steps = 0

    def expression(self, n):
        self.steps += 1
        if self.steps > 300:
            raise Unsupported("step limit")
        result = self._expression(n)
        if isinstance(result, (list, tuple)) and len(result) > 32:
            raise Unsupported("sequence limit")
        if type(result) in (int, float) and (abs(result) > 1e12 or not math.isfinite(result)):
            raise Unsupported("result limit")
        return result

    def _expression(self, n):
        if isinstance(n, ast.Constant):
            return n.value
        if isinstance(n, ast.Name):
            if n.id not in self.env:
                raise Unsupported("unbound name")
            return self.env[n.id]
        if isinstance(n, (ast.List, ast.Tuple)):
            return [self.expression(x) for x in n.elts]
        if isinstance(n, ast.BinOp):
            left, right = self.expression(n.left), self.expression(n.right)
            if type(left) not in (int, float, bool) or type(right) not in (int, float, bool):
                raise Unsupported("non-numeric operation")
            return BIN[type(n.op)](left, right)
        if isinstance(n, ast.UnaryOp):
            value = self.expression(n.operand)
            if isinstance(n.op, ast.Not):
                return not value
            if type(value) not in (int, float, bool):
                raise Unsupported("non-numeric unary operation")
            return -value if isinstance(n.op, ast.USub) else +value
        if isinstance(n, ast.BoolOp):
            for item in n.values:
                value = self.expression(item)
                if isinstance(n.op, ast.And) and not value or isinstance(n.op, ast.Or) and value:
                    return value
            return value
        if isinstance(n, ast.Compare):
            left = self.expression(n.left)
            for op, other in zip(n.ops, n.comparators):
                right = self.expression(other)
                if not CMP[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(n, ast.Call):
            value = self.expression(n.args[0])
            if not isinstance(value, (list, tuple)) or any(type(x) not in (int, float, bool) for x in value):
                raise Unsupported("builtin input type")
            return len(value) if n.func.id == "len" else sum(value)
        raise Unsupported("expression forbidden")

    def block(self, statements):
        for n in statements:
            if isinstance(n, ast.Return):
                return True, self.expression(n.value) if n.value else None
            if isinstance(n, ast.If):
                done, value = self.block(n.body if self.expression(n.test) else n.orelse)
                if done:
                    return done, value
            elif isinstance(n, ast.Assign):
                self.env[n.targets[0].id] = self.expression(n.value)
            elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                continue
            elif not isinstance(n, ast.If):
                raise Unsupported("statement forbidden")
        return False, None


def probe(source: str, symbol: str, line: int) -> dict:
    module = tree(source)
    matches = [item for item in candidates(module) if item[0].name == symbol and item[1].lineno == line]
    if len(matches) != 1:
        raise Unsupported("claim does not match source")
    fn, _, arg, boundary = matches[0]
    validate(fn)
    # Module-level rebinding can invalidate builtin or function semantics.
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            if node is not fn and node.name in {symbol, "len", "sum"}:
                raise Unsupported("module rebinding")
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            if any(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id in {symbol, "len", "sum"} for n in ast.walk(node)):
                raise Unsupported("module rebinding")
        elif isinstance(node, ast.ImportFrom) and any(a.name == "*" or (a.asname or a.name) in {symbol, "len", "sum"} for a in node.names):
            raise Unsupported("module rebinding")
    env = {a.arg: 1 for a in fn.args.args}
    if arg:
        if arg not in env:
            raise Unsupported("denominator is not an input")
        env[arg] = boundary
    outcomes = []
    for _ in range(3):
        try:
            _, value = Evaluator(env).block(fn.body)
            outcomes.append({"outcome": "returned", "value": value})
        except ZeroDivisionError:
            outcomes.append({"outcome": "zero_division"})
    return {"inputs": env, "observations": outcomes, "scope": "이 함수 본문의 지정 입력에 대한 제한된 Python AST 계산입니다. 실제 앱 실행·호출부 입력 허용 여부는 별도 확인이 필요합니다.", "engine": "bounded-python-ast-v1"}
