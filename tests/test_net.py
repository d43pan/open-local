import socket

import pytest
from openlocal import net


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.org/x", "gopher://example.org/", "javascript:alert(1)", "http://localhost/",
    "http://127.0.0.1/", "http://10.0.0.5/", "http://192.168.1.1/", "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/", "http://0.0.0.0/", "http://user:pw@example.org/", "https://example.org:22/", "https://example.org:6379/",
    "http://intranet/", "http://db.internal/", "http://printer.local/", "https://exa mple.org/", "https://example.org/\r\nHost: x", "",
])
def test_unsafe_urls_are_refused(url):
    with pytest.raises(net.Blocked):
        net.check_url(url)


@pytest.mark.parametrize("url", ["https://example.org/", "http://example.org:8080/feed?x=1", "https://93.184.216.34/"])
def test_public_urls_pass_the_shape_check(url):
    net.check_url(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "172.16.0.9", "192.168.0.1", "169.254.169.254", "100.64.0.9", "::1", "fd00::1", "::ffff:10.0.0.1"])
def test_names_that_resolve_to_private_addresses_are_refused(monkeypatch, ip):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(family, socket.SOCK_STREAM, 6, "", (ip, 443))])
    with pytest.raises(net.Blocked):
        net.public_addresses("evil.example.org", 443)


def test_one_private_address_among_public_ones_is_enough_to_refuse(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, 1, 6, "", ("93.184.216.34", 443)), (socket.AF_INET, 1, 6, "", ("10.0.0.1", 443))])
    with pytest.raises(net.Blocked):
        net.public_addresses("rebind.example.org", 443)


def test_redirect_to_a_private_address_is_refused(monkeypatch):
    monkeypatch.setattr(net, "_request", lambda parts, *a, **k: (302, {"location": "http://169.254.169.254/latest/"}, b"", False))
    with pytest.raises(net.Blocked):
        net.fetch("https://example.org/", respect_robots=False)


def test_redirect_to_another_scheme_is_refused(monkeypatch):
    monkeypatch.setattr(net, "_request", lambda parts, *a, **k: (301, {"location": "file:///etc/passwd"}, b"", False))
    with pytest.raises(net.Blocked):
        net.fetch("https://example.org/", respect_robots=False)


def test_redirect_loops_stop(monkeypatch):
    monkeypatch.setattr(net, "_request", lambda parts, *a, **k: (302, {"location": "/again"}, b"", False))
    with pytest.raises(net.FetchError):
        net.fetch("https://example.org/", respect_robots=False)


def test_robots_txt_is_honoured(monkeypatch):
    net._robots.clear()

    def fake(parts, *a, **k):
        if parts.path == "/robots.txt":
            return 200, {}, b"User-agent: *\nDisallow: /private/\n", False
        return 200, {"content-type": "text/html"}, b"ok", False
    monkeypatch.setattr(net, "_request", fake)
    assert net.fetch("https://robots.example.org/public").body == b"ok"
    with pytest.raises(net.Blocked):
        net.fetch("https://robots.example.org/private/page")
    net._robots.clear()


def test_robots_server_error_means_disallowed(monkeypatch):
    net._robots.clear()
    monkeypatch.setattr(net, "_request", lambda parts, *a, **k: (503, {}, b"", False))
    with pytest.raises(net.Blocked):
        net.fetch("https://down.example.org/page")
    net._robots.clear()
