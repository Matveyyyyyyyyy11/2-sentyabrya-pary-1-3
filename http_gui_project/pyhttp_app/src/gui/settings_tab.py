"""Вкладка «Настройки»: таймаут, тема, сохранение истории."""
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable

from .settings import HistoryStore, Settings


class SettingsTab(ttk.Frame):
    """Таймаут по умолчанию, светлая/тёмная тема, история запросов в JSON."""

    def __init__(self, master: tk.Misc, settings: Settings, history: HistoryStore,
                 on_theme: Callable[[str], None]) -> None:
        super().__init__(master, padding=12)
        self._settings = settings
        self._history = history
        self._on_theme = on_theme
        self._timeout = tk.StringVar(value=str(settings.timeout_ms))
        self._theme = tk.StringVar(value=settings.theme)
        self._info = ttk.Label(self, text="")

        ttk.Label(self, text="Таймаут по умолчанию, мс:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(self, from_=100, to=60000, increment=100, width=8,
                    textvariable=self._timeout).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(self, text="Тема:").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Combobox(self, textvariable=self._theme, values=("light", "dark"),
                     state="readonly", width=8).grid(row=1, column=1, sticky="w", padx=6)
        apply_btn = ttk.Button(self, text="Применить", command=self.apply)
        apply_btn.grid(row=2, column=0, sticky="w", pady=6)
        ttk.Button(self, text="Сохранить историю в JSON…",
                   command=self.save_history).grid(row=3, column=0, sticky="w")
        self._info.grid(row=4, column=0, columnspan=2, sticky="w", pady=8)

    def apply(self) -> None:
        """Применить настройки (с валидацией таймаута)."""
        text = self._timeout.get().strip()
        if not text.isdigit() or not 1 <= int(text) <= 600000:
            self._info.config(text="Таймаут: целое число 1…600000 мс")
            return
        self._settings.timeout_ms = int(text)
        self._settings.theme = self._theme.get()
        self._on_theme(self._settings.theme)
        self._info.config(text="Настройки применены")

    def save_history(self) -> None:
        """Сохранить историю запросов в выбранный JSON-файл."""
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            self._history.save(path)
            self._info.config(text=f"Сохранено записей: {len(self._history)}")
