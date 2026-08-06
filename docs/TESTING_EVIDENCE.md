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

python -m pytest -q --disable-warnings
Result: 125 passed in 153.47s

Original Trend Intelligence tests: 94
Marketing Operations tests: 31

Trend Intelligence process:
  /_stcore/health = ok
  GET / = HTTP 200

Marketing Operations process (no credentials; fixture mode):
  /_stcore/health = ok
  GET / = HTTP 200
```

Marketing Operations coverage includes:

- all five navigation workspaces and every consolidated subview without credentials;
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
captured at a 1600 × 1100 desktop viewport for Home, Campaigns and Performance
to verify the simplified navigation, KPI cards and campaign workroom.

Tests are offline and use fixtures/mocked HTTP sessions. CI must never perform a
live write. Production provider contract checks are explicit read-only health
checks run by an authorized administrator.
