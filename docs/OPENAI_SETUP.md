# OpenAI article-extraction setup

The first-party path uses the Responses API with strict structured output:

- `gpt-5.6-luna` scans bounded recent-article batches and extracts concrete
  trend names, concise Google queries and short evidence excerpts;
- `gpt-5.6-terra` conservatively groups genuine aliases;
- `gpt-5.6-sol` produces the optional evidence-locked synthesis and blog.

Python—not a model—calculates dates, publisher overlap, freshness, Google
time-series metrics, priority, action rules, product matches and ordering.

## Secrets

```toml
OPENAI_API_KEY = "your-private-key"
OPENAI_API_URL = "https://api.openai.com/v1/responses"
OPENAI_LUNA_MODEL = "gpt-5.6-luna"
OPENAI_TERRA_MODEL = "gpt-5.6-terra"
OPENAI_SOL_MODEL = "gpt-5.6-sol"
OPENAI_TIMEOUT_SECONDS = "180"
EDITORIAL_AI_BATCH_SIZE = "5"
```

Add `OPENAI_API_KEY` separately to Streamlit Secrets and GitHub Actions Secrets
if both environments run the workflow. Never commit a real key.

## Data and cost controls

- Requests use `store: false`.
- Every extraction task uses a strict JSON schema.
- Batches contain bounded titles, headings and article paragraphs.
- Full article bodies are not stored in the snapshot.
- The model may return only specific fashion concepts; passing mentions and
  vague themes are rejected by deterministic filters.
- The blog can cite only URLs already stored in the ranked evidence.
- Token usage and an estimated model cost are stored in snapshot metadata.
- Explicit publisher titles/headings remain a deterministic fallback when the
  API is absent or one extraction batch fails.

Use **Data & Setup → Test OpenAI article extraction** before the first live
refresh. Pricing changes over time, so confirm current rates in the official
OpenAI documentation before budgeting.

Official references:

- <https://developers.openai.com/api/docs/guides/migrate-to-responses>
- <https://developers.openai.com/api/docs/guides/structured-outputs>
- <https://developers.openai.com/api/docs/pricing>
