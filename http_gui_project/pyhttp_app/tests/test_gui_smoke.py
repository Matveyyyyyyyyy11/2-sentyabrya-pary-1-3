"""Дымовой тест GUI (нужен дисплей; без него пропускается)."""
import gc
import queue
import time

import pytest

tk = pytest.importorskip("tkinter")

from src.gui.app import App  # noqa: E402  pylint: disable=wrong-import-position


@pytest.fixture(name="app")
def app_fixture():
    try:
        window = App(queue.Queue())
    except tk.TclError:
        pytest.skip("нет дисплея")
    yield window
    window.on_close()
    del window
    gc.collect()  # Tk-переменные должны финализироваться в главном потоке


def pump(app, seconds, until=lambda: False):
    end = time.time() + seconds
    while time.time() < end and not until():
        app.update()
        time.sleep(0.01)


def test_client_server_roundtrip_in_gui(app):
    server_tab, client_tab = app.server_tab, app.client_tab
    server_tab._port.set("18765")  # noqa: SLF001  pylint: disable=protected-access
    server_tab.start_server()
    client_tab._url.set("http://127.0.0.1:18765/status/418")  # pylint: disable=protected-access
    client_tab.send_request()
    pump(app, 3, until=lambda: len(server_tab._log) > 0)  # pylint: disable=protected-access
    assert len(server_tab._log) == 1  # pylint: disable=protected-access
    assert "418" in client_tab._response._status.cget("text")  # pylint: disable=protected-access


def test_invalid_url_shows_error_in_gui(app):
    app.client_tab._url.set("garbage")  # pylint: disable=protected-access
    app.client_tab.send_request()
    shown = app.client_tab._response._body.get("1.0", "end")  # pylint: disable=protected-access
    assert "ParseError" in shown
