# Google Merchant API — read-only setup

Build pin: **Merchant API v1**. v1beta was discontinued; see
[official latest updates](https://developers.google.com/merchant/api/latest-updates).

This release contains a configuration/health shell only.

## HULA owner actions

1. Confirm Merchant account/subaccount, data source/feed, linked Ads account,
   product IDs and current feed-management owner.
2. Complete Merchant API developer registration where required.
3. Authorize OAuth/service-account access and grant only read permissions.

```dotenv
MERCHANT_CENTER_ACCOUNT_ID=
GOOGLE_OAUTH_ACCESS_TOKEN=
MERCHANT_READ_ONLY=true
```

Future reporting covers product status, issues, feed freshness and mismatches.
Do not replace the current feed-management process until its ownership and rules
are understood. No product/feed mutation exists in this release.
