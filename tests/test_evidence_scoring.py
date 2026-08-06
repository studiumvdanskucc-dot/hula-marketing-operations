from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.analysis.evidence_scoring import (
    COMPONENT_WEIGHTS,
    apply_hula_opportunity_scores,
    recency_factor,
    score_trend_v2,
)
from src.analysis.trends import sanitize_snapshot_trends


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def evidence(
    source: str,
    domain: str,
    kind: str = "editorial trend heading",
    *,
    days_old: int = 1,
    title: str | None = None,
) -> dict:
    return {
        "publisher": source,
        "url": f"https://{domain}/fashion/{source.casefold().replace(' ', '-')}",
        "article_title": title or f"Original {source} report on layered tops",
        "published_at": (NOW - timedelta(days=days_old)).date().isoformat(),
        "evidence_kind": kind,
        "explicit_label": "Layered tops",
    }


def daily_series(days: int = 90) -> list[dict]:
    start = NOW.date() - timedelta(days=days - 1)
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "raw_value": min(100, 20 + index * 0.65),
        }
        for index in range(days)
    ]


def test_recency_factors_match_methodology() -> None:
    assert recency_factor(NOW, now=NOW) == 1.0
    assert recency_factor(NOW - timedelta(days=3), now=NOW) == 0.85
    assert recency_factor(NOW - timedelta(days=7), now=NOW) == 0.65
    assert recency_factor(NOW - timedelta(days=14), now=NOW) == 0.35
    assert recency_factor(NOW - timedelta(days=15), now=NOW) == 0.10


def test_missing_google_is_null_and_weights_are_redistributed() -> None:
    trend = score_trend_v2(
        {
            "id": "layered-tops",
            "name": "Layered tops",
            "commercial_evidence": [
                evidence("Data But Make It Fashion", "data.example"),
                evidence("Who What Wear", "editorial.example", days_old=2),
                evidence("Tagwalk", "runway.example", "runway taxonomy", days_old=4),
                evidence("Lyst Index", "retail.example", "ranked product", days_old=5),
            ],
        },
        now=NOW,
    )
    assert trend["score_breakdown"]["google_trends"] is None
    assert trend["google_trends_metrics"]["current_week_mean"] is None
    assert "Google Trends" in trend["missing_components"]
    assert trend["data_completeness_score"] == pytest.approx(65.0)
    assert sum(trend["component_weights"].values()) == pytest.approx(1.0, abs=0.001)


def test_single_independent_source_caps_confidence_at_55() -> None:
    trend = score_trend_v2(
        {
            "id": "layered-tops",
            "name": "Layered tops",
            "commercial_evidence": [
                evidence("Who What Wear", "whowhatwear.example", days_old=0),
                evidence(
                    "Who What Wear",
                    "whowhatwear.example",
                    days_old=1,
                    title="A second original layered tops article",
                ),
            ],
            "series": daily_series(),
        },
        now=NOW,
    )
    assert trend["independent_domain_count"] == 2  # publisher + Google Trends
    # Isolate one-domain evidence by removing search measurement.
    without_search = score_trend_v2(
        {
            "id": "layered-tops",
            "name": "Layered tops",
            "commercial_evidence": [
                evidence("Who What Wear", "whowhatwear.example", days_old=0),
                evidence(
                    "Who What Wear",
                    "whowhatwear.example",
                    days_old=1,
                    title="A second original layered tops article",
                ),
            ],
        },
        now=NOW,
    )
    assert without_search["independent_domain_count"] == 1
    assert without_search["confidence_score"] <= 55
    assert any("one independent source" in warning.lower() for warning in without_search["warnings"])


def test_syndicated_title_is_counted_once() -> None:
    title = "The exact same substantial syndicated layered tops trend report"
    trend = score_trend_v2(
        {
            "id": "layered-tops",
            "name": "Layered tops",
            "commercial_evidence": [
                evidence("ELLE", "elle.example", title=title),
                evidence("InStyle", "instyle.example", title=title),
                evidence("Who What Wear", "www.example", title="Independent layered tops analysis"),
            ],
        },
        now=NOW,
    )
    assert trend["evidence_count"] == 2
    assert any("duplicate or likely syndicated" in warning for warning in trend["warnings"])


def test_strong_current_cross_source_signal_can_be_ready_without_google() -> None:
    trend = score_trend_v2(
        {
            "id": "layered-tops",
            "name": "Layered tops",
            "commercial_evidence": [
                evidence("Data But Make It Fashion", "data.example", days_old=0),
                evidence("Who What Wear", "www.example", days_old=1),
                evidence("Vogue", "vogue.example", days_old=1),
                evidence("ELLE", "elle.example", days_old=2),
                evidence("Tagwalk", "tagwalk.example", "runway taxonomy", days_old=2),
                evidence("Runway report", "runway.example", "runway recurrence", days_old=3),
                evidence("Lyst Index", "lyst.example", "ranked product", days_old=3),
                evidence("Retail report", "retail.example", "ranked product", days_old=4),
            ],
            "x_score": 70,
            "mentions": 85,
            "unique_authors": 30,
            "author_growth": 38,
            "engagement_per_1000_views": 44,
            "evidence_quality": 92,
        },
        now=NOW,
    )
    assert trend["score_breakdown"]["google_trends"] is None
    assert trend["data_completeness_score"] == pytest.approx(80.0)
    assert trend["decision_ready"] is True
    assert trend["confidence_score"] >= 55

    snapshot = {
        "methodology_version": "2.0",
        "meta": {"methodology_version": "2.0"},
        "trends": [trend],
        "recommendations": [],
    }
    sanitised = sanitize_snapshot_trends(snapshot)
    assert sanitised["trends"][0]["decision_ready"] is True


def test_google_metrics_use_two_windows_and_baseline() -> None:
    trend = score_trend_v2(
        {
            "id": "layered-tops",
            "name": "Layered tops",
            "series": daily_series(),
            "commercial_evidence": [
                evidence("Who What Wear", "www.example"),
                evidence("ELLE", "elle.example"),
                evidence("InStyle", "instyle.example"),
            ],
        },
        now=NOW,
    )
    metrics = trend["google_trends_metrics"]
    assert metrics["current_week_mean"] > metrics["previous_week_mean"]
    assert metrics["seven_day_slope"] > 0
    assert metrics["ninety_day_baseline_mean"] is not None
    assert trend["score_breakdown"]["google_trends"] is not None


def test_hula_opportunity_formula_is_separate_from_confidence() -> None:
    trend = {
        "id": "layered-tops",
        "name": "Layered tops",
        "trend_type": "product",
        "category": "Bags",
        "confidence_score": 80.0,
        "score": 80.0,
    }
    recommendation = {
        "trend_id": "layered-tops",
        "product_id": "product-1",
        "match_score": 60.0,
    }
    products = [{"id": "product-1", "vendor": "Demo", "title": "Layered bag"}]
    trends, _ = apply_hula_opportunity_scores([trend], [recommendation], products)
    expected = 0.65 * 80 + 0.25 * 60 + 0.10 * 92
    assert trends[0]["hula_opportunity_score"] == pytest.approx(expected, abs=0.1)
    assert trends[0]["confidence_score"] == 80.0
    assert set(COMPONENT_WEIGHTS) == {
        "editorial",
        "cross_source",
        "google_trends",
        "social",
        "runway_celebrity",
        "commercial",
    }
