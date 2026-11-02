"""Маршрутизатор: (метод, путь) -> обработчик."""
from typing import Callable, Dict, List, Tuple

from ..http.request import Request
from ..http.response import Response

Handler = Callable[[Request], Response]


class Router:
    """Хранит обработчики как Callable (а не имена функций) — их легко подменять в тестах."""

    def __init__(self) -> None:
        self._routes: Dict[Tuple[str, str], Handler] = {}
        self._prefixes: List[Tuple[str, str, Handler]] = []

    def route(self, method: str, path: str, handler: Handler) -> None:
        """Точное совпадение метода и пути."""
        self._routes[(method.upper(), path)] = handler

    def route_prefix(self, method: str, prefix: str, handler: Handler) -> None:
        """Совпадение по префиксу пути (например, /status/)."""
        self._prefixes.append((method.upper(), prefix, handler))

    def dispatch(self, req: Request) -> Response:
        """Найти обработчик; нет подходящего — 404 Not Found."""
        method, path = req.method.upper(), req.route_path
        handler = self._routes.get((method, path))
        if handler is None:
            for pref_method, prefix, candidate in self._prefixes:
                if pref_method == method and path.startswith(prefix):
                    handler = candidate
                    break
        if handler is None:
            return Response(404, "Not Found",
                            headers={"Content-Type": "text/plain; charset=utf-8"},
                            body=b"404 Not Found")
        return handler(req)
