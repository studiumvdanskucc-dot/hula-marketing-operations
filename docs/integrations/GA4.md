# Google Analytics 4 Data API — read-only setup

The connector uses the official Data API v1 `runReport` method through its
documented REST `v1beta/properties/{property}:runReport` resource path. See the
[GA4 Data API overview](https://developers.google.com/analytics/devguides/reporting/data/v1).

## HULA owner actions

1. Confirm numeric property ID, property timezone/currency, reporting identity,
   web stream ID, custom definitions and ecommerce event map.
2. Enable Google Analytics Data API in a HULA-owned Google Cloud project.
3. Grant the selected service identity or OAuth user only the required Viewer or
   Analyst access.
4. Configure a secure production OAuth/service-account flow. The access-token
   environment value below is intended for a short local connection test, not
   durable production storage.

```dotenv
GA4_PROPERTY_ID=
GOOGLE_OAUTH_ACCESS_TOKEN=
GA4_READ_ONLY=true
```

The first sync reads date, default channel group, sessions, active users,
engaged sessions, ecommerce purchases and total revenue. Confirm that HULA's
actual property has the required ecommerce events; missing steps are shown as
missing, never fabricated.

GA4 is analytics attribution, not Shopify booked commerce truth.
