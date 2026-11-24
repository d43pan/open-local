"""Draft place files from a national gazetteer, so contributors add sources, not geography.

    run.py seed us-census --places 2024_Gaz_cousubs_national.txt \
                          --counties 2024_Gaz_counties_national.txt --state RI [--write]

The files are the US Census Bureau Gazetteer files (public domain), downloaded by the
person running this: https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
Use the county subdivisions file where towns are real governments (New England, New York,
New Jersey, Pennsylvania, the Midwest townships), and the places file elsewhere.

A seeded place has an id, a name, its county, a centre point and its Census GEOID. It
has no sources: it exists so that a person mapping it never has to type coordinates or
identifiers, and so that `where` can say "known place, nothing mapped yet" instead of
"not in the registry". Places already in the registry are never changed.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import pathlib
import re
import unicodedata

from . import registry
from .registry import Registry

DATASET = "US Census Gazetteer"
# Legal/statistical descriptors at the end of Gazetteer names, longest first.
DESCRIPTORS = ["unorganized territory", "census designated place", "consolidated government", "metropolitan government",
               "unified government", "urban county", "planning region", "census area", "city and borough", "plantation",
               "township", "borough", "village", "charter township", "municipality", "location", "purchase", "county",
               "parish", "grant", "town", "city", "gore", "cdp"]
SKIP_FUNCSTAT = {"S", "N", "I"}  # statistical, nonfunctioning, inactive: not places people govern or name


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def split_name(raw: str) -> tuple[str, str | None]:
    """"Little Compton town" -> ("Little Compton", "town"). Names without a descriptor are kept whole."""
    low = raw.lower()
    for d in DESCRIPTORS:
        if low.endswith(" " + d):
            return raw[: -len(d) - 1].strip(), d
    return raw.strip(), None


def read_gazetteer(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    return [{k.strip(): (v or "").strip() for k, v in r.items() if k} for r in rows]


def plan(reg: Registry, places_file: str, counties_file: str, state: str, today: dt.date | None = None) -> dict:
    """What seeding would add for one state, without writing anything."""
    today = today or dt.date.today()
    state = state.upper()
    state_id = f"US/{state}"
    if state_id not in reg.places:
        raise SystemExit(f"{state_id} is not in the registry yet; add the state's own place file first.")
    by_geoid = {(p.get("identifiers") or {}).get("us_census_geoid"): pid for pid, p in reg.places.items()}
    vintage = re.search(r"(20\d\d)", pathlib.Path(places_file).name)
    dataset = f"{DATASET} {vintage.group(1)}" if vintage else DATASET
    new, existing = {}, []

    county_id_by_geoid = {}
    for r in read_gazetteer(counties_file):
        if r.get("USPS") != state:
            continue
        geoid, (name, desc) = r["GEOID"], split_name(r["NAME"])
        pid = by_geoid.get(geoid) or f"{state_id}/{slug(r['NAME'])}"
        county_id_by_geoid[geoid] = pid
        if pid in reg.places:
            existing.append({"id": pid, "geoid": geoid, "has_geoid": geoid in by_geoid})
            continue
        place = {"id": pid, "name": r["NAME"], "kind": "county", "local_kind": desc or "county", "country": "US",
                 "subdivision": f"US-{state}", "parents": [state_id],
                 "centroid": {"lat": round(float(r["INTPTLAT"]), 4), "lon": round(float(r["INTPTLONG"]), 4)},
                 "identifiers": {"us_census_geoid": geoid}}
        if desc == "county":
            place["identifiers"]["ocd_division"] = f"ocd-division/country:us/state:{state.lower()}/county:{slug(name).replace('-', '_')}"
        new[pid] = place

    rows = [r for r in read_gazetteer(places_file) if r.get("USPS") == state]
    cousub = bool(rows) and len(rows[0]["GEOID"]) == 10
    if cousub:
        dataset += " (county subdivisions)"
    else:
        dataset += " (places)"
    candidates = []
    for r in rows:
        if r.get("FUNCSTAT") in SKIP_FUNCSTAT or "not defined" in r["NAME"].lower() or r["GEOID"].endswith("00000"):
            continue
        name, desc = split_name(r["NAME"])
        county = county_id_by_geoid.get(r["GEOID"][:5]) if cousub else None
        candidates.append((r, name, desc, county))
    counts: dict[str, int] = {}
    for _, name, _, _ in candidates:
        counts[slug(name)] = counts.get(slug(name), 0) + 1
    for r, name, desc, county in candidates:
        geoid = r["GEOID"]
        base = slug(name)
        if counts[base] > 1:  # two Washington townships in one state: tell them apart by county, then by kind
            base = f"{base}-{slug(county.split('/')[-1]).removesuffix('-county')}" if county else f"{base}-{slug(desc or 'place')}"
        pid = by_geoid.get(geoid) or f"{state_id}/{base}"
        if pid in reg.places or pid in new:
            existing.append({"id": pid, "geoid": geoid, "has_geoid": geoid in by_geoid})
            continue
        place = {"id": pid, "name": name, "kind": "municipality", **({"local_kind": desc} if desc else {}), "country": "US",
                 "subdivision": f"US-{state}", "parents": [county or state_id],
                 "centroid": {"lat": round(float(r["INTPTLAT"]), 4), "lon": round(float(r["INTPTLONG"]), 4)},
                 "identifiers": {"us_census_geoid": geoid}}
        new[pid] = place
    for place in new.values():
        place["provenance"] = {"method": "import", "dataset": dataset, "imported": today.isoformat()}
    return {"state": state_id, "dataset": dataset, "new": new, "existing": existing,
            "existing_without_geoid": [e for e in existing if not e["has_geoid"]]}


def to_yaml(place: dict) -> str:
    import yaml
    return yaml.safe_dump({"place": place}, sort_keys=False, allow_unicode=True, width=120)


def main(args) -> int:
    if registry.ROOT is None:
        print("seed needs a checkout of the repository")
        return 2
    reg = Registry.load()
    got = plan(reg, args.places, args.counties, args.state)
    summary = {"state": got["state"], "dataset": got["dataset"], "new_places": sorted(got["new"]),
               "already_in_registry": [e["id"] for e in got["existing"]],
               "in_registry_without_a_census_geoid": [e["id"] for e in got["existing_without_geoid"]],
               "written": False}
    if args.write:
        for pid, place in got["new"].items():
            f = registry.REGISTRY_DIR / f"{pid}.yaml"
            if f.exists():
                continue
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(to_yaml(place), encoding="utf-8")
        summary["written"] = True
        summary["next"] = "Run validate and build. Seeded places have no sources; map them with references/build.md."
    print(json.dumps(summary, indent=1))
    return 0
