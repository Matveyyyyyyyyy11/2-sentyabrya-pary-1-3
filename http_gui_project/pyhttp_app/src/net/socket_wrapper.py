"""Обёртка над сокетом (контекстный менеджер) и in-memory соединение для тестов."""
import socket
from typing import Optional

from ..errors import HttpConnectionError, HttpTimeoutError
from .interfaces import Connection


class Socket(Connection):
    """Сокет с автоматическим закрытием и переводом ошибок ОС в наши исключения."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock: Optional[socket.socket] = sock

    def _require(self) -> socket.socket:
        sock = self._sock
        if sock is None:
            raise HttpConnectionError("socket is closed")
        return sock

    @property
    def is_closed(self) -> bool:
        """True после close()."""
        return self._sock is None

    def settimeout(self, seconds: Optional[float]) -> None:
        """Таймаут операций чтения/записи (None — без таймаута)."""
        self._require().settimeout(seconds)

    def send_all(self, data: bytes) -> None:
        sock = self._require()
        try:
            sock.sendall(data)
        except TimeoutError as exc:
            raise HttpTimeoutError("send timed out") from exc
        except OSError as exc:
            raise HttpConnectionError(f"send failed: {exc}") from exc

    def recv(self, size: int) -> bytes:
        sock = self._require()
        try:
            return sock.recv(size)
        except TimeoutError as exc:
            raise HttpTimeoutError("read timed out") from exc
        except OSError as exc:
            raise HttpConnectionError(f"receive failed: {exc}") from exc

    def shutdown(self) -> None:
        """Прервать обмен (будит поток, висящий в recv); ошибки игнорируются."""
        sock = self._sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def close(self) -> None:
        sock, self._sock = self._sock, None
        if sock is not None:
            sock.close()


class BytesConnection(Connection):
    """Соединение поверх готового буфера байт: удобно для разбора и unit-тестов."""

    def __init__(self, data: bytes = b"") -> None:
        self._data = bytearray(data)
        self.sent = bytearray()
        self.closed = False

    def send_all(self, data: bytes) -> None:
        self.sent.extend(data)

    def recv(self, size: int) -> bytes:
        chunk = bytes(self._data[:size])
        del self._data[:size]
        return chunk

    def close(self) -> None:
        self.closed = True
