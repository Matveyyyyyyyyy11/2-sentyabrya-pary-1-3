"""Разбор URL вида scheme://host[:port]/path?query."""
import re
from dataclasses import dataclass
from typing import Tuple

from ..errors import ParseError

__all__ = ["Url", "ParseError"]

DEFAULT_PORTS = {"http": 80, "https": 443}
_HOST_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_IPV6_RE = re.compile(r"^\[([0-9A-Fa-f:.]+)\](?::(\d*))?$")


@dataclass(frozen=True)
class Url:
    """Разобранный URL."""

    scheme: str
    host: str
    port: int
    path: str = "/"
    query: str = ""

    @classmethod
    def parse(cls, text: str) -> "Url":
        """Разобрать строку; при любой проблеме бросает ParseError."""
        if not isinstance(text, str) or not text.strip():
            raise ParseError("empty URL")
        text = text.strip()
        if any(ch.isspace() or ord(ch) < 32 for ch in text):
            raise ParseError("URL contains whitespace or control characters")
        scheme, sep, rest = text.partition("://")
        scheme = scheme.lower()
        if not sep or scheme not in DEFAULT_PORTS:
            raise ParseError(f"unsupported or missing scheme in {text!r}")
        rest = rest.split("#", 1)[0]
        match = re.search(r"[/?]", rest)
        if match:
            netloc, tail = rest[:match.start()], rest[match.start():]
        else:
            netloc, tail = rest, ""
        path, _, query = tail.partition("?")
        host, port = cls._split_netloc(netloc, scheme)
        return cls(scheme, host, port, path or "/", query)

    @staticmethod
    def _split_netloc(netloc: str, scheme: str) -> Tuple[str, int]:
        if not netloc:
            raise ParseError("URL has no host")
        if "@" in netloc:
            raise ParseError("user info in URL is not supported")
        if netloc.startswith("["):
            ipv6 = _IPV6_RE.match(netloc)
            if not ipv6:
                raise ParseError(f"invalid IPv6 address: {netloc!r}")
            host, port_text = ipv6.group(1), ipv6.group(2)
        else:
            if netloc.count(":") > 1:
                raise ParseError(f"invalid host: {netloc!r}")
            host, _, port_text = netloc.partition(":")
            if not _HOST_RE.match(host):
                raise ParseError(f"invalid host: {host!r}")
        if not port_text:
            return host.lower(), DEFAULT_PORTS[scheme]
        if not port_text.isdigit() or not 1 <= int(port_text) <= 65535:
            raise ParseError(f"invalid port: {port_text!r}")
        return host.lower(), int(port_text)

    @property
    def is_secure(self) -> bool:
        """True для https."""
        return self.scheme == "https"

    @property
    def target(self) -> str:
        """Request-target для стартовой строки: путь + ?query."""
        return self.path + (f"?{self.query}" if self.query else "")

    @property
    def host_header(self) -> str:
        """Значение заголовка Host (порт опускается, если он по умолчанию)."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        if self.port == DEFAULT_PORTS[self.scheme]:
            return host
        return f"{host}:{self.port}"

    def resolve(self, location: str) -> "Url":
        """Разрешить значение Location (абсолютное или относительное) для редиректа."""
        location = location.strip()
        if "://" in location:
            return Url.parse(location)
        if location.startswith("//"):
            return Url.parse(f"{self.scheme}:{location}")
        base = f"{self.scheme}://{self.host_header}"
        if location.startswith("/"):
            return Url.parse(base + location)
        directory = self.path.rsplit("/", 1)[0]
        return Url.parse(f"{base}{directory}/{location}")

    def __str__(self) -> str:
        return f"{self.scheme}://{self.host_header}{self.target}"
