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
- command-centre signals and playbooks, including channel-coverage governance;
- tasks, approvals, campaigns, content, experiments, jobs and audit history;
- role-aware navigation and Supabase Auth production adapter;
- read-only Shopify, GA4 and Search Console clients;
- provider setup/health shells for remaining channels;
- structured PDF and CSV/ZIP monthly export;
- Supabase/Postgres migration and RLS;
- complete setup, metric, attribution, security, deployment and operator docs.

## Verified

- 126/126 tests pass (94 preserved Trend Intelligence + 32 Marketing Operations);
- Trend Intelligence health `ok`, HTTP 200;
- Marketing Operations health `ok`, HTTP 200 without credentials;
- all Administrator workspaces/subviews and the single Viewer page passed
  1600 × 1100 rendered visual review;
- generated four-page PDF visually rendered and inspected.

## Honest boundary

Live HULA dashboards cannot exist until HULA installs account credentials and
the fixed-range source data reconciles. Google Ads, Meta, Klaviyo, GBP,
Merchant and PageSpeed are health/configuration shells in this release. No live
publishing, campaign mutation, budget change, send, audience upload or public
review reply is implemented.

Start with [`docs/FINAL_STATUS.md`](docs/FINAL_STATUS.md), then follow
[`docs/MARKETING_OPERATIONS_MANUAL.md`](docs/MARKETING_OPERATIONS_MANUAL.md) and
the provider guides under [`docs/integrations/`](docs/integrations/SHOPIFY.md).
The [`capability map`](docs/CAPABILITY_MAP.md) shows where each retained function
lives in the calmer navigation and which items still require live data or HULA
business rules.
