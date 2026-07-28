# Supabase aggregate history

Supabase stores weekly aggregate snapshots and blog drafts. It does not store
raw social posts, customers, orders or payment data.

## Create the tables

1. Open the `hula-trend-intelligence` project in Supabase.
2. Open **SQL Editor → New query**.
3. Open this repository's `supabase/schema.sql`.
4. Copy the complete SQL into the editor and select **Run**.
5. Open **Data & Setup → Test Supabase history** in the HULA app.

## Secrets

Use the project-root URL without `/rest/v1/`:

```toml
SUPABASE_URL = "https://your-project-reference.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_your-complete-key"
SUPABASE_SNAPSHOT_TABLE = "hula_trend_snapshots"
SUPABASE_BLOG_TABLE = "hula_blog_drafts"
```

Add the same URL and secret to Streamlit Secrets and GitHub Actions Secrets.
Never commit the secret. The newer `sb_secret_` value is sent through the
server-side `apikey` header and is not treated as a user JWT.

The dashboard loads a newer Supabase snapshot at startup when one is available.
A Supabase outage never deletes the local aggregate; it produces a visible
diagnostic warning instead.
