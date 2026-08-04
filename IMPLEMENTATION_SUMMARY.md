# HULA Trend Intelligence — build 2026.08.03.1

## Requested corrections

- Google charts use the original 0–100 index only. Anchor-calibrated values are
  internal, and old snapshots without a raw display index are withheld.
- Low-resolution, plateau-heavy and isolated-spike timelines are not drawn.
- The ranked decision table contains only trends with fresh Google demand plus
  at least one X, commercial-report or hashtag confirmation. Incomplete rows are
  shown separately as a watchlist.
- `pants`, `skirt`, `flats` and `polka` are blocked alone.
- `capri pants`, `pencil skirt`, `ballet flats` and `polka dots` remain valid;
  `jeans`, `loafers` and `sandals` are approved standalone exceptions.
- Soho and The Hub are both available as campaign formats, objectives, blog
  reasons, destinations and calls to action.

## New source stack

- Strict fourteen-day timestamp gate for X.
- Commercial discovery from Tagwalk, Trendalytics, Heuritech, Who What Wear,
  Who What Wear UK, Data But Make It Fashion, Vogue, ELLE and Lyst Index.
- Only explicit article/report titles, trend-labelled headings and Tagwalk
  taxonomy count; ordinary body text is excluded.
- Instagram uses aggregate hashtag analytics after qualification, with
  top/latest post collection disabled.
- Google rising-query discovery over seven days, one-month validation and
  seven-day acceleration.
- Supabase aggregate snapshot and blog-draft history.
- Gemini 3.6 Flash grounded editorial research after deterministic ranking.
- Claim-level source mapping; unsupported confirmed claims are downgraded and
  removed from publishable body copy when matched exactly.

## First deployment

1. Run `supabase/schema.sql` once in the Supabase SQL Editor.
2. Add `SUPABASE_URL`, `SUPABASE_SECRET_KEY` and `GEMINI_API_KEY` to GitHub
   Actions Secrets as well as Streamlit Secrets.
3. Preserve the existing SerpApi, Apify, OpenRouter and catalogue secrets.
4. Deploy the repository and confirm **Build 2026.08.03.1**.
5. In **Data & Setup**, run the publisher, hashtag and API connection checks.
6. Run one manual full refresh and review the source-health diagnostics.
7. Open **Wednesday Blog** and review claim statuses before publishing.

See `START_HERE.md` and the `docs/` folder for complete instructions.

## Verification

```text
80 offline tests passed
Python compilation passed
Streamlit smoke tests passed for all six pages
Workflow YAML and Streamlit TOML parsed successfully
```
