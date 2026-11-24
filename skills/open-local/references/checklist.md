# Where local information lives: a checklist

Go through these with the person. Most small places have something in about half of them.
The type in brackets is the registry `type`.

## Public bodies (first-hand records)

- **The town, city or parish website** [`government`]: news, notices, alerts.
- **Council, select board, parish council** [`meetings`]: agendas, minutes, video. Many
  places file these on a state or national portal instead of their own site, so check
  both. List the page with the documents as an endpoint.
- **Planning, zoning, conservation, harbour boards** [`planning-zoning`].
- **School committee and district** [`schools`]: calendar, committee agendas, budget.
- **Budget and finance** [`budget`]: adopted budgets, audits, warrants, town meeting.
- **Permits and development** [`permits`]: building permits, applications, hearings.
- **Public and legal notices** [`public-notices`]: often a statewide site.
- **Police, fire, emergency management** [`public-safety`, `emergency`]: alerts and
  notices, not individual arrest logs.
- **Public health, beaches, water** [`public-health`].
- **Transport** [`transportation`]: bus agency, ferry, road works.
- **Utilities and special districts** [`utility`].

## Reporting

- **The paper people actually read** [`newspaper`], and its town section or tag if it has
  one (a town-specific feed is worth far more than the whole paper's).
- **Online-only newsrooms and nonprofits** [`news-site`].
- **Independent journalists, newsletters, blogs** [`journalist`, `newsletter`, `blog`].
- **Radio, TV, public-access TV, podcasts** [`radio`, `television`, `public-access-tv`,
  `podcast`], and meeting recordings [`meeting-video`].

## Community

- **Library** [`library`]: usually the best events calendar in town.
- **Parks and recreation** [`parks-recreation`], sports leagues [`sports`].
- **Community centre, civic groups, land trusts, friends-of groups**
  [`community-organization`, `environment`].
- **Historical society, museum** [`history`, `museum`].
- **Chamber of commerce, business association, tourism office**
  [`chamber-of-commerce`, `business`, `tourism`].
- **Churches and other congregations with public calendars** [`religious`].
- **Public community forums** [`forum`]: only open, public ones.

## Food, arts and culture

- **Farms, farm stands, farmers markets, fish markets** [`farm-market`].
- **Restaurants, cafes, bakeries, vineyards, breweries that publish their own hours,
  menus or events** [`food-drink`]. The venue's own page, not a review site.
- **Galleries, art associations, studios, cultural councils** [`arts-culture`].
- **Theatres, music series, concert halls** [`performance-venue`].
- **Festivals and annual events** [`events`].

## Finding the machine-readable part

`run.py discover <url>` checks what a page advertises and tries common paths. If it
finds nothing, look by hand; these are common:

| Platform | Try |
|---|---|
| WordPress | `/feed/`, `/category/<name>/feed/`, `/tag/<town>/feed/`, The Events Calendar: `/events/?ical=1` |
| Squarespace | add `?format=rss` to a blog or events page |
| CivicPlus (many US town sites) | `/RSSFeed.aspx?ModID=…`, `/iCalendar.aspx`, "Notify Me" and "RSS" links in the footer |
| Drupal | `/rss.xml`, `/feed` |
| Substack, Ghost | `/feed`, `/rss/` |
| YouTube | the channel page advertises `https://www.youtube.com/feeds/videos.xml?channel_id=…` |
| Google Calendar embeds | the public `.ics` address from the calendar's settings, if the owner publishes it |
| Podcasts | the RSS feed linked from the show's page |
| Legistar, Granicus, BoardDocs, ClerkBase | usually no feed; list the meetings page as `html` or `documents` |

No feed is normal. List the page that carries the updates with `kind: html` (or
`documents` for a folder of PDFs) and a `note` saying what is there. Agents will read it.

Do not list: private Facebook groups, personal social accounts, sites that require a
login to read, or anything the owner has asked not to be crawled.
