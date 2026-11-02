"""Работа с заголовками: имена регистронезависимы, значения — без CR/LF."""
import re
from typing import Dict, Optional

from ..errors import ParseError

TOKEN_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def find_key(headers: Dict[str, str], name: str) -> Optional[str]:
    """Вернуть фактический ключ словаря для имени заголовка (без учёта регистра)."""
    lowered = name.lower()
    for key in headers:
        if key.lower() == lowered:
            return key
    return None


def get_header(headers: Dict[str, str], name: str,
               default: Optional[str] = None) -> Optional[str]:
    """Значение заголовка без учёта регистра имени."""
    key = find_key(headers, name)
    return headers[key] if key is not None else default


def set_header(headers: Dict[str, str], name: str, value: str) -> None:
    """Установить заголовок, заменив существующий с другим регистром имени."""
    key = find_key(headers, name)
    if key is not None:
        del headers[key]
    headers[name] = value


def remove_header(headers: Dict[str, str], name: str) -> None:
    """Удалить заголовок, если он есть."""
    key = find_key(headers, name)
    if key is not None:
        del headers[key]


def validate_header(name: str, value: str) -> None:
    """Проверить имя и значение (защита от инъекции заголовков через CR/LF)."""
    if not TOKEN_RE.match(name):
        raise ParseError(f"invalid header name: {name!r}")
    if any(ch in value for ch in "\r\n\x00"):
        raise ParseError(f"invalid characters in value of header {name!r}")
