from __future__ import annotations

from datetime import datetime, timezone

from src.analysis.listening import build_listening_plan, deduplicate_posts


def test_listening_plan_has_separate_windows_and_expert_layer() -> None:
    plan = build_listening_plan(
        now=datetime(2026, 7, 22, tzinfo=timezone.utc),
        expert_accounts=["VogueRunway", "BoF"],
        expert_chunk_size=8,
    )
    open_rows = [row for row in plan if not row["is_expert"]]
    expert_rows = [row for row in plan if row["is_expert"]]
    assert len(open_rows) == 10
    assert len(expert_rows) == 4
    assert {
        (row["expert_tier"], row["expert_weight"])
        for row in expert_rows
    } == {
        ("commercial-priority", 3.0),
        ("expert-support", 1.0),
    }
    priority_query = next(
        row
        for row in expert_rows
        if row["expert_tier"] == "commercial-priority"
        and row["window"] == "current"
    )["input"]["query"]
    assert "from:WhoWhatWear" in priority_query
    assert "from:WhoWhatWearUK" in priority_query
    assert "from:Lyst" in priority_query
    assert {row["window"] for row in plan} == {"current", "previous"}
    current_query = next(row for row in open_rows if row["window"] == "current")["input"]["query"]
    previous_query = next(row for row in open_rows if row["window"] == "previous")["input"]["query"]
    assert "since:2026-07-15" in current_query
    assert "until:2026-07-23" in current_query
    assert "since:2026-07-08" in previous_query
    assert "until:2026-07-15" in previous_query


def test_deduplication_preserves_open_and_expert_provenance() -> None:
    base = {
        "post_hash": "same-post",
        "text": "Ballet flats are back",
        "created_at": "2026-07-21T10:00:00+00:00",
        "engagement": 12,
        "views": 500,
    }
    unique, stats = deduplicate_posts(
        [
            {
                **base,
                "listening_group": "silhouette",
                "evidence_channels": ["open"],
            },
            {
                **base,
                "listening_group": "expert-1",
                "evidence_channels": ["expert"],
                "is_expert": True,
                "expert_tier": "commercial-priority",
                "expert_weight": 3.0,
            },
        ]
    )
    assert stats == {"collected": 2, "unique": 1, "duplicates_removed": 1}
    assert unique[0]["evidence_channels"] == ["expert", "open"]
    assert unique[0]["listening_groups"] == ["expert-1", "silhouette"]
    assert unique[0]["expert_tiers"] == ["commercial-priority"]
    assert unique[0]["expert_weight"] == 3.0


def test_live_publisher_terms_add_targeted_current_and_previous_searches() -> None:
    plan = build_listening_plan(
        now=datetime(2026, 8, 6, tzinfo=timezone.utc),
        expert_accounts=[],
        priority_accounts=[],
        validation_terms=["Layered Tops", "Kitten-Heel Flip-Flops"],
    )
    targeted = [row for row in plan if row.get("is_dynamic_validation")]

    assert len(targeted) == 2
    assert {row["window"] for row in targeted} == {"current", "previous"}
    assert all('"Layered Tops"' in row["input"]["query"] for row in targeted)
    assert all(
        '"Kitten-Heel Flip-Flops"' in row["input"]["query"]
        for row in targeted
    )
