"""Тесты."""
import json

from src.http.request import Request
from src.server.handlers import build_default_router


def dispatch(method, path, body=b"", headers=None):
    return build_default_router().dispatch(Request(method, path, headers=headers or {},
                                                   body=body))


def test_index_is_hello_html():
    resp = dispatch("GET", "/")
    assert resp.status == 200 and b"Hello" in resp.body
    assert "html" in resp.get_header("Content-Type")


def test_echo_keeps_body_and_content_type():
    resp = dispatch("POST", "/echo", b"abc", {"Content-Type": "text/plain"})
    assert resp.body == b"abc" and resp.get_header("Content-Type") == "text/plain"


def test_time_is_json():
    assert "time" in json.loads(dispatch("GET", "/time").body)


def test_headers_returns_request_headers():
    data = json.loads(dispatch("GET", "/headers", headers={"X-A": "1"}).body)
    assert data["X-A"] == "1"


def test_status_code():
    assert dispatch("GET", "/status/418").status == 418
    assert dispatch("GET", "/status/204").body == b""


def test_status_invalid():
    assert dispatch("GET", "/status/abc").status == 400
    assert dispatch("GET", "/status/99").status == 400


def test_unknown_path_and_wrong_method_are_404():
    assert dispatch("GET", "/nonexistent").status == 404
    assert dispatch("GET", "/echo").status == 404
    assert dispatch("DELETE", "/").status == 404


def test_query_string_ignored_in_routing():
    assert dispatch("GET", "/time?x=1").status == 200


def test_path_traversal_is_just_404():
    assert dispatch("GET", "/../../etc/passwd").status == 404
