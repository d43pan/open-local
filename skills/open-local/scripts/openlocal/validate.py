"""Check the registry: schema, then the rules a schema cannot express.

Deterministic and offline. Network checks live in check.py.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import urllib.parse

from . import net, registry

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


# Sites that need an account to read (decision 25): listed for a person, never fetched.
LOGIN_WALLED = {"facebook.com", "nextdoor.com", "instagram.com"}

def normalize_url(url: str) -> str:
    p = urllib.parse.urlsplit(url.strip())
    host = (p.hostname or "").lower().removeprefix("www.")
    path = re.sub(r"/+$", "", p.path)
    return f"{host}{path}" + (f"?{p.query}" if p.query else "")


def validate(directory: pathlib.Path | None = None, today: dt.date | None = None,
             only: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors fail a pull request; warnings do not.

    With only (repository paths of registry files, e.g. the ones a pull request changed),
    warnings are limited to those files. Errors are always reported for the whole registry:
    deleting or renaming a place can break a file the pull request never touched.
    """
    errors, warnings = _validate(directory, today)
    if only is None:
        return errors, warnings
    wanted = {f.replace("\\", "/").split("registry/", 1)[-1] for f in only if f.endswith(".yaml")}
    return errors, [w for w in warnings if any(w.startswith(x + ":") for x in wanted)]


