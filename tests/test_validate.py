import datetime as dt
import shutil

import pytest
import yaml
from conftest import FIX
from openlocal import registry, validate

TODAY = dt.date(2026, 11, 24)


def test_the_fixture_registry_is_valid():
    errors, warnings = validate.validate(FIX / "registry", TODAY)
    assert errors == []
    assert any("no endpoints" in w for w in warnings)


def test_the_real_registry_is_valid():
    errors, _ = validate.validate()
    assert errors == []


@pytest.fixture
def broken(tmp_path):
    """A copy of the fixture registry with one change applied; returns the errors."""
    def run(path, change, new_path=None):
        root = tmp_path / "registry"
        if root.exists():
            shutil.rmtree(root)
        shutil.copytree(FIX / "registry", root)
        f = root / path
        doc = yaml.safe_load(f.read_text())
        change(doc)
        if new_path:
            f.unlink()
            f = root / new_path
            f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(yaml.safe_dump(doc))
        return validate.validate(root, TODAY)[0]
    return run


A = "XX/NO/alder.yaml"


@pytest.mark.parametrize("change, expect", [
    (lambda d: d["sources"][0].update(id="xx-no-alder-harbour-times"), "duplicate source id"),
    (lambda d: d["sources"][0].update(id="town-council"), "id must start with xx-no-alder-"),
    (lambda d: d["sources"][0].update(id="XX_Bad Id"), "does not match"),
    (lambda d: d["sources"][1]["coverage"].append({"place": "XX/NO/nowhere"}), "coverage refers to XX/NO/nowhere"),
    (lambda d: d["place"].update(parents=["XX/NO/missing"]), "parents refers to XX/NO/missing"),
    (lambda d: d["place"].update(centroid={"lat": -33.9, "lon": 151.2}), "check the coordinates"),
    (lambda d: d["place"].update(centroid={"lat": 141.5, "lon": -71.1}), "greater than the maximum"),
    (lambda d: d["sources"][0].update(url="http://192.168.1.10/council"), "refused"),
    (lambda d: d["sources"][0].update(url="ftp://alder.example.org/"), "does not match"),
    (lambda d: d["sources"][0]["endpoints"].append({"kind": "rss", "url": "http://localhost/feed"}), "refused"),
    (lambda d: d["sources"][0].update(discovered="2027-01-01"), "in the future"),
    (lambda d: d["sources"][0].update(verified="2025-01-01"), "verified before it was discovered"),
    (lambda d: d["sources"][0].update(discovered="2026-02-30"), "real calendar dates"),
    (lambda d: d["sources"][0].pop("verified"), "no verified date"),
    (lambda d: d["sources"][0].update(type="gossip"), "is not one of"),
    (lambda d: d["sources"][0].update(notes="ask the clerk, clerk@alder.example.org"), "email address"),
    (lambda d: d["sources"][0].update(provenance={"method": "agent-proposed"}), "named human reviewer"),
    (lambda d: d["sources"][0].update(surprise=True), "Additional properties"),
    (lambda d: d["place"].update(country="YY"), "must start with its country code"),
    (lambda d: d["place"].update(subdivision="YY-NO"), "is not in country"),
    (lambda d: d["place"].update(identifiers={"wikidata": "Q7"}, adjacent_unmapped=[{"name": "Itself", "wikidata": "Q7"}]), "move it to neighbors"),
    (lambda d: d["place"].update(adjacent_unmapped=[{"wikidata": "Q7"}]), "'name' is a required property"),
])
def test_bad_entries_are_caught(broken, change, expect):
    errors = broken(A, change)
    assert any(expect in e for e in errors), errors


def test_a_file_in_the_wrong_place_is_caught(broken):
    errors = broken(A, lambda d: None, new_path="XX/NO/elsewhere.yaml")
    assert any("must live at registry/XX/NO/alder.yaml" in e for e in errors)


def test_a_cycle_is_caught(broken):
    errors = broken("XX/NO.yaml", lambda d: d["place"].update(parents=["XX/NO/alder"]))
    assert any("own ancestor" in e for e in errors)


def test_url_normalisation():
    n = validate.normalize_url
    assert n("https://www.Example.org/a/") == n("http://example.org/a")
    assert n("https://example.org/a?x=1") != n("https://example.org/a")
