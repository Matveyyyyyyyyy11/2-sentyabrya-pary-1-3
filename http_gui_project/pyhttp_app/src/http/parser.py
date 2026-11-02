"""Разбор HTTP-запросов и ответов (из байт и из потока соединения)."""
import re
from typing import Dict, Optional, Tuple

from ..errors import HttpConnectionError, ParseError
from ..net.interfaces import Connection
from ..net.socket_wrapper import BytesConnection
from .headers import TOKEN_RE, find_key, get_header
from .request import Request
from .response import Response
from .status import has_body

MAX_HEADER_BYTES = 8192
MAX_HEADER_COUNT = 100
MAX_BODY_BYTES = 10 * 1024 * 1024
_VERSION_RE = re.compile(r"^HTTP/\d\.\d$")
_METHOD_RE = re.compile(r"^[A-Z]+$")


class Parser:
    """Разбор стартовой строки и заголовков + парсинг целых сообщений."""

    @staticmethod
    def parse_head(head: bytes) -> Tuple[str, Dict[str, str]]:
        """Разобрать блок до пустой строки: (стартовая строка, заголовки)."""
        if len(head) > MAX_HEADER_BYTES:
            raise ParseError("header section too large")
        lines = head.decode("latin-1").split("\r\n")
        start, header_lines = lines[0], lines[1:]
        if len(header_lines) > MAX_HEADER_COUNT:
            raise ParseError("too many headers")
        headers: Dict[str, str] = {}
        for line in header_lines:
            if not line or line[0] in " \t":
                raise ParseError("empty header line or obsolete line folding")
            name, sep, value = line.partition(":")
            if not sep or not TOKEN_RE.match(name):
                raise ParseError(f"malformed header line: {line[:40]!r}")
            value = value.strip(" \t")
            key = find_key(headers, name)
            if key is None:
                headers[name] = value
            else:  # повторные заголовки склеиваются по RFC 9110
                headers[key] = f"{headers[key]}, {value}"
        return start, headers

    @staticmethod
    def parse_request_line(line: str) -> Tuple[str, str, str]:
        """«GET /path HTTP/1.1» → (метод, цель, версия)."""
        parts = line.split(" ")
        if len(parts) != 3 or not parts[1]:
            raise ParseError(f"malformed request line: {line[:60]!r}")
        method, target, version = parts
        if not _METHOD_RE.match(method):
            raise ParseError(f"invalid method: {method[:20]!r}")
        if not _VERSION_RE.match(version):
            raise ParseError(f"invalid HTTP version: {version[:20]!r}")
        return method, target, version

    @staticmethod
    def parse_status_line(line: str) -> Tuple[str, int, str]:
        """«HTTP/1.1 200 OK» → (версия, код, фраза)."""
        parts = line.split(" ", 2)
        if len(parts) < 2 or not _VERSION_RE.match(parts[0]):
            raise ParseError(f"malformed status line: {line[:60]!r}")
        if not (len(parts[1]) == 3 and parts[1].isdigit()):
            raise ParseError(f"invalid status code: {parts[1][:10]!r}")
        status = int(parts[1])
        if not 100 <= status <= 599:
            raise ParseError(f"status code out of range: {status}")
        return parts[0], status, parts[2] if len(parts) == 3 else ""

    @staticmethod
    def validate_request(req: Request) -> None:
        """Проверки уровня сервера: Host для HTTP/1.1 и корректная цель запроса."""
        if not req.path.startswith("/"):
            raise ParseError(f"unsupported request target: {req.path[:60]!r}")
        if req.version == "HTTP/1.1" and req.get_header("Host") is None:
            raise ParseError("missing Host header")

    @staticmethod
    def parse_request(data: bytes, require_host: bool = False) -> Request:
        """Разобрать запрос целиком из байт (require_host — требовать Host)."""
        req = MessageReader(BytesConnection(data)).read_request()
        if req is None:
            raise ParseError("empty request")
        if require_host:
            Parser.validate_request(req)
        return req

    @staticmethod
    def parse_response(data: bytes) -> Response:
        """Разобрать ответ целиком из байт."""
        return MessageReader(BytesConnection(data)).read_response()


