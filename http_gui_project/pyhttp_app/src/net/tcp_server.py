"""TCP-сервер: bind, listen, accept с опросом (чтобы можно было остановить)."""
import socket
from typing import Optional, Tuple

from ..errors import HttpConnectionError
from .socket_wrapper import Socket


class TcpServer:
    """Слушающий сокет. accept() не блокируется дольше accept_timeout."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080,
                 backlog: int = 128, accept_timeout: float = 0.2) -> None:
        self._host = host
        self._port = port
        self._backlog = backlog
        self._accept_timeout = accept_timeout
        self._sock: Optional[socket.socket] = None

    @property
    def port(self) -> int:
        """Фактический порт (полезно при port=0)."""
        if self._sock is None:
            return self._port
        return self._sock.getsockname()[1]

    def start(self) -> None:
        """bind + listen; SO_REUSEADDR позволяет перезапуск без ожидания TIME_WAIT."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self._host, self._port))
            sock.listen(self._backlog)
            sock.settimeout(self._accept_timeout)
        except OSError as exc:
            sock.close()
            raise HttpConnectionError(
                f"cannot listen on {self._host}:{self._port}: {exc}") from exc
        self._sock = sock

    def accept(self) -> Optional[Tuple[Socket, tuple]]:
        """Принять соединение; None, если за accept_timeout никто не пришёл."""
        sock = self._sock
        if sock is None:
            raise HttpConnectionError("server is not listening")
        try:
            conn, addr = sock.accept()
        except TimeoutError:
            return None
        except OSError as exc:
            raise HttpConnectionError(f"accept failed: {exc}") from exc
        return Socket(conn), addr

    def close(self) -> None:
        """Закрыть слушающий сокет (идемпотентно)."""
        sock, self._sock = self._sock, None
        if sock is not None:
            sock.close()
