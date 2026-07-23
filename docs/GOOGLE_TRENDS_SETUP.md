# Google Trends through SerpApi

Build `2026.07.22.8` uses worldwide Google Trends through SerpApi.
SerpApi makes the Google-facing request and returns structured Trends data, so
the Streamlit app does not launch another Actor and does not connect to
`trends.google.com` directly.

## Create the free key

1. Open <https://serpapi.com/users/sign_up>.
2. Create a free account.
3. Open the SerpApi dashboard.
4. Copy the private API key.
5. Add it locally to `.env`:

   ```env
   SERPAPI_API_KEY=your-key
   ```

6. In Streamlit Community Cloud, add the same value in **App settings →
   Secrets**:

   ```toml
   SERPAPI_API_KEY = "your-key"
   ```

7. In GitHub, add it separately under **Repository → Settings → Secrets and
   variables → Actions** with the name `SERPAPI_API_KEY`.

Never commit the key to the repository.

## Bounded weekly use

The app omits the country parameter so Google Trends returns worldwide data.
One full live refresh is capped at:

- three Interest over time comparisons, covering up to 12 fashion terms;
- two related-query searches;
- five SerpApi searches in total.

The small connection test uses one search. A successful full result is cached
for 24 hours, so repeated refresh clicks during the same day do not spend more
searches. A compatible last-good result can be retained for seven days if a
later API call fails.

The current SerpApi free plan includes 250 searches per month. A weekly refresh
uses about 20 searches per month; even one full refresh every day remains below
the current free allowance.

## Settings

The supplied defaults are:

```toml
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
SERPAPI_TIMEOUT_SECONDS = "75"
GOOGLE_TRENDS_PROVIDER = "auto"
GOOGLE_TRENDS_GEO = "WORLDWIDE"
GOOGLE_TRENDS_TIMEFRAME = "today 3-m"
GOOGLE_TRENDS_MAX_TERMS = "12"
GOOGLE_TRENDS_MAX_DISCOVERY_SEEDS = "2"
GOOGLE_TRENDS_CACHE_HOURS = "24"
GOOGLE_TRENDS_STALE_CACHE_DAYS = "7"
```

`auto` means SerpApi. It deliberately does not silently return to the failing
Google webpage route. A manual Google Trends CSV upload remains available in
Data & Setup if the API allowance is ever exhausted.

## Verify it

Open **Data & Setup → Connection checks → Test Google Trends (Worldwide)**. A successful
message must say:

- market `Worldwide`;
- provider `SerpApi Google Trends`;
- a positive timeline-point count;
- one API search.

The full refresh status and safe diagnostic report also record the provider,
market, term count, request count and cache age without including the API key.

## Common errors

- `SERPAPI_API_KEY is missing`: add the key in the environment where the app is
  running and reboot the Streamlit app.
- `rejected the API key`: copy a new key from the SerpApi dashboard and replace
  the old secret.
- `request allowance`: wait for the plan allowance to reset or use the manual
  Trends CSV importer.
- An Apify 402 memory error now concerns X searches only. Google Trends uses no
  Apify memory in this build.
