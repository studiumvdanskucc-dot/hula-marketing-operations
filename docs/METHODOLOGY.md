# Methodology and interpretation

## What the system answers

The dashboard prioritises: **which currently available HULA products deserve
marketing attention because external demand is strengthening and the catalogue
provides a credible match?**

It is decision support. It does not forecast unit sales, replace a merchandiser
or prove that a campaign will perform.

## X discovery and measurement

### Balanced rolling searches

The default ScrapeBadger plan covers five open topic families: products,
colours/materials, shapes/silhouettes, aesthetics, and styling/resale behaviour.
A separate expert panel acts as validation. Every search is run twice:

- current seven days;
- previous seven days.

The windows do not overlap. This avoids comparing a very recent `Latest` sample
with older posts inside one uneven result set. Ordinary phrases and hashtags are
both accepted; neither hashtags nor monitored profiles define the discovery
universe by themselves.

### Privacy-safe author breadth and deduplication

The same post may appear in several searches. It is collapsed by a one-way post
fingerprint while its query-family provenance is retained. Author identifiers
are one-way hashed in memory, used to calculate breadth and dominance, and then
discarded. Raw posts, handles and hashes are not written to the weekly snapshot.

For each topic the app records:

- current and previous post mentions;
- current and previous unique-author counts;
- author and post growth;
- engagement per 1,000 views when views are available;
- number of independent open query families;
- expert-panel mentions and authors;
- novelty against the previous four weeks of saved snapshots;
- duplicate, promotional and dominant-author indicators.

### Topic grouping

Candidate phrases come from fashion-aware one-, two- and three-word phrases,
hashtags and a maintained fashion alias ontology. A local word/character
similarity method groups spelling and near-lexical variants. When Qwen is
available, it receives only aggregated candidate phrases and proposes stricter
semantic groups—for example `ballet pumps`, `ballet flats` and `balletcore
shoes`. The local method validates the output and remains the fallback.

Qwen cannot create numerical evidence. It can group or label supplied phrases;
all post, author, engagement and growth values are calculated from collected
records.

### Open X component

The open-conversation score is a percentile composite:

```text
25% current unique-author breadth
20% unique-author growth
15% post growth
15% engagement per 1,000 views
10% independent query-family breadth
10% four-week novelty
 5% current post volume
```

The result is multiplied by an evidence-quality factor. Quality falls when the
topic contains many cross-query duplicates, likely promotional posts, low
author coverage or excessive concentration in one author. This makes it harder
for one highly active commercial account to manufacture a trend.

### Expert component

Expert evidence is scored independently from open discovery using current
expert-author breadth, expert mention growth and engagement per view. Expert
accounts can confirm an open topic but cannot create open-conversation growth.
The account list is configurable and should be reviewed quarterly for relevance
and activity.

X data remains a listening sample, not a census. Actor query design, platform
demographics and access conditions affect the result.

## Google Trends worldwide

Candidate phrases from social discovery, related-query discovery and the HULA
watchlist are measured for the selected market and time range. A percentile
score combines:

```text
45% current relative interest
40% momentum versus the recent baseline
15% recent time-series slope
```

Google Trends web values are normalised from 0 to 100. They are not absolute
search volume. The connector uses a repeated anchor term to make separate
batches more directionally comparable, but the output should still be read as
momentum rather than market size.

Automatic mode uses SerpApi's Google Trends endpoint. It performs the
Google-facing request outside the Streamlit process and returns structured
timelines and related queries. This avoids both Apify Actor memory and the
archived `pytrends` cookie-bootstrap route. A manual CSV importer remains the
final operational fallback.

Each live refresh measures at most 12 primary terms in three multi-term
comparisons and checks at most two related-query seeds. This five-search ceiling
is a usage safeguard, not an analytical weight: the highest-scoring X
discoveries are prioritised before the fixed watchlist.

Successful live series are reused for 24 hours. If a later request is blocked or
times out, a market- and timeframe-compatible cache up to seven days old may be
retained with an explicit cached status. Cached data is never presented as a
new live collection.

The provider, requested worldwide market, attempts, API-search count and returned
timeline count are saved with the aggregate snapshot. The API key is never
saved in the snapshot or safe diagnostic report.

## Combined external trend score

The target evidence mix is:

```text
45% Google Trends worldwide
30% open X topic momentum
15% expert-fashion confirmation
10% visual validation from TikTok/Pinterest
```

The current build reserves the visual component for a future governed data
connection. A missing component is excluded and the remaining weights are
renormalised; missing evidence is not silently treated as a zero. The snapshot
stores the effective component weights used for every trend.

Confidence is **High** when Google and open X independently support the same
canonical idea, **Medium** when at least two other components agree, and
**Exploratory** when only one component is available.

## Catalogue matching

The app reads active, in-stock products from the selected source: an uploaded
Shopify/product CSV snapshot or the live read-only Shopify API. It builds a text
representation from title, brand, product type, tags and description, then
combines word and character TF-IDF similarity with exact attribute overlap and
category fit.

The default product opportunity score is:

```text
45% external trend signal
35% catalogue relevance
15% content readiness
 5% catalogue freshness
```

Content readiness checks stock, image, description and merchandising tags.
Because HULA sells one-of-one pre-owned items, inventory quantity `1` is treated
as fully available. Out-of-stock items are excluded.

## What is intentionally missing

The app does not use order or customer data. It therefore does not yet account
for gross margin, sales velocity, conversion, recent campaign fatigue or paid
media performance. The most useful next commercial input is a privacy-safe
weekly product table containing SKU, views, add-to-cart rate, units sold, margin
band and last campaign date.

TikTok Creative Center and Pinterest Trends are represented as a reserved visual
validation component rather than scraped automatically. Connect them only
through a stable, permitted source with clear provenance and comparable weekly
windows.

## Editorial controls

Before using a recommendation:

1. verify stock and condition in Shopify;
2. confirm rarity, collection, runway, celebrity or provenance claims from
   primary product evidence;
3. check margin and current commercial priorities;
4. check whether the piece appeared in a recent campaign;
5. let HULA's team approve the final creative idea and copy.
