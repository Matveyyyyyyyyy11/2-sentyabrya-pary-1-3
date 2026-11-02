"""Вкладка «Клиент»."""
import queue
import tkinter as tk
from tkinter import ttk
from typing import Optional

from ..client.http_client import HttpClient
from ..errors import ParseError
from ..http.url import Url
from .settings import HistoryStore, Settings
from .widgets import HeaderTable, ResponseView
from .workers import JobResult, RequestJob


class ClientTab(ttk.Frame):
    """URL, метод, заголовки, тело, отправка в фоновом потоке, вывод ответа."""

    def __init__(self, master: tk.Misc, settings: Settings, history: HistoryStore) -> None:
        super().__init__(master, padding=8)
        self._settings = settings
        self._history = history
        self._results: "queue.Queue[JobResult]" = queue.Queue()
        self._poll_id: Optional[str] = None
        self._busy = False
        self._request_info = {"method": "GET", "url": ""}

        self._url = tk.StringVar(value="http://localhost:8080/")
        self._method = tk.StringVar(value="GET")
        self._content_type = tk.StringVar(value="text/plain")
        self._follow = tk.BooleanVar(value=False)

        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew")
        self._method_box = ttk.Combobox(top, textvariable=self._method, width=6,
                                        values=("GET", "POST"), state="readonly")
        self._method_box.pack(side="left")
        self._method_box.bind("<<ComboboxSelected>>", self._on_method_change)
        url_entry = ttk.Entry(top, textvariable=self._url)
        url_entry.pack(side="left", fill="x", expand=True, padx=6)
        url_entry.bind("<Return>", lambda _e: self.send_request())
        self._send_btn = ttk.Button(top, text="Отправить", command=self.send_request)
        self._send_btn.pack(side="left")
        ttk.Button(top, text="Очистить", command=self.clear).pack(side="left", padx=(6, 0))

        self._headers = HeaderTable(self)
        self._headers.grid(row=1, column=0, sticky="ew", pady=6)

        body_row = ttk.Frame(self)
        body_row.grid(row=2, column=0, sticky="ew")
        ttk.Label(body_row, text="Content-Type:").pack(side="left")
        self._ct_entry = ttk.Entry(body_row, textvariable=self._content_type, width=28)
        self._ct_entry.pack(side="left", padx=4)
        ttk.Checkbutton(body_row, text="Следовать редиректам (до 5)",
                        variable=self._follow).pack(side="left", padx=12)
        self._body = tk.Text(self, height=5, wrap="word")
        self._body.grid(row=3, column=0, sticky="ew", pady=4)

        status_row = ttk.Frame(self)
        status_row.grid(row=4, column=0, sticky="ew")
        self._busy_label = ttk.Label(status_row, text="")
        self._busy_label.pack(side="left")
        self._spinner = ttk.Progressbar(status_row, mode="indeterminate", length=120)

        self._response = ResponseView(self)
        self._response.grid(row=5, column=0, sticky="nsew")
        self.rowconfigure(5, weight=1)
        self.columnconfigure(0, weight=1)
        self._on_method_change()

    def _on_method_change(self, _event=None) -> None:
        post = self._method.get() == "POST"
        self._body.config(state="normal" if post else "disabled")
        self._ct_entry.config(state="normal" if post else "disabled")

    def clear(self) -> None:
        """Очистить ответ, тело и заголовки."""
        self._response.clear()
        self._headers.clear()
        self._body.config(state="normal")
        self._body.delete("1.0", "end")
        self._on_method_change()

    def send_request(self) -> None:
        """Проверить ввод и запустить запрос в фоновом потоке."""
        if self._busy:
            return
        try:
            url_text = self._url.get().strip()
            Url.parse(url_text)
            headers = self._headers.get_headers()
        except ParseError as exc:
            self._response.show_error(f"ParseError: {exc}")
            return
        method = self._method.get()
        body = self._body.get("1.0", "end-1c").encode("utf-8") if method == "POST" else b""
        client = HttpClient(self._settings.timeout_ms, 5 if self._follow.get() else 0)
        self._request_info = {"method": method, "url": url_text}
        self._set_busy(True)
        RequestJob(client, method, url_text, body, self._content_type.get().strip(),
                   headers, self._results).start()
        self._poll_id = self.after(40, self._poll)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._send_btn.config(state="disabled" if busy else "normal")
        self._busy_label.config(text="Отправка..." if busy else "")
        if busy:
            self._spinner.pack(side="left", padx=8)
            self._spinner.start(12)
        else:
            self._spinner.stop()
            self._spinner.pack_forget()

    def _poll(self) -> None:
        """Выполняется в главном потоке: забирает результат из очереди."""
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(40, self._poll)
            return
        self._poll_id = None
        self._set_busy(False)
        if result.error is not None:
            name = type(result.error).__name__
            self._response.show_error(f"{name}: {result.error}")
            outcome = {"error": f"{name}: {result.error}"}
        else:
            assert result.response is not None
            self._response.show_response(result.response, result.elapsed_ms)
            outcome = {"status": result.response.status}
        self._history.add({**self._request_info, **outcome,
                           "elapsed_ms": round(result.elapsed_ms, 1)})

    def destroy(self) -> None:
        if self._poll_id is not None:
            self.after_cancel(self._poll_id)
        super().destroy()
