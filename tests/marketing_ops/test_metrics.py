from __future__ import annotations

import pytest

from src.marketing_ops.demo_data import demo_dataset
from src.marketing_ops.metrics import (
    blended_cac,
    blended_roas,
    percentage_change,
    rfm_score,
    seo_opportunity_score,
    weighted_ctr,
    weighted_position,
)


def test_report_parity_metrics_are_calculated_not_hardcoded_labels() -> None:
    values = demo_dataset()["executive"]
    assert blended_roas(values["platform_paid_revenue"], values["paid_spend"]) == pytest.approx(7.6944, rel=1e-3)
    assert blended_cac(values["paid_spend"], values["new_customers"]) == pytest.approx(182.03, rel=1e-3)
    assert values["blended_roas"] == pytest.approx((148_913.65 + 84_986.32) / 30_398.60)
    assert values["spend_per_all_new_customer"] == pytest.approx(182.03, rel=1e-3)
    assert values["paid_cac"] is None


def test_weighted_search_metrics_use_clicks_and_impressions() -> None:
    rows = [
        {"clicks": 10, "impressions": 100, "position": 2},
        {"clicks": 1, "impressions": 900, "position": 10},
    ]
    assert weighted_ctr(rows) == pytest.approx(1.1)
    assert weighted_position(rows) == pytest.approx(9.2)


def test_transparent_seo_score_names_missing_factors() -> None:
    result = seo_opportunity_score({"demand": 80, "ctr_gap": 100})
    assert 0 <= result.score <= 100
    assert set(result.weighted_contributions) == {"demand", "ctr_gap"}
    assert "conversion_value" in result.missing
    assert sum(result.weighted_contributions.values()) == pytest.approx(result.score, abs=0.2)


def test_rfm_thresholds_are_configurable_and_labelled() -> None:
    vip = rfm_score(12, 10, 100_000)
    lapsed = rfm_score(500, 1, 2_000)
    assert vip["segment"] == "VIP / Champions"
    assert lapsed["segment"] == "Lapsed"


def test_percentage_change_handles_zero_and_negative() -> None:
    assert percentage_change(120, 100) == pytest.approx(20)
    assert percentage_change(80, 100) == pytest.approx(-20)
    assert percentage_change(10, 0) is None


def test_reconciliation_keeps_known_agency_gap_visible() -> None:
    rows = demo_dataset()["reconciliation"]
    store = next(row for row in rows if row["Metric"] == "Store/location revenue sum")
    orders = next(row for row in rows if row["Metric"] == "Orders")
    assert store["Absolute difference"] == pytest.approx(30_146.56)
    assert orders["Absolute difference"] == -5
    assert store["Status"] == "Review required"


def test_report_faithful_session_rows_are_not_combined_with_shopify_orders() -> None:
    dataset = demo_dataset()
    assert dataset["funnel"] == []
    assert [row["count"] for row in dataset["session_behaviour"]] == [57_585, 56_127, 35_081, 851]
    assert dataset["online_summary"]["orders"] == 84
    assert "checkout" not in " ".join(row["event"].lower() for row in dataset["session_behaviour"])


def test_channel_chart_gap_and_attribution_windows_stay_explicit() -> None:
    dataset = demo_dataset()
    assert sum(row["reported_revenue"] for row in dataset["channel_revenue"]) == pytest.approx(1_337_083.87)
    assert dataset["executive"]["channel_chart_coverage_pct"] == pytest.approx(53.69, abs=0.01)
    windows = {row["channel"]: row["attribution_window"] for row in dataset["channel_revenue"]}
    assert windows["Email"] == "90 days"
    assert windows["Meta"] == "7 days"
