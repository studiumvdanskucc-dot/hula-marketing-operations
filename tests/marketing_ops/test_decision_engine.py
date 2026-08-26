from __future__ import annotations

import pytest

from src.marketing_ops.decision_engine import (
    DecisionPolicy,
    break_even_roas,
    claim_excess_indicator,
    contribution_rate,
    contribution_value,
    evaluate_paid_media,
    large_order_dependency,
    retained_revenue_proxy,
)


def test_profitability_bridge_does_not_invent_missing_costs() -> None:
    assert retained_revenue_proxy(10_000, 0.31) == pytest.approx(3_100)
    assert contribution_rate(0.31, None) is None
    assert contribution_value(10_000, 0.31, None) is None


def test_confirmed_scenario_calculates_contribution_and_break_even() -> None:
    rate = contribution_rate(0.31, 0.10, 0.10)
    assert rate == pytest.approx(0.2511)
    assert contribution_value(10_000, 0.31, 0.10, 0.10) == pytest.approx(2_511)
    assert break_even_roas(rate) == pytest.approx(3.9824771)


def test_actual_shopify_refunds_are_not_deducted_twice() -> None:
    # The input is already net of an actual HK$2,000 refund, so the forecast
    # return provision is deliberately zero for the accounting calculation.
    assert contribution_value(8_000, 0.31, 0.10) == pytest.approx(2_232)


def test_large_order_dependency_recalculates_roas_without_largest_order() -> None:
    result = large_order_dependency([20_000, 8_000, 4_000], spend=4_000)
    assert result["share_pct"] == pytest.approx(62.5)
    assert result["roas_including"] == pytest.approx(8.0)
    assert result["roas_excluding"] == pytest.approx(3.0)


def test_claim_excess_requires_same_scope_and_is_only_an_indicator() -> None:
    assert claim_excess_indicator([25, 17], 34, comparable_scope=False) is None
    assert claim_excess_indicator([25, 17], 34, comparable_scope=True) == 8


def test_unresolved_hula_policy_forces_review() -> None:
    result = evaluate_paid_media(
        attributed_gmv=100_000,
        spend=10_000,
        purchases=25,
        order_values=[40_000, 30_000, 20_000, 10_000],
        median_order_value=5_000,
        inventory_available=None,
        channel="Google Ads",
        policy=DecisionPolicy(),
    )
    assert result.decision == "REVIEW"
    assert result.platform_roas == pytest.approx(10)
    assert result.retained_roas_proxy == pytest.approx(2.79)
    assert result.contribution_roas == pytest.approx(2.511)
    assert "Confirm whether the 10% return provision is approved or illustrative" in result.blockers
    assert "HULA must approve a contribution ROAS scaling target" in result.blockers
    assert "Google Ads monthly hard cap is not recorded" in result.blockers


def test_complete_policy_can_recommend_scale_or_reduce_without_auto_execution() -> None:
    policy = DecisionPolicy(
        retained_margin_rate=0.31,
        retained_margin_confirmed=True,
        returns_refunds_confirmed=True,
        forecast_return_rate=0.10,
        forecast_return_rate_confirmed=True,
        variable_cost_rate_of_retained=0.10,
        variable_cost_confirmed=True,
        platform_gmv_roas_floor=4.0,
        contribution_roas_floor=1.0,
        contribution_roas_scale_target=1.5,
        minimum_purchases=10,
        google_monthly_cap_hkd=50_000,
    )
    strong = evaluate_paid_media(
        attributed_gmv=100_000,
        spend=10_000,
        purchases=25,
        order_values=[4_000] * 25,
        median_order_value=4_000,
        inventory_available=True,
        channel="Google Ads",
        policy=policy,
    )
    weak = evaluate_paid_media(
        attributed_gmv=30_000,
        spend=10_000,
        purchases=12,
        order_values=[2_500] * 12,
        median_order_value=2_500,
        inventory_available=True,
        channel="Google Ads",
        policy=policy,
    )
    assert strong.decision == "SCALE"
    assert strong.contribution_roas == pytest.approx(2.511)
    assert weak.decision == "REDUCE"
    assert weak.contribution_roas == pytest.approx(0.7533)


def test_unavailable_inventory_pauses_even_when_finance_inputs_are_open() -> None:
    result = evaluate_paid_media(
        attributed_gmv=20_000,
        spend=2_000,
        purchases=4,
        order_values=[10_000, 5_000, 3_000, 2_000],
        median_order_value=4_000,
        inventory_available=False,
        channel="Meta Ads",
        policy=DecisionPolicy(),
    )
    assert result.decision == "PAUSE"
    assert "unavailable" in result.reason.lower()
