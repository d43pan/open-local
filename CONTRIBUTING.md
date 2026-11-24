# Contributing

The most useful contribution is knowledge of a place: where the minutes are posted, which
paper people read, who keeps the best events calendar. You do not need to code.

| You want to | Do this |
|---|---|
| Add one source | [Open an "Add a source" issue](https://github.com/d43pan/open-local/issues/new/choose): a form, no git |
| Add your town | [Open an "Add a community" issue](https://github.com/d43pan/open-local/issues/new/choose), or let your AI agent do the legwork with the Open Local skill |
| Add the towns around one that is already mapped | Ask your agent to expand Open Local to the next town over: the skill finds the unmapped neighbours and reuses what the registry already knows |
| Report something broken or wrong | [Open a "Broken source" issue](https://github.com/d43pan/open-local/issues/new/choose) |
| Do it all yourself | Edit the YAML and open a pull request (below) |

New to all this? Read [docs/for-everyone.md](docs/for-everyone.md) first.

## What gets accepted

The full rules are in
[skills/open-local/references/acceptance.md](skills/open-local/references/acceptance.md).
In short: public, about the place, identifiable, honestly described, working, and not about
private individuals. Listing is not endorsement and sources are not judged on viewpoint.

## Adding or changing registry entries by hand

1. Fork and clone. Install the checking tools: `pip install pyyaml jsonschema pytest`.
2. Find or create the place file: `registry/<place id>.yaml`
   ([how to write one](skills/open-local/references/place-file.md)).
3. Draft entries. `python3 skills/open-local/scripts/run.py propose <url> --place <id> --type <type>`
   loads the site, finds its feeds and prints YAML to paste in. Then read the site and fix
   the name, type, coverage and paywall fields. Field reference: [docs/registry.md](docs/registry.md).
4. Open every address yourself. Set `status: verified` and `verified:` to today only for
   those that load.
5. Check and rebuild:
   ```
   python3 skills/open-local/scripts/run.py validate
   python3 skills/open-local/scripts/run.py build
   pytest -q
   ```
6. Open a pull request and fill in the template.

## With an AI agent

Install the skill (see the README), then say: *"Use Open Local to add my town."*
The agent asks you what you know, finds the sources, drafts the entries and, with your
go-ahead, opens the pull request.

Agents may draft; people decide. An agent-drafted entry carries
`provenance.method: agent-proposed`, and validation refuses to let it be marked verified
until `provenance.added_by` names the person who reviewed it. Pull requests are merged by
maintainers only, never by an agent, and never automatically.

## Review

A maintainer, ideally one who knows the place, checks that the addresses load, that the
descriptions are accurate and that the rules above are met. Expect questions; small fixes
are often made directly on your branch. Checks that run automatically:

- **On every pull request (no network):** schema, unique ids, references between places,
  geographic consistency, safe URLs, dates, exports up to date, tests.
- **Weekly (network):** every listed address is loaded; failures open an issue. A town
  website being down never blocks your pull request.

## Code, skills and documentation

Keep it small and dependency-free: the tools run on the Python standard library so they
work inside any agent. Add a test with every change. Skill instructions stay short;
detail goes in `references/`. Architecture decisions are recorded in
[docs/decisions.md](docs/decisions.md); propose changes to them in an issue first.

## Licences

By contributing you agree that registry data you add (`registry/`, `dist/`) is dedicated
to the public domain under [CC0](LICENSE-DATA), and that code, documentation and skill
text are under the [MIT licence](LICENSE). Only contribute descriptions you wrote
yourself; do not copy descriptions, geometry or bulk data from sources under other
licences.

## Conduct

The [Code of Conduct](CODE_OF_CONDUCT.md) applies everywhere in the project.
