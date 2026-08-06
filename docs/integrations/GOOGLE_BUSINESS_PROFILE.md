# Google Business Profile — read-only setup

The build targets Performance API v1 and the currently documented reviews
resource. API access can require approval and can have zero quota until granted.
See the [Business Profile API overview](https://developers.google.com/my-business)
and [quota limits](https://developers.google.com/my-business/content/limits).

This release contains a configuration/health shell only.

## HULA owner actions

1. Confirm account ID and canonical Central/Quarry Bay location IDs/names.
2. Add an approved OAuth user/application and complete basic API access.
3. Grant read access first.
4. Confirm ownership and any agency-managed locations before transition.

```dotenv
GBP_ACCOUNT_ID=
GBP_LOCATION_IDS=
GOOGLE_OAUTH_ACCESS_TOKEN=
GBP_READ_ONLY=true
```

Future reads include location performance and reviews. Review-response text may
be drafted internally, but this release cannot post a public reply.
