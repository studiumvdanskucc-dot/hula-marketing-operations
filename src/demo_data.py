from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from src.analysis.matching import match_products


def _series(base: float, lift: float, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    today = datetime.now(tz=timezone.utc).date()
    points = []
    for week in range(13):
        progress = week / 12
        value = base + lift * progress + math.sin(week / 1.8) * 4 + rng.uniform(-3, 3)
        points.append(
            {
                "date": (today - timedelta(days=(12 - week) * 7)).isoformat(),
                "value": max(0, min(100, round(value))),
            }
        )
    return points


def demo_trends() -> list[dict[str, Any]]:
    rows = [
        ("east-west-bags", "East–West Bags", "Bags", 92, 89, 86, 74, 128, 486, "Rising", 1),
        ("butter-yellow", "Butter Yellow", "Ready-to-Wear", 87, 84, 82, 52, 91, 344, "Established", 2),
        ("fisherman-sandals", "Fisherman Sandals", "Shoes", 83, 78, 85, 67, 142, 296, "Emerging", 3),
        ("polka-dots", "Polka Dots", "Ready-to-Wear", 79, 75, 77, 39, 64, 251, "Rising", 4),
        ("charm-jewellery", "Charm Jewellery", "Jewellery & Accessories", 75, 68, 79, 28, 88, 223, "Rising", 5),
        ("scarf-styling", "Scarf Styling", "Jewellery & Accessories", 71, 72, 64, 34, 43, 179, "Established", 6),
    ]
    output = []
    for trend_id, name, category, score, google, x_score, search_growth, social_growth, mentions, stage, seed in rows:
        output.append(
            {
                "id": trend_id,
                "name": name,
                "category": category,
                "score": score,
                "google_score": google,
                "x_score": x_score,
                "search_interest": round(48 + score / 2.2, 1),
                "search_baseline": round(42 + score / 4.0, 1),
                "search_momentum": search_growth,
                "mentions": mentions,
                "previous_mentions": max(1, int(mentions / (1 + social_growth / 100))),
                "mention_growth": social_growth,
                "unique_authors": max(8, int(mentions * 0.62)),
                "previous_unique_authors": max(4, int(mentions * 0.38)),
                "author_growth": round(social_growth * 0.82, 1),
                "engagement": mentions * 18,
                "engagement_per_1000_views": round(18 + seed * 1.7, 1),
                "source_breadth": 4,
                "expert_score": max(40, x_score - 8),
                "commercial_source_score": max(40, x_score - 8),
                "expert_mentions": 3 + seed,
                "expert_authors": 2 + seed // 2,
                "commercial_priority_mentions": 2 + seed // 2,
                "commercial_priority_authors": 2,
                "commercial_weighted_mentions": 6 + seed,
                "duplicate_rate": 4.0 + seed,
                "spam_rate": 2.0,
                "evidence_quality": 91.0 - seed,
                "novelty_score": max(0, 100 - seed * 12),
                "confidence": "High",
                "sources": ["Google Trends", "Open X topics", "Priority commercial panel"],
                "stage": stage,
                "why_now": (
                    f"Demo signal: search momentum is {search_growth:+.0f}% and X conversation "
                    f"is {social_growth:+.0f}% week on week."
                ),
                "aliases": [name, name.lower(), name.replace("–", " ").lower()],
                "content_angles": [
                    f"The HULA edit: pre-owned pieces that tap into {name.lower()}",
                    f"Three ways to style {name.lower()} without buying new",
                    f"Then vs now: the designer archive view of {name.lower()}",
                ],
                "series": _series(28 + seed * 2, 28 + seed * 1.5, seed),
            }
        )
    return output


def demo_products() -> list[dict[str, Any]]:
    now = datetime.now(tz=timezone.utc)
    rows = [
        ("demo-1", "Pink Intrecciato East–West Bag", "Bottega Veneta", "Bag", ["east west", "pink", "woven leather", "shoulder bag"], "assets/demo_bag.svg", 9),
        ("demo-2", "Butter Yellow Tweed Jacket", "Chanel", "Jacket", ["butter yellow", "tweed", "cropped", "ready to wear"], "assets/demo_jacket.svg", 18),
        ("demo-3", "Leather Fisherman Sandals", "Prada", "Sandals", ["fisherman sandals", "leather", "summer shoes"], "assets/demo_sandals.svg", 25),
        ("demo-4", "Polka-Dot Silk Midi Dress", "Saint Laurent", "Dress", ["polka dots", "silk", "midi dress"], "assets/demo_dress.svg", 33),
        ("demo-5", "Gold Charm Chain Belt", "Chanel", "Belt", ["charm jewellery", "chain", "statement belt"], "assets/demo_belt.svg", 47),
        ("demo-6", "Printed Silk Twilly Scarf", "Louis Vuitton", "Scarf", ["scarf styling", "silk", "printed"], "assets/demo_scarf.svg", 12),
        ("demo-7", "Ballet Flats with Bow", "Miu Miu", "Shoes", ["ballet flats", "bow", "flat shoes"], "assets/demo_flats.svg", 61),
        ("demo-8", "Natural Raffia Market Tote", "Loewe", "Bag", ["raffia bag", "woven", "summer bag", "tote"], "assets/demo_raffia.svg", 76),
    ]
    products = []
    for index, (product_id, title, vendor, product_type, tags, image, age) in enumerate(rows):
        products.append(
            {
                "id": product_id,
                "numeric_id": product_id,
                "title": title,
                "handle": product_id,
                "description": f"Demo catalogue item with {', '.join(tags)} attributes.",
                "product_type": product_type,
                "vendor": vendor,
                "tags": tags,
                "status": "ACTIVE",
                "created_at": (now - timedelta(days=age)).isoformat(),
                "updated_at": now.isoformat(),
                "inventory": 1,
                "price": 4200 + index * 650,
                "currency": "HKD",
                "image_url": image,
                "image_alt": title,
                "product_url": "",
                "admin_url": "",
                "is_demo": True,
            }
        )
    return products


def demo_snapshot() -> dict[str, Any]:
    trends = demo_trends()
    products = demo_products()
    recommendations = match_products(trends, products)
    return {
        "meta": {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "mode": "demo",
            "region": "HK",
            "catalogue_source": "demo",
            "catalogue_filename": "",
            "source_status": {
                "google_trends": "demo",
                "x_apify": "demo",
                "shopify": "demo",
                "openrouter": "not used",
            },
            "raw_counts": {"x_posts_aggregated": 0, "shopify_products": len(products)},
            "x_listening": {
                "mode": "demo",
                "planned": 14,
                "succeeded": 0,
                "failed": 0,
                "collected": 0,
                "unique": 0,
                "duplicates_removed": 0,
                "semantic_clustering": "illustrative",
                "expert_accounts": 14,
                "priority_commercial_accounts": 3,
            },
            "warnings": [
                "Demo data is illustrative. Add credentials and select Refresh data for live evidence."
            ],
            "methodology_version": "0.2",
        },
        "trends": trends,
        "products": products,
        "recommendations": recommendations,
    }
