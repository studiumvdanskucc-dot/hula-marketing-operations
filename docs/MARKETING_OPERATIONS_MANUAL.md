# HULA Marketing Operations manual

This guide is written for HULA's sole Administrator. The default app is a
safe fixture until HULA's named account owners install credentials and live
source reconciliation passes.

## Start the application

```bash
python -m streamlit run apps/marketing_operations.py --server.port 8502
```

The sidebar must show **Build 2026.08.16-marketing.4** and either:

- `FIXTURE MODE · No live account data`, or
- an authenticated production state.

## Daily workflow

1. Open **Overview**.
2. Read Critical signals first. Open the evidence and playbook.
3. Convert a confirmed signal to a task; duplicate rules will reuse the active
   task rather than create repeated work.
4. Confirm owner and due date under **Work**, then record any required review.
5. Check pending approvals and connection health under **Settings**.
6. Never treat a fixture/demo task as authorization for a live change.

## Weekly workflow

1. Review **Settings → Connections** for freshness and errors.
2. Review the source-specific views under **Performance**.
3. Open **Work → Content & SEO → Trend handoff** and pass only evidence-backed,
   inventory-relevant trends into a campaign or content brief.
4. Check unavailable products before using any one-off resale item in content
   or advertising.
5. Prioritize two or three actions with a success measure; do not create a long
   unowned recommendation list.
6. Schedule 7/14/30-day measurements appropriate to the action.

## Monthly workflow

1. Wait for the agreed source-finalization window.
2. Reconcile Shopify/POS totals first.
3. Review GA4 and each platform-attribution view separately.
4. Resolve or explain every reconciliation tolerance breach.
5. Add factual executive commentary in **Settings → Reports**.
6. Record the named human reviewer and approval evidence required by HULA's
   release policy. High-risk self-approval remains blocked.
7. Export the structured PDF and table ZIP. Do not distribute a fixture-labelled
   report as live performance.

## Content workflow

```text
Idea → Research → Brief → Draft → Evidence check → Brand review
→ Product check → SEO review → Awaiting Approval → Approved
→ Shopify draft → Published → Measuring → Update / retire
```

Content Studio stores drafts and evidence. AI copy remains labelled as a draft.
Authentication, condition, material, hardware and counterfeit claims require a
named HULA expert and original support. Product availability is checked again
immediately before any later manual publication.

## Paid-media workflow

Use **Performance → Paid media** to diagnose. Confirm the same values in the live
platform before proposing a change. A paid specialist reviews conversion
health, search terms/audience overlap, landing page and inventory. This release
cannot change budget, bidding, targeting, status, ads or conversion settings.

## Common terms

- **ROAS:** attributed revenue divided by ad spend. It follows the provider's
  attribution settings and is not booked commerce revenue.
- **MER:** booked Shopify/POS commerce revenue divided by included paid spend; a blended
  efficiency view.
- **Paid CAC:** paid spend divided by deduplicated new customers attributable to
  paid media. It is unavailable in the supplied report. HK$182.03 is instead
  labelled **spend per all new customer** because it includes store and
  potentially organic customers.
- **CLV:** customer value under a stated historical or predictive method. The
  fixture uses historical realized value, not a prediction.
- **CTR:** clicks divided by impressions.
- **Canonical:** the URL a page declares as its preferred indexed version.
- **Creative fatigue:** repeated audience exposure accompanied by weakening
  response; it is a review signal, not proof of causality.
- **Attribution:** rules used to assign conversion credit. Provider views can
  overlap.

## When something fails

One provider failure should not stop other pages. Open **Settings → Connections**,
read the redacted state, confirm credential ownership/permission/API version,
run one explicit connection test, then queue a read-only resync. Never paste a
secret into a task, report, screenshot or chat.

## Viewer experience

CEO and sales Viewer accounts open directly into one read-only page showing
sales, orders, AOV, customer mix, location performance and three priority items.
They cannot see Settings, connectors, audit history, campaign forms or action
controls.
