# Attribution guide

HULA Marketing Operations never presents channel-attributed revenue as if each
channel owns a mutually exclusive slice of Shopify revenue.

## The three views

1. **Shopify booked commerce revenue** — what HULA booked through Shopify/POS
   under the signed revenue definition. This is the commerce source of truth.
2. **Platform-attributed revenue** — Google Ads, Meta and Klaviyo values under
   each provider's conversion action, attribution model and window.
3. **Analytics-attributed revenue** — GA4 values under its selected reporting
   identity and attribution model.

These views answer different questions and can overlap. Do not add Google,
Meta, Klaviyo, organic and direct revenue to produce a “total.”

## Required labels

Every attributed metric must display:

- provider/source;
- selected conversion metric;
- attribution model/window, if exposed;
- account timezone and currency;
- data freshness;
- known limitation.

If the API does not expose the account setting, configure and show it as a
declared limitation rather than guessing.

## Reconciliation order

1. Fix one date range in HKT.
2. Confirm order inclusion/exclusion rules.
3. Confirm source currency and conversion date.
4. Reconcile Shopify headline to order rows and location/channel dimensions.
5. Reconcile GA4 purchase events/revenue to Shopify while retaining expected
   identity, consent, event and attribution differences.
6. Compare each ad/email platform separately with its actual configured window.
7. Record late-arriving data and finalization dates.
8. Preserve unexplained differences as visible controls.

## Key formulas

```text
Blended paid ROAS =
  (Google Ads platform conversion value + Meta platform purchase value)
  / (Google Ads cost + Meta spend)

MER =
  included Shopify/POS commerce revenue / included paid-media spend

Spend per all new customer (proxy, not CAC) =
  included paid-media spend / Shopify new customers

True paid CAC =
  included paid-media spend / deduplicated new customers attributable to paid media
```

Email-attributed revenue is not included in paid ROAS. The July report cannot
support true paid CAC because its 167-new-customer denominator includes store
and potentially organic customers. The app therefore labels HK$182.03 only as
spend per all new customer and shows paid CAC as unavailable.
