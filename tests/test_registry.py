import pytest


def test_resolve_by_name_alias_id_and_qualifier(reg):
    assert [m["id"] for m in reg.resolve("Alder")] == ["XX/NO/alder"]
    assert [m["id"] for m in reg.resolve("alder harbour")] == ["XX/NO/alder"]
    assert [m["id"] for m in reg.resolve("Alder, Northshire")] == ["XX/NO/alder"]
    assert [m["id"] for m in reg.resolve("Alder, NO")] == ["XX/NO/alder"]
    assert reg.resolve("Alder, Elsewhere") == []
    assert reg.resolve("XX/NO/birch")[0]["matched_by"] == "exact id"
    assert reg.resolve("Atlantis") == []


def test_resolve_by_postal_code_and_point(reg):
    assert [m["id"] for m in reg.resolve(postal="02837")] == ["XX/NO/alder"]
    near = reg.resolve(lat=41.52, lon=-71.17)
    assert near[0]["id"] == "XX/NO/alder" and near[1]["id"] == "XX/NO/birch"


def test_overlapping_jurisdictions_are_found(reg):
    up = reg.ancestors("XX/NO/alder")
    assert up[-1] == "XX" and "XX/NO" in up and "XX/NO/school-district" in up
    assert reg.ancestors("XX") == []
    assert set(reg.descendants("XX/NO/school-district")) == {"XX/NO/alder", "XX/NO/birch"}


def test_sources_for_a_place_most_local_first(reg):
    got = {s["id"]: s for s in reg.sources_for("XX/NO/alder")}
    assert got["xx-no-alder-town-council"]["relation"] == "direct"
    assert got["xx-no-alder-harbour-times"]["relation"] == "direct"      # covers Alder though it sits in Birch
    assert got["xx-no-school-district-committee"]["relation"] == "area"  # a district that covers the town
    assert got["xx-no-shire-gazette"]["relation"] == "area"
    assert "xx-no-birch-library" not in got                              # a neighbour's source is not included by default
    order = [s["id"] for s in reg.sources_for("XX/NO/alder")]
    assert order.index("xx-no-alder-town-council") < order.index("xx-no-shire-gazette")


def test_coverage_decides_relevance_not_the_publishers_address(reg):
    birch = {s["id"]: s for s in reg.sources_for("XX/NO/birch")}
    assert birch["xx-no-alder-harbour-times"]["relation"] == "direct" and birch["xx-no-alder-harbour-times"]["level"] == "regular"
    assert "xx-no-alder-town-council" not in birch


def test_neighbors_and_radius(reg):
    assert "xx-no-birch-library" in {s["id"] for s in reg.sources_for("XX/NO/alder", neighbors=True)}
    near = {s["id"]: s["relation"] for s in reg.sources_for("XX/NO/alder", radius_km=15)}
    assert near["xx-no-birch-library"] == "nearby"
    assert "xx-no-birch-library" not in {s["id"] for s in reg.sources_for("XX/NO/alder", radius_km=2)}


def test_filters(reg):
    assert [s["id"] for s in reg.sources_for("XX/NO/alder", types=["farm-market"])] == ["xx-no-alder-farm-stand"]
    assert [s["id"] for s in reg.sources_for("XX/NO/alder", topics=["food"])] == ["xx-no-alder-farm-stand"]
    assert [s["id"] for s in reg.search("gazette")] == ["xx-no-shire-gazette"]


def test_unknown_place_raises(reg):
    with pytest.raises(KeyError):
        reg.sources_for("XX/NO/nowhere")


def test_frontier_ranks_unmapped_neighbours_and_suggests_what_to_reuse(reg):
    reg.places["XX/NO/alder"]["adjacent_unmapped"] = [{"name": "Cedar", "wikidata": "Q5"}, {"name": "Dune"}]
    reg.places["XX/NO/birch"]["adjacent_unmapped"] = [{"name": "Cedar", "wikidata": "Q5", "note": "by the bridge"}]
    rows = reg.frontier()
    assert [r["name"] for r in rows] == ["Cedar", "Dune"]          # Cedar borders two mapped places
    cedar = rows[0]
    assert cedar["borders"] == ["XX/NO/alder", "XX/NO/birch"] and cedar["notes"] == ["by the bridge"]
    assert [a["place"] for a in cedar["likely_shared_areas"]] == ["XX/NO/school-district", "XX/NO", "XX"]  # most specific first
    reuse = {s["id"] for s in cedar["neighbour_sources_to_check"]}
    assert "xx-no-alder-harbour-times" in reuse      # a paper that already covers two towns
    assert "xx-no-alder-town-council" in reuse       # a portal pattern worth looking up for the new town
    assert "xx-no-alder-farm-stand" not in reuse     # the town's own farm stand does not transfer
    assert [r["name"] for r in reg.frontier("XX/NO/birch")] == ["Cedar"]


def test_frontier_drops_places_that_have_since_been_mapped(reg):
    reg.places["XX/NO/alder"]["adjacent_unmapped"] = [{"name": "Birch", "wikidata": "Q9"}]
    reg.places["XX/NO/birch"]["identifiers"] = {"wikidata": "Q9"}
    assert reg.frontier() == []


def test_gaps(reg):
    g = reg.gaps("XX/NO/birch")
    assert g["has"] == {"library": 1, "newspaper": 1} and g["sources"] == 2
    assert "government" in g["missing_core_types"] and "library" not in g["missing_core_types"]
    assert {"meetings", "farm-market"} <= set(g["neighbours_have"])
    assert g["neighbours_have"]["meetings"][0]["place"] == "XX/NO/alder"
    assert g["area_sources_reaching_it"] == 2
