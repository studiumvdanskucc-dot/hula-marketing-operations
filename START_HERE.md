# Start HULA Trend Intelligence

Build **2026.08.06.3** uses evidence methodology **2.0**.

## First run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m streamlit run app.py
```

Open <http://localhost:8501>, confirm the build number in the sidebar, then
open **Data & Setup**.

The bundled pre-repair snapshot is deliberately shown as **STALE DATA**. This
is a safety guard, not a failed installation. Complete one full refresh before
using the ranking; a successful refresh records discovery pipeline `3.0`.

## Minimum useful configuration

1. Add a HULA catalogue through CSV or the read-only Shopify API.
2. Add `SERPAPI_API_KEY` for measured Google Trends and publisher fallback.
3. Add `OPENAI_API_KEY` for the recommended Luna/Terra/Sol workflow.
4. Optionally add Apify X/Instagram credentials for social evidence.
5. Run `supabase/schema.sql`, then add the Supabase URL and secret if weekly
   history should be durable.

OpenRouter and Gemini are optional fallbacks. The app and scoring engine still
work when no writing model is configured.

## Connection checks

Run these from **Data & Setup**:

1. Test Google Trends (Worldwide)
2. Test Apify task, if configured
3. Test OpenAI Responses (or OpenRouter fallback)
4. Test publisher pages
5. Test hashtag Actor, if configured
6. Test Supabase history, if configured
7. Test Gemini fallback, if configured
8. Run one full refresh

Review the first result in **Trend Radar**. Confirm that every actionable trend
has linked evidence, a visible evidence-coverage percentage, current dates and
no unexplained cap. Missing Google must appear as insufficient data—not zero.
Also inspect **Data & Setup → Live validation queue**: current publisher finds
must appear before any `configured_seed` fallback, and the candidate cache
match must explain whether Google was reused or refreshed.

For hosting and scheduled refresh instructions, use
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
