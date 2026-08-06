from __future__ import annotations

import math
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

from src.analysis.freshness import parse_utc


METHODOLOGY_VERSION = "2.0"

# These are the only weights used for the public confidence score. Missing
# components are excluded and the remaining weights are normalised.
COMPONENT_WEIGHTS: dict[str, float] = {
    "editorial": 0.25,
    "cross_source": 0.20,
    "google_trends": 0.20,
    "social": 0.15,
    "runway_celebrity": 0.10,
    "commercial": 0.10,
}

COMPONENT_LABELS = {
    "editorial": "editorial / industry evidence",
    "cross_source": "cross-source confirmation",
    "google_trends": "Google Trends",
    "social": "social momentum",
    "runway_celebrity": "runway / celebrity activation",
    "commercial": "commercial availability",
}

# Public methodology weights from the user-approved v2 design.
SOURCE_AUTHORITY: dict[str, float] = {
    "data but make it fashion": 1.50,
    "lyst": 1.45,
    "lyst index": 1.45,
    "tagwalk": 1.40,
    "who what wear": 1.30,
    "who what wear uk": 1.30,
    "vogue": 1.20,
    "elle": 1.20,
    "harper's bazaar": 1.20,
    "harpers bazaar": 1.20,
    "bazaar": 1.20,
    "instyle": 1.10,
    "refinery29": 1.10,
    "business of fashion": 1.10,
    "wwd": 1.10,
    "fashionista": 1.10,
    "trendalytics": 1.10,
    "heuritech": 1.10,
    "teen vogue": 1.10,
}

INDUSTRY_SOURCES = {
    "data but make it fashion",
    "lyst",
    "lyst index",
    "trendalytics",
    "heuritech",
}

EDITORIAL_SOURCES = {
    "who what wear",
    "who what wear uk",
    "vogue",
    "elle",
    "harper's bazaar",
    "harpers bazaar",
    "bazaar",
    "instyle",
    "refinery29",
    "teen vogue",
    "business of fashion",
    "wwd",
    "fashionista",
}

MOMENTUM_LABELS = {
    "breakout",
    "accelerating",
    "steadily rising",
    "stable",
    "cooling",
    "declining",
    "insufficient data",
}