def _validate(directory: pathlib.Path | None = None, today: dt.date | None = None) -> tuple[list[str], list[str]]:
    import jsonschema
    today = today or dt.date.today()
    if registry.ROOT is None:
        raise RuntimeError("validate needs a checkout of the repository (registry/ and schemas/)")
    directory = directory or registry.REGISTRY_DIR
    schema = json.loads((registry.ROOT / "schemas" / "registry-file.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    errors, warnings = [], []
    docs = registry.load_yaml_files(directory)
    places: dict[str, dict] = {}
    seen_ids: dict[str, str] = {}
    urls: dict[str, str] = {}
    all_sources: list[tuple[str, str, dict]] = []

    for path, doc in docs:
        rel = path.relative_to(directory).as_posix()
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.absolute_path)):
            where = "/".join(str(x) for x in e.absolute_path) or "(top)"
            errors.append(f"{rel}: {where}: {e.message[:200]}")
        place = (doc or {}).get("place") or {}
        pid = place.get("id")
        if not pid:
            continue
        if rel != pid + ".yaml":
            errors.append(f"{rel}: place id {pid} must live at registry/{pid}.yaml")
        if pid in places:
            errors.append(f"{rel}: duplicate place id {pid}")
        places[pid] = place
        if not pid.startswith(place.get("country", "??")):
            errors.append(f"{rel}: place id must start with its country code {place.get('country')}")
        sub = place.get("subdivision")
        if sub and not sub.startswith(place.get("country", "??") + "-"):
            errors.append(f"{rel}: subdivision {sub} is not in country {place.get('country')}")
        for s in doc.get("sources") or []:
            if isinstance(s, dict) and s.get("id"):
                all_sources.append((rel, pid, s))

    reg = registry.Registry(registry.build(directory)) if not errors else None

    for pid, place in places.items():
        rel = pid + ".yaml"
        for key in ("parents", "covers", "neighbors"):
            for ref in place.get(key) or []:
                if ref not in places:
                    errors.append(f"{rel}: {key} refers to {ref}, which is not in the registry")
                elif ref == pid:
                    errors.append(f"{rel}: {key} refers to itself")
        for n in place.get("neighbors") or []:
            if n in places and pid not in (places[n].get("neighbors") or []):
                warnings.append(f"{rel}: lists {n} as a neighbor but {n} does not list it back")
        if place.get("kind") != "country" and not place.get("parents") and "/" in pid:
            warnings.append(f"{rel}: has no parents, so area-wide sources will not reach it")
        if reg and any(pid in reg.ancestors(u) for u in reg._up.get(pid, ())):
            errors.append(f"{rel}: is its own ancestor (cycle in parents/covers)")
        if reg:  # geographic consistency: a place should sit near the areas said to contain it
            c = place.get("centroid")
            for up in place.get("parents") or []:
                pc = places.get(up, {}).get("centroid")
                limit = {"county": 150, "region": 1500, "country": 6000}.get(places.get(up, {}).get("kind"), 400)
                if c and pc and reg.distance_km(c, pc) > limit:
                    errors.append(f"{rel}: centre is {reg.distance_km(c, pc):.0f} km from parent {up}; check the coordinates")
            for n in place.get("neighbors") or []:
                nc = places.get(n, {}).get("centroid")
                if c and nc and reg.distance_km(c, nc) > 100:
                    warnings.append(f"{rel}: neighbor {n} is {reg.distance_km(c, nc):.0f} km away")
        known_q = {(pl.get("identifiers") or {}).get("wikidata"): other for other, pl in places.items()}
        for adj in place.get("adjacent_unmapped") or []:
            if adj.get("wikidata") in known_q and adj.get("wikidata"):
                errors.append(f"{rel}: adjacent_unmapped lists {adj['name']}, but it is in the registry as {known_q[adj['wikidata']]}; move it to neighbors")
        if place.get("kind") in ("municipality", "neighbourhood") and not place.get("centroid"):
            warnings.append(f"{rel}: no centroid, so radius and coordinate searches cannot find it")

    for rel, pid, s in all_sources:
        sid = s["id"]
        tag = f"{rel}: {sid}"
        if sid in seen_ids:
            errors.append(f"{tag}: duplicate source id (also in {seen_ids[sid]})")
        seen_ids[sid] = rel
        prefix = pid.lower().replace("/", "-") + "-"
        if not sid.startswith(prefix):
            errors.append(f"{tag}: id must start with {prefix}")
        for c in s.get("coverage") or []:
            if c.get("place") not in places:
                errors.append(f"{tag}: coverage refers to {c.get('place')}, which is not in the registry")
        for key in ("jurisdiction",):
            if s.get(key) and s[key] not in places:
                errors.append(f"{tag}: {key} refers to {s[key]}, which is not in the registry")
        loc = (s.get("location") or {}).get("place")
        if loc and loc not in places:
            errors.append(f"{tag}: location refers to {loc}, which is not in the registry")
        for label, url in [("url", s.get("url"))] + [(f"endpoint {e.get('kind')}", e.get("url")) for e in s.get("endpoints") or []]:
            if not url:
                continue
            try:
                net.check_url(url)
            except net.Blocked as e:
                errors.append(f"{tag}: {label} refused: {e}")
            key = normalize_url(url)
            if label != "url":
                continue
            if key in urls and urls[key] != sid:
                warnings.append(f"{tag}: same home page as {urls[key]}; one source or two?")
            urls.setdefault(key, sid)
        try:
            found = dt.date.fromisoformat(s.get("discovered", ""))
            if found > today:
                errors.append(f"{tag}: discovered date is in the future")
            if s.get("verified"):
                ver = dt.date.fromisoformat(s["verified"])
                if ver > today:
                    errors.append(f"{tag}: verified date is in the future")
                if ver < found:
                    errors.append(f"{tag}: verified before it was discovered")
        except ValueError:
            errors.append(f"{tag}: dates must be real calendar dates (YYYY-MM-DD)")
        if s.get("status") in ("verified", "checked") and not s.get("verified"):
            errors.append(f"{tag}: status is {s['status']} but there is no verified date")
        if s.get("status") == "verified" and (s.get("provenance") or {}).get("method") == "agent-proposed" \
                and not (s.get("provenance") or {}).get("added_by"):
            errors.append(f"{tag}: an agent-proposed source needs a named human reviewer (provenance.added_by) before it is verified")
        if EMAIL.search(json.dumps(s)):
            errors.append(f"{tag}: contains an email address; the registry holds no personal contact details")
        if not s.get("endpoints"):
            warnings.append(f"{tag}: no endpoints listed; agents can only visit the home page")
        for e in s.get("endpoints") or []:
            if e.get("agent_readable") is False and not e.get("blocked_by"):
                errors.append(f"{tag}: endpoint {e.get('url')} is marked agent_readable: false; say why with blocked_by")
            if e.get("blocked_by") and e.get("agent_readable") is not False:
                errors.append(f"{tag}: endpoint {e.get('url')} has blocked_by but is not marked agent_readable: false")
        acc = s.get("access") or {}
        if acc.get("agent_readable") is False and not acc.get("blocked_by"):
            errors.append(f"{tag}: access.agent_readable is false; say why with access.blocked_by")
        host = urllib.parse.urlsplit(s.get("url", "")).netloc.lower().removeprefix("www.").removeprefix("m.")
        if host in LOGIN_WALLED and acc.get("agent_readable") is not False:
            errors.append(f"{tag}: {host} needs an account to read; mark access.agent_readable: false, blocked_by: login")
        if host in LOGIN_WALLED and s.get("endpoints"):
            errors.append(f"{tag}: list no endpoints for {host}; tools must not read it")
    return errors, warnings
