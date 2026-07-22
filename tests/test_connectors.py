from __future__ import annotations

import pytest

from src.connectors.apify_x import normalize_post
from src.connectors.openrouter import _extract_json
from src.connectors.shopify import ShopifyError, normalize_shop
from src.diagnostics import hybrid_explanation, safe_error, source_diagnostic_rows


def test_shopify_domain_normalization() -> None:
    assert normalize_shop("https://hula-hk.myshopify.com/") == "hula-hk"
    assert normalize_shop("hula-hk") == "hula-hk"
    with pytest.raises(ShopifyError):
        normalize_shop("not a valid shop")


def test_apify_normalizer_handles_common_actor_fields() -> None:
    post = normalize_post(
        {
            "fullText": "Butter yellow is the colour of the season",
            "createdAt": "2026-07-20T10:00:00Z",
            "likeCount": 12,
            "retweetCount": 3,
            "replyCount": 2,
            "viewCount": 800,
            "author": {"userName": "not-persisted"},
        }
    )
    assert post is not None
    assert post["engagement"] == 20
    assert "author" not in post
    assert post["author_hash"]
    assert post["post_hash"]


def test_openrouter_json_extraction_handles_fenced_payload() -> None:
    assert _extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_hybrid_explanation_says_csv_is_not_openrouter_failure() -> None:
    message = hybrid_explanation(
        {
            "mode": "hybrid",
            "catalogue_source": "csv",
            "source_status": {
                "google_trends": "live",
                "x_apify": "live",
                "shopify": "CSV snapshot · 199 products",
                "openrouter": "live · qwen/qwen3-vl-32b-instruct",
            },
        }
    )
    assert "expected" in message.lower()
    assert "does not mean OpenRouter failed" in message


def test_safe_error_redacts_secret() -> None:
    secret = "sk-or-v1-private"
    detail = safe_error(RuntimeError(f"Provider rejected {secret}"), [secret])
    assert secret not in detail
    assert "[redacted]" in detail


def test_diagnostics_distinguish_current_config_from_old_snapshot() -> None:
    rows = source_diagnostic_rows(
        {
            "catalogue_source": "csv",
            "source_status": {
                "google_trends": "live",
                "x_apify": "not configured",
                "shopify": "CSV snapshot · 199 products",
                "openrouter": "not configured",
            },
        },
        google_configured=True,
        apify_configured=True,
        shopify_configured=False,
        openrouter_configured=True,
    )
    openrouter = next(row for row in rows if row["Source"] == "OpenRouter / Qwen")
    catalogue = next(row for row in rows if row["Source"] == "Product catalogue")
    assert openrouter["Configured now"] == "Yes"
    assert "older status" in openrouter["Meaning / next action"]
    assert "Expected" in catalogue["Meaning / next action"]


def test_partial_apify_status_has_specific_diagnostic_action() -> None:
    rows = source_diagnostic_rows(
        {
            "catalogue_source": "csv",
            "source_status": {
                "x_apify": "partial · 12/14 searches · 500 unique posts",
            },
        },
        google_configured=False,
        apify_configured=True,
        shopify_configured=False,
        openrouter_configured=False,
    )
    apify = next(row for row in rows if row["Source"] == "X via Apify")
    assert "Some planned searches completed" in apify["Meaning / next action"]
