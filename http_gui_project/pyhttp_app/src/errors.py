"""Исключения приложения (никаких «магических» кодов возврата)."""


class ParseError(ValueError):
    """Некорректный URL или HTTP-сообщение."""


class HttpConnectionError(ConnectionError):
    """Не удалось установить соединение или оно оборвалось."""


class HttpTimeoutError(TimeoutError):
    """Истёк таймаут соединения или чтения."""


class HttpError(Exception):
    """HTTP-ошибка: ответ 4xx/5xx или слишком много редиректов."""

    def __init__(self, status: int, message: str = "") -> None:
        text = f"HTTP {status}"
        if message:
            text += f": {message}"
        super().__init__(text)
        self.status = status
        self.message = message
