# Google Ads API — read-only setup

Build pin: **v25**, released 22 July 2026. Recheck the
[official release notes](https://developers.google.com/google-ads/api/docs/release-notes)
and deprecation schedule before deployment.

This release contains a configuration/health shell only; it does not run a live
report or mutation.

## HULA owner actions

1. Confirm manager/login customer ID, client customer ID, timezone, currency,
   conversion actions, attribution models and account hierarchy.
2. Obtain a HULA-owned developer token and OAuth authorization.
3. Grant reporting access only. Do not authorize a general-purpose shared user.
4. Record brand/non-brand/competitor classification rules outside campaign names.

```dotenv
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
GOOGLE_ADS_CUSTOMER_ID=
GOOGLE_ADS_API_VERSION=v25
GOOGLE_ADS_READ_ONLY=true
```

Future reporting must use GAQL, paginate, capture conversion action and source
settings, and respect quota/rate limits. No mutate operation, budget change,
bidding change, conversion-setting change or status change is allowed in the
first release.
