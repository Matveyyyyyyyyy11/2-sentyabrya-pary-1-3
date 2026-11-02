"""Тесты."""
import pytest

from src.http.url import ParseError, Url


def test_u1_full_url():
    url = Url.parse("http://host:8080/path?q=1")
    assert (url.host, url.port, url.path, url.query) == ("host", 8080, "/path", "q=1")


def test_u2_default_port_http():
    assert Url.parse("http://host/path").port == 80


def test_default_port_https():
    url = Url.parse("https://host/")
    assert url.port == 443 and url.is_secure


def test_u3_garbage():
    with pytest.raises(ParseError):
        Url.parse("garbage")


@pytest.mark.parametrize("bad", ["", "   ", "ftp://host/", "http://", "http://host:0/",
                                 "http://host:65536/", "http://host:abc/",
                                 "http://ho st/", "http://user@host/", "http://a:b:c/",
                                 "http://[::1/"])
def test_invalid_urls(bad):
    with pytest.raises(ParseError):
        Url.parse(bad)


def test_no_path_defaults_to_slash():
    assert Url.parse("http://host").path == "/"
    assert Url.parse("http://host?x=1").target == "/?x=1"


def test_fragment_is_dropped():
    assert Url.parse("http://host/a#frag").target == "/a"


def test_max_port_ok():
    assert Url.parse("http://h:65535/").port == 65535


def test_ipv6():
    url = Url.parse("http://[::1]:8080/x")
    assert url.host == "::1" and url.port == 8080
    assert url.host_header == "[::1]:8080"


def test_host_header_omits_default_port():
    assert Url.parse("http://example.com/").host_header == "example.com"
    assert Url.parse("http://example.com:81/").host_header == "example.com:81"


@pytest.mark.parametrize("location,expected", [
    ("http://other/x", "http://other/x"),
    ("/abs", "http://h:9/abs"),
    ("rel", "http://h:9/dir/rel"),
    ("//cdn/x", "http://cdn/x"),
])
def test_resolve(location, expected):
    assert str(Url.parse("http://h:9/dir/page").resolve(location)) == expected
