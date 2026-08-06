# Recent fashion-editorial sources

Pipeline 4.0 uses fashion publishers as the discovery engine.

| Publisher | Public section | Weekly article cap | Window |
| --- | --- | ---: | ---: |
| Who What Wear | Fashion trends | 12 | 21 days |
| Vogue | Fashion trends | 10 | 21 days |
| ELLE | Trend reports | 10 | 21 days |
| Harper's Bazaar | Fashion trends | 10 | 21 days |
| Marie Claire | Fall/fashion coverage | 10 | 21 days |
| Glamour | Fashion | 10 | 21 days |
| InStyle | Fashion | 10 | 21 days |

## What becomes evidence

A publisher can introduce a trend through an article title, a trend-labelled
heading or a concrete GPT extraction supported by the collected page. Each row
retains its publisher, independent group, article title, publication date,
public URL, short excerpt and extraction route.

Generic body copy, sale stories, sponsored material, unrelated product cards,
brands and broad category words do not become trend candidates. Repeated URLs
and same-group editions are deduplicated before overlap is counted.

## Collection routes

Each publisher is attempted independently through:

1. its public trend/fashion index;
2. configured current articles;
3. public RSS or sitemap candidates;
4. a bounded domain-restricted SerpApi fallback if a public page is blocked or
   JavaScript-only.

The collector does not log in, bypass paywalls or save full article bodies.
One blocked publisher does not stop the weekly run; the dashboard exposes the
state and first issue for every source.

```toml
COMMERCIAL_SOURCES_ENABLED = "true"
COMMERCIAL_TIMEOUT_SECONDS = "25"
COMMERCIAL_MAX_WORKERS = "4"
EDITORIAL_LOOKBACK_DAYS = "21"
EDITORIAL_MAX_ARTICLES = "48"
EDITORIAL_AI_BATCH_SIZE = "5"
```

Use **Data & Setup → Test publisher pages** and **Editorial Radar → Publisher
scan** to inspect source-level coverage.
