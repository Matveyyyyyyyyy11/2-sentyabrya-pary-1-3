"""Вкладка «Сервер»."""
import queue
import tkinter as tk
import webbrowser
from tkinter import ttk
from typing import Optional

from ..errors import HttpConnectionError
from ..server.handlers import build_default_router
from ..server.http_server import HttpServer
from ..server.interfaces import RequestRecord
from ..server.observers import LoggingObserver, QueueObserver
from .widgets import TAG_COLORS, LogTable, StatusIndicator


class ServerTab(ttk.Frame):
    """Запуск/остановка сервера и живой лог запросов (через queue + after)."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=8)
        self._server: Optional[HttpServer] = None
        self._records: "queue.Queue[RequestRecord]" = queue.Queue()
        self._port = tk.StringVar(value="8080")

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew")
        ttk.Label(top, text="Порт:").pack(side="left")
        self._port_entry = ttk.Entry(top, textvariable=self._port, width=8)
        self._port_entry.pack(side="left", padx=4)
        self._start_btn = ttk.Button(top, text="Запустить", command=self.start_server)
        self._start_btn.pack(side="left")
        self._stop_btn = ttk.Button(top, text="Остановить", command=self.stop_server,
                                    state="disabled")
        self._stop_btn.pack(side="left", padx=4)
        self._indicator = StatusIndicator(top)
        self._indicator.pack(side="left", padx=8)
        self._state = ttk.Label(top, text="Остановлен")
        self._state.pack(side="left")

        self._log = LogTable(self)
        self._log.grid(row=1, column=0, sticky="nsew", pady=8)

        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, sticky="ew")
        ttk.Button(bottom, text="Очистить лог", command=self._log.clear).pack(side="left")
        ttk.Button(bottom, text="Открыть в браузере",
                   command=self.open_browser).pack(side="left", padx=6)
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        self._poll_id: Optional[str] = self.after(100, self._poll)

    def _read_port(self) -> int:
        text = self._port.get().strip()
        if not text.isdigit() or not 1 <= int(text) <= 65535:
            raise ValueError("Порт должен быть целым числом от 1 до 65535")
        return int(text)

    def start_server(self) -> None:
        """Запустить сервер на порту из поля."""
        try:
            port = self._read_port()
        except ValueError as exc:
            self._state.config(text=str(exc), foreground=TAG_COLORS["error"])
            return
        server = HttpServer(build_default_router(), port=port,
                            observers=[QueueObserver(self._records), LoggingObserver()])
        try:
            server.start()
        except HttpConnectionError as exc:
            self._state.config(text=f"Ошибка: {exc}", foreground=TAG_COLORS["error"])
            return
        self._server = server
        self._set_running(True, f"Работает на порту {server.port}")

    def stop_server(self) -> None:
        """Остановить сервер (порт освобождается)."""
        if self._server is not None:
            self._server.stop()
            self._server = None
        self._set_running(False, "Остановлен")

    def _set_running(self, running: bool, text: str) -> None:
        self._indicator.set_running(running)
        self._state.config(text=text, foreground="")
        self._start_btn.config(state="disabled" if running else "normal")
        self._stop_btn.config(state="normal" if running else "disabled")
        self._port_entry.config(state="disabled" if running else "normal")

    def open_browser(self) -> None:
        """Открыть http://localhost:<порт>/ в браузере."""
        port = self._server.port if self._server is not None else 8080
        webbrowser.open(f"http://localhost:{port}/")

    def _poll(self) -> None:
        """Главный поток: переносит записи из очереди в таблицу."""
        for _ in range(200):
            try:
                self._log.add(self._records.get_nowait())
            except queue.Empty:
                break
        self._poll_id = self.after(100, self._poll)

    def shutdown(self) -> None:
        """Корректно остановить сервер при закрытии окна."""
        if self._server is not None:
            self._server.stop()
            self._server = None

    def destroy(self) -> None:
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
        super().destroy()
