"""The deterministic half of the evaluation suite: place resolution and source selection
for representative questions, against the real registry. See evals/README.md."""
import json

import pytest
from conftest import ROOT
from openlocal import registry

DOC = json.loads((ROOT / "evals" / "cases.json").read_text())
CASES = DOC["cases"]


@pytest.fixture(scope="module")
def real():
    return registry.Registry(registry.build())


def test_the_suite_covers_the_representative_questions():
    assert len(CASES) >= 8 and len(DOC["always"]) >= 4
    assert all(c["answer_must"] for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_case(real, case):
    if case["resolve"] is None:
        return  # nothing to resolve: the behaviour is "ask the user"
    found = real.resolve(case["resolve"].get("query"), postal=case["resolve"].get("postal"))
    if case["expect_place"] is None:
        assert found == [], "an unknown place must not resolve to something else"
        return
    assert [f["id"] for f in found] == [case["expect_place"]]
    got = {s["id"]: s for s in real.sources_for(case["expect_place"], types=case.get("types"),
                                                neighbors=case.get("neighbors", False), radius_km=case.get("radius_km"))}
    missing = [s for s in case["must_include"] if s not in got]
    assert not missing, f"expected sources not consulted: {missing}"
    wrong = [s for s in case["must_exclude"] if s in got]
    assert not wrong, f"sources that should not be consulted: {wrong}"
    for sid, rel in (case.get("relations") or {}).items():
        assert got[sid]["relation"] == rel


def test_every_source_named_in_a_case_exists(real):
    ids = {s["id"] for s in real.sources}
    named = {s for c in CASES for s in c.get("must_include", []) + c.get("must_exclude", [])}
    assert named <= ids, named - ids
