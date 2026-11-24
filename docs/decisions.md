# Architecture decisions

Short records of the choices that shape the project, with the reason for each. The
research behind them is in [research/ecosystem.md](research/ecosystem.md).

## 1. Three parts that each stand alone

**Decision.** The registry (data), the tools (Python) and the skill (instructions) are
separate. The registry is useful with no tools; the tools are useful with no agent.

**Why.** No open, geography-keyed registry of local sources was found in the ecosystem
research. Projects such as Communities News, CivicFM, Scoutpost and Civic Newsroom each
build a product on their own private source list. The shared map is the missing piece,
so it must not depend on our skill, or on any agent, to be worth contributing to.

## 2. Wider than news

**Decision.** The project is "Open Local", not "Open Local News". The registry lists any
public source of local fact: records, calendars, hours, menus, shows, notices, as well as
reporting. The skill reports facts with their origin.

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
searches, which the skill is told to describe as approximate.

## 6. YAML to edit, JSON to consume

**Decision.** One YAML file per place under `registry/`, validated by JSON Schema.
`dist/` holds generated JSON, OPML, CSV and GeoJSON, committed to the repository and
checked in CI to be up to date.

**Why.** YAML with one file per place is what a non-developer can edit in the GitHub web
page and what makes pull requests readable and ownership (CODEOWNERS) per place possible.
Committing `dist/` means consumers and installed skills fetch static files from a
stable address with no build step and no server. (Since 0.2 the skill fetches an index
and one file per place rather than the whole registry; see 16.)

## 7. Standard library only at run time

**Decision.** The tools an agent runs need only Python's standard library. PyYAML and
jsonschema are needed only to validate and rebuild (maintainers and CI).

**Why.** Skills run inside many different agents and sandboxes; a `pip install` is often
impossible. The cost is hand-written feed and iCalendar parsing, kept small and tested.

## 8. One skill, in `skills/open-local/`

**Decision.** A single skill, `skills/open-local`. Its SKILL.md covers asking about a
place and routes to two reference files for the other jobs: `references/build.md` (map a
place and send it back) and `references/expand.md` (grow to the next towns over). The
tools live in the skill's `scripts/`. A skill
installed on its own fetches `dist/index.json` and the file for the place asked about,
cached for a day and revalidated by ETag.

**Why.** The Agent Skills specification requires the skill name to match its folder, the
Claude apps want a ZIP of one skill folder, and installers such as `npx skills add`
discover `skills/*`. A root-level SKILL.md would drag the whole repository into every
agent's skill folder. One skill rather than several because there should be one thing to install and one name
to remember; an early version split the jobs into three skills and that was more to
explain than it was worth. The format's progressive disclosure does the separating: the
mapping and expanding instructions cost nothing until someone asks for them.

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

## 15. Growth is outward, one town at a time, from a recorded frontier

**Decision.** A place may list `adjacent_unmapped` neighbours. `frontier` ranks them by
how many mapped places border each, and the skill's expanding workflow (`references/expand.md`) maps one at a
time by reusing regional sources, per-town sections and portal patterns already in the
registry before searching for anything new.

**Why.** The second town costs a fraction of the first, because the state portal, the
weekly paper and the regional newsrooms are already known. Growing from an edge also
makes "near me" answers better for people already covered, and keeps each pull request
small enough for a local to review. Adjacency is recorded by people, not computed from
coordinates, because water and borders make nearby places strangers.

## 12. What we reuse instead of building

- **Feeds and calendars:** RSS, Atom, JSON Feed, iCalendar, with standard autodiscovery.
  **Subscriptions:** OPML.
- **Place ids:** ISO 3166, Wikidata, Open Civic Data.
- **State and provincial legislatures:** left to Open States; this registry is about the
  local level.
- **Meeting transcripts and search:** left to existing projects (Council Data Project,
  Documenters, CivicFM and others); the registry points to where records are published.
- **Skill format and installers:** the Agent Skills specification and the tools around it.

## 16. One file per place, so nobody downloads the country

**Decision.** `build` also writes `dist/index.json` (every place, only what finding it
needs) and `dist/places/<id>.json` (a place, the areas above it, its neighbours, every
place within 50 km, and the sources covering any of them). The installed skill fetches
the index and one place file; `dist/registry.json` stays for bulk users. Still static
files on GitHub: no server (see "Not planned" in the roadmap).

**Why.** The skill never put other towns into an agent's context, but it did download
every town daily, and a national registry would pass the 50 MB fetch cap. A place file
answers exactly as the whole registry would for that place, neighbours and radii up to
50 km included; a test checks this for every place. Per-place files repeat state and
national sources; that costs disk, not context. Shard the index by country or state once
it passes a few megabytes.

## 17. Output is budgeted, and area-wide items must name the place

**Decision.** `recent` lists items from area-wide sources (county, state, region) only if
they name the place, and says how many it left out; `--all-area` lists everything. It
caps items per feed (15 by default), and `--brief` drops summaries and per-feed detail.
The skill starts with `--brief`. Target: a typical brief answer under about 15 KB.

**Why.** Tool output is what fills an agent's context. A week of Little Compton was 101 KB
and 104 items, about 80 of them statewide stories that never mention the town; every new
area source made every town noisier. The same week is now 13 KB brief, 35 KB full, with
the same 20 local items.

## 18. Data and skill are versioned separately

**Decision.** Published data carries `schema` (major version), `skill_version` (the newest
skill when it was built) and `data_version` (a content fingerprint). The skill refuses a
newer schema major with an update message, passes on a notice when a newer skill exists,
and reports the versions it used in every answer's coverage block (`run.py --version`).

**Why.** Registry fixes reach everyone within a day; skill fixes reach only people who
reinstall. Without this, the first breaking change would be silently misread.

## 19. "A person must open this" is first-class

**Decision.** An endpoint (or a whole source, under `access`) can be marked
`agent_readable: false` with a `blocked_by` reason. The tools never fetch it; `recent`
lists it under `coverage.needs_a_person`, and a robots.txt refusal found at run time goes
there too, not under `failed`. The weekly check skips marked endpoints.

**Why.** The Little Compton town calendar is a Google Calendar whose robots.txt forbids
tools. Reported as a failure, it looked broken; it is not broken, it needs a person.

## 20. Places are seeded from national gazetteers; sources are added by people

**Decision.** `run.py seed us-census` drafts place files (id, name, county, centre point,
Census GEOID) from the Census Gazetteer for one state, marked `provenance.method: import`.
It never changes a place that exists. Seeded places have no sources; `where` says so
(`sources_of_its_own: 0`) and the skill tells the person only area-wide sources reach it.
Rhode Island is seeded as the first test.

**Why.** Contributors should add what they know (sources), never hand-type coordinates
or identifiers. Keeping seeded places in the index lets `where` say "known place, nothing
mapped yet" instead of "not in the registry". Wikidata and Open Civic Data ids for towns
are a later join; county OCD ids follow a documented pattern and are filled in now.

## 21. Checks rotate, shard by host, and are recorded

**Decision.** The weekly availability check takes one of four rotation groups (by source
id), split into parallel shards by host so one site's requests stay in one job. Results
go to `dist/checks/<home>.json`, committed by the job and read by the skill
(`last_checked`), and problems go to one issue per area, naming maintainers from
`.github/CODEOWNERS`. Pull requests show warnings only for the files they change; errors
always cover the whole registry, and a nightly run shows every warning.

**Why.** At ten sources a town, a national registry is about 300,000 addresses, more
than one job can load in a week while waiting politely between requests to each site.
`dist/checks/` is kept apart from what `build` writes, so contributors' pull requests
never conflict with the weekly job.
