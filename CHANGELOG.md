# Changelog

## Build 2026.08.06.2 — Evidence-First Methodology 2.0

- Replaced the legacy Google/X/commercial/Instagram score with deterministic
  editorial, cross-source, Google, social, runway/celebrity and commercial
  components.
- Added explicit data completeness, missing-component renormalisation,
  confidence caps, contradiction penalties and duplicate/syndication removal.
- Removed the mandatory-Google action gate; insufficient search data remains
  `null` and visible.
- Added the separate HULA opportunity score and structured evidence schema.
- Expanded publisher coverage with Harper's Bazaar, InStyle, Refinery29 and
  Teen Vogue.
- Added optional Luna/Terra/Sol Responses API orchestration and usage records.
- Replaced live-grounded blog research with an evidence-locked writer.
- Migrated the included snapshot, refreshed the Streamlit views and expanded
  regression coverage.

## Build 2026.08.04.1 — Layered Publisher Discovery

- Fixed the publisher collector that previously reported a loaded page as a
  successful source even when it extracted zero named trends.
- Added source-specific extraction plus publisher RSS, news sitemaps, current
  report routes and a domain-restricted SerpApi fallback for blocked or
  JavaScript-heavy pages. All nine approved sites are attempted independently.
- Added a visible publisher inventory containing every explicitly sourced
  trend and its page link. The smaller action list remains separate and still
  requires fresh cross-source validation.
- Expanded Google validation from 12 to 24 candidates with reserved capacity
  for both publisher and open/social signals. Cache schema 3.0 forces the first
  refresh to replace the previous narrow cache.
- Fixed Instagram aggregate rows whose Actor identifies the requested hashtag
  with `searchTerm`, and added field-level mismatch diagnostics without storing
  captions, accounts, images or posts.
- Publisher tests now report named-trend and evidence-row counts per site, so a
  page that merely returns HTTP 200 can no longer look healthy.
- Added live-structure regression fixtures for Who What Wear, Vogue, feeds and
  sitemaps. All 85 offline tests pass.

## Build 2026.08.03.1 — Publisher Evidence & Trustworthy Charts

- Replaced Instagram profile/post scraping with aggregate hashtag analytics for
  already-qualified trends. Top/latest post collection is explicitly disabled.
- Added direct public-page evidence from Tagwalk, Trendalytics, Heuritech, Who
  What Wear, Who What Wear UK, Data But Make It Fashion, Vogue, ELLE and Lyst.
- Restricted commercial evidence to explicit titles, trend-labelled headings,
  dates and URLs; ordinary body text never creates a trend.
- Added the source-aware specificity gate: `pants`, `skirt`, `flats` and
  `polka` fail while specific combinations and the approved `jeans`, `loafers`
  and `sandals` exceptions pass.
- Separated Google ranking values from the displayed raw 0–100 index, added
  resolution/plateau/spike checks and invalidated legacy chart caches.
- Replaced the large priority bar chart with compact decision rows and exposed
  exact publisher evidence in each trend deep dive.
- Added commercial-source, hashtag-metadata and Google-display regressions;
  80 offline tests now cover the build after removing the retired profile-post
  connector and its obsolete tests.

## Build 2026.07.28.2 — Gemini 3.6 Compatibility

- Replaced the retired Gemini 2.5 default with stable `gemini-3.6-flash`.
- Increased the diagnostic output allowance and uses minimal thinking so the
  connection test cannot spend its full allowance before returning JSON.
- Removed sampling overrides that Google no longer recommends for Gemini 3.
- Added Gemini 3 structured JSON output for both diagnostics and grounded blogs.
- Retries one transient blank HTTP-200 response and exposes the finish reason
  and token counts if Gemini remains blank.

## Build 2026.07.28.1 — Fresh Sources & Researched Editorial

- Added strict fourteen-day timestamp validation before topic discovery.
- Added the approved ten-profile Instagram panel with 3×/2× authority tiers
  and capped Qwen visual reading.
- Split Google into seven-day rising-query discovery, one-month validation and
  seven-day acceleration.
- Excluded invariant Google series from scoring and charts.
- Moved incomplete rows into a separate watchlist so the decision table has no
  missing Google values.
- Updated the exact-name filter: `sandal` and `sandals` are valid; `trousers`,
  `outfit ideas`, `dress` and `mini` are blocked alone, while `red trousers`
  and `mini dress` remain valid.
- Added Supabase aggregate history and grounded Gemini Wednesday blogs.
- Added Soho and The Hub equally across campaign reasons, objectives, store
  activations, blog reasons and calls to action.
- Added source-health diagnostics and regression coverage; 66 offline tests pass.

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
