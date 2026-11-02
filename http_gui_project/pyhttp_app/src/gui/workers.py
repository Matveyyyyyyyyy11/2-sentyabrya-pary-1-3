"""Фоновый поток для HTTP-запроса: результат уходит в очередь, GUI не блокируется."""
import queue
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

from ..client.http_client import HttpClient
from ..http.response import Response


@dataclass
class JobResult:
    """Результат запроса: либо ответ, либо исключение."""

    elapsed_ms: float
    response: Optional[Response] = None
    error: Optional[BaseException] = None


class RequestJob(threading.Thread):
    """Выполняет один запрос и кладёт JobResult в очередь."""

    def __init__(self, client: HttpClient, method: str, url: str, body: bytes,
                 content_type: str, headers: Dict[str, str],
                 results: "queue.Queue[JobResult]") -> None:
        super().__init__(daemon=True, name="http-request")
        self._client = client
        self._method = method
        self._url = url
        self._body = body
        self._content_type = content_type
        self._headers = headers
        self._results = results

    def run(self) -> None:
        started = time.perf_counter()
        try:
            if self._method == "GET":
                response = self._client.get(self._url, self._headers)
            else:
                response = self._client.post(self._url, self._body,
                                             self._content_type, self._headers)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            # любая ошибка должна дойти до GUI и быть показана в области ответа
            self._results.put(JobResult((time.perf_counter() - started) * 1000, error=exc))
        else:
            self._results.put(JobResult((time.perf_counter() - started) * 1000,
                                        response=response))
