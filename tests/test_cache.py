"""The local copies of feeds: fewer requests, never a silently stale answer."""
import datetime as dt

from openlocal import cache, net, recent

FEED = "https://alder.example.org/feed/"


class Site:
    """A site that honours ETags, counts requests and can be switched off."""

    def __init__(self):
        self.calls, self.body, self.etag, self.down, self.blocked = [], b"<rss><channel><title>one</title></channel></rss>", '"v1"', False, False

    def __call__(self, url, **kw):
        self.calls.append(kw)
        if self.blocked:
            raise net.Blocked("disallowed by robots.txt")
        if self.down:
            raise net.FetchError("timed out")
        if kw.get("if_none_match") == self.etag:
            return net.Response(url, 304, {}, b"")
        return net.Response(url, 200, {"etag": self.etag, "content-type": "application/rss+xml"}, self.body)


def make(tmp_path, site, minutes=60):
    clock = {"t": 1_000_000.0}
    return cache.Cache(fetch=site, max_age_minutes=minutes, root=tmp_path / "c", clock=lambda: clock["t"]), clock


def test_a_recent_copy_is_used_without_asking_the_site(tmp_path):
    site = Site(); c, clock = make(tmp_path, site)
    first = c(FEED); clock["t"] += 600; second = c(FEED)
    assert len(site.calls) == 1 and second.body == first.body and second.status == 200
    assert c.how[FEED] == {"from": "copy", "copy_minutes_old": 10}


def test_an_older_copy_is_checked_with_the_sites_own_tag(tmp_path):
    site = Site(); c, clock = make(tmp_path, site)
    c(FEED); clock["t"] += 2 * 3600; r = c(FEED)
    assert site.calls[1] == {"if_none_match": '"v1"'} and r.status == 200 and r.body == site.body
    assert c.how[FEED]["from"] == "copy, site says unchanged"
    clock["t"] += 600; c(FEED)
    assert len(site.calls) == 2, "an unchanged answer renews the copy"


def test_a_changed_feed_replaces_the_copy(tmp_path):
    site = Site(); c, clock = make(tmp_path, site)
    c(FEED); site.body, site.etag = b"<rss>two</rss>", '"v2"'; clock["t"] += 2 * 3600
    assert c(FEED).body == b"<rss>two</rss>" and c.how[FEED] == {"from": "network"}


def test_fresh_means_every_source_is_asked(tmp_path):
    site = Site(); c, _ = make(tmp_path, site, minutes=0)
    c(FEED); c(FEED)
    assert len(site.calls) == 2


def test_a_site_that_is_down_gives_the_last_copy_and_says_so(tmp_path):
    site = Site(); c, clock = make(tmp_path, site)
    c(FEED); site.down = True; clock["t"] += 5 * 3600
    assert c(FEED).body == site.body
    assert c.how[FEED] == {"from": "old copy, site did not answer", "copy_minutes_old": 300}
    assert c.summary()["old_copy_site_down"] == 1 and c.summary()["oldest_copy_minutes"] == 300
    clock["t"] += (cache.KEEP_DAYS + 1) * 86400
    try:
        c(FEED); raise AssertionError("a copy past its keep time must not be served")
    except net.FetchError:
        pass


def test_a_site_that_now_refuses_is_not_read_from_a_copy(tmp_path):
    site = Site(); c, clock = make(tmp_path, site)
    c(FEED); site.blocked = True; clock["t"] += 2 * 3600
    try:
        c(FEED); raise AssertionError("robots.txt wins over a copy")
    except net.Blocked:
        pass


def test_errors_and_cut_off_bodies_are_never_kept(tmp_path):
    calls = []

    def bad(url, **kw):
        calls.append(url)
        return net.Response(url, 500, {}, b"oops") if len(calls) == 1 else net.Response(url, 200, {}, b"half", truncated=True)
    c, _ = make(tmp_path, bad)
    c(FEED); c(FEED); c(FEED)
    assert len(calls) == 3 and cache.status(tmp_path / "c")["copies"] == 0


def test_recent_reports_where_each_feed_came_from(reg, fake_net, tmp_path):
    from test_pages_recent import NETWORK, TODAY
    f = fake_net(NETWORK)
    c = cache.Cache(fetch=f, root=tmp_path / "c")
    first = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=c)
    asked = len(f.calls)
    again = cache.Cache(fetch=f, root=tmp_path / "c")
    second = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=again)
    assert len(f.calls) == asked, "the second run loads nothing"
    assert [i["title"] for i in second["items"]] == [i["title"] for i in first["items"]]
    assert first["coverage"]["cache"]["used_local_copy"] == 0
    assert second["coverage"]["cache"]["used_local_copy"] == len(second["coverage"]["fetched"]) > 0
    assert all(x["read_from"] == "copy" for x in second["coverage"]["fetched"])
    assert recent.brief(second)["coverage"]["cache"]["used_local_copy"] > 0


def test_clear_removes_the_copies(tmp_path):
    site = Site(); c, _ = make(tmp_path, site)
    c(FEED)
    assert cache.status(tmp_path / "c")["copies"] == 1 and cache.clear(tmp_path / "c") == 1
    assert cache.status(tmp_path / "c")["copies"] == 0
