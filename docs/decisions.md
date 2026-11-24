# Architecture decisions

Short records of the choices that shape the project, with the reason for each. The
research behind them is in [research/ecosystem.md](research/ecosystem.md).

## 1. Three parts that each stand alone

**Decision.** The registry (data), the tools (Python) and the skills (instructions) are
separate. The registry is useful with no tools; the tools are useful with no agent.

**Why.** No open, geography-keyed registry of local sources was found in the ecosystem
research. Projects such as Communities News, CivicFM, Scoutpost and Civic Newsroom each
build a product on their own private source list. The shared map is the missing piece,
so it must not depend on our skill, or on any agent, to be worth contributing to.

## 2. Wider than news

**Decision.** The project is "Open Local", not "Open Local News". The registry lists any
public source of local fact: records, calendars, hours, menus, shows, notices, as well as
reporting. The skills report facts with their origin.

**Why.** What people ask about their town is mostly not news in the newspaper sense:
what is on, what is open, what was decided. And the label "news" invites an agent to
write like a newspaper, which is not the job.

## 3. Places are a graph, not a tree

**Decision.** A place id is `CC/…/slug`, but containment comes from `parents` (any
number) and `covers` (for areas that cut across), never from the path. `kind` is a small
neutral vocabulary; the local word goes in `local_kind`.

**Why.** Country, state, county, town is a US pattern. Elsewhere there may be no county
level, or parishes, or overlapping special districts. Even in the US, school districts,
watersheds and named regions cut across. A source filed under a school district must
reach both of its towns.

## 4. Coverage is declared, and separate from location

**Decision.** Each source lists the places it covers and how heavily. Relevance is
computed from that alone. The publisher's address is optional metadata.

**Why.** Distance from the newsroom is a poor guide to what a paper covers. A weekly two
towns away can be a town's main source.

## 5. Identifiers: our own slug, plus Wikidata as the cross-reference

**Decision.** The primary key is the registry's own place id. Each place may carry
`wikidata` (preferred, CC0, worldwide), `ocd_division`, national statistical codes, and
`geonames` / `osm_relation` as bare pointers. No geometry is stored; places have a
centre point.

**Why.** Wikidata ids are public domain and cover the world. Open Civic Data division ids
are CC0 and are what civic-tech tools in the US and Canada already use. OpenStreetMap
data is under the ODbL, whose share-alike terms do not fit a CC0 file, so we store at most
an id. Centre points keep the registry small and licence-clean at the cost of fuzzy radius
searches, which the skills are told to describe as approximate.

## 6. YAML to edit, JSON to consume

**Decision.** One YAML file per place under `registry/`, validated by JSON Schema.
`dist/` holds generated JSON, OPML, CSV and GeoJSON, committed to the repository and
checked in CI to be up to date.

**Why.** YAML with one file per place is what a non-developer can edit in the GitHub web
page and what makes pull requests readable and ownership (CODEOWNERS) per place possible.
Committing `dist/` means consumers and installed skills fetch one static file from a
stable address with no build step and no server.

## 7. Standard library only at run time

**Decision.** The tools an agent runs need only Python's standard library. PyYAML and
jsonschema are needed only to validate and rebuild (maintainers and CI).

**Why.** Skills run inside many different agents and sandboxes; a `pip install` is often
impossible. The cost is hand-written feed and iCalendar parsing, kept small and tested.

## 8. Skills in `skills/<name>/`, two of them

**Decision.** `skills/open-local` (ask about a place) and `skills/open-local-build` (map
a place and send it back). The tools live inside the first skill's `scripts/`. A skill
installed on its own downloads `dist/registry.json` and caches it for a day.

**Why.** The Agent Skills specification requires the skill name to match its folder, the
Claude apps want a ZIP of one skill folder, and installers such as `npx skills add`
discover `skills/*`. A root-level SKILL.md would drag the whole repository into every
agent's skill folder. Two skills because asking and contributing are different jobs with
different instructions; one of them being about contribution makes giving back a
first-class path rather than a paragraph at the end.

## 9. Agents propose, people decide

**Decision.** `propose` prints a draft and never edits the registry. Agent-drafted
entries are marked `agent-proposed`, cannot be marked verified without a named human
reviewer, and are merged only through ordinary reviewed pull requests.

**Why.** An open registry that agents could write to directly would fill with plausible
invented sources. The value of the map is that someone checked.

## 10. Network checks are scheduled, not part of pull requests

**Decision.** Pull request checks are deterministic and offline. A weekly job loads every
source and opens an issue for failures.

**Why.** A town website having a bad afternoon should not block a contributor, and
flaky checks teach people to ignore red marks.

## 11. Everything fetched is hostile

**Decision.** One fetch function with SSRF protection, redirect checking, size and time
limits, robots.txt and rate limiting; feeds parsed without entity expansion; tool output
and skills both state that fetched text is data, not instructions.

**Why.** Anyone can propose a URL, and whatever a URL returns is read by an agent that
may have other tools. See [SECURITY.md](../SECURITY.md).

## 13. robots.txt is obeyed even for feeds and calendars

**Decision.** The tools refuse any address a site's robots.txt disallows, including
subscription addresses such as YouTube channel feeds and public Google Calendar files.
Those endpoints stay in the registry with a note, and `recent` reports them as not read.

**Why.** The project promises to respect robots.txt, and a rule with exceptions the
project grants itself is not a rule. The cost is real: in Little Compton the town's
calendar and meeting videos are both behind such rules, so an agent must open them
itself. There is a fair argument that fetching a feed a publisher offers for subscription
is what a feed reader does, not crawling. This is the decision most worth revisiting, in
the open, with publishers in the conversation.

## 14. "Checked" is not "verified"

**Decision.** `checked` means a tool loaded the addresses on the given date. `verified`
means that and a person who knows the place has reviewed the entry. The first community
was seeded by an AI research agent and is `checked`.

**Why.** Loading is not the same as being right. Whether a site is really the town's
paper of record, or a calendar is the one people use, is local knowledge. Marking the
seed data `verified` would have claimed a review that has not happened.

## 12. What we reuse instead of building

- **Feeds and calendars:** RSS, Atom, JSON Feed, iCalendar, with standard autodiscovery.
  **Subscriptions:** OPML.
- **Place ids:** ISO 3166, Wikidata, Open Civic Data.
- **State and provincial legislatures:** left to Open States; this registry is about the
  local level.
- **Meeting transcripts and search:** left to existing projects (Council Data Project,
  Documenters, CivicFM and others); the registry points to where records are published.
- **Skill format and installers:** the Agent Skills specification and the tools around it.
