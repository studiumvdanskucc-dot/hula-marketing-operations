# Methodology 2.0

## Purpose

The system answers two different questions:

1. How confidently is a specific fashion trend gaining momentum now?
2. If it is real, how useful is it for HULA's current luxury-resale catalogue?

The first answer must not increase merely because HULA owns matching stock.
This is decision support, not a sales forecast.

## Evidence contract

Every trend stores its aliases, score breakdown, Google measurements,
independent-domain count, evidence count, linked evidence, warnings and dates.
Every URL must come from collected input. Models may classify relevance,
merge aliases and write explanations; they may not invent a source or number.

Duplicate URLs are counted once. Identical substantial titles on different
domains are treated as likely syndication and the higher-authority copy is
retained. Contradictory evidence remains visible and reduces confidence.

## Source authority

| Source | Weight |
| --- | ---: |
| Data But Make It Fashion | 1.50 |
| Lyst | 1.45 |
| Tagwalk | 1.40 |
| Who What Wear / UK | 1.30 |
| Vogue / ELLE / Harper's Bazaar | 1.20 |
| InStyle / Refinery29 / recognised fashion trade | 1.10 |
| Recognised general news | 0.70 |
| Unknown blog, aggregator or unverified account | 0.30 |

Authority does not override relevance: the evidence must specifically support
the identified trend.

## Recency

| Age | Factor |
| --- | ---: |
| Today | 1.00 |
| 1–3 days | 0.85 |
| 4–7 days | 0.65 |
| 8–14 days | 0.35 |
| More than 14 days | 0.10 |

An unknown date is deliberately weaker and never treated as current.

## Component scores

### Editorial evidence — 25%

Relevant original mentions are weighted by source authority, recency and
evidence relevance. The score reaches 100 at eight weighted mentions. Reprints
and shopping-card repetition do not add independent mentions.

### Cross-source confirmation — 20%

Independent authoritative domains map to 20, 40, 60, 75, 88 and 100 for one
through six-or-more domains. A small diversity bonus rewards evidence across
editorial, industry, runway, retail, search and social types.

### Google Trends momentum — 20%

The app retains the original Google 0–100 values and uses daily measurements:

```text
35% current seven-day mean
35% week-over-week growth
20% current seven-day regression slope
10% breakout versus the 90-day mean, when available
```

Google values are relative interest, not absolute volume. Fewer than fourteen
daily points, invariant/zero timelines or stale results produce `null`, not
zero. The public output includes both weekly means, percentage change, slope
and the optional 90-day baseline.

### Social momentum — 15%

```text
40% mention growth
30% engagement velocity
20% creator diversity
10% platform diversity
```

Evidence quality discounts duplicated, promotional or author-dominated X
conversation. Aggregate Instagram metadata is directional and capped; one
viral post is not treated as broad adoption.

### Runway / celebrity activation — 10%

The component measures current runway recurrence, independent reporting and
repeated adoption. A single old runway reference or isolated appearance stays
weak. Named-person claims must be supported by the exact supplied evidence.

### Commercial availability — 10%

Independent current retail domains distinguish isolated availability from
several recognised channels or widespread luxury/high-street adoption. HULA's
own catalogue is excluded from this external-confidence component.

## Missing data and completeness

When a component is unavailable, its value remains `null`. The score is
calculated from available components after proportionally redistributing their
weights. Evidence coverage is reported separately as the sum of the original
weights present. Therefore a 70-confidence result with 45% coverage is visibly
different from 70 confidence with 90% coverage.

## Confidence caps

- One independent source: maximum 55.
- Only an isolated product launch/retail signal: maximum 50.
- Fewer than three independent evidence items: maximum 60.
- Nothing published or measured in the current fourteen days: maximum 45.
- Duplicate/syndicated rows are removed before scoring.
- Contradictory evidence lowers the score.

The action gate additionally requires current evidence, at least three items
and two independent domains. `Act now` requires 75 confidence, 65% coverage,
four items and three domains.

## Momentum labels

The average of available Google and social week-over-week changes maps to
`breakout`, `accelerating`, `steadily rising`, `stable`, `cooling`, `declining`
or `insufficient data`.

## HULA opportunity

```text
65% trend confidence
25% current HULA catalogue match
10% luxury-resale suitability
```

This score changes merchandising priority but never changes trend confidence.

## Weekly pipeline

1. Collect permitted source URLs and metadata.
2. Retain titles, dates, selected headings and short evidence summaries.
3. Collect Google daily series separately.
4. Collect available aggregate social, runway and retail signals.
5. Extract specific candidates and reject broad/non-fashion phrases.
6. Merge true aliases without merging a whole aesthetic.
7. Produce a short evidence-led synthesis.
8. Calculate every number, cap and ordering in Python.
9. Match the HULA catalogue and calculate HULA opportunity.
10. Save the full evidence snapshot and optionally draft the blog from it.

## Editorial control

The blog writer receives stored trend evidence and selected public product
fields only. It does not use live search grounding. Confirmed claims require
valid source indices; unsupported exact claims are downgraded and kept outside
publishable copy. An editor must still verify stock, condition, links, product
details and final wording before publication.
