import pytest
from conftest import FIX
from openlocal import feeds


def read(name):
    return (FIX / name).read_bytes()


def test_rss():
    f = feeds.parse(read("feed.rss"))
    assert f["kind"] == "rss" and f["title"] == "Harbour Times" and len(f["items"]) == 3
    first = f["items"][0]
    assert first["url"] == "https://harbourtimes.example.org/a1"
    assert first["published"].startswith("2026-11-23T14:00:00")
    assert first["summary"] == "The council voted 4-1 on Thursday."  # markup and script removed
    assert f["items"][2]["published"] is None


def test_atom():
    f = feeds.parse(read("feed.atom"))
    assert f["kind"] == "atom" and f["items"][0]["url"] == "https://alder.example.org/n/1"
    assert f["items"][0]["published"].startswith("2026-11-20")


def test_json_feed():
    f = feeds.parse(read("feed.json"))
    assert f["kind"] == "jsonfeed" and f["items"][0]["title"] == "Hello"
    assert f["items"][0]["published"] == "2026-11-21T08:00:00-05:00"


def test_icalendar():
    f = feeds.parse(read("council.ics"))
    assert f["kind"] == "ical" and f["title"] == "Alder Council" and len(f["items"]) == 3
    e = f["items"][0]
    assert e["start"] == "2026-12-03T19:00:00" and e["end"] == "2026-12-03T21:00:00"
    assert e["location"] == "Town Hall, 40 Commons"
    assert e["summary"] == "Agenda: dredging, budgethearing continued" or "hearing continued" in e["summary"]
    assert f["items"][2]["start"] == "2027-06-01"
    assert e["published"] is None  # an event date is never reported as a publication date


def test_entity_declarations_are_refused():
    with pytest.raises(feeds.NotAFeed):
        feeds.parse(read("bomb.xml"))


@pytest.mark.parametrize("data", [b"<html><body>hi</body></html>", b"", b"{\"a\": 1}", b"not a feed", b"<rss><channel><item>"])
def test_things_that_are_not_feeds(data):
    with pytest.raises(feeds.NotAFeed):
        feeds.parse(data)


def test_summaries_are_short():
    long = b"<rss version='2.0'><channel><title>t</title><item><title>x</title><description>" + b"word " * 500 + b"</description></item></channel></rss>"
    assert len(feeds.parse(long)["items"][0]["summary"]) <= feeds.SUMMARY_CHARS + 1


def test_discovery_finds_advertised_and_linked_feeds_and_skips_unsafe_ones(fake_net):
    net = fake_net({
        "https://alder.example.org/planning": (200, "page.html"),
        "https://alder.example.org/feed/": (200, "feed.rss"),
        "https://alder.example.org/council.ics": (200, "council.ics"),
        "https://alder.example.org/minutes.rss": (200, "feed.atom"),
        "https://alder.example.org/rss": (200, b"<html>404 page that returns 200</html>"),
    })
    found = feeds.discover("https://alder.example.org/planning")
    urls = {f["url"]: f for f in found["feeds"]}
    assert set(urls) == {"https://alder.example.org/feed/", "https://alder.example.org/council.ics", "https://alder.example.org/minutes.rss",
                         "https://alder.example.org/planning"}
    assert urls["https://alder.example.org/council.ics"]["kind"] == "ical"
    assert urls["https://alder.example.org/planning"]["kind"] == "events"   # the page marks up its hearing as an Event
    assert urls["https://alder.example.org/feed/"]["newest"].startswith("2026-11-23")
    assert found["title"].startswith("Planning Board")
    assert "http://169.254.169.254/latest/rss.xml" in net.calls  # it was tried, and the fetch layer refused it


def test_discovery_on_a_feed_url_returns_that_feed(fake_net):
    fake_net({"https://alder.example.org/feed/": (200, "feed.rss")})
    found = feeds.discover("https://alder.example.org/feed/")
    assert [f["kind"] for f in found["feeds"]] == ["rss"]


def test_events_page_reads_only_marked_up_events():
    from openlocal import feeds
    f = feeds.read("events", (FIX / "events.html").read_bytes(), "https://alder.example.org/whats-on")
    assert f["kind"] == "events" and f["title"] == "Alder Hall: What's on"
    titles = [i["title"] for i in f["items"]]
    assert titles == ["Folk night & open mic", "Winter show opening", "Last summer's fair"]   # duplicate dropped, org ignored
    folk = f["items"][0]
    assert folk["url"] == "https://alder.example.org/events/folk-night" and folk["location"] == "Alder Hall, 1 Commons, Alder"
    assert folk["start"].startswith("2026-11-28T19:30")


def test_a_page_without_event_data_is_not_an_events_feed():
    import pytest
    from openlocal import feeds
    with pytest.raises(feeds.NotAFeed):
        feeds.read("events", b"<html><head><title>No events</title></head><body><p>Meets 9 Dec 2026</p></body></html>")


def test_squarespace_events_json_uses_the_real_event_dates():
    body = (FIX / "squarespace-events.json").read_bytes()
    f = feeds.read("events", body, "https://alder-vineyard.example.org/events?format=json")
    assert f["kind"] == "events" and f["title"] == "Events"
    assert [i["title"] for i in f["items"]] == ["Live music: Folk duo", "Holiday market"]  # past and untitled left out
    folk = f["items"][0]
    assert folk["start"] == "2026-11-27T15:00:00-05:00" and folk["end"] == "2026-11-27T18:00:00-05:00"
    assert folk["url"] == "https://alder-vineyard.example.org/events/folk-duo"
    assert folk["location"] == "Alder Vineyard, 1 Main Rd, Alder" and folk["summary"] == "Songs by the fire ."


def test_squarespace_reader_refuses_other_json():
    import pytest
    with pytest.raises(feeds.NotAFeed):
        feeds.parse_squarespace_events(b'{"items": []}')
