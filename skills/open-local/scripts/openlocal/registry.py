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

DATA_URL = os.environ.get("OPEN_LOCAL_DATA_URL", "https://raw.githubusercontent.com/d43pan/open-local/main/dist/")
REGISTRY_URL = DATA_URL + "registry.json"
CACHE_HOURS = 24
SCHEMA = "open-local/registry/1"
SCHEMA_MAJOR = 1  # the newest major version of the published data this code can read
PLACE_RADIUS_KM = 50  # a per-place file carries every place within this distance, so --radius-km up to it works


class IncompatibleData(RuntimeError):
    """The published data uses a newer schema than this copy of the skill understands."""


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


def cache_dir() -> pathlib.Path:
    base = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
    return pathlib.Path(base) / "open-local"


def cache_file() -> pathlib.Path:
    return cache_dir() / "registry.json"


def cached_get(path: str) -> bytes | None:
    """A published file (e.g. "index.json", "places/US/RI/little-compton.json"), cached a day.

    After a day the copy is revalidated with its ETag, so an unchanged file costs one
    small request. Returns None when the file does not exist (HTTP 404), or when it cannot
    be fetched and no older copy is cached.
    """
    from . import net
    if ".." in path.split("/") or path.startswith("/"):
        raise ValueError(f"bad data path: {path}")
    target = cache_dir() / path
    tag_file = target.with_name(target.name + ".etag")
    if target.exists() and (time.time() - target.stat().st_mtime) < CACHE_HOURS * 3600:
        return target.read_bytes()
    etag = tag_file.read_text(encoding="utf-8").strip() if (target.exists() and tag_file.exists()) else None
    try:
        r = net.fetch(DATA_URL + path, respect_robots=False, max_bytes=50_000_000, if_none_match=etag)
        if r.status == 304 and target.exists():
            target.touch()
        elif r.status == 200:
            if path.endswith(".json"):
                json.loads(r.body)  # never cache something that is not JSON
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(r.body)
            if r.headers.get("etag"):
                tag_file.write_text(r.headers["etag"], encoding="utf-8")
        elif r.status == 404:
            return None
    except (net.Blocked, net.FetchError, ValueError):
        pass  # fall back to an older copy below
    return target.read_bytes() if target.exists() else None


def download() -> dict:
    """Fetch the whole published registry (for a skill installed without the repository)."""
    body = cached_get("registry.json")
    if body is None:
        raise RuntimeError("No registry available: could not download " + REGISTRY_URL +
                           ". Clone https://github.com/d43pan/open-local and run from there, or set OPEN_LOCAL_REGISTRY to a registry.json.")
    return json.loads(body)


def version_key(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.+-]", str(v))[:3])


def compatibility(data: dict) -> str | None:
    """Raise IncompatibleData if the data is too new to read; return a notice if the skill is out of date."""
    from . import __version__
    schema = str(data.get("schema") or SCHEMA)
    try:
        major = int(schema.rsplit("/", 1)[-1])
    except ValueError:
        major = SCHEMA_MAJOR
    if major > SCHEMA_MAJOR:
        raise IncompatibleData(f"The published registry uses {schema}, newer than this copy of the open-local skill "
                               f"(version {__version__}) can read. Update the skill: https://github.com/d43pan/open-local#install")
    latest = data.get("skill_version")
    if latest and version_key(latest) > version_key(__version__):
        return (f"A newer open-local skill ({latest}) is available; this copy is {__version__}. "
                "It still works; update it when convenient: https://github.com/d43pan/open-local#install")
    return None


