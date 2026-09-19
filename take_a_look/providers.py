"""Providers propose text, never commands, evidence or verdicts."""

import ast
import copy
import re
from dataclasses import dataclass
from typing import Callable, Protocol

from .probes import candidates, tree, Unsupported


@dataclass(frozen=True)
class RoleRequest:
    role: str
    instructions: str
    data: dict


class Provider(Protocol):
    name: str

    def complete(self, request: RoleRequest) -> dict: ...


class FunctionAdapter:
    """Wrap an OpenAI/Claude/other SDK call; transport is explicitly user supplied.

    The default product never creates this adapter or sends network requests.
    Each role receives a fresh request, with no conversation history.
    """

    def __init__(self, name: str, completion: Callable[[RoleRequest], dict]):
        self.name = name
        self.completion = completion

    def complete(self, request: RoleRequest) -> dict:
        result = self.completion(copy.deepcopy(request))
        if not isinstance(result, dict):
            raise ValueError("provider response must be an object")
        return result


class MockProvider:
    name = "offline-structural-mock-v1"

    def complete(self, request: RoleRequest) -> dict:
        if request.role == "investigator":
            claims = []
            for file, source in request.data["sources"].items():
                if file.endswith(".py"):
                    try:
                        module = tree(source)
                    except SyntaxError as exc:
                        claims.append(self.item("syntax", file, exc.lineno or 1, "Python 문법을 읽을 수 없습니다", "구문 분석기가 파일을 해석하지 못했습니다.", "실행 전에 시작이 막힐 수 있습니다.", "독립 구문 분석"))
                        continue
                    except Unsupported:
                        continue
                    for fn, node, arg, boundary in candidates(module):
                        claims.append(self.item("boundary_division", file, node.lineno, "경계값에서 이 함수 본문에 0 나눗셈이 발생할 수 있습니다", "나눗셈의 분모가 입력값 또는 입력 길이입니다.", "이 입력이 허용된다면 계산 요청이 실패할 수 있습니다.", "빈 목록 또는 0 입력으로 함수 본문 계산", fn.name))
                    for node in ast.walk(module):
                        if isinstance(node, ast.ExceptHandler) and (node.type is None or isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"}) and any(isinstance(n, ast.Pass) for n in node.body):
                            claims.append(self.item("swallowed_error", file, node.lineno, "실패를 알려주지 않고 넘어갈 가능성이 있습니다", "넓은 범위의 예외를 잡은 뒤 아무 동작 없이 넘어갑니다.", "처리 실패를 사용자가 모를 수 있습니다.", "실패 입력과 제품의 오류 처리 규칙을 확인"))
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "round":
                            claims.append(self.item("product_policy", file, node.lineno, "반올림 기준이 의도와 맞는지 확인이 필요합니다", "계산 결과에 반올림을 적용합니다.", "금액·정산 기준은 제품 정책에 따라 달라집니다.", "담당자가 반올림 단위와 정책을 확인"))
                elif file.endswith((".js", ".ts", ".jsx", ".tsx")):
                    for line, text in enumerate(source.splitlines(), 1):
                        if re.search(r"/\s*\w+\.length\b", text):
                            claims.append(self.item("js_boundary", file, line, "빈 목록 계산이 유효하지 않은 숫자를 만들 수 있습니다", "목록 길이로 나누는 표현이 있습니다. 문자열·주석일 수도 있어 확인이 필요합니다.", "화면이나 저장 값에 잘못된 숫자가 전달될 수 있습니다.", "JavaScript 실행 증거 필요"))
            return {"claims": claims[:100]}
        if request.role == "challenger":
            claim = request.data["claim"]
            source = request.data["source"]
            locations = []
            if claim["rule"] == "boundary_division":
                try:
                    for fn in tree(source).body:
                        if isinstance(fn, ast.FunctionDef) and fn.name == claim["symbol"]:
                            locations = [str(n.lineno) for n in ast.walk(fn) if isinstance(n, ast.If)]
                except (SyntaxError, Unsupported):
                    pass
                counter = "앞선 조건문이 빈 입력을 처리할 수 있습니다." if locations else "호출자가 이 입력을 차단하거나, 이 함수가 빈 입력을 허용하지 않는 계약일 수 있습니다."
            elif claim["rule"] == "syntax":
                counter = "다른 Python 버전 문법이거나 생성용 템플릿 파일일 가능성이 있습니다. 현재 분석기 버전의 결과로 한정해야 합니다."
            elif claim["rule"] == "product_policy":
                counter = "현재 반올림이 제품에서 정한 올바른 정책일 수 있습니다. 코드만으로 정책을 결정할 수 없습니다."
            else:
                counter = "상위 계층의 방어 코드나 의도된 실패 무시 정책이 있을 수 있습니다. 이 패턴만으로 버그라고 확정할 수 없습니다."
            return {"counterargument": counter, "defense_lines": locations}
        raise ValueError("unknown role")

    @staticmethod
    def item(rule, file, line, title, reason, impact, method, symbol=""):
        return dict(rule=rule, file=file, line=line, title=title, reason=reason, impact=impact, method=method, symbol=symbol)
