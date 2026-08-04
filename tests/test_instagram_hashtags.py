from __future__ import annotations

from src.connectors.apify_instagram_hashtags import (
    InstagramHashtagAnalyticsConnector,
    normalize_hashtag_metric,
    parse_compact_number,
    score_hashtag_metrics,
)


def test_hashtag_actor_input_explicitly_disables_post_collection() -> None:
    assert InstagramHashtagAnalyticsConnector.build_input(
        ["#BalletFlats", "balletflats", "Polka Dots"]
    ) == {
        "hashtags": ["balletflats", "polkadots"],
        "includeLatestPosts": False,
        "includeTopPosts": False,
    }


def test_compact_instagram_counts_are_parsed() -> None:
    assert parse_compact_number("75.83 k") == 75_830
    assert parse_compact_number("2.15 G") == 2_150_000_000
    assert parse_compact_number(4200) == 4200


def test_normalization_keeps_aggregate_metadata_only() -> None:
    metric = normalize_hashtag_metric(
        {
            "name": "balletflats",
            "postsCount": 120_000,
            "postsPerDay": "45",
            "topPosts": [{"caption": "must not survive"}],
            "related": [{"hash": "#maryjanes", "info": "80 k"}],
        },
        trend_by_hashtag={
            "balletflats": {"id": "ballet-flats", "name": "Ballet Flats"}
        },
    )
    assert metric is not None
    assert metric["posts_count"] == 120_000
    assert metric["posts_per_day"] == 45
    assert "topPosts" not in metric
    assert "caption" not in str(metric)


def test_normalization_accepts_actor_search_term_output() -> None:
    metric = normalize_hashtag_metric(
        {
            "searchTerm": "#BalletFlats",
            "postsCount": "75.83 k",
            "postsPerDay": 31,
        },
        trend_by_hashtag={
            "balletflats": {"id": "ballet-flats", "name": "Ballet Flats"}
        },
    )
    assert metric is not None
    assert metric["hashtag"] == "balletflats"
    assert metric["posts_count"] == 75_830
    assert metric["posts_per_day"] == 31


def test_hashtag_scores_are_directional_comparisons() -> None:
    rows = score_hashtag_metrics(
        [
            {"id": "one", "name": "One", "posts_count": 1000, "posts_per_day": 2},
            {"id": "two", "name": "Two", "posts_count": 5000, "posts_per_day": 20},
        ]
    )
    assert rows[0]["id"] == "two"
    assert rows[0]["directional_only"] is True
