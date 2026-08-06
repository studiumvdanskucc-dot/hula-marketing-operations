# HULA Trend Intelligence — build 2026.08.06.3

## Delivered architecture

- Methodology 2.0 with six deterministic Python components and documented
  source/recency weights.
- Missing-component renormalisation plus a separate data-completeness score.
- Duplicate/syndication exclusion, contradiction penalties and the requested
  one-source, product-launch, low-evidence and outdated-evidence caps.
- Daily Google calculations for the current week, previous week, seven-day
  slope and optional 90-day breakout baseline.
- Structured trend objects with aliases, momentum, component breakdown,
  metrics, domains, evidence rows, warnings and HULA opportunity.
- Expanded publisher panel including Harper's Bazaar, InStyle, Refinery29 and
  Teen Vogue.
- Live-first enrichment plan: fresh publisher names drive targeted X, Google
  and Instagram checks while configured terms are fallback fill only.
- Candidate-aware Google cache, conservative publisher-alias consolidation and
  visible per-trend discovery provenance.
- Separate fresh-discovery queue so a new one-source signal is visible without
  being misrepresented as action-ready.
- Optional OpenAI Responses connector using Luna, Terra and Sol with strict
  JSON schemas and per-call usage/cost records.
- Evidence-locked blog generation: no live-search claims and no invented
  sources or measurements.
- A runtime guard that demotes the included pre-repair snapshot to historical
  context until a complete discovery-pipeline-3.0 refresh succeeds.
- Updated Streamlit views, examples, secrets template, weekly workflow,
  documentation and regression tests.

## Decision rules

`Act now` requires high confidence, at least 65% evidence coverage, four
evidence items and three independent domains. `Test this week` requires at
least 55 confidence, 40% coverage, three evidence items and two domains.
Google may contribute, but it is not mandatory.

## Verification

Run:

```bash
python -m compileall -q app.py src scripts tests
pytest -q
```

No real service credentials are required for the test suite.
