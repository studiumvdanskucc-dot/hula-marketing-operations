from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from typing import Any

from src.analysis.matching import match_products


def _series(
    base: float,
    lift: float,
    seed: int,
    *,
    points: int = 90,
    step_days: int = 1,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    today = datetime.now(tz=timezone.utc).date()
    output = []
    for day in range(points):
        progress = day / max(1, points - 1)
        value = base + lift * progress + math.sin(day / 7.5) * 4 + rng.uniform(-2, 2)
        output.append(
            {
                "date": (
                    today - timedelta(days=(points - 1 - day) * step_days)
                ).isoformat(),
                "value": max(0, min(100, round(value))),
                "raw_value": max(0, min(100, round(value))),
                "display_value": max(0, min(100, round(value))),
            }
        )
    return output


def demo_trends() -> list[dict[str, Any]]:
    rows = [
        ("east-west-bags", "East–West Bags", "east west bag", "Bags", 88, 4, 5, 82, 26, 145, "Strong consensus", 1),
        ("butter-yellow", "Butter Yellow", "butter yellow fashion", "Ready-to-Wear", 83, 3, 4, 76, 18, 84, "Strong consensus", 2),
        ("fisherman-sandals", "Fisherman Sandals", "fisherman sandals", "Shoes", 77, 3, 3, 72, 31, 112, "Strong consensus", 3),
        ("polka-dots", "Polka Dots", "polka dot fashion", "Ready-to-Wear", 70, 2, 3, 67, 12, 53, "Confirmed", 4),
        ("charm-jewellery", "Charm Jewellery", "charm jewellery", "Jewellery & Accessories", 64, 2, 2, 61, 9, 41, "Confirmed", 5),
        ("scarf-styling", "Scarf Styling", "scarf styling", "Jewellery & Accessories", 49, 1, 1, 73, 24, 36, "Single-publisher breakout", 6),
    ]
    publisher_panel = [
        ("Who What Wear", "whowhatwear"),
        ("Vogue", "vogue"),
        ("ELLE", "elle"),
        ("Marie Claire", "marie-claire"),
    ]
    output: list[dict[str, Any]] = []
    for (
        trend_id,
        name,
        google_query,
        category,
        editorial_score,
        publisher_count,
        article_count,
        google_score,
        week_change,
        year_change,
        stage,
        seed,
    ) in rows:
        context_series = _series(
            22 + seed * 2,
            30 + seed,
            seed,
            points=53,
            step_days=7,
        )
        recent_series = _series(28 + seed * 2, 28 + seed * 1.5, seed, points=90)
        today = datetime.now(tz=timezone.utc).date()
        demo_evidence = []
        for article_index in range(article_count):
            publisher, group = publisher_panel[article_index % publisher_count]
            demo_evidence.append(
                {
                    "publisher": publisher,
                    "publisher_id": group,
                    "publisher_group": group,
                    "url": (
                        f"https://{group}.demo.example/"
                        f"{trend_id}-{article_index + 1}"
                    ),
                    "article_title": f"Illustrative recent article: {name}",
                    "published_at": (
                        today - timedelta(days=1 + article_index * 2)
                    ).isoformat(),
                    "evidence_kind": "GPT article extraction",
                    "extraction_method": "Illustrative recent-article scan",
                    "explicit_label": name,
                    "trend_name": name,
                    "google_query": google_query,
                    "model_relevance_score": 0.92,
                    "explicit": True,
                }
            )
        priority = round(0.70 * editorial_score + 0.30 * google_score, 1)
        action = (
            "Act now"
            if publisher_count >= 3 and priority >= 70
            else "Test this week"
            if publisher_count >= 2 or week_change >= 20
            else "Watch"
        )
        publisher_names = [
            publisher for publisher, _ in publisher_panel[:publisher_count]
        ]
        output.append(
            {
                "id": trend_id,
                "name": name,
                "category": category,
                "score": priority,
                "confidence_score": priority,
                "data_completeness_score": 90,
                "editorial_consensus_score": editorial_score,
                "ranking_score": priority,
                "google_score": google_score,
                "google_query": google_query,
                "query": google_query,
                "x_score": None,
                "instagram_score": None,
                "publisher_count": publisher_count,
                "publisher_names": publisher_names,
                "publisher_groups": [
                    group for _, group in publisher_panel[:publisher_count]
                ],
                "article_count": article_count,
                "current_article_count": article_count,
                "commercial_article_count": article_count,
                "newest_published_at": demo_evidence[0]["published_at"],
                "overlap_label": (
                    "Strong editorial consensus"
                    if publisher_count >= 3
                    else "Confirmed by two publishers"
                    if publisher_count == 2
                    else "Single-publisher discovery"
                ),
                "commercial_evidence": demo_evidence,
                "google_trends_metrics": {
                    "current_week_mean": recent_series[-1]["raw_value"],
                    "previous_week_mean": recent_series[-8]["raw_value"],
                    "week_over_week_change_percent": week_change,
                    "seven_day_slope": round(week_change / 35, 2),
                    "ninety_day_baseline_mean": round(
                        sum(point["raw_value"] for point in recent_series)
                        / len(recent_series),
                        1,
                    ),
                    "year_over_year_change_percent": year_change,
                },
                "score_breakdown": {
                    "editorial": editorial_score,
                    "cross_source": min(100, 20 * publisher_count),
                    "google_trends": google_score,
                    "social": None,
                    "runway_celebrity": None,
                    "commercial": None,
                },
                "confidence": "High" if priority >= 75 else "Medium",
                "sources": [*publisher_names, "Google Trends"],
                "stage": stage,
                "why_now": (
                    f"Illustrative signal: {publisher_count} independent publishers; "
                    f"Google interest {week_change:+.0f}% week on week."
                ),
                "aliases": [name, name.lower(), name.replace("–", " ").lower()],
                "content_angles": [
                    f"The HULA edit: pre-owned pieces that tap into {name.lower()}",
                    f"Three ways to style {name.lower()} without buying new",
                    f"Then vs now: the designer archive view of {name.lower()}",
                ],
                "series": context_series,
                "display_series": [
                    {"date": point["date"], "value": point["raw_value"], "raw_value": point["raw_value"]}
                    for point in context_series
                ],
                "recent_series": recent_series,
                "recent_display_series": [
                    {"date": point["date"], "value": point["raw_value"], "raw_value": point["raw_value"]}
                    for point in recent_series
                ],
                "chart_ready": True,
                "recent_chart_ready": True,
                "decision_ready": True,
                "business_action": action,
                "live_discovered": False,
                "seed_only": False,
                "primary_discovery_origin": "demo",
                "discovery_origin_label": "Illustrative publisher-consensus demo",
                "is_demo": True,
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
                "editorial_publishers": "DEMO · illustrative recent articles",
                "commercial_websites": "DEMO · illustrative recent articles",
                "google_trends": "DEMO · illustrative 0–100 timelines",
                "x_apify": "RETIRED · not used by pipeline 4.0",
                "instagram_hashtags": "RETIRED · not used by pipeline 4.0",
                "shopify": "DEMO · illustrative catalogue",
                "openai": "DEMO · illustrative structured extraction",
                "openrouter": "STANDBY",
            },
            "raw_counts": {
                "editorial_publishers_configured": 7,
                "editorial_articles_scanned": sum(
                    int(trend.get("article_count") or 0) for trend in trends
                ),
                "editorial_trends": len(trends),
                "editorial_overlap_trends": sum(
                    int(trend.get("publisher_count") or 0) >= 2
                    for trend in trends
                ),
                "google_chart_ready_terms": len(trends),
                "x_posts_collected": 0,
                "instagram_hashtags_returned": 0,
                "shopify_products": len(products),
            },
            "google_trends": {
                "provider": "illustrative demo",
                "market": "Worldwide",
                "context_timeframe": "today 12-m",
                "discovery_timeframe": "today 3-m",
                "chart_ready_terms": len(trends),
                "seed_terms_used": 0,
                "used_cache": False,
            },
            "warnings": [
                "Demo publisher names, links and measurements are illustrative. Add credentials and run a refresh for live evidence."
            ],
            "methodology_version": "3.0",
            "discovery_pipeline_version": "4.0",
            "quality_filter_version": "5.0",
            "google_display_schema_version": "3.0",
            "privacy": (
                "Pipeline 4.0 stores article metadata and short excerpts only; "
                "X and Instagram are not queried."
            ),
        },
        "methodology_version": "3.0",
        "trends": trends,
        "products": products,
        "recommendations": recommendations,
    }
