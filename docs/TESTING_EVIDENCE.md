# Testing evidence

## Baseline before implementation

- Python 3.12 isolated audit environment.
- Existing repository: **94 tests passed**.
- Existing `app.py`: Streamlit health `ok`, root HTTP 200, no credentials.

## First-release verification

Final verification used a clean Python 3.12 virtual environment resolving the
repository's declared dependency ranges.

```text
python -m compileall -q app.py apps src jobs scripts tests
Result: passed

python -m pytest -q
Result: 142 passed in 163.38s

Original Trend Intelligence tests: 94
Marketing Operations tests: 48

Trend Intelligence process:
  /_stcore/health = ok
  GET / = HTTP 200

Marketing Operations process (no credentials; fixture mode):
  /_stcore/health = ok
  GET / = HTTP 200
```

Marketing Operations coverage includes:

- all four Administrator workspaces and every consolidated subview without credentials;
- the single Viewer overview, with no navigation selector or mutation buttons;
- the expand-sidebar control remains visible after the navigation is collapsed;
- campaign-checklist selection and idempotent task creation;
- metric calculations and July reconciliation controls;
- profitability bridge and fail-closed paid-media decisions;
- exact 31% × 90% × 90% scenario math and protection against deducting actual
  Shopify refunds twice;
- 7/14/28/56-day evidence, large-order dependency and one-more-order sensitivity;
- same-scope protection for the claim-excess indicator;
- configurable finance, hard-budget and named-approver policy inputs;
- explicit separation of analytics events from the Shopify Online Store summary;
- channel-chart coverage and 90-day email / seven-day Meta window controls;
- permission and risk matrix;
- fixture/demo live-action guard;
- task deduplication and rejection reason;
- second-approval self-approval prevention and the all-three major-change rule;
- redacted errors and customer-data redaction;
- Shopify, Meta Ads, GA4 and Search Console connector contracts with mocked HTTP;
- API-access readiness kept distinct from live credential/sync state;
- report PDF and CSV/ZIP generation.

The updated four-page management PDF is rendered with Poppler and checked page
by page after the decision-section layout change. Streamlit AppTest renders all
Administrator subviews and the single Viewer page, checks the recommendation
evidence labels, and verifies the Viewer exposes no mutation buttons.

Tests are offline and use fixtures/mocked HTTP sessions. CI must never perform a
live write. Production provider contract checks are explicit read-only health
checks run by an authorized administrator.
