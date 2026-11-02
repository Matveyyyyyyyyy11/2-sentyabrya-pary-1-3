"""HTTP-сервер: цикл accept в отдельном потоке + поток на каждое соединение."""
import logging
import threading
import time
from typing import List, Optional, Set

from ..errors import HttpConnectionError, HttpTimeoutError, ParseError
from ..http.parser import MessageReader, Parser
from ..http.request import Request
from ..http.response import Response
from ..http.serializer import Serializer
from ..net.socket_wrapper import Socket
from ..net.tcp_server import TcpServer
from .interfaces import RequestObserver, RequestRecord
from .router import Router

LOG = logging.getLogger("http_gui.server")
SERVER_NAME = "PyHttpGui/1.0"


def _wants_keep_alive(req: Request) -> bool:
    tokens = {t.strip().lower() for t in (req.get_header("Connection") or "").split(",")}
    if req.version == "HTTP/1.0":
        return "keep-alive" in tokens
    return "close" not in tokens


class HttpServer:
    """Запускается/останавливается; обрабатывает соединения параллельно."""

    def __init__(self, router: Router, host: str = "127.0.0.1", port: int = 8080,
                 observers: Optional[List[RequestObserver]] = None,
                 idle_timeout: float = 5.0, max_connections: int = 256) -> None:
        self._router = router
        self._host = host
        self._port = port
        self._observers: List[RequestObserver] = list(observers or [])
        self._idle_timeout = idle_timeout
        self._max_connections = max_connections
        self._tcp: Optional[TcpServer] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()          # защищает _connections и _workers
        self._notify_lock = threading.Lock()   # упорядочивает уведомления наблюдателей
        self._connections: Set[Socket] = set()
        self._workers: Set[threading.Thread] = set()

    def add_observer(self, observer: RequestObserver) -> None:
        """Подписать наблюдателя."""
        with self._notify_lock:
            self._observers.append(observer)

    @property
    def running(self) -> bool:
        """Работает ли цикл приёма соединений."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def port(self) -> int:
        """Фактический порт (при port=0 назначается ОС)."""
        return self._tcp.port if self._tcp is not None else self._port

    @property
    def active_connections(self) -> int:
        """Число открытых клиентских соединений."""
        with self._lock:
            return len(self._connections)

    def start(self) -> None:
        """Занять порт и запустить поток приёма соединений."""
        if self.running:
            raise RuntimeError("server is already running")
        tcp = TcpServer(self._host, self._port)
        tcp.start()  # HttpConnectionError, если порт занят
        self._tcp = tcp
        self._port = tcp.port
        self._stop.clear()
        self._thread = threading.Thread(target=self._serve, args=(tcp,),
                                        name="http-accept", daemon=True)
        self._thread.start()
        LOG.info("server started on %s:%d", self._host, tcp.port)

    def stop(self, timeout: float = 2.0) -> None:
        """Остановить: флаг + закрытие слушающего сокета + обрыв активных соединений."""
        self._stop.set()
        if self._tcp is not None:
            self._tcp.close()
        with self._lock:
            connections = list(self._connections)
            workers = list(self._workers)
        for conn in connections:
            conn.shutdown()  # будит потоки, висящие в recv
        if self._thread is not None:
            self._thread.join(timeout)
        for worker in workers:
            worker.join(timeout)
        self._thread = None
        LOG.info("server stopped")

    def _serve(self, tcp: TcpServer) -> None:
        while not self._stop.is_set():
            try:
                accepted = tcp.accept()
            except HttpConnectionError:
                if self._stop.is_set():
                    break
                LOG.exception("accept failed")
                time.sleep(0.1)
                continue
            if accepted is None:
                continue
            sock, addr = accepted
            with self._lock:
                overloaded = len(self._connections) >= self._max_connections
                if not overloaded:
                    self._connections.add(sock)
                    worker = threading.Thread(target=self._handle_connection,
                                              args=(sock, addr), daemon=True,
                                              name=f"http-conn-{addr[1]}")
                    self._workers.add(worker)
                    worker.start()
            if overloaded:
                self._reject_overloaded(sock)

    @staticmethod
    def _reject_overloaded(sock: Socket) -> None:
        with sock:
            try:
                resp = Response(503, headers={"Connection": "close"}, body=b"busy")
                sock.send_all(Serializer.serialize(resp))
            except (HttpConnectionError, HttpTimeoutError):
                pass

    def _handle_connection(self, sock: Socket, addr: tuple) -> None:
        client = f"{addr[0]}:{addr[1]}"
        try:
            with sock:
                sock.settimeout(self._idle_timeout)
                self._conversation(sock, MessageReader(sock), client)
        except (HttpConnectionError, HttpTimeoutError):
            pass  # клиент ушёл или молчит дольше idle_timeout
        finally:
            with self._lock:
                self._connections.discard(sock)
                self._workers.discard(threading.current_thread())

    def _conversation(self, sock: Socket, reader: MessageReader, client: str) -> None:
        while not self._stop.is_set():
            try:
                req = reader.read_request()
                if req is None:
                    return
                Parser.validate_request(req)
            except ParseError as exc:
                LOG.warning("%s bad request: %s", client, exc)
                started = time.perf_counter()
                self._respond(sock, Response(400, "Bad Request", body=b"400 Bad Request"),
                              False)
                self._notify("-", "-", 400, started, client)
                return
            started = time.perf_counter()
            keep_alive = _wants_keep_alive(req)
            response = self._dispatch(req)
            try:
                self._respond(sock, response, keep_alive)
            finally:
                self._notify(req.method, req.path, response.status, started, client)
            if not keep_alive:
                return

    def _dispatch(self, req: Request) -> Response:
        try:
            return self._router.dispatch(req)
        except Exception:  # pylint: disable=broad-exception-caught
            # обработчик не должен ронять поток соединения: отвечаем 500
            LOG.exception("handler failed for %s %s", req.method, req.path)
            return Response(500, "Internal Server Error", body=b"500 Internal Server Error")

    @staticmethod
    def _respond(sock: Socket, response: Response, keep_alive: bool) -> None:
        headers = dict(response.headers)
        headers["Server"] = SERVER_NAME
        headers["Connection"] = "keep-alive" if keep_alive else "close"
        if "Content-Type" not in headers and response.body:
            headers["Content-Type"] = "text/plain; charset=utf-8"
        out = Response(response.status, response.reason, response.version, headers,
                       response.body)
        sock.send_all(Serializer.serialize(out))

    def _notify(self, method: str, path: str, status: int, started: float,
                client: str) -> None:
        record = RequestRecord(time.strftime("%H:%M:%S"), method, path, status,
                               round((time.perf_counter() - started) * 1000, 2), client)
        with self._notify_lock:
            for observer in self._observers:
                try:
                    observer.on_request(record)
                except Exception:  # pylint: disable=broad-exception-caught
                    LOG.exception("observer failed")
