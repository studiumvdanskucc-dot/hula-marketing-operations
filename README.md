# HULA Trend Intelligence

Current build: **2026.08.06.4** · editorial-consensus pipeline **4.0**.

This Streamlit app turns recent fashion-editorial coverage into a weekly HULA
decision board. It reads trend articles published during the last 21 days,
uses structured GPT extraction to identify concrete fashion ideas, rewards
independent publisher overlap, validates only those ideas in Google Trends and
then matches them to HULA's catalogue.

X and Instagram are not queried by pipeline 4.0. Their legacy connectors remain
in the repository only so older snapshots and tests can still be read safely.

## How discovery works

1. Read recent pages from Who What Wear, Vogue, ELLE, Harper's Bazaar, Marie
   Claire, Glamour and InStyle.
2. Extract specific garments, accessories, silhouettes, colours, materials or
   styling ideas with a strict OpenAI schema. Titles and trend headings provide
   a deterministic fallback when the model is unavailable.
3. Merge conservative aliases and count each independent publisher group once.
4. Rank editorial consensus from publisher overlap, freshness, repeated article
   coverage and extraction confidence.
5. Send the bounded publisher shortlist—not a static seed list—to Google
   Trends. Save both a recent 90-day chart and 12-month context.
6. Combine editorial consensus (70%) with available Google validation (30%),
   apply transparent action rules and match in-stock HULA products.

## Dashboard

- **This Week** — ranked opportunities, exact Google query, week-on-week and
  year-on-year movement, charts, article proof and matched products.
- **Editorial Radar** — publisher health, the full consensus inventory and a
  per-trend evidence deep dive.
- **Product Match** — current catalogue opportunities.
- **Campaign Studio** — campaign briefs based on the ranked snapshot.
- **Wednesday Blog** — an editable evidence-locked draft.
- **Data & Setup** — the four-step method, publisher panel, connection checks,
  catalogue controls, safe diagnostics and the live refresh.

## Ranking

```text
Final trend priority = 70% editorial consensus + 30% Google validation

Editorial consensus = 55% independent publisher overlap
                    + 25% publication freshness
                    + 10% repeated article coverage
                    + 10% extraction confidence
```

Google's original 0–100 index is preserved for charts. Missing or unusable
Google data remains unavailable rather than becoming zero. Models extract and
explain; deterministic Python owns dates, overlap counts, time-series metrics,
scores, action rules and ordering.

See [the methodology](docs/METHODOLOGY.md) for the full data contract.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m streamlit run app.py
```

Open **Data & Setup**, add a CSV catalogue or configure read-only Shopify, then
configure `OPENAI_API_KEY` and `SERPAPI_API_KEY`. Run one complete refresh.
Seeing **Build 2026.08.06.4** in the sidebar confirms the correct source.

An older saved snapshot is deliberately labelled **STALE DATA** until the
first pipeline-4.0 refresh succeeds. It is never promoted as a current result.

## Setup order

1. Choose [CSV](docs/CSV_CATALOGUE.md) or [Shopify](docs/SHOPIFY_SETUP.md).
2. Configure [OpenAI article extraction](docs/OPENAI_SETUP.md).
3. Configure [Google Trends](docs/GOOGLE_TRENDS_SETUP.md).
4. Review the [publisher panel](docs/COMMERCIAL_SOURCES.md).
5. Optionally configure [Supabase](docs/SUPABASE_SETUP.md) and the Gemini
   writing fallback.
6. Follow the [deployment guide](docs/DEPLOYMENT.md).

Streamlit Secrets and GitHub Actions Secrets are separate. Never commit `.env`,
`.streamlit/secrets.toml`, API keys or raw catalogue exports.

## Verification

```bash
python -m compileall -q app.py src scripts tests
pytest -q
```

The suite is offline and uses no real API credentials.
