from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterable


def parse_utc(value: Any) -> datetime | None:
    """Parse common API timestamp formats without inventing a fallback date."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            parsed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OSError, OverflowError, TypeError, ValueError):
            return None
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
            except (TypeError, ValueError, OverflowError):
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_timestamp(
    value: Any,
    *,
    now: datetime | None = None,
    current_days: int = 7,
    total_days: int = 14,
    future_tolerance_hours: int = 6,
) -> str:
    """Classify a real timestamp into the current or comparison window."""

    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    parsed = parse_utc(value)
    if parsed is None:
        return "invalid"
    if parsed > reference + timedelta(hours=max(0, future_tolerance_hours)):
        return "future"
    if parsed >= reference - timedelta(days=max(1, current_days)):
        return "current"
    if parsed >= reference - timedelta(days=max(current_days + 1, total_days)):
        return "previous"
    return "outside"


def validate_fresh_posts(
    posts: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    current_days: int = 7,
    total_days: int = 14,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply the freshness contract before text extraction or scoring.

    Missing/malformed dates, future records, reposts, empty posts and records
    older than the comparison window are rejected. Any scraper-supplied window
    is overwritten from the actual publication timestamp.
    """

    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    accepted: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    seen: set[str] = set()

    for original in posts:
        row = dict(original)
        text = str(row.get("text") or "").strip()
        if not text:
            rejected["empty_text"] += 1
            continue
        if row.get("is_repost"):
            rejected["repost"] += 1
            continue

        parsed = parse_utc(row.get("created_at"))
        window = classify_timestamp(
            parsed,
            now=reference,
            current_days=current_days,
            total_days=total_days,
        )
        if window == "invalid":
            rejected["missing_or_invalid_date"] += 1
            continue
        if window == "future":
            rejected["future_date"] += 1
            continue
        if window == "outside":
            rejected["older_than_14_days"] += 1
            continue

        identifier = str(row.get("post_hash") or "").strip()
        if identifier and identifier in seen:
            rejected["duplicate"] += 1
            continue
        if identifier:
            seen.add(identifier)

        row["created_at"] = parsed.isoformat()
        row["listening_window"] = window
        accepted.append(row)

    dates = [
        parsed
        for parsed in (parse_utc(row.get("created_at")) for row in accepted)
        if parsed is not None
    ]
    profile_counts = Counter(
        str(row.get("source_account") or row.get("platform") or "unknown")
        for row in accepted
    )
    stats: dict[str, Any] = {
        "collected": len(accepted) + sum(rejected.values()),
        "accepted": len(accepted),
        "rejected": sum(rejected.values()),
        "rejected_by_reason": dict(sorted(rejected.items())),
        "current": sum(row.get("listening_window") == "current" for row in accepted),
        "previous": sum(row.get("listening_window") == "previous" for row in accepted),
        "oldest_post": min(dates).isoformat() if dates else None,
        "newest_post": max(dates).isoformat() if dates else None,
        "profile_counts": dict(sorted(profile_counts.items())),
        "window_days": total_days,
    }
    return accepted, stats


def validate_series(
    points: Iterable[dict[str, Any]],
    *,
    min_score_points: int = 3,
    min_chart_points: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Clean one search timeline and report whether drawing it is meaningful."""

    by_date: dict[str, dict[str, Any]] = {}
    rejected = 0
    for point in points:
        parsed = parse_utc(point.get("date") or point.get("timestamp"))
        raw_value = point.get("value")
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            rejected += 1
            continue
        if parsed is None or not math.isfinite(value):
            rejected += 1
            continue
        row = {
            "date": parsed.date().isoformat(),
            "value": round(value, 4),
        }
        if point.get("raw_value") is not None:
            try:
                raw_number = float(point["raw_value"])
                if math.isfinite(raw_number):
                    row["raw_value"] = round(raw_number, 4)
            except (TypeError, ValueError):
                pass
        by_date[row["date"]] = row

    cleaned = [by_date[key] for key in sorted(by_date)]
    values = [float(point["value"]) for point in cleaned]
    distinct_values = len({round(value, 6) for value in values})
    flat = len(values) >= min_score_points and distinct_values < 2
    # An invariant provider series can reflect an anchor/calibration failure.
    # It is neither scored nor charted, so a fabricated-looking horizontal
    # line cannot become a business recommendation.
    score_ready = len(values) >= min_score_points and not flat
    chart_ready = len(values) >= min_chart_points and not flat
    issue = ""
    if len(values) < min_score_points:
        issue = "Too few valid timeline points"
    elif flat:
        issue = (
            "The provider returned an invariant series; it is excluded from "
            "scoring and charts"
        )

    return cleaned, {
        "points": len(cleaned),
        "rejected_points": rejected,
        "distinct_values": distinct_values,
        "flat": flat,
        "score_ready": score_ready,
        "chart_ready": chart_ready,
        "issue": issue,
        "oldest_date": cleaned[0]["date"] if cleaned else None,
        "newest_date": cleaned[-1]["date"] if cleaned else None,
    }


def source_freshness_state(
    *,
    configured: bool,
    succeeded: bool,
    accepted: int = 0,
    rejected: int = 0,
    partial: bool = False,
    newest_at: Any = None,
    stale_after_hours: int = 192,
    now: datetime | None = None,
) -> str:
    """Return one of the five governed source-health states."""

    if not configured:
        return "NOT CONFIGURED"
    if not succeeded:
        return "FAILED"
    newest = parse_utc(newest_at)
    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    if newest is not None:
        age_hours = (reference - newest).total_seconds() / 3600
        if age_hours > max(1, stale_after_hours):
            return "STALE"
    if partial or rejected or accepted == 0:
        return "PARTIAL"
    return "LIVE"
