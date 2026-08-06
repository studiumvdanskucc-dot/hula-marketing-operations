# Google Trends through SerpApi

Google Trends is an optional measured component. Missing or low-resolution
search data is labelled insufficient and is not interpreted as zero demand.

## Configure

Create a SerpApi key, then add it separately to local `.env`, Streamlit Secrets
and GitHub Actions Secrets wherever that environment needs to refresh:

```toml
SERPAPI_API_KEY = "your-private-key"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
SERPAPI_TIMEOUT_SECONDS = "75"
GOOGLE_TRENDS_PROVIDER = "auto"
GOOGLE_TRENDS_GEO = "WORLDWIDE"
GOOGLE_TRENDS_TIMEFRAME = "today 3-m"
GOOGLE_TRENDS_DISCOVERY_TIMEFRAME = "now 7-d"
GOOGLE_TRENDS_MAX_TERMS = "24"
GOOGLE_TRENDS_CACHE_HOURS = "24"
GOOGLE_TRENDS_STALE_CACHE_DAYS = "3"
```

Worldwide requests omit a country parameter. The app validates aliases across
approximately 90 days so Python can calculate two daily seven-day windows,
the current slope and a longer baseline.

## Interpretation

- Google's 0–100 values are relative to the selected query/time range.
- Current and previous seven-day means drive week-over-week movement.
- A 90-day baseline is used only when enough daily coverage exists.
- Invariant, zero, stale or fewer-than-fourteen-point series return `null`.
- Charts use only Google's original 0–100 values.
- Anchor-calibrated internal values are never presented as measured interest.

A compatible result under 24 hours is reused as live cache. An older last-good
result may be displayed as stale for up to three days, but is excluded from
scoring. A manual Google Trends CSV remains available in **Data & Setup**.

Use **Test Google Trends (Worldwide)** to verify provider, market, timeline
points and request count without exposing the key.
