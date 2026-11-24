"""Draft a registry entry for a source, for a person to review.

This never edits the registry. It prints YAML to paste into a pull request or an issue.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse

from . import feeds, net
from .registry import Registry, norm


def yaml_scalar(v) -> str:
    return json.dumps(v, ensure_ascii=False)  # a JSON string is a valid YAML scalar


def propose(reg: Registry, url: str, place: str, *, name: str | None = None, source_type: str = "other",
            classification: str = "primary", added_by: str = "", today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    if place not in reg.places:
        raise KeyError(f"unknown place {place}; add the place first (see CONTRIBUTING.md)")
    found = feeds.discover(url)
    home = found["url"]
    title = name or re.split(r"\s+[|\-–—:]\s+", found.get("title") or "")[0].strip() or urllib.parse.urlsplit(home).hostname
    sid = place.lower().replace("/", "-") + "-" + "-".join(norm(title).split()[:6])
    existing = {s["id"] for s in reg.sources}
    n, base = 2, sid
    while sid in existing:
        sid, n = f"{base}-{n}", n + 1
    lines = [f"# Proposed by an agent on {today}. A person must check every line before this is merged.",
             f"# Paste under `sources:` in registry/{place}.yaml",
             f"- id: {sid}", f"  name: {yaml_scalar(title)}", f"  url: {yaml_scalar(home)}", f"  type: {source_type}",
             f"  classification: {classification}", "  coverage:", f"    - place: {place}", "      level: dedicated"]
    if found["feeds"]:
        lines.append("  endpoints:")
        for f in found["feeds"]:
            lines += [f"    - kind: {f['kind']}", f"      url: {yaml_scalar(f['url'])}"]
            if f.get("title"):
                lines.append(f"      title: {yaml_scalar(f['title'])}")
            note = "{} items, newest {} ({})".format(f["items"], f["newest"] or "undated", f["how"])
            lines.append(f"      note: {yaml_scalar(note)}")
    else:
        lines += ["  endpoints:", "    - kind: html", f"      url: {yaml_scalar(home)}", '      note: "No feed found; list the page that carries the updates."']
    lines += ["  access:", "    paywall: unknown", f"  discovered: \"{today}\"", "  status: unverified", "  provenance:",
              "    method: agent-proposed", f"    added_by: {yaml_scalar(added_by)}",
              "    evidence: " + yaml_scalar("Home page loaded {}; {} feed(s) found by discovery.".format(today, len(found["feeds"])))]
    return "\n".join(lines) + "\n"
