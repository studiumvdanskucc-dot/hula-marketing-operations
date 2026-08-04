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
- a short heading inside an article whose title identifies it as a trend
  report;
- Tagwalk's named runway taxonomy.

Ordinary paragraphs and shopping body copy are never mined for trend names.
Every retained row records the publisher, explicit label, article/report title,
publication date when exposed, public URL and evidence type.

The collector requests only public HTML and does not log in, bypass paywalls or
execute subscriber-only content. Each publisher is isolated: a timeout,
paywall or redesign at one site is reported as `PARTIAL` or `FAILED` without
blocking the other sources.

## Settings

No API key is required.

```toml
COMMERCIAL_SOURCES_ENABLED = "true"
COMMERCIAL_TIMEOUT_SECONDS = "15"
COMMERCIAL_MAX_WORKERS = "6"
```

Use **Data & Setup → Test publisher pages** to see the live/partial/failed
publisher count. The last refresh stores per-publisher status for diagnostics.
