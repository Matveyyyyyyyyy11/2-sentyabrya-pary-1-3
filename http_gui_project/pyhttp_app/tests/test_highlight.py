"""Тесты."""
from src.gui.highlight import detect_kind, find_spans, format_body


def test_detect_kind():
    assert detect_kind("application/json", "{}") == "json"
    assert detect_kind("text/html; charset=utf-8", "<p>") == "html"
    assert detect_kind("", "[1]") == "json"
    assert detect_kind("text/plain", "hi") == "text"


def test_format_json_pretty_and_invalid():
    assert format_body("json", '{"a":1}') == '{\n  "a": 1\n}'
    assert format_body("json", "{broken") == "{broken"


def test_json_spans():
    text = '{"k": "v", "n": 12, "b": true}'
    tags = [t for t, _s, _e in find_spans("json", text)]
    assert tags == ["key", "string", "key", "number", "key", "literal"]


def test_html_spans():
    tags = [t for t, _s, _e in find_spans("html", "<!-- c --><b>x</b>")]
    assert tags == ["comment", "tag", "tag"]


def test_plain_text_no_spans():
    assert not find_spans("text", "abc")
