"""Составные виджеты: таблица заголовков, лог запросов, ответ, индикатор."""
import tkinter as tk
from tkinter import ttk
from typing import Dict

from ..errors import ParseError
from ..http.headers import validate_header
from ..http.response import Response
from ..server.interfaces import RequestRecord
from .highlight import detect_kind, find_spans, format_body

TAG_COLORS = {"key": "#4a9eff", "string": "#2e9d4f", "number": "#d97706",
              "literal": "#c04fd0", "tag": "#4a9eff", "comment": "#888888",
              "error": "#d62828"}
MAX_LOG_ROWS = 2000


class HeaderTable(ttk.Frame):
    """Таблица «имя → значение» с добавлением и удалением строк."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self._tree = ttk.Treeview(self, columns=("name", "value"), show="headings",
                                  height=4, selectmode="browse")
        self._tree.heading("name", text="Заголовок")
        self._tree.heading("value", text="Значение")
        self._tree.column("name", width=160, stretch=False)
        self._tree.column("value", width=360)
        self._tree.grid(row=0, column=0, columnspan=5, sticky="nsew")
        self._name_var = tk.StringVar()
        self._value_var = tk.StringVar()
        ttk.Entry(self, textvariable=self._name_var, width=20).grid(row=1, column=0, sticky="ew")
        ttk.Entry(self, textvariable=self._value_var).grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Button(self, text="Добавить", command=self.add_from_fields).grid(row=1, column=2)
        delete_btn = ttk.Button(self, text="Удалить", command=self.delete_selected)
        delete_btn.grid(row=1, column=3, padx=4)
        self._error = ttk.Label(self, text="", foreground=TAG_COLORS["error"])
        self._error.grid(row=2, column=0, columnspan=5, sticky="w")
        self.columnconfigure(1, weight=1)

    def add_from_fields(self) -> None:
        """Добавить строку из полей ввода (с валидацией)."""
        name, value = self._name_var.get().strip(), self._value_var.get().strip()
        if not name:
            return
        try:
            validate_header(name, value)
        except ParseError as exc:
            self._error.config(text=str(exc))
            return
        self._error.config(text="")
        self._tree.insert("", "end", values=(name, value))
        self._name_var.set("")
        self._value_var.set("")

    def delete_selected(self) -> None:
        """Удалить выбранную строку."""
        for item in self._tree.selection():
            self._tree.delete(item)

    def get_headers(self) -> Dict[str, str]:
        """Заголовки из таблицы; ParseError при некорректных."""
        headers: Dict[str, str] = {}
        for item in self._tree.get_children():
            name, value = self._tree.item(item, "values")
            validate_header(str(name), str(value))
            headers[str(name)] = str(value)
        return headers

    def clear(self) -> None:
        """Удалить все строки."""
        self._tree.delete(*self._tree.get_children())
        self._error.config(text="")


class LogTable(ttk.Frame):
    """Лог запросов сервера: время, метод, путь, статус, мс."""

    COLUMNS = (("time", "Время", 80), ("method", "Метод", 70), ("path", "Путь", 260),
               ("status", "Статус", 70), ("ms", "мс", 70))

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self._tree = ttk.Treeview(self, columns=[c[0] for c in self.COLUMNS],
                                  show="headings", height=10)
        for key, title, width in self.COLUMNS:
            self._tree.heading(key, text=title)
            self._tree.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(self, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.tag_configure("error", foreground=TAG_COLORS["error"])
        self._tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

    def __len__(self) -> int:
        return len(self._tree.get_children())

    def add(self, record: RequestRecord) -> None:
        """Добавить строку (старые удаляются при переполнении)."""
        tags = ("error",) if record.status >= 400 else ()
        item = self._tree.insert("", "end", tags=tags, values=(
            record.time, record.method, record.path, record.status,
            f"{record.elapsed_ms:.1f}"))
        self._tree.see(item)
        rows = self._tree.get_children()
        if len(rows) > MAX_LOG_ROWS:
            self._tree.delete(rows[0])

    def clear(self) -> None:
        """Очистить лог."""
        self._tree.delete(*self._tree.get_children())


class StatusIndicator(tk.Canvas):
    """Круглый индикатор: зелёный — работает, красный — остановлен."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, width=18, height=18, highlightthickness=0)
        self._dot = self.create_oval(2, 2, 16, 16, fill="#c0392b", outline="")

    def set_running(self, running: bool) -> None:
        """Переключить цвет."""
        self.itemconfig(self._dot, fill="#27ae60" if running else "#c0392b")


class ResponseView(ttk.Frame):
    """Область ответа: статус, заголовки, тело (с подсветкой JSON/HTML)."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self._status = ttk.Label(self, text="Ответ появится здесь",
                                 font=("TkDefaultFont", 10, "bold"))
        self._status.grid(row=0, column=0, sticky="w")
        self._headers = self._make_text(1, 7)
        self._body = self._make_text(2, 14)
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

    def _make_text(self, row: int, height: int) -> tk.Text:
        frame = ttk.Frame(self)
        frame.grid(row=row, column=0, sticky="nsew", pady=2)
        text = tk.Text(frame, height=height, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        for tag, color in TAG_COLORS.items():
            text.tag_configure(tag, foreground=color)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return text

    @staticmethod
    def _set(widget: tk.Text, content: str, spans=()) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        for tag, start, end in spans:
            widget.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")
        widget.config(state="disabled")

    def clear(self) -> None:
        """Сбросить область ответа."""
        self._status.config(text="Ответ появится здесь", foreground="")
        self._set(self._headers, "")
        self._set(self._body, "")

    def show_response(self, resp: Response, elapsed_ms: float) -> None:
        """Показать статус, заголовки и тело."""
        self._status.config(
            text=f"{resp.version} {resp.status} {resp.reason}   ({elapsed_ms:.0f} мс)",
            foreground="#27ae60" if resp.status < 400 else TAG_COLORS["error"])
        self._set(self._headers, "\n".join(f"{k}: {v}" for k, v in resp.headers.items()))
        kind = detect_kind(resp.get_header("Content-Type") or "", resp.text)
        text = format_body(kind, resp.text)
        self._set(self._body, text, find_spans(kind, text))

    def show_error(self, message: str) -> None:
        """Показать ошибку в области ответа (а не в консоли)."""
        self._status.config(text="Ошибка", foreground=TAG_COLORS["error"])
        self._set(self._headers, "")
        self._set(self._body, message, [("error", 0, len(message))])
