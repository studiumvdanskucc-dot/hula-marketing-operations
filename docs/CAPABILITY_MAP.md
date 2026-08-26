# Capability map after the calm-UI rebuild

The redesign changes navigation and presentation, not the underlying operating
model. HULA has exactly two access levels: the sole **Administrator** and a
read-only **Viewer** experience for leadership and sales. Marketing, paid media,
merchandising and data-owner labels describe work responsibilities only.

| Agreed capability | New location | Current boundary |
| --- | --- | --- |
| Executive commerce view | Overview | Shopify/Report Pundit GMV, actual discounts/refunds, net revenue, retained revenue, contribution and MER stay separate from attribution. |
| Priority recommendations | Viewer Overview, Work → Actions and Performance → Paid media | 7/14/28/56 windows, platform ROAS, purchases, retained/contribution ROAS, large-order dependency, inventory, confidence, blockers, owner and trigger. |
| Tasks and work ownership | Work → Actions | Administrator can create/update work; duplicate active signals are reused. |
| Human approval and audit | Work → Actions; Settings → Governance | Major changes require Sarah + Elena + Tiffany; current decisions create work and never execute externally. |
| Campaign planning and readiness | Work → Campaigns | Brief, channel-specific checklist, owners, dates, gates, UTMs and launch approval are retained. |
| Experiments | Work → Actions | Hypothesis, baseline, target, control, variant and confidence limitation are retained. |
| SEO opportunity scoring | Work → Content & SEO → SEO opportunities | Transparent factors, missing-data handling, evidence and task creation are retained. |
| Content drafting and review | Work → Content & SEO → Content studio | Evidence, AI-draft label, product checks and human review are retained. |
| Technical SEO, catalogue and feed health | Work → Content & SEO → Site & catalogue | Page issues, one-off inventory checks and Merchant Center status remain available. |
| Trend Intelligence handoff | Work → Content & SEO → Trend handoff | The original Trend Intelligence app stays independent; selected evidence can create campaign/content work. |
| Booked sales and attribution reconciliation | Performance → Business truth and Data quality | Channel claims are never added together as revenue; known report gaps remain visible. |
| Google and Meta diagnosis | Performance → Paid media | Platform-native and normalized management views remain separate; claim excess is guarded by same-scope validation. |
| Klaviyo and local/store reporting | Performance → Email & local | Campaign/flow performance, attribution caveat and Google Business Profile interactions are retained. |
| Customer and discovery analysis | Performance → Customers & discovery | Privacy-safe segments and observable AI-referral traffic remain available. |
| Data connections and sync requests | Settings → Connections | Shopify, Meta Ads, GA4 and Search Console have read-only clients; other providers expose honest configuration/health shells. The access-audit table stays separate from credential state. |
| Metric definitions and report exports | Settings → Metric definitions / Reports | Source, formula, attribution and limitations remain visible; PDF and governed table exports remain available. |
| CEO/sales view | Viewer → Overview | One read-only page; no settings, integrations, campaign forms, approval controls or writes. |

## Agreed decision layers that remain input-gated

The interface does not fabricate these outputs from the two supplied PDFs:

- **GMV → Shopify net revenue → HULA retained revenue → contribution** now has
  a provisional 31% retained rate and payment/shipping at 10% of retained
  margin. Case-specific discount/voucher rules and final margin approval remain.
- **Contribution ROAS** can be shown as a provisional scenario. The 10% forecast
  return provision, scaling target and reliable Shopify-order join remain open.
- **Break-even ROAS** is labelled in two equivalent forms: about 4.0x gross/
  platform GMV ROAS or 1.0x contribution ROAS.
- **Largest-order dependency and one-more-order sensitivity** need order-level
  conversion values, not monthly campaign totals.
- **7/14/28/56-day decisions** need daily Google/Meta data with complete-window
  markers and the configured conversion actions/windows.
- **Paid-attributed new-customer CPA** needs deduplicated first-order identity
  joined to paid acquisition evidence.
- **International funnel diagnosis** needs country-level GA4/Shopify event and
  order populations using one documented definition.
- **External API actions** remain disabled until provider-specific preview,
  approval, idempotency, verification and rollback controls are proven.

These are data and governance dependencies, not reasons to add more navigation.
They belong inside Performance, Work and Settings as their required inputs become
available.
