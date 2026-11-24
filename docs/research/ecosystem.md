# Ecosystem research: Open Local

Researched 2026-11-24. Every claim carries a source URL. **NV** = not verified this session (page blocked, not fetched, or recalled from prior knowledge); treat NV items as leads, not facts.

## 1. Agent Skills specification

Source: <https://agentskills.io/specification>. Spec repo: <https://github.com/agentskills/agentskills> (Apache-2.0 per GitHub).

**Frontmatter** (YAML, then Markdown body):

| Field | Required | Constraint (quoted) |
| - | - | - |
| `name` | Yes | "Must be 1-64 characters"; "May only contain unicode lowercase alphanumeric characters (`a-z`, `0-9`) and hyphens (`-`)"; "Must not start or end with a hyphen"; "Must not contain consecutive hyphens (`--`)"; "**Must match the parent directory name**" |
| `description` | Yes | "Must be 1-1024 characters"; "Should describe both what the skill does and when to use it" |
| `license` | No | "License name or reference to a bundled license file" |
| `compatibility` | No | "Must be 1-500 characters if provided" |
| `metadata` | No | "A map from string keys to string values" |
| `allowed-tools` | No | "A space-separated string of tools that are pre-approved to run"; "Experimental" |

- Layout: `SKILL.md` (required) plus optional `scripts/`, `references/`, `assets/`. "Any additional files or directories" are allowed.
- Progressive disclosure: metadata "~100 tokens" loaded at startup; instructions "< 5000 tokens recommended"; "Keep your main `SKILL.md` under 500 lines." "Keep file references one level deep from `SKILL.md`"; use relative paths from the skill root.
- Stricter hosts: Claude.ai uploads and the Skills API accept only those six fields ("any other field there causes a hard error") <https://code.claude.com/docs/en/skills>; Claude's help centre gives a **200-character** description maximum for uploaded skills <https://support.claude.com/en/articles/12512198-how-to-create-custom-skills>. Claude Code itself treats all fields as optional and truncates description + `when_to_use` at 1,536 characters in listings (same docs page).
- **Validation:** `skills-ref validate ./my-skill` (spec). The reference library lives at <https://github.com/agentskills/agentskills/tree/main/skills-ref>; documented install is from a clone (`pip install -e .` or `uv sync`, then activate the venv). It is also on PyPI as `skills-ref` 0.1.1 <https://pypi.org/project/skills-ref/>, so `uvx --from skills-ref skills-ref validate skills/open-local` should work; **NV, the run was not executed here.** Other commands: `read-properties`, `to-prompt`. README warning: "intended for demonstration purposes only. It is not meant to be used in production." Its validator rejects unknown top-level fields and enforces the directory-name match (<https://github.com/agentskills/agentskills/blob/main/skills-ref/src/skills_ref/validator.py>).
- **Use:** keep frontmatter to the six spec fields, description under 200 characters if Claude.ai upload matters, and run `skills-ref validate` in CI.

## 2. Install paths and repo layout

