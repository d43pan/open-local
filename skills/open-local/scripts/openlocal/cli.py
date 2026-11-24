"""Command line for Open Local. Every command prints JSON unless it says otherwise.

  where      resolve a place from a name, postal code, id or coordinates
  sources    the known sources for a place, most local first
  recent     what those sources published lately, plus upcoming calendar events
  discover   find the feeds and calendars a website offers
  dates      the dates a web page declares, labelled by meaning
  changed    has this page changed since the last look
  propose    draft a registry entry for a person to review
  frontier   unmapped places next to mapped ones: where to expand next
  gaps       what kinds of source a place has, and what its neighbours have that it lacks
  validate   check the registry (needs PyYAML and jsonschema)
  check      load every endpoint of the sources for a place (network)
  stale      entries nobody has verified lately
  dupes      sources that share a URL
  export     json | opml | csv | geojson
  build      rewrite dist/ from registry/
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, check, export, feeds, net, pages, propose, recent
from .registry import Registry


def out(obj) -> None:
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def one_place(reg: Registry, args) -> str:
    """Resolve the place arguments to exactly one place, or exit explaining the choice."""
    found = reg.resolve(args.place, postal=getattr(args, "postal", None), lat=getattr(args, "lat", None), lon=getattr(args, "lon", None))
    if not found:
        out({"error": "place not in the registry", "asked": args.place or getattr(args, "postal", None),
             "next": "Tell the user this place has no entry yet, answer from a web search with that caveat, and offer to help add it (open-local-build skill)."})
        sys.exit(3)
    if len(found) > 1 and found[0]["matched_by"] not in ("exact id", "postal code") and not str(found[0]["matched_by"]).endswith("point"):
        out({"error": "more than one place matches; ask which", "candidates": found})
        sys.exit(4)
    return found[0]["id"]


def add_place(p, required=True):
    p.add_argument("place", nargs="?" if not required else None, help='a name ("Little Compton, RI"), or a place id (US/RI/little-compton)')
    p.add_argument("--postal", help="postal code")
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)


def add_scope(p):
    p.add_argument("--radius-km", type=float, help="also include sources for places within this distance")
    p.add_argument("--neighbors", action="store_true", help="also include sources for neighbouring places")
    p.add_argument("--type", action="append", dest="types", help="only this source type (repeatable)")
    p.add_argument("--topic", action="append", dest="topics", help="only sources with this topic (repeatable)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="open-local", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("where"); add_place(p, required=False)
    p = sub.add_parser("sources"); add_place(p, required=False); add_scope(p)
    p.add_argument("--brief", action="store_true", help="one line per source")
    p = sub.add_parser("recent"); add_place(p, required=False); add_scope(p)
    p.add_argument("--days", type=int, default=7, help="published in the last N days (default 7)")
    p.add_argument("--ahead", type=int, default=14, help="calendar events in the next N days (default 14)")
    p = sub.add_parser("discover"); p.add_argument("url"); p.add_argument("--no-probe", action="store_true")
    p = sub.add_parser("dates"); p.add_argument("url")
    p = sub.add_parser("changed"); p.add_argument("url"); p.add_argument("--no-remember", action="store_true")
    p = sub.add_parser("propose"); p.add_argument("url"); p.add_argument("--place", required=True); p.add_argument("--name")
    p.add_argument("--type", default="other", dest="source_type"); p.add_argument("--classification", default="primary")
    p.add_argument("--added-by", default="")
    sub.add_parser("validate")
    p = sub.add_parser("check"); add_place(p, required=False); p.add_argument("--all", action="store_true"); p.add_argument("--id", action="append")
    p = sub.add_parser("stale"); p.add_argument("--max-age-days", type=int, default=180)
    sub.add_parser("dupes")
    p = sub.add_parser("export"); p.add_argument("format", choices=["json", "opml", "csv", "geojson"]); p.add_argument("--place")
    p = sub.add_parser("build"); p.add_argument("--check", action="store_true", help="fail if dist/ is out of date")
    p = sub.add_parser("search"); p.add_argument("text")
    p = sub.add_parser("frontier"); add_place(p, required=False)
    p = sub.add_parser("gaps"); add_place(p, required=False)
    args = ap.parse_args(argv)

    if args.cmd == "validate":
        from . import validate
        errors, warnings = validate.validate()
        for w in warnings:
            print("warning:", w)
        for e in errors:
            print("ERROR:", e)
        print(f"{len(errors)} error(s), {len(warnings)} warning(s)")
        return 1 if errors else 0
    if args.cmd in ("discover", "dates", "changed"):
        try:
            if args.cmd == "discover":
                out(feeds.discover(args.url, probe=not args.no_probe))
            elif args.cmd == "dates":
                r = net.fetch(args.url, accept="text/html,*/*")
                out({"url": r.url, "http": r.status, "dates": pages.extract_dates(r.text()),
                     "note": "published and event dates are different things; 'mentioned' dates are only text that looks like a date"})
            else:
                out(pages.changed(args.url, remember=not args.no_remember))
        except (net.Blocked, net.FetchError) as e:
            out({"error": str(e), "url": args.url})
            return 2
        return 0

    reg = Registry.load()
    if args.cmd == "where":
        if not (args.place or args.postal or args.lat is not None):
            out({"places": sorted(reg.places)})
        else:
            found = reg.resolve(args.place, postal=args.postal, lat=args.lat, lon=args.lon)
            out({"matches": found} if found else {"matches": [], "note": "not in the registry yet"})
    elif args.cmd == "sources":
        pid = one_place(reg, args)
        srcs = reg.sources_for(pid, radius_km=args.radius_km, neighbors=args.neighbors, types=args.types, topics=args.topics)
        if args.brief:
            for s in srcs:
                kinds = ",".join(sorted({e["kind"] for e in s.get("endpoints") or []})) or "-"
                print(f"{s['relation']:7} {s['type']:22} {s['classification']:9} {kinds:18} {s['name']}  <{s['url']}>")
        else:
            out({"place": reg.describe(pid), "sources": srcs})
    elif args.cmd == "recent":
        pid = one_place(reg, args)
        out(recent.recent(reg, pid, days=args.days, ahead=args.ahead, radius_km=args.radius_km, neighbors=args.neighbors,
                          types=args.types, topics=args.topics))
    elif args.cmd == "propose":
        try:
            print(propose.propose(reg, args.url, args.place, name=args.name, source_type=args.source_type,
                                  classification=args.classification, added_by=args.added_by), end="")
        except (net.Blocked, net.FetchError, KeyError) as e:
            out({"error": str(e)})
            return 2
    elif args.cmd == "check":
        if args.id:
            srcs = [s for s in reg.sources if s["id"] in args.id]
        elif args.all:
            srcs = reg.sources
        else:
            srcs = reg.sources_for(one_place(reg, args))
        reports = [check.check_source(s) for s in srcs if s.get("status") != "retired"]
        bad = [r for r in reports if r["problems"]]
        out({"checked": len(reports), "with_problems": len(bad), "reports": reports})
        return 1 if bad else 0
    elif args.cmd == "frontier":
        pid = one_place(reg, args) if (args.place or args.postal or args.lat is not None) else None
        rows = reg.frontier(pid)
        out({"frontier": rows, "note": "Places listed by mapped neighbours as adjacent and not yet in the registry. "
                                        "An empty list means nobody has recorded the next places out, not that there are none."})
    elif args.cmd == "gaps":
        out(reg.gaps(one_place(reg, args)))
    elif args.cmd == "stale":
        out(check.stale_entries(reg, args.max_age_days))
    elif args.cmd == "dupes":
        out(check.duplicates(reg))
    elif args.cmd == "search":
        out([{k: s.get(k) for k in ("id", "name", "type", "url", "home")} for s in reg.search(args.text)])
    elif args.cmd == "export":
        text = {"json": export.to_json, "csv": export.to_csv, "geojson": export.to_geojson}.get(args.format, lambda r: export.to_opml(r, args.place))(reg)
        sys.stdout.write(text)
    elif args.cmd == "build":
        from . import registry
        if registry.ROOT is None:
            print("build needs a checkout of the repository")
            return 2
        files = {"registry.json": export.to_json(reg), "feeds.opml": export.to_opml(reg), "sources.csv": export.to_csv(reg),
                 "places.geojson": export.to_geojson(reg)}
        dist = registry.ROOT / "dist"
        stale = [n for n, t in files.items() if not (dist / n).exists() or (dist / n).read_text(encoding="utf-8") != t]
        if args.check:
            if stale:
                print("dist/ is out of date:", ", ".join(stale), "- run: python3 skills/open-local/scripts/run.py build")
                return 1
            print("dist/ is up to date")
            return 0
        dist.mkdir(exist_ok=True)
        for n, t in files.items():
            (dist / n).write_text(t, encoding="utf-8")
        print(f"wrote {len(files)} files to dist/ ({len(reg.places)} places, {len(reg.sources)} sources)")
    return 0
