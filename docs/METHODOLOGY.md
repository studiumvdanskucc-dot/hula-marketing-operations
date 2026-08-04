# Methodology and interpretation

## What the system answers

The dashboard prioritises which currently available HULA products deserve
marketing attention because fresh external demand is strengthening and the
catalogue provides a credible match. It is decision support, not a sales
forecast.

## Freshness contract

X records are eligible only when they have:

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
styling and resale language. Every search is run for the current and previous
windows with Latest ordering, no replies and no reposts. Publisher accounts on
X remain supporting context; they no longer supply the commercial score.

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

## Commercial website and report evidence

The commercial collector reads public pages from Tagwalk, Trendalytics,
Heuritech, Who What Wear, Who What Wear UK, Data But Make It Fashion, Vogue,
ELLE and the Lyst Index. Source-specific pages, publisher feeds and sitemaps are
used first; a domain-restricted SerpApi search is the fallback. A source counts
only when a publisher title, selected editorial trend heading, Tagwalk
taxonomy, Lyst ranked product or explicit quantified data statement names the
trend. Ordinary unlabelled body text and shopping product cards are excluded.

The component combines unique-publisher breadth, authority weight and recency.
Tagwalk, Trendalytics, Heuritech, Data But Make It Fashion and Lyst receive the
higher authority weight. A publisher failure is isolated and never converted
to a zero for the other sources.

## Instagram aggregate metadata

Instagram is queried only after a trend has been qualified elsewhere. The
aggregate hashtag Actor returns lifetime public uses, posts per day and related
hashtag counts. Top/latest post collection is disabled, so no captions,
accounts or images enter the pipeline.

The score is a comparison among the hashtags queried during that refresh.
Posts per day leads when available; lifetime counts are log-scaled. The result
is directional and non-causal.

## Topic grouping

Candidate phrases come from fashion-aware one-, two- and three-word phrases,
hashtags and a maintained alias ontology. Qwen may group aggregated aliases,
but it cannot create numerical evidence. The deterministic local method
validates the output and is the fallback.

The source-aware specificity gate rejects category-only labels before scoring.
`pants`, `skirt`, `flats` and `polka` fail; `capri pants`, `pencil skirt`,
`ballet flats` and `polka dots` pass. `jeans`, `loafers` and `sandals` are the
approved standalone exceptions. A trusted report may introduce a named colour,
material or aesthetic such as `burgundy`, `suede` or `boho chic`; raw social
frequency cannot promote those one-word labels by itself.

## Google discovery and validation

Google uses SerpApi's structured Trends endpoint:

- rising related queries over `now 7-d` discover fresh phrases;
- `today 1-m` validates persistence;
- `now 7-d` measures immediate acceleration.

Worldwide requests omit `geo`; the literal value `WORLDWIDE` is never sent as a
country code. Timeline values must carry their query names and are never
assigned by array position.

Google normalises every multi-query comparison independently. The app repeats
an anchor term and may use an anchor-calibrated value internally for ranking
across batches. That calculated value is never plotted. Charts use only
Google's original 0–100 index with light rolling smoothing. Timelines with too
few distinct values, excessive plateaus, isolated spikes, out-of-range values
or no preserved raw index are withheld with an “Insufficient Google
resolution” explanation.

The Google score combines current relative interest, baseline momentum and
time-series slope. Google values are relative, not absolute search volume.

A compatible result under 24 hours is a live cache. A cache up to three days
old may be displayed as stale after a provider failure, but stale Google
evidence cannot make a trend decision-ready.

## Combined score and completeness

```text
35% Google Trends worldwide
20% open X topic momentum
35% approved website/report confirmation
10% aggregate Instagram hashtag comparison
```

Missing components are excluded and the available weights are renormalised;
missing evidence is not converted to zero. A row enters the decision list only
when fresh Google and at least one X, commercial-report or hashtag component
agree.
Incomplete rows remain in a separate watchlist.

Confidence is **High** when Google and commercial reports agree alongside X or
Instagram, or when Google agrees with at least two approved publishers. Google
plus one other eligible source is **Medium**. One-source evidence is
**Exploratory** and cannot receive an action recommendation.

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

Supabase stores aggregate weekly snapshots and blog drafts. Raw X posts are not
stored. Commercial evidence contains only public titles, explicit labels,
dates and URLs. Instagram stores only aggregate hashtag counts; captions,
accounts and images are never collected. Customers, orders and payment data
are not accessed.

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
