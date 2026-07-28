# Start HULA Trend Intelligence

This is build **2026.07.28.1**.

## Before the first refresh

1. Open `supabase/schema.sql`.
2. Copy the complete SQL into **Supabase → SQL Editor** and run it once.
3. Keep the `SUPABASE_URL`, `SUPABASE_SECRET_KEY` and `GEMINI_API_KEY` values
   you already added to Streamlit Secrets.
4. Add those same three values to **GitHub → Repository settings → Actions
   secrets**. Streamlit and GitHub do not share secrets.
5. Also confirm `SERPAPI_API_KEY`, `APIFY_TOKEN`, `APIFY_X_TASK_ID` and
   `OPENROUTER_API_KEY` exist in both environments.

Never paste complete keys into source files or commit them.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m streamlit run app.py
```

Open <http://localhost:8501>, confirm **Build 2026.07.28.1**, then open
**Data & Setup** and run:

1. Test Google Trends (Worldwide)
2. Test Apify task
3. Test Instagram Actor
4. Test OpenRouter
5. Test Supabase history
6. Test Gemini research
7. Upload/apply the HULA catalogue CSV if Shopify API is not being used
8. Run the full refresh

The first refresh collects the latest fourteen-day X and Instagram windows,
discovers fresh Google queries, validates the candidates and can generate the
Wednesday blog. A CSV catalogue correctly keeps the dataset in Hybrid Mode.

For deployment, follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
