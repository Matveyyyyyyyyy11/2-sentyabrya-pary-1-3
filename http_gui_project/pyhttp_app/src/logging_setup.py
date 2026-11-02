"""Настройка logging: вывод в файл и (опционально) в очередь для GUI."""
import logging
import queue
from typing import Optional

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class QueueLogHandler(logging.Handler):
    """Складывает отформатированные записи в queue.Queue (читает GUI в главном потоке)."""

    def __init__(self, target: "queue.Queue[str]") -> None:
        super().__init__()
        self._queue = target

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._queue.put_nowait(self.format(record))
        except queue.Full:
            self.handleError(record)


def setup_logging(log_file: str = "http_gui.log",
                  gui_queue: "Optional[queue.Queue[str]]" = None,
                  level: int = logging.INFO) -> logging.Logger:
    """Настроить логгер «http_gui» (повторный вызов заменяет обработчики)."""
    logger = logging.getLogger("http_gui")
    logger.setLevel(level)
    for old in list(logger.handlers):
        logger.removeHandler(old)
        old.close()
    formatter = logging.Formatter(LOG_FORMAT, "%H:%M:%S")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if gui_queue is not None:
        gui_handler = QueueLogHandler(gui_queue)
        gui_handler.setFormatter(formatter)
        logger.addHandler(gui_handler)
    return logger
