"""Модель HTTP-ответа."""
import re
from dataclasses import dataclass, field
from typing import Dict, Optional

from ..errors import HttpError
from .headers import get_header

_CHARSET_RE = re.compile(r"charset\s*=\s*\"?([^\s;\"]+)", re.IGNORECASE)


@dataclass
class Response:
    """HTTP-ответ."""

    status: int
    reason: str = ""
    version: str = "HTTP/1.1"
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Заголовок без учёта регистра имени."""
        return get_header(self.headers, name, default)

    @property
    def ok(self) -> bool:
        """True, если статус < 400."""
        return self.status < 400

    @property
    def charset(self) -> str:
        """Кодировка из Content-Type (по умолчанию utf-8)."""
        match = _CHARSET_RE.search(self.get_header("Content-Type") or "")
        return match.group(1) if match else "utf-8"

    @property
    def text(self) -> str:
        """Тело, декодированное по charset (ошибки заменяются)."""
        try:
            return self.body.decode(self.charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        """Бросить HttpError для 4xx/5xx."""
        if self.status >= 400:
            raise HttpError(self.status, self.reason)
