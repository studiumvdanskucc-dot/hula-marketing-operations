# Start HULA Trend Intelligence

Build **2026.08.06.4** uses the publisher-first editorial-consensus pipeline
**4.0**.

## First run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m streamlit run app.py
```

Open <http://localhost:8501>, confirm **Build 2026.08.06.4** in the sidebar and
open **Data & Setup**.

## Minimum useful configuration

1. Add HULA products with a CSV or the read-only Shopify API.
2. Add `OPENAI_API_KEY` so GPT can scan bounded recent-article text.
3. Add `SERPAPI_API_KEY` for the recent and 12-month Google Trends plots.
4. Optionally add Supabase for durable weekly history and Gemini as the
   evidence-locked writing fallback.

No Apify, X or Instagram credential is needed or used by this build.

## First live refresh

In **Data & Setup**:

1. Test publisher pages.
2. Test OpenAI article extraction.
3. Test Google Trends.
4. Apply the catalogue source.
5. Run the editorial-consensus refresh.

Then open **Editorial Radar**. Check that each trend has a specific name,
recent linked articles, a visible independent-publisher count and the exact
Google query. A two- or three-publisher overlap should outrank a similar
single-publisher find unless the latter has unusually strong Google growth.

The bundled pre-4.0 snapshot is deliberately marked **STALE DATA**. Complete
one refresh before using the ranking for a real decision.

For hosting and scheduled refresh instructions, use
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
