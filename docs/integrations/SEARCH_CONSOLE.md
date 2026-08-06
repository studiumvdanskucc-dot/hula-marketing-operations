# Google Search Console — read-only setup

The connector uses Search Analytics query with OAuth read-only authorization.
See [Search Analytics query](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)
and [OAuth scopes](https://developers.google.com/webmaster-tools/v1/how-tos/authorizing).

## HULA owner actions

1. Confirm the exact property: `sc-domain:thehula.com` or a precise URL-prefix.
2. Enable Search Console API in the HULA Google Cloud project.
3. Grant the OAuth identity access to the property.
4. Request only `https://www.googleapis.com/auth/webmasters.readonly`.

```dotenv
GSC_SITE_URL=sc-domain:thehula.com
GOOGLE_OAUTH_ACCESS_TOKEN=
GSC_READ_ONLY=true
```

The client paginates query/page/device/country/day rows with `startRow`. Search
Console can prioritize top rows and has reporting lag; grouping also changes
metric interpretation. Store freshness, dimensions and limitations with every
sync. FAQ search appearance support was scheduled for deprecation in August
2026 and must not be hardcoded into new reporting.