| Agent | Where skills live | Install | Source |
| - | - | - | - |
| Claude Code | `~/.claude/skills/<name>/SKILL.md` (personal), `.claude/skills/<name>/SKILL.md` (project), `<plugin>/skills/<name>/SKILL.md` | copy, symlink, or plugin | <https://code.claude.com/docs/en/skills> |
| Claude.ai / apps | uploaded ZIP | Customize > Skills > "+" > Create skill > Upload a skill; needs code execution enabled. "The ZIP should contain the skill folder as its root (not a subfolder)"; a listed failure is "Skill folder name doesn't match the skill name" | <https://support.claude.com/en/articles/12512180-using-skills-in-claude>, <https://support.claude.com/en/articles/12512198-how-to-create-custom-skills> |
| OpenAI Codex | `$CWD/.agents/skills` up to repo root, `$HOME/.agents/skills`, `/etc/codex/skills`, bundled system skills. Current docs do not list `~/.codex/skills`; third-party reports call `$CODEX_HOME/skills` a deprecated fallback (**NV**) | `$skill-installer <name>` or copy | <https://learn.chatgpt.com/docs/build-skills> (redirect target of developers.openai.com/codex/skills) |
| OpenClaw | precedence: `<workspace>/skills`, `<workspace>/.agents/skills`, `~/.agents/skills`, `<state-dir>/skills`; `--global` targets `~/.openclaw/skills`. "Follows the AgentSkills spec" | `openclaw skills install git:owner/repo@ref`, `skills-sh:owner/repo/slug`, `./path --as name`, or `@owner/<slug>` (ClawHub) | <https://docs.openclaw.ai/tools/skills> |
| Hermes Agent | `~/.hermes/skills/` (category folders allowed); agentskills.io compatible | `hermes skills install owner/repo/skills/<name>` or `skills-sh/<owner>/<repo>/<skill>` | <https://hermes-agent.nousresearch.com/docs/user-guide/features/skills> |
| Generic | `npx skills add <owner>/<repo>` (MIT, Node 22.20+). Flags: `-g`, `-a <agent>`, `-s/--skill <name>`, `-l`, `-y`, `--all`, `--copy`. Sources: shorthand, GitHub/GitLab URL, tree URL to a subdirectory, any git URL, local path. Writes to `.claude/skills/`, `.agents/skills/` (Codex and others), `~/.openclaw/skills/`, `~/.hermes/skills/` etc. | | <https://github.com/vercel-labs/skills>, `docs/commands.md`, `docs/agents.md` |

