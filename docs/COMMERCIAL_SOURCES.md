# Editorial and industry sources

Publisher evidence feeds several methodology 2.0 components; it is no longer a
single 35% “commercial report” score.

| Source | Primary role | Authority |
| --- | --- | ---: |
| Data But Make It Fashion | Data-led fashion evidence | 1.50 |
| Lyst Index | Shopping demand / ranked products | 1.45 |
| Tagwalk | Runway taxonomy | 1.40 |
| Who What Wear / UK | Editorial and shopping confirmation | 1.30 |
| Vogue, ELLE, Harper's Bazaar | Editorial/runway confirmation | 1.20 |
| InStyle, Refinery29, Teen Vogue | Editorial confirmation | 1.10 |
| Trendalytics, Heuritech | Industry-data context | 1.10 |

## Evidence rules

A source may introduce a specific trend through a publisher-owned title,
selected trend heading, runway taxonomy, ranked product or explicitly attached
data statement. Generic body copy, unrelated shopping cards and broad labels
such as “summer outfits” do not create trends.

Every retained row records publisher, explicit label, article/report title,
date when exposed, public URL, evidence type and acquisition route. Repeated
press-release copies and syndicated titles are deduplicated before scoring.

## Collection routes

The collector tries, in order:

1. public category/archive HTML;
2. configured current reports;
3. RSS or publisher sitemaps;
4. a bounded domain-restricted SerpApi result when a public page is blocked or
   rendered only with JavaScript.

It does not log in, bypass paywalls or retain full articles. Each publisher
fails independently and exposes a `LIVE`, `PARTIAL` or `FAILED` status.

```toml
COMMERCIAL_SOURCES_ENABLED = "true"
COMMERCIAL_TIMEOUT_SECONDS = "25"
COMMERCIAL_MAX_WORKERS = "4"
```

Use **Data & Setup → Test publisher pages** to inspect source-by-source
evidence counts and collection routes.
