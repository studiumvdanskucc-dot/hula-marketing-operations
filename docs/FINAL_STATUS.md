# HULA Marketing Operations first-release status

**Build:** `2026.08.26-marketing.6`
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
- Shopify/Report Pundit profitability bridge: GMV, recorded discounts and
  refunds, net revenue, configurable provisional retained revenue and HULA
  contribution without double-deducting refunds.
- Paid-media decision cards with 7/14/28/56-day views, purchase counts,
  platform and contribution ROAS, large-order dependency, inventory,
  confidence, blockers and review triggers.
- Normalized 7-day click-only management comparison with provider-native views
  preserved and Klaviyo separated.
- Questionnaire-backed finance register, hard-budget controls, all-three major
  approval policy, automation boundaries and GoodSauce ownership checklist.
- Deterministic signals with evidence, explanation, action, owner, playbook and
  success measure.
- Local/offline tasks, approvals, campaigns, content, experiments, jobs and
  immutable-style audit events.
- Two-role permission matrix and Supabase Auth production adapter.
- Repeatable Postgres/Supabase foundation plus two-role RLS migration.
- Read-only Shopify order/refund, Meta campaign-insights, GA4 runReport and
  Search Console connectors.
- Honest health/configuration shells for Google Ads, Klaviyo, GBP,
  Merchant Center and PageSpeed.
- Access-readiness register reflecting the 26 August audit: Shopify and Meta
  administrative readiness passed, credentials remain uncreated/unconfigured,
  and Google Ads access is missing.
- Structured monthly PDF and CSV/ZIP export.
- Metric dictionary, attribution guide, integration guides, operating manual,
  security checklist and deployment guide.
- Safe defaults: no credentials required, all write flags off, no fake live
  connection.
- Final verification: 142/142 tests passed, including the corrected
  profitability calculation, access-readiness model and mocked read-only Meta
  connector. Full evidence is recorded in `docs/TESTING_EVIDENCE.md`.

## Partially completed

- Provider sync clients return normalized read records, but production marts,
  backfill persistence and a deployed worker require HULA's infrastructure and
  credentials.
- Meta has a read-only campaign-insights client; it still requires a HULA-owned
  production app/system-user token and assigned ad-account asset. Google Ads,
  Klaviyo, GBP, Merchant and PageSpeed remain configuration/health shells.
- The technical crawler has a controlled job request and fixture issues; the
  production crawler worker is not implemented.
- Supabase schema/RLS is supplied but cannot be live-tested without a HULA-owned
  staging project and invited users.

## Blocked by account access / business decisions

- Shopify app installation/credentials, Store-owner/recovery confirmation,
  legacy-app dependency mapping, protected-order/customer access decision and
  fixed-range validation.
- GA4 property/event map/reporting identity.
- Search Console exact property.
- Google Ads HULA Admin access and ownership; Meta production token/asset
  assignment; Klaviyo, GBP and Merchant account IDs/read permissions; actual
  attribution settings.
- Final retained-margin definition, approval of the 10% forecast return
  provision, contribution scaling target, maximum CAC, payback, minimum volume,
  monthly caps and adjustment ranges.
- Named sole Administrator, Viewer account list and identity-specific evidence
  from Sarah, Elena and Tiffany for major-change approval.

## Deliberately not implemented

- Shopify publishing or catalogue writes.
- Google/Meta budget, bid, targeting, keyword, creative or status mutation.
- Klaviyo campaign send or flow activation.
- Public review replies.
- Merchant writes, discounts or customer audience uploads.
- Autonomous campaign management or automatic mass edits.

Testing status is updated in `docs/TESTING_EVIDENCE.md` after the final run.
