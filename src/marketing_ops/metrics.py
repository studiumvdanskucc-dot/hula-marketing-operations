from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Iterable, Mapping


def safe_divide(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    result = float(numerator) / float(denominator)
    return result if isfinite(result) else None


def percentage_change(current: float | int | None, comparison: float | int | None) -> float | None:
    ratio = safe_divide(
        None if current is None or comparison is None else float(current) - float(comparison),
        comparison,
    )
    return None if ratio is None else ratio * 100.0


def blended_roas(platform_paid_revenue: float, paid_spend: float) -> float | None:
    """Platform-attributed paid revenue divided by paid-media spend.

    Email revenue is intentionally excluded because it is not paid-media revenue.
    """
    return safe_divide(platform_paid_revenue, paid_spend)


def marketing_efficiency_ratio(shopify_net_sales: float, paid_spend: float) -> float | None:
    return safe_divide(shopify_net_sales, paid_spend)


def blended_cac(paid_spend: float, new_customers: int) -> float | None:
    return safe_divide(paid_spend, new_customers)


def average_order_value(net_sales: float, orders: int) -> float | None:
    return safe_divide(net_sales, orders)


def weighted_ctr(rows: Iterable[Mapping[str, Any]]) -> float | None:
    clicks = sum(float(row.get("clicks") or 0) for row in rows)
    impressions = sum(float(row.get("impressions") or 0) for row in rows)
    ratio = safe_divide(clicks, impressions)
    return None if ratio is None else ratio * 100.0


def weighted_position(rows: Iterable[Mapping[str, Any]]) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for row in rows:
        impressions = float(row.get("impressions") or 0)
        position = row.get("position")
        if position is None or impressions <= 0:
            continue
        numerator += float(position) * impressions
        denominator += impressions
    return safe_divide(numerator, denominator)


@dataclass(frozen=True)
class ScoreResult:
    score: float
    factors: dict[str, float]
    weighted_contributions: dict[str, float]
    missing: tuple[str, ...]


def transparent_score(
    values: Mapping[str, float | int | None],
    weights: Mapping[str, float],
) -> ScoreResult:
    """Calculate a 0–100 score while showing every factor contribution.

    Missing factors are not silently treated as zero. Available weights are
    renormalized, and missing factor names are returned to the caller.
    """
    available = {
        name: max(0.0, min(100.0, float(value)))
        for name, value in values.items()
        if value is not None and float(weights.get(name, 0)) > 0
    }
    missing = tuple(name for name in weights if name not in available)
    available_weight = sum(float(weights[name]) for name in available)
    if available_weight <= 0:
        return ScoreResult(0.0, available, {}, missing)
    contributions = {
        name: value * float(weights[name]) / available_weight
        for name, value in available.items()
    }
    return ScoreResult(
        score=round(sum(contributions.values()), 1),
        factors=available,
        weighted_contributions={
            name: round(contribution, 1)
            for name, contribution in contributions.items()
        },
        missing=missing,
    )


SEO_OPPORTUNITY_WEIGHTS = {
    "demand": 0.20,
    "position_opportunity": 0.15,
    "ctr_gap": 0.15,
    "conversion_value": 0.15,
    "inventory_relevance": 0.10,
    "trend_relevance": 0.10,
    "content_gap": 0.08,
    "business_priority": 0.07,
}


def seo_opportunity_score(factors: Mapping[str, float | int | None]) -> ScoreResult:
    return transparent_score(factors, SEO_OPPORTUNITY_WEIGHTS)


def rfm_score(
    recency_days: int,
    order_count: int,
    monetary_value: float,
    *,
    recency_thresholds: tuple[int, int, int, int] = (30, 60, 120, 240),
    frequency_thresholds: tuple[int, int, int, int] = (1, 2, 4, 7),
    monetary_thresholds: tuple[float, float, float, float] = (3000, 8000, 20000, 50000),
) -> dict[str, int | str]:
    """Return configurable RFM quintile-style scores.

    Lower recency is better; higher frequency and monetary values are better.
    """
    r = 5 - sum(recency_days > threshold for threshold in recency_thresholds)
    f = 1 + sum(order_count > threshold for threshold in frequency_thresholds)
    m = 1 + sum(monetary_value > threshold for threshold in monetary_thresholds)
    r, f, m = (max(1, min(5, score)) for score in (r, f, m))
    total = r + f + m
    if r >= 4 and f >= 4 and m >= 4:
        label = "VIP / Champions"
    elif r >= 4 and f <= 2:
        label = "Recent first-time"
    elif r <= 2 and (f >= 3 or m >= 3):
        label = "At risk"
    elif r == 1 and f <= 2:
        label = "Lapsed"
    else:
        label = "Active"
    return {"recency": r, "frequency": f, "monetary": m, "total": total, "segment": label}


def funnel_rates(steps: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(step) for step in steps]
    first = float(rows[0].get("users") or 0) if rows else 0.0
    previous: float | None = None
    output: list[dict[str, Any]] = []
    for row in rows:
        users = float(row.get("users") or 0)
        overall = safe_divide(users, first)
        step_rate = safe_divide(users, previous) if previous is not None else 1.0
        output.append(
            {
                **row,
                "overall_rate_pct": None if overall is None else round(overall * 100, 2),
                "step_rate_pct": None if step_rate is None else round(step_rate * 100, 2),
            }
        )
        previous = users
    return output


def reconciliation_row(
    metric: str,
    reference: float | None,
    platform: float | None,
    *,
    tolerance_pct: float,
    reason: str,
    source_formula: str,
) -> dict[str, Any]:
    absolute = None
    difference_pct = None
    if reference is not None and platform is not None:
        absolute = platform - reference
        difference_pct = percentage_change(platform, reference)
    within = (
        difference_pct is not None and abs(difference_pct) <= tolerance_pct
    )
    return {
        "Metric": metric,
        "Agency report": reference,
        "New platform": platform,
        "Absolute difference": absolute,
        "Difference %": difference_pct,
        "Likely reason": reason,
        "Source / formula": source_formula,
        "Status": "Within tolerance" if within else "Review required",
    }


def format_hkd(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "—"
    return f"HK${float(value):,.{decimals}f}"
