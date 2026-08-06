from __future__ import annotations

from datetime import datetime, timezone

from src.analysis.editorial_consensus import (
    apply_editorial_decision_rules,
    build_editorial_evidence,
    build_editorial_validation_plan,
    editorial_plan_fingerprint,
    score_editorial_consensus,
)


NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


def _article(article_id: str, publisher: str, group: str, url: str) -> dict:
    return {
        "article_id": article_id,
        "publisher": publisher,
        "publisher_id": group,
        "publisher_group": group,
        "publisher_weight": 1.0,
        "title": f"{publisher} names the drop-waist trend",
        "url": url,
        "published_at": "2026-08-04T00:00:00+00:00",
        "collected_at": NOW.isoformat(),
        "acquisition": "publisher page",
        "headings": ["Drop-Waist Dresses"],
        "paragraphs": ["Drop-waist dresses are returning for fall."],
    }


def _model_result(article_id: str, *, name: str = "Drop-Waist Dresses") -> dict:
    return {
        "article_id": article_id,
        "trends": [
            {
                "name": name,
                "google_query": "drop waist dress",
                "category": "clothing",
                "article_role": "central",
                "evidence_excerpt": "Drop-waist dresses are returning for fall.",
                "why_it_is_a_trend": "The article presents the silhouette as current.",
                "confidence": 0.94,
            }
        ],
    }


def test_model_extractions_become_traceable_article_evidence() -> None:
    articles = [
        _article("a1", "ELLE", "elle", "https://elle.example/drop-waist"),
        _article(
            "a2",
            "Marie Claire",
            "marie-claire",
            "https://marie.example/drop-waist",
        ),
    ]
    evidence = build_editorial_evidence(
        articles,
        [_model_result("a1"), _model_result("a2", name="Dropped Waist Dresses")],
        now=NOW,
    )

    assert len(evidence) == 2
    assert {row["publisher"] for row in evidence} == {"ELLE", "Marie Claire"}
    assert all(row["extraction_method"] == "OpenAI recent-article scan" for row in evidence)
    assert all(row["google_query"] == "drop waist dress" for row in evidence)


def test_independent_publisher_overlap_dominates_consensus_ranking() -> None:
    articles = [
        _article("a1", "ELLE", "elle", "https://elle.example/drop-waist"),
        _article("a2", "Vogue", "vogue", "https://vogue.example/drop-waist"),
        _article("a3", "Glamour", "glamour", "https://glamour.example/drop-waist"),
        _article("a4", "InStyle", "instyle", "https://instyle.example/coin-necklace"),
    ]
    results = [
        _model_result("a1"),
        _model_result("a2"),
        _model_result("a3"),
        _model_result("a4", name="Gold Coin Necklaces"),
    ]
    evidence = build_editorial_evidence(articles, results, now=NOW)
    rows = score_editorial_consensus(evidence, now=NOW)

    assert rows[0]["name"] == "Drop-Waist Dresses"
    assert rows[0]["publisher_count"] == 3
    assert rows[0]["overlap_label"] == "Strong editorial consensus"
    assert rows[0]["editorial_consensus_score"] > rows[1]["editorial_consensus_score"]


def test_same_publisher_group_counts_once() -> None:
    evidence = build_editorial_evidence(
        [
            _article("a1", "Who What Wear", "whowhatwear", "https://www.example/a"),
            _article("a2", "Who What Wear UK", "whowhatwear", "https://uk.example/b"),
        ],
        [_model_result("a1"), _model_result("a2")],
        now=NOW,
    )
    row = score_editorial_consensus(evidence, now=NOW)[0]

    assert row["article_count"] == 2
    assert row["publisher_count"] == 1


def test_validation_plan_contains_only_publisher_discoveries() -> None:
    rows = [
        {
            "id": "drop-waist-dresses",
            "name": "Drop-Waist Dresses",
            "google_query": "drop waist dress",
            "publisher_count": 2,
            "article_count": 2,
            "current_article_count": 2,
            "editorial_consensus_score": 82,
        }
    ]
    plan = build_editorial_validation_plan(rows)

    assert plan == [
        {
            "rank": 1,
            "id": "drop-waist-dresses",
            "name": "Drop-Waist Dresses",
            "query": "drop waist dress",
            "priority": 82.0,
            "publisher_count": 2,
            "article_count": 2,
            "current_article_count": 2,
            "origins": ["recent_editorial_publishers"],
            "seed_only": False,
        }
    ]
    assert editorial_plan_fingerprint(plan) != editorial_plan_fingerprint(
        [{**plan[0], "query": "dropped waist dress"}]
    )


def test_business_action_rewards_overlap_and_allows_search_breakout() -> None:
    common = {
        "current_article_count": 1,
        "article_count": 1,
        "confidence_score": 72,
        "editorial_consensus_score": 75,
        "score_breakdown": {"google_trends": 70},
        "google_trends_metrics": {
            "week_over_week_change_percent": 25,
            "year_over_year_change_percent": 200,
        },
    }
    rows = apply_editorial_decision_rules(
        [
            {**common, "name": "A", "publisher_count": 3},
            {**common, "name": "B", "publisher_count": 1},
            {
                **common,
                "name": "C",
                "publisher_count": 1,
                "google_trends_metrics": {
                    "week_over_week_change_percent": 5,
                    "year_over_year_change_percent": 20,
                },
            },
        ]
    )
    by_name = {row["name"]: row for row in rows}

    assert by_name["A"]["business_action"] == "Act now"
    assert by_name["B"]["business_action"] == "Test this week"
    assert by_name["C"]["business_action"] == "Watch"


def test_sponsored_article_is_not_used_as_trend_evidence() -> None:
    article = _article("a1", "Who What Wear", "whowhatwear", "https://example.com/ad")
    article["title"] = "Sponsor Content: Five Fall Trends"

    assert build_editorial_evidence([article], [_model_result("a1")], now=NOW) == []


def test_undated_article_is_visible_as_context_but_not_counted_as_recent_overlap() -> None:
    dated = _article("a1", "ELLE", "elle", "https://elle.example/drop-waist")
    undated = _article(
        "a2",
        "Marie Claire",
        "marie-claire",
        "https://marie.example/drop-waist",
    )
    undated["published_at"] = ""
    evidence = build_editorial_evidence(
        [dated, undated],
        [_model_result("a1"), _model_result("a2")],
        now=NOW,
    )

    row = score_editorial_consensus(evidence, now=NOW)[0]

    assert len(row["commercial_evidence"]) == 2
    assert row["publisher_count"] == 1
    assert row["article_count"] == 1
    assert row["current_article_count"] == 1
