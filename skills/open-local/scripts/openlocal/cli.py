"""Command line for Open Local. Every command prints JSON unless it says otherwise.

  where      resolve a place from a name, postal code, id or coordinates
  sources    the known sources for a place, most local first
  recent     what those sources published lately, plus upcoming calendar events
  discover   find the feeds and calendars a website offers
  dates      the dates a web page declares, labelled by meaning
  changed    has this page changed since the last look
  cache      the local copies of feeds already read (--clear to delete them)
  propose    draft a registry entry for a person to review
  frontier   unmapped places next to mapped ones: where to expand next
  gaps       what kinds of source a place has, and what its neighbours have that it lacks
  validate   check the registry (needs PyYAML and jsonschema)
  check      load every endpoint of the sources for a place (network)
  stale      entries nobody has verified lately
  dupes      sources that share a URL
  export     json | opml | csv | geojson
  build      rewrite dist/ from registry/
  record     store results of `check` in dist/checks/ (the scheduled check does this)
  seed       draft place files from a national gazetteer (US Census), for a person to review
  version    the skill version and the version of the data it reads (also --version)
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, cache, check, export, feeds, net, pages, propose, recent
from .registry import IncompatibleData, Registry


def out(obj) -> None:
    print(json.dumps(obj, indent=1, ensure_ascii=False))


def one_place(reg: Registry, args) -> str:
    """Resolve the place arguments to exactly one place, or exit explaining the choice."""
    found = reg.resolve(args.place, postal=getattr(args, "postal", None), lat=getattr(args, "lat", None), lon=getattr(args, "lon", None))
    if not found:
        out({"error": "place not in the registry", "asked": args.place or getattr(args, "postal", None),
             "next": "Tell the user this place has no entry yet, answer from a web search with that caveat, and offer to help add it (references/build.md in this skill)."})
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
    ap.add_argument("--version", action="store_true", help="print the skill and data versions")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("where"); add_place(p, required=False)
    p = sub.add_parser("sources"); add_place(p, required=False); add_scope(p)
    p.add_argument("--brief", action="store_true", help="one line per source")
    p = sub.add_parser("recent"); add_place(p, required=False); add_scope(p)
    p.add_argument("--days", type=int, default=7, help="published in the last N days (default 7)")
    p.add_argument("--ahead", type=int, default=14, help="calendar events in the next N days (default 14)")
    p.add_argument("--brief", action="store_true", help="leave out summaries and per-feed detail (much smaller)")
    p.add_argument("--all-area", action="store_true", help="also list items from area-wide sources that do not name the place")
    p.add_argument("--per-source", type=int, default=15, help="at most this many items from each feed (default 15)")
    p.add_argument("--fresh", action="store_true", help="read every source again, ignoring local copies")
    p.add_argument("--max-age", type=cache.parse_age, default=None, metavar="AGE",
                   help="use a local copy of a feed read within this long: 90m, 6h, 2d (default 24h; "
                        "see `cache --max-age` to change it for good)")
    p = sub.add_parser("cache"); p.add_argument("--clear", action="store_true", help="delete the local copies of feeds")
    p.add_argument("--max-age", metavar="AGE", help="how long to trust copies from now on (90m, 6h, 2d; 0 = always re-read); "
                                                    "'default' goes back to 24h. Saved in the settings file.")
    p = sub.add_parser("discover"); p.add_argument("url"); p.add_argument("--no-probe", action="store_true")
    p = sub.add_parser("dates"); p.add_argument("url")
    p = sub.add_parser("changed"); p.add_argument("url"); p.add_argument("--no-remember", action="store_true")
    p = sub.add_parser("propose"); p.add_argument("url"); p.add_argument("--place", required=True); p.add_argument("--name")
    p.add_argument("--type", default="other", dest="source_type"); p.add_argument("--classification", default="primary")
    p.add_argument("--added-by", default="")
    p = sub.add_parser("validate"); p.add_argument("--files", nargs="*", help="only report on these registry files (references are still checked against everything)")
    p = sub.add_parser("check"); add_place(p, required=False); p.add_argument("--all", action="store_true"); p.add_argument("--id", action="append")
    p.add_argument("--part", help="rotation: check group w of R (w/R), so R runs cover everything")
    p.add_argument("--shard", help="parallel jobs: take shard i of K (i/K); one site never spans two shards")
    p.add_argument("--home", help="only sources whose home place id starts with this, e.g. US/RI")
    p.add_argument("--record", action="store_true", help="also store the results in dist/checks/")
    p = sub.add_parser("record"); p.add_argument("reports", nargs="+", help="JSON written by `check`")
    p = sub.add_parser("seed"); p.add_argument("dataset", choices=["us-census"])
    p.add_argument("--places", required=True, help="Census Gazetteer file of county subdivisions or places (.txt, tab-separated)")
    p.add_argument("--counties", required=True, help="Census Gazetteer counties file")
    p.add_argument("--state", required=True, help="two-letter state code, e.g. RI")
    p.add_argument("--write", action="store_true", help="write new place files into registry/ (default: print what would be written)")
    sub.add_parser("version")
    p = sub.add_parser("stale"); p.add_argument("--max-age-days", type=int, default=180)
    sub.add_parser("dupes")
    p = sub.add_parser("export"); p.add_argument("format", choices=["json", "opml", "csv", "geojson"]); p.add_argument("--place")
    p = sub.add_parser("build"); p.add_argument("--check", action="store_true", help="fail if dist/ is out of date")
    p = sub.add_parser("search"); p.add_argument("text")
    p = sub.add_parser("frontier"); add_place(p, required=False)
    p = sub.add_parser("gaps"); add_place(p, required=False)
    args = ap.parse_args(argv)
    try:
        return run(ap, args)
    except IncompatibleData as e:
        out({"error": str(e), "next": "Tell the user the open-local skill needs updating, and how."})
        return 5


def run(ap, args) -> int:
    if args.version or args.cmd == "version":
        try:
            out(Registry.load_index().versions())
        except RuntimeError as e:
            out({"skill": __version__, "data": None, "error": str(e)})
        return 0
    if not args.cmd:
        ap.print_help()
        return 2
    if args.cmd == "validate":
        from . import validate
        errors, warnings = validate.validate(only=args.files)
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

    if args.cmd == "seed":
        from . import seed
        return seed.main(args)
    if args.cmd == "cache":
        if args.max_age is not None:
            try:
                cache.save_setting(None if args.max_age == "default" else args.max_age)
            except ValueError as err:
                print(err)
                return 2
        removed = cache.clear() if args.clear else None
        minutes, where = cache.setting()
        out({**cache.status(), **({"removed": removed} if removed is not None else {}),
             "trusted_for_minutes": minutes, "trusted_for_set_by": where})
        return 0
    if args.cmd == "record":
        from . import registry
        if registry.ROOT is None:
            print("record needs a checkout of the repository")
            return 2
        reports = [r for f in args.reports for r in json.load(open(f, encoding="utf-8"))["reports"]]
        written = check.record(reports, Registry.load().sources, registry.ROOT / "dist")
        print(f"recorded {len(reports)} source checks in {len(written)} files under dist/checks/")
        return 0

    if args.cmd in ("where", "sources", "recent", "gaps"):
        index = Registry.load_index()
        if args.cmd == "where":
            if not (args.place or args.postal or args.lat is not None):
                out({"places": sorted(index.places), "registry": index.versions()})
            else:
                found = index.resolve(args.place, postal=args.postal, lat=args.lat, lon=args.lon)
                out({"matches": found, "registry": index.versions()} if found else
                    {"matches": [], "note": "not in the registry yet", "registry": index.versions()})
            return 0
        pid = one_place(index, args)
        reg = Registry.load_place(pid, radius_km=getattr(args, "radius_km", None))
        if args.cmd == "gaps":
            out(reg.gaps(pid))
        elif args.cmd == "sources":
            srcs = reg.sources_for(pid, radius_km=args.radius_km, neighbors=args.neighbors, types=args.types, topics=args.topics)
            if args.brief:
                if reg.notice:
                    print("notice:", reg.notice)
                if not reg.describe(pid)["sources_of_its_own"]:
                    print("note:", reg.describe(pid)["note"])
                for s in srcs:
                    kinds = ",".join(sorted({e["kind"] for e in s.get("endpoints") or []})) or "-"
                    print(f"{s['relation']:7} {s['type']:22} {s['classification']:9} {kinds:18} {s['name']}  <{s['url']}>")
            else:
                out({"place": reg.describe(pid), "sources": srcs, "registry": reg.versions()})
        else:
            got = recent.recent(reg, pid, days=args.days, ahead=args.ahead, radius_km=args.radius_km, neighbors=args.neighbors,
                                types=args.types, topics=args.topics, per_source=args.per_source, all_area=args.all_area,
                                fetch=cache.Cache(max_age_minutes=0 if args.fresh else args.max_age))
            out(recent.brief(got) if args.brief else got)
        return 0

    reg = Registry.load()
    if args.cmd == "propose":
        try:
            print(propose.propose(reg, args.url, args.place, name=args.name, source_type=args.source_type,
                                  classification=args.classification, added_by=args.added_by), end="")
        except (net.Blocked, net.FetchError, KeyError) as e:
            out({"error": str(e)})
            return 2
    elif args.cmd == "check":
        if args.id:
            srcs = [s for s in reg.sources if s["id"] in args.id]
        elif args.all or args.part or args.shard or args.home:
            srcs = reg.sources
        else:
            srcs = reg.sources_for(one_place(reg, args))
        srcs = check.select(srcs, part=args.part, shard=args.shard, home_prefix=args.home)
        reports = [check.check_source(s) for s in srcs]
        bad = [r for r in reports if r["problems"]]
        if args.record:
            from . import registry
            check.record(reports, reg.sources, registry.ROOT / "dist")
        out({"checked": len(reports), "with_problems": len(bad), "selection": {"part": args.part, "shard": args.shard, "home": args.home},
             "reports": reports})
        return 1 if bad else 0
    elif args.cmd == "frontier":
        pid = one_place(reg, args) if (args.place or args.postal or args.lat is not None) else None
        rows = reg.frontier(pid)
        out({"frontier": rows, "note": "Places listed by mapped neighbours as adjacent and not yet in the registry. "
                                        "An empty list means nobody has recorded the next places out, not that there are none."})
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
        files = export.published_files(reg)
        dist = registry.ROOT / "dist"
        stale = [n for n, t in files.items() if not (dist / n).exists() or (dist / n).read_text(encoding="utf-8") != t]
        leftover = sorted(f.relative_to(dist).as_posix() for f in (dist / "places").rglob("*.json")
                          if f.relative_to(dist).as_posix() not in files) if (dist / "places").exists() else []
        if args.check:
            if stale or leftover:
                shown = (stale + leftover)[:8]
                print(f"dist/ is out of date ({len(stale)} changed, {len(leftover)} to remove):", ", ".join(shown),
                      "- run: python3 skills/open-local/scripts/run.py build")
                return 1
            print("dist/ is up to date")
            return 0
        for n in stale:
            (dist / n).parent.mkdir(parents=True, exist_ok=True)
            (dist / n).write_text(files[n], encoding="utf-8")
        for n in leftover:
            (dist / n).unlink()
        print(f"wrote {len(stale)} of {len(files)} files to dist/, removed {len(leftover)} "
              f"({len(reg.places)} places, {len(reg.sources)} sources, data {reg.data.get('data_version')})")
    return 0
