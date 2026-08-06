# Deploy with GitHub and Streamlit Community Cloud

This build does not need Render. GitHub stores the code and last aggregate
snapshot; Streamlit Community Cloud hosts the dashboard.

## 1. Test locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m streamlit run app.py
```

Complete `.env`, run `supabase/schema.sql`, then confirm all external
connection checks pass. `.env` is ignored by Git and must never be committed.

## 2. Create a private GitHub repository

Create a new private repository named `hula-trend-intelligence`. Do not mix the
dashboard into the existing `web` repository used by `studiumvdansku.cc`.

From this extracted project folder:

```bash
git init
git branch -M main
git add .
git status
git commit -m "Deploy HULA Trend Intelligence"
git remote add origin https://github.com/studiumvdanskucc-dot/hula-trend-intelligence.git
git push -u origin main
```

Before committing, `git status` must not contain `.env`,
`.streamlit/secrets.toml`, `.venv`, API keys or a raw catalogue CSV.

## 3. Add GitHub Actions secrets

Open **Repository → Settings → Secrets and variables → Actions → New repository
secret**. Add:

- `SERPAPI_API_KEY`
- `APIFY_TOKEN`
- `APIFY_X_TASK_ID`
- `APIFY_X_TASK_INPUT_JSON` with `{}`
- `OPENAI_API_KEY` for the recommended Luna/Terra/Sol path
- `OPENROUTER_API_KEY`
- `OPENROUTER_SITE_URL` after Streamlit gives you the final URL
- `SUPABASE_URL`
- `SUPABASE_SECRET_KEY`
- `GEMINI_API_KEY`

If the live Shopify API is configured, also add `SHOPIFY_SHOP`,
`SHOPIFY_CLIENT_ID` and `SHOPIFY_CLIENT_SECRET`.

Then open **Settings → Actions → General → Workflow permissions**, choose
**Read and write permissions**, and save. The included workflow needs this to
commit `data/latest_snapshot.json`.

The workflow runs each Wednesday at 09:17 Hong Kong time. Run it once manually
from **Actions → Weekly HULA trend refresh → Run workflow** after all secrets
are added.

## 4. Deploy the Streamlit app

1. Open <https://share.streamlit.io/> and sign in with GitHub.
2. Select **Create app**.
3. Choose `studiumvdanskucc-dot/hula-trend-intelligence`.
4. Choose branch `main` and entrypoint `app.py`.
5. Open **Advanced settings → Secrets**.
6. Copy `.streamlit/secrets.toml.example` into the box and replace the
   placeholders. At minimum, add the catalogue route, SerpApi, OpenAI and
   team-password values. Apify, Supabase, OpenRouter and Gemini are optional.
7. Select **Deploy**.
8. Open the final URL and confirm the sidebar says **Build 2026.08.06.3**.

The Streamlit and GitHub secrets stores are separate. The weekly Action needs
its own copy of every secret used during an automated refresh.

## 5. Understand the 12-hour sleep rule

Community Cloud sleeps an app after 12 hours with no traffic. This is a rolling
inactivity timer, not one fixed daily window:

- opening or using the app keeps it awake and starts a new inactivity period;
- if it is already asleep, any authorised viewer can select **Yes, get this app
  back up!**;
- after it wakes, the app operates normally and can sleep again only after
  another 12 traffic-free hours.

You do not need to leave a browser tab open tonight. Deploy it, then open it in
the morning. If more than 12 hours have passed, wake it with the button.

Code, GitHub data and configured Streamlit secrets remain available. Files
created only inside a running Streamlit container are not durable, so the
scheduled GitHub workflow—not a manual in-app refresh—should be the permanent
weekly source of `data/latest_snapshot.json`.

## 6. First production check

1. Wake/open the Streamlit app.
2. Confirm the team password works.
3. Confirm **Build 2026.08.06.3**.
   The included pre-repair snapshot may initially say **STALE DATA**; this is
   intentional and prevents its old ranking from being treated as current.
4. Run **Test Google Trends (Worldwide)**; it should report SerpApi and one search.
5. Run the publisher-page and OpenAI tests, plus any configured X, hashtag,
   Supabase, OpenRouter or Gemini fallback tests.
6. Run the GitHub workflow manually.
7. Confirm it creates a `data: refresh weekly HULA trend snapshot` commit.
8. Reopen the dashboard and confirm the refresh timestamp and live sources.

The app sleeping between weekly visits is safe. The only inconvenience is the
one-click wake page on the first visit after a quiet period.