class MessageReader:
    """Читает HTTP-сообщения из Connection, сохраняя остаток буфера (keep-alive)."""

    CHUNK = 4096

    def __init__(self, conn: Connection, max_body: int = MAX_BODY_BYTES) -> None:
        self._conn = conn
        self._buf = bytearray()
        self._max_body = max_body

    def _fill(self) -> bool:
        data = self._conn.recv(self.CHUNK)
        if not data:
            return False
        self._buf.extend(data)
        return True

    def _read_head(self) -> Optional[bytes]:
        while self._buf.startswith(b"\r\n"):  # пустые строки между запросами
            del self._buf[:2]
        while True:
            idx = self._buf.find(b"\r\n\r\n")
            if idx != -1:
                if idx > MAX_HEADER_BYTES:
                    raise ParseError("header section too large")
                head = bytes(self._buf[:idx])
                del self._buf[:idx + 4]
                return head
            if len(self._buf) > MAX_HEADER_BYTES:
                raise ParseError("header section too large")
            if not self._fill():
                if not self._buf:
                    return None
                raise ParseError("connection closed inside header section")

    def _read_exact(self, size: int) -> bytes:
        while len(self._buf) < size:
            if not self._fill():
                raise ParseError("unexpected end of message body")
        data = bytes(self._buf[:size])
        del self._buf[:size]
        return data

    def _read_line(self) -> bytes:
        while True:
            idx = self._buf.find(b"\r\n")
            if idx != -1:
                line = bytes(self._buf[:idx])
                del self._buf[:idx + 2]
                return line
            if len(self._buf) > MAX_HEADER_BYTES:
                raise ParseError("chunk line too long")
            if not self._fill():
                raise ParseError("unexpected end inside chunked body")

    def _read_until_close(self) -> bytes:
        while self._fill():
            if len(self._buf) > self._max_body:
                raise ParseError("body too large")
        data = bytes(self._buf)
        self._buf.clear()
        return data

    def _read_chunked(self) -> bytes:
        body = bytearray()
        while True:
            size_text = self._read_line().split(b";", 1)[0].strip()
            if not re.fullmatch(rb"[0-9A-Fa-f]{1,8}", size_text):
                raise ParseError("invalid chunk size")
            size = int(size_text, 16)
            if size == 0:
                while self._read_line():  # trailer-заголовки до пустой строки
                    pass
                return bytes(body)
            if len(body) + size > self._max_body:
                raise ParseError("body too large")
            body.extend(self._read_exact(size))
            if self._read_exact(2) != b"\r\n":
                raise ParseError("chunk is not terminated by CRLF")

    def _read_body(self, headers: Dict[str, str], until_close: bool) -> bytes:
        encoding = get_header(headers, "Transfer-Encoding")
        length = get_header(headers, "Content-Length")
        if encoding is not None and length is not None:
            # классический вектор request smuggling — отвергаем
            raise ParseError("both Content-Length and Transfer-Encoding present")
        if encoding is not None:
            if encoding.strip().lower() != "chunked":
                raise ParseError(f"unsupported Transfer-Encoding: {encoding[:30]!r}")
            return self._read_chunked()
        if length is not None:
            if not re.fullmatch(r"\d{1,12}", length.strip()):
                raise ParseError(f"invalid Content-Length: {length[:30]!r}")
            size = int(length)
            if size > self._max_body:
                raise ParseError("body too large")
            return self._read_exact(size)
        return self._read_until_close() if until_close else b""

    def read_request(self) -> Optional[Request]:
        """Прочитать следующий запрос; None — соединение чисто закрыто."""
        head = self._read_head()
        if head is None:
            return None
        start, headers = Parser.parse_head(head)
        method, target, version = Parser.parse_request_line(start)
        body = self._read_body(headers, until_close=False)
        return Request(method, target, version, headers, body)

    def read_response(self) -> Response:
        """Прочитать ответ; тело — по Content-Length, chunked или до закрытия."""
        head = self._read_head()
        if head is None:
            raise HttpConnectionError("connection closed before response")
        start, headers = Parser.parse_head(head)
        version, status, reason = Parser.parse_status_line(start)
        body = b""
        if has_body(status):
            body = self._read_body(headers, until_close=True)
        return Response(status, reason, version, headers, body)
