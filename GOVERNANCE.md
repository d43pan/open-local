# Governance

Open Local is a commons: a shared map that is only as good as the local people who keep
it. Governance exists to keep it accurate, open and hard to capture.

## Where things stand

The project is new. Today it has one project maintainer (the repository owner) and no
community maintainers yet. This document describes how it is meant to work as people
join, and the roadmap has the steps for getting there. Nothing here is ceremonial: if a
rule below is not being followed, open an issue.

## Roles

- **Contributors** propose sources, places and fixes. Anyone.
- **Community maintainers** look after one or more places they know: they review changes
  for those places and answer questions about them. Local journalists, librarians, clerks,
  members of civic organisations and long-time residents are the people this role is for.
  No coding needed; review can be done in the GitHub web page.
- **Project maintainers** look after the schema, tools, skills and rules, merge pull
  requests, and step in when a place has no maintainer.

## Becoming a community maintainer

1. Make two or three accepted contributions for a place (issues count).
2. Ask in an issue, or be invited. Say what your connection to the place is. A connection
   is not a conflict; an undisclosed one is. If you work for a listed source, say so.
3. A project maintainer adds you to `.github/CODEOWNERS` for that place's files, so
   GitHub asks you to review changes to them.

Maintainers who are inactive for a year are moved to emeritus; they can return by asking.

## How decisions are made

- **Registry entries:** by the acceptance rules. One approving review from a maintainer
  (the place's, where there is one), who is not the author. Disagreements are settled in
  the issue, by the rules, with reasons written down.
- **Rules, schema and governance:** proposed in an issue, open for at least two weeks,
  decided by consensus of project maintainers, recorded in `docs/decisions.md`. Schema
  changes that break existing files need a migration.
- **Removal requests from a source's owner:** honoured. The entry is retired.
- **No pay-to-list, no ranking for sale, no exclusive deals.** The registry stays CC0.

## Moderation

- Sources are judged on the acceptance rules, not on viewpoint.
- Entries that are fake, impersonating, mostly scraped or generated content, or aimed at
  private individuals are removed, and repeat submitters are blocked.
- Code of Conduct reports go to the private channel named in that document.
- A maintainer does not review their own contribution or rule on a dispute about a source
  they are affiliated with.

## Avoiding centralisation

- Everything needed to run the project is in this repository. Forking is welcome, and the
  data licence (CC0) makes it possible without asking.
- The data is published as plain files (`dist/`) that anyone can mirror or build on
  without using the skill.
- The tools use no proprietary service, model or API.
- If the project grows, the aim is a small steering group drawn from community
  maintainers, with the repository moved to a neutral organisation. See the roadmap.
