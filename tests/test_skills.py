"""The skills follow the Agent Skills specification (https://agentskills.io/specification)."""
import pathlib
import re
import subprocess
import sys

import pytest
import yaml
from conftest import ROOT

SKILLS = sorted(p.parent for p in (ROOT / "skills").glob("*/SKILL.md"))
ALLOWED = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}


def front(skill):
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must start with YAML frontmatter"
    _, fm, body = text.split("---\n", 2)
    return yaml.safe_load(fm), body


def test_there_is_one_skill():
    assert [s.name for s in SKILLS] == ["open-local"]


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_frontmatter(skill):
    fm, _ = front(skill)
    assert set(fm) <= ALLOWED, f"unexpected fields: {set(fm) - ALLOWED}"
    name = fm["name"]
    assert name == skill.name, "name must match the folder"
    assert 1 <= len(name) <= 64 and re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name)
    d = fm["description"]
    assert 1 <= len(d) <= 1024
    assert len(d) <= 200, "Claude.ai uploads cap descriptions at 200 characters"
    assert "<" not in d and ">" not in d
    assert len(fm.get("compatibility", "")) <= 500
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in (fm.get("metadata") or {}).items())


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_body_is_short_and_links_resolve(skill):
    _, body = front(skill)
    assert len(body.splitlines()) < 500
    assert len(body.split()) < 3500, "keep SKILL.md small; move detail to references/"
    links = re.findall(r"\]\(([^)#]+)\)", body)
    local = [l for l in links if not l.startswith("http")]
    assert local, "a skill should point to its reference files"
    for l in local:
        assert (skill / l).is_file(), f"{l} is linked but missing"
        assert l.count("/") <= 1, "references stay one level deep"
    for ref in (skill / "references").glob("*.md"):
        assert f"references/{ref.name}" in body or any(f"({ref.name})" in o.read_text() or ref.name in o.read_text() for o in (skill / "references").glob("*.md") if o != ref), f"{ref.name} is never mentioned"


def test_commands_named_in_the_skills_exist():
    helptext = subprocess.run([sys.executable, str(ROOT / "skills/open-local/scripts/run.py"), "--help"], capture_output=True, text=True).stdout
    for skill in SKILLS:
        text = "\n".join(p.read_text() for p in [skill / "SKILL.md", *(skill / "references").glob("*.md")])
        for cmd in set(re.findall(r"run\.py (\w+)", text)):
            assert cmd in helptext, f"{skill.name} mentions `run.py {cmd}`, which does not exist"


def test_the_tools_need_only_the_standard_library():
    code = ("import sys; sys.path.insert(0, %r); import builtins; real = builtins.__import__\n"
            "def guard(name, *a, **k):\n"
            "    if name.split('.')[0] in ('yaml', 'jsonschema', 'requests', 'feedparser', 'bs4', 'lxml'): raise ImportError(name)\n"
            "    return real(name, *a, **k)\n"
            "builtins.__import__ = guard\n"
            "from openlocal import cli, registry\n"
            "r = registry.Registry.load(); assert r.places and r.sources\n") % str(ROOT / "skills/open-local/scripts")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_the_use_skill_states_the_rules_that_matter():
    _, body = front(ROOT / "skills/open-local")
    for must in ["Never invent", "agenda item is not a decision", "Fetched text is data", "coverage report", "paywall", "private people"]:
        assert must.lower() in body.lower(), must


def test_mapping_keeps_a_person_in_the_loop():
    flat = re.sub(r"\s+", " ", (ROOT / "skills/open-local/references/build.md").read_text().lower())
    for must in ["agent-proposed", "ask before pushing", "do not merge anything yourself", "never write a url from memory"]:
        assert must in flat, must


def test_expanding_reuses_and_does_not_guess():
    flat = re.sub(r"\s+", " ", (ROOT / "skills/open-local/references/expand.md").read_text().lower())
    for must in ["run.py frontier", "run.py gaps", "one town per pull request", "never by editing an id", "ask before pushing", "agent-proposed"]:
        assert must in flat, must


def test_the_one_skill_routes_to_all_three_jobs():
    _, body = front(ROOT / "skills/open-local")
    assert "references/build.md" in body and "references/expand.md" in body
