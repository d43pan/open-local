"""Web pages without feeds: pull out dates, and notice when a page changes."""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import os
import pathlib
import re
from html.parser import HTMLParser

from . import net
from .feeds import iso

MONTHS = "january february march april may june july august september october november december".split()
TEXT_DATE = re.compile(r"\b(" + "|".join(m[:3] for m in MONTHS) + r")[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.I)
NUM_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b|\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
SKIP = {"script", "style", "noscript", "template", "svg"}


class _Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.times, self.ld, self.text = [], [], [], []
        self._skip, self._ld = 0, False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._ld = True
            self.ld.append("")
        if tag in SKIP:
            self._skip += 1
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content"):
                self.meta.append((key, a["content"]))
        if tag == "time" and a.get("datetime"):
            self.times.append(a["datetime"])

    def handle_endtag(self, tag):
        if tag in SKIP and self._skip:
            self._skip -= 1
        if tag == "script":
            self._ld = False

    def handle_data(self, data):
        if self._ld:
            self.ld[-1] += data
        elif not self._skip and data.strip():
            self.text.append(re.sub(r"\s+", " ", data).strip())


def _walk(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("datePublished", "dateModified", "startDate", "endDate", "dateCreated") and isinstance(v, str):
                out.append((k, v))
            else:
                _walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out)


def parse_html(html_text: str) -> _Page:
    p = _Page()
    try:
        p.feed(html_text)
    except Exception:
        pass
    return p


def extract_dates(html_text: str) -> list[dict]:
    """Dates a page declares, labelled by what they mean.

    kind is one of: published, modified, event-start, event-end, mentioned.
    A "mentioned" date is only text that looks like a date; do not treat it as
    the publication date or as proof that something happened then.
    """
    p = parse_html(html_text)
    out: list[dict] = []
    kinds = {"article:published_time": "published", "datepublished": "published", "pubdate": "published", "date": "published",
             "dc.date": "published", "dc.date.issued": "published", "article:modified_time": "modified",
             "datemodified": "modified", "og:updated_time": "modified", "startdate": "event-start", "enddate": "event-end"}
    for key, value in p.meta:
        if key in kinds and iso(value):
            out.append({"kind": kinds[key], "date": iso(value), "from": f"meta {key}"})
    for blob in p.ld:
        try:
            found: list[tuple[str, str]] = []
            _walk(json.loads(blob), found)
        except ValueError:
            continue
        for k, v in found:
            if iso(v):
                out.append({"kind": kinds.get(k.lower(), "published" if k == "dateCreated" else "mentioned"), "date": iso(v), "from": f"JSON-LD {k}"})
    for t in p.times:
        if iso(t):
            out.append({"kind": "mentioned", "date": iso(t), "from": "time element"})
    text = " ".join(p.text)
    for m in TEXT_DATE.finditer(text):
        month = [x[:3] for x in MONTHS].index(m.group(1)[:3].lower()) + 1
        try:
            out.append({"kind": "mentioned", "date": dt.date(int(m.group(3)), month, int(m.group(2))).isoformat(), "from": f"text: {m.group(0)}"})
        except ValueError:
            pass
    seen, uniq = set(), []
    for d in out:
        key = (d["kind"], d["date"][:10])
        if key not in seen:
            seen.add(key)
            uniq.append(d)
    return uniq


def visible_lines(html_text: str) -> list[str]:
    return [t for t in parse_html(html_text).text if len(t) > 2]


def state_path() -> pathlib.Path:
    base = os.environ.get("OPEN_LOCAL_STATE_DIR") or os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "open-local")
    return pathlib.Path(base) / "pages.json"


def changed(url: str, state_file: pathlib.Path | None = None, remember: bool = True) -> dict:
    """Compare a page with the last time it was looked at.

    The first look only records the page. State is a local file; nothing is sent anywhere.
    """
    state_file = state_file or state_path()
    try:
        state = json.loads(state_file.read_text())
    except (OSError, ValueError):
        state = {}
    r = net.fetch(url, accept="text/html,*/*")
    if r.status != 200:
        return {"url": url, "status": "error", "http": r.status}
    lines = visible_lines(r.text())
    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    old = state.get(url)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    result = {"url": url, "checked": now}
    if not old:
        result["status"] = "first-look"
    elif old["sha256"] == digest:
        result.update(status="unchanged", last_changed=old.get("changed"))
    else:
        added = [l[2:] for l in difflib.ndiff(old.get("lines", []), lines) if l.startswith("+ ")]
        result.update(status="changed", previous_look=old.get("checked"), added=[a[:300] for a in added[:40]], added_total=len(added))
    if remember:
        state[url] = {"sha256": digest, "checked": now, "changed": now if (not old or old["sha256"] != digest) else old.get("changed"),
                      "lines": lines[:2000]}
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state))
    return result
