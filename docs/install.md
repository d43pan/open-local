# Installing the skill

There is one skill, `open-local`. It answers questions about a place, and it also carries
the instructions for adding a town and for growing coverage to the next towns over; those
load only when someone asks for them.

The folder name must stay `open-local` (the Agent Skills format requires the folder to
match the skill's name).

## Let your agent do it

Paste this to your agent:

> Install the Open Local skill from https://github.com/d43pan/open-local. Clone the
> repository to a temporary folder, copy the folder `skills/open-local` into your skills
> folder keeping that name, then run
> `python3 <skills folder>/open-local/scripts/run.py where "Little Compton, RI"` to
> confirm it works, and tell me what it printed. Do not run anything else from the
> repository.

## Any agent that reads Agent Skills

With Node.js installed, the open-source `skills` installer finds the skill in this
repository and puts it where your agent looks:

```
npx skills add d43pan/open-local            # choose agents when asked
npx skills add d43pan/open-local -g -y      # for your user, no questions
npx skills add d43pan/open-local -s open-local -a claude-code
```

## By hand

```
git clone https://github.com/d43pan/open-local
```

then copy the folder `skills/open-local` to your agent's skills folder:

| Agent | Skills folder (per user) | In one project |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenAI Codex | `~/.agents/skills/` | `.agents/skills/` |
| OpenClaw | `~/.openclaw/skills/` or `~/.agents/skills/` | `skills/` or `.agents/skills/` in the workspace |
| Hermes Agent | `~/.hermes/skills/` | |

```
cp -r open-local/skills/open-local ~/.claude/skills/
```

Hermes and OpenClaw can also install from GitHub directly:

```
hermes skills install d43pan/open-local/skills/open-local
openclaw skills install git:d43pan/open-local
```

## Claude apps (claude.ai, desktop)

Skills are uploaded as a ZIP whose top folder is the skill:

```
cd open-local/skills && zip -r open-local.zip open-local
```

Then Customize > Skills > "+" > Upload a skill, and choose the ZIP. Code execution must
be on, and the skill needs network access to reach local sources.

## Check it works

```
python3 ~/.claude/skills/open-local/scripts/run.py where "Little Compton, RI"
python3 ~/.claude/skills/open-local/scripts/run.py sources US/RI/little-compton --brief
```

The first run downloads a small index of places and the file for the place you ask about,
and keeps them for a day in `~/.cache/open-local/` (after that, an unchanged file costs one
small request). It never downloads every town. Then ask your agent: *"What's happening in Little Compton this
week?"*

## What was tested

| Method | Status on 2026-11-24 |
|---|---|
| Copy into `~/.claude/skills/` and run the tools | Tested |
| Folder names, frontmatter and limits against the Agent Skills specification | Tested in CI: `tests/test_skills.py`, and the specification's own `skills-ref` validator reports the skill valid |
| `npx skills add`, Codex, OpenClaw, Hermes, Claude app upload | Paths and commands are taken from each tool's documentation (linked in [research/ecosystem.md](research/ecosystem.md)); not run by this project yet. Reports welcome. |

## Requirements

Python 3.10 or newer and internet access. No packages to install, no API key, no account.
To edit and validate the registry you also need `pip install pyyaml jsonschema`.
