# Writing a place file

One file per place: `registry/<place id>.yaml`. The id is the country code and a path,
for example `US/RI/little-compton`, `CA/NS/lunenburg`, `GB/ENG/hebden-bridge`,
`FR/BRE/douarnenez`. Use the ISO 3166-2 code for the first level below the country where
one exists, then a lower-case, hyphenated name. Ids never change once merged.

```yaml
place:
  id: US/RI/little-compton
  name: Little Compton
  kind: municipality          # country | region | county | municipality | neighbourhood | district | natural | custom
  local_kind: town            # the word used locally: town, parish, comune, ward, borough…
  country: US                 # ISO 3166-1 alpha-2
  subdivision: US-RI          # ISO 3166-2, if there is one
  aliases: [Sakonnet, Adamsville]   # other names people use, villages inside it
  parents: [US/RI/newport-county]   # areas that contain it; more than one is fine
  neighbors: [US/RI/tiverton, US/MA/westport]
  centroid: {lat: 41.51, lon: -71.17}
  postal_codes: ["02837"]
  languages: [en]
  timezone: America/New_York
  identifiers:
    wikidata: Q…
    ocd_division: ocd-division/country:us/state:ri/place:little_compton
    us_census_geoid: "…"
sources:
  - …
```

## Getting it right

- **Parents must exist.** If the county, state or country file is missing, add it too
  (a parent file can have no sources). Places with no parents are cut off from area-wide
  sources such as the state's newsrooms.
- **Hierarchy is whatever is true locally.** Do not invent a county where there is none.
  A place can sit directly under its country. A place can have two parents.
- **Areas that cut across** (a school district covering two towns, a watershed, a named
  region like "South Coast") are their own place with `kind: district`, `natural` or
  `custom` and a `covers:` list of the places inside. Sources filed there reach all of them.
- **Neighbours go both ways.** If A lists B, B should list A.
- **Record the frontier.** List adjoining places that have no file yet under
  `adjacent_unmapped` (a `name`, and the `wikidata` id if you can copy it). It tells the
  next contributor where to go, and the `open-local-expand` skill reads it.
- **Centroid:** a point roughly in the middle, to three decimal places. It powers "near me"
  and radius searches. Take it from the place's Wikidata item (coordinate location) or
  the national statistics office.
- **Identifiers:** copy them from the source, do not construct them.
  - `wikidata`: the Q-number on the place's page at wikidata.org. Works worldwide and is
    the main cross-reference.
  - `ocd_division`: from the Open Civic Data lists at
    github.com/opencivicdata/ocd-division-ids (where the country is covered).
  - `us_census_geoid`: from data.census.gov or the Census gazetteer files (US only).
  - `geonames`, `osm_relation`: optional pointers. Copy the id only, never geometry or
    other data from OpenStreetMap, whose licence does not fit a public-domain registry.
- **Postal codes** only where they are open data in that country and useful to residents.

## Sources

Fields and allowed values are defined in `schemas/registry-file.schema.json` and
explained in `docs/registry.md`. The fastest route is `run.py propose`, then edit.
A source's `id` starts with the place id in lower case with hyphens:
`us-ri-little-compton-brownell-library`.

File a source under the smallest place it is really about. A paper covering three towns
goes under the one it is most identified with and lists all three in `coverage`. A state
agency goes in the state's file and reaches every place inside it automatically.
