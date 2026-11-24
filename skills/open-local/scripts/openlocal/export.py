"""Write the registry in formats other tools read: JSON, OPML, CSV, GeoJSON."""
from __future__ import annotations

import csv
import io
import json
from xml.sax.saxutils import quoteattr

from .registry import FEED_KINDS, Registry


def to_json(reg: Registry) -> str:
    return json.dumps(reg.data, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def to_opml(reg: Registry, place: str | None = None, **query) -> str:
    """OPML 2.0 of every RSS, Atom and JSON Feed endpoint, grouped by home place.

    With a place, only sources relevant to that place (same rules as `sources`).
    Calendars are left out: feed readers do not subscribe to iCalendar through OPML.
    """
    sources = reg.sources_for(place, **query) if place else reg.sources
    groups: dict[str, list[str]] = {}
    for s in sources:
        for e in s.get("endpoints") or []:
            if e.get("kind") in ("rss", "atom", "jsonfeed"):
                title = s["name"] + (f" – {e['title']}" if e.get("title") else "")
                line = (f'      <outline type="rss" text={quoteattr(title)} title={quoteattr(title)} '
                        f'xmlUrl={quoteattr(e["url"])} htmlUrl={quoteattr(s["url"])} category={quoteattr(s.get("type", ""))}/>')
                groups.setdefault(s.get("home") or "", []).append(line)
    name = reg.places[place]["name"] if place else "all places"
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<opml version="2.0">', "  <head>",
           f"    <title>Open Local: {name}</title>",
           "    <docs>https://opml.org/spec2.opml</docs>", "  </head>", "  <body>"]
    for home in sorted(groups):
        label = reg.places.get(home, {}).get("name", home)
        out.append(f"    <outline text={quoteattr(label)} title={quoteattr(label)}>")
        out += sorted(groups[home])
        out.append("    </outline>")
    out += ["  </body>", "</opml>", ""]
    return "\n".join(out)


def to_csv(reg: Registry) -> str:
    """One row per source, for spreadsheets."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["id", "name", "type", "classification", "publisher", "url", "home", "covers", "feeds", "calendars",
                "other_endpoints", "paywall", "languages", "topics", "status", "discovered", "verified"])
    for s in reg.sources:
        eps = s.get("endpoints") or []
        w.writerow([s["id"], s["name"], s.get("type"), s.get("classification"), s.get("publisher", ""), s["url"], s.get("home"),
                    " ".join(c["place"] for c in s.get("coverage") or []),
                    " ".join(e["url"] for e in eps if e["kind"] in ("rss", "atom", "jsonfeed")),
                    " ".join(e["url"] for e in eps if e["kind"] == "ical"),
                    " ".join(e["url"] for e in eps if e["kind"] not in FEED_KINDS),
                    (s.get("access") or {}).get("paywall", ""), " ".join(s.get("languages") or []),
                    " ".join(s.get("topics") or []), s.get("status"), s.get("discovered"), s.get("verified", "")])
    return buf.getvalue()


def to_geojson(reg: Registry) -> str:
    """Places as points with the number of sources that cover each directly."""
    feats = []
    for pid, p in reg.places.items():
        c = p.get("centroid")
        if not c:
            continue
        direct = sum(1 for s in reg.sources if any(cv.get("place") == pid for cv in s.get("coverage") or []))
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
                      "properties": {"id": pid, "name": p["name"], "kind": p["kind"], "sources": direct,
                                     **{k: v for k, v in (p.get("identifiers") or {}).items()}}})
    return json.dumps({"type": "FeatureCollection", "features": feats}, indent=1, ensure_ascii=False) + "\n"
