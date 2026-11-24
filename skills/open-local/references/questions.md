# Which sources answer which question

Use `--type` (repeatable) with `sources` and `recent`. Types come from the registry schema.

| The user asks | Start with these types | Notes |
|---|---|---|
| What's happening? What happened this week? | all (no filter) | Lead with `direct` sources. Default window: 7 days back, 14 ahead. |
| What did the council decide? | `meetings`, `government`, `meeting-video`, then `newspaper`, `news-site` | Decisions come from minutes, recordings or reporting. Agendas show proposals only. Minutes can lag by weeks: widen `--days` to 45. |
| What's being built or changed? | `planning-zoning`, `permits`, `public-notices`, `meetings` | Applications and hearings are proposals until decided. |
| Any new businesses? | `business`, `chamber-of-commerce`, `permits`, `planning-zoning`, `public-notices`, `newspaper`, `news-site` | Licence hearings and sign permits are early signals, not openings. Say which you found. |
| What's on this weekend? | `events`, `library`, `arts-culture`, `performance-venue`, `museum`, `community-organization`, `parks-recreation`, `religious` | Use `--ahead` to reach the weekend. Give day, time, place. |
| Where can I eat / buy local food? | `food-drink`, `farm-market` | Hours and seasons change; say when you checked and link the venue's own page. |
| Schools? | `schools`, `meetings` | School committee agendas and minutes follow the meeting rules. |
| Is the beach / road / service open? | `emergency`, `public-safety`, `public-health`, `transportation`, `government`, `environment` | Time-sensitive. Give the time of the notice and link it. For emergencies point to the official source first. |
| What should I be paying attention to? | all | Use observable signals (see facts.md, Tone) and say that is the basis. |
| History of a place or building | `history`, `library`, `museum` | |

If a needed type has no source for the place, say so in the coverage report: that gap is
useful to the reader and to the registry.
