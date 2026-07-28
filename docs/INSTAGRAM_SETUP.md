# Approved Instagram fashion panel

The app uses Apify's maintained `apify/instagram-post-scraper` Actor with the
same `APIFY_TOKEN` used by the X connector. The approved public profiles do not
require a separate Instagram login.

## Default panel

Priority, 3× evidence weight:

- `databutmakeitfashion`
- `tagwalk`
- `whowhatwear`
- `whowhatwear.uk`
- `lyst`

Specialist, 2× evidence weight:

- `voguerunway`
- `wgsn`
- `trendalytics`
- `edited_hq`
- `heuritech`

## Settings

```toml
INSTAGRAM_ENABLED = "true"
APIFY_INSTAGRAM_ACTOR_ID = "apify~instagram-post-scraper"
INSTAGRAM_RESULTS_PER_PROFILE = "15"
INSTAGRAM_MAX_TOTAL_CHARGE_USD = "0.75"
INSTAGRAM_VISUAL_MAX_POSTS = "10"
INSTAGRAM_PRIORITY_ACCOUNTS = "databutmakeitfashion,tagwalk,whowhatwear,whowhatwear.uk,lyst"
INSTAGRAM_SPECIALIST_ACCOUNTS = "voguerunway,wgsn,trendalytics,edited_hq,heuritech"
```

The Actor input skips pinned posts, requests only posts newer than the
fourteen-day cutoff and limits results per profile. The app validates every
timestamp again, removes duplicates and reports profiles with no accepted
results. Start with these caps and inspect real Apify usage before increasing
them.

Use **Data & Setup → Test Instagram Actor** to verify the Actor without
starting a paid scrape.

Official Actor page: <https://apify.com/apify/instagram-post-scraper>
