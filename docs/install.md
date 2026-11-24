# Installing the skills

There are two skills. Most people want the first; add the second if you plan to map a
place.

- `open-local`: ask about a place.
- `open-local-build`: add or fix a place and send it back.

The folder names must stay exactly as they are (the Agent Skills format requires the
folder to match the skill's name).

## Let your agent do it

Paste this to your agent:

> Install the Open Local skills from https://github.com/d43pan/open-local. Clone the
> repository to a temporary folder, copy `skills/open-local` and `skills/open-local-build`
> into your skills folder keeping those folder names, then run
> `python3 <skills folder>/open-local/scripts/run.py where "Little Compton, RI"` to
> confirm it works, and tell me what it printed. Do not run anything else from the
> repository.

## Any agent that reads Agent Skills

With Node.js installed, the open-source `skills` installer finds both skills in this
repository and puts them where your agent looks:

```
npx skills add d43pan/open-local            # choose skills and agents when asked
npx skills add d43pan/open-local -g -y      # both skills, for your user, no questions
npx skills add d43pan/open-local -s open-local -a claude-code
```

## By hand

```
git clone https://github.com/d43pan/open-local
```

then copy the two folders under `skills/` to your agent's skills folder:

| Agent | Skills folder (per user) | In one project |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenAI Codex | `~/.agents/skills/` | `.agents/skills/` |
| OpenClaw | `~/.openclaw/skills/` or `~/.agents/skills/` | `skills/` or `.agents/skills/` in the workspace |
| Hermes Agent | `~/.hermes/skills/` | |

```
cp -r open-local/skills/open-local open-local/skills/open-local-build ~/.claude/skills/
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

The first run downloads the registry (one file) and keeps it for a day in
`~/.cache/open-local/`. Then ask your agent: *"What's happening in Little Compton this
week?"*

## What was tested

| Method | Status on 2026-11-24 |
|---|---|
| Copy into `~/.claude/skills/` and run the tools | Tested |
| Folder names, frontmatter and limits against the Agent Skills specification | Tested in CI (`tests/test_skills.py`) |
| `npx skills add`, Codex, OpenClaw, Hermes, Claude app upload | Paths and commands are taken from each tool's documentation (linked in [research/ecosystem.md](research/ecosystem.md)); not run by this project yet. Reports welcome. |

## Requirements

Python 3.10 or newer and internet access. No packages to install, no API key, no account.
To edit and validate the registry you also need `pip install pyyaml jsonschema`.
