# Commercial website and report sources

The 35% commercial component comes from public pages belonging to nine
approved publishers:

| Publisher | Role | Weight |
| --- | --- | ---: |
| Tagwalk | Named runway taxonomy | 3× |
| Trendalytics | Data-backed trend reports | 3× |
| Heuritech | Quantified fashion forecasts | 3× |
| Data But Make It Fashion | Data-led fashion analysis | 3× |
| Lyst Index | Quarterly shopping-demand evidence | 3× |
| Who What Wear | Commercial/editorial trend reports | 2× |
| Who What Wear UK | UK/European commercial interpretation | 2× |
| Vogue | Runway and seasonal confirmation | 2× |
| ELLE | Runway and seasonal confirmation | 2× |

## Evidence contract

A trend counts only when the publisher explicitly names it in one of these
locations:

- the article or report title;
- a publisher-owned RSS or sitemap title;
- a source-specific editorial heading inside a trend report;
- Tagwalk's named runway taxonomy;
- a Lyst ranked-product list; or
- a numerical demand statement from Trendalytics or Data But Make It Fashion
  that directly attaches a named item to growth.

Ordinary paragraphs and shopping product cards are not mined for trend names.
Every retained row records the publisher, explicit label, article/report title,
publication date when exposed, public URL, evidence type and acquisition route.

## Discovery routes

The collector does not rely on a single category-page selector. It works in
layers:

1. source-specific public category/archive HTML;
2. configured current reports for high-value seasonal lists;
3. publisher RSS feeds or news sitemaps where available;
4. a domain-restricted query through the already configured SerpApi key when a
   publisher yields too little evidence or blocks the app server.

The fallback accepts only URLs on the approved publisher's own domain. It does
not add a new source or require a new credential.

The collector requests only public HTML and does not log in, bypass paywalls or
execute subscriber-only content. Each publisher is isolated: a timeout,
paywall or redesign at one site is reported as `PARTIAL` or `FAILED` without
blocking the other sources.

## Settings

Direct publisher routes require no API key. If `SERPAPI_API_KEY` is already
configured for Google Trends, it is also used for the bounded fallback.

```toml
COMMERCIAL_SOURCES_ENABLED = "true"
COMMERCIAL_TIMEOUT_SECONDS = "25"
COMMERCIAL_MAX_WORKERS = "4"
```

Use **Data & Setup → Test publisher pages** to see the live/partial/failed
publisher count plus the number of named trends, evidence rows and discovery
routes for every site. A loaded page with zero extracted trends is `PARTIAL`,
not a false success. The last refresh stores the same per-publisher status.
