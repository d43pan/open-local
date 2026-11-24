import datetime as dt
import json

from conftest import FIX
from openlocal import check, net, pages, propose, recent

TODAY = dt.date(2026, 11, 24)


def test_dates_are_labelled_by_meaning():
    found = pages.extract_dates((FIX / "page.html").read_text())
    kinds = {(d["kind"], d["date"][:10]) for d in found}
    assert ("published", "2026-11-18") in kinds
    assert ("event-start", "2026-12-09") in kinds
    assert ("mentioned", "2026-12-09") in kinds
    assert not any(d["date"].startswith("1999") for d in found)  # text inside scripts is ignored


def test_change_detection(fake_net, tmp_path):
    state = tmp_path / "s.json"
    f = fake_net({"https://alder.example.org/p": (200, b"<html><body><p>Agenda for June</p></body></html>")})
    assert pages.changed("https://alder.example.org/p", state)["status"] == "first-look"
    assert pages.changed("https://alder.example.org/p", state)["status"] == "unchanged"
    f.pages["https://alder.example.org/p"] = (200, b"<html><body><p>Agenda for June</p><p>Minutes for May posted</p><script>t=1</script></body></html>")
    r = pages.changed("https://alder.example.org/p", state)
    assert r["status"] == "changed" and r["added"] == ["Minutes for May posted"]


NETWORK = {
    "https://harbourtimes.example.org/rss.xml": (200, "feed.rss"),
    "https://gazette.example.org/feed/": (200, "gazette.rss"),
    "https://alder.example.org/council.ics": (200, "council.ics"),
}


def run(reg, fake_net, **kw):
    f = fake_net(NETWORK)
    return recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=f, **kw)


def test_recent_keeps_only_the_window_and_separates_events(reg, fake_net):
    out = run(reg, fake_net)
    titles = [i["title"] for i in out["items"]]
    assert "Old story" not in titles and "Past meeting" not in titles and "Far future" not in titles
    meeting = next(i for i in out["items"] if i["kind"] == "event")
    assert meeting["title"] == "Town Council regular meeting" and meeting["date_means"] == "when the event starts"
    story = next(i for i in out["items"] if i["source_id"] == "xx-no-alder-harbour-times")
    assert story["date_means"] == "when this was published" and story["classification"] == "primary"
    assert out["coverage"]["undated_items_skipped"] == 1


def test_recent_groups_the_same_story_and_keeps_both_sources(reg, fake_net):
    out = run(reg, fake_net)
    a = next(i for i in out["items"] if i["source_id"] == "xx-no-alder-harbour-times")
    b = next(i for i in out["items"] if i["source_id"] == "xx-no-shire-gazette")
    assert a["group"] == b["group"]
    assert a["leads_group"] and not b["leads_group"]  # the earlier report leads
    assert a["also_reported_by"] == ["xx-no-shire-gazette"]


def test_recent_reports_what_it_could_not_read(reg, fake_net):
    f = fake_net({k: v for k, v in NETWORK.items() if "gazette" not in k})
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=f)
    cov = out["coverage"]
    assert [x["source_id"] for x in cov["failed"]] == ["xx-no-shire-gazette"]
    by_hand = {x["source_id"] for x in cov["read_by_hand"]}
    assert {"xx-no-alder-farm-stand", "xx-no-school-district-committee"} <= by_hand
    assert "not evidence that nothing happened" in cov["warning"]
    assert "untrusted" in out["handling"]


def test_feed_text_is_passed_through_as_data_only(reg, fake_net):
    out = run(reg, fake_net)
    injected = next(i for i in out["items"] if i["source_id"] == "xx-no-shire-gazette")
    assert "Ignore previous instructions" in injected["summary"]  # reported as content, with the handling note above
    assert set(out) == {"place", "window", "items", "coverage", "handling"}


