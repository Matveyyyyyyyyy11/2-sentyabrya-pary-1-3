"""Настройки приложения и история запросов (сохранение в JSON)."""
import json
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Settings:
    """Параметры, общие для вкладок."""

    timeout_ms: int = 5000
    theme: str = "light"


class HistoryStore:
    """История запросов клиента."""

    def __init__(self) -> None:
        self._items: List[Dict[str, Any]] = []

    def add(self, item: Dict[str, Any]) -> None:
        """Добавить запись."""
        self._items.append(item)

    def __len__(self) -> int:
        return len(self._items)

    def save(self, path: str) -> None:
        """Записать историю в JSON-файл."""
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self._items, handle, ensure_ascii=False, indent=2)
