# Reusing what the registry already knows

Before searching the web for a new town, look at what its mapped neighbours taught the
registry. `run.py frontier` gives `neighbour_sources_to_check` and
`likely_shared_areas`; `run.py sources <neighbour> --brief` shows the full list.

## Three kinds of reuse

### 1. The same source already covers this town

Regional papers, tourism bodies, watershed groups, bus agencies, chambers of commerce.

- Open the source and confirm it carries the new town: a town section, a service-area
  statement, or items about the town in recent months.
- If it does, add `{place: <new town>, level: …}` to that entry's `coverage`. Do not add a
  second entry for the same publisher and the same address.
- If the source is filed under a county, state or region that contains the new town, it
  already reaches the town. Do nothing.
- If a cluster of towns keeps sharing sources, consider one area (`kind: custom` or
  `district`, with `covers:`) and move the shared sources there. Propose that in the pull
  request rather than doing it silently; it changes other towns' files.

### 2. The same publisher has a separate page or feed per town

Weekly paper groups with town sections, a state site with one page per municipality,
a school union with a page per school.

- Load the publisher's page for the new town. Run `run.py discover` on it: the feed
  address often follows the neighbour's pattern, but only what loads gets listed.
- Create a new entry for this town's section, filed under the new town, with the
  neighbour's entry as a model for type and classification.
- Set `coverage` to what the section actually covers. Town sections of one paper often
  carry each other's stories; the tools group duplicates, so that is fine.

### 3. The same platform or portal, a different account

State open-meetings portals, permit systems, agenda hosts, town website vendors.

- Note the neighbour's `platform` and the shape of its endpoints.
- Go to the portal's own search or directory and find the new town's bodies there. Copy
  the addresses the portal gives you. Entity numbers and account names are not guessable,
  and a guessed address that happens to load may belong to another town.
- For each public body the neighbour lists (council, planning, zoning, school committee),
  look for the new town's equivalent. Names differ: select board, board of selectmen,
  city council, town meeting, board of aldermen.
- Carry over the neighbour's useful notes about the platform (for example, which feed
  types are worth listing and which are too large), after confirming they hold.

## Across a border

A neighbour in another state, province or country shares fewer sources than it seems.

- Public-notice sites, open-meetings portals and state newsrooms stop at the line.
- The local word for things changes (town council or select board; county government or
  none), and so does where records are filed.
- Regional papers, tourism names and watersheds often do cross. File those under a
  cross-border area, as the registry does for regions that span a state line.

## What does not transfer

- Community organisations, churches, farms, galleries, restaurants, the library: these
  are the town's own. Find them with the checklist and the person you are working with.
- Paywall status, publication frequency and notes about dormant feeds: read them from the
  new source.
- `status` and `verified`: every entry starts unverified, however familiar it looks.
