# HULA Marketing Operations - build handoff

This repository now contains the simplified, campaign-first Marketing
Operations release while preserving the original Trend Intelligence app.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env

# Existing Trend Intelligence
python -m streamlit run app.py --server.port 8501

# New Marketing Operations app
python -m streamlit run apps/marketing_operations.py --server.port 8502
```

Marketing Operations starts safely in explicit fixture mode. No credential is
required, and no external write can execute.

## What is working now

- two access levels: one full Administrator and one read-only Viewer experience;
- four Administrator workspaces: Overview, Work, Performance and Settings;
- one Viewer page for leadership and sales, with no technical or mutation controls;
- campaign-specific channel checklists and owned workboards;
- agency-report parity fixture with corrected measurement logic and reconciliation;
- GMV → Shopify net revenue → retained revenue → contribution bridge with
  actual refunds deducted once and provisional assumptions visible;
- recommendation cards with 7/14/28/56-day windows, purchases, outlier,
  inventory, confidence and contribution controls;
- normalized paid-attribution comparison and same-scope overlap protection;
- questionnaire-backed budgets, approvals, automation and ownership handover;
- command-centre signals and playbooks, including channel-coverage governance;
- tasks, approvals, campaigns, content, experiments, jobs and audit history;
- role-aware navigation and Supabase Auth production adapter;
- read-only Shopify, Meta Ads, GA4 and Search Console clients;
- provider setup/health shells for remaining channels and a separate access-
  readiness register from the 26 August audit;
- structured PDF and CSV/ZIP monthly export;
- Supabase/Postgres migration and RLS;
- complete setup, metric, attribution, security, deployment and operator docs.

## Verified

- 142/142 tests pass (94 preserved Trend Intelligence + 48 Marketing Operations);
- Trend Intelligence health `ok`, HTTP 200;
- Marketing Operations health `ok`, HTTP 200 without credentials;
- all Administrator workspaces/subviews and the single Viewer page passed
  1600 × 1100 rendered visual review;
- generated four-page PDF visually rendered and inspected after pagination repair.

## Honest boundary

Live HULA dashboards cannot exist until HULA installs account credentials and
the fixed-range source data reconciles. Google Ads, Meta, Klaviyo, GBP,
Merchant and PageSpeed are not all live: Meta now has a read-only connector but
still needs its production system-user token/asset assignment; the other named
providers remain health/configuration shells. No live
publishing, campaign mutation, budget change, send, audience upload or public
review reply is implemented.

The app now calculates a provisional scenario using 31% retained margin and
payment fees plus shipping at 10% of retained margin. Actual Shopify refunds
are deducted once; a separate 10% return provision is used only for paid-
platform gross-value scenarios and still needs approval. Decisions remain
REVIEW until the retained definition, scaling target, minimum volume, hard
budgets and live inventory/data are complete, and Sarah + Elena + Tiffany
confirmations can be evidenced for major changes.

Start with [`docs/FINAL_STATUS.md`](docs/FINAL_STATUS.md), then follow
[`docs/MARKETING_OPERATIONS_MANUAL.md`](docs/MARKETING_OPERATIONS_MANUAL.md) and
the provider guides under [`docs/integrations/`](docs/integrations/SHOPIFY.md).
The [`capability map`](docs/CAPABILITY_MAP.md) shows where each retained function
lives in the calmer navigation and which items still require live data or HULA
business rules.
