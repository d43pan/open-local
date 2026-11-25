"""Network checks on registry entries: does it load, is the feed alive, is the entry old.

These run on a schedule, not on pull requests, because the network is not deterministic.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import urllib.parse

from . import feeds, net
from .registry import FEED_KINDS, Registry
from .validate import normalize_url


def check_source(s: dict, today: dt.date | None = None, quiet_days: int = 120) -> dict:
    today = today or dt.date.today()
    report = {"id": s["id"], "name": s["name"], "problems": [], "endpoints": []}
    targets = [("home", s["url"])] + [(e["kind"], e["url"]) for e in s.get("endpoints") or []]
    flagged = {e["url"] for e in s.get("endpoints") or [] if e.get("agent_readable") is False}
    whole = (s.get("access") or {}).get("agent_readable") is False
    for kind, url in targets:
        row = {"kind": kind, "url": url}
        if whole or url in flagged:
            row["skipped"] = "marked not readable by agents"
            report["endpoints"].append(row)
            continue
        try:
            r = net.fetch(url)
            row["http"] = r.status
            if r.redirects and normalize_url(r.url) != normalize_url(url):
                row["moved_to"] = r.url
            if r.status >= 400:
                report["problems"].append(f"{kind} returns HTTP {r.status}: {url}")
            elif kind in FEED_KINDS:
                try:
                    f = feeds.read(kind, r.body, r.url)
                    row["items"], row["newest"] = len(f["items"]), feeds.newest(f["items"])
                    if kind not in ("ical", "events") and row["newest"]:
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


def _bucket(text: str, n: int) -> int:
    """A stable bucket for text (not Python's hash(), which changes between runs)."""
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % n


def host(s: dict) -> str:
    return (urllib.parse.urlsplit(s.get("url", "")).hostname or "").lower().removeprefix("www.")


def select(sources: list[dict], part: str | None = None, shard: str | None = None, home_prefix: str | None = None) -> list[dict]:
    """Choose which sources one run checks.

    part  "w/R": rotation. Source ids are split into R stable groups; this run takes group w,
          so R weekly runs check every source once.
    shard "i/K": parallel jobs. Sources are split by host, so every request to one site
          stays in one job and the per-host delay still holds.
    home_prefix: only sources whose home place id starts with this (e.g. "US/RI").
    """
    def parse(spec):
        i, n = (int(x) for x in spec.split("/"))
        if not (n >= 1 and 0 <= i < n):
            raise ValueError(f"bad slice {spec!r}: want i/n with 0 <= i < n")
        return i, n
    out = [s for s in sources if s.get("status") != "retired"]
    if home_prefix:
        out = [s for s in out if (s.get("home") or "") == home_prefix or (s.get("home") or "").startswith(home_prefix.rstrip("/") + "/")]
    if part:
        w, r = parse(part)
        out = [s for s in out if _bucket(s["id"], r) == w]
    if shard:
        i, k = parse(shard)
        out = [s for s in out if _bucket(host(s), k) == i]
    return out


def record(reports: list[dict], sources: list[dict], dist: pathlib.Path, today: dt.date | None = None) -> list[pathlib.Path]:
    """Store each source's latest check in dist/checks/<home>.json, keeping earlier results for the rest.

    These files are written by the scheduled check, never by hand or by `build`, so
    pull requests do not touch them.
    """
    today = today or dt.date.today()
    home_of = {s["id"]: s.get("home") for s in sources}
    by_home: dict[str, dict] = {}
    for r in reports:
        home = home_of.get(r["id"])
        if not home:
            continue
        eps = []
        for e in r["endpoints"]:
            row = {"url": e["url"], "kind": e["kind"]}
            if "skipped" in e:
                row["skipped"] = e["skipped"]
            elif "blocked" in e:
                row["blocked"] = e["blocked"]
            else:
                row["http"] = e.get("http")
                row["ok"] = not e.get("error") and (e.get("http") or 999) < 400
            eps.append(row)
        by_home.setdefault(home, {})[r["id"]] = {"checked": today.isoformat(), "ok": not r["problems"],
                                                 "problems": r["problems"], "endpoints": eps}
    written = []
    for home, results in sorted(by_home.items()):
        f = dist / "checks" / f"{home}.json"
        old = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        merged = {**(old.get("sources") or {}), **results}
        merged = {k: merged[k] for k in sorted(merged) if k in home_of}  # forget sources that no longer exist
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"schema": "open-local/checks/1", "home": home, "sources": merged}, indent=1,
                                ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(f)
    return written


def area_of(home: str | None) -> str:
    """The reporting area for a source's home: the country and first subdivision (US/RI), or the country."""
    parts = (home or "??").split("/")
    return "/".join(parts[:2])


def owners_for(path: str, codeowners: str) -> list[str]:
    """Owners of a repository path under a CODEOWNERS file (last matching rule wins, as on GitHub).

    Supports the patterns this project uses: directory prefixes (registry/US/RI/) and exact
    files, with an optional leading slash and trailing *.
    """
    found: list[str] = []
    for line in codeowners.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pattern, *owners = line.split()
        pat = pattern.lstrip("/").rstrip("*")
        if pat and (path == pat or (pat.endswith("/") and path.startswith(pat))):
            found = owners
    return found


def report_by_area(reports: list[dict], sources: list[dict], codeowners: str = "", stale: list[dict] | None = None) -> dict[str, str]:
    """One Markdown report per area (e.g. US/RI) for the sources with problems, naming each place's maintainers."""
    home_of = {s["id"]: s.get("home") for s in sources}
    bad: dict[str, list[dict]] = {}
    for r in reports:
        if r["problems"]:
            bad.setdefault(area_of(home_of.get(r["id"])), []).append(r)
    stale_by: dict[str, list[dict]] = {}
    for s in stale or []:
        stale_by.setdefault(area_of(home_of.get(s["id"])), []).append(s)
    out = {}
    for area in sorted(set(bad) | set(stale_by)):
        rows = bad.get(area, [])
        owners = sorted({o for r in rows for o in owners_for(f"registry/{home_of.get(r['id'])}.yaml", codeowners)})
        lines = [f"{len(rows)} source(s) in {area} had a problem in this check."]
        if owners:
            lines.append(f"Maintainers for these places: {' '.join(owners)}")
        lines.append("")
        for r in sorted(rows, key=lambda r: r["id"]):
            lines.append(f"### {r['name']} (`{r['id']}`, {home_of.get(r['id'])})")
            lines += [f"- {p}" for p in r["problems"]]
        if stale_by.get(area):
            lines += ["", "### Not verified recently"] + [f"- `{s['id']}` (last verified: {s['verified'] or 'never'})"
                                                         for s in sorted(stale_by[area], key=lambda s: s["id"])]
        lines += ["", "A failure here can be a site having a bad day. Confirm by hand before changing an entry's status."]
        out[area] = "\n".join(lines) + "\n"
    return out
