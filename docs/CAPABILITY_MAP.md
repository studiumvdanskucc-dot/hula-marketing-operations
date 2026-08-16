# Capability map after the calm-UI rebuild

The redesign changes navigation and presentation, not the underlying operating
model. HULA has exactly two access levels: the sole **Administrator** and a
read-only **Viewer** experience for leadership and sales. Marketing, paid media,
merchandising and data-owner labels describe work responsibilities only.

| Agreed capability | New location | Current boundary |
| --- | --- | --- |
| Executive commerce view | Overview | Shopify/POS fixture is the booked source of truth; platform attribution is separate. |
| Priority recommendations | Overview and Work → Actions | Deterministic evidence, confidence, owner, next action and success measure are retained. |
| Tasks and work ownership | Work → Actions | Administrator can create/update work; duplicate active signals are reused. |
| Human approval and audit | Work → Actions; Settings → Governance | Decisions are recorded; they do not execute an external action. |
| Campaign planning and readiness | Work → Campaigns | Brief, channel-specific checklist, owners, dates, gates, UTMs and launch approval are retained. |
| Experiments | Work → Actions | Hypothesis, baseline, target, control, variant and confidence limitation are retained. |
| SEO opportunity scoring | Work → Content & SEO → SEO opportunities | Transparent factors, missing-data handling, evidence and task creation are retained. |
| Content drafting and review | Work → Content & SEO → Content studio | Evidence, AI-draft label, product checks and human review are retained. |
| Technical SEO, catalogue and feed health | Work → Content & SEO → Site & catalogue | Page issues, one-off inventory checks and Merchant Center status remain available. |
| Trend Intelligence handoff | Work → Content & SEO → Trend handoff | The original Trend Intelligence app stays independent; selected evidence can create campaign/content work. |
| Booked sales and attribution reconciliation | Performance → Business truth and Data quality | Channel claims are never added together as revenue; known report gaps remain visible. |
| Google and Meta diagnosis | Performance → Paid media | Spend, purchases, attributed value, ROAS, pacing, creative/frequency and recommendations remain available. |
| Klaviyo and local/store reporting | Performance → Email & local | Campaign/flow performance, attribution caveat and Google Business Profile interactions are retained. |
| Customer and discovery analysis | Performance → Customers & discovery | Privacy-safe segments and observable AI-referral traffic remain available. |
| Data connections and sync requests | Settings → Connections | Shopify, GA4 and Search Console have read-only clients; other providers expose honest configuration/health shells. |
| Metric definitions and report exports | Settings → Metric definitions / Reports | Source, formula, attribution and limitations remain visible; PDF and governed table exports remain available. |
| CEO/sales view | Viewer → Overview | One read-only page; no settings, integrations, campaign forms, approval controls or writes. |

## Agreed decision layers that remain input-gated

The interface does not fabricate these outputs from the two supplied PDFs:

- **GMV → HULA retained revenue → contribution → post-ad contribution** needs
  signed consignment, discount, refund, payment, fulfilment and variable-cost
  rules.
- **Contribution ROAS, break-even ROAS and maximum CAC** need those same rules
  plus a reliable Shopify-order join.
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
