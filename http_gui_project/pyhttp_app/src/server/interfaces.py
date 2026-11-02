"""Интерфейсы (ABC) сервера: обработчик запроса и наблюдатель за запросами."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..http.request import Request
from ..http.response import Response


@dataclass(frozen=True)
class RequestRecord:
    """Запись о обработанном запросе (для лога)."""

    time: str
    method: str
    path: str
    status: int
    elapsed_ms: float
    client: str = ""


class RequestHandler(ABC):
    """Обработчик маршрута: вызываемый объект Request -> Response."""

    @abstractmethod
    def __call__(self, req: Request) -> Response:
        """Обработать запрос."""


class RequestObserver(ABC):
    """Получатель уведомлений о завершённых запросах (лог, GUI, ...)."""

    @abstractmethod
    def on_request(self, record: RequestRecord) -> None:
        """Вызывается после отправки ответа."""
