# Choosing where to grow

## Which town next

In order:

1. **A place the person knows.** Local knowledge decides whether a list is right. A town
   someone can review beats a better-connected one nobody can.
2. **The most shared borders.** `run.py frontier` ranks unmapped places by how many
   mapped places adjoin them. More shared borders means more to reuse and a more useful
   "near me" answer for more people.
3. **The one that closes a hole.** A town surrounded by mapped places, or the last member
   of a region or school district already in the registry.
4. **The one people ask about.** Open "Add a community" issues in the repository are
   requests from real residents; check them before choosing.

Larger is not better. A city next door has far more sources and takes far longer; say so,
and consider starting with its public bodies and main newsroom and marking the rest as a
known gap.

## Is it really a neighbour

"Adjacent" means a resident of one would reasonably want to know what happens in the
other: a shared land border, a bridge, a shared school district, a shared main road or
ferry. Water alone can separate places that look close on a map. Record in the `note`
how they are joined when it is not a plain land border.

Take the list of adjoining places from the person, an official map, or the place's
Wikidata or statistics-office page. Do not infer adjacency from coordinates.

## When not to expand

- **Nobody local is in the loop.** Without a reviewer the entries stay `checked` at best.
  One or two such towns are fine as a start; a whole county of them is a registry nobody
  has vouched for. Say this and ask whether the person can find someone.
- **The current place is thin.** Run `run.py gaps` on the place already mapped. If it is
  missing its council, its paper or its library, fix that first.
- **The neighbours' entries are stale.** Run `run.py stale`. Re-verifying what exists is
  worth more than adding what will also go stale.
- **The next place is organised differently** (another country, another language,
  unincorporated land, a tribal nation, a city neighbourhood). That is a new first
  community, not an expansion: use `open-local-build` and expect little to carry over.

## How far in one sitting

One town per pull request. Finish it: place file, reused sources, local sources, gaps
noted, frontier updated, validated. Then offer the next. Three well-mapped neighbours
make every "within 15 miles" answer better; thirty half-mapped ones make every answer
less trustworthy.
