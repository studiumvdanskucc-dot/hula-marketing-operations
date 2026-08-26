# Meta Marketing API — read-only setup

Build pin: **v26.0**, released 29 July 2026. Recheck the
[official Marketing API versioning page](https://developers.facebook.com/documentation/ads-commerce/marketing-api/overview/versioning)
before deployment.

This release contains a real read-only account test and campaign-insights
client. Dashboard values remain fixtures until HULA creates a production token,
assigns the ad account to the chosen system user/app, runs a fixed-range sync
and reconciles it.

The 26 August audit confirmed that **The Hula** owns the checked portfolio, ad
account, Page, Instagram account and dataset/pixel, and that HULA Marketing has
full access. It did not assign reporting assets or create an API token.

## HULA owner actions

1. Create or select a clearly named HULA production developer app; do not use
   the generic existing app named `test` without first documenting its purpose.
2. Create or select a dedicated HULA reporting system user; assign only the
   HULA ad account and, if later required, the dataset.
3. Generate a system-user token with `ads_read`. Store it directly in the
   deployment secret manager—never in Git or chat.
4. Record the numeric ad-account ID, currency, timezone and account attribution
   setting; then use Settings → Connections to run the account test.
5. Run one fixed seven-day read sync and reconcile spend, campaign IDs,
   purchases and claimed value against Meta Ads Manager. Do
   not request `ads_management` for release one.

```dotenv
META_SYSTEM_USER_ACCESS_TOKEN=
META_AD_ACCOUNT_ID=act_
META_PAGE_ID=
META_INSTAGRAM_ACCOUNT_ID=
META_PIXEL_ID=
META_CATALOG_ID=
META_API_VERSION=v26.0
META_READ_ONLY=true
```

The connector requests campaign/day insights using a normalized `7d_click`
window. When Meta returns several purchase action types, it selects one by a
documented priority rather than summing overlapping purchase rows. Reporting
retains the account attribution setting, time range and freshness. It must not
infer prohibited or sensitive attributes. No audience upload, creative/ad
creation, budget or status mutation exists in this release.
