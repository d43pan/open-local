"""Load and query the registry.

A registry file describes one place and the sources whose home is that place:

    registry/US/RI/little-compton.yaml   ->  place id "US/RI/little-compton"

Sources say what they cover with `coverage` (a list of place ids), so a newspaper filed
under one town can cover three towns, and a state agency filed under the state covers
every place inside it. Hierarchy comes from `parents` and `covers`, never from the path,
so places that do not nest the way US places do can still be described.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import re
import time
import unicodedata

REGISTRY_URL = "https://raw.githubusercontent.com/d43pan/open-local/main/dist/registry.json"
CACHE_HOURS = 24


def repo_root() -> pathlib.Path | None:
    """The checkout this code runs from, if it is one (it has registry/ and schemas/)."""
    env = os.environ.get("OPEN_LOCAL_REPO")
    if env:
        return pathlib.Path(env)
    for p in pathlib.Path(__file__).resolve().parents:
        if (p / "registry").is_dir() and (p / "schemas").is_dir():
            return p
    return None


ROOT = repo_root()
REGISTRY_DIR = (ROOT / "registry") if ROOT else None
BUILT = (ROOT / "dist" / "registry.json") if ROOT else None


def cache_file() -> pathlib.Path:
    base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return pathlib.Path(base) / "open-local" / "registry.json"


def download() -> dict:
    """Fetch the published registry (for a skill installed without the repository)."""
    from . import net
    cache = cache_file()
    fresh = cache.exists() and (time.time() - cache.stat().st_mtime) < CACHE_HOURS * 3600
    if not fresh:
        try:
            r = net.fetch(REGISTRY_URL, respect_robots=False, max_bytes=50_000_000)
            if r.status == 200:
                json.loads(r.body)
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(r.body)
        except (net.Blocked, net.FetchError, ValueError):
            pass  # fall back to an older copy below
    if not cache.exists():
        raise RuntimeError("No registry available: could not download " + REGISTRY_URL +
                           ". Clone https://github.com/d43pan/open-local and run from there, or set OPEN_LOCAL_REGISTRY to a registry.json.")
    return json.loads(cache.read_text(encoding="utf-8"))


FEED_KINDS = ("rss", "atom", "jsonfeed", "ical")
LEVELS = ("dedicated", "regular", "occasional")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_yaml_files(directory: pathlib.Path | None = None) -> list[tuple[pathlib.Path, dict]]:
    import yaml  # only needed when reading the YAML source of the registry
    directory = directory or REGISTRY_DIR
    out = []
    for f in sorted(directory.rglob("*.yaml")):
        out.append((f, yaml.safe_load(f.read_text(encoding="utf-8")) or {}))
    return out


def build(directory: pathlib.Path | None = None) -> dict:
    """Combine every registry file into one document (what dist/registry.json holds)."""
    places, sources = {}, []
    for path, doc in load_yaml_files(directory):
        place = dict(doc.get("place") or {})
        if place.get("id"):
            places[place["id"]] = place
        for s in doc.get("sources") or []:
            s = dict(s)
            s["home"] = place.get("id")
            if not s.get("coverage"):
                s["coverage"] = [{"place": place.get("id"), "level": "dedicated"}]
            sources.append(s)
    return {"schema": "open-local/registry/1", "license": "CC0-1.0",
            "places": dict(sorted(places.items())), "sources": sorted(sources, key=lambda s: s.get("id", ""))}


class Registry:
    def __init__(self, data: dict):
        self.data = data
        self.places: dict[str, dict] = data.get("places", {})
        self.sources: list[dict] = data.get("sources", [])
        self._up: dict[str, set[str]] = {pid: set(p.get("parents") or []) for pid, p in self.places.items()}
        for pid, p in self.places.items():  # an area that "covers" a place acts as one more parent of it
            for member in p.get("covers") or []:
                self._up.setdefault(member, set()).add(pid)

    @classmethod
    def load(cls, prefer_yaml: bool = True) -> "Registry":
        """From OPEN_LOCAL_REGISTRY, else this checkout, else the published copy (cached a day)."""
        env = os.environ.get("OPEN_LOCAL_REGISTRY")
        if env:
            return cls(json.loads(pathlib.Path(env).read_text(encoding="utf-8")))
        if ROOT:
            if prefer_yaml:
                try:
                    return cls(build())
                except ImportError:
                    pass
            return cls(json.loads(BUILT.read_text(encoding="utf-8")))
        return cls(download())

    # ---- geography -------------------------------------------------------------------
    def ancestors(self, pid: str) -> list[str]:
        """Every area that contains this place, nearest first (parents, then theirs)."""
        seen, order, frontier = {pid}, [], [pid]
        while frontier:
            nxt = []
            for cur in frontier:
                for up in sorted(self._up.get(cur, ())):
                    if up not in seen:
                        seen.add(up)
                        order.append(up)
                        nxt.append(up)
            frontier = nxt
        return order

    def descendants(self, pid: str) -> list[str]:
        return sorted(p for p in self.places if pid in self.ancestors(p))

    @staticmethod
    def distance_km(a: dict, b: dict) -> float:
        la1, lo1, la2, lo2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 2 * 6371.0088 * math.asin(math.sqrt(h))

    def near(self, lat: float, lon: float, radius_km: float) -> list[tuple[float, str]]:
        """Places whose centre is within radius_km of a point, nearest first."""
        out = []
        for pid, p in self.places.items():
            c = p.get("centroid")
            if c:
                d = self.distance_km({"lat": lat, "lon": lon}, c)
                if d <= radius_km:
                    out.append((round(d, 1), pid))
        return sorted(out)

    def resolve(self, query: str | None = None, *, postal: str | None = None, lat: float | None = None,
                lon: float | None = None) -> list[dict]:
        """Find places for a name ("Little Compton, RI"), an id, a postal code or a point.

        Returns candidates, best first. More than one candidate means the request is
        ambiguous and the caller should ask which was meant.
        """
        hits: list[tuple[float, str, str]] = []
        if postal:
            want = norm(postal).replace(" ", "")
            for pid, p in self.places.items():
                if any(norm(z).replace(" ", "") == want for z in p.get("postal_codes") or []):
                    hits.append((0, pid, "postal code"))
        if lat is not None and lon is not None:
            local = [(d, pid) for d, pid in self.near(lat, lon, 25) if self.places[pid].get("kind") in ("municipality", "neighbourhood")]
            hits += [(1 + d, pid, f"{d} km from the point") for d, pid in local[:5]]
        if query:
            if query in self.places:
                return [self.describe(query, "exact id")]
            parts = [norm(x) for x in re.split(r"[,/]", query) if norm(x)]
            head, quals = (parts[0], parts[1:]) if parts else ("", [])
            for pid, p in self.places.items():
                names = [norm(p.get("name", ""))] + [norm(a) for a in p.get("aliases") or []]
                if head not in names:
                    continue
                context = self._context_words(pid)
                if all(q in context for q in quals):
                    hits.append((0 if names[0] == head else 0.5, pid, "name" if names[0] == head else "alias"))
        best: dict[str, tuple[float, str]] = {}
        for score, pid, why in hits:
            if pid not in best or score < best[pid][0]:
                best[pid] = (score, why)
        return [self.describe(pid, why) for pid, (score, why) in sorted(best.items(), key=lambda kv: (kv[1][0], kv[0]))]

    def _context_words(self, pid: str) -> set[str]:
        words = set()
        for a in [pid] + self.ancestors(pid):
            p = self.places.get(a, {})
            for v in [p.get("name"), p.get("country"), p.get("subdivision"), (p.get("subdivision") or "").split("-")[-1],
                      p.get("abbreviation"), *(p.get("aliases") or [])]:
                if v:
                    words.add(norm(v))
        return words

    def describe(self, pid: str, matched_by: str = "") -> dict:
        p = self.places[pid]
        return {"id": pid, "name": p.get("name"), "kind": p.get("kind"), "local_kind": p.get("local_kind"),
                "matched_by": matched_by, "contained_in": self.ancestors(pid),
                "neighbors": list(p.get("neighbors") or []), "centroid": p.get("centroid"),
                "postal_codes": list(p.get("postal_codes") or [])}

    # ---- sources ---------------------------------------------------------------------
    def sources_for(self, pid: str, *, radius_km: float | None = None, neighbors: bool = False,
                    types: list[str] | None = None, topics: list[str] | None = None,
                    include_retired: bool = False) -> list[dict]:
        """Sources relevant to a place, most local first.

        relation is how the source relates to the place asked about:
          direct  the source says it covers this place
          area    the source covers an area that contains this place (county, state, region)
          nearby  the source covers a neighbouring place, or one within the radius
        Relevance comes from declared coverage, never from where the publisher sits.
        """
        if pid not in self.places:
            raise KeyError(pid)
        up = self.ancestors(pid)
        nearby: dict[str, float | None] = {}
        if neighbors:
            nearby.update({n: None for n in self.places[pid].get("neighbors") or []})
        centre = self.places[pid].get("centroid")
        if radius_km and centre:
            nearby.update({p: d for d, p in self.near(centre["lat"], centre["lon"], radius_km) if p != pid})
        out = []
        for s in self.sources:
            if s.get("status") == "retired" and not include_retired:
                continue
            if types and s.get("type") not in types:
                continue
            if topics and not set(topics) & set(s.get("topics") or []):
                continue
            best = None
            for c in s.get("coverage") or []:
                cp, level = c.get("place"), c.get("level", "regular")
                if cp == pid:
                    rel, depth = "direct", 0
                elif cp in up:
                    rel, depth = "area", 1 + up.index(cp)
                elif cp in nearby:
                    rel, depth = "nearby", 50
                else:
                    continue
                rank = (("direct", "area", "nearby").index(rel), depth, LEVELS.index(level) if level in LEVELS else 1)
                if best is None or rank < best[0]:
                    best = (rank, rel, cp, level)
            if best:
                out.append({**s, "relation": best[1], "via_place": best[2], "level": best[3], "_rank": best[0]})
        out.sort(key=lambda s: (s["_rank"], s.get("classification") != "primary", s.get("name", "")))
        for s in out:
            del s["_rank"]
        return out

    # ---- growing coverage --------------------------------------------------------------
    CORE_TYPES = ("government", "meetings", "newspaper", "news-site", "library", "schools", "events",
                  "planning-zoning", "public-safety", "community-organization", "food-drink", "farm-market", "arts-culture")
    SHARED_TYPES = ("newspaper", "news-site", "tourism", "television", "radio", "chamber-of-commerce",
                    "transportation", "public-notices", "meetings", "planning-zoning", "schools")

    def direct_sources(self, pid: str) -> list[dict]:
        return [s for s in self.sources if s.get("status") != "retired" and any(c.get("place") == pid for c in s.get("coverage") or [])]

    def frontier(self, pid: str | None = None) -> list[dict]:
        """Unmapped places next to mapped ones: where coverage can grow next.

        Ranked by how many mapped places border each one, since more shared borders means
        more shared sources to reuse. With pid, only that place's unmapped neighbours.
        """
        found: dict[str, dict] = {}
        known_q = {(p.get("identifiers") or {}).get("wikidata") for p in self.places.values()}
        for place_id, p in self.places.items():
            for adj in p.get("adjacent_unmapped") or []:
                if adj.get("wikidata") and adj["wikidata"] in known_q:
                    continue  # already mapped under its own file
                key = adj.get("wikidata") or norm(adj["name"])
                row = found.setdefault(key, {"name": adj["name"], "wikidata": adj.get("wikidata"), "borders": [], "notes": []})
                row["borders"].append(place_id)
                if adj.get("note"):
                    row["notes"].append(adj["note"])
        rows = [r for r in found.values() if pid is None or pid in r["borders"]]
        for r in rows:
            areas: dict[str, int] = {}
            reuse: dict[str, dict] = {}
            for b in r["borders"]:
                for a in self.ancestors(b):
                    areas[a] = areas.get(a, 0) + 1
                for s in self.direct_sources(b):
                    if len(s.get("coverage") or []) > 1 or s.get("type") in self.SHARED_TYPES:
                        reuse[s["id"]] = {"id": s["id"], "name": s["name"], "type": s["type"], "url": s["url"],
                                          "platform": s.get("platform"), "seen_in": b}
            r["likely_shared_areas"] = [{"place": a, "name": self.places[a]["name"], "area_sources": len(self.direct_sources(a))}
                                        for a, n in sorted(areas.items(), key=lambda kv: (-kv[1], -len(self.ancestors(kv[0])), kv[0]))]
            r["neighbour_sources_to_check"] = sorted(reuse.values(), key=lambda s: (s["type"], s["name"]))
        rows.sort(key=lambda r: (-len(r["borders"]), r["name"]))
        return rows

    def gaps(self, pid: str) -> dict:
        """What kinds of source a place has, and what its neighbours have that it lacks."""
        if pid not in self.places:
            raise KeyError(pid)
        mine: dict[str, list[str]] = {}
        for s in self.direct_sources(pid):
            mine.setdefault(s["type"], []).append(s["name"])
        theirs: dict[str, list[dict]] = {}
        for n in self.places[pid].get("neighbors") or []:
            for s in self.direct_sources(n):
                if s["type"] not in mine:
                    theirs.setdefault(s["type"], []).append({"place": n, "name": s["name"], "url": s["url"], "platform": s.get("platform")})
        statuses: dict[str, int] = {}
        for s in self.direct_sources(pid):
            statuses[s.get("status", "?")] = statuses.get(s.get("status", "?"), 0) + 1
        with_feed = sum(1 for s in self.direct_sources(pid) if any(e["kind"] in FEED_KINDS for e in s.get("endpoints") or []))
        return {"place": pid, "sources": sum(len(v) for v in mine.values()), "with_feed_or_calendar": with_feed, "by_status": statuses,
                "has": {k: len(v) for k, v in sorted(mine.items())},
                "missing_core_types": [t for t in self.CORE_TYPES if t not in mine],
                "neighbours_have": {k: v for k, v in sorted(theirs.items())},
                "area_sources_reaching_it": len([s for s in self.sources_for(pid) if s["relation"] == "area"]),
                "note": "A missing type is a place to look, not proof of a gap: some towns have no paper, no chamber, no farm stand."}

    def search(self, text: str) -> list[dict]:
        want = norm(text)
        return [s for s in self.sources if want in norm(" ".join(str(s.get(k, "")) for k in ("id", "name", "description", "publisher", "type"))
                                                         + " " + " ".join(s.get("topics") or []))]
