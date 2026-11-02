"""Таблица стандартных фраз статус-кодов."""

REASONS = {
    100: "Continue", 101: "Switching Protocols",
    200: "OK", 201: "Created", 202: "Accepted", 204: "No Content",
    206: "Partial Content",
    301: "Moved Permanently", 302: "Found", 303: "See Other",
    304: "Not Modified", 307: "Temporary Redirect", 308: "Permanent Redirect",
    400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
    404: "Not Found", 405: "Method Not Allowed", 408: "Request Timeout",
    409: "Conflict", 410: "Gone", 411: "Length Required",
    413: "Payload Too Large", 414: "URI Too Long",
    415: "Unsupported Media Type", 418: "I'm a teapot",
    422: "Unprocessable Entity", 429: "Too Many Requests",
    431: "Request Header Fields Too Large",
    500: "Internal Server Error", 501: "Not Implemented",
    502: "Bad Gateway", 503: "Service Unavailable", 504: "Gateway Timeout",
}


def reason_phrase(code: int) -> str:
    """Стандартная фраза для кода (или нейтральная, если код нестандартный)."""
    return REASONS.get(code, "Unknown Status")


def has_body(code: int) -> bool:
    """Может ли ответ с таким кодом иметь тело (1xx, 204, 304 — нет)."""
    return not (code < 200 or code in (204, 304))
