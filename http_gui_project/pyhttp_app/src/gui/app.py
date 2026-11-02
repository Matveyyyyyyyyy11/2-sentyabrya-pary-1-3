"""Главное окно: вкладки и журнал приложения."""
import queue
import tkinter as tk
from tkinter import ttk

from .client_tab import ClientTab
from .server_tab import ServerTab
from .settings import HistoryStore, Settings
from .settings_tab import SettingsTab

THEMES = {
    "light": {"bg": "#f0f0f0", "fg": "#111111", "field": "#ffffff"},
    "dark": {"bg": "#2b2b2b", "fg": "#e6e6e6", "field": "#1e1e1e"},
}


class App(tk.Tk):
    """Окно приложения. Сетевая работа — в потоках, GUI обновляется через after."""

    def __init__(self, log_queue: "queue.Queue[str]") -> None:
        super().__init__()
        self.title("HTTP-клиент и сервер")
        self.geometry("980x780")
        self._log_queue = log_queue
        self._settings = Settings()
        self._history = HistoryStore()

        notebook = self.notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        self.client_tab = ClientTab(notebook, self._settings, self._history)
        self.server_tab = ServerTab(notebook)
        notebook.add(self.client_tab, text="Клиент")
        notebook.add(self.server_tab, text="Сервер")
        notebook.add(SettingsTab(notebook, self._settings, self._history, self.apply_theme),
                     text="Настройки")

        log_frame = ttk.LabelFrame(self, text="Журнал приложения")
        log_frame.pack(fill="x", padx=6, pady=4)
        self._log_text = tk.Text(log_frame, height=6, state="disabled", wrap="none")
        self._log_text.pack(fill="x")
        self.apply_theme("light")
        self._poll_id = self.after(150, self._poll_log)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _poll_log(self) -> None:
        lines = []
        for _ in range(200):
            try:
                lines.append(self._log_queue.get_nowait())
            except queue.Empty:
                break
        if lines:
            self._log_text.config(state="normal")
            self._log_text.insert("end", "\n".join(lines) + "\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self._poll_id = self.after(150, self._poll_log)

    def apply_theme(self, name: str) -> None:
        """Применить светлую или тёмную тему ко всем виджетам."""
        colors = THEMES.get(name, THEMES["light"])
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=colors["bg"], foreground=colors["fg"],
                        fieldbackground=colors["field"])
        style.configure("Treeview", background=colors["field"], foreground=colors["fg"],
                        fieldbackground=colors["field"])
        style.map("TCombobox", fieldbackground=[("readonly", colors["field"])],
                  foreground=[("readonly", colors["fg"])])
        self.configure(bg=colors["bg"])
        self._recolor(self, colors)

    def _recolor(self, widget: tk.Misc, colors: dict) -> None:
        if isinstance(widget, tk.Text):
            widget.config(bg=colors["field"], fg=colors["fg"], insertbackground=colors["fg"])
        elif isinstance(widget, tk.Canvas):
            widget.config(bg=colors["bg"])
        for child in widget.winfo_children():
            self._recolor(child, colors)

    def on_close(self) -> None:
        """Остановить сервер и закрыть окно."""
        self.server_tab.shutdown()
        self.after_cancel(self._poll_id)
        self.destroy()
