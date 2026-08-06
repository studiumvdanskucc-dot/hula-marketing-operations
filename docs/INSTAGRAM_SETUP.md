# Aggregate Instagram hashtag comparison

Instagram is a small, directional validation component—not a discovery source.
The app uses Apify's maintained
`apify/instagram-hashtag-analytics-scraper` with the same `APIFY_TOKEN` used by
X. It does not require an Instagram login.

The app first qualifies specific trend names through approved commercial
websites, X and Google. It then converts up to eight qualified names into
hashtags and retrieves only:

- total public uses;
- estimated posts per day when available;
- aggregate related-hashtag counts.

Top and latest post collection are explicitly disabled. The pipeline never
receives Instagram captions, usernames, accounts, images or videos.

## Settings

```toml
INSTAGRAM_ENABLED = "true"
APIFY_INSTAGRAM_ACTOR_ID = "apify~instagram-hashtag-analytics-scraper"
INSTAGRAM_HASHTAG_MAX_TERMS = "8"
INSTAGRAM_MAX_TOTAL_CHARGE_USD = "0.25"
```

The Actor input always includes:

```json
{
  "includeLatestPosts": false,
  "includeTopPosts": false
}
```

The score compares hashtags within the same refresh. Posts per day carries the
most weight when available; otherwise the log-scaled lifetime count is used.
This is descriptive metadata. It does not prove that a hashtag caused reach,
sales or search demand.

Use **Data & Setup → Test hashtag Actor** to verify access without starting a
paid run. That button checks Actor availability only. The full refresh records
requested hashtags, returned aggregate dataset rows, normalised hashtags,
missing hashtags and the returned top-level field names. Build 2026.08.06.3
accepts the Actor's `searchTerm` field as well as `name`, `id` and `hashtag`, so
a valid dataset row is no longer silently discarded because of its identifier
field.

Official Actor page:
<https://apify.com/apify/instagram-hashtag-analytics-scraper>
