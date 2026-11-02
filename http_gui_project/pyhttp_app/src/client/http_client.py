"""HTTP-клиент на сокетах."""
import logging
from typing import Dict, Optional, Union

from ..errors import HttpError
from ..http.headers import set_header
from ..http.parser import MessageReader
from ..http.request import Request
from ..http.response import Response
from ..http.serializer import Serializer
from ..http.url import Url
from ..net.tcp_client import TcpClient

LOG = logging.getLogger("http_gui.client")
REDIRECT_CODES = (301, 302, 303, 307, 308)
USER_AGENT = "PyHttpGui/1.0"


class HttpClient:
    """GET/POST, таймауты, Content-Length / chunked, редиректы, HTTPS (ssl)."""

    def __init__(self, timeout_ms: int = 5000, max_redirects: int = 0) -> None:
        self._timeout = 5.0
        self._max_redirects = 0
        self.set_timeout(timeout_ms)
        self.follow_redirects(max_redirects)

    def set_timeout(self, ms: int) -> None:
        """Таймаут соединения и чтения, миллисекунды."""
        if ms <= 0:
            raise ValueError("timeout must be positive")
        self._timeout = ms / 1000.0

    def follow_redirects(self, max_redirects: int) -> None:
        """Сколько редиректов 3xx выполнять (0 — не следовать)."""
        if max_redirects < 0:
            raise ValueError("max_redirects must be >= 0")
        self._max_redirects = max_redirects

    def get(self, url: str, headers: Optional[Dict[str, str]] = None) -> Response:
        """GET-запрос."""
        return self.request("GET", url, headers=headers)

    def post(self, url: str, body: Union[bytes, str], content_type: str,
             headers: Optional[Dict[str, str]] = None) -> Response:
        """POST-запрос; str кодируется в UTF-8."""
        data = body.encode("utf-8") if isinstance(body, str) else body
        return self.request("POST", url, data, headers, content_type)

    def request(self, method: str, url: str, body: bytes = b"",
                headers: Optional[Dict[str, str]] = None,
                content_type: Optional[str] = None) -> Response:
        """Выполнить запрос (с редиректами, если включены)."""
        method = method.upper()
        current = Url.parse(url)
        redirects = 0
        while True:
            response = self._send_once(current, method, body, headers, content_type)
            location = response.get_header("Location")
            if (self._max_redirects == 0 or response.status not in REDIRECT_CODES
                    or not location):
                return response
            if redirects >= self._max_redirects:
                raise HttpError(response.status, "too many redirects")
            redirects += 1
            current = current.resolve(location)
            if response.status == 303 or (response.status in (301, 302)
                                          and method == "POST"):
                method, body, content_type = "GET", b"", None
            LOG.info("redirect %d -> %s", response.status, current)

    def _send_once(self, url: Url, method: str, body: bytes,
                   headers: Optional[Dict[str, str]],
                   content_type: Optional[str]) -> Response:
        request_headers: Dict[str, str] = {
            "Host": url.host_header,
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Connection": "close",
        }
        if content_type:
            request_headers["Content-Type"] = content_type
        for name, value in (headers or {}).items():
            set_header(request_headers, name, value)
        request = Request(method, url.target, "HTTP/1.1", request_headers, body)
        data = Serializer.serialize(request)
        LOG.info("%s %s", method, url)
        with TcpClient(self._timeout).connect(url.host, url.port, url.is_secure) as sock:
            sock.send_all(data)
            response = MessageReader(sock).read_response()
        LOG.info("%s %s -> %d", method, url, response.status)
        return response
