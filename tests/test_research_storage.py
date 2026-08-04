from __future__ import annotations

from src.connectors.gemini_research import (
    GeminiResearchConnector,
    GeminiResearchError,
    _response_text,
    attach_claim_sources,
    extract_json_object,
    grounding_sources,
)
from src.editorial.evidence import normalise_blog_evidence
from src.connectors.supabase_store import SupabaseStore
import pytest


class _StubResponse:
    ok = True
    status_code = 200
    text = ""

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class _StubSession:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.requests: list[dict] = []

    def post(self, *_args, **kwargs) -> _StubResponse:
        self.requests.append(kwargs)
        return _StubResponse(self.payloads.pop(0))


def test_gemini_json_and_grounding_metadata_are_normalized() -> None:
    assert extract_json_object('Result:\n{"title":"Mini dress edit"}') == {
        "title": "Mini dress edit"
    }
    sources = grounding_sources(
        {
            "candidates": [
                {
                    "groundingMetadata": {
                        "groundingChunks": [
                            {
                                "web": {
                                    "title": "Runway source",
                                    "uri": "https://example.com/runway",
                                }
                            },
                            {
                                "web": {
                                    "title": "Duplicate",
                                    "uri": "https://example.com/runway",
                                }
                            },
                        ]
                    }
                }
            ]
        }
    )
    assert sources == [
        {
            "index": 1,
            "title": "Runway source",
            "url": "https://example.com/runway",
        }
    ]


def test_new_supabase_secret_uses_apikey_header_not_bearer_jwt() -> None:
    store = SupabaseStore(
        "https://project.supabase.co",
        "sb_secret_example",
    )
    assert store.headers["apikey"] == "sb_secret_example"
    assert "Authorization" not in store.headers


def test_confirmed_claim_requires_matching_grounding_support() -> None:
    payload = {
        "candidates": [
            {
                "groundingMetadata": {
                    "groundingChunks": [
                        {
                            "web": {
                                "title": "Event report",
                                "uri": "https://example.com/event",
                            }
                        }
                    ],
                    "groundingSupports": [
                        {
                            "segment": {
                                "text": "Alex Example wore the exact blue mini dress."
                            },
                            "groundingChunkIndices": [0],
                        }
                    ],
                }
            }
        ]
    }
    researched = attach_claim_sources(
        {
            "body_markdown": (
                "Alex Example wore the exact blue mini dress. "
                "Another person wore it in Paris."
            ),
            "claims": [
                {
                    "claim": "Alex Example wore the exact blue mini dress.",
                    "status": "confirmed",
                },
                {
                    "claim": "Another person wore it in Paris.",
                    "status": "confirmed",
                },
            ],
            "sources": grounding_sources(payload),
        },
        payload,
    )
    normalised = normalise_blog_evidence(researched)
    assert normalised["claims"][0]["status"] == "confirmed"
    assert normalised["claims"][0]["source_indices"] == [1]
    assert normalised["claims"][1]["status"] == "uncertain"
    assert "Another person wore it in Paris." not in normalised["body_markdown"]


def test_legacy_supabase_service_role_keeps_bearer_header() -> None:
    store = SupabaseStore(
        "https://project.supabase.co",
        "legacy.jwt.value",
    )
    assert store.headers["Authorization"] == "Bearer legacy.jwt.value"


def test_empty_gemini_response_reports_finish_reason_and_tokens() -> None:
    payload = {
        "candidates": [
            {
                "content": {"parts": []},
                "finishReason": "MAX_TOKENS",
            }
        ],
        "usageMetadata": {
            "candidatesTokenCount": 0,
            "thoughtsTokenCount": 50,
            "totalTokenCount": 61,
        },
    }
    with pytest.raises(GeminiResearchError) as error:
        _response_text(payload)
    detail = str(error.value)
    assert "finish reason: MAX_TOKENS" in detail
    assert "thought tokens: 50" in detail


def test_gemini_3_diagnostic_leaves_room_for_visible_json() -> None:
    session = _StubSession(
        [
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"ok":true}'}]},
                        "finishReason": "STOP",
                    }
                ]
            }
        ]
    )
    connector = GeminiResearchConnector("secret", model="gemini-3.6-flash")
    connector.session = session

    assert connector.test_connection() == {
        "ok": True,
        "model": "gemini-3.6-flash",
    }
    config = session.requests[0]["json"]["generationConfig"]
    assert config["maxOutputTokens"] == 1024
    assert config["thinkingConfig"]["thinkingLevel"] == "minimal"
    assert config["responseFormat"]["text"]["mimeType"] == "application/json"
    assert "temperature" not in config


def test_gemini_retries_one_transient_blank_response() -> None:
    session = _StubSession(
        [
            {
                "candidates": [
                    {
                        "content": {"parts": []},
                        "finishReason": "STOP",
                    }
                ]
            },
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": '{"ok":true}'}]},
                        "finishReason": "STOP",
                    }
                ]
            },
        ]
    )
    connector = GeminiResearchConnector("secret", model="gemini-3.6-flash")
    connector.session = session

    assert connector.test_connection()["ok"] is True
    assert len(session.requests) == 2


def test_researched_blog_attaches_claim_level_grounding(monkeypatch) -> None:
    payload = {
        "candidates": [
            {
                "groundingMetadata": {
                    "groundingChunks": [
                        {
                            "web": {
                                "title": "Runway report",
                                "uri": "https://example.com/runway",
                            }
                        }
                    ],
                    "groundingSupports": [
                        {
                            "segment": {
                                "text": "The exact blue mini dress appeared on the runway."
                            },
                            "groundingChunkIndices": [0],
                        }
                    ],
                }
            }
        ]
    }
    text = """
    {
      "title": "Blue Mini Dresses",
      "dek": "A grounded edit.",
      "body_markdown": "The exact blue mini dress appeared on the runway.",
      "shopify_excerpt": "A grounded edit.",
      "seo_title": "Blue Mini Dresses | HULA",
      "seo_description": "A grounded HULA edit.",
      "claims": [{
        "claim": "The exact blue mini dress appeared on the runway.",
        "status": "confirmed",
        "product_id": "1",
        "evidence_note": "Matched to the source."
      }],
      "editorial_notes": []
    }
    """
    connector = GeminiResearchConnector("secret", model="gemini-3.6-flash")
    monkeypatch.setattr(
        connector,
        "_generate_text",
        lambda *_args, **_kwargs: (payload, text),
    )

    result = connector.researched_blog(
        {"name": "Mini dress"},
        [{"id": "1", "title": "Blue Mini Dress"}],
        reason="This week's strongest product trend",
    )

    assert result["claims"][0]["source_indices"] == [1]
