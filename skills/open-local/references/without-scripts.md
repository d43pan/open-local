# Using Open Local without running scripts

Some agents can fetch web pages but cannot run a shell. The registry is a plain file, so
the skill still works by hand.

1. Fetch `https://raw.githubusercontent.com/d43pan/open-local/main/dist/registry.json`.
   It has `places` (keyed by id) and `sources` (a list).
2. Find the place: match the user's words against each place's `name`, `aliases` and
   `postal_codes`. If more than one matches, ask.
3. Collect its containing areas: follow `parents` upward, and add any place whose
   `covers` list includes the place or one of those areas.
4. Pick sources whose `coverage[].place` is the place (direct) or one of those areas
   (area). Skip sources with `status: retired`.
5. For each source, fetch its `endpoints` of kind `rss`, `atom`, `jsonfeed` or `ical` and
   keep items inside the time window. For sources with only `html` or `documents`
   endpoints, open the page.
6. Follow the same rules (facts.md) and the same answer shape (briefing.md), including the
   coverage report.

Also available: `dist/feeds.opml` (all feeds, for a feed reader), `dist/sources.csv` and
`dist/places.geojson`.

Be polite to the sites: one request at a time per site, obey robots.txt, and do not fetch
more than the question needs.
