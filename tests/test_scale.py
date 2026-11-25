"""Scaling without growing context: smaller output, per-place files, versioned data,
sources that need a person, seeded places, and checks that rotate and shard (issue #2)."""
import datetime as dt
import json

import pytest

from conftest import FIX
from openlocal import check, cli, export, net, recent, registry, seed, validate
from openlocal.registry import IncompatibleData, Registry

TODAY = dt.date(2026, 11, 24)

GAZETTE_MIXED = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>Shire Gazette</title>
<item><title>Alder council approves harbour dredging contract</title><link>https://gazette.example.org/x9</link>
<pubDate>Tue, 24 Nov 2026 09:00:00 GMT</pubDate><description>In Alder.</description></item>
<item><title>Ferry fares rise across the shire</title><link>https://gazette.example.org/x10</link>
<pubDate>Mon, 23 Nov 2026 09:00:00 GMT</pubDate><description>Statewide story.</description></item>
<item><title>Elsewhere: a bakery opens</title><link>https://gazette.example.org/x11</link>
<pubDate>Mon, 23 Nov 2026 10:00:00 GMT</pubDate><description>Not about the town.</description></item>
</channel></rss>"""

NETWORK = {
    "https://harbourtimes.example.org/rss.xml": (200, "feed.rss"),
    "https://gazette.example.org/feed/": (200, GAZETTE_MIXED),
    "https://alder.example.org/council.ics": (200, "council.ics"),
}


# ---- 1. output stays small and local ---------------------------------------------------

def test_area_items_must_name_the_place(reg, fake_net):
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=fake_net(NETWORK))
    gazette = [i["title"] for i in out["items"] if i["source_id"] == "xx-no-shire-gazette"]
    assert gazette == ["Alder council approves harbour dredging contract"]
    assert out["coverage"]["area_items_not_about_place"] == 2
    assert out["coverage"]["area_filter"].startswith("on")
    row = next(f for f in out["coverage"]["fetched"] if f["source_id"] == "xx-no-shire-gazette")
    assert row["not_about_place"] == 2


def test_all_area_lists_everything(reg, fake_net):
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=fake_net(NETWORK), all_area=True)
    assert len([i for i in out["items"] if i["source_id"] == "xx-no-shire-gazette"]) == 3
    assert out["coverage"]["area_items_not_about_place"] == 0


def test_direct_sources_are_never_filtered(reg, fake_net):
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=fake_net(NETWORK))
    assert any(i["source_id"] == "xx-no-alder-harbour-times" for i in out["items"])


def test_mentions_matches_whole_words_only():
    assert recent.mentions("Little Compton approves budget", ["little compton"])
    assert recent.mentions("Café in Ålder", ["alder"])
    assert not recent.mentions("Balderdash at the fair", ["alder"])


def test_brief_is_much_smaller_and_keeps_what_a_briefing_cites(reg, fake_net):
    full = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=fake_net(NETWORK), all_area=True)
    short = recent.brief(full)
    assert len(json.dumps(short)) < 0.75 * len(json.dumps(full))
    for i in short["items"]:
        assert {"title", "url", "date", "source", "kind", "relation"} <= set(i) and "summary" not in i
    assert short["coverage"]["warning"] and "untrusted" in short["handling"]
    assert "registry" in short["coverage"]


def test_per_source_cap(reg, fake_net):
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=fake_net(NETWORK), all_area=True, per_source=1)
    assert len([i for i in out["items"] if i["source_id"] == "xx-no-shire-gazette"]) == 1


# ---- 4. sources that need a person ------------------------------------------------------

def test_flagged_endpoint_is_not_fetched_and_is_listed_for_a_person(reg, fake_net):
    council = next(s for s in reg.sources if s["id"] == "xx-no-alder-town-council")
    ics = next(e for e in council["endpoints"] if e["kind"] == "ical")
    ics.update(agent_readable=False, blocked_by="robots-txt")
    f = fake_net(NETWORK)
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=f)
    assert ics["url"] not in f.calls
    need = out["coverage"]["needs_a_person"]
    assert [(n["source_id"], n["blocked_by"]) for n in need] == [("xx-no-alder-town-council", "robots-txt")]
    assert not any(x["source_id"] == "xx-no-alder-town-council" for x in out["coverage"]["failed"])
    assert not any(x["source_id"] == "xx-no-alder-town-council" for x in out["coverage"]["read_by_hand"])


def test_robots_block_found_at_run_time_is_for_a_person_not_a_failure(reg, fake_net):
    f = fake_net(NETWORK)

    def fetch(url, **kw):
        if url.endswith("council.ics"):
            raise net.Blocked("disallowed by robots.txt")
        return f(url, **kw)
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=fetch)
    need = out["coverage"]["needs_a_person"]
    assert need and need[0]["blocked_by"] == "robots-txt" and need[0]["detected_now"]
    assert not out["coverage"]["failed"]


def test_whole_source_marked_not_readable(reg, fake_net):
    gazette = next(s for s in reg.sources if s["id"] == "xx-no-shire-gazette")
    gazette["access"].update(agent_readable=False, blocked_by="terms", restrictions="Terms forbid automated access.")
    f = fake_net(NETWORK)
    out = recent.recent(reg, "XX/NO/alder", today=TODAY, fetch=f)
    assert "https://gazette.example.org/feed/" not in f.calls
    assert out["coverage"]["needs_a_person"][0]["why"] == "Terms forbid automated access."


def test_check_skips_flagged_endpoints(reg, fake_net):
    s = next(s for s in reg.sources if s["id"] == "xx-no-alder-harbour-times")
    s["endpoints"][0].update(agent_readable=False, blocked_by="robots-txt")
    f = fake_net({"https://harbourtimes.example.org/": (200, b"<html></html>")})
    rep = check.check_source(s, TODAY)
    assert rep["problems"] == [] and "https://harbourtimes.example.org/rss.xml" not in f.calls
    assert rep["endpoints"][1]["skipped"]


def test_validate_requires_a_reason_for_agent_readable_false(tmp_path):
    reg_dir = tmp_path / "registry"
    import shutil
    shutil.copytree(FIX / "registry", reg_dir)
    f = reg_dir / "XX" / "NO.yaml"
    f.write_text(f.read_text().replace('endpoints: [{kind: rss, url: "https://gazette.example.org/feed/"}]',
                                       'endpoints: [{kind: rss, url: "https://gazette.example.org/feed/", agent_readable: false}]'))
    errors, _ = validate.validate(reg_dir, TODAY)
    assert any("say why with blocked_by" in e for e in errors)


# ---- 2. per-place files and the index ----------------------------------------------------

def test_a_place_file_answers_exactly_like_the_whole_registry(reg):
    for pid in reg.places:
        part = Registry(reg.place_slice(pid))
        assert part.partial
        for kw in ({}, {"neighbors": True}, {"radius_km": registry.PLACE_RADIUS_KM}):
            assert [s["id"] for s in part.sources_for(pid, **kw)] == [s["id"] for s in reg.sources_for(pid, **kw)], (pid, kw)
        assert part.describe(pid) == reg.describe(pid)
        assert part.gaps(pid) == reg.gaps(pid)


def test_the_index_resolves_places_without_any_sources(reg):
    idx = Registry(reg.index())
    assert idx.sources == []
    for q in ("Alder", "Alder, NO", "XX/NO/birch"):
        assert [m["id"] for m in idx.resolve(q)] == [m["id"] for m in reg.resolve(q)]
    assert [m["id"] for m in idx.resolve(postal="02837")] == ["XX/NO/alder"]
    assert idx.describe("XX/NO/alder")["sources_of_its_own"] == reg.describe("XX/NO/alder")["sources_of_its_own"] > 0


def test_a_place_with_no_sources_says_so(reg):
    reg.places["XX/NO/cedar"] = {"id": "XX/NO/cedar", "name": "Cedar", "kind": "municipality", "country": "XX", "parents": ["XX/NO"]}
    d = reg.describe("XX/NO/cedar")
    assert d["sources_of_its_own"] == 0 and "No sources of its own" in d["note"]


def test_published_files_include_index_and_one_file_per_place(reg):
    files = export.published_files(reg)
    assert {"registry.json", "index.json"} <= set(files)
    assert {f"places/{p}.json" for p in reg.places} <= set(files)
    for p in reg.places:
        assert json.loads(files[f"places/{p}.json"])["place"] == p


# ---- 3. versions ----------------------------------------------------------------------

def test_data_carries_versions_and_a_content_fingerprint():
    a = registry.build(FIX / "registry")
    assert a["schema"] == registry.SCHEMA and a["skill_version"] and len(a["data_version"]) == 12
    assert registry.build(FIX / "registry")["data_version"] == a["data_version"]  # deterministic
    b = dict(a, sources=a["sources"][1:])
    assert registry.data_version(b["places"], b["sources"]) != a["data_version"]


def test_newer_schema_is_refused_with_an_update_message():
    with pytest.raises(IncompatibleData, match="Update the skill"):
        Registry({"schema": "open-local/registry/2", "places": {}, "sources": []})


def test_newer_skill_version_gives_a_notice_not_an_error():
    r = Registry({"schema": registry.SCHEMA, "skill_version": "99.0.0", "places": {}, "sources": []})
    assert "newer open-local skill" in r.notice and r.versions()["notice"] == r.notice
    assert Registry({"schema": registry.SCHEMA, "skill_version": "0.0.1", "places": {}, "sources": []}).notice is None


def test_version_command(capsys):
    assert cli.main(["--version"]) == 0
    got = json.loads(capsys.readouterr().out)
    assert got["skill"] and got["data"] and got["schema"] == registry.SCHEMA


# ---- installed-skill path: fetch the index, then one place, with ETags --------------------

class Net:
    def __init__(self, files):
        self.files, self.calls = files, []

    def __call__(self, url, if_none_match=None, **kw):
        self.calls.append((url, if_none_match))
        path = url.removeprefix(registry.DATA_URL)
        if path not in self.files:
            return net.Response(url, 404, {}, b"")
        body = self.files[path].encode()
        etag = f'"{hash(body)}"'
        if if_none_match == etag:
            return net.Response(url, 304, {"etag": etag}, b"")
        return net.Response(url, 200, {"etag": etag, "content-type": "application/json"}, body)


@pytest.fixture
def installed(monkeypatch, tmp_path, reg):
    """Behave like a skill installed without the repository."""
    monkeypatch.setattr(registry, "ROOT", None)
    monkeypatch.delenv("OPEN_LOCAL_REGISTRY", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    Registry._local_cache.clear()
    fake = Net(export.published_files(Registry(registry.build(FIX / "registry"))))
    monkeypatch.setattr(net, "fetch", fake)
    return fake


def test_installed_skill_fetches_index_then_one_place(installed):
    idx = Registry.load_index()
    assert idx.partial and "XX/NO/alder" in idx.places and idx.sources == []
    part = Registry.load_place("XX/NO/alder")
    assert part.partial and part.data["place"] == "XX/NO/alder"
    fetched = [u.removeprefix(registry.DATA_URL) for u, _ in installed.calls]
    assert fetched[:2] == ["index.json", "places/XX/NO/alder.json"]
    assert "registry.json" not in fetched


def test_cache_is_revalidated_with_the_etag(installed, tmp_path):
    import os
    import time
    registry.cached_get("index.json")
    f = tmp_path / "open-local" / "index.json"
    old = time.time() - 2 * 86400
    os.utime(f, (old, old))
    registry.cached_get("index.json")
    assert installed.calls[-1][1] is not None  # sent If-None-Match
    assert f.stat().st_mtime > old  # 304 refreshed the copy's age


def test_wider_radius_falls_back_to_the_whole_registry(installed):
    Registry.load_place("XX/NO/alder", radius_km=registry.PLACE_RADIUS_KM + 1)
    paths = [u.removeprefix(registry.DATA_URL) for u, _ in installed.calls]
    assert "registry.json" in paths and not any(p.startswith("places/") for p in paths)


def test_check_results_are_fetched_only_for_homes_that_reach_the_place(installed):
    Registry.load_place("XX/NO/alder")
    checks = sorted(u.removeprefix(registry.DATA_URL) for u, _ in installed.calls if "/checks/" in u)
    homes = sorted({f"checks/{s['home']}.json" for s in Registry(registry.build(FIX / "registry")).sources_for(
        "XX/NO/alder", neighbors=True, radius_km=registry.PLACE_RADIUS_KM)})
    assert checks == homes


def test_older_published_data_without_an_index_still_works(installed):
    del installed.files["index.json"]
    assert "XX/NO/alder" in Registry.load_index().places
    assert any(u.endswith("registry.json") for u, _ in installed.calls)


def test_cached_get_refuses_odd_paths(installed):
    with pytest.raises(ValueError):
        registry.cached_get("../secrets.json")


def test_check_results_are_merged_into_a_place(installed):
    installed.files["checks/XX/NO/alder.json"] = json.dumps(
        {"schema": "open-local/checks/1", "home": "XX/NO/alder",
         "sources": {"xx-no-alder-town-council": {"checked": "2026-11-23", "ok": True, "problems": [], "endpoints": []}}})
    part = Registry.load_place("XX/NO/alder")
    council = next(s for s in part.sources if s["id"] == "xx-no-alder-town-council")
    assert council["last_checked"]["checked"] == "2026-11-23"


# ---- 6. checks that rotate, shard by host, and are recorded ------------------------------

def many_sources(n=200):
    return [{"id": f"xx-s{i}", "url": f"https://site{i % 37}.example.org/p{i}", "home": "XX/NO/alder" if i % 2 else "XX/NO/birch"}
            for i in range(n)]


def test_parts_cover_every_source_exactly_once():
    srcs = many_sources()
    parts = [check.select(srcs, part=f"{w}/4") for w in range(4)]
    ids = [s["id"] for p in parts for s in p]
    assert sorted(ids) == sorted(s["id"] for s in srcs) and len(ids) == len(set(ids))
    assert all(parts)  # no empty week


def test_a_site_never_spans_two_shards():
    srcs = many_sources()
    shard_of = {}
    for i in range(3):
        for s in check.select(srcs, shard=f"{i}/3"):
            assert shard_of.setdefault(check.host(s), i) == i


def test_select_by_home_and_bad_specs():
    srcs = many_sources(10)
    assert {s["home"] for s in check.select(srcs, home_prefix="XX/NO/birch")} == {"XX/NO/birch"}
    assert len(check.select(srcs, home_prefix="XX/NO")) == 10
    assert check.select(srcs, home_prefix="XX/N") == []  # a prefix is a whole path segment
    with pytest.raises(ValueError):
        check.select(srcs, part="4/4")


def test_record_keeps_older_results_and_forgets_removed_sources(tmp_path, reg):
    srcs = reg.sources
    council = next(s for s in srcs if s["id"] == "xx-no-alder-town-council")
    stand = next(s for s in srcs if s["id"] == "xx-no-alder-farm-stand")
    rep = lambda s, problems: {"id": s["id"], "name": s["name"], "problems": problems,
                               "endpoints": [{"kind": "home", "url": s["url"], "http": 200}]}
    check.record([rep(council, [])], srcs, tmp_path, dt.date(2026, 11, 1))
    check.record([rep(stand, ["home returns HTTP 500: x"])], srcs, tmp_path, dt.date(2026, 11, 8))
    data = json.loads((tmp_path / "checks" / "XX" / "NO" / "alder.json").read_text())
    assert data["sources"]["xx-no-alder-town-council"]["checked"] == "2026-11-01"
    assert data["sources"]["xx-no-alder-farm-stand"] == {"checked": "2026-11-08", "ok": False, "problems": ["home returns HTTP 500: x"],
                                                         "endpoints": [{"url": stand["url"], "kind": "home", "http": 200, "ok": True}]}
    check.record([], [s for s in srcs if s["id"] != "xx-no-alder-farm-stand"], tmp_path)
    check.record([rep(council, [])], [s for s in srcs if s["id"] != "xx-no-alder-farm-stand"], tmp_path, dt.date(2026, 11, 15))
    data = json.loads((tmp_path / "checks" / "XX" / "NO" / "alder.json").read_text())
    assert set(data["sources"]) == {"xx-no-alder-town-council"}


def test_validate_only_filters_warnings_but_never_errors(tmp_path):
    import shutil
    reg_dir = tmp_path / "registry"
    shutil.copytree(FIX / "registry", reg_dir)
    errors_all, warnings_all = validate.validate(reg_dir, TODAY)
    assert warnings_all
    errors, warnings = validate.validate(reg_dir, TODAY, only=["registry/XX.yaml"])
    assert errors == errors_all and all(w.startswith("XX.yaml:") for w in warnings)
    # Breaking a reference elsewhere is still an error when only an unrelated file changed
    (reg_dir / "XX" / "NO" / "birch.yaml").unlink()
    errors, _ = validate.validate(reg_dir, TODAY, only=["registry/XX.yaml"])
    assert any("birch" in e for e in errors)


# ---- 5. seeding places from the Census Gazetteer ------------------------------------------

COUNTIES = ("USPS\tGEOID\tANSICODE\tNAME\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG\n"
            "NO\t99001\t1\tWest County\t1\t1\t1\t1\t41.50\t-71.20\n"
            "NO\t99003\t1\tEast County\t1\t1\t1\t1\t41.60\t-71.10\n"
            "ZZ\t98001\t1\tOther County\t1\t1\t1\t1\t30.0\t-90.0\n")
COUSUBS = ("USPS\tGEOID\tANSICODE\tNAME\tFUNCSTAT\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG\n"
           "NO\t9900100001\t1\tAlder town\tA\t1\t1\t1\t1\t41.51\t-71.17\n"
           "NO\t9900100002\t1\tCedar Hill city\tF\t1\t1\t1\t1\t41.52\t-71.18\n"
           "NO\t9900100003\t1\tWashington township\tA\t1\t1\t1\t1\t41.53\t-71.19\n"
           "NO\t9900300004\t1\tWashington township\tA\t1\t1\t1\t1\t41.63\t-71.09\n"
           "NO\t9900300005\t1\tNorth CCD\tS\t1\t1\t1\t1\t41.6\t-71.1\n"
           "NO\t9900500000\t0\tCounty subdivisions not defined\tF\t0\t0\t0\t0\t0\t0\n")


def test_seed_plans_counties_and_towns_and_never_touches_existing_places(tmp_path, reg):
    (tmp_path / "c.txt").write_text(COUNTIES)
    (tmp_path / "2024_Gaz_cousubs_national.txt").write_text(COUSUBS)
    reg.places["XX/NO/alder"].setdefault("identifiers", {})["us_census_geoid"] = "9900100001"
    reg.places["US/NO"] = dict(reg.places["XX/NO"], id="US/NO", country="US", subdivision="US-NO")
    got = seed.plan(reg, str(tmp_path / "2024_Gaz_cousubs_national.txt"), str(tmp_path / "c.txt"), "NO", TODAY)
    new = got["new"]
    assert set(new) == {"US/NO/west-county", "US/NO/east-county", "US/NO/cedar-hill", "US/NO/washington-west", "US/NO/washington-east"}
    assert [e["id"] for e in got["existing"]] == ["XX/NO/alder"]  # matched by GEOID, left alone
    cedar = new["US/NO/cedar-hill"]
    assert cedar["name"] == "Cedar Hill" and cedar["local_kind"] == "city" and cedar["parents"] == ["US/NO/west-county"]
    assert cedar["identifiers"] == {"us_census_geoid": "9900100002"} and cedar["centroid"] == {"lat": 41.52, "lon": -71.18}
    assert cedar["provenance"] == {"method": "import", "dataset": "US Census Gazetteer 2024 (county subdivisions)", "imported": "2026-11-24"}
    assert new["US/NO/west-county"]["identifiers"]["ocd_division"] == "ocd-division/country:us/state:no/county:west"
    assert "sources" not in seed.to_yaml(cedar)


def test_seed_needs_the_state_first(tmp_path, reg):
    (tmp_path / "c.txt").write_text(COUNTIES)
    (tmp_path / "p.txt").write_text(COUSUBS)
    with pytest.raises(SystemExit, match="not in the registry"):
        seed.plan(reg, str(tmp_path / "p.txt"), str(tmp_path / "c.txt"), "NO", TODAY)


def test_split_name():
    assert seed.split_name("Little Compton town") == ("Little Compton", "town")
    assert seed.split_name("Newport County") == ("Newport", "county")
    assert seed.split_name("Anchorage municipality") == ("Anchorage", "municipality")
    assert seed.split_name("Nantucket") == ("Nantucket", None)


def test_reports_are_split_by_area_and_name_maintainers(reg):
    srcs = [{"id": "a", "home": "US/RI/little-compton"}, {"id": "b", "home": "US/MA/westport"}, {"id": "c", "home": "US/RI"},
            {"id": "d", "home": "US/RI/tiverton"}]
    reports = [{"id": "a", "name": "A", "problems": ["x"]}, {"id": "b", "name": "B", "problems": ["y"]},
               {"id": "c", "name": "C", "problems": []}, {"id": "d", "name": "D", "problems": ["z"]}]
    owners = "# maintainers\nregistry/US/RI/ @ri-team\n/registry/US/RI/tiverton.yaml @tiverton-librarian\n"
    got = check.report_by_area(reports, srcs, owners, stale=[{"id": "c", "verified": None}])
    assert set(got) == {"US/RI", "US/MA"}
    assert "2 source(s) in US/RI" in got["US/RI"] and "@ri-team" in got["US/RI"] and "@tiverton-librarian" in got["US/RI"]
    assert "@" not in got["US/MA"] and "`c` (last verified: never)" in got["US/RI"]
    assert check.owners_for("registry/US/RI/tiverton.yaml", owners) == ["@tiverton-librarian"]  # last match wins
    assert check.owners_for("registry/US/MA/westport.yaml", owners) == []


def test_a_place_copy_older_than_the_published_data_is_fetched_again(installed):
    Registry.load_place("XX/NO/alder")
    place = json.loads(installed.files["places/XX/NO/alder.json"])
    index = json.loads(installed.files["index.json"])
    # A merge lands: the published index and place file move to a new data version.
    place["data_version"] = index["data_version"] = "newer"
    installed.files["places/XX/NO/alder.json"], installed.files["index.json"] = json.dumps(place), json.dumps(index)
    import os, time
    old = time.time() - 2 * 3600  # older than the index's hourly recheck, well inside the place file's day
    os.utime(registry.cache_dir() / "index.json", (old, old))
    assert Registry.load_place("XX/NO/alder").data["data_version"] == "newer"
