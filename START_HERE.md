# Start HULA Trend Intelligence

This is build **2026.08.04.1**.

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

Open <http://localhost:8501>, confirm **Build 2026.08.04.1**, then open
**Data & Setup** and run:

1. Test Google Trends (Worldwide)
2. Test Apify task
3. Test OpenRouter
4. Test publisher pages
5. Test hashtag Actor
6. Test Supabase history
7. Test Gemini research
8. Upload/apply the HULA catalogue CSV if Shopify API is not being used
9. Run the full refresh

The first refresh collects the latest fourteen-day X window and explicit trend
evidence through publisher pages, feeds, sitemaps and a domain-restricted
SerpApi fallback. It then validates up to 24 balanced candidates with Google,
compares qualified hashtags on Instagram and can generate the Wednesday blog.
The previous Google cache is deliberately invalidated once. A CSV catalogue
correctly keeps the dataset in Hybrid Mode.

For deployment, follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
