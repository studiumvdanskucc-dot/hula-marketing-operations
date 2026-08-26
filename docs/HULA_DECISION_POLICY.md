# HULA profitability and paid-media decision policy

This document records the questionnaire answers and 26 August access audit
implemented in Build `2026.08.26-marketing.6`. A blank or **blocking** input is not replaced with an
industry benchmark. It causes the recommendation engine to return **REVIEW**.

## Confirmed direction

- Shopify is the commerce source of truth. HULA currently uses Report Pundit
  for operational reporting from Shopify.
- The top line keeps three separate measures: GMV, HULA retained revenue and
  HULA contribution.
- Paid-media decisions use HULA contribution, not the full product selling
  price. Platform GMV ROAS remains visible as a diagnostic.
- Repeat-customer profitability should be included once the cohort, observation
  window and contribution definition are approved.
- Total-spend increases, new campaigns/audiences/creative, billing changes and
  customer messages are never automatic.
- Major changes require confirmation from Sarah, Elena and Tiffany.
- Actual refunds reduce Shopify revenue before retained revenue and
  contribution are calculated.
- Payment fees and shipping are the only current variable-cost categories;
  together they are configured as 10% of HULA retained margin.

## Provisional commercial rule

HULA approved **31% for now**, as a configurable retained-margin planning
proxy. It is not hard-coded and does not authorize a spend decision.

Discount handling is case-dependent:

- during a sale period, the discount is shared between seller and HULA;
- outside a sale period, the discount is on the seller side;
- HULA vouchers are funded by HULA;
- HELLOHULA currently removes HK$250 from a first order above HK$3,500.

The order-level formula, exceptions and effective dates still need Sarah's
approval. Finance confirmed that actual refunds come off total revenue.

For booked Shopify commerce, the app applies actual refunds once:

```text
Shopify net revenue = gross sales − recorded discounts − actual refunds
HULA retained revenue = Shopify net revenue × 31%
Contribution = HULA retained revenue × (1 − 10% payment/shipping rate)
```

For a platform-attributed gross-value scenario, the supplied example also uses
a provisional 10% return provision:

```text
Scenario contribution rate = 31% × 90% × 90% = 25.11%
Break-even gross/platform GMV ROAS = 1 ÷ 25.11% = 3.98x ≈ 4.0x
Break-even contribution ROAS = contribution ÷ spend = 1.0x
```

These are the same economic break-even expressed using different numerators.
The app never labels 4.0x as a contribution ROAS floor. The 10% return
provision still needs confirmation as an operating rule rather than an
illustrative example.

## Blocking inputs

| Input | Owner | Why it blocks |
| --- | --- | --- |
| Retained-revenue formula and 31% definition | Sarah | A blended estimate cannot price individual discounted or voucher orders. |
| 10% forecast return provision | Finance / HULA | It was supplied in the example but has not been confirmed as the forward-looking policy. |
| Contribution ROAS scaling target | Sarah / HULA | Break-even is defined, but the engine needs an approved buffer above break-even before SCALE. |
| Minimum purchases and complete window | HULA | Small samples and one luxury order can distort ROAS. |
| Maximum paid CAC and payback window | Sarah | First-order and 90/180-day acquisition decisions remain undefined. |
| Google and Meta monthly hard caps | HULA | Budget pacing and automation cannot be bounded. |
| Internal reallocation and bid ranges | HULA | Candidate automations do not have safe numeric limits. |
| Live inventory and live source data | HULA | A fixture or unavailable-product destination cannot authorize a campaign change. |

## Access readiness from the 26 August audit

- **Shopify:** administrative/app capability passed, but the HULA app has zero
  installs and no production credential was created. Map legacy custom apps and
  confirm Store owner/recovery before removing collaborators.
- **Meta / Instagram:** HULA owns the checked core assets and has full access.
  A production app/system user still needs the ad account and dataset assigned,
  followed by a read-only token. The app now contains a real `ads_read`
  reporting connector, but it remains unconfigured.
- **Google Ads:** direct HULA access is still missing. Customer ID, HULA Admin
  access, manager-account control, conversions and Cloud/API ownership must be
  confirmed.

Administrative access is not the same as an API connection. No credential was
created by the audit, and no secret belongs in Git.

## Attribution policy

Management reporting uses two layers:

1. Shopify/Report Pundit actual orders, GMV, retained revenue, contribution,
   paid spend and blended MER. This layer is not attributed.
2. Google and Meta self-reported orders/value/ROAS, shown with their platform
   native settings and a normalized **7-day click-only** management comparison
   where the APIs allow it.

The normalized view does not alter the provider account setting. Google and
Meta native views remain visible. Klaviyo stays in a separate email block.

Google Ads' uncustomized default click-through conversion window is 30 days
and can be configured; Google recommends at least seven days. Meta reporting
commonly exposes 1-day and 7-day click plus 1-day view settings. Therefore the
app does not claim that the two native windows are identical.

Official references:

- [Google Ads conversion windows](https://support.google.com/google-ads/answer/3123169?hl=en)
- [Meta attribution-setting overview](https://www.facebook.com/business/help/460276478298895)
- [Meta Ads action-stat windows](https://developers.facebook.com/docs/marketing-api/reference/ads-action-stats/)
- [Klaviyo attribution settings](https://help.klaviyo.com/hc/en-us/articles/1260804504250)

## Claim excess / overlap indicator

The proposed calculation is:

```text
sum of comparable platform-claimed orders
minus same-scope actual Shopify orders
```

The app returns **Unavailable** until dates, eligible order population and
channel scope match. A positive result is an overlap indicator, not the number
of duplicated customers. Exact duplication requires order-level identifiers.

## Automation boundary

Alerts are the safest first automation. Pauses, internal reallocations and bid
adjustments are only candidates after their thresholds, caps, live data,
identity approvals, provider previews, idempotency and verification are proven.

In this release every external action is OFF. A recommendation can become owned
work; it cannot change Google, Meta, Shopify or Klaviyo.
