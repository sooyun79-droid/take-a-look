"""SearchLens 연계 웹·이커머스 정적 신호.

같은 고정 패턴을 두 지점에서 쓴다.

- Investigator 규칙 탐색(MockProvider): 안전을 위해 마스킹된 스냅샷을 본다.
- DeterministicQA 검증: 같은 파일의 원문을 다시 읽어 그 줄에 신호가 있는지 확인한다.

마스킹된 스냅샷에는 비밀값 대신 자리표시자가 남는다. 그래서 탐색 패턴은
자리표시자와 이름(환경변수·설정 키)까지 함께 보고, 값 자체는 어느 경로에서도
claim에 담지 않는다. 주석 안의 문구는 원문 재확인 단계에서 제외한다.
"""

import re
from pathlib import PurePosixPath

ENGINE = "web-static-pattern-v1"
WEB_RULES = ("seo_noindex", "client_secret_leak", "a11y_image_alt", "client_payment_tamper")
MAX_MATCHES_PER_RULE = 50

TITLES = {
    "seo_noindex": "검색엔진 인덱싱이 차단(noindex)되어 있을 가능성이 있습니다",
    "client_secret_leak": "클라이언트 코드에 민감한 시크릿 키나 환경변수가 노출되었을 위험이 있습니다",
    "a11y_image_alt": "이미지 태그에 대체 텍스트(alt)가 누락되어 있습니다",
    "client_payment_tamper": "결제 요청 금액이 클라이언트에서 변조될 위험이 있습니다",
}
IMPACTS = {
    "seo_noindex": "검색엔진 및 AI 크롤러에서 페이지 노출이 완전히 제외될 수 있습니다.",
    "client_secret_leak": "브라우저 번들에 비밀키가 포함되어 외부로 유출될 수 있습니다.",
    "a11y_image_alt": "시각장애인 접근성이 저해되고 AI 검색 크롤러가 이미지 내용을 인식하지 못합니다.",
    "client_payment_tamper": "악의적인 사용자가 프론트엔드 스크립트를 조작해 결제 금액을 낮출 수 있습니다.",
}
METHODS = {
    "seo_noindex": "메타 태그 및 robots 설정의 noindex 지시어 정적 분석",
    "client_secret_leak": "공개 접두사 환경변수 및 민감 토큰 패턴 정적 분석",
    "a11y_image_alt": "HTML/JSX 이미지 태그의 alt 속성 존재 여부 정적 분석",
    "client_payment_tamper": "PG사 결제 호출부의 클라이언트 금액 지정 패턴 정적 분석",
}
REASONS = {
    "meta-robots-noindex": "robots 메타 태그의 content에 noindex 지시어가 있습니다.",
    "next-metadata-noindex": "Next.js/React 메타데이터에 index: false 또는 robots: 'noindex' 설정이 있습니다.",
    "robots-txt-disallow-all": "robots.txt가 모든 경로(Disallow: /)를 차단하고 있습니다.",
    "public-env-secret": "공개 접두사 환경변수 이름에 SECRET·TOKEN 같은 민감한 단어가 들어 있습니다. 번들에 포함되면 값이 노출됩니다.",
    "masked-token": "이 줄에 알려진 형식의 시크릿 토큰이 있었습니다. 값은 이미 가려져 있습니다.",
    "pg-secret-name": "결제·API 시크릿 키로 보이는 이름이 클라이언트 코드에 있습니다.",
    "image-missing-alt": "이미지 태그에 alt 속성이 없습니다. 장식용 이미지일 수도 있어 확인이 필요합니다.",
    "payment-amount-literal": "결제 SDK 호출 근처에서 금액이 숫자 리터럴로 지정되어 있습니다. 서버 검증이 있는지 확인해야 합니다.",
}

SCRIPT_SUFFIXES = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte"}
MARKUP_SUFFIXES = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte"}
WEB_SUFFIXES = SCRIPT_SUFFIXES | MARKUP_SUFFIXES

_HTML_COMMENT = re.compile(r"<!--[\s\S]*?-->")
_SCRIPT_COMMENT = re.compile(r"/\*[\s\S]*?\*/|(?:^|(?<=\s))//[^\n]*", re.MULTILINE)
_ROBOTS_DISALLOW_ALL = re.compile(r"^[ \t]*disallow[ \t]*:[ \t]*/[ \t]*$", re.IGNORECASE | re.MULTILINE)

