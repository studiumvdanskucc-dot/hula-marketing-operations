from __future__ import annotations

import json

from src.connectors.openai_responses import OpenAIResponsesConnector


class FakeResponse:
    ok = True
    status_code = 200
    headers = {"x-request-id": "test-request"}

    def __init__(self, result: dict, *, input_tokens: int = 100, output_tokens: int = 20) -> None:
        self._payload = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": json.dumps(result)}
                    ],
                }
            ],
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        }

    def json(self) -> dict:
        return self._payload


def test_responses_connection_uses_strict_schema_and_store_false(monkeypatch) -> None:
    connector = OpenAIResponsesConnector("test-key")
    captured: dict = {}

    def post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "body": json, "timeout": timeout})
        return FakeResponse({"ok": True})

    monkeypatch.setattr(connector.session, "post", post)
    result = connector.test_connection()

    assert result == {"ok": True, "model": "gpt-5.6-luna"}
    assert captured["body"]["store"] is False
    assert captured["body"]["text"]["format"]["type"] == "json_schema"
    assert captured["body"]["text"]["format"]["strict"] is True
    assert connector.usage_log[0]["estimated_cost_usd"] is not None


def test_evidence_locked_blog_returns_only_supplied_source_urls(monkeypatch) -> None:
    connector = OpenAIResponsesConnector("test-key")
    model_result = {
        "title": "The Layered Tops Edit",
        "dek": "A considered weekly signal.",
        "body_markdown": "## Why now\n\nStored evidence supports a styling shift.",
        "shopify_excerpt": "The layered edit.",
        "seo_title": "Layered tops | HULA",
        "seo_description": "Explore HULA's layered edit.",
        "claims": [
            {
                "claim": "Stored evidence supports a styling shift.",
                "status": "confirmed",
                "product_id": "",
                "source_indices": [1],
                "evidence_note": "Supported by source 1.",
            }
        ],
        "editorial_notes": [],
    }

    def post(url, *, headers, json, timeout):
        return FakeResponse(model_result)

    monkeypatch.setattr(connector.session, "post", post)
    result = connector.evidence_locked_blog(
        {
            "name": "Layered tops",
            "evidence": [
                {
                    "source_name": "Who What Wear",
                    "source_url": "https://example.com/supplied",
                    "title": "Layered tops report",
                    "evidence_summary": "The report names layered tops.",
                }
            ],
        },
        [{"id": "p1", "title": "Silk cami", "vendor": "Demo"}],
        reason="Weekly signal",
    )

    assert result["evidence_locked"] is True
    assert result["grounded"] is False
    assert result["sources"] == [
        {
            "index": 1,
            "title": "Layered tops report",
            "url": "https://example.com/supplied",
        }
    ]
