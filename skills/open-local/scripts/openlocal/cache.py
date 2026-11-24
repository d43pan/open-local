"""Remember what was read, so asking twice does not load every site twice.

A local folder of feed and calendar responses, one per address. Nothing is sent
anywhere and nothing is shared between users: it is this machine's own memory.

A copy younger than `max_age_minutes` is used without touching the network. An older
copy is revalidated with the ETag or Last-Modified the site gave, so an unchanged feed
costs one small request and no download. If a site is down, the last good copy is used
and reported as out of date, with its age.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import pathlib
import time

from . import net

DEFAULT_MINUTES = 60
KEEP_DAYS = 30


def directory() -> pathlib.Path:
    base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return pathlib.Path(base) / "open-local" / "fetch"


def default_minutes() -> int:
    try:
        return max(0, int(os.environ.get("OPEN_LOCAL_CACHE_MINUTES", DEFAULT_MINUTES)))
    except ValueError:
        return DEFAULT_MINUTES


class Cache:
    """Call it like net.fetch. `how` says, per address, where the answer came from."""

    def __init__(self, fetch=None, max_age_minutes: int | None = None, root: pathlib.Path | None = None, clock=time.time):
        self.fetch = fetch or net.fetch
        self.max_age = (default_minutes() if max_age_minutes is None else max(0, max_age_minutes)) * 60
        self.root = root or directory()
        self.clock = clock
        self.how: dict[str, dict] = {}

    def _file(self, url: str) -> pathlib.Path:
        return self.root / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")

    def _load(self, url: str) -> dict | None:
        try:
            rec = json.loads(self._file(url).read_text(encoding="utf-8"))
            return rec if rec.get("url") == url else None
        except (OSError, ValueError):
            return None

    def _save(self, url: str, r: net.Response, now: float) -> None:
        rec = {"url": url, "final_url": r.url, "read": now, "confirmed": now, "headers": r.headers,
               "body": base64.b64encode(r.body).decode("ascii")}
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = self._file(url).with_suffix(".tmp")
            tmp.write_text(json.dumps(rec), encoding="utf-8")
            tmp.replace(self._file(url))
        except OSError:
            pass  # a cache that cannot be written is only slower

    def _response(self, rec: dict) -> net.Response:
        return net.Response(rec.get("final_url") or rec["url"], 200, rec["headers"], base64.b64decode(rec["body"]))

    def _note(self, url: str, state: str, rec: dict | None, now: float) -> None:
        self.how[url] = {"from": state, **({"copy_minutes_old": int((now - rec["confirmed"]) // 60)} if rec and state != "network" else {})}

    def __call__(self, url: str, **kw) -> net.Response:
        now = self.clock()
        rec = self._load(url)
        if rec and now - rec["confirmed"] < self.max_age:
            self._note(url, "copy", rec, now)
            return self._response(rec)
        cond = {}
        if rec:
            if rec["headers"].get("etag"):
                cond["if_none_match"] = rec["headers"]["etag"]
            if rec["headers"].get("last-modified"):
                cond["if_modified_since"] = rec["headers"]["last-modified"]
        try:
            r = self.fetch(url, **kw, **cond)
        except net.Blocked:
            raise  # a site that now refuses is not read from an old copy
        except net.FetchError:
            if rec and now - rec["read"] < KEEP_DAYS * 86400:
                self._note(url, "old copy, site did not answer", rec, now)
                return self._response(rec)
            raise
        if r.status == 304 and rec:
            rec["confirmed"] = now
            try:
                self._file(url).write_text(json.dumps(rec), encoding="utf-8")
            except OSError:
                pass
            self._note(url, "copy, site says unchanged", rec, now)
            return self._response(rec)
        if r.status == 200 and not r.truncated:
            self._save(url, r, now)
        self._note(url, "network", None, now)
        return r

    def summary(self) -> dict:
        states = [h["from"] for h in self.how.values()]
        ages = [h["copy_minutes_old"] for h in self.how.values() if "copy_minutes_old" in h]
        out = {"read_from_network": states.count("network"),
               "used_local_copy": states.count("copy"),
               "unchanged_since_last_read": states.count("copy, site says unchanged"),
               "old_copy_site_down": states.count("old copy, site did not answer"),
               "copies_trusted_for_minutes": self.max_age // 60}
        if ages:
            out["oldest_copy_minutes"] = max(ages)
        out["note"] = "Copies are this machine's own, kept in {}. Pass --fresh to read every source again.".format(self.root)
        return out


def status(root: pathlib.Path | None = None) -> dict:
    root = root or directory()
    files = list(root.glob("*.json")) if root.exists() else []
    return {"folder": str(root), "copies": len(files), "bytes": sum(f.stat().st_size for f in files)}


def clear(root: pathlib.Path | None = None, older_than_days: float = 0) -> int:
    root = root or directory()
    cutoff, n = time.time() - older_than_days * 86400, 0
    for f in (root.glob("*.json") if root.exists() else []):
        if f.stat().st_mtime <= cutoff:
            f.unlink(missing_ok=True)
            n += 1
    return n
