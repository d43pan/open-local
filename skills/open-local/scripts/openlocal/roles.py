"""What part a source plays in a place's information: the archetypes `gaps` checks for.

`type` says what a source is (a newspaper, a radio station, a farm stand). A role says what
it does for the people of a place (the legacy daily, the independent voice, where to buy
food). One source can have several. A place is well covered when it has a spread of roles,
not just many sources: ten outlets of one owner are one voice.

A source's roles are its `roles` field when set, otherwise the defaults for its type below.
News outlets have no default (a newspaper may be a daily, a weekly or an alt-weekly), so
they should carry `roles` explicitly.
"""
from __future__ import annotations

ROLES: dict[str, tuple[str, str]] = {
    # role: (group, what it means)
    "legacy-daily": ("news", "A daily paper or its site, usually for the county or region."),
    "community-weekly": ("news", "A weekly or twice-weekly paper for a town or a few towns."),
    "hyperlocal-digital": ("news", "An online-only local news site for a town or small area."),
    "nonprofit-newsroom": ("news", "A nonprofit or investigative newsroom."),
    "public-media": ("news", "Public radio or television."),
    "broadcast-tv": ("news", "A commercial television station."),
    "alternative": ("news", "An alt-weekly or other alternative press: opinion and culture-heavy."),
    "independent-voice": ("news", "A solo reporter, newsletter, blog or podcast publishing in public."),
    "community-language": ("news", "Press for a language or ethnic community."),
    "student-press": ("news", "A school or college paper or station."),
    "business-press": ("news", "Business, trade or real-estate news."),
    "arts": ("culture", "Galleries, arts councils, reviews, arts calendars."),
    "music-nightlife": ("culture", "Venues, bands, open mics, nightlife calendars."),
    "events-listings": ("culture", "What's on: event calendars and listings."),
    "dining": ("culture", "Restaurants, cafes and bars: openings, menus, reviews."),
    "food-buying": ("culture", "Farm stands, markets, CSAs, fish markets, food pantries."),
    "outdoors-nature": ("culture", "Sanctuaries, land trusts, beaches, trails, tides, fishing."),
    "sports": ("culture", "School, youth and local sports."),
    "public-notices": ("civic", "Legal notices, hearings, bids."),
    "classifieds": ("civic", "Jobs, for sale, yard sales, lost pets."),
    "real-estate-development": ("civic", "Development, permits, property listings."),
    "obituaries": ("civic", "Obituaries and milestones."),
    "police-fire-log": ("civic", "Police and fire logs and alerts."),
    "official-record": ("civic", "The government's own records: meetings, agendas, minutes, budgets."),
    "faith": ("community", "Churches and other faith communities."),
    "community-groups": ("community", "Clubs, associations, seniors, families, veterans, other groups."),
    "community-forum": ("community", "Where residents talk to each other: Facebook groups, listservs, forums. "
                                     "Listed for a person to open; tools never read them."),
}

# Defaults by type, only where the type says the role without doubt.
TYPE_ROLES: dict[str, list[str]] = {
    "government": ["official-record"], "meetings": ["official-record"], "budget": ["official-record"],
    "planning-zoning": ["official-record", "real-estate-development"], "permits": ["real-estate-development"],
    "public-notices": ["public-notices"], "public-safety": ["police-fire-log"], "emergency": ["police-fire-log"],
    "journalist": ["independent-voice"], "newsletter": ["independent-voice"], "blog": ["independent-voice"],
    "podcast": ["independent-voice"], "television": ["broadcast-tv"], "public-access-tv": ["official-record"],
    "meeting-video": ["official-record"], "events": ["events-listings"], "arts-culture": ["arts"], "museum": ["arts"],
    "performance-venue": ["music-nightlife", "events-listings"], "food-drink": ["dining"], "farm-market": ["food-buying"],
    "environment": ["outdoors-nature"], "parks-recreation": ["outdoors-nature"], "sports": ["sports"],
    "religious": ["faith"], "community-organization": ["community-groups"], "history": ["community-groups"],
    "forum": ["community-forum"], "library": ["events-listings"],
}

# The spread a place should aim for. Missing ones are places to look, not proof of a gap.
CORE_ROLES = ("official-record", "legacy-daily", "community-weekly", "hyperlocal-digital", "independent-voice",
              "events-listings", "dining", "food-buying", "arts", "music-nightlife", "outdoors-nature", "sports",
              "public-notices", "police-fire-log", "classifieds", "obituaries", "community-groups", "community-forum")
MAINSTREAM = {"legacy-daily", "community-weekly", "broadcast-tv", "public-media"}
INDEPENDENT = {"hyperlocal-digital", "nonprofit-newsroom", "alternative", "independent-voice", "community-language", "student-press"}
NEWS = {r for r, (group, _) in ROLES.items() if group == "news"}


def roles_of(source: dict) -> list[str]:
    return list(source.get("roles") or TYPE_ROLES.get(source.get("type", ""), []))


def spread(sources: list[dict]) -> dict:
    """Roles present among these sources, and the checks on balance and ownership."""
    have: dict[str, list[str]] = {}
    for s in sources:
        for r in roles_of(s):
            have.setdefault(r, []).append(s["name"])
    news = [s for s in sources if set(roles_of(s)) & NEWS]
    owners = sorted({(s.get("publisher") or s["name"]).split("(")[-1].rstrip(") ").strip() for s in news})
    checks = []
    if not set(have) & MAINSTREAM:
        checks.append("No mainstream outlet (daily, weekly, TV or public media) reaches this place.")
    if not set(have) & INDEPENDENT:
        checks.append("No independent or hyperlocal voice is listed.")
    if len(owners) == 1:
        checks.append(f"Every news outlet listed has one publisher ({owners[0]}).")
    untagged = sorted(s["name"] for s in sources if s.get("type") in ("newspaper", "news-site", "radio") and not s.get("roles"))
    return {"has": {r: len(v) for r, v in sorted(have.items())},
            "missing_core_roles": [r for r in CORE_ROLES if r not in have],
            "news_publishers": len(owners), "checks": checks,
            **({"news_sources_without_roles": untagged} if untagged else {})}
