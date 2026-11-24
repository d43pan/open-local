# Places and scope

## Place ids

A place id is an ISO 3166-1 country code and then a path: `US`, `US/RI`,
`US/RI/little-compton`, `GB/ENG/hebden-bridge`. The path is a filing convention. What
contains what comes from each place's `parents` and `covers`, so the registry does not
assume the US pattern of country, state, county, town. A place can have several parents
(a county and a school district), and an area that is not a strict parent (a watershed,
a named region, a district spanning towns) lists the places it `covers`.

Each place may carry identifiers from open datasets (`wikidata`, `ocd_division`,
`us_census_geoid`, `geonames`, `osm_relation`) so it can be joined to other data.

## Resolving what the user said

`run.py where` accepts:

- a name, optionally qualified: `"Westport, MA"`, `"Westport, Massachusetts"`
- a place id: `US/MA/westport`
- a postal code: `--postal 02837`
- a point: `--lat 41.51 --lon -71.17` (nearest municipalities within 25 km)

More than one match means the name is ambiguous: ask. No match means the place is not in
the registry yet: say so.

Counties, states, countries and named regions are places too. Asking for a county returns
sources that cover the county as a whole; to include every town in it, query the towns.

## Relation: why a source is on the list

- `direct`: the source declares that it covers this place.
- `area`: it covers an area containing this place (county, state, district, region).
  Statewide sources produce a lot that is not about this town. Use an area item only when
  it mentions the place or plainly applies to everyone in the area (a statewide deadline,
  a regional road closure).
- `nearby`: only with `--neighbors` or `--radius-km`. It covers a neighbouring place.

`level` says how much of the source is about that place: `dedicated`, `regular` or
`occasional`.

## Coverage is not location

A weekly paper printed two towns away may be the main source for this town; a TV station
five miles off may never mention it. The registry records what a source **covers**
(`coverage`) separately from where its publisher **is** (`location`), and relevance is
decided by coverage alone. Do not add or drop a source because of its address.

## Radius

`--radius-km` finds places whose centre point is within that distance, then their
sources. Centres are single points, not boundaries, so a place at the edge can be missed
or included by a few kilometres; say "about". 15 miles is 24 km. Name the town for each
item when answering a radius question.

## How far to trust an entry

Each source has a `status`. `verified`: it loads and someone who knows the place has
reviewed it. `checked`: a tool loaded it on the `verified` date, and no local person has
reviewed it yet. `unverified` and `broken` sources are not fetched by `recent`; they
appear under `read_by_hand` with the reason. If most sources for a place are only
`checked`, say so in the coverage report.
