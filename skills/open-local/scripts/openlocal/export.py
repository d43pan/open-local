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


FEED_KINDS = {"rss", "atom", "jsonfeed", "ical", "podcast"}
REPO_URL = "https://github.com/d43pan/open-local"
# simplestyle-spec markers, which GitHub and geojson.io draw: green for a place with
# sources of its own, grey for one that is only an outline so far.
MAPPED, UNMAPPED = "#2e7d32", "#9e9e9e"


def _names(reg: Registry, ids) -> str:
    return ", ".join(reg.places[i]["name"] for i in ids or [] if i in reg.places)


def to_geojson(reg: Registry) -> str:
    """Places as points, each described well enough to read the map without the registry.

    `title` and `description` are what a map shows first; the rest of the properties say
    how well the place is mapped, what kinds of source it has, what it sits inside,
    what is next to it, and where its file is.
    """
    feats = []
    for pid, p in reg.places.items():
        c = p.get("centroid")
        if not c:
            continue
        own = [s for s in reg.sources if any(cv.get("place") == pid for cv in s.get("coverage") or [])]
        n = len(own)
        feeds = sum(1 for s in own if any(e.get("kind") in FEED_KINDS for e in s.get("endpoints") or []))
        types: dict[str, int] = {}
        status: dict[str, int] = {}
        for s in own:
            types[s["type"]] = types.get(s["type"], 0) + 1
            status[s.get("status", "unverified")] = status.get(s.get("status", "unverified"), 0) + 1
        type_text = ", ".join("{} {}".format(k, v) for k, v in sorted(types.items(), key=lambda kv: (-kv[1], kv[0])))
        inside = _names(reg, p.get("parents"))
        near = _names(reg, p.get("neighbors"))
        todo = ", ".join(a["name"] for a in p.get("adjacent_unmapped") or [])
        if n:
            desc = "{} source{} ({} with a feed or calendar): {}.".format(n, "" if n == 1 else "s", feeds, type_text)
        else:
            desc = "Not mapped yet: the place is known but no sources are listed. Help add them."
        if near:
            desc += " Next to: {}.".format(near)
        if todo:
            desc += " Not in the registry yet: {}.".format(todo)
        props = {
            "title": "{}: {}".format(p["name"], "{} source{}".format(n, "" if n == 1 else "s") if n else "not mapped yet"),
            "description": desc,
            "id": pid, "name": p["name"], "kind": p["kind"],
            "mapped": bool(n), "sources": n, "with_feed_or_calendar": feeds,
        }
        if p.get("local_kind"):
            props["local_kind"] = p["local_kind"]
        if type_text:
            props["source_types"] = type_text
        for k in ("verified", "checked", "unverified", "broken", "stale"):
            if status.get(k):
                props["sources_" + k] = status[k]
        if inside:
            props["inside"] = inside
        if near:
            props["neighbors"] = near
        if todo:
            props["neighbors_not_in_registry"] = todo
        if p.get("postal_codes"):
            props["postal_codes"] = ", ".join(p["postal_codes"])
        props["registry_file"] = "{}/blob/main/registry/{}.yaml".format(REPO_URL, pid)
        props.update(p.get("identifiers") or {})
        props["marker-color"] = MAPPED if n else UNMAPPED
        props["marker-size"] = "large" if n >= 20 else "medium" if n else "small"
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [c["lon"], c["lat"]]},
                      "properties": props})
    return json.dumps({"type": "FeatureCollection", "features": feats}, indent=1, ensure_ascii=False) + "\n"


def compact(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n"


def published_files(reg: Registry) -> dict[str, str]:
    """Everything `build` writes under dist/, by path.

    registry.json and the exports hold the whole registry (for bulk users and other
    tools). index.json and places/<id>.json are what an installed skill fetches: a small
    index to find a place, then one file per place, so nobody downloads every town.
    dist/checks/ is not here: the scheduled availability check writes it.
    """
    files = {"registry.json": to_json(reg), "feeds.opml": to_opml(reg), "sources.csv": to_csv(reg),
             "places.geojson": to_geojson(reg), "index.json": compact(reg.index())}
    for pid in reg.places:
        files[f"places/{pid}.json"] = compact(reg.place_slice(pid))
    return files
