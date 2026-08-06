from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.editorial.evidence import normalise_blog_evidence


def fallback_blog(
    trend: dict[str, Any],
    products: list[dict[str, Any]],
    *,
    reason: str,
    stores: list[str] | None = None,
) -> dict[str, Any]:
    names = [
        f"{product.get('vendor', '')} {product.get('title', '')}".strip()
        for product in products[:5]
    ]
    product_lines = "\n".join(f"- {name}" for name in names if name)
    destinations = ", ".join(stores or ["HULA Soho", "The Hub", "online"])
    trend_name = str(trend.get("name") or "This week's signal")
    body = f"""## Why it matters now

{trend.get('why_now') or 'The available trend evidence makes this a useful story to test this week.'}

## The HULA edit

{product_lines or '- Review the matched HULA products before publishing.'}

## A circular way to wear it

The strongest version of a trend does not need to be newly made. Choosing a
well-constructed pre-owned designer piece keeps exceptional fashion in
circulation and gives the idea a life beyond a single season.

Explore the edit at {destinations}. Availability is one of one.
"""
    return normalise_blog_evidence(
        {
            "title": f"The {trend_name} Edit",
            "dek": "A working HULA draft created from the ranked signal and selected products.",
            "body_markdown": body,
            "shopify_excerpt": f"Discover HULA's pre-owned {trend_name.lower()} edit.",
            "seo_title": f"{trend_name} | HULA",
            "seo_description": f"Explore pre-owned designer pieces inspired by {trend_name.lower()} at HULA.",
            "claims": [],
            "editorial_notes": [
                "The configured writing model was unavailable. This fallback contains no unsupported celebrity or runway claims."
            ],
            "sources": [
                {
                    "index": index,
                    "title": str(row.get("title") or row.get("source_name") or f"Source {index}"),
                    "url": str(row.get("source_url") or ""),
                }
                for index, row in enumerate(trend.get("evidence") or [], 1)
                if str(row.get("source_url") or "").startswith(("https://", "http://"))
            ],
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "model": "deterministic fallback",
            "grounded": False,
            "evidence_locked": True,
            "reason": reason,
            "trend_id": trend.get("id"),
            "product_ids": [product.get("id") for product in products[:5]],
        }
    )


def generate_evidence_blog(
    connector: Any,
    trend: dict[str, Any],
    products: list[dict[str, Any]],
    *,
    reason: str,
    stores: list[str] | None = None,
) -> dict[str, Any]:
    result = connector.evidence_locked_blog(
        trend,
        products,
        reason=reason,
        stores=stores,
    )
    result.update(
        {
            "reason": reason,
            "trend_id": trend.get("id"),
            "product_ids": [product.get("id") for product in products[:5]],
        }
    )
    return normalise_blog_evidence(result)


def generate_researched_blog(
    connector: Any,
    trend: dict[str, Any],
    products: list[dict[str, Any]],
    *,
    reason: str,
    stores: list[str] | None = None,
) -> dict[str, Any]:
    """Backward-compatible name for the evidence-locked writer."""

    return generate_evidence_blog(
        connector,
        trend,
        products,
        reason=reason,
        stores=stores,
    )
