"""Наблюдатели за запросами: запись в logging и передача в GUI через очередь."""
import logging
import queue

from .interfaces import RequestObserver, RequestRecord

LOG = logging.getLogger("http_gui.server")


class LoggingObserver(RequestObserver):
    """Пишет каждый запрос в модуль logging (файл и GUI-журнал)."""

    def on_request(self, record: RequestRecord) -> None:
        LOG.info("%s %s %s -> %d (%.1f ms)", record.client, record.method,
                 record.path, record.status, record.elapsed_ms)


class QueueObserver(RequestObserver):
    """Кладёт записи в queue.Queue; GUI забирает их в главном потоке через root.after."""

    def __init__(self, target: "queue.Queue[RequestRecord]") -> None:
        self._queue = target

    def on_request(self, record: RequestRecord) -> None:
        self._queue.put(record)
