# HULA Marketing Operations first-release status

**Build:** `2026.08.16-marketing.4`  
**Data mode:** fixture by default  
**External writes:** disabled and not implemented

## Completed

- Independent `apps/marketing_operations.py` entry point.
- Existing `app.py` retained as Trend Intelligence production entry point.
- Two access levels: one Administrator and one read-only Viewer experience.
- Four Administrator workspaces—Overview, Work, Performance and Settings—with
  campaigns, content, SEO, recommendations, approvals and experiments retained
  inside Work.
- July 2026 report-parity fixtures retain visible source, attribution and
  freshness labels.
- Campaign-specific channel checklists that create owned, due-dated work only
  for the channels selected in the campaign.
- Corrected measurement layer: no unsupported checkout funnel, paid CAC shown
  as unavailable, and explicit channel-chart coverage/window controls.
- Deterministic signals with evidence, explanation, action, owner, playbook and
  success measure.
- Local/offline tasks, approvals, campaigns, content, experiments, jobs and
  immutable-style audit events.
- Two-role permission matrix and Supabase Auth production adapter.
- Repeatable Postgres/Supabase foundation plus two-role RLS migration.
- Read-only Shopify order/refund, GA4 runReport and Search Console connectors.
- Honest health/configuration shells for Google Ads, Meta, Klaviyo, GBP,
  Merchant Center and PageSpeed.
- Structured monthly PDF and CSV/ZIP export.
- Metric dictionary, attribution guide, integration guides, operating manual,
  security checklist and deployment guide.
- Safe defaults: no credentials required, all write flags off, no fake live
  connection.
- Final verification: 127/127 tests passed; both Streamlit entry points returned
  health `ok` and HTTP 200; the interface and four-page PDF passed rendered visual QA.

## Partially completed

- Provider sync clients return normalized read records, but production marts,
  backfill persistence and a deployed worker require HULA's infrastructure and
  credentials.
- Google Ads, Meta, Klaviyo, GBP, Merchant and PageSpeed have configuration and
  health shells; their complete reporting syncs are not implemented.
- The technical crawler has a controlled job request and fixture issues; the
  production crawler worker is not implemented.
- Supabase schema/RLS is supplied but cannot be live-tested without a HULA-owned
  staging project and invited users.

## Blocked by account access / business decisions

- Shopify store and location IDs, protected-order/customer access decision and
  fixed-range export.
- GA4 property/event map/reporting identity.
- Search Console exact property.
- Google Ads, Meta, Klaviyo, GBP and Merchant account IDs, read permissions and
  actual attribution settings.
- Signed revenue/order/customer/paid-CAC/CLV/MER definitions and July 2026
  reconciliation rules.
- Named sole Administrator, Viewer account list, workflow responsibility owners
  and an independent high-risk review route.

## Deliberately not implemented

- Shopify publishing or catalogue writes.
- Google/Meta budget, bid, targeting, keyword, creative or status mutation.
- Klaviyo campaign send or flow activation.
- Public review replies.
- Merchant writes, discounts or customer audience uploads.
- Autonomous campaign management or automatic mass edits.

Testing status is updated in `docs/TESTING_EVIDENCE.md` after the final run.
