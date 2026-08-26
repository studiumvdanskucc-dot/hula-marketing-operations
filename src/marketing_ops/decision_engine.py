from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .metrics import safe_divide


@dataclass(frozen=True)
class DecisionPolicy:
    """Business inputs required before paid-media recommendations can execute.

    A value of ``None`` is deliberate: the app must surface an unresolved
    business decision instead of silently substituting an industry benchmark.
    """

    retained_margin_rate: float | None = 0.31
    retained_margin_confirmed: bool = False
    returns_refunds_confirmed: bool = True
    forecast_return_rate: float | None = 0.10
    forecast_return_rate_confirmed: bool = False
    variable_cost_rate_of_retained: float | None = 0.10
    variable_cost_confirmed: bool = True
    platform_gmv_roas_floor: float | None = 4.0
    contribution_roas_floor: float | None = 1.0
    contribution_roas_scale_target: float | None = None
    minimum_purchases: int | None = None
    max_paid_cac_hkd: float | None = None
    payback_window_days: int | None = None
    google_monthly_cap_hkd: float | None = None
    meta_monthly_cap_hkd: float | None = None
    max_internal_reallocation_pct: float | None = None
    normalized_click_window_days: int = 7
    major_change_approvers: tuple[str, ...] = ("Sarah", "Elena", "Tiffany")
    all_major_approvers_required: bool = True


@dataclass(frozen=True)
class RecommendationResult:
    decision: str
    confidence: str
    reason: str
    blockers: tuple[str, ...]
    platform_roas: float | None
    retained_roas_proxy: float | None
    contribution_roas: float | None
    break_even_gmv_roas: float | None
    large_order_share_pct: float | None
    roas_excluding_largest: float | None
    one_more_order_contribution_roas: float | None


def retained_revenue_proxy(gmv: float | None, retained_margin_rate: float | None) -> float | None:
    if gmv is None or retained_margin_rate is None:
        return None
    return float(gmv) * float(retained_margin_rate)


def contribution_rate(
    retained_margin_rate: float | None,
    variable_cost_rate_of_retained: float | None,
    refund_rate: float | None = 0.0,
) -> float | None:
    if (
        retained_margin_rate is None
        or variable_cost_rate_of_retained is None
        or refund_rate is None
    ):
        return None
    retained = float(retained_margin_rate)
    variable = float(variable_cost_rate_of_retained)
    refunds = float(refund_rate)
    if not (0 < retained <= 1 and 0 <= variable < 1 and 0 <= refunds < 1):
        return None
    # Payment fees and shipping are approximately 10% of HULA's retained
    # margin, not ten percentage points of GMV. A forecast return provision is
    # applied only when the input value has not already been reduced by actual
    # Shopify refunds.
    rate = retained * (1.0 - variable) * (1.0 - refunds)
    return rate if rate > 0 else None


def contribution_value(
    gmv: float | None,
    retained_margin_rate: float | None,
    variable_cost_rate_of_retained: float | None,
    refund_rate: float | None = 0.0,
) -> float | None:
    rate = contribution_rate(
        retained_margin_rate,
        variable_cost_rate_of_retained,
        refund_rate,
    )
    if gmv is None or rate is None:
        return None
    return float(gmv) * rate


def break_even_roas(contribution_margin_rate: float | None) -> float | None:
    return safe_divide(1.0, contribution_margin_rate)


def attributed_contribution_roas(
    attributed_gmv: float | None,
    spend: float | None,
    contribution_margin_rate: float | None,
) -> float | None:
    if attributed_gmv is None or contribution_margin_rate is None:
        return None
    return safe_divide(float(attributed_gmv) * contribution_margin_rate, spend)


def large_order_dependency(
    order_values: Iterable[float],
    *,
    spend: float | None,
) -> dict[str, float | None]:
    values = [max(0.0, float(value)) for value in order_values]
    total = sum(values)
    largest = max(values, default=0.0)
    share = safe_divide(largest, total)
    return {
        "largest_order_hkd": largest or None,
        "share_pct": None if share is None else share * 100,
        "roas_including": safe_divide(total, spend),
        "roas_excluding": safe_divide(total - largest, spend),
    }


def one_more_order_sensitivity(
    attributed_gmv: float | None,
    median_order_value: float | None,
    spend: float | None,
    contribution_margin_rate: float | None,
) -> float | None:
    if attributed_gmv is None or median_order_value is None:
        return None
    return attributed_contribution_roas(
        float(attributed_gmv) + float(median_order_value),
        spend,
        contribution_margin_rate,
    )


