"""TCP-клиент: подключение с таймаутом, опционально TLS."""
import socket
import ssl

from ..errors import HttpConnectionError, HttpTimeoutError
from .socket_wrapper import Socket


class TcpClient:
    """Создаёт подключённые Socket."""

    def __init__(self, timeout: float = 5.0) -> None:
        self._timeout = timeout

    def connect(self, host: str, port: int, use_tls: bool = False) -> Socket:
        """Подключиться к host:port; таймаут действует и на connect, и на чтение."""
        try:
            plain = socket.create_connection((host, port), timeout=self._timeout)
        except TimeoutError as exc:
            raise HttpTimeoutError(f"connect to {host}:{port} timed out") from exc
        except OSError as exc:
            raise HttpConnectionError(f"cannot connect to {host}:{port}: {exc}") from exc
        sock = plain
        if use_tls:
            try:
                context = ssl.create_default_context()
                sock = context.wrap_socket(plain, server_hostname=host)
            except TimeoutError as exc:
                plain.close()
                raise HttpTimeoutError(f"TLS handshake with {host} timed out") from exc
            except OSError as exc:  # ssl.SSLError — подкласс OSError
                plain.close()
                raise HttpConnectionError(f"TLS error with {host}: {exc}") from exc
        sock.settimeout(self._timeout)
        return Socket(sock)
