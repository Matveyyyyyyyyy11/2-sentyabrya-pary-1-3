"""Интерфейс (ABC) двунаправленного байтового соединения."""
from abc import ABC, abstractmethod


class Connection(ABC):
    """Соединение: отправка, чтение, закрытие, поддержка with."""

    @abstractmethod
    def send_all(self, data: bytes) -> None:
        """Отправить все байты."""

    @abstractmethod
    def recv(self, size: int) -> bytes:
        """Прочитать до size байт; b'' означает, что собеседник закрыл соединение."""

    @abstractmethod
    def close(self) -> None:
        """Закрыть соединение (повторный вызов безопасен)."""

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
