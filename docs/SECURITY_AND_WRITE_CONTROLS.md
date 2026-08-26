# Security and external-write controls

## First-release guarantees

- All external-write flags default to `false`.
- No external action adapter exists in this release.
- No page can publish Shopify content, edit a live catalogue item, mutate an ad,
  change a budget, send Klaviyo, upload an audience or post a public reply.
- Demo/fixture tasks cannot transition to Approved, Scheduled or Implemented as
  live work.
- Provider secrets are never displayed by the health page.
- HTTP/provider exceptions pass through structured redaction.
- Customer email addresses and phone numbers are removed before any future AI
  drafting call.
- The SQLite fallback is local/demo only. Production identity and operational
  data use Supabase Auth, Postgres and RLS.

## Production secret placement

Store secrets in the deployment secret manager or Streamlit Secrets. Worker-only
credentials—especially `SUPABASE_SERVICE_ROLE_KEY`—must not be supplied to
browser code or client-side state. Never place secrets in the repository,
downloads, task evidence, screenshots or chat.

Use named accounts and least privilege. Do not share passwords. HULA owns every
provider account, OAuth application and recovery method.

## Roles

| Capability | Viewer | Administrator |
|---|---:|---:|
| View the business overview | Yes | Yes |
| Export approved reporting | Yes | Yes |
| Create or update tasks | — | Yes |
| Create campaigns and content | — | Yes |
| Record review and approval decisions | — | Yes |
| Configure integrations and access | — | Yes |

The complete matrix is implemented in `src/marketing_ops/permissions.py` and
displayed in the app.

## Mandatory future action sequence

```text
Recommendation → proposal → validation → permission → before snapshot
→ human-readable diff → risk → approval → dry run → execute
→ provider verification → audit → outcome measurement
```

Major paid-media changes require named confirmation from **Sarah, Elena and
Tiffany**. These are approval identities, not extra operational views. The sole
Administrator cannot substitute for the three confirmations. Until a governed
identity-specific voting method and the future action adapter are released,
major external actions remain blocked. Every future adapter also needs an
idempotency key and a tested rollback or an explicitly documented no-rollback
limitation.

## Pre-production checklist

- [ ] Invite-only users and named backup owners configured.
- [ ] Sarah, Elena and Tiffany approval identities and evidence retention configured.
- [ ] Google and Meta hard monthly caps approved and recorded.
- [ ] Final 31% retained-margin definition, 10% forecast return provision,
  scale target, purchase-volume threshold and payback window approved.
- [ ] Shopify production app installed with least-privilege reads; Store owner,
  recovery and legacy custom-app dependencies documented.
- [ ] Meta production app/system user has only required assets and `ads_read`;
  token is stored in the deployment secret manager and reconciled once.
- [ ] Google Ads HULA-controlled Admin access and manager/API ownership confirmed.
- [ ] Both migrations applied; sole Administrator and Viewer access tested.
- [ ] Service-role key available only to worker runtime.
- [ ] All provider permissions reviewed against official current docs.
- [ ] Secret rotation and revocation exercised.
- [ ] Redacted error and structured logging tests pass.
- [ ] Customer-data classification, retention and deletion rules approved.
- [ ] Consent, suppression and minimum audience rules approved.
- [ ] Webhook signatures verified before event processing.
- [ ] Crawler enforces HTTPS, HULA host allow-list, robots, byte/time/page limits
  and redirect validation.
- [ ] Audit backup, recovery and incident contacts documented.
- [ ] External writes remain disabled unless a separate adapter release passes
  diff, approval, idempotency, verification and rollback tests.
