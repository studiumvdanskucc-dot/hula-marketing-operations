# Meta Marketing API — read-only setup

Build pin: **v26.0**, released 29 July 2026. Recheck the
[official Marketing API versioning page](https://developers.facebook.com/documentation/ads-commerce/marketing-api/overview/versioning)
before deployment.

This release contains a configuration/health shell only; dashboard values are
clearly labelled fixtures.

## HULA owner actions

1. Confirm Business portfolio, ad account, Page, Instagram business account,
   Pixel/dataset and catalog IDs plus account currency/timezone/attribution.
2. Use a HULA-owned developer app and system user with assigned assets.
3. Install the token directly in the secret manager.
4. Begin with `ads_read` and only necessary business/page read permissions. Do
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

Future reporting must retain action type, attribution setting, breakdown,
time range and data freshness. It must not infer prohibited or sensitive
attributes. No audience upload, creative/ad creation, budget or status mutation
exists in this release.
