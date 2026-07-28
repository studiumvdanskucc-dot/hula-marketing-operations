from __future__ import annotations

from datetime import datetime, timezone

from src.connectors.apify_instagram import (
    ApifyInstagramConnector,
    normalize_instagram_post,
)
from src.connectors.apify_x import normalize_post


def test_instagram_input_enforces_governed_panel_window() -> None:
    actor_input = ApifyInstagramConnector.build_input(
        ["@DataButMakeItFashion", "tagwalk", "TAGWALK"],
        results_per_profile=15,
        cutoff=datetime(2026, 7, 14, tzinfo=timezone.utc),
    )
    assert actor_input == {
        "username": ["databutmakeitfashion", "tagwalk"],
        "resultsLimit": 15,
        "skipPinnedPosts": True,
        "onlyPostsNewerThan": "2026-07-14",
        "dataDetailLevel": "basicData",
    }


def test_instagram_post_is_normalized_without_raw_identity() -> None:
    post = normalize_instagram_post(
        {
            "id": "post-1",
            "caption": "Mini dresses and fisherman sandals are rising.",
            "timestamp": "2026-07-27T10:00:00Z",
            "ownerUsername": "DataButMakeItFashion",
            "likesCount": 100,
            "commentsCount": 12,
            "displayUrl": "https://example.com/public-image.jpg",
            "url": "https://www.instagram.com/p/example/",
        },
        account_weights={"databutmakeitfashion": 3},
    )
    assert post is not None
    assert post["platform"] == "instagram"
    assert post["expert_weight"] == 3
    assert post["evidence_channels"] == ["expert", "visual"]
    assert post["engagement"] == 112
    assert post["author_hash"]
    assert "ownerUsername" not in post


def test_same_publisher_is_deduplicated_across_instagram_and_x_handles() -> None:
    instagram = normalize_instagram_post(
        {
            "id": "ig-1",
            "caption": "Ballet flats are rising.",
            "timestamp": "2026-07-27T10:00:00Z",
            "ownerUsername": "whowhatwear.uk",
        }
    )
    x_post = normalize_post(
        {
            "id": "x-1",
            "text": "Ballet flats are rising.",
            "createdAt": "2026-07-27T10:00:00Z",
            "username": "WhoWhatWearUK",
        }
    )
    assert instagram is not None and x_post is not None
    assert instagram["author_hash"] == x_post["author_hash"]
