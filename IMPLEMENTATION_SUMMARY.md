# HULA Trend Intelligence — build 2026.07.28.1

## Requested corrections

- Invariant Google series are excluded from scoring and charts. Old saved flat
  series are demoted on load before the dashboard renders.
- The ranked decision table contains only trends with fresh Google demand plus
  at least one social, commercial or visual confirmation. Incomplete rows are
  shown separately as a watchlist.
- `sandal` and `sandals` are kept.
- `outfit ideas`, `trousers`, `dress` and `mini` are blocked when they are the
  complete trend label.
- `mini dress`, `red trousers`, `designer bags` and other specific
  combinations remain eligible.
- Soho and The Hub are both available as campaign formats, objectives, blog
  reasons, destinations and calls to action.

## New source stack

- Strict fourteen-day timestamp gate for X and Instagram.
- Separate open-X discovery and commercial confirmation.
- Approved ten-profile Instagram panel using
  `apify/instagram-post-scraper`.
- Google rising-query discovery over seven days, one-month validation and
  seven-day acceleration.
- Supabase aggregate snapshot and blog-draft history.
- Gemini 2.5 Flash grounded editorial research after deterministic ranking.
- Claim-level source mapping; unsupported confirmed claims are downgraded and
  removed from publishable body copy when matched exactly.

## First deployment

1. Run `supabase/schema.sql` once in the Supabase SQL Editor.
2. Add `SUPABASE_URL`, `SUPABASE_SECRET_KEY` and `GEMINI_API_KEY` to GitHub
   Actions Secrets as well as Streamlit Secrets.
3. Preserve the existing SerpApi, Apify, OpenRouter and catalogue secrets.
4. Deploy the repository and confirm **Build 2026.07.28.1**.
5. In **Data & Setup**, run all six connection checks.
6. Run one manual full refresh and review the source-health diagnostics.
7. Open **Wednesday Blog** and review claim statuses before publishing.

See `START_HERE.md` and the `docs/` folder for complete instructions.

## Verification

```text
66 offline tests passed
Python compilation passed
Streamlit smoke tests passed for all six pages
Workflow YAML and Streamlit TOML parsed successfully
```
