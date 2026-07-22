from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import FeatureUnion


DEFAULT_WEIGHTS = {
    "trend": 0.45,
    "match": 0.35,
    "readiness": 0.15,
    "freshness": 0.05,
}

IGNORE_TOKENS = {
    "and", "the", "for", "with", "from", "size", "one", "worn", "hardly",
    "designer", "fashion", "style", "styling", "trend", "trending",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in IGNORE_TOKENS
    }


def product_text(product: dict[str, Any]) -> str:
    return " ".join(
        [
            str(product.get("title", "")),
            str(product.get("vendor", "")),
            str(product.get("product_type", "")),
            " ".join(str(tag) for tag in product.get("tags", [])),
            str(product.get("description", ""))[:1200],
        ]
    ).lower()


def trend_text(trend: dict[str, Any]) -> str:
    return " ".join(
        [
            str(trend.get("name", "")),
            str(trend.get("category", "")),
            " ".join(str(alias) for alias in trend.get("aliases", [])),
        ]
    ).lower()


def _freshness(created_at: Any) -> float:
    if not created_at:
        return 45.0
    raw = str(created_at).replace("Z", "+00:00")
    try:
        created = datetime.fromisoformat(raw)
    except ValueError:
        return 45.0
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    days = max(0, (datetime.now(tz=timezone.utc) - created).days)
    if days <= 14:
        return 100.0
    if days <= 45:
        return 82.0
    if days <= 90:
        return 65.0
    if days <= 180:
        return 48.0
    return 35.0


def _readiness(product: dict[str, Any]) -> float:
    if int(product.get("inventory") or 0) <= 0:
        return 0.0
    score = 45.0  # one available piece is normal for a pre-owned assortment
    if product.get("image_url"):
        score += 30
    if product.get("description"):
        score += 15
    if product.get("tags") or product.get("product_type"):
        score += 10
    return min(100.0, score)


def _category_fit(trend: dict[str, Any], product: dict[str, Any]) -> float:
    category = str(trend.get("category", "")).lower()
    product_blob = product_text(product)
    rules = {
        "bags": {"bag", "bags", "handbag", "tote", "clutch", "pouch"},
        "shoes": {"shoe", "shoes", "sandal", "sandals", "boot", "boots", "flat", "flats", "heel", "heels", "loafer", "loafers"},
        "jewellery & accessories": {"jewellery", "jewelry", "earring", "earrings", "necklace", "bracelet", "belt", "scarf", "hat", "accessory"},
        "ready-to-wear": {"dress", "skirt", "top", "shirt", "jacket", "coat", "blazer", "cardigan", "pants", "trousers", "denim"},
    }
    words = rules.get(category)
    if not words:
        return 0.5
    return 1.0 if any(word in product_blob for word in words) else 0.0


def _reason(trend: dict[str, Any], product: dict[str, Any], overlap: set[str]) -> str:
    matched = ", ".join(sorted(overlap)[:3])
    if matched:
        return f"Strong catalogue match through {matched}; available now with usable product content."
    if _category_fit(trend, product) > 0:
        return f"Category-level match for {str(trend.get('name', '')).lower()}, with stock available now."
    return "A softer editorial match worth reviewing before campaign selection."


def match_products(
    trends: list[dict[str, Any]],
    products: list[dict[str, Any]],
    *,
    max_per_trend: int = 12,
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    weight_total = sum(max(0.0, value) for value in weights.values()) or 1.0
    weights = {key: max(0.0, value) / weight_total for key, value in weights.items()}
    eligible = [
        product
        for product in products
        if int(product.get("inventory") or 0) > 0
        and str(product.get("status", "ACTIVE")).upper() == "ACTIVE"
    ]
    if not trends or not eligible:
        return []
    product_docs = [product_text(product) for product in eligible]
    trend_docs = [trend_text(trend) for trend in trends]
    vectorizer = FeatureUnion(
        [
            (
                "words",
                TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1),
            ),
            (
                "chars",
                TfidfVectorizer(
                    analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1
                ),
            ),
        ]
    )
    matrix = vectorizer.fit_transform([*product_docs, *trend_docs])
    product_matrix = matrix[: len(eligible)]
    trend_matrix = matrix[len(eligible) :]
    similarities = cosine_similarity(trend_matrix, product_matrix)
    recommendations: list[dict[str, Any]] = []
    for trend_index, trend in enumerate(trends):
        query_tokens = _tokens(trend_text(trend))
        candidates: list[dict[str, Any]] = []
        for product_index, product in enumerate(eligible):
            product_tokens = _tokens(product_docs[product_index])
            overlap = query_tokens & product_tokens
            overlap_score = min(1.0, len(overlap) / max(2, min(5, len(query_tokens))))
            category_score = _category_fit(trend, product)
            semantic = float(similarities[trend_index, product_index])
            match_score = min(
                100.0,
                68 * semantic + 22 * overlap_score + 10 * category_score,
            )
            if match_score < 7.5:
                continue
            readiness = _readiness(product)
            freshness = _freshness(product.get("created_at"))
            trend_score = float(trend.get("score") or 0)
            opportunity = (
                weights["trend"] * trend_score
                + weights["match"] * match_score
                + weights["readiness"] * readiness
                + weights["freshness"] * freshness
            )
            if readiness == 0:
                opportunity = 0
            candidates.append(
                {
                    "trend_id": trend.get("id"),
                    "trend_name": trend.get("name"),
                    "product_id": product.get("id"),
                    "opportunity_score": round(opportunity, 1),
                    "match_score": round(match_score, 1),
                    "trend_score": round(trend_score, 1),
                    "readiness_score": round(readiness, 1),
                    "freshness_score": round(freshness, 1),
                    "reason": _reason(trend, product, overlap),
                    "content_hook": (
                        f"Why {str(trend.get('name', '')).lower()} is back — "
                        f"and the pre-owned piece to wear now."
                    ),
                }
            )
        recommendations.extend(
            sorted(candidates, key=lambda item: item["opportunity_score"], reverse=True)[
                :max_per_trend
            ]
        )
    return recommendations
