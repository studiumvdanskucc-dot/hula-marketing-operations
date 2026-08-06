# HULA Trend Intelligence

Current build: **2026.08.06.3** · methodology **2.0**.

An evidence-first Streamlit workflow for detecting current fashion momentum,
showing exactly why each trend is ranked, matching the opportunity to HULA's
catalogue, and drafting an editorial story from the same stored evidence.

## What changed

The app no longer treats an AI synthesis as measured trend data and no longer
requires Google Trends to be present before a trend can qualify. Every public
score is calculated deterministically in Python from evidence saved with the
weekly snapshot. Missing data stays `null`, remaining component weights are
renormalised, and a separate evidence-coverage score prevents incomplete rows
from looking complete.

Build 2026.08.06.3 also makes live publisher discoveries the input to the
enrichment pipeline. Fresh names are prioritised for targeted X, Google and
Instagram validation; publisher aliases are consolidated before breadth is
counted; and a Google cache is reusable only when its candidate fingerprint
still matches the current live shortlist. Configured example terms are now
fallback fill only and every trend stores its discovery origin.

The dashboard contains:

- **This Week** — fresh publisher discoveries, HULA-ranked opportunities,
  90-day Google context and products.
- **Trend Radar** — confidence, coverage, momentum, component scores, caps,
  warnings, independent domains and linked evidence.
- **Product Match** — in-stock catalogue ranking and the separate HULA
  opportunity score.
- **Campaign Studio** — deterministic or model-assisted campaign briefs.
- **Wednesday Blog** — an editable 700–1,000-word draft constrained to the
  stored trend evidence and selected product facts.
- **Data & Setup** — source health, credential-safe tests, methodology and
  refresh controls.

## Confidence model

| Component | Weight |
| --- | ---: |
| Editorial evidence | 25% |
| Cross-source confirmation | 20% |
| Google Trends momentum | 20% |
| Social momentum | 15% |
| Runway / celebrity activation | 10% |
| Commercial availability | 10% |

Confidence and HULA opportunity are deliberately separate:

```text
HULA opportunity = 65% trend confidence
                 + 25% catalogue match
                 + 10% luxury-resale suitability
```

See [the full methodology](docs/METHODOLOGY.md) for recency factors, source
weights, missing-data behaviour, duplicate handling and confidence caps.

## Collection approach

This is web research and trend aggregation—not unrestricted scraping. The app
prefers public publisher pages, RSS, sitemaps, permitted metadata, short
excerpts and domain-restricted search results. It does not bypass login or
paywalls and does not store copied articles.

The approved editorial/industry panel includes Data But Make It Fashion, Lyst,
Tagwalk, Who What Wear, Who What Wear UK, Vogue, ELLE, Harper's Bazaar,
InStyle, Refinery29, Teen Vogue, Trendalytics and Heuritech. Google Trends,
aggregate Instagram metadata and open X signals remain optional components.

## Model responsibilities

The recommended mixed path is:

- **Luna** — cheap relevance filtering and boilerplate classification;
- **Terra** — candidate extraction and conservative alias merging;
- **Sol** — one final evidence-led synthesis and the editorial draft;
- **Python** — dates, recency decay, time-series calculations, domain counts,
  caps, weights, HULA opportunity, ordering, usage totals and snapshots.

The app uses the OpenAI Responses API with strict structured output when an
`OPENAI_API_KEY` is configured. OpenRouter and Gemini remain optional
fallbacks. A model never owns the numerical confidence score.

## Honest limitations

TikTok, Pinterest and Reddit are not silently inferred: without a permitted
connector their measurements remain absent. External commercial availability
is currently strongest where Lyst or an explicit retail source supplies it.
Publisher blocks, missing dates and low-volume Google queries lower evidence
coverage instead of being filled with model guesses. The bundled demo URLs and
numbers are clearly illustrative and must never be presented as live research.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m streamlit run app.py
```

Seeing **Build 2026.08.06.3** in the sidebar confirms the current copy.
The included August 6 snapshot predates the live-discovery repair and is
intentionally labelled **STALE DATA**. Run one full refresh to create the first
pipeline-3.0 ranking; the old Leopard Print/Mary Janes result is never treated
as a current recommendation.

## Setup order

1. Choose [CSV](docs/CSV_CATALOGUE.md) or [Shopify](docs/SHOPIFY_SETUP.md).
2. Configure [Google Trends](docs/GOOGLE_TRENDS_SETUP.md).
3. Review [approved publisher sources](docs/COMMERCIAL_SOURCES.md).
4. Optionally configure [X](docs/APIFY_SETUP.md) and
   [Instagram aggregates](docs/INSTAGRAM_SETUP.md).
5. Configure the [OpenAI mixed-model path](docs/OPENAI_SETUP.md).
6. Run the [Supabase schema](docs/SUPABASE_SETUP.md) for durable snapshots.
7. Follow the [deployment guide](docs/DEPLOYMENT.md).

Streamlit Secrets and GitHub Actions Secrets are separate. Add credentials to
both only when both the dashboard and scheduled workflow need them. Never
commit `.env`, `.streamlit/secrets.toml`, API keys or raw catalogue exports.

## Verification

```bash
python -m compileall -q app.py src scripts tests
pytest -q
```

The suite is offline and uses no real API credentials.
