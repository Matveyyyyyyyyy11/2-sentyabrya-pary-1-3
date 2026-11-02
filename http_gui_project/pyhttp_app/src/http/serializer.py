"""Сборка Request/Response в байты."""
from email.utils import formatdate
from typing import Dict, Union

from ..errors import ParseError
from .headers import TOKEN_RE, find_key, remove_header, set_header, validate_header
from .request import Request
from .response import Response
from .status import has_body, reason_phrase


def _render(start_line: str, headers: Dict[str, str], body: bytes) -> bytes:
    for name, value in headers.items():
        validate_header(name, value)
    lines = [start_line] + [f"{name}: {value}" for name, value in headers.items()]
    try:
        head = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ParseError("header contains non-latin-1 characters") from exc
    return head + body


class Serializer:
    """Превращает HTTP-сообщения в байты для отправки по сокету."""

    @staticmethod
    def serialize_request(req: Request) -> bytes:
        """Запрос → байты; Content-Length добавляется автоматически."""
        if not TOKEN_RE.match(req.method):
            raise ParseError(f"invalid method: {req.method!r}")
        if not req.path or any(ch in req.path for ch in " \r\n\x00"):
            raise ParseError(f"invalid request target: {req.path!r}")
        headers = dict(req.headers)
        no_length = (find_key(headers, "Content-Length") is None
                     and find_key(headers, "Transfer-Encoding") is None)
        if no_length and (req.body or req.method.upper() in ("POST", "PUT", "PATCH")):
            set_header(headers, "Content-Length", str(len(req.body)))
        start = f"{req.method} {req.path} {req.version}"
        return _render(start, headers, req.body)

    @staticmethod
    def serialize_response(resp: Response) -> bytes:
        """Ответ → байты; добавляет Content-Length и Date, если их нет."""
        reason = resp.reason or reason_phrase(resp.status)
        headers = dict(resp.headers)
        remove_header(headers, "Transfer-Encoding")  # тело отдаём уже целиком
        if has_body(resp.status):
            body = resp.body
            set_header(headers, "Content-Length", str(len(body)))
        else:
            body = b""
            remove_header(headers, "Content-Length")
        if find_key(headers, "Date") is None:
            headers["Date"] = formatdate(usegmt=True)
        return _render(f"{resp.version} {resp.status} {reason}", headers, body)

    @classmethod
    def serialize(cls, message: Union[Request, Response]) -> bytes:
        """Универсальная точка входа (диспетчеризация по типу через isinstance)."""
        if isinstance(message, Request):
            return cls.serialize_request(message)
        if isinstance(message, Response):
            return cls.serialize_response(message)
        raise TypeError(f"cannot serialize {type(message).__name__}")
