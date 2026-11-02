"""Модель HTTP-запроса."""
from dataclasses import dataclass, field
from typing import Dict, Optional

from .headers import get_header


@dataclass
class Request:
    """HTTP-запрос."""

    method: str
    path: str
    version: str = "HTTP/1.1"
    headers: Dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    def get_header(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Заголовок без учёта регистра имени."""
        return get_header(self.headers, name, default)

    @property
    def route_path(self) -> str:
        """Путь без query-строки (по нему работает маршрутизатор)."""
        return self.path.split("?", 1)[0]

    @property
    def query(self) -> str:
        """Query-строка без «?»."""
        return self.path.partition("?")[2]
