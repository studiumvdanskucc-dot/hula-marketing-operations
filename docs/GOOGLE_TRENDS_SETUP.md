# Google Trends through SerpApi

Google Trends validates terms already found in recent fashion articles. It no
longer discovers extra seeds or related queries.

## Configure

Add the key separately to local `.env`, Streamlit Secrets and GitHub Actions
Secrets wherever that environment performs a refresh:

```toml
SERPAPI_API_KEY = "your-private-key"
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
SERPAPI_TIMEOUT_SECONDS = "75"
GOOGLE_TRENDS_PROVIDER = "auto"
GOOGLE_TRENDS_GEO = "WORLDWIDE"
GOOGLE_TRENDS_CONTEXT_TIMEFRAME = "today 12-m"
GOOGLE_TRENDS_RECENT_TIMEFRAME = "today 3-m"
GOOGLE_TRENDS_RELATED_QUERIES = "false"
GOOGLE_TRENDS_MAX_TERMS = "20"
GOOGLE_TRENDS_MAX_DISCOVERY_SEEDS = "0"
GOOGLE_TRENDS_RELATED_VALIDATION_TERMS = "0"
GOOGLE_TRENDS_CACHE_HOURS = "24"
GOOGLE_TRENDS_STALE_CACHE_DAYS = "3"
```

Worldwide requests omit a country parameter. The exact GPT-selected term is
measured twice: a recent timeline for readable movement and a 12-month context
for seasonality and year-ago comparison.

## Interpretation

- Google's 0–100 values are relative to the selected query and period.
- Current and previous seven-day means drive week-on-week movement.
- The 12-month series supplies longer context and a comparable year-ago window
  when resolution permits.
- Invariant, zero, stale or insufficient series remain unavailable.
- Charts preserve Google's original 0–100 values.
- A cached result is reused only when the current publisher shortlist and
  exact queries produce the same fingerprint.

Use **Data & Setup → Test Google Trends** to verify provider, market and live
timeline points without exposing the key. Every trend screen also includes a
link that opens the exact query in Google Trends.
