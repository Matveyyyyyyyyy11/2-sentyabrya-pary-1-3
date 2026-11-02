"""Тесты."""
import pytest

from src.errors import ParseError
from src.http.parser import Parser
from src.http.request import Request
from src.http.response import Response
from src.http.serializer import Serializer


def test_u7_request_ends_with_blank_line():
    data = Serializer.serialize(Request("GET", "/", headers={"Host": "x"}))
    assert data.startswith(b"GET / HTTP/1.1\r\n") and data.endswith(b"\r\n\r\n")


def test_u8_response_has_content_length():
    data = Serializer.serialize(Response(200, body=b"hi"))
    assert b"Content-Length: 2\r\n" in data and data.endswith(b"\r\n\r\nhi")


def test_response_gets_reason_and_date():
    data = Serializer.serialize(Response(404))
    assert data.startswith(b"HTTP/1.1 404 Not Found\r\n") and b"Date: " in data


def test_post_without_body_gets_zero_length():
    data = Serializer.serialize(Request("POST", "/", headers={"Host": "x"}))
    assert b"Content-Length: 0\r\n" in data


def test_request_body_gets_length():
    data = Serializer.serialize(Request("POST", "/", body=b"abc"))
    assert b"Content-Length: 3\r\n" in data


def test_204_has_no_length_and_no_body():
    data = Serializer.serialize(Response(204, body=b"ignored"))
    assert b"Content-Length" not in data and data.endswith(b"\r\n\r\n")


def test_transfer_encoding_replaced_by_length():
    resp = Response(200, headers={"Transfer-Encoding": "chunked"}, body=b"abc")
    data = Serializer.serialize(resp)
    assert b"Transfer-Encoding" not in data and b"Content-Length: 3" in data


@pytest.mark.parametrize("headers", [{"X": "a\r\nInjected: 1"}, {"Bad Name": "v"}])
def test_header_injection_rejected(headers):
    with pytest.raises(ParseError):
        Serializer.serialize(Request("GET", "/", headers=headers))


def test_invalid_target_rejected():
    with pytest.raises(ParseError):
        Serializer.serialize(Request("GET", "/a b"))


def test_non_message_type():
    with pytest.raises(TypeError):
        Serializer.serialize("text")  # type: ignore[arg-type]


def test_roundtrip():
    original = Request("POST", "/echo?a=1", headers={"Host": "h", "X-T": "v"}, body=b"data")
    parsed = Parser.parse_request(Serializer.serialize(original))
    assert (parsed.method, parsed.path, parsed.body) == ("POST", "/echo?a=1", b"data")
    assert parsed.get_header("x-t") == "v"
