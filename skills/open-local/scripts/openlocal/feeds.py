"""Read RSS, Atom, JSON Feed and iCalendar, and find feeds on a web page.

Feed content is untrusted data. It is parsed, never executed, and summaries are cut
short: a briefing should point readers to the original, not reproduce it.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import html
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

from . import net

SUMMARY_CHARS = 280
FEED_TYPES = {"application/rss+xml": "rss", "application/atom+xml": "atom", "application/feed+json": "jsonfeed",
              "application/json": "jsonfeed", "text/calendar": "ical", "application/rdf+xml": "rss"}
COMMON_PATHS = ["/feed/", "/feed", "/rss", "/rss.xml", "/atom.xml", "/index.xml", "/feed.xml", "/?format=rss",
                "/RSSFeed.aspx", "/calendar.ics", "/events/?ical=1", "/feed.json"]


class NotAFeed(Exception):
    pass


def clean(text: str | None, limit: int = SUMMARY_CHARS) -> str:
    if not text:
        return ""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"


def iso(value: str | None) -> str | None:
    """Normalise a feed date to ISO 8601, or None if it cannot be read."""
    if not value:
        return None
    value = value.strip()
    try:
        d = email.utils.parsedate_to_datetime(value)
        return d.isoformat()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
        return m.group(0) if m else None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _kids(el, name):
    return [c for c in el if _local(c.tag) == name]


def _text(el, *names):
    for n in names:
        for c in _kids(el, n):
            if c.text and c.text.strip():
                return c.text.strip()
    return None


def parse_xml(data: bytes) -> dict:
    head = data[:4000].lower()
    if b"<!entity" in data.lower()[:200_000]:
        raise NotAFeed("XML declares entities; refused")
    if b"<rss" not in head and b"<feed" not in head and b"<rdf" not in head:
        raise NotAFeed("not RSS or Atom")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise NotAFeed(f"XML does not parse: {e}") from e
    kind = "atom" if _local(root.tag) == "feed" else "rss"
    items = []
    if kind == "atom":
        title = _text(root, "title")
        for e in _kids(root, "entry"):
            link = next((l.get("href") for l in _kids(e, "link") if l.get("rel", "alternate") == "alternate" and l.get("href")), None)
            items.append({"title": clean(_text(e, "title"), 300), "url": link,
                          "published": iso(_text(e, "published", "updated")),
                          "summary": clean(_text(e, "summary", "content"))})
    else:
        channel = next(iter(_kids(root, "channel")), root)
        title = _text(channel, "title")
        for e in _kids(channel, "item") + (_kids(root, "item") if channel is not root else []):
            items.append({"title": clean(_text(e, "title"), 300), "url": _text(e, "link") or _text(e, "guid"),
                          "published": iso(_text(e, "pubdate", "date", "published")),
                          "summary": clean(_text(e, "description", "summary"))})
    return {"kind": kind, "title": clean(title, 200), "items": items}


def parse_json(data: bytes) -> dict:
    try:
        doc = json.loads(data.decode("utf-8", "replace"))
    except ValueError as e:
        raise NotAFeed("not JSON") from e
    if not isinstance(doc, dict) or "jsonfeed.org/version" not in str(doc.get("version", "")):
        raise NotAFeed("not a JSON Feed")
    items = [{"title": clean(i.get("title"), 300), "url": i.get("url") or i.get("external_url"),
              "published": iso(i.get("date_published") or i.get("date_modified")),
              "summary": clean(i.get("summary") or i.get("content_text") or i.get("content_html"))}
             for i in doc.get("items", []) if isinstance(i, dict)]
    return {"kind": "jsonfeed", "title": clean(doc.get("title"), 200), "items": items}


def _ical_date(value: str) -> str | None:
    m = re.match(r"(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})(Z)?)?", value.strip())
    if not m:
        return None
    y, mo, d, h, mi, s, z = m.groups()
    return f"{y}-{mo}-{d}" if h is None else f"{y}-{mo}-{d}T{h}:{mi}:{s}" + ("+00:00" if z else "")


def parse_ical(data: bytes) -> dict:
    text = data.decode("utf-8", "replace")
    if "BEGIN:VCALENDAR" not in text[:2000].upper():
        raise NotAFeed("not iCalendar")
    lines = re.sub(r"\r?\n[ \t]", "", text).splitlines()
    items, cur, title = [], None, None
    bs = chr(92)

    def unesc(v):
        for a, b in ((bs + "n", " "), (bs + "N", " "), (bs + ",", ","), (bs + ";", ";"), (bs + bs, bs)):
            v = v.replace(a, b)
        return v
    for line in lines:
        name, _, value = line.partition(":")
        key = name.split(";")[0].upper()
        if key == "BEGIN" and value.upper() == "VEVENT":
            cur = {}
        elif key == "END" and value.upper() == "VEVENT" and cur is not None:
            items.append({"title": clean(unesc(cur.get("SUMMARY", "")), 300), "url": cur.get("URL"),
                          "published": None, "start": _ical_date(cur.get("DTSTART", "")), "end": _ical_date(cur.get("DTEND", "")),
                          "location": clean(unesc(cur.get("LOCATION", "")), 200), "summary": clean(unesc(cur.get("DESCRIPTION", "")))})
            cur = None
        elif cur is not None and key in ("SUMMARY", "DTSTART", "DTEND", "URL", "LOCATION", "DESCRIPTION"):
            cur.setdefault(key, value)
        elif cur is None and key == "X-WR-CALNAME":
            title = value
    return {"kind": "ical", "title": clean(title, 200), "items": items}


EVENT_TYPES = {"Event", "MusicEvent", "TheaterEvent", "ExhibitionEvent", "Festival", "FoodEvent", "ScreeningEvent",
               "LiteraryEvent", "ComedyEvent", "DanceEvent", "ChildrensEvent", "EducationEvent", "SocialEvent",
               "SportsEvent", "VisualArtsEvent", "CourseInstance", "BusinessEvent"}


def _ld_events(node, out: list) -> None:
    if isinstance(node, list):
        for v in node:
            _ld_events(v, out)
    elif isinstance(node, dict):
        types = node.get("@type")
        types = set(types) if isinstance(types, list) else {types}
        if types & EVENT_TYPES and node.get("startDate"):
            out.append(node)
        for k, v in node.items():
            if k in ("@graph", "itemListElement", "item", "subEvent", "event", "events") or isinstance(v, list):
                _ld_events(v, out)


def _place_name(loc) -> str:
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, str):
        return loc
    if isinstance(loc, dict):
        name = loc.get("name") or ""
        addr = loc.get("address")
        if isinstance(addr, dict):
            addr = ", ".join(str(addr[k]) for k in ("streetAddress", "addressLocality") if addr.get(k))
        return ", ".join(x for x in (name, addr if isinstance(addr, str) else "") if x)
    return ""


def parse_events_page(data: bytes, base_url: str = "") -> dict:
    """Events a web page publishes as schema.org Event data (JSON-LD), as an event feed.

    Venue, library and arts sites often have no feed but mark up their event listings this
    way. Only marked-up events are read; the page's visible text is never guessed at.
    Raises NotAFeed when the page carries no Event data.
    """
    from .pages import parse_html
    p = parse_html(data.decode("utf-8", "replace"))
    found: list[dict] = []
    for blob in p.ld:
        try:
            _ld_events(json.loads(blob), found)
        except ValueError:
            continue
    items, seen = [], set()
    for ev in found:
        start = str(ev.get("startDate"))
        title = clean(html.unescape(str(ev.get("name") or "")), 300)
        link = ev.get("url") or ev.get("@id") or ""
        link = urllib.parse.urljoin(base_url, link) if isinstance(link, str) and link else ""
        key = (title.lower(), start[:16])
        if not title or key in seen:
            continue
        seen.add(key)
        items.append({"title": title, "url": link or None, "start": start, "end": str(ev.get("endDate") or "") or None,
                      "location": clean(_place_name(ev.get("location")), 200), "summary": clean(html.unescape(str(ev.get("description") or "")))})
    if not items:
        raise NotAFeed("no schema.org Event data on the page")
    title = next((v for k, v in p.meta if k == "og:title"), "")
    return {"kind": "events", "title": clean(title, 200), "items": items}


def parse_squarespace_events(data: bytes, base_url: str = "") -> dict:
    """A Squarespace events page read as JSON (`<page>?format=json`), as an event feed.

    Squarespace's own RSS for an events collection dates each item by when it was posted,
    not when it happens, so upcoming events look months old. The JSON view carries each
    upcoming event's real start and end. Raises NotAFeed for anything else.
    """
    try:
        d = json.loads(data)
    except ValueError as e:
        raise NotAFeed(f"not JSON: {e}") from None
    if not isinstance(d, dict) or not isinstance(d.get("upcoming"), list) or "collection" not in d:
        raise NotAFeed("not a Squarespace events collection")
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(str((d.get("website") or {}).get("timeZone") or "UTC"))
    except Exception:
        tz = dt.timezone.utc

    def when(ms):
        try:
            return dt.datetime.fromtimestamp(int(str(ms)) / 1000, tz).replace(microsecond=0).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            return None

    items = []
    for ev in d["upcoming"]:
        if not isinstance(ev, dict):
            continue
        title, start = clean(html.unescape(str(ev.get("title") or "")), 300), when(ev.get("startDate"))
        if not title or not start:
            continue
        loc = ev.get("location") if isinstance(ev.get("location"), dict) else {}
        place = ", ".join(str(loc[k]) for k in ("addressTitle", "addressLine1", "addressLine2") if loc.get(k))
        link = urllib.parse.urljoin(base_url, ev["fullUrl"]) if isinstance(ev.get("fullUrl"), str) else None
        items.append({"title": title, "url": link, "start": start, "end": when(ev.get("endDate")),
                      "location": clean(place, 200), "summary": clean(html.unescape(re.sub(r"<[^>]+>", " ", str(ev.get("excerpt") or ""))))})
    title = (d.get("collection") or {}).get("title") or ""
    return {"kind": "events", "title": clean(str(title), 200), "items": items}


def read(kind: str, data: bytes, url: str = "") -> dict:
    """Parse an endpoint's body by its registry kind."""
    if kind == "events":
        if data.lstrip()[:1] == b"{":
            return parse_squarespace_events(data, url)
        return parse_events_page(data, url)
    return parse(data)