def normalise_exclusion_reason(value: Any) -> str:
    text = str(value or "").casefold()
    if "duplicate" in text or "syndicat" in text:
        return "duplicate"
    if any(token in text for token in ("non-fashion", "non fashion", "unrelated")):
        return "non-fashion"
    if any(token in text for token in ("outdated", "stale", "too old")):
        return "outdated"
    if any(token in text for token in ("broad", "generic", "category-only", "too vague")):
        return "too broad"
    if any(token in text for token in ("insufficient", "too few", "no evidence")):
        return "insufficient evidence"
    return "low relevance"


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _source_key(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def source_authority(source_name: Any) -> float:
    key = _source_key(source_name)
    if key in SOURCE_AUTHORITY:
        return SOURCE_AUTHORITY[key]
    if any(token in key for token in ("new york times", "the times", "guardian")):
        return 0.70
    return 0.30


def recency_factor(published_at: Any, *, now: datetime | None = None) -> float:
    published = parse_utc(published_at)
    if published is None:
        # Unknown is explicitly weaker than dated current evidence, but it is
        # not silently treated as fresh or as zero.
        return 0.20
    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    age_days = max(0, (reference - published).days)
    if age_days == 0:
        return 1.00
    if age_days <= 3:
        return 0.85
    if age_days <= 7:
        return 0.65
    if age_days <= 14:
        return 0.35
    return 0.10


def analysis_period(reference: datetime | None = None, *, geography: str = "global") -> dict[str, str]:
    current = (reference or datetime.now(tz=timezone.utc)).astimezone(timezone.utc).date()
    return {
        "current_week_start": (current - timedelta(days=6)).isoformat(),
        "current_week_end": current.isoformat(),
        "comparison_week_start": (current - timedelta(days=13)).isoformat(),
        "comparison_week_end": (current - timedelta(days=7)).isoformat(),
        "geography": str(geography or "global"),
    }


def _canonical_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url.startswith(("https://", "http://")):
        return ""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def _domain(value: Any) -> str:
    url = _canonical_url(value)
    if not url:
        return ""
    return urlparse(url).netloc.casefold().removeprefix("www.")


def _title_fingerprint(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _publisher_evidence_type(row: dict[str, Any]) -> str:
    source = _source_key(row.get("publisher") or row.get("source_name"))
    kind = _source_key(row.get("evidence_kind") or row.get("evidence_type"))
    title = _source_key(row.get("article_title") or row.get("title"))
    if source == "tagwalk" or "runway" in kind or "runway" in title:
        return "runway"
    if source in {"lyst", "lyst index"} and any(
        token in kind for token in ("product", "ranked", "hottest")
    ):
        return "retail"
    if source in INDUSTRY_SOURCES:
        return "industry_data"
    if source in EDITORIAL_SOURCES:
        return "editorial"
    return "editorial"


def _publisher_evidence(row: dict[str, Any]) -> dict[str, Any]:
    source_name = str(row.get("publisher") or row.get("source_name") or "Unknown source").strip()
    title = str(row.get("article_title") or row.get("title") or row.get("explicit_label") or "").strip()
    summary_parts = [
        str(row.get("explicit_label") or row.get("trend_name") or "").strip(),
        str(row.get("evidence_kind") or "").strip(),
    ]
    summary = " · ".join(part for part in summary_parts if part)
    relevance = _safe_float(
        row.get("model_relevance_score"),
        0.70 + min(0.28, source_authority(source_name) / 6.0),
    )
    if row.get("explicit") is False:
        relevance -= 0.20
    return {
        "source_name": source_name,
        "source_url": _canonical_url(row.get("url") or row.get("source_url")),
        "title": title,
        "published_at": str(row.get("published_at") or "")[:10] or None,
        "evidence_type": _publisher_evidence_type(row),
        "relevance_score": round(_clamp(relevance, 0.0, 1.0), 2),
        "supports_or_contradicts": str(row.get("supports_or_contradicts") or "supports"),
        "evidence_summary": summary or "The source explicitly named the trend.",
    }


def _series_value(point: dict[str, Any]) -> float | None:
    # Raw/display values are Google's original 0–100 index. The legacy `value`
    # field may be anchor-calibrated and can exceed 100, so it is last choice.
    for key in ("raw_value", "display_value", "value"):
        if point.get(key) is None:
            continue
        value = _safe_float(point.get(key), math.nan)
        if math.isfinite(value) and 0 <= value <= 100:
            return value
    return None


def _linear_slope(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    x_mean = (len(values) - 1) / 2
    y_mean = statistics.mean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    if denominator == 0:
        return 0.0
    return sum(
        (index - x_mean) * (value - y_mean)
        for index, value in enumerate(values)
    ) / denominator


def _dated_series(trend: dict[str, Any]) -> list[tuple[date, float]]:
    rows: list[tuple[date, float]] = []
    for point in trend.get("series") or []:
        if not isinstance(point, dict):
            continue
        value = _series_value(point)
        if value is None:
            continue
        raw_date = str(point.get("date") or "")[:10]
        try:
            parsed = date.fromisoformat(raw_date)
        except ValueError:
            continue
        rows.append((parsed, value))
    deduped = {day: value for day, value in rows}
    return sorted(deduped.items())


def google_component(trend: dict[str, Any]) -> tuple[float | None, dict[str, float | None], list[str]]:
    if trend.get("google_stale"):
        metrics = {
            "current_week_mean": None,
            "previous_week_mean": None,
            "week_over_week_change_percent": None,
            "seven_day_slope": None,
            "ninety_day_baseline_mean": None,
        }
        return None, metrics, [
            "Google Trends data is stale; it is displayed only as context and is excluded from scoring."
        ]
    rows = _dated_series(trend)
    warnings: list[str] = []
    metrics: dict[str, float | None] = {
        "current_week_mean": None,
        "previous_week_mean": None,
        "week_over_week_change_percent": None,
        "seven_day_slope": None,
        "ninety_day_baseline_mean": None,
    }
    if len(rows) < 14:
        warnings.append("Insufficient Google Trends history for two seven-day windows.")
        return None, metrics, warnings
    values = [value for _, value in rows]
    if len({round(value, 3) for value in values}) < 3 or max(values) <= 0:
        warnings.append("Insufficient Google Trends resolution; search demand is not scored as zero.")
        return None, metrics, warnings

    current_values = values[-7:]
    previous_values = values[-14:-7]
    current_mean = statistics.mean(current_values)
    previous_mean = statistics.mean(previous_values)
    week_change = 100 * (current_mean - previous_mean) / max(previous_mean, 1.0)
    slope = _linear_slope(current_values) or 0.0
    span_days = (rows[-1][0] - rows[0][0]).days
    baseline_values = values[-90:] if span_days >= 80 and len(values) >= 80 else []
    baseline_mean = statistics.mean(baseline_values) if baseline_values else None

    metrics.update(
        {
            "current_week_mean": round(current_mean, 2),
            "previous_week_mean": round(previous_mean, 2),
            "week_over_week_change_percent": round(week_change, 2),
            "seven_day_slope": round(slope, 3),
            "ninety_day_baseline_mean": round(baseline_mean, 2) if baseline_mean is not None else None,
        }
    )
    subcomponents: list[tuple[float, float]] = [
        (0.35, _clamp(current_mean)),
        (0.35, _clamp(50 + week_change * 0.5)),
        (0.20, _clamp(50 + slope * 10)),
    ]
    if baseline_mean is not None:
        peak_ratio = current_mean / max(baseline_mean, 1.0)
        subcomponents.append((0.10, _clamp(50 * peak_ratio)))
    denominator = sum(weight for weight, _ in subcomponents)
    score = sum(weight * value for weight, value in subcomponents) / denominator
    return round(score, 1), metrics, warnings


def _search_evidence(trend: dict[str, Any], metrics: dict[str, float | None]) -> dict[str, Any]:
    summary = (
        f"Current seven-day mean {metrics.get('current_week_mean')}; "
        f"previous seven-day mean {metrics.get('previous_week_mean')}; "
        f"week-on-week change {metrics.get('week_over_week_change_percent')}%."
    )
    last_date = None
    rows = _dated_series(trend)
    if rows:
        last_date = rows[-1][0].isoformat()
    return {
        "source_name": "Google Trends",
        "source_url": "https://trends.google.com/trends/",
        "title": str(trend.get("query") or trend.get("name") or "Google Trends measurement"),
        "published_at": last_date,
        "evidence_type": "search",
        "relevance_score": 1.0,
        "supports_or_contradicts": "supports",
        "evidence_summary": summary,
    }


def social_component(trend: dict[str, Any]) -> tuple[float | None, list[dict[str, Any]], list[str]]:
    has_x = trend.get("x_score") is not None or trend.get("open_x_score") is not None
    has_instagram = trend.get("instagram_score") is not None
    if not has_x and not has_instagram:
        return None, [], []

    growth = _safe_float(
        trend.get("author_growth")
        if trend.get("author_growth") is not None
        else trend.get("mention_growth"),
        0.0,
    )
    mention_growth_score = _clamp(50 + growth * 0.5)
    engagement_rate = _safe_float(trend.get("engagement_per_1000_views"), 0.0)
    if has_x:
        engagement_score = _clamp(100 * (1 - math.exp(-engagement_rate / 25.0)))
        creator_score = _clamp(_safe_float(trend.get("unique_authors")) / 10 * 100)
    else:
        # Aggregate hashtag metadata is directional. Its provider score may be
        # used for within-refresh comparison but cannot create broad confidence.
        engagement_score = _clamp(_safe_float(trend.get("instagram_score")))
        creator_score = 0.0
    platform_count = int(has_x) + int(has_instagram)
    platform_score = 100.0 if platform_count >= 2 else 50.0
    score = (
        0.40 * mention_growth_score
        + 0.30 * engagement_score
        + 0.20 * creator_score
        + 0.10 * platform_score
    )
    quality = _clamp(_safe_float(trend.get("evidence_quality"), 70.0))
    if has_x:
        score *= 0.60 + 0.40 * quality / 100
    else:
        score = min(score, 60.0)

    evidence: list[dict[str, Any]] = []
    if has_x:
        evidence.append(
            {
                "source_name": "X public fashion conversation",
                "source_url": "https://x.com/",
                "title": "Current versus previous seven-day topic window",
                "published_at": datetime.now(tz=timezone.utc).date().isoformat(),
                "evidence_type": "social",
                "relevance_score": round(quality / 100, 2),
                "supports_or_contradicts": "supports",
                "evidence_summary": (
                    f"{int(trend.get('mentions') or 0)} current mentions from "
                    f"{int(trend.get('unique_authors') or 0)} independent authors; "
                    f"author growth {growth:+.1f}%."
                ),
            }
        )
    if has_instagram:
        hashtag = str(trend.get("instagram_hashtag") or trend.get("name") or "").replace(" ", "")
        evidence.append(
            {
                "source_name": "Instagram aggregate hashtag metadata",
                "source_url": "https://www.instagram.com/",
                "title": f"#{hashtag}" if hashtag else "Hashtag comparison",
                "published_at": datetime.now(tz=timezone.utc).date().isoformat(),
                "evidence_type": "social",
                "relevance_score": 0.65,
                "supports_or_contradicts": "supports",
                "evidence_summary": (
                    f"{int(trend.get('instagram_posts_count') or 0):,} public uses"
                    + (
                        f"; {float(trend.get('instagram_posts_per_day') or 0):,.0f} posts/day."
                        if trend.get("instagram_posts_per_day")
                        else "."
                    )
                ),
            }
        )
    return round(_clamp(score), 1), evidence, []


def _deduplicate_evidence(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    exact_seen: set[tuple[str, str, str, str]] = set()
    title_seen: dict[str, dict[str, Any]] = {}
    deduped: list[dict[str, Any]] = []
    duplicates = 0
    for original in rows:
        row = dict(original)
        row["source_url"] = _canonical_url(row.get("source_url"))
        identity = (
            _source_key(row.get("source_name")),
            row["source_url"],
            _title_fingerprint(row.get("title")),
            _source_key(row.get("evidence_summary")),
        )
        if identity in exact_seen:
            duplicates += 1
            continue
        exact_seen.add(identity)
        fingerprint = _title_fingerprint(row.get("title"))
        # Identical substantial titles across domains are likely syndicated.
        if len(fingerprint.split()) >= 6 and fingerprint in title_seen:
            previous = title_seen[fingerprint]
            if source_authority(row.get("source_name")) > source_authority(previous.get("source_name")):
                index = deduped.index(previous)
                deduped[index] = row
                title_seen[fingerprint] = row
            duplicates += 1
            continue
        deduped.append(row)
        if fingerprint:
            title_seen[fingerprint] = row
    return deduped, duplicates


def editorial_component(evidence: list[dict[str, Any]], *, now: datetime) -> float | None:
    eligible = [
        row
        for row in evidence
        if row.get("supports_or_contradicts") == "supports"
        and row.get("evidence_type") in {"editorial", "industry_data", "runway"}
    ]
    if not eligible:
        return None
    weighted_mentions = sum(
        source_authority(row.get("source_name"))
        * recency_factor(row.get("published_at"), now=now)
        * _clamp(_safe_float(row.get("relevance_score"), 0.0), 0.0, 1.0)
        for row in eligible
    )
    return round(min(100.0, weighted_mentions / 8.0 * 100), 1)


def cross_source_component(evidence: list[dict[str, Any]]) -> tuple[float | None, int, set[str]]:
    supporting = [row for row in evidence if row.get("supports_or_contradicts") == "supports"]
    if not supporting:
        return None, 0, set()
    domains = {_domain(row.get("source_url")) for row in supporting}
    domains.discard("")
    domain_count = len(domains)
    base_by_count = {0: 0, 1: 20, 2: 40, 3: 60, 4: 75, 5: 88}
    base = 100 if domain_count >= 6 else base_by_count[domain_count]
    evidence_types = {str(row.get("evidence_type") or "") for row in supporting}
    diversity_bonus = max(0, len(evidence_types) - 1) * 3
    return round(min(100.0, base + diversity_bonus), 1), domain_count, evidence_types


def runway_component(evidence: list[dict[str, Any]]) -> float | None:
    rows = [
        row
        for row in evidence
        if row.get("supports_or_contradicts") == "supports"
        and row.get("evidence_type") in {"runway", "celebrity"}
    ]
    if not rows:
        return None
    domains = {_domain(row.get("source_url")) for row in rows if _domain(row.get("source_url"))}
    celebrity = sum(row.get("evidence_type") == "celebrity" for row in rows)
    runway = len(rows) - celebrity
    score = 35 + min(45, max(0, runway - 1) * 18 + celebrity * 12)
    if len(domains) >= 2:
        score += 10
    return round(_clamp(score), 1)


def commercial_component(evidence: list[dict[str, Any]]) -> float | None:
    rows = [
        row
        for row in evidence
        if row.get("supports_or_contradicts") == "supports"
        and row.get("evidence_type") == "retail"
    ]
    if not rows:
        return None
    domains = {_domain(row.get("source_url")) for row in rows if _domain(row.get("source_url"))}
    if len(domains) >= 4:
        score = 95
    elif len(domains) >= 2:
        score = 78
    elif len(rows) >= 3:
        score = 65
    elif len(rows) >= 2:
        score = 55
    else:
        score = 40
    return float(score)


def _infer_trend_type(trend: dict[str, Any]) -> str:
    name = _source_key(trend.get("name"))
    if any(token in name for token in ("yellow", "red", "pink", "purple", "blue", "green", "brown", "white", "black", "colour", "color")):
        return "colour"
    if any(token in name for token in ("suede", "raffia", "denim", "silk", "lace", "crochet", "leather", "satin", "tweed")):
        return "material"
    if any(token in name for token in ("layered", "styling", "over ", "under ", "scarf top")):
        return "styling"
    if any(token in name for token in ("waist", "hem", "silhouette", "barrel", "bubble", "oversized", "slim")):
        return "silhouette"
    if any(token in name for token in ("core", "chic", "aesthetic", "boho", "preppy", "minimalism", "romantic")):
        return "aesthetic"
    return "product"


def _momentum_label(metrics: dict[str, float | None], trend: dict[str, Any]) -> str:
    signals: list[float] = []
    if metrics.get("week_over_week_change_percent") is not None:
        signals.append(float(metrics["week_over_week_change_percent"] or 0))
    if trend.get("author_growth") is not None or trend.get("mention_growth") is not None:
        signals.append(
            _safe_float(
                trend.get("author_growth")
                if trend.get("author_growth") is not None
                else trend.get("mention_growth")
            )
        )
    if not signals:
        return "insufficient data"
    value = statistics.mean(signals)
    if value >= 50:
        return "breakout"
    if value >= 20:
        return "accelerating"
    if value >= 5:
        return "steadily rising"
    if value > -5:
        return "stable"
    if value > -20:
        return "cooling"
    return "declining"


def _confidence_label(score: float, completeness: float, domains: int, evidence_count: int) -> str:
    if score >= 75 and completeness >= 65 and domains >= 3 and evidence_count >= 4:
        return "High"
    if score >= 55 and completeness >= 40 and domains >= 2 and evidence_count >= 3:
        return "Medium"
    return "Exploratory"


def _commercial_interpretation(score: float | None, evidence: list[dict[str, Any]]) -> str:
    retailers = {
        row.get("source_name")
        for row in evidence
        if row.get("evidence_type") == "retail"
        and row.get("supports_or_contradicts") == "supports"
    }
    if score is None:
        return "External retailer availability was not measured; do not interpret this as no demand."
    if score >= 90:
        return "The trend is available across several independent retail channels."
    if score >= 70:
        return "Several recognised retail sources show current commercial availability."
    if score >= 50:
        return "Commercial availability is visible but still concentrated in a limited set of sources."
    return f"Only isolated product-level availability was found{f' via {next(iter(retailers))}' if retailers else ''}."


def score_trend_v2(trend: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    publisher_rows = [
        _publisher_evidence(row)
        for row in trend.get("commercial_evidence") or trend.get("evidence") or []
        if isinstance(row, dict)
        and (
            row.get("publisher")
            or row.get("article_title")
            or row.get("source_name")
        )
    ]
    google_score, google_metrics, google_warnings = google_component(trend)
    social_score, social_evidence, social_warnings = social_component(trend)
    raw_evidence: list[dict[str, Any]] = [*publisher_rows, *social_evidence]
    if google_score is not None:
        raw_evidence.append(_search_evidence(trend, google_metrics))
    evidence, duplicate_count = _deduplicate_evidence(raw_evidence)

    editorial_score = editorial_component(evidence, now=reference)
    cross_score, domain_count, evidence_types = cross_source_component(evidence)
    runway_score = runway_component(evidence)
    commercial_score = commercial_component(evidence)
    breakdown: dict[str, float | None] = {
        "editorial": editorial_score,
        "cross_source": cross_score,
        "google_trends": google_score,
        "social": social_score,
        "runway_celebrity": runway_score,
        "commercial": commercial_score,
    }
    available = {
        component: value
        for component, value in breakdown.items()
        if value is not None
    }
    denominator = sum(COMPONENT_WEIGHTS[key] for key in available) or 1.0
    score = sum(
        COMPONENT_WEIGHTS[key] * float(value)
        for key, value in available.items()
    ) / denominator
    completeness = 100 * sum(COMPONENT_WEIGHTS[key] for key in available)
    supporting = [row for row in evidence if row.get("supports_or_contradicts") == "supports"]
    contradictions = [row for row in evidence if row.get("supports_or_contradicts") == "contradicts"]
    score -= min(20.0, 6.0 * len(contradictions))

    warnings = [*google_warnings, *social_warnings]
    caps: list[tuple[float, str]] = []
    if domain_count <= 1:
        caps.append((55.0, "Only one independent source: confidence capped at 55."))
    if len(supporting) < 3:
        caps.append((60.0, "Fewer than three independent evidence items: confidence capped at 60."))
    product_launch_only = bool(supporting) and all(
        row.get("evidence_type") == "retail" for row in supporting
    )
    if product_launch_only:
        caps.append((50.0, "Only isolated product-launch or retail evidence: confidence capped at 50."))
    dated_recent = any(
        (
            (published := parse_utc(row.get("published_at"))) is not None
            and 0 <= (reference - published).days <= 14
        )
        for row in supporting
    )
    if not dated_recent:
        caps.append((45.0, "No evidence published or measured in the current 14-day period: confidence capped at 45."))
    for cap, message in caps:
        if score > cap:
            score = cap
        warnings.append(message)
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate or likely syndicated evidence item(s) were excluded.")
    if contradictions:
        warnings.append(f"{len(contradictions)} contradictory evidence item(s) reduced confidence.")

    score = round(_clamp(score), 1)
    completeness = round(_clamp(completeness), 1)
    evidence_count = len(evidence)
    confidence = _confidence_label(score, completeness, domain_count, evidence_count)
    decision_ready = (
        score >= 55
        and evidence_count >= 3
        and domain_count >= 2
        and dated_recent
    )
    missing = [
        COMPONENT_LABELS[key]
        for key, value in breakdown.items()
        if value is None
    ]
    sources = list(
        dict.fromkeys(
            str(row.get("source_name") or "")
            for row in evidence
            if row.get("source_name")
        )
    )
    name = str(trend.get("name") or trend.get("trend_name") or "Unnamed trend")
    result = dict(trend)
    result.update(
        {
            "trend_name": name,
            "canonical_slug": str(trend.get("id") or trend.get("canonical_slug") or ""),
            "trend_type": _infer_trend_type(trend),
            "confidence_score": score,
            "data_completeness_score": completeness,
            "hula_opportunity_score": _safe_float(trend.get("hula_opportunity_score"), 0.0),
            "momentum": _momentum_label(google_metrics, trend),
            "score_breakdown": breakdown,
            "google_trends_metrics": google_metrics,
            "independent_domain_count": domain_count,
            "evidence_count": evidence_count,
            "commercial_interpretation": _commercial_interpretation(commercial_score, evidence),
            "recommended_hula_products": list(trend.get("recommended_hula_products") or []),
            "evidence": evidence,
            "warnings": list(dict.fromkeys(str(item) for item in warnings if str(item))),
            # Compatibility fields used by the existing app and catalogue matcher.
            "score": score,
            "google_score": google_score,
            "x_score": social_score,
            "open_x_score": social_score,
            "commercial_score": commercial_score,
            "instagram_score": trend.get("instagram_score"),
            "confidence": confidence,
            "decision_ready": decision_ready,
            "missing_components": missing,
            "sources": sources,
            "component_weights": {
                key: round(COMPONENT_WEIGHTS[key] / denominator, 4)
                for key in available
            },
            "evidence_type_count": len(evidence_types),
        }
    )
    return result


def upgrade_trends_to_v2(
    trends: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    limit: int = 80,
) -> list[dict[str, Any]]:
    scored = [score_trend_v2(dict(trend), now=now) for trend in trends]
    scored.sort(
        key=lambda row: (
            float(row.get("confidence_score") or 0),
            float(row.get("data_completeness_score") or 0),
        ),
        reverse=True,
    )
    return scored[: max(1, int(limit))]


def _resale_suitability(trend: dict[str, Any]) -> float:
    trend_type = str(trend.get("trend_type") or "product")
    category = str(trend.get("category") or "").casefold()
    if trend_type == "product":
        return 92.0 if category in {"bags", "shoes", "jewellery & accessories"} else 86.0
    if trend_type in {"material", "silhouette"}:
        return 84.0
    if trend_type in {"styling", "aesthetic"}:
        return 76.0
    return 70.0


def apply_hula_opportunity_scores(
    trends: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    products: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    product_lookup = {str(product.get("id")): product for product in products}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in recommendations:
        grouped[str(row.get("trend_id") or "")].append(row)
    updated_trends: list[dict[str, Any]] = []
    trend_scores: dict[str, float] = {}
    for original in trends:
        trend = dict(original)
        trend_id = str(trend.get("id") or trend.get("canonical_slug") or "")
        matches = sorted(
            grouped.get(trend_id, []),
            key=lambda row: float(row.get("match_score") or 0),
            reverse=True,
        )
        top_scores = [float(row.get("match_score") or 0) for row in matches[:3]]
        if top_scores:
            catalogue_match = 0.65 * max(top_scores) + 0.35 * statistics.mean(top_scores)
        else:
            catalogue_match = 0.0
        resale = _resale_suitability(trend)
        confidence = float(trend.get("confidence_score") or trend.get("score") or 0)
        hula_score = round(
            _clamp(0.65 * confidence + 0.25 * catalogue_match + 0.10 * resale),
            1,
        )
        product_names: list[str] = []
        for row in matches[:5]:
            product = product_lookup.get(str(row.get("product_id") or "")) or {}
            label = " · ".join(
                part
                for part in (
                    str(product.get("vendor") or "").strip(),
                    str(product.get("title") or "").strip(),
                )
                if part
            )
            if label:
                product_names.append(label)
        trend.update(
            {
                "catalogue_match_score": round(catalogue_match, 1),
                "luxury_resale_suitability_score": round(resale, 1),
                "hula_opportunity_score": hula_score,
                "recommended_hula_products": product_names,
            }
        )
        trend_scores[trend_id] = hula_score
        updated_trends.append(trend)

    updated_recommendations = [
        {
            **row,
            "trend_confidence_score": round(
                float(
                    next(
                        (
                            trend.get("confidence_score")
                            for trend in updated_trends
                            if str(trend.get("id") or trend.get("canonical_slug") or "")
                            == str(row.get("trend_id") or "")
                        ),
                        row.get("trend_score") or 0,
                    )
                ),
                1,
            ),
            "hula_trend_opportunity_score": trend_scores.get(str(row.get("trend_id") or ""), 0.0),
        }
        for row in recommendations
    ]
    return updated_trends, updated_recommendations


def upgrade_snapshot_to_v2(snapshot: dict[str, Any]) -> dict[str, Any]:
    updated = dict(snapshot)
    meta = dict(updated.get("meta") or {})
    generated = parse_utc(meta.get("generated_at")) or datetime.now(tz=timezone.utc)
    existing_trends = list(updated.get("trends") or [])
    already_v2 = (
        str(meta.get("methodology_version") or updated.get("methodology_version") or "")
        == METHODOLOGY_VERSION
        and all(
            isinstance(trend.get("score_breakdown"), dict)
            and trend.get("confidence_score") is not None
            for trend in existing_trends
        )
    )
    trends = (
        [dict(trend) for trend in existing_trends]
        if already_v2
        else upgrade_trends_to_v2(existing_trends, now=generated)
    )
    trends, recommendations = apply_hula_opportunity_scores(
        trends,
        list(updated.get("recommendations") or []),
        list(updated.get("products") or []),
    )
    meta["methodology_version"] = METHODOLOGY_VERSION
    updated["meta"] = meta
    updated["analysis_period"] = analysis_period(
        generated,
        geography=str(meta.get("region") or "global"),
    )
    updated["methodology_version"] = METHODOLOGY_VERSION
    updated["trends"] = trends
    updated["recommendations"] = recommendations
    if not updated.get("excluded_candidates"):
        updated["excluded_candidates"] = [
            {
                "candidate": str(row.get("term") or row.get("candidate") or ""),
                "reason": normalise_exclusion_reason(row.get("reason")),
            }
            for row in meta.get("filtered_terms") or []
            if str(row.get("term") or row.get("candidate") or "").strip()
        ]
    return updated