_META_TAG = re.compile(r"<meta\b[^>]{0,2000}?>", re.IGNORECASE)
_ROBOTS_NAME = re.compile(r"\bname\s*=\s*[\"']robots[\"']", re.IGNORECASE)
_NOINDEX_CONTENT = re.compile(r"\bcontent\s*=\s*[\"'][^\"']*noindex", re.IGNORECASE)
_NEXT_ROBOTS_OBJECT = re.compile(r"\brobots\s*:\s*\{[^{}]{0,600}?\bindex\s*:\s*false", re.DOTALL)
_NEXT_ROBOTS_STRING = re.compile(r"\brobots\s*:\s*[\"']noindex[\"']")

_PUBLIC_ENV = re.compile(
    r"\b(?:NEXT_PUBLIC_[A-Za-z0-9_]*(?:SECRET|PRIVATE|API_?KEY|TOKEN|PASSWORD)"
    r"|VITE_[A-Za-z0-9_]*(?:SECRET|PRIVATE|API_?KEY|TOKEN|PASSWORD))\b",
    re.IGNORECASE,
)
_TOKEN_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{8,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    re.compile(r"https?://[^\s/@:]+:[^\s/@]+@"),
)
_MASKED_TOKEN = re.compile(r"\[토큰 숨김\]")
_PG_SECRET_NAME = re.compile(
    r"\b(?:NICEPAY|NICE_?PAY|TOSS_?PAYMENTS|TOSS_?PAY|TOSSPAY|INICIS|KCP|PORTONE|IAMPORT|STRIPE|PAYPAL)"
    r"[A-Za-z0-9_]*(?:SECRET|PRIVATE)[A-Za-z0-9_]*",
    re.IGNORECASE,
)
_SECRET_KEY_ASSIGN = re.compile(
    r"\b(?:secretKey|secret_key|clientSecret|client_secret|apiSecret|api_secret)\s*[:=]\s*[\"'`][^\"'`]{8,}",
    re.IGNORECASE,
)

_IMG_TAG = re.compile(r"<(?:img|Image|IMG)\b[^>]{0,2000}?>")
_ALT_ATTR = re.compile(r"\balt\s*=")
_SPREAD_ATTR = re.compile(r"\{\s*\.\.\.")

_PAYMENT_SDK = re.compile(
    r"\b(?:IMP\s*\.\s*(?:request_pay|init)|loadTossPayments|requestPayment|NicePay|NICEPAY|nicepay"
    r"|TossPayments|tossPayments|INICIS|inicis|KCP|PortOne|portone|Iamport)\b"
)
_AMOUNT_LITERAL = re.compile(r"\b(?:amount|price)\s*:\s*\d+")
PAYMENT_WINDOW_LINES = 15


def basename(file: str) -> str:
    return PurePosixPath(file.replace("\\", "/")).name


def suffix(file: str) -> str:
    return PurePosixPath(file.replace("\\", "/")).suffix.lower()


def is_web_file(file: str) -> bool:
    return suffix(file) in WEB_SUFFIXES or basename(file).lower() == "robots.txt"


def _blank(text: str) -> str:
    """같은 줄 번호를 유지한 채 주석 내용만 지운다."""
    return "".join("\n" if ch == "\n" else " " for ch in text)


def _without_comments(source: str, file: str) -> str:
    if suffix(file) in WEB_SUFFIXES:
        source = _HTML_COMMENT.sub(lambda m: _blank(m.group(0)), source)
        source = _SCRIPT_COMMENT.sub(lambda m: _blank(m.group(0)), source)
    return source


