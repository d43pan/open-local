# Security

## Reporting a problem

Report privately at https://github.com/d43pan/open-local/security/advisories/new.
Please do not open a public issue for a vulnerability. You should hear back within a week.

## What this project guards against

The registry is a list of web addresses that anyone can propose, and the tools fetch
them. Agents then read what comes back. Both are treated as hostile input.

| Risk | What is done |
|---|---|
| A registry entry points at an internal address (SSRF) | Only `http`/`https`, no credentials, a short list of ports. Every hostname is resolved and refused unless all its addresses are public; the connection is made to the address that was checked. Validation in CI rejects such URLs before merge. |
| A public URL redirects somewhere internal | Redirects are followed by hand, at most five, each checked the same way. |
| Huge or slow responses | 5 MB cap, 20 second timeout, one request per host per second. |
| Malicious XML | Feeds that declare entities are refused; nothing is resolved from outside the document. |
| Code execution | Nothing fetched is executed, imported or unpickled. YAML is loaded with `safe_load`. No shell commands are built from registry data. |
| Prompt injection through a feed, page or registry field | The skills tell agents that all fetched text is data. Tool output carries the same note. This reduces the risk; it cannot remove it. Agents that act on what they read (send, buy, delete) should not do so on the strength of local-news content. |
| A fake or impersonating source gets listed | Human review of every pull request, acceptance rules, `provenance` on each entry, and scheduled checks. Agent-drafted entries cannot be marked verified without a named reviewer. |
| Personal data in the registry | Validation rejects email addresses; the rules forbid personal contact details. |

## Known limits

- The tools obey `robots.txt` and rate limits. An agent that fetches pages with its own
  browser or HTTP tool is outside these protections.
- Radius search uses centre points, not boundaries.
- A source can change owner or content after it was verified. `verified` dates and the
  scheduled check exist for that reason; treat old entries with more care.
