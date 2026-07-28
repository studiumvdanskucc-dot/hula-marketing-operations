# Methodology and interpretation

## What the system answers

The dashboard prioritises which currently available HULA products deserve
marketing attention because fresh external demand is strengthening and the
catalogue provides a credible match. It is decision support, not a sales
forecast.

## Freshness contract

X and Instagram records are eligible only when they have:

- a valid publication timestamp inside the latest fourteen days;
- usable text;
- no repost flag;
- no duplicate post fingerprint.

The real timestamp overrides any scraper-supplied listening-window label. The
latest seven days form the current window; the preceding seven days form the
comparison window. Missing timestamps are rejected and are never replaced with
the current time.

## X discovery

Five broad topic families discover product, material, silhouette, aesthetic,
styling and resale language. A separate commercial panel confirms evidence.
Every search is run for the current and previous windows with Latest ordering,
no replies and no reposts.

The open-X component combines:

```text
25% current unique-author breadth
20% unique-author growth
15% post growth
15% engagement per 1,000 views
10% independent query-family breadth
10% four-week novelty
 5% current post volume
```

An evidence-quality multiplier penalises promotional content, cross-query
duplicates, low author coverage and excessive concentration in one author.

## Instagram commercial and visual evidence

The approved priority panel—Data But Make It Fashion, Tagwalk, Who What Wear,
Who What Wear UK and Lyst—receives 3× commercial evidence weight. Vogue Runway,
WGSN, Trendalytics, EDITED and Heuritech receive 2×.

Instagram captions contribute to the commercial-source component. A capped set
of public post images may be read by Qwen for concrete product, silhouette,
material, colour and styling labels, contributing to the visual component.
Publisher breadth is deduplicated across Instagram and X.

## Topic grouping

Candidate phrases come from fashion-aware one-, two- and three-word phrases,
hashtags and a maintained alias ontology. Qwen may group aggregated aliases,
but it cannot create numerical evidence. The deterministic local method
validates the output and is the fallback.

The exact-name filter removes vague labels before scoring. `sandal` and
`sandals` remain valid. `trousers`, `outfit ideas`, `dress` and `mini` are
removed alone, while `red trousers`, `mini dress` and other specific
combinations remain eligible.

## Google discovery and validation

Google uses SerpApi's structured Trends endpoint:

- rising related queries over `now 7-d` discover fresh phrases;
- `today 1-m` validates persistence;
- `now 7-d` measures immediate acceleration.

Worldwide requests omit `geo`; the literal value `WORLDWIDE` is never sent as a
country code. Timeline values must carry their query names and are never
assigned by array position. An invariant series is considered an unusable
provider/calibration result and is excluded from scoring and charts.

The Google score combines current relative interest, baseline momentum and
time-series slope. Google values are relative, not absolute search volume.

A compatible result under 24 hours is a live cache. A cache up to three days
old may be displayed as stale after a provider failure, but stale Google
evidence cannot make a trend decision-ready.

## Combined score and completeness

```text
35% Google Trends worldwide
20% open X topic momentum
35% approved commercial-source confirmation
10% approved Instagram visual validation
```

Missing components are excluded and the available weights are renormalised;
missing evidence is not converted to zero. A row enters the decision list only
when fresh Google and at least one open, commercial or visual component agree.
Incomplete rows remain in a separate watchlist.

Confidence is **High** when Google, open X and commercial/visual evidence agree,
or when Google agrees with a priority commercial source. Google plus one other
eligible source is **Medium**. One-source evidence is **Exploratory** and
cannot receive an action recommendation.

## Catalogue matching

The app reads active, in-stock products from an uploaded catalogue snapshot or
the live read-only Shopify API. Matching uses product title, brand, product
type, tags and description.

```text
45% external trend signal
35% catalogue relevance
15% content readiness
 5% catalogue freshness
```

Content readiness checks stock, image, description and merchandising tags.
One-of-one stock quantity `1` is fully available; out-of-stock products are
excluded.

## Storage and editorial controls

Supabase stores aggregate weekly snapshots and blog drafts. Raw X/Instagram
posts, raw profile identifiers, customers, orders and payment data are not
stored.

Gemini runs only after deterministic ranking and product matching. A named
person may be described as wearing a selected product only when a credible
source supports the exact design. A similar item is labelled
`similar_design_only` and stays outside factual publishable copy.

Before publishing:

1. verify stock and condition;
2. review every confirmed source;
3. check margin and campaign fatigue;
4. approve the final copy and imagery;
5. verify whether Soho, The Hub, online—or a combination—is the correct CTA.
