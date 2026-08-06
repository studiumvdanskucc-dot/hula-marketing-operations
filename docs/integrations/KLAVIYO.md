# Klaviyo — read-only setup

Build pin: stable revision **2026-01-15**. Klaviyo supports revisions for a
limited period; recheck the [versioning policy](https://developers.klaviyo.com/en/docs/api_versioning_and_deprecation_policy)
and account revision usage before release.

The newer 2026 campaign endpoints were still documented as beta/pre-release at
build time, so they are deliberately not used. This release contains a
configuration/health shell only.

## HULA owner actions

1. Confirm account ID, timezone/currency, lists, segments, flows, campaigns,
   conversion metric, attribution window, consent and suppression model.
2. Create a dedicated private key with only required read scopes.
3. Install it directly in deployment secrets and record its owner/rotation date.

```dotenv
KLAVIYO_PRIVATE_API_KEY=
KLAVIYO_ACCOUNT_ID=
KLAVIYO_API_REVISION=2026-01-15
KLAVIYO_READ_ONLY=true
```

Future syncs must use the reporting endpoints intended to align with the
Klaviyo UI, store the revision and attribution settings, paginate links and
respect rate-limit headers. This release cannot create, activate or send a
campaign or flow.
