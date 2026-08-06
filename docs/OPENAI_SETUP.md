# OpenAI mixed-model setup

The recommended first-party workflow uses the Responses API with strict
structured JSON output:

- `gpt-5.6-luna` for inexpensive relevance checks;
- `gpt-5.6-terra` for conservative alias grouping;
- `gpt-5.6-sol` for the final short-list synthesis and evidence-locked blog.

Python—not a model—calculates dates, trends, weights, caps, confidence,
coverage, HULA opportunity and ordering.

## Secrets

```toml
OPENAI_API_KEY = "your-private-key"
OPENAI_API_URL = "https://api.openai.com/v1/responses"
OPENAI_LUNA_MODEL = "gpt-5.6-luna"
OPENAI_TERRA_MODEL = "gpt-5.6-terra"
OPENAI_SOL_MODEL = "gpt-5.6-sol"
OPENAI_TIMEOUT_SECONDS = "180"
```

Add `OPENAI_API_KEY` separately to Streamlit Secrets and GitHub Actions Secrets
if both environments run the workflow. Never put a real key in a repository.

## Behaviour and cost controls

- Requests use `store: false`.
- Each task uses a strict JSON schema.
- Sol receives a short list and compact evidence summaries—not whole pages.
- The blog can cite only URLs already stored in the trend evidence.
- API token usage and a model-price estimate are stored in snapshot metadata.
- OpenRouter is used only when OpenAI is absent; deterministic local logic is
  the final fallback.

Use **Data & Setup → Test OpenAI Responses** before the first scheduled run.
Pricing can change, so confirm current rates in the official OpenAI pricing
documentation before budgeting.

Official references:

- <https://developers.openai.com/api/docs/guides/migrate-to-responses>
- <https://developers.openai.com/api/docs/guides/structured-outputs>
- <https://developers.openai.com/api/docs/pricing>