def data_version(places: dict, sources: list) -> str:
    """A short fingerprint of the registry content, so an answer can say which data it used."""
    import hashlib
    blob = json.dumps({"places": places, "sources": sources}, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


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
    from . import __version__
    places, sources = dict(sorted(places.items())), sorted(sources, key=lambda s: s.get("id", ""))
    return {"schema": SCHEMA, "license": "CC0-1.0", "skill_version": __version__,
            "data_version": data_version(places, sources), "places": places, "sources": sources}


def read_checks(homes: set[str]) -> dict[str, dict]:
    """The latest network-check result for each source whose home is one of these places.

    Written by the scheduled availability check to dist/checks/<home>.json. Missing files
    simply mean nothing has been recorded yet.
    """
    out: dict[str, dict] = {}
    for home in sorted(h for h in homes if h):
        path = f"checks/{home}.json"
        if os.environ.get("OPEN_LOCAL_REGISTRY"):
            body = None  # an explicit registry file comes without check results
        elif ROOT:
            f = ROOT / "dist" / path
            body = f.read_bytes() if f.exists() else None
        else:
            body = cached_get(path)
        if body:
            try:
                out.update(json.loads(body).get("sources") or {})
            except ValueError:
                pass
    return out


class Registry:
    def __init__(self, data: dict):
        self.data = data
        self.places: dict[str, dict] = data.get("places", {})
        self.sources: list[dict] = data.get("sources", [])
        self.notice: str | None = compatibility(data)
        self.partial = bool(data.get("partial"))  # True for an index or a per-place file, not the whole registry
        self._up: dict[str, set[str]] = {pid: set(p.get("parents") or []) for pid, p in self.places.items()}
        for pid, p in self.places.items():  # an area that "covers" a place acts as one more parent of it
            for member in p.get("covers") or []:
                self._up.setdefault(member, set()).add(pid)

    def versions(self) -> dict:
        from . import __version__
        return {"skill": __version__, "data": self.data.get("data_version"), "schema": self.data.get("schema"),
                **({"notice": self.notice} if self.notice else {})}

    _local_cache: dict = {}

    @classmethod
    def _local(cls) -> dict | None:
        """The whole registry when it is on this machine (a file or a checkout), parsed once per run."""
        env = os.environ.get("OPEN_LOCAL_REGISTRY")
        key = env or (str(ROOT) if ROOT else None)
        if key is None:
            return None
        if key not in cls._local_cache:
            if env:
                data = json.loads(pathlib.Path(env).read_text(encoding="utf-8"))
            else:
                try:
                    data = build()
                except ImportError:
                    data = json.loads(BUILT.read_text(encoding="utf-8"))
            cls._local_cache[key] = data
        return json.loads(json.dumps(cls._local_cache[key]))  # a copy, so one caller's changes never leak to another

    @classmethod
    def load(cls, prefer_yaml: bool = True) -> "Registry":
        """The whole registry: from OPEN_LOCAL_REGISTRY, else this checkout, else the published copy (cached a day)."""
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

    @classmethod
    def load_index(cls) -> "Registry":
        """Enough to resolve any place by name, postal code or point, without any sources.

        Installed skills fetch the small dist/index.json; a checkout uses the whole registry.
        """
        local = cls._local()
        if local is not None:
            return cls(local)
        body = cached_get("index.json")
        return cls(json.loads(body)) if body else cls(download())  # older published data has no index

    @classmethod
    def load_place(cls, pid: str, radius_km: float | None = None) -> "Registry":
        """What is needed to answer about one place: it, the areas above it, its neighbours,
        everything within PLACE_RADIUS_KM, and the sources covering any of them.

        Installed skills fetch dist/places/<id>.json; a checkout uses the whole registry.
        Falls back to the whole registry for a wider radius or older published data.
        """
        local = cls._local()
        if local is None:
            body = None if (radius_km or 0) > PLACE_RADIUS_KM else cached_get(f"places/{pid}.json")
            local = json.loads(body) if body else download()
        reg = cls(local)
        if pid not in reg.places:
            raise KeyError(pid)
        relevant = reg.sources_for(pid, neighbors=True, radius_km=max(radius_km or 0, PLACE_RADIUS_KM))
        checks = read_checks({s.get("home") for s in relevant})  # one small file per home, never one per place in the country
        for s in reg.sources:
            if s["id"] in checks:
                s["last_checked"] = checks[s["id"]]
        return reg

    # ---- slicing for publication ----------------------------------------------------
    def place_slice(self, pid: str) -> dict:
        """The per-place file for pid (see load_place)."""
        keep = {pid, *self.ancestors(pid), *(self.places[pid].get("neighbors") or [])}
        c = self.places[pid].get("centroid")
        if c:
            keep.update(p for _, p in self.near(c["lat"], c["lon"], PLACE_RADIUS_KM))
        for extra in list(keep):  # nearby places need their own areas so they resolve and describe correctly
            keep.update(self.ancestors(extra))
        sources = [s for s in self.sources if any(cv.get("place") in keep for cv in s.get("coverage") or [])]
        return {"schema": self.data.get("schema", SCHEMA), "license": self.data.get("license", "CC0-1.0"),
                "skill_version": self.data.get("skill_version"), "data_version": self.data.get("data_version"),
                "partial": True, "place": pid, "radius_km": PLACE_RADIUS_KM,
                "places": {k: self.places[k] for k in sorted(keep)}, "sources": sources}

    INDEX_FIELDS = ("name", "kind", "local_kind", "country", "subdivision", "abbreviation", "aliases", "parents",
                    "covers", "neighbors", "centroid", "postal_codes")

    def index(self) -> dict:
        """Every place, with only what resolving and describing it needs, plus how many sources it has."""
        places = {}
        for pid, p in self.places.items():
            row = {k: p[k] for k in self.INDEX_FIELDS if p.get(k) not in (None, [], "")}
            row["direct_sources"] = len(self.direct_sources(pid))
            places[pid] = row
        return {"schema": self.data.get("schema", SCHEMA), "license": self.data.get("license", "CC0-1.0"),
                "skill_version": self.data.get("skill_version"), "data_version": self.data.get("data_version"),
                "partial": True, "places": places, "sources": []}

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
        own = p["direct_sources"] if "direct_sources" in p else len(self.direct_sources(pid))
        out = {"id": pid, "name": p.get("name"), "kind": p.get("kind"), "local_kind": p.get("local_kind"),
               "matched_by": matched_by, "contained_in": self.ancestors(pid),
               "neighbors": list(p.get("neighbors") or []), "centroid": p.get("centroid"),
               "postal_codes": list(p.get("postal_codes") or []), "sources_of_its_own": own}
        if own == 0:
            out["note"] = ("No sources of its own are mapped yet: only area-wide sources (county, state, region) reach it. "
                           "Say so in the coverage report, and offer to map it (references/build.md).")
        return out

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
                "roles": self._role_gaps(pid),
                "neighbours_have": {k: v for k, v in sorted(theirs.items())},
                "area_sources_reaching_it": len([s for s in self.sources_for(pid) if s["relation"] == "area"]),
                "note": "A missing type is a place to look, not proof of a gap: some towns have no paper, no chamber, no farm stand."}

    def _role_gaps(self, pid: str) -> dict:
        """The spread of roles among sources reaching the place (its own and area-wide), and
        which missing roles its neighbours have, so a gap comes with somewhere to look."""
        from . import roles
        reaching = [s for s in self.sources_for(pid) if s["relation"] in ("direct", "area")]
        out = roles.spread(reaching)
        theirs: dict[str, list[dict]] = {}
        for n in self.places[pid].get("neighbors") or []:
            for s in self.direct_sources(n):
                for r in roles.roles_of(s):
                    if r in out["missing_core_roles"]:
                        theirs.setdefault(r, []).append({"place": n, "name": s["name"], "url": s["url"]})
        out["neighbours_have"] = dict(sorted(theirs.items()))
        return out

    def search(self, text: str) -> list[dict]:
        want = norm(text)
        return [s for s in self.sources if want in norm(" ".join(str(s.get(k, "")) for k in ("id", "name", "description", "publisher", "type"))
                                                         + " " + " ".join(s.get("topics") or []))]
