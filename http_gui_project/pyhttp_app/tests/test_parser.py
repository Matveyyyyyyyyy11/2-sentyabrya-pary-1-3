"""Тесты."""
import pytest

from src.errors import ParseError
from src.http.parser import MAX_HEADER_BYTES, Parser


def test_u4_simple_request():
    req = Parser.parse_request(b"GET / HTTP/1.1\r\n\r\n")
    assert (req.method, req.path, req.version) == ("GET", "/", "HTTP/1.1")


def test_u5_body_with_content_length():
    raw = b"POST /echo HTTP/1.1\r\nHost: x\r\nContent-Length: 5\r\n\r\nhello"
    assert Parser.parse_request(raw).body == b"hello"


def test_u6_missing_host_rejected_when_required():
    with pytest.raises(ParseError):
        Parser.parse_request(b"GET / HTTP/1.1\r\n\r\n", require_host=True)


def test_http10_does_not_need_host():
    assert Parser.parse_request(b"GET / HTTP/1.0\r\n\r\n", require_host=True).path == "/"


def test_u9_chunked_response():
    raw = (b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n"
           b"4\r\nWiki\r\n5;ext=1\r\npedia\r\n0\r\nTrailer: x\r\n\r\n")
    assert Parser.parse_response(raw).body == b"Wikipedia"


def test_u10_oversized_header():
    raw = b"GET / HTTP/1.1\r\nHost: x\r\nX: " + b"a" * (MAX_HEADER_BYTES + 10) + b"\r\n\r\n"
    with pytest.raises(ParseError):
        Parser.parse_request(raw)


def test_oversized_header_without_terminator():
    with pytest.raises(ParseError):
        Parser.parse_request(b"GET / HTTP/1.1\r\nX: " + b"a" * 20000)


@pytest.mark.parametrize("raw", [
    b"garbage\r\n\r\n",
    b"GET /\r\n\r\n",
    b"get / HTTP/1.1\r\n\r\n",
    b"GET / HTTX/1.1\r\n\r\n",
    b"GET / HTTP/1.1\r\nno-colon-line\r\n\r\n",
    b"GET / HTTP/1.1\r\n bad: fold\r\n\r\n",
    b"GET / HTTP/1.1\r\nBad Name: v\r\n\r\n",
])
def test_malformed_requests(raw):
    with pytest.raises(ParseError):
        Parser.parse_request(raw)


def test_content_length_and_chunked_conflict():
    raw = (b"POST / HTTP/1.1\r\nContent-Length: 3\r\n"
           b"Transfer-Encoding: chunked\r\n\r\n0\r\n\r\n")
    with pytest.raises(ParseError):
        Parser.parse_request(raw)


@pytest.mark.parametrize("value", ["abc", "-1", "1, 2", "99999999999999"])
def test_invalid_content_length(value):
    raw = f"POST / HTTP/1.1\r\nContent-Length: {value}\r\n\r\nx".encode()
    with pytest.raises(ParseError):
        Parser.parse_request(raw)


def test_truncated_body():
    with pytest.raises(ParseError):
        Parser.parse_request(b"POST / HTTP/1.1\r\nContent-Length: 10\r\n\r\nabc")


def test_header_names_are_case_insensitive_and_duplicates_merge():
    req = Parser.parse_request(b"GET / HTTP/1.1\r\nhost: a\r\nAccept: x\r\naccept: y\r\n\r\n")
    assert req.get_header("HOST") == "a"
    assert req.get_header("accept") == "x, y"


def test_response_status_line():
    resp = Parser.parse_response(b"HTTP/1.1 404 Not Found\r\nContent-Length: 2\r\n\r\nno")
    assert (resp.status, resp.reason, resp.body) == (404, "Not Found", b"no")


@pytest.mark.parametrize("line", [b"HTTP/1.1 abc OK", b"HTTP/1.1 99 X", b"HTTP/1.1 700 X",
                                  b"FTP 200 OK"])
def test_bad_status_line(line):
    with pytest.raises(ParseError):
        Parser.parse_response(line + b"\r\n\r\n")


def test_response_without_length_reads_until_close():
    assert Parser.parse_response(b"HTTP/1.0 200 OK\r\n\r\nstream").body == b"stream"


def test_204_has_no_body():
    assert Parser.parse_response(b"HTTP/1.1 204 No Content\r\n\r\n").body == b""


def test_bad_chunk_size():
    with pytest.raises(ParseError):
        Parser.parse_response(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nZZ\r\n")


def test_unsupported_transfer_encoding():
    with pytest.raises(ParseError):
        Parser.parse_response(b"HTTP/1.1 200 OK\r\nTransfer-Encoding: gzip\r\n\r\n")


def test_non_origin_form_target_rejected_by_validation():
    req = Parser.parse_request(b"GET http://evil/ HTTP/1.1\r\nHost: x\r\n\r\n")
    with pytest.raises(ParseError):
        Parser.validate_request(req)