def claim_excess_indicator(
    claimed_orders: Iterable[int | float],
    actual_shopify_orders: int | float | None,
    *,
    comparable_scope: bool,
) -> float | None:
    """Return claimed minus actual orders only for genuinely comparable scopes.

    A positive result is an overlap *indicator*, not a count of duplicated
    customers. Proving duplication requires order-level identifiers.
    """

    if not comparable_scope or actual_shopify_orders is None:
        return None
    return sum(float(value) for value in claimed_orders) - float(actual_shopify_orders)


def confidence_label(
    purchases: int,
    largest_order_share_pct: float | None,
    *,
    profitability_confirmed: bool,
) -> str:
    if purchases < 5:
        return "Low"
    if not profitability_confirmed:
        return "Low / Medium" if purchases >= 15 else "Low"
    if purchases < 20 or (largest_order_share_pct or 0) >= 35:
        return "Medium"
    return "High"


def evaluate_paid_media(
    *,
    attributed_gmv: float,
    spend: float,
    purchases: int,
    order_values: Iterable[float],
    median_order_value: float | None,
    inventory_available: bool | None,
    channel: str,
    policy: DecisionPolicy,
) -> RecommendationResult:
    platform_roas = safe_divide(attributed_gmv, spend)
    retained_after_returns_rate = (
        None
        if policy.retained_margin_rate is None or policy.forecast_return_rate is None
        else float(policy.retained_margin_rate)
        * (1.0 - float(policy.forecast_return_rate))
    )
    retained_proxy = attributed_contribution_roas(
        attributed_gmv, spend, retained_after_returns_rate
    )
    margin = contribution_rate(
        policy.retained_margin_rate,
        policy.variable_cost_rate_of_retained,
        policy.forecast_return_rate,
    )
    contribution_roas = attributed_contribution_roas(attributed_gmv, spend, margin)
    dependency = large_order_dependency(order_values, spend=spend)
    profitability_confirmed = (
        policy.retained_margin_confirmed
        and policy.returns_refunds_confirmed
        and policy.forecast_return_rate_confirmed
        and policy.variable_cost_confirmed
        and margin is not None
        and policy.contribution_roas_floor is not None
    )
    confidence = confidence_label(
        purchases,
        dependency["share_pct"],
        profitability_confirmed=profitability_confirmed,
    )

    blockers: list[str] = []
    if not policy.retained_margin_confirmed:
        blockers.append("Sarah must confirm the retained-margin definition")
    if not policy.returns_refunds_confirmed:
        blockers.append("Finance must confirm that refunds reduce total revenue")
    if policy.forecast_return_rate is None:
        blockers.append("HULA must set a paid-media return provision")
    elif not policy.forecast_return_rate_confirmed:
        blockers.append("Confirm whether the 10% return provision is approved or illustrative")
    if policy.variable_cost_rate_of_retained is None:
        blockers.append("HULA must set the payment-and-shipping cost rate")
    elif not policy.variable_cost_confirmed:
        blockers.append("Finance must confirm the payment-and-shipping cost proxy")
    if policy.platform_gmv_roas_floor is None:
        blockers.append("HULA must record the gross/platform ROAS floor")
    if policy.contribution_roas_floor is None:
        blockers.append("HULA must approve a contribution ROAS floor")
    if policy.contribution_roas_scale_target is None:
        blockers.append("HULA must approve a contribution ROAS scaling target")
    if policy.minimum_purchases is None:
        blockers.append("HULA must approve the minimum purchase volume")
    cap = policy.google_monthly_cap_hkd if channel.lower().startswith("google") else policy.meta_monthly_cap_hkd
    if cap is None:
        blockers.append(f"{channel} monthly hard cap is not recorded")
    if inventory_available is None:
        blockers.append("Live inventory check is not connected")
    elif not inventory_available:
        return RecommendationResult(
            decision="PAUSE",
            confidence=confidence,
            reason="The promoted inventory is unavailable. Stop spend and verify the replacement destination.",
            blockers=tuple(blockers),
            platform_roas=platform_roas,
            retained_roas_proxy=retained_proxy,
            contribution_roas=contribution_roas,
            break_even_gmv_roas=break_even_roas(margin),
            large_order_share_pct=dependency["share_pct"],
            roas_excluding_largest=dependency["roas_excluding"],
            one_more_order_contribution_roas=one_more_order_sensitivity(
                attributed_gmv, median_order_value, spend, margin
            ),
        )

    if blockers:
        decision = "REVIEW"
        reason = (
            "Platform performance is visible, but HULA contribution is not yet decision-ready. "
            "Resolve the named policy and data gaps before changing spend."
        )
    elif purchases < int(policy.minimum_purchases or 0):
        decision = "HOLD"
        reason = "The result has not reached HULA's approved purchase-volume threshold."
    elif contribution_roas is not None and contribution_roas < float(policy.contribution_roas_floor or 0) * 0.5:
        decision = "PAUSE"
        reason = "Contribution ROAS is materially below HULA's approved floor at sufficient volume. Prepare a pause proposal."
    elif contribution_roas is not None and contribution_roas < float(policy.contribution_roas_floor or 0):
        decision = "REDUCE"
        reason = "Contribution ROAS is below HULA's approved floor at sufficient volume."
    elif (
        contribution_roas is not None
        and policy.contribution_roas_scale_target is not None
        and contribution_roas >= float(policy.contribution_roas_scale_target)
    ):
        if (dependency["share_pct"] or 0) >= 35:
            decision = "HOLD"
            reason = "Contribution clears the floor, but the result still depends too heavily on the largest order."
        else:
            decision = "SCALE"
            reason = "Contribution clears the approved floor with sufficient volume and manageable order dependency. Prepare a scale proposal for all named approvers; do not execute automatically."
    else:
        decision = "HOLD"
        reason = "Contribution performance is near the approved floor; wait for the next review trigger."

    return RecommendationResult(
        decision=decision,
        confidence=confidence,
        reason=reason,
        blockers=tuple(blockers),
        platform_roas=platform_roas,
        retained_roas_proxy=retained_proxy,
        contribution_roas=contribution_roas,
        break_even_gmv_roas=break_even_roas(margin),
        large_order_share_pct=dependency["share_pct"],
        roas_excluding_largest=dependency["roas_excluding"],
        one_more_order_contribution_roas=one_more_order_sensitivity(
            attributed_gmv, median_order_value, spend, margin
        ),
    )


