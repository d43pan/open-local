"""Network checks on registry entries: does it load, is the feed alive, is the entry old.

These run on a schedule, not on pull requests, because the network is not deterministic.
"""
from __future__ import annotations

import datetime as dt

from . import feeds, net
from .registry import FEED_KINDS, Registry
from .validate import normalize_url


def check_source(s: dict, today: dt.date | None = None, quiet_days: int = 120) -> dict:
    today = today or dt.date.today()
    report = {"id": s["id"], "name": s["name"], "problems": [], "endpoints": []}
    targets = [("home", s["url"])] + [(e["kind"], e["url"]) for e in s.get("endpoints") or []]
    for kind, url in targets:
        row = {"kind": kind, "url": url}
        try:
            r = net.fetch(url)
            row["http"] = r.status
            if r.redirects and normalize_url(r.url) != normalize_url(url):
                row["moved_to"] = r.url
            if r.status >= 400:
                report["problems"].append(f"{kind} returns HTTP {r.status}: {url}")
            elif kind in FEED_KINDS:
                try:
                    f = feeds.parse(r.body)
                    row["items"], row["newest"] = len(f["items"]), feeds.newest(f["items"])
                    if kind != "ical" and row["newest"]:
                        age = (today - dt.date.fromisoformat(row["newest"][:10])).days
                        if age > quiet_days:
                            report["problems"].append(f"{kind} feed has published nothing for {age} days: {url}")
                    if not f["items"]:
                        report["problems"].append(f"{kind} feed is empty: {url}")
                except feeds.NotAFeed as e:
                    report["problems"].append(f"{kind} endpoint is not a feed ({e}): {url}")
        except net.Blocked as e:
            row["blocked"] = str(e)
            if "robots" not in str(e):
                report["problems"].append(f"{kind} refused ({e}): {url}")
        except net.FetchError as e:
            row["error"] = str(e)[:200]
            report["problems"].append(f"{kind} failed ({str(e)[:120]}): {url}")
        report["endpoints"].append(row)
    return report


def stale_entries(reg: Registry, max_age_days: int = 180, today: dt.date | None = None) -> list[dict]:
    """Entries nobody has verified recently (or ever)."""
    today = today or dt.date.today()
    out = []
    for s in reg.sources:
        if s.get("status") == "retired":
            continue
        last = s.get("verified")
        age = (today - dt.date.fromisoformat(last)).days if last else None
        if age is None or age > max_age_days:
            out.append({"id": s["id"], "verified": last, "age_days": age, "status": s.get("status")})
    return out


def duplicates(reg: Registry) -> list[dict]:
    """Sources that share a home page or an endpoint: probably the same source twice."""
    seen: dict[str, set[str]] = {}
    for s in reg.sources:
        for url in [s["url"]] + [e["url"] for e in s.get("endpoints") or [] if e["kind"] in FEED_KINDS]:
            seen.setdefault(normalize_url(url), set()).add(s["id"])
    return [{"url": u, "sources": sorted(ids)} for u, ids in sorted(seen.items()) if len(ids) > 1]
