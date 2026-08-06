# Editorial-consensus methodology 3.0

## Purpose

The app answers two separate questions:

1. Which concrete fashion ideas are several recent editorial publishers
   independently covering?
2. Which of those ideas also show useful search movement and fit HULA's current
   catalogue?

HULA inventory never changes whether a trend is considered real. It changes
only the downstream merchandising opportunity.

## Discovery contract

The approved panel is Who What Wear, Vogue, ELLE, Harper's Bazaar, Marie
Claire, Glamour and InStyle. Each weekly run looks back 21 days and attempts
every publisher independently through public index pages, configured current
articles, RSS/sitemaps and a bounded domain search fallback.

The collector does not log in, bypass a paywall or keep full copied articles.
Bounded titles, headings and article paragraphs exist only in memory while GPT
extracts candidates. The saved snapshot contains publisher, title, date, URL,
acquisition route, short excerpt and extraction method.

## Candidate extraction

GPT receives small article batches and a strict schema. It may return only a
specific garment, accessory, silhouette, colour, material or styling idea,
together with a concise Google query and evidence excerpt. Passing mentions,
brands, sale stories, shopping boilerplate and vague labels such as `fashion`,
`style` or `pants` alone are rejected.

If OpenAI is unavailable, explicit titles and trend-labelled headings form a
deterministic fallback. Models may extract and merge aliases, but they never
invent URLs, calculate dates, count publishers or own a score.

## Independent overlap

Evidence is deduplicated by publisher group, article URL and canonical trend.
Editions belonging to one publisher group count once. Conservative alias
groups are applied before breadth is measured; unrelated concepts are never
merged merely because their wording is similar.

The editorial-consensus score is:

```text
55% independent publisher overlap
25% publication freshness
10% repeated article coverage
10% extraction confidence
```

Publisher overlap is the dominant input. Two independent publishers are a
confirmation; three or more create strong consensus. Articles older than the
21-day window cannot contribute.

## Google validation

Only the bounded publisher-discovered shortlist is sent to Google Trends. No
static seed list, related-query expansion, X topic or Instagram hashtag can
introduce a candidate in pipeline 4.0.

For each term the app stores:

- a recent 90-day timeline for readable movement;
- a 12-month context timeline;
- current and previous seven-day averages;
- week-on-week percentage change and recent slope;
- a comparable year-ago-window change when the timeline supports it;
- the exact query, market, provider, fetch time and data-quality state.

The original Google 0–100 index is used for the chart. It is relative interest,
not absolute search volume. Short, invariant, all-zero, stale or otherwise
untrustworthy timelines remain unavailable rather than becoming zero.

## Final priority and actions

```text
Final trend priority = 70% editorial consensus + 30% Google validation
```

When Google is unavailable, the scoring engine renormalises available
non-zero-weight evidence and exposes lower coverage; it does not fabricate a
measurement.

- **Act now**: at least three independent publishers, usable Google movement,
  final priority of at least 70 and no sharp recent decline.
- **Test this week**: at least two independent publishers plus Google, or one
  fresh publisher with at least 20% week-on-week Google growth.
- **Watch**: discovery is visible but not sufficiently confirmed.

The evidence-first confidence model keeps legacy component fields for snapshot
compatibility, but social has weight 0% in this build. X and Instagram are not
queried.

## HULA opportunity

Trend priority is matched separately to the current in-stock catalogue. The
product match uses title, type, vendor, tags and availability; it cannot raise
the underlying editorial or Google evidence.

## Weekly pipeline

1. Read recent approved publisher pages.
2. Extract specific trends from bounded article text.
3. Filter noise and merge conservative aliases.
4. Count independent publisher overlap and freshness.
5. Query Google Trends for that shortlist only.
6. Calculate charts, change metrics, priority and action rules in Python.
7. Match the HULA catalogue and prepare campaign/editorial outputs.
8. Save the evidence snapshot and optional Supabase history.

## Editorial control

The blog writer receives the saved evidence and selected public product fields
only. Confirmed claims require stored evidence URLs. An editor must still
verify stock, condition, links, product details and final wording before
publication.