def parse(data: bytes) -> dict:
    """Parse any supported feed. Raises NotAFeed."""
    start = data.lstrip()[:1]
    if start == b"{":
        return parse_json(data)
    if b"BEGIN:VCALENDAR" in data[:2000].upper():
        return parse_ical(data)
    return parse_xml(data)


class _Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.feeds, self.anchors, self.title, self._in_title = [], [], "", False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "link" and "alternate" in a.get("rel", "").lower() and a.get("href"):
            kind = FEED_TYPES.get(a.get("type", "").lower().strip())
            if kind:
                self.feeds.append((a["href"], kind, a.get("title", "")))
        elif tag == "a" and a.get("href"):
            h = a["href"].lower()
            if re.search(r"(rss|atom|feed)(\.xml|/|$|\?)|\.ics($|\?)|ical|format=rss|rssfeed", h) and not h.startswith(("mailto:", "javascript:")):
                self.anchors.append(a["href"])
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def newest(items: list[dict]) -> str | None:
    dates = [i.get("published") or i.get("start") for i in items if i.get("published") or i.get("start")]
    return max(dates, key=lambda d: d[:10]) if dates else None


def discover(url: str, probe: bool = True, limit: int = 12) -> dict:
    """Find feeds for a site: those it advertises, those it links to, then common paths."""
    page = net.fetch(url, accept="text/html,*/*")
    found: dict[str, dict] = {}
    tried: list[str] = []
    try:  # the URL may itself be a feed
        f = parse(page.body)
        return {"url": page.url, "title": f["title"], "feeds": [{"url": page.url, "kind": f["kind"], "title": f["title"],
                                                                "items": len(f["items"]), "newest": newest(f["items"]), "how": "the URL itself"}]}
    except NotAFeed:
        pass
    try:  # the page may list events as schema.org data: an `events` endpoint
        ev = parse_events_page(page.body, page.url)
        found[page.url] = {"url": page.url, "kind": "events", "title": ev["title"], "items": len(ev["items"]),
                           "newest": newest(ev["items"]), "how": "schema.org Event data on the page"}
    except NotAFeed:
        pass
    if b"This is Squarespace" in page.body[:20000] and urllib.parse.urlsplit(page.url).path.strip("/"):
        sq = urllib.parse.urlunsplit(urllib.parse.urlsplit(page.url)._replace(query="format=json", fragment=""))
        try:  # a Squarespace events page: its JSON view has the real event dates (its RSS does not)
            r = net.fetch(sq, accept="application/json")
            ev = parse_squarespace_events(r.body, r.url) if r.status == 200 else None
            if ev is not None:
                found[sq] = {"url": sq, "kind": "events", "title": ev["title"], "items": len(ev["items"]),
                             "newest": newest(ev["items"]), "how": "Squarespace events page read as JSON"}
        except (net.Blocked, net.FetchError, NotAFeed):
            pass
    p = _Links()
    try:
        p.feed(page.text())
    except Exception:  # malformed HTML must not stop discovery
        pass
    candidates = [(urllib.parse.urljoin(page.url, h), "advertised by the page") for h, _, _ in p.feeds]
    candidates += [(urllib.parse.urljoin(page.url, h), "linked from the page") for h in p.anchors]
    if probe:
        origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(page.url))
        candidates += [(origin + path, "common path") for path in COMMON_PATHS]
    for cand, how in candidates:
        if cand in found or cand in tried or len(tried) >= limit + len(COMMON_PATHS):
            continue
        tried.append(cand)
        try:
            r = net.fetch(cand, accept="application/rss+xml, application/atom+xml, application/feed+json, text/calendar, */*;q=0.5")
            if r.status != 200:
                continue
            f = parse(r.body)
        except (net.Blocked, net.FetchError, NotAFeed):
            continue
        if r.url not in found:
            found[r.url] = {"url": r.url, "kind": f["kind"], "title": f["title"], "items": len(f["items"]),
                            "newest": newest(f["items"]), "how": how}
    return {"url": page.url, "title": clean(p.title, 200), "feeds": list(found.values())}
