# Grounded Wednesday blog

Gemini runs after deterministic trend ranking and product matching. It cannot
change a trend score.

## Secrets

```toml
GEMINI_API_KEY = "your-complete-key"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_TIMEOUT_SECONDS = "180"
GEMINI_GROUNDING_ENABLED = "true"
```

Add the same API key to Streamlit Secrets and GitHub Actions Secrets. Use
**Data & Setup → Test Gemini research** before the first scheduled refresh.

The connection test uses ordinary Gemini generation and works on the free tier.
The publishable researched-blog workflow uses live Google Search grounding,
which Google currently makes available only to billing-enabled projects. The
first 5,000 Gemini 3 grounded prompts per month have no separate Search
surcharge; normal model-token charges still apply.

## Editorial safeguards

- The draft targets 700–1,000 words.
- Google Search grounding is enabled through the Gemini API.
- Gemini 3.6 uses low thinking for long blog drafts and minimal thinking for
  connection tests, leaving enough output capacity for the visible JSON.
- One transient HTTP-200 response with no visible text is retried automatically.
- If both responses are blank, the error reports Gemini's finish reason and
  token usage instead of hiding the cause.
- Exact-product celebrity/runway claims require credible supporting evidence.
- Similar designs are labelled `similar_design_only` and stay outside factual
  publishable copy.
- Confirmed and uncertain claims are displayed separately with source URLs.
- If Gemini fails or reaches a quota, the app creates a clearly labelled safe
  fallback with no web-derived claims.
- Only public trend and selected-product information is sent. Customer and
  order information is never included.

The Wednesday workflow drafts the strongest decision-ready trend. The
**Wednesday Blog** page can generate another eligible story and includes
separate reasons for Soho and The Hub.

Official grounding guide:
<https://ai.google.dev/gemini-api/docs/google-search>