def policy_from_mapping(values: Mapping[str, object]) -> DecisionPolicy:
    """Small adapter used by fixtures/imports without coupling to app config."""

    return DecisionPolicy(
        retained_margin_rate=values.get("retained_margin_rate", 0.31),  # type: ignore[arg-type]
        retained_margin_confirmed=bool(values.get("retained_margin_confirmed", False)),
        returns_refunds_confirmed=bool(values.get("returns_refunds_confirmed", True)),
        forecast_return_rate=values.get("forecast_return_rate", 0.10),  # type: ignore[arg-type]
        forecast_return_rate_confirmed=bool(values.get("forecast_return_rate_confirmed", False)),
        variable_cost_rate_of_retained=values.get("variable_cost_rate_of_retained", 0.10),  # type: ignore[arg-type]
        variable_cost_confirmed=bool(values.get("variable_cost_confirmed", True)),
        platform_gmv_roas_floor=values.get("platform_gmv_roas_floor", 4.0),  # type: ignore[arg-type]
        contribution_roas_floor=values.get("contribution_roas_floor", 1.0),  # type: ignore[arg-type]
        contribution_roas_scale_target=values.get("contribution_roas_scale_target"),  # type: ignore[arg-type]
        minimum_purchases=values.get("minimum_purchases"),  # type: ignore[arg-type]
        max_paid_cac_hkd=values.get("max_paid_cac_hkd"),  # type: ignore[arg-type]
        payback_window_days=values.get("payback_window_days"),  # type: ignore[arg-type]
        google_monthly_cap_hkd=values.get("google_monthly_cap_hkd"),  # type: ignore[arg-type]
        meta_monthly_cap_hkd=values.get("meta_monthly_cap_hkd"),  # type: ignore[arg-type]
        max_internal_reallocation_pct=values.get("max_internal_reallocation_pct"),  # type: ignore[arg-type]
        normalized_click_window_days=int(values.get("normalized_click_window_days", 7)),
        major_change_approvers=tuple(values.get("major_change_approvers") or ("Sarah", "Elena", "Tiffany")),  # type: ignore[arg-type]
        all_major_approvers_required=bool(values.get("all_major_approvers_required", True)),
    )
