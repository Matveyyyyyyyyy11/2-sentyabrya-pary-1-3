"""Подсветка JSON/HTML: чистые функции без tkinter (их можно тестировать)."""
import json
import re
from typing import List, Tuple

_JSON_RE = re.compile(
    r'(?P<key>"(?:[^"\\]|\\.)*"(?=\s*:))'
    r'|(?P<string>"(?:[^"\\]|\\.)*")'
    r'|(?P<number>-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)'
    r'|(?P<literal>\b(?:true|false|null)\b)')
_HTML_RE = re.compile(r'(?P<comment><!--.*?-->)|(?P<tag></?[A-Za-z!][^>]*>)', re.DOTALL)
MAX_HIGHLIGHT_CHARS = 200_000

Span = Tuple[str, int, int]


def detect_kind(content_type: str, text: str) -> str:
    """Определить формат тела: json / html / text."""
    lowered = (content_type or "").lower()
    stripped = text.lstrip()
    if "json" in lowered or (not lowered and stripped[:1] in ("{", "[")):
        return "json"
    if "html" in lowered or stripped[:15].lower().startswith(("<!doctype", "<html")):
        return "html"
    return "text"


def format_body(kind: str, text: str) -> str:
    """Красиво отформатировать JSON (если он корректен), иначе вернуть как есть."""
    if kind == "json":
        try:
            return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except ValueError:
            return text
    return text


def find_spans(kind: str, text: str) -> List[Span]:
    """Диапазоны для подсветки: (тег, начало, конец) в символах."""
    if kind not in ("json", "html") or len(text) > MAX_HIGHLIGHT_CHARS:
        return []
    pattern = _JSON_RE if kind == "json" else _HTML_RE
    return [(m.lastgroup or "", m.start(), m.end()) for m in pattern.finditer(text)]
