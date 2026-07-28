from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.analysis.freshness import validate_fresh_posts, validate_series
from src.analysis.trends import (
    merge_trend_signals,
    sanitize_snapshot_trends,
    score_google_series,
)


def test_missing_and_old_dates_are_rejected_without_becoming_current() -> None:
    now = datetime(2026, 7, 28, 12, tzinfo=timezone.utc)
    accepted, stats = validate_fresh_posts(
        [
            {
                "post_hash": "missing",
                "text": "Ballet flats",
                "created_at": "",
                "listening_window": "current",
            },
            {
                "post_hash": "old",
                "text": "Ballet flats",
                "created_at": (now - timedelta(days=30)).isoformat(),
                "listening_window": "current",
            },
            {
                "post_hash": "fresh",
                "text": "Ballet flats",
                "created_at": (now - timedelta(days=2)).isoformat(),
                "listening_window": "previous",
            },
        ],
        now=now,
    )

    assert [row["post_hash"] for row in accepted] == ["fresh"]
    assert accepted[0]["listening_window"] == "current"
    assert stats["rejected_by_reason"] == {
        "missing_or_invalid_date": 1,
        "older_than_14_days": 1,
    }


def test_invariant_google_series_is_not_scored_or_charted() -> None:
    points = [
        {"date": f"2026-07-{day:02d}", "value": 50}
        for day in range(1, 8)
    ]
    cleaned, quality = validate_series(points)
    assert len(cleaned) == 7
    assert quality["flat"] is True
    assert quality["score_ready"] is False
    assert quality["chart_ready"] is False
    assert score_google_series({"ballet flats": points}) == []


def test_social_only_row_stays_out_of_decision_list() -> None:
    merged = merge_trend_signals(
        [],
        [
            {
                "id": "sandals",
                "name": "Sandals",
                "open_x_score": 65,
                "mentions": 14,
                "aliases": ["sandals"],
            }
        ],
    )
    assert merged[0]["name"] == "Sandals"
    assert merged[0]["google_score"] is None
    assert merged[0]["decision_ready"] is False
    assert "Google Trends" in merged[0]["missing_components"]


def test_old_flat_snapshot_is_demoted_before_the_dashboard_renders() -> None:
    snapshot = {
        "meta": {"raw_counts": {}},
        "trends": [
            {
                "id": "ballet-flats",
                "name": "Ballet Flats",
                "decision_ready": True,
                "google_score": 80,
                "x_score": 70,
                "series": [
                    {"date": f"2026-07-{day:02d}", "value": 50}
                    for day in range(1, 8)
                ],
            }
        ],
        "recommendations": [],
    }
    cleaned = sanitize_snapshot_trends(snapshot)
    trend = cleaned["trends"][0]
    assert trend["google_score"] is None
    assert trend["decision_ready"] is False
    assert trend["chart_ready"] is False
