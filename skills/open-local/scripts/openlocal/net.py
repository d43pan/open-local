"""Fetching URLs that come from the registry or from the web. All of them are untrusted.

Protections:
  * http and https only, no credentials in the URL, a short list of ports
  * every hostname is resolved first and refused unless all its addresses are public
    (blocks loopback, private, link-local, cloud metadata and reserved ranges: SSRF)
  * the connection is made to the address that was checked (no DNS rebinding window)
  * redirects are followed by hand, at most five, each one checked the same way
  * responses are capped in size and time; nothing fetched is ever executed
  * robots.txt is honoured (RFC 9309) and requests to one host are spaced out
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import time
import urllib.parse
import urllib.robotparser
import zlib
from dataclasses import dataclass, field

USER_AGENT = "open-local/0.1 (+https://github.com/d43pan/open-local)"
MAX_BYTES = 5_000_000
MAX_REDIRECTS = 5
ALLOWED_PORTS = {80, 443, 8080, 8443}
HOST_DELAY = 1.0  # seconds between requests to the same host

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


class Blocked(Exception):
    """The URL was refused before any request was made."""


class FetchError(Exception):
    """The request was made and failed."""


@dataclass
class Response:
    url: str
    status: int
    headers: dict[str, str]
    body: bytes
    truncated: bool = False
    redirects: list[str] = field(default_factory=list)

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";")[0].strip().lower()

    def text(self) -> str:
        ctype = self.headers.get("content-type", "")
        charset = "utf-8"
        if "charset=" in ctype.lower():
            charset = ctype.lower().split("charset=")[1].split(";")[0].strip(" \"'") or "utf-8"
        try:
            return self.body.decode(charset, "replace")
        except LookupError:
            return self.body.decode("utf-8", "replace")


def public_addresses(host: str, port: int) -> list[str]:
    """Resolve host and return its addresses, or raise Blocked if any is not public."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise FetchError(f"cannot resolve {host}: {e}") from e
    addrs = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        if not ip.is_global or ip.is_multicast:
            raise Blocked(f"{host} resolves to a non-public address ({ip})")
        addrs.append(str(ip))
    if not addrs:
        raise FetchError(f"no addresses for {host}")
    return addrs


def check_url(url: str) -> urllib.parse.SplitResult:
    """Validate the shape of a URL. Raises Blocked. Does not touch the network."""
    if not isinstance(url, str) or len(url) > 2000 or any(c in url for c in "\r\n\t "):
        raise Blocked("malformed URL")
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise Blocked(f"scheme not allowed: {parts.scheme or '(none)'}")
    if parts.username or parts.password:
        raise Blocked("credentials in URL")
    if not parts.hostname:
        raise Blocked("no host")
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as e:
        raise Blocked("bad port") from e
    if port not in ALLOWED_PORTS:
        raise Blocked(f"port not allowed: {port}")
    host = parts.hostname
    try:  # a literal IP address must itself be public
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise Blocked(f"non-public address ({ip})")
    except ValueError:
        if "." not in host or host.endswith((".local", ".internal", ".localhost")) or host == "localhost":
            raise Blocked(f"host not allowed: {host}")
    return parts


def _request(parts: urllib.parse.SplitResult, method: str, headers: dict, timeout: float, max_bytes: int):
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == "https" else 80)
    ip = public_addresses(host, port)[0]
    wait = HOST_DELAY - (time.monotonic() - _last_hit.get(host, 0.0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()
    try:
        raw = socket.create_connection((ip, port), timeout)
        if parts.scheme == "https":
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
            conn.sock = ctx.wrap_socket(raw, server_hostname=host)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
            conn.sock = raw
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        conn.request(method, path, headers=headers)
        resp = conn.getresponse()
        hdrs = {k.lower(): v for k, v in resp.getheaders()}
        body, truncated = b"", False
        if method != "HEAD":
            body = resp.read(max_bytes + 1)
            if len(body) > max_bytes:
                body, truncated = body[:max_bytes], True
            if hdrs.get("content-encoding", "").lower() in ("gzip", "deflate"):
                try:
                    d = zlib.decompressobj(47)
                    body = d.decompress(body, max_bytes)
                    truncated = truncated or bool(d.unconsumed_tail)
                except zlib.error:
                    pass
        conn.close()
        return resp.status, hdrs, body, truncated
    except (OSError, http.client.HTTPException) as e:
        raise FetchError(f"{type(e).__name__}: {e}") from e


def allowed_by_robots(url: str, timeout: float = 15.0) -> bool:
    parts = check_url(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _robots:
        rp = None
        try:
            r = fetch(origin + "/robots.txt", respect_robots=False, timeout=timeout, max_bytes=500_000)
            if r.status >= 500:  # RFC 9309: unreachable means assume disallowed
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(["User-agent: *", "Disallow: /"])
            elif r.status == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(r.text().splitlines())
        except (Blocked, FetchError):
            rp = None  # no usable robots.txt: allowed
        _robots[origin] = rp
    rp = _robots[origin]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def fetch(url: str, *, method: str = "GET", timeout: float = 20.0, max_bytes: int = MAX_BYTES,
          respect_robots: bool = True, accept: str = "*/*", if_none_match: str | None = None) -> Response:
    """GET (or HEAD) a public URL safely. Raises Blocked or FetchError.

    With if_none_match (an ETag from an earlier response), an unchanged resource comes
    back as status 304 with an empty body.
    """
    seen: list[str] = []
    for _ in range(MAX_REDIRECTS + 1):
        parts = check_url(url)
        if respect_robots and not allowed_by_robots(url, timeout):
            raise Blocked("disallowed by robots.txt")
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "gzip", "Host": parts.netloc,
                   "Connection": "close"}
        if if_none_match:
            headers["If-None-Match"] = if_none_match
        status, hdrs, body, truncated = _request(parts, method, headers, timeout, max_bytes)
        if status in (301, 302, 303, 307, 308) and hdrs.get("location"):
            seen.append(url)
            url = urllib.parse.urljoin(url, hdrs["location"])
            continue
        return Response(url, status, hdrs, body, truncated, seen)
    raise FetchError("too many redirects")
