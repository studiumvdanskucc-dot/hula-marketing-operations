from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.analysis.trends import (
    build_topic_clusters,
    canonical_name,
    extract_x_signals,
    generic_trend_reason,
    merge_trend_signals,
    sanitize_snapshot_trends,
    score_google_series,
)


def test_extract_x_signals_finds_fashion_phrase_and_growth() -> None:
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    posts = []
    for days_ago in (1, 2, 3, 4):
        posts.append(
            {
                "text": "East west bag styling is everywhere #EastWestBag",
                "created_at": (now - timedelta(days=days_ago)).isoformat(),
                "engagement": 20,
                "views": 500,
            }
        )
    posts.append(
        {
            "text": "An east west bag edit",
            "created_at": (now - timedelta(days=10)).isoformat(),
            "engagement": 5,
            "views": 100,
        }
    )
    signals = extract_x_signals(posts, now=now)
    row = next(signal for signal in signals if signal["name"] == "East–West Bags")
    assert row["mentions"] == 4
    assert row["previous_mentions"] == 1
    assert row["mention_growth"] > 0


def test_google_series_scores_momentum() -> None:
    series = {
        "butter yellow fashion": [
            {"date": f"2026-06-{index:02d}", "value": value}
            for index, value in enumerate([10, 11, 12, 14, 18, 25, 40, 60], 1)
        ],
        "polka dot outfit": [
            {"date": f"2026-06-{index:02d}", "value": value}
            for index, value in enumerate([50, 49, 51, 50, 48, 47, 46, 45], 1)
        ],
    }
    rows = score_google_series(series)
    butter = next(row for row in rows if row["name"] == "Butter Yellow")
    dots = next(row for row in rows if row["name"] == "Polka Dots")
    assert butter["search_momentum"] > dots["search_momentum"]
    assert butter["google_score"] > dots["google_score"]


def test_cross_source_agreement_increases_confidence() -> None:
    google = [
        {
            "id": "east-west-bags",
            "name": "East–West Bags",
            "google_score": 80,
            "search_momentum": 50,
            "search_interest": 75,
            "series": [],
            "aliases": ["east west bag"],
        }
    ]
    social = [
        {
            "id": "east-west-bags",
            "name": "East–West Bags",
            "x_score": 70,
            "mention_growth": 90,
            "mentions": 30,
            "aliases": ["east west bags"],
        }
    ]
    merged = merge_trend_signals(google, social)
    assert merged[0]["confidence"] == "High"
    assert merged[0]["sources"] == ["Google Trends", "Open X topics"]
    assert merged[0]["score"] >= 70


def test_semantic_aliases_group_ballet_pumps_and_flats() -> None:
    clusters = build_topic_clusters(
        [
            {"phrase": "ballet pumps", "count": 8},
            {"phrase": "ballet flats", "count": 10},
            {"phrase": "suede bags", "count": 5},
        ]
    )
    ballet = next(cluster for cluster in clusters if cluster["name"] == "Ballet Flats")
    assert "ballet pumps" in ballet["aliases"]
    assert "ballet flats" in ballet["aliases"]


def test_x_score_tracks_unique_authors_and_expert_confirmation() -> None:
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    posts = []
    for index in range(5):
        posts.append(
            {
                "text": "Ballet pumps and ballet flats are back",
                "created_at": (now - timedelta(days=1)).isoformat(),
                "author_hash": f"author-{index}",
                "post_hash": f"post-{index}",
                "engagement": 20,
                "views": 1000,
                "listening_window": "current",
                "listening_groups": ["silhouette"],
                "evidence_channels": ["open"],
            }
        )
    posts.append(
        {
            "text": "Ballet flats lead the shoe conversation",
            "created_at": (now - timedelta(days=1)).isoformat(),
            "author_hash": "expert-1",
            "post_hash": "expert-post",
            "engagement": 30,
            "views": 1000,
            "listening_window": "current",
            "listening_groups": ["expert-1"],
            "evidence_channels": ["expert"],
            "is_expert": True,
        }
    )
    signals = extract_x_signals(posts, now=now)
    ballet = next(row for row in signals if row["name"] == "Ballet Flats")
    assert ballet["unique_authors"] == 5
    assert ballet["expert_mentions"] == 1
    assert ballet["expert_score"] is not None
    assert ballet["evidence_quality"] > 80


def test_generic_category_filter_keeps_specific_combinations() -> None:
    for broad in (
        "bag",
        "bags",
        "trousers",
        "garments",
        "designer bags",
        "mini",
        "ebay",
    ):
        assert generic_trend_reason(broad)

    for specific in (
        "black bags",
        "red trousers",
        "mini bags",
        "raffia bags",
        "east west bags",
    ):
        assert generic_trend_reason(specific) == ""


def test_non_fashion_topics_are_rejected_but_jane_is_kept_as_mary_janes() -> None:
    for unrelated in ("Interior Design", "Kindness", "wellness", "architecture"):
        assert generic_trend_reason(unrelated)

    assert generic_trend_reason("Jane") == ""
    assert canonical_name("Jane") == "Mary Janes"
    assert generic_trend_reason("Raffia Bags") == ""


def test_current_noise_snapshot_is_cleaned_and_jane_is_normalised() -> None:
    snapshot = {
        "meta": {"raw_counts": {}},
        "trends": [
            {"id": "jane", "name": "Jane"},
            {"id": "raffia-bags", "name": "Raffia Bags"},
            {"id": "interior-design", "name": "Interior Design"},
            {"id": "kindness", "name": "Kindness"},
        ],
        "recommendations": [
            {"trend_id": "jane", "product_id": "1"},
            {"trend_id": "raffia-bags", "product_id": "2"},
            {"trend_id": "interior-design", "product_id": "3"},
            {"trend_id": "kindness", "product_id": "4"},
        ],
    }

    cleaned = sanitize_snapshot_trends(snapshot)

    assert [trend["name"] for trend in cleaned["trends"]] == [
        "Mary Janes",
        "Raffia Bags",
    ]
    assert [row["trend_id"] for row in cleaned["recommendations"]] == [
        "mary-janes",
        "raffia-bags",
    ]
    removed = {row["term"] for row in cleaned["meta"]["filtered_terms"]}
    assert {"Interior Design", "Kindness"} <= removed


def test_generic_google_series_is_removed_and_audited() -> None:
    points = [
        {"date": f"2026-06-{index:02d}", "value": value}
        for index, value in enumerate([10, 15, 20, 30, 40, 50], 1)
    ]
    audit = []
    rows = score_google_series(
        {"bags": points, "black bags": points},
        audit=audit,
    )
    assert [row["name"] for row in rows] == ["Black Bags"]
    assert any(row["term"] == "bags" for row in audit)


def test_old_snapshot_is_cleaned_before_landing_page_renders() -> None:
    snapshot = {
        "meta": {"raw_counts": {}},
        "trends": [
            {"id": "bags", "name": "Bags"},
            {"id": "black-bags", "name": "Black Bags"},
        ],
        "recommendations": [
            {"trend_id": "bags", "product_id": "1"},
            {"trend_id": "black-bags", "product_id": "2"},
        ],
    }
    cleaned = sanitize_snapshot_trends(snapshot)
    assert [trend["name"] for trend in cleaned["trends"]] == ["Black Bags"]
    assert [row["product_id"] for row in cleaned["recommendations"]] == ["2"]
    assert cleaned["meta"]["filtered_terms"][0]["term"] == "Bags"
