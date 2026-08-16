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
Result: 126 passed in 177.40s

Original Trend Intelligence tests: 94
Marketing Operations tests: 32

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
- campaign-checklist selection and idempotent task creation;
- metric calculations and July reconciliation controls;
- explicit separation of analytics events from the Shopify Online Store summary;
- channel-chart coverage and 90-day email / seven-day Meta window controls;
- permission and risk matrix;
- fixture/demo live-action guard;
- task deduplication and rejection reason;
- second-approval self-approval prevention;
- redacted errors and customer-data redaction;
- Shopify, GA4 and Search Console connector contracts with mocked HTTP;
- report PDF and CSV/ZIP generation.

The management PDF is rendered with Poppler and checked page by page after each
material report-layout change. The Marketing Operations interface is also
captured at a 1600 × 1100 desktop viewport for Overview, all three Work views,
all five Performance views, Connections, Governance and the single Viewer page
to verify navigation, responsive KPI cards, tables and safety controls.

Tests are offline and use fixtures/mocked HTTP sessions. CI must never perform a
live write. Production provider contract checks are explicit read-only health
checks run by an authorized administrator.
