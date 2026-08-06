# HULA Trend Intelligence — build 2026.08.06.4

## Delivered architecture

- A publisher-first 21-day scan of Who What Wear, Vogue, ELLE, Harper's
  Bazaar, Marie Claire, Glamour and InStyle.
- Transient, bounded article documents for GPT; weekly snapshots retain only
  metadata and short evidence excerpts, never full article bodies.
- Strict structured extraction of concrete trends and a deterministic
  title/heading fallback.
- Independent publisher-group overlap, conservative alias merging and
  sponsored/noise filters.
- A simple consensus score: 55% overlap, 25% freshness, 10% repetition and
  10% extraction confidence.
- Google validation only for publisher-discovered terms, with recent 90-day
  and contextual 12-month timelines, week-on-week and year-on-year metrics.
- Final priority weighted 70% editorial consensus and 30% Google validation.
- Transparent `Act now`, `Test this week` and `Watch` rules.
- Updated This Week, Editorial Radar and Data & Setup screens.
- Existing catalogue matching, campaign studio, blog writer, Supabase history,
  safe diagnostics and scheduled Wednesday refresh preserved.
- X and Instagram calls removed from the active pipeline and UI.
- Pipeline/cache version 4.0/5.0 guard older snapshots and incompatible caches.

## Verification

```bash
python -m compileall -q app.py src scripts tests
pytest -q
```

The offline suite does not require service credentials.