**Root vs subdirectory.** `npx skills` discovery searches "Root directory (if it contains `SKILL.md`)", then `skills/`, then agent folders, walking containers three levels deep (<https://github.com/vercel-labs/skills/blob/main/docs/creating-skills.md>). So a root `SKILL.md` is installable by `npx skills`, and by a plain `git clone` into `~/.claude/skills/open-local`. It is the weaker layout for this project:

- The spec requires `name` to equal the parent directory; a root skill only validates when the checkout directory is exactly `open-local` (forks, worktrees and CI checkouts break it).
- Claude.ai needs a ZIP whose single top folder is the skill; zipping a repo root ships the registry, tests and `.git` debris.
- Hermes' documented GitHub form is a path to a skill folder (`owner/repo/skills/<name>`); a root-skill install is NV for Hermes and OpenClaw.
- A root skill drags the whole registry into every agent's skill directory.

**Recommendation: `skills/open-local/SKILL.md`** with its own `scripts/`, `references/`, `assets/`; registry data and the Python package stay outside the skill folder (the skill fetches or bundles a compact index). Works with `npx skills add <owner>/open-local`, Hermes path installs, Codex `.agents/skills`, and a CI-built ZIP for Claude.ai.

## 3. Named projects (all four exist)

- **Communities News** <https://communities.news/>. Communities News, Inc.; platform for community newsrooms; first newsroom Alaska News (alaskanews.com). API at `https://alaskanews.com/api/v1` with OpenAPI at `/api/v1/openapi.json`; public modes (`digest`, `topics`, `tags`), `cn_` key for the rest; 300 reads/min. Ships a read-only skill, `local-news-api` (<https://communities.news/skills>, repo <https://github.com/news-community/news-skills>, MIT-0 per GitHub). No bulk open data found. alaskanews.com `robots.txt` carries `Content-Signal: ai-train=yes, search=yes, ai-input=yes` and `Disallow: /api/` (observed 2026-11-24). *Interop:* list alaskanews.com as a source with its API/OpenAPI URL in an `api` field; their skill is a model for a single-file stdlib Python helper.
- **CivicFM** <https://civic.fm/>. AI-produced weekly podcasts on public meetings, 17 California shows (statewide, LA, Bay Area, others); operator not named. Open read-only JSON API `https://civic.fm/api/v1` (no key, CORS `*`, OpenAPI at `/api/v1/openapi.json`, 60 calls/min), MCP server `https://civic.fm/mcp`, `llms.txt`, per-show podcast RSS (<https://civic.fm/agents>). Reuse licence not found (NV). *Interop:* register each show as a source (`type: podcast` + API) keyed to its city/county; their `/places` lookup is prior art for address-to-coverage.
- **Scoutpost** <https://scoutpost.ai/>. "AI-powered monitoring infrastructure for journalists": scheduled scouts (page, beat, civic, fleet) extracting deduplicated facts. REST API, MCP (`https://www.scoutpost.ai/mcp`), CLI, skills, `llms.txt`. Open source, AGPL-3.0: <https://github.com/buriedsignals/scoutpost-os>. No source registry or open data found. *Interop:* complementary. We are the catalogue of what to watch; Scoutpost is a watcher. Offer an export of registry URLs it can ingest; do not copy AGPL code into a permissively licensed repo. (Unrelated: scoutpost.io is a Reddit research tool.)
- **Civic Newsroom** <https://scottconverse.github.io/civic-newsroom>, repo <https://github.com/scottconverse/civic-newsroom> (MIT). Nine editorial prompts for turning city agendas, budgets and records into leads and drafts; companions `civic-transparency-toolkit` and `civic-scanner`. No registry or API. *Interop:* downstream consumer; link it as a workflow for what to do with sources. A different project, Nebraska Civic Newsroom <https://civicnewsroom.org/>, is a paid-documenter programme with no stated API.

## 4. Civic data and meetings

- **OCD division IDs.** Format `ocd-division/country:<country_code>(/<type>:<type_id>)*`; type: "lowercase UTF-8 letters, hyphen (-), and underscore (_)"; type_id adds numerals, period and tilde; spaces become underscores (<https://open-civic-data.readthedocs.io/en/latest/proposals/0002.html>). Canonical CSVs: <https://github.com/opencivicdata/ocd-division-ids> under `identifiers/country-<cc>.csv`; **CC0** (`LICENSE.md`); last push 2026-11-13. `country-us.csv` (about 195k rows) contains `ocd-division/country:us/state:ri/place:little_compton,Little Compton town` with `census_geoid` `place-4400542400`. *Reuse:* carry `ocd_id` for US and Canadian places and validate against the CSV; non-US coverage is thin (NV per country).
- **Open States.** API v3 at `https://v3.openstates.org/`, key via `X-API-KEY`; covers states, DC, Puerto Rico and "municipal governments for which we have limited support" (<https://docs.openstates.org/api-v3/>). Scrapers GPL-3.0 (<https://github.com/openstates/openstates-scrapers>); people data CC0 (<https://github.com/openstates/people>). Bulk-data terms NV. *Interop:* register it as a state-level source per `state:` division; do not mirror bills.
- **Legistar (Granicus).** `https://webapi.legistar.com/v1/{Client}/` with OData (`/events`, `/matters`, `$top`, `$skip`, `$filter`), 1,000-item cap, token only for some clients (<https://webapi.legistar.com/Home/Examples>). Scraper: <https://github.com/opencivicdata/python-legistar-scraper> (BSD-3). *Use:* a `platform: legistar` + `client` field lets utilities derive the API URL.
- **Councilmatic** <https://github.com/datamade/django-councilmatic> (MIT) sits on OCD/Legistar data. **CivicPlus, Granicus (non-Legistar), BoardDocs, PrimeGov:** proprietary portals, NV; <https://github.com/biglocalnews/civic-scraper> (Apache-2.0) downloads agendas and minutes from several. *Use:* a `platform` enum so per-platform adapters can be written once.
- **City Scrapers / Documenters.** <https://github.com/City-Bureau/city-scrapers> (MIT) standardises meetings; Documenters Network, run by City Bureau, lists 31 entries, seven hibernating (<https://www.documenters.org/>). No public API stated. *Interop:* their spiders are a per-agency URL inventory worth cross-referencing.
- **Council Data Project** <https://github.com/CouncilDataProject/cdp-backend>: open pipelines for council transcripts; licence shown as both MIT and MPL-2.0; last push 2026-02. Instance list NV.
- **LocalView.** 139,616 meeting videos with transcripts from 1,012 places (<https://www.nature.com/articles/s41597-023-02044-y>); Dataverse doi:10.7910/DVN/NJTBEM (<https://www.localview.net/>). Licence NV.
- **MeetingBank.** 1,366 council meetings from six US cities (<https://meetingbank.github.io/>). Licence NV.
- **CivicSearch** <https://civicsearch.org/>: meeting search, 547 US/Canadian cities, parent Datamuse, per <https://directory.civictech.guide/listing/civicsearch>. API NV. **citymeetings.nyc** <https://citymeetings.nyc/>: AI-segmented NYC Council meetings; no API stated.
- *Interop for all four:* list as sources of type `meeting-archive`; link, never copy.

## 5. Local-news directories and datasets

- **Project Oasis** <https://globalprojectoasis.org/about-the-study/us-ca/>: SembraMedia with Google News Initiative support; "more than 1,800 media outlets and news content creators"; directory at directory.globalprojectoasis.org. Footer "All Rights Reserved", no download or API stated. Do not bulk-copy.
- **LION Publishers** <https://www.lionpublishers.com/members/>: public member list, updated quarterly; "Copyright LION Publishers"; no API. Count NV.
- **INN**: 497 members, 524 outlets (<https://inn.org/wp-content/uploads/2026/04/INN_Impact-Report-2025_REL.pdf>, via search); directory page returned 403, terms NV.
- **Medill State of Local News** <https://localnewsinitiative.northwestern.edu/projects/state-of-local-news/>: 2026 report counts 238 news-desert counties (<https://www.niemanlab.org/2026/10/from-bad-to-worse-2026-is-shaping-up-to-be-a-super-el-nino-year-for-local-news/>). Site unreachable here (TLS error); data-access terms NV. Assume by request, not open.
- **Media Cloud** <https://www.mediacloud.org/media-cloud-directory>: directory of "over 25,000 media sources" (another page says 60,000; unresolved), collections for 100+ countries, with per-country "State & Local" collections (<https://www.mediacloud.org/blog/approaches-to-searching-by-place-in-media-cloud>). API via `mediacloud` PyPI client (<https://github.com/mediacloud/api-client>, Apache-2.0); default quota 4,000 requests/week (<https://mediacloud.org/documentation/faqs>). Redistribution terms NV. *Interop:* store `mediacloud_source_id` as an external ID; use it for discovery, with human-confirmed additions.
- **Chronicling America / US Newspaper Directory:** since 2025 "accessible exclusively via the loc.gov API" (<https://www.loc.gov/apis/additional-apis/chronicling-america-api/>). Directory endpoints, limits and rights NV. *Use:* `lccn` as an external ID for US newspapers.
- **Wikidata:** structured data "released into the public domain under Creative Commons Zero" (<https://www.wikidata.org/wiki/Wikidata:Licensing>). The only large CC0-compatible seed; newspaper coverage quality NV. *Use:* `wikidata` QID on every source that has one; seed by SPARQL, then verify URLs.
- **Other:** Civic Tech Field Guide lists 32 public-meeting projects (<https://civictech.guide/category/public-meetings>); `awesomelistsio/awesome-civic-tech` exists (via search, NV). No dedicated "awesome local news sources" list found. Muck Rack, Google News Initiative datasets, Brown/Columbia Local News Lab, "US News Deserts" (UNC, now Medill): NV, none known to publish open bulk data.

**Finding:** no open, machine-readable, geography-keyed registry of local sources was found. Existing directories are membership lists, research datasets or proprietary.

## 6. Standards (canonical spec URLs; not re-fetched unless noted)

- **RSS 2.0** <https://www.rssboard.org/rss-specification>, **Atom** <https://www.rfc-editor.org/rfc/rfc4287>, **JSON Feed 1.1** <https://www.jsonfeed.org/version/1.1/>: registry stores `feeds[] {url, format}`; utilities parse all three and send conditional GETs.
- **Autodiscovery** <https://www.rssboard.org/rss-autodiscovery>: a utility finds `<link rel="alternate" type="application/rss+xml">` from a homepage and proposes feeds for a PR.
- **OPML 2.0** <http://opml.org/spec2.opml>: export any place's feeds as OPML for feed readers.
- **iCalendar** <https://www.rfc-editor.org/rfc/rfc5545>: `calendars[]` holds `.ics` URLs for meetings and events.
- **WebSub** <https://www.w3.org/TR/websub/>: record a `hub` if advertised; polling stays the default.
- **Sitemaps** <https://www.sitemaps.org/protocol.html> and **news sitemaps** (verified: namespace `http://www.google.com/schemas/sitemap-news/0.9`, only articles "created in the last two days", up to 1,000 `news:news` tags; <https://developers.google.com/search/docs/crawling-indexing/sitemaps/news-sitemap>): fallback discovery for sites without feeds.
- **schema.org** <https://schema.org/NewsArticle>, <https://schema.org/Event>, <https://schema.org/NewsMediaOrganization>: parse JSON-LD for dates and events; borrow property names (`areaServed`, `sameAs`) for registry fields.
- **robots.txt, RFC 9309** <https://www.rfc-editor.org/rfc/rfc9309>: utilities must check it and send an identifying User-Agent.
- **llms.txt** <https://llmstxt.org/> (verified): community proposal, "not a formal standard"; H1, blockquote, H2 link lists. Record `llms_txt` when present; publish one for the registry site.
- **IETF AIPREF** <https://datatracker.ietf.org/wg/aipref/about/> (verified): active working group; `draft-ietf-aipref-vocab-08` and `draft-ietf-aipref-attach-05` are still drafts, no RFC. `Content-Signal` lines already appear in the wild (alaskanews.com). Utilities should read and surface these, not hard-code policy.

## 7. Geographic identifiers

| Identifier | Licence | Safe in a CC0 registry? | Source |
| - | - | - | - |
| Wikidata QID | CC0 | Yes | <https://www.wikidata.org/wiki/Wikidata:Licensing> |
| OCD division ID | CC0 | Yes | <https://github.com/opencivicdata/ocd-division-ids> |
| US Census GEOID / TIGER | "Copyright protection is not available for any work of the United States Government (Title 17 U.S.C., Section 105)"; "TIGER/Line" is a trademark; boundaries "for statistical ... purposes only" | Yes, IDs and geometry | <https://www2.census.gov/geo/pdfs/maps-data/data/tiger/tgrshp2024/TGRSHP2024_TechDoc_Ch1.pdf> |
| Natural Earth | public domain | Yes | <https://github.com/nvkelso/natural-earth-vector/blob/master/LICENSE.md> |
| ISO 3166-1/-2 codes | codes widely reused; ISO text copyrighted (NV) | Codes yes | <https://www.iso.org/iso-3166-country-codes.html> |
| GeoNames ID | CC BY, credit required | ID as a bare reference: yes. Copied names/coordinates: carry attribution, so not pure CC0 | <https://www.geonames.org/export/> |
| OSM relation ID | ODbL | ID as a link key: reasonable, see below. Geometries: **no** | below |
| Who's On First | format CC0; data mixed, "some sources require attribution", licence link "required"; repo last pushed 2024-03 | ID only | <https://github.com/whosonfirst-data/whosonfirst-data/blob/master/LICENSE.md> |
| Overture divisions / GERS | divisions theme ODbL (OSM-derived); GERS IDs are UUIDs | ID only; data no | <https://docs.overturemaps.org/attribution/>, <https://docs.overturemaps.org/gers/> |
| geoBoundaries | CC BY 4.0 | Link only | <https://www.geoboundaries.org/> |
| UN/LOCODE, UN M49 | mirrors claim PDDL; UNECE's own terms NV | NV | <https://datahub.io/core/un-locode> |
| Postal codes | US ZCTA is Census (public domain, as above); other countries NV, often not open | US only | |

**OSM and CC0.** ODbL: a "Derivative Database ... must continue to be licensed under the ODbL" (<https://osmfoundation.org/wiki/Licence/Licence_and_Legal_FAQ>). Copying OSM geometries, or systematically harvesting names/coordinates, into a CC0 registry is therefore out. The Collective Database Guideline says "a reference between non-OSM and OSM data can be by a database key" and treats such joins as "equivalent to a reference" (<https://osmfoundation.org/wiki/Licence/Community_Guidelines/Collective_Database_Guideline_Guideline>); the Geocoding Guideline calls individual results "insubstantial database extracts" unless aggregated into a substantial part of OSM. Reading: storing `osm_relation` as an optional pointer is defensible; this is a community guideline, not legal advice, and neither page names OSM IDs explicitly. OSM relation IDs are also not guaranteed stable (NV). Nominatim's public API allows "an absolute maximum of 1 request per second", requires an identifying User-Agent and caching, and forbids systematic queries (<https://operations.osmfoundation.org/policies/nominatim/>): fine for an end user's one-off lookup, not for building the registry.

**Recommendation.**

- Registry primary key: our own stable path slug, ISO 3166-based (`us/ri/little-compton`), so a place can exist before any external ID does.
- Primary external identifier worldwide: **Wikidata QID** (CC0, global, multilingual, links onward to GeoNames, OSM, FIPS).
- Also carry, where present: `ocd_id` (US/CA), `census_geoid` (US), ISO 3166-2 code; optional pointer-only `geonames`, `osm_relation`, `wof`, `gers`.
- Ship no boundary geometry. Resolve geometry at runtime from TIGER (US) or the user's chosen provider; at most a CC0 centroid from Wikidata.

## Opportunities for interoperability

- Emit OPML and iCalendar bundles per place, so the registry is useful without an agent.
- Carry `wikidata`, `ocd_id`, `census_geoid`, `lccn`, `mediacloud_source_id` so Wikidata, Open States, Chronicling America and Media Cloud join without fuzzy matching.
- `platform` + `client` fields (Legistar, CivicPlus, Granicus) let one adapter serve thousands of towns; Legistar's OData API needs no scraping.
- Register agent-ready APIs as first-class sources: CivicFM (open API + MCP), Communities News / Alaska News (OpenAPI), Open States.
- Export registry URLs in a form Scoutpost and City Scrapers can ingest; import City Scrapers' agency URLs as candidates.
- Publish `llms.txt` and a static JSON index so any agent, not only skill hosts, can read the registry.
- Contribute missing newspaper and official-website statements back to Wikidata (CC0 both ways).

## Risks / things not to duplicate

- Do not rebuild meeting scrapers, transcription, or summarisation (City Scrapers, CDP, LocalView, CivicSearch, CivicFM, Scoutpost exist). The gap is the catalogue.
- Do not bulk-import Project Oasis, LION, INN, Medill or Media Cloud lists: none was found with an open licence. Use them for manual discovery only.
- Do not store OSM, Overture, geoBoundaries or WOF geometries or bulk attributes in a CC0 dataset.
- Do not copy AGPL (Scoutpost) or GPL (Open States scrapers) code into a permissive repo.
- Do not mint a new geographic ID scheme beyond a slug; lean on QID and OCD.
- Link rot is the main maintenance cost: plan a scheduled checker that respects robots.txt and AI-preference signals.
- Skill-host drift: Codex moved its user path to `~/.agents/skills`, and limits differ by host (1,024 vs 200 characters). Re-verify section 2 before each release.
- `skills-ref` is a demo-grade validator; pin its version in CI.
- AI-generated "local news" networks exist; the registry needs inclusion criteria and provenance fields so it does not launder them.
