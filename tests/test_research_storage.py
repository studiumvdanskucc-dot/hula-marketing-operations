from __future__ import annotations

from src.connectors.gemini_research import (
    attach_claim_sources,
    extract_json_object,
    grounding_sources,
)
from src.editorial.evidence import normalise_blog_evidence
from src.connectors.supabase_store import SupabaseStore


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
