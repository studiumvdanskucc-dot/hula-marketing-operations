# Deploying both HULA applications

## Local verification

```bash
python -m pip install -r requirements.txt
python -m compileall -q app.py apps src jobs scripts tests
pytest -q

python -m streamlit run app.py --server.port 8501
python -m streamlit run apps/marketing_operations.py --server.port 8502
```

Check `/_stcore/health` on each port and open both root pages.

## Streamlit deployments

Create two deployments from the same repository and branch:

| App | Entry point | Purpose |
|---|---|---|
| HULA Trend Intelligence | `app.py` | Fashion trend research and evidence |
| HULA Marketing Operations | `apps/marketing_operations.py` | Marketing reporting and operations |

Begin Marketing Operations with `DEMO_MODE=true`. A first deployment must not
receive any provider write scope.

## Production prerequisites

1. Create separate development and production Supabase projects or schemas.
2. Apply `supabase/schema.sql` for the legacy trend cache if it is still used.
3. Apply `database/migrations/001_marketing_operations.sql` with the migration
   owner.
4. Create invited Auth users and `marketing_members` records.
5. Configure RLS and test each role with a real user JWT.
6. Install only required read credentials in deployment secrets.
7. Run provider connection tests and fixed-range reconciliation.
8. Keep every `ENABLE_*_WRITES`, automatic publishing and automatic budget flag
   false.
9. Deploy the worker separately before enabling scheduled sync jobs.

## Background worker

The UI can enqueue jobs but must not run crawls/backfills in Streamlit. Deploy a
separate Python worker with:

- worker-only database/service credentials;
- job leases, retry limits and idempotency;
- structured logs and correlation IDs;
- provider rate limits and hard timeouts;
- restricted network egress;
- alerts for dead-letter jobs.

The first repository contains the queue contract; large crawler and provider
backfill workers remain a production follow-up and are not falsely advertised
as active.

## Rollback

- Deploy the previous known-good commit for either app independently.
- Do not roll back by deleting production rows.
- Database migrations require a reviewed reverse migration and backup.
- Disable a failing connector/worker without taking the other app offline.
- Rotate any credential involved in a suspected incident.

## Release checks

- Both app health endpoints return `ok`.
- Existing Trend Intelligence tests and pages pass.
- Marketing app starts with no credentials in fixture mode.
- No secret/token pattern exists in tracked files.
- All external-write flags are false.
- Report PDF and CSV bundle generate.
- RLS, role and second-approval tests pass in staging.
- API versions are checked against official provider documentation on the
  release date.