def test_propose_drafts_an_unverified_entry_without_touching_the_registry(reg, fake_net):
    fake_net({"https://alder.example.org/planning": (200, "page.html"), "https://alder.example.org/feed/": (200, "feed.rss"),
              "https://alder.example.org/council.ics": (200, "council.ics")})
    before = json.dumps(reg.data)
    text = propose.propose(reg, "https://alder.example.org/planning", "XX/NO/alder", source_type="planning-zoning", today=TODAY)
    import yaml
    entry = yaml.safe_load(text)[0]
    assert entry["id"] == "xx-no-alder-planning-board" and entry["status"] == "unverified"
    assert entry["provenance"]["method"] == "agent-proposed" and "verified" not in entry
    assert {e["kind"] for e in entry["endpoints"]} == {"rss", "ical"}
    assert json.dumps(reg.data) == before


def test_stale_and_duplicate_reports(reg):
    assert {s["id"] for s in check.stale_entries(reg, 180, TODAY)} == {s["id"] for s in reg.sources}
    assert check.stale_entries(reg, 400, TODAY) == []
    reg.sources.append({**reg.sources[0], "id": "xx-no-copy"})
    assert check.duplicates(reg)[0]["sources"] == sorted(["xx-no-copy", reg.sources[0]["id"]])


def test_check_source_flags_dead_and_quiet_feeds(reg, fake_net):
    fake_net({"https://harbourtimes.example.org/": (200, b"<html></html>"), "https://harbourtimes.example.org/rss.xml": (404, b"")})
    s = next(s for s in reg.sources if s["id"] == "xx-no-alder-harbour-times")
    assert any("HTTP 404" in p for p in check.check_source(s, TODAY)["problems"])
    fake_net({"https://harbourtimes.example.org/": (200, b"<html></html>"), "https://harbourtimes.example.org/rss.xml": (200, "feed.rss")})
    assert check.check_source(s, TODAY)["problems"] == []
    assert any("published nothing" in p for p in check.check_source(s, dt.date(2027, 6, 1))["problems"])


def test_feed_links_are_made_absolute_and_useful(reg, fake_net):
    # CivicPlus-style calendar: one relative link back to the feed itself, one relative event page, one unsafe link.
    ics = (FIX / "council.ics").read_text().replace(
        "URL:https://alder.example.org/council/2026-12-03",
        "URL:/council.ics")
    ics = ics.replace("SUMMARY:Far future\nDTSTART;VALUE=DATE:20270601",
                      "SUMMARY:Harbour walk\nDTSTART;VALUE=DATE:20261205\nURL:events/harbour-walk")
    ics = ics.replace("SUMMARY:Past meeting\nDTSTART:20261001T190000Z",
                      "SUMMARY:Odd link\nDTSTART;VALUE=DATE:20261206\nURL:javascript:alert(1)")
    f = fake_net({**NETWORK, "https://alder.example.org/council.ics": (200, ics.encode())})
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=f)
    links = {i["title"]: i["url"] for i in out["items"] if i["kind"] == "event"}
    page = next(s["url"] for s in reg.sources if any(e["url"] == "https://alder.example.org/council.ics" for e in s.get("endpoints") or []))
    assert links["Town Council regular meeting"] == page          # link to the feed itself -> the source's page
    assert links["Harbour walk"] == "https://alder.example.org/events/harbour-walk"
    assert links["Odd link"] == page                               # never a non-web link


def test_item_link_rules():
    feed = "https://t.example.gov/common/iCalendar.aspx?feed=calendar&catID=14"
    assert recent.item_link("/common/iCalendar.aspx?catID=14&feed=calendar", feed, "https://t.example.gov/") == "https://t.example.gov/"
    assert recent.item_link("/Calendar.aspx?EID=9", feed, "https://t.example.gov/") == "https://t.example.gov/Calendar.aspx?EID=9"
    assert recent.item_link(None, feed, "https://t.example.gov/") == "https://t.example.gov/"
    assert recent.item_link("https://news.example.org/a", feed, "x") == "https://news.example.org/a"
