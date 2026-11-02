"""Обработчики маршрутов: /, /echo, /time, /headers, /status/{code}."""
import json
from datetime import datetime, timezone

from ..http.request import Request
from ..http.response import Response
from ..http.status import has_body, reason_phrase
from .interfaces import RequestHandler
from .router import Router

JSON_TYPE = "application/json; charset=utf-8"
HTML_TYPE = "text/html; charset=utf-8"
TEXT_TYPE = "text/plain; charset=utf-8"

_HELLO_PAGE = (
    "<!DOCTYPE html>\n<html lang=\"en\">\n<head><meta charset=\"utf-8\">"
    "<title>Hello</title></head>\n<body><h1>Hello</h1>"
    "<p>Served by a hand-written HTTP server.</p></body>\n</html>\n"
)


def json_response(payload: object, status: int = 200) -> Response:
    """Ответ с JSON-телом."""
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(status, headers={"Content-Type": JSON_TYPE}, body=body)


class IndexHandler(RequestHandler):
    """GET / — HTML-страница «Hello»."""

    def __call__(self, req: Request) -> Response:
        return Response(200, headers={"Content-Type": HTML_TYPE},
                        body=_HELLO_PAGE.encode("utf-8"))


class EchoHandler(RequestHandler):
    """POST /echo — тело запроса, Content-Type сохраняется."""

    def __call__(self, req: Request) -> Response:
        content_type = req.get_header("Content-Type") or "application/octet-stream"
        return Response(200, headers={"Content-Type": content_type}, body=req.body)


class TimeHandler(RequestHandler):
    """GET /time — текущее время в JSON."""

    def __call__(self, req: Request) -> Response:
        now = datetime.now(timezone.utc)
        return json_response({"time": now.isoformat(timespec="seconds"),
                              "timestamp": round(now.timestamp(), 3)})


class HeadersHandler(RequestHandler):
    """GET /headers — все заголовки запроса в JSON."""

    def __call__(self, req: Request) -> Response:
        return json_response(dict(req.headers))


class StatusHandler(RequestHandler):
    """GET /status/{code} — ответ с указанным кодом (200–599)."""

    def __call__(self, req: Request) -> Response:
        tail = req.route_path[len("/status/"):]
        if not (tail.isdigit() and 200 <= int(tail) <= 599):
            return Response(400, "Bad Request", headers={"Content-Type": TEXT_TYPE},
                            body=b"status code must be an integer 200..599")
        code = int(tail)
        body = f"{code} {reason_phrase(code)}".encode("utf-8") if has_body(code) else b""
        return Response(code, headers={"Content-Type": TEXT_TYPE}, body=body)


def build_default_router() -> Router:
    """Маршруты из задания."""
    router = Router()
    router.route("GET", "/", IndexHandler())
    router.route("POST", "/echo", EchoHandler())
    router.route("GET", "/time", TimeHandler())
    router.route("GET", "/headers", HeadersHandler())
    router.route_prefix("GET", "/status/", StatusHandler())
    return router
