"""Интеграционные тесты: сервер в потоке, клиент — в тесте (I1–I10 + дополнительные)."""
import queue
import socket
import threading
import time

import pytest

from src.client.http_client import HttpClient
from src.errors import HttpConnectionError, HttpError, HttpTimeoutError
from src.http.parser import MessageReader
from src.http.request import Request
from src.http.response import Response
from src.http.serializer import Serializer
from src.net.tcp_client import TcpClient
from src.server.handlers import build_default_router
from src.server.http_server import HttpServer
from src.server.observers import QueueObserver


def _slow(_req):
    time.sleep(1.0)
    return Response(200, body=b"late")


def _boom(_req):
    raise RuntimeError("handler bug")


def _redirect(_req):
    return Response(302, headers={"Location": "/"})


@pytest.fixture(name="server")
def server_fixture():
    router = build_default_router()
    router.route("GET", "/slow", _slow)
    router.route("GET", "/boom", _boom)
    router.route("GET", "/redirect", _redirect)
    records = queue.Queue()
    srv = HttpServer(router, port=0, idle_timeout=2.0, observers=[QueueObserver(records)])
    srv.records = records
    srv.start()
    yield srv
    srv.stop()


def url(srv, path="/"):
    return f"http://127.0.0.1:{srv.port}{path}"


def raw_exchange(srv, payload):
    with TcpClient(2.0).connect("127.0.0.1", srv.port) as sock:
        sock.send_all(payload)
        return MessageReader(sock).read_response()


def test_i1_get_root(server):
    resp = HttpClient(2000).get(url(server))
    assert resp.status == 200 and b"Hello" in resp.body


def test_i2_post_echo(server):
    resp = HttpClient(2000).post(url(server, "/echo"), b"abc", "text/plain")
    assert resp.body == b"abc" and resp.get_header("Content-Type") == "text/plain"


def test_i3_status_404(server):
    assert HttpClient(2000).get(url(server, "/status/404")).status == 404


def test_i4_nonexistent(server):
    assert HttpClient(2000).get(url(server, "/nonexistent")).status == 404


def test_i5_hundred_sequential(server):
    client = HttpClient(2000)
    assert all(client.get(url(server, "/time")).status == 200 for _ in range(100))


def test_i6_ten_parallel(server):
    statuses = []

    def work():
        statuses.append(HttpClient(3000).get(url(server)).status)

    threads = [threading.Thread(target=work) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert statuses == [200] * 10


def test_i7_timeout(server):
    client = HttpClient(100)
    with pytest.raises(HttpTimeoutError):
        client.get(url(server, "/slow"))


def test_i8_garbage_gets_400_and_server_survives(server):
    resp = raw_exchange(server, b"\x00\x01 garbage\r\n\r\n")
    assert resp.status == 400
    assert HttpClient(2000).get(url(server)).status == 200


def test_i9_keep_alive_three_requests(server):
    req = Serializer.serialize(Request("GET", "/time", headers={"Host": "x"}))
    with TcpClient(2.0).connect("127.0.0.1", server.port) as sock:
        reader = MessageReader(sock)
        for _ in range(3):
            sock.send_all(req)
            resp = reader.read_response()
            assert resp.status == 200
            assert resp.get_header("Connection") == "keep-alive"


def test_connection_close_is_honoured(server):
    resp = HttpClient(2000).get(url(server))
    assert resp.get_header("Connection") == "close"


def test_i10_thousand_requests_no_leaks(server):
    baseline = threading.active_count()
    client = HttpClient(3000)
    for _ in range(1000):
        assert client.get(url(server, "/time")).status == 200
    deadline = time.time() + 3
    while server.active_connections and time.time() < deadline:
        time.sleep(0.05)
    assert server.active_connections == 0
    assert threading.active_count() <= baseline + 2


def test_missing_host_is_400(server):
    assert raw_exchange(server, b"GET / HTTP/1.1\r\n\r\n").status == 400


def test_huge_header_is_400(server):
    payload = b"GET / HTTP/1.1\r\nHost: x\r\nX: " + b"a" * 50_000 + b"\r\n\r\n"
    try:
        status = raw_exchange(server, payload).status
    except HttpConnectionError:  # сервер успел закрыть соединение раньше, чем мы дописали
        status = 400
    assert status == 400


def test_content_length_with_chunked_is_400(server):
    payload = (b"POST /echo HTTP/1.1\r\nHost: x\r\nContent-Length: 3\r\n"
               b"Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n")
    assert raw_exchange(server, payload).status == 400


def test_handler_exception_gives_500_and_server_lives(server):
    assert HttpClient(2000).get(url(server, "/boom")).status == 500
    assert HttpClient(2000).get(url(server)).status == 200


def test_redirects(server):
    assert HttpClient(2000).get(url(server, "/redirect")).status == 302
    client = HttpClient(2000, max_redirects=3)
    assert client.get(url(server, "/redirect")).status == 200


def test_redirect_loop_raises(server):
    server_router = build_default_router()
    server_router.route("GET", "/loop", lambda _r: Response(302, headers={"Location": "/loop"}))
    srv = HttpServer(server_router, port=0)
    srv.start()
    try:
        with pytest.raises(HttpError):
            HttpClient(2000, max_redirects=2).get(url(srv, "/loop"))
    finally:
        srv.stop()


def test_connection_refused_after_stop_and_restart_same_port():
    srv = HttpServer(build_default_router(), port=0)
    srv.start()
    port = srv.port
    assert HttpClient(1000).get(f"http://127.0.0.1:{port}/").status == 200
    srv.stop()
    with pytest.raises(HttpConnectionError):
        HttpClient(1000).get(f"http://127.0.0.1:{port}/")
    again = HttpServer(build_default_router(), port=port)
    again.start()  # SO_REUSEADDR: порт освободился
    try:
        assert HttpClient(1000).get(f"http://127.0.0.1:{port}/").status == 200
    finally:
        again.stop()


def test_port_in_use_raises():
    first = HttpServer(build_default_router(), port=0)
    first.start()
    try:
        with pytest.raises(HttpConnectionError):
            HttpServer(build_default_router(), port=first.port).start()
    finally:
        first.stop()


def test_observer_receives_records(server):
    HttpClient(2000).get(url(server, "/status/418"))
    record = server.records.get(timeout=2)
    assert (record.method, record.path, record.status) == ("GET", "/status/418", 418)
    assert record.elapsed_ms >= 0


def test_client_validates_url():
    with pytest.raises(Exception) as info:
        HttpClient().get("garbage")
    assert type(info.value).__name__ == "ParseError"


def test_client_reads_chunked_from_raw_server():
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def serve():
        conn, _ = listener.accept()
        with conn:
            conn.recv(4096)
            conn.sendall(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
                         b"3\r\nabc\r\n3\r\ndef\r\n0\r\n\r\n")

    thread = threading.Thread(target=serve)
    thread.start()
    try:
        port = listener.getsockname()[1]
        assert HttpClient(2000).get(f"http://127.0.0.1:{port}/").body == b"abcdef"
    finally:
        thread.join()
        listener.close()


def test_client_settings_validation():
    client = HttpClient()
    with pytest.raises(ValueError):
        client.set_timeout(0)
    with pytest.raises(ValueError):
        client.follow_redirects(-1)


def test_raise_for_status(server):
    resp = HttpClient(2000).get(url(server, "/nonexistent"))
    with pytest.raises(HttpError) as info:
        resp.raise_for_status()
    assert info.value.status == 404
