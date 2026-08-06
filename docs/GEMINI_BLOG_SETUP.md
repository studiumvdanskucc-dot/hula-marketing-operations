# Gemini evidence-locked fallback

OpenAI Sol is the recommended blog writer. Gemini remains an optional fallback
when no OpenAI API key is configured.

```toml
GEMINI_API_KEY = "your-private-key"
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_TIMEOUT_SECONDS = "180"
GEMINI_GROUNDING_ENABLED = "false"
```

The writer receives only the selected trend's stored evidence and public HULA
product fields. Live Google Search grounding is deliberately disabled so the
blog cannot introduce sources that are absent from the scored weekly snapshot.

Confirmed claims require valid source indices. Uncertain or similar-design
claims remain in the editorial QA panel and outside factual publishable copy.
If generation fails, the app produces a labelled deterministic draft with no
unsupported celebrity, runway or archive claims.
