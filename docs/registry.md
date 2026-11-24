# The registry, for people who want the data

You do not need the skill or the tools to use this. The registry is a set of plain
files in the public domain (CC0).

## Get it

| File | What | For |
|---|---|---|
| [`dist/registry.json`](../dist/registry.json) | Every place and source in one document | Programs |
| [`dist/index.json`](../dist/index.json) | Every place with only what finding it needs (names, aliases, postal codes, parents, centre) and how many sources it has | Looking a place up |
| `dist/places/<place id>.json` | One place, the areas above it, its neighbours, every place within 50 km, and the sources that cover any of them | Answering about one place |
| `dist/checks/<place id>.json` | The latest scheduled check of each source whose home is that place (written by the weekly job, not by `build`) | How fresh an entry is |
| [`dist/feeds.opml`](../dist/feeds.opml) | Every RSS, Atom and JSON Feed, grouped by place | Feed readers |
| [`dist/sources.csv`](../dist/sources.csv) | One row per source | Spreadsheets |
| [`dist/places.geojson`](../dist/places.geojson) | Places as points with source counts | Maps |
| [`registry/`](../registry) | The YAML the above are built from | Editing |
| [`schemas/registry-file.schema.json`](../schemas/registry-file.schema.json) | JSON Schema (2020-12) for a registry file | Validation |

Stable address for the built file:
`https://raw.githubusercontent.com/d43pan/open-local/main/dist/registry.json`

OPML for one place: `python3 skills/open-local/scripts/run.py export opml --place US/RI/little-compton`

## Shape

```
registry.json
├── schema         "open-local/registry/1"
├── license        "CC0-1.0"
├── skill_version  the newest skill release when this was built, e.g. "0.2.0"
├── data_version   a fingerprint of the content, e.g. "56d22db7c2fb"
├── places         { "<place id>": {…} }
└── sources        [ {…}, … ]
```

`index.json` and `places/<id>.json` have the same top-level keys, plus `partial: true`;
a place file also names its `place` and the `radius_km` it carries. An installed skill
fetches the index and one place file, revalidating each with its ETag after a day, and
never downloads the whole registry unless asked for a radius wider than 50 km.

### Place

| Field | Meaning |
|---|---|
| `id` | Country code then a path: `US/RI/little-compton`. Stable. |
| `name`, `aliases` | What people call it. |
| `kind` | Neutral class: `country`, `region`, `county`, `municipality`, `neighbourhood`, `district`, `natural`, `custom`. |
| `local_kind` | The local word: town, parish, comune, ward. |
| `country`, `subdivision` | ISO 3166-1 alpha-2 and ISO 3166-2. |
| `parents` | Areas that contain it. Any number. |
| `covers` | For areas that cut across the hierarchy: the places inside. |
| `neighbors` | Adjacent places. |
| `adjacent_unmapped` | Adjacent places not in the registry yet (`name`, `wikidata`, `note`): the frontier. |
| `centroid` | `{lat, lon}`, WGS 84. A point, not a boundary. |
| `postal_codes`, `languages`, `timezone` | As named. |
| `identifiers` | `wikidata`, `ocd_division`, `us_census_geoid`, `geonames`, `osm_relation`, and others as strings. |

To find everything that contains a place, follow `parents` upward and add any place whose
`covers` includes it or one of its ancestors.

### Source

| Field | Meaning |
|---|---|
| `id` | Stable, unique, never reused. Begins with the home place id in lower case. |
| `name`, `description`, `publisher`, `url` | What it is and who runs it. |
| `type` | One of the types in the schema (`government`, `meetings`, `newspaper`, `library`, `farm-market`, `arts-culture`, …). |
| `classification` | `primary` (first-hand records, announcements or original reporting), `secondary` (lists or repeats others), `mixed`. |
| `home` | The place whose file it is in (added at build time). |
| `coverage` | `[{place, level, note}]`: what it covers. `level` is `dedicated`, `regular` or `occasional`. |
| `jurisdiction` | For a public body, the place it governs. |
| `location` | Where the publisher is. Never used to decide relevance. |
| `endpoints` | `[{kind, url, title, note, agent_readable, blocked_by}]`. `kind`: `rss`, `atom`, `jsonfeed`, `ical`, `api`, `sitemap`, `html`, `documents`, `video`, `podcast`. `agent_readable: false` with `blocked_by` (`robots-txt`, `terms`, `login`, `javascript-only`, `other`) marks an address tools must not or cannot read, so a person has to open it. |
| `languages`, `topics`, `frequency`, `platform` | As named. Languages are BCP 47 tags. |
| `access` | `paywall` (`none`, `metered`, `hard`, `registration`, `unknown`), the source's own `license` if it states one, known `restrictions`, and `agent_readable: false` with `blocked_by` when no part of the source may be read by tools. |
| `discovered`, `verified` | Dates (YYYY-MM-DD): first added, last confirmed to load. |
| `status` | `verified` (loads, and reviewed by someone who knows the place), `checked` (loaded by a tool, not yet reviewed locally), `unverified`, `broken`, `stale`, `retired`. |
| `provenance` | `added_by` (a public handle), `method` (`human`, `agent-proposed`, `import`), `evidence`. |

## Which sources apply to a place

A source applies to place P if any `coverage[].place` is P (direct) or is an area that
contains P (area-wide). `python3 skills/open-local/scripts/run.py sources <place>` does
this, or see `sources_for` in
[`registry.py`](../skills/open-local/scripts/openlocal/registry.py), about forty lines.

## What the data is and is not

- It describes sources. It contains none of their content, and the CC0 dedication covers
  only these descriptions. What a source publishes remains its publisher's.
- `verified` and `checked` mean the addresses loaded on the `verified` date. It is not a judgement of accuracy
  or quality.
- `paywall` and `restrictions` are best-effort notes. Check a source's own terms before
  building on its content.
- Identifiers from other datasets are pointers. Geometry is deliberately not included:
  the common open boundary sets carry licences that do not fit a CC0 file.
- Coverage is uneven and always will be. A place with few sources listed may have many
  that nobody has added yet.

## Stability

The `schema` value changes only for breaking changes, which are announced in an issue
first and come with a migration. The skill refuses data with a newer `schema` than it
knows, with a message to update, rather than misreading it; when `skill_version` is newer
than the installed skill it keeps working and passes on a notice. New optional fields and new enum values can appear at
any time; ignore what you do not recognise. Source and place ids are permanent.
