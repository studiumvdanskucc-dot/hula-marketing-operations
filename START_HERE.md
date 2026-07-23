# Start HULA Trend Intelligence

This is build **2026.07.22.8**. The same build number appears at the bottom of
the app sidebar.

## One new Google Trends secret

Google Trends no longer uses the Apify Google Actor or the unreliable direct
Google webpage request. Create a free SerpApi account, copy its API key and add:

```toml
SERPAPI_API_KEY = "your-key"
```

Keep your existing Apify key and task ID: they still power the X listening
layer. See [Google Trends setup](docs/GOOGLE_TRENDS_SETUP.md) for the exact
clicks and usage limits.

## Run locally

```bash
cd ~/Downloads/hula_trend_intelligence_GLOBAL_FASHION
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If another copy is already running, stop it with `Control + C` first. Open
<http://localhost:8501>, confirm **Build 2026.07.22.8**, then open **Data &
Setup** and run these checks in order:

1. **Test Google Trends (Worldwide)**
2. **Test Apify task**
3. **Test OpenRouter**
4. Upload and apply the HULA catalogue CSV if you are not using Shopify API
5. Run the full refresh

A CSV catalogue correctly keeps the dataset in Hybrid Mode. Google Trends uses
at most five small API searches for the first full refresh and then reuses its
24-hour cache.

For GitHub and Streamlit Community Cloud, follow
[the deployment guide](docs/DEPLOYMENT.md).
