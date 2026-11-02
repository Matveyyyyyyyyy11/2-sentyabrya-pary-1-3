"""Снимает скриншоты GUI (Linux: xvfb-run -a -s '-screen 0 1100x820x24' python tools/make_screenshots.py)."""
import queue
import subprocess
import time

from src.client.http_client import HttpClient
from src.gui.app import App
from src.logging_setup import setup_logging

OUT = "docs/screenshots"


def pump(app, seconds, until=lambda: False):
    """Обрабатывать события GUI заданное время или пока не выполнится условие."""
    end = time.time() + seconds
    while time.time() < end and not until():
        app.update()
        time.sleep(0.01)


def shot(app, name):
    """Сохранить снимок экрана."""
    pump(app, 0.4)
    subprocess.run(["import", "-window", "root", f"{OUT}/{name}.png"], check=True)
    print("saved", name)


def send(app, method, url, body=""):
    """Заполнить вкладку клиента и дождаться ответа."""
    tab = app.client_tab
    tab._method.set(method)  # pylint: disable=protected-access
    tab._on_method_change()  # pylint: disable=protected-access
    tab._url.set(url)  # pylint: disable=protected-access
    tab._body.config(state="normal")  # pylint: disable=protected-access
    tab._body.delete("1.0", "end")  # pylint: disable=protected-access
    tab._body.insert("1.0", body)  # pylint: disable=protected-access
    tab._on_method_change()  # pylint: disable=protected-access
    tab.send_request()
    pump(app, 5, until=lambda: not tab._busy)  # pylint: disable=protected-access


def main():
    """Сценарий съёмки."""
    log_queue = queue.Queue()
    setup_logging("/tmp/shots.log", log_queue)
    app = App(log_queue)
    app.geometry("1000x800+0+0")
    app.server_tab._port.set("8080")  # pylint: disable=protected-access
    app.server_tab.start_server()
    app.notebook.select(app.server_tab)
    shot(app, "S4_server_running")

    app.notebook.select(app.client_tab)
    send(app, "GET", "http://localhost:8080/time")
    shot(app, "S1_client_get")

    header_table = app.client_tab._headers  # pylint: disable=protected-access
    header_table._name_var.set("X-Demo")  # pylint: disable=protected-access
    header_table._value_var.set("1")  # pylint: disable=protected-access
    header_table.add_from_fields()
    send(app, "POST", "http://localhost:8080/echo", '{"hello": "world", "n": 42}')
    app.client_tab._content_type.set("application/json")  # pylint: disable=protected-access
    send(app, "POST", "http://localhost:8080/echo", '{"hello": "world", "n": 42}')
    shot(app, "S2_client_post_echo")

    send(app, "GET", "garbage")
    shot(app, "S3_client_error_invalid_url")
    send(app, "GET", "http://localhost:9/")
    shot(app, "S3b_client_error_connection_refused")

    client = HttpClient(2000)
    for path in ["/", "/time", "/headers", "/status/418", "/nonexistent", "/status/204",
                 "/status/500", "/time", "/", "/status/301"]:
        client.get(f"http://localhost:8080{path}")
    app.notebook.select(app.server_tab)
    pump(app, 1)
    shot(app, "S9_server_log")
    app.on_close()


if __name__ == "__main__":
    main()
