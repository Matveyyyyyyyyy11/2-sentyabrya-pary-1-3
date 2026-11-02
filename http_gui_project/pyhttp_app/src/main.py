"""Точка входа: python -m src.main"""
import queue

from .gui.app import App
from .logging_setup import setup_logging


def main() -> None:
    """Настроить логирование (файл + GUI) и запустить окно."""
    log_queue: "queue.Queue[str]" = queue.Queue()
    setup_logging("http_gui.log", log_queue)
    App(log_queue).mainloop()


if __name__ == "__main__":
    main()