def _line_at(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _match(signal: str, symbol: str, text: str, start: int, end: int) -> dict:
    return {"signal": signal, "symbol": symbol, "line": _line_at(text, start), "end_line": _line_at(text, end)}


def _dedupe(matches: list[dict]) -> list[dict]:
    seen, result = set(), []
    for match in sorted(matches, key=lambda m: (m["line"], m["signal"])):
        if match["line"] in seen:
            continue
        seen.add(match["line"])
        result.append(match)
    return result[:MAX_MATCHES_PER_RULE]


def _scan_noindex(file: str, text: str) -> list[dict]:
    if basename(file).lower() == "robots.txt":
        return [{"signal": "robots-txt-disallow-all", "symbol": "robots.txt", "line": _line_at(text, m.start()), "end_line": _line_at(text, m.end())} for m in _ROBOTS_DISALLOW_ALL.finditer(text)]
    if suffix(file) not in WEB_SUFFIXES:
        return []
    found = []
    for meta in _META_TAG.finditer(text):
        tag = meta.group(0)
        if _ROBOTS_NAME.search(tag) and _NOINDEX_CONTENT.search(tag):
            found.append(_match("meta-robots-noindex", "meta-robots", text, meta.start(), meta.end()))
    if suffix(file) in SCRIPT_SUFFIXES:
        for pattern, symbol in ((_NEXT_ROBOTS_OBJECT, "next-metadata-robots"), (_NEXT_ROBOTS_STRING, "next-metadata-robots")):
            for hit in pattern.finditer(text):
                found.append(_match("next-metadata-noindex", symbol, text, hit.start(), hit.end()))
    return _dedupe(found)


def _scan_secret(file: str, text: str) -> list[dict]:
    if suffix(file) not in WEB_SUFFIXES:
        return []
    found = []
    for hit in _PUBLIC_ENV.finditer(text):
        found.append(_match("public-env-secret", hit.group(0), text, hit.start(), hit.end()))
    for hit in _MASKED_TOKEN.finditer(text):
        found.append(_match("masked-token", "redacted-token", text, hit.start(), hit.end()))
    for pattern in _TOKEN_PATTERNS:
        for hit in pattern.finditer(text):
            found.append(_match("masked-token", "known-token-pattern", text, hit.start(), hit.end()))
    for hit in _PG_SECRET_NAME.finditer(text):
        found.append(_match("pg-secret-name", hit.group(0), text, hit.start(), hit.end()))
    for hit in _SECRET_KEY_ASSIGN.finditer(text):
        found.append(_match("pg-secret-name", "secret-key-assignment", text, hit.start(), hit.end()))
    return _dedupe(found)


def _scan_alt(file: str, text: str) -> list[dict]:
    if suffix(file) not in WEB_SUFFIXES:
        return []
    found = []
    for tag in _IMG_TAG.finditer(text):
        body = tag.group(0)
        if _ALT_ATTR.search(body):
            continue
        if _SPREAD_ATTR.search(body):
            # {...props}로 alt가 전달될 수 있어 정적으로 단정하지 않는다.
            continue
        found.append(_match("image-missing-alt", "img", text, tag.start(), tag.end()))
    return _dedupe(found)


def _scan_payment(file: str, text: str) -> list[dict]:
    if suffix(file) not in WEB_SUFFIXES:
        return []
    sdk_lines = [( _line_at(text, m.start()), re.sub(r"\s+", "", m.group(0))) for m in _PAYMENT_SDK.finditer(text)]
    if not sdk_lines:
        return []
    found = []
    for amount in _AMOUNT_LITERAL.finditer(text):
        line = _line_at(text, amount.start())
        near = [symbol for sdk_line, symbol in sdk_lines if abs(sdk_line - line) <= PAYMENT_WINDOW_LINES]
        if near:
            found.append(_match("payment-amount-literal", near[0], text, amount.start(), amount.end()))
    return _dedupe(found)


_SCANNERS = {
    "seo_noindex": _scan_noindex,
    "client_secret_leak": _scan_secret,
    "a11y_image_alt": _scan_alt,
    "client_payment_tamper": _scan_payment,
}


def scan(rule: str, file: str, source: str) -> list[dict]:
    scanner = _SCANNERS.get(rule)
    if scanner is None or not is_web_file(file):
        return []
    return scanner(file, _without_comments(source, file))


def scan_all(file: str, source: str) -> list[dict]:
    if not is_web_file(file):
        return []
    text = _without_comments(source, file)
    results = []
    for rule, scanner in _SCANNERS.items():
        for match in scanner(file, text):
            results.append({"rule": rule, **match})
    return results


def verify(rule: str, file: str, source: str, line: int) -> dict:
    """같은 파일 원문에서 그 줄(또는 그 줄을 덮는 태그)에 신호가 있는지 다시 확인한다."""
    matches = scan(rule, file, source)
    covering = [m for m in matches if m["line"] <= line <= m["end_line"]]
    details = {"engine": ENGINE, "rule": rule, "line": line, "matches_in_file": len(matches)}
    if covering:
        details.update(outcome="found", signal=covering[0]["signal"], symbol=covering[0]["symbol"], inputs={"line": line}, observations=[{"outcome": "found", "signal": covering[0]["signal"], "line": line}])
    else:
        details.update(outcome="absent", signal="")
    return details
