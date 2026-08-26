# Attribution guide

HULA Marketing Operations never presents channel-attributed revenue as if each
channel owns a mutually exclusive slice of Shopify revenue.

## The three views

1. **Shopify commerce truth** — actual orders, GMV, recorded discounts/refunds,
   net revenue, retained revenue and contribution under the Shopify/Report
   Pundit definition. Actual refunds are deducted once in this layer.
2. **Platform-attributed revenue** — Google Ads, Meta and Klaviyo values under
   each provider's conversion action, attribution model and window.
3. **Analytics-attributed revenue** — GA4 values under its selected reporting
   identity and attribution model.

These views answer different questions and can overlap. Do not add Google,
Meta, Klaviyo, organic and direct revenue to produce a “total.”

## Management comparison window

Use a normalized **7-day click-only** management view for Google and Meta where
their APIs support the required breakdown. This is a comparison layer—not a
claim that both provider-native settings are identical. Keep each platform's
native conversion actions, model, click/view window and value visible beside
the normalized view. Klaviyo remains separate.

The supplied report's Meta seven-day label does not identify its click/view
mix, and the Google setting was not stated. Both are therefore unresolved until
verified in the live accounts.

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

Claim excess indicator =
  sum of same-scope platform-claimed orders − same-scope actual Shopify orders

Booked-commerce contribution =
  Shopify net revenue × 31% retained rate × 90% after payment/shipping

Platform-claim contribution scenario =
  platform-attributed gross value × 31% × 90% × 90% forecast non-return rate

Break-even gross/platform GMV ROAS = 1 / 25.11% = 3.98x ≈ 4.0x
Break-even contribution ROAS = contribution / spend = 1.0x
```

The 31% rate is configurable and provisional. The 10% forecast return
provision applies only to platform-claim scenarios and still requires approval;
it must not be applied again to Shopify net revenue that already reflects
actual refunds.

Email-attributed revenue is not included in paid ROAS. The July report cannot
support true paid CAC because its 167-new-customer denominator includes store
and potentially organic customers. The app therefore labels HK$182.03 only as
spend per all new customer and shows paid CAC as unavailable.

The claim excess result is also unavailable until the platform claims and
Shopify denominator share dates, eligibility and channel scope. A positive
result is a warning signal, not proof of the exact duplicated customers without
order-level identifiers.
