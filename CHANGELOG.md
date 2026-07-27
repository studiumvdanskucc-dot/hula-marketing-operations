# Changelog

## Build 2026.07.26.1 — Commercial Priority Sources

- Rebalanced the external trend score to 35% Google Trends worldwide, 20% open
  X discovery, 35% curated commercial-source confirmation and 10% reserved
  visual validation.
- Added a 3× evidence multiplier for the stable X accounts of Who What Wear,
  Who What Wear UK and Lyst; supporting fashion sources retain 1× weight.
- Added Data But Make It Fashion and Tagwalk to the high-priority editorial
  hierarchy through their official Instagram/site outputs without introducing
  an unauthorised Instagram scraper.
- Added priority-source mentions, weighted breadth and commercial authority to
  the deterministic score and dashboard methodology.
- Preserved worldwide Google Trends, the fashion-only guardrail and the
  150 MB / 400,000-row large-catalogue importer.

## Build 2026.07.25.1 — Large Catalogue Upload

- Raised the Streamlit catalogue upload ceiling from 20 MB to 150 MB.
- Raised the source-row safety limit from 50,000 to 400,000 rows.
- Reduced large-export memory usage by reading only the catalogue fields used
  by the dashboard instead of every Shopify export column.
- Changed product grouping to stream one group at a time rather than retaining
  thousands of grouped DataFrames in memory.
- Validated the importer against HULA's 102.7 MiB, 325,149-row merged export:
  56,060 products were normalised in under ten seconds in the test environment.

## Build 2026.07.22.8 — Global Fashion Guardrail

- Changed Google Trends from Hong Kong to worldwide. Worldwide SerpApi requests
  omit the country parameter, as required by Google Trends.
- Kept X listening global and English-language.
- Added a strict fashion-relevance gate after source collection. Unrelated
  concepts such as `Interior Design` and `Kindness` are now removed before
  scoring, product matching or display.
- Normalised the shortened `Jane` signal to `Mary Janes`; specific fashion
  ideas such as `Raffia Bags` remain eligible.
- Invalidated the older Hong Kong Google cache automatically when the worldwide
  build runs its first refresh.

## Build 2026.07.22.7 — Streamlit-Ready Google Trends

- Replaced the Apify Google Trends Actor and default direct `pytrends` request
  with SerpApi's structured Google Trends endpoint.
- Removed Google Trends from Apify capacity usage; Apify memory recovery now
  targets the HULA X task only.
- Added explicit `SERPAPI_API_KEY` configuration for local, Streamlit and GitHub
  Actions environments.
- Bounded the Google plan to three multi-term timeline comparisons and two
  related-query searches, or five API searches per live refresh.
- Preserved the 24-hour fresh cache, seven-day last-good recovery and manual
  Google Trends CSV importer.
- Added Hong Kong request, response-normalisation, related-query, key validation
  and request-ceiling tests. The full suite contains 47 passing offline tests.
- Added a no-Render deployment guide explaining Streamlit's rolling 12-hour
  inactivity sleep and one-click wake behaviour.

## Build 2026.07.22.6 — Low-Memory Queue & Recovery

- Added explicit Actor memory limits: 512 MB for each X search and 1 GB for
  Google Trends, replacing Google's former 4 GB default.
- Reduced Google Trends to one browser page at a time, 12 primary terms, two
  discovery seeds and four related-query validations per live refresh.
- Added server-side timeouts and automatic aborts. If a run outlives the app or
  a polling request fails, the connector stops that known run instead of
  leaving its memory reserved in Apify.
- Added capacity-aware fail-fast handling. One Apify 402 memory error stops the
  remaining X plan rather than printing the same error for all 14 searches.
- Added **Data & Setup → Apify run capacity** to inspect and stop active runs
  belonging to the configured HULA X task and Google Trends Actor.
- Added a 24-hour Google Trends cache. Repeated refreshes reuse the latest live
  series without another Actor run; a live failure can retain a cache up to
  seven days old rather than switching the entire radar to demo data.
- Updated Google term selection so the highest-scoring X discoveries are tested
  before the fixed watchlist when the 12-term ceiling is applied.
- Added nine resource-management and cache regressions. The full suite now
  contains 48 passing tests.

## Build 2026.07.22.5 — Resilient Signals & Business Radar

- Replaced the single fragile Google Trends route with automatic failover. When
  `APIFY_TOKEN` is present, the maintained `apify/google-trends-scraper` Actor
  is preferred; the direct `pytrends` route and manual CSV remain fallbacks.
- Added an independent live Google Trends test, persisted route/market/attempt
  diagnostics, an Actor cost ceiling and clearer explanations of pytrends'
  hard-coded US cookie-bootstrap URL.
- Replaced the overlapping raw-growth bubble plot with a ranked 0–100 business
  chart and three plain decisions: Act now, Test this week and Watch.
- Added an auditable quality filter for category-only, vague and platform terms.
  Specific combinations remain eligible, and every term removed from the last
  refresh is listed in Data & Setup.
- Replaced Product Match's easy-to-miss select field with a bordered,
  pink-accented expandable trend chooser that displays the current selection.

## Build 2026.07.22.4 — Topic Intelligence

- Replaced the single generic X Task run with a 14-search rolling plan covering
  five open topic families and a two-part expert panel across separate current
  and previous seven-day windows.
- Added ScrapeBadger Advanced Search input generation, per-query result limits,
  a per-run charge ceiling, partial-run recovery and run-level diagnostics.
- Added cross-query post deduplication and privacy-safe in-memory author hashing.
- Added unique-author breadth and growth, engagement per view, query-family
  breadth, expert confirmation, four-week novelty, spam rate, duplicate rate,
  dominant-author concentration and evidence-quality scoring.
- Added semantic topic grouping through Qwen using aggregated candidate phrases,
  with a local fashion ontology and word/character similarity fallback.
- Updated the external trend weighting to 45% Google Trends HK, 30% open X,
  15% expert confirmation and a reserved 10% visual-validation component. Missing
  sources are renormalised rather than treated as zero.
- Expanded Trend Radar and Data & Setup with listening-plan previews, source
  provenance, independent-author metrics and precise Actor compatibility checks.
- Updated configuration examples, deployment workflow and methodology documents.
- Preserved the Shopify CSV/API catalogue choice, OpenRouter campaigns, safe
  diagnostics and existing CSV upload fix.
- Added regression coverage; 32 offline tests pass.
