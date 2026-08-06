from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from src.analysis.freshness import parse_utc
from src.analysis.trends import canonical_name, generic_trend_reason, slugify


LIVE_DISCOVERY_ORIGINS = {
    "live_publisher",
    "live_social",
    "live_search_discovery",
}

ORIGIN_PRIORITY = (
    "live_publisher",
    "live_search_discovery",
    "live_social",
    "configured_seed",
    "historical",
    "demo",
)

ORIGIN_LABELS = {
    "live_publisher": "Live publisher discovery",
    "live_search_discovery": "Live Google related-query discovery",
    "live_social": "Live social discovery",
    "configured_seed": "Configured fallback seed",
    "historical": "Historical snapshot",
    "demo": "Illustrative demo data",
}


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, float(value)))


def _published_freshness(value: Any, *, now: datetime) -> float:
    published = parse_utc(value)
    if published is None:
        return 20.0
    age_days = max(0.0, (now - published).total_seconds() / 86400)
    if age_days <= 1:
        return 100.0
    if age_days <= 3:
        return 92.0
    if age_days <= 7:
        return 82.0
    if age_days <= 14:
        return 65.0
    if age_days <= 30:
        return 40.0
    if age_days <= 90:
        return 20.0
    return 8.0


def enrich_commercial_priorities(
    rows: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Rank publisher discoveries for *validation*, not public confidence.

    The public score correctly requires corroboration. This separate priority
    makes sure a newly published, one-source discovery is measured before an
    older multi-source theme instead of disappearing below yesterday's seeds.
    """

    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    output: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        evidence = [
            dict(item)
            for item in row.get("commercial_evidence") or []
            if isinstance(item, dict)
        ]
        dates = [
            parsed
            for item in evidence
            if (parsed := parse_utc(item.get("published_at"))) is not None
        ]
        newest = max(dates) if dates else None
        current_count = sum(
            0 <= (reference - published).total_seconds() / 86400 <= 14
            for published in dates
        )
        freshness = max(
            (_published_freshness(item.get("published_at"), now=reference) for item in evidence),
            default=20.0,
        )
        commercial_score = _clamp(float(row.get("commercial_score") or 0))
        publisher_count = max(0, int(row.get("publisher_count") or 0))
        breadth = min(100.0, 33.34 * publisher_count)
        priority = 0.60 * freshness + 0.25 * commercial_score + 0.15 * breadth
        row.update(
            {
                "validation_priority_score": round(_clamp(priority), 1),
                "publisher_freshness_score": round(freshness, 1),
                "current_article_count": current_count,
                "newest_published_at": newest.isoformat() if newest else "",
            }
        )
        output.append(row)
    return sorted(
        output,
        key=lambda row: (
            float(row.get("validation_priority_score") or 0),
            float(row.get("commercial_score") or 0),
            str(row.get("name") or ""),
        ),
        reverse=True,
    )


def consolidate_commercial_evidence(
    evidence: Iterable[dict[str, Any]],
    clusters: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply conservative alias clusters before publisher counts are scored."""

    alias_lookup: dict[str, str] = {}
    for cluster in clusters:
        name = canonical_name(str(cluster.get("name") or ""))
        if not name or generic_trend_reason(name, trusted_source=True):
            continue
        aliases = [name, *(cluster.get("aliases") or [])]
        for alias in aliases:
            canonical = canonical_name(str(alias or ""))
            if canonical:
                alias_lookup.setdefault(slugify(canonical), name)

    output: list[dict[str, Any]] = []
    for original in evidence:
        row = dict(original)
        original_name = canonical_name(
            str(row.get("trend_name") or row.get("explicit_label") or "")
        )
        if not original_name:
            continue
        name = alias_lookup.get(slugify(original_name), original_name)
        row["original_trend_name"] = original_name
        row["trend_name"] = name
        row["trend_id"] = slugify(name)
        output.append(row)
    return output


def _origin_sort(origins: Iterable[str]) -> list[str]:
    values = {str(value) for value in origins if str(value)}
    return [origin for origin in ORIGIN_PRIORITY if origin in values]


def build_validation_plan(
    commercial_rows: Iterable[dict[str, Any]],
    social_rows: Iterable[dict[str, Any]],
    *,
    related_rows: Iterable[dict[str, Any]] = (),
    configured_terms: Iterable[str] = (),
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Choose a bounded, live-first set for Google and Instagram validation."""

    maximum = max(1, int(limit))
    candidates: dict[str, dict[str, Any]] = {}

    def add(name: Any, origin: str, priority: float, **detail: Any) -> None:
        canonical = canonical_name(str(name or ""))
        if not canonical:
            return
        trusted = origin == "live_publisher"
        if generic_trend_reason(canonical, trusted_source=trusted):
            return
        trend_id = slugify(canonical)
        row = candidates.setdefault(
            trend_id,
            {
                "id": trend_id,
                "name": canonical,
                "priority": 0.0,
                "origins": set(),
                "publisher_count": 0,
                "current_article_count": 0,
                "newest_published_at": "",
            },
        )
        row["priority"] = max(float(row.get("priority") or 0), _clamp(priority))
        row["origins"].add(origin)
        row["publisher_count"] = max(
            int(row.get("publisher_count") or 0),
            int(detail.get("publisher_count") or 0),
        )
        row["current_article_count"] = max(
            int(row.get("current_article_count") or 0),
            int(detail.get("current_article_count") or 0),
        )
        newest = str(detail.get("newest_published_at") or "")
        if newest > str(row.get("newest_published_at") or ""):
            row["newest_published_at"] = newest

    for row in enrich_commercial_priorities(commercial_rows):
        add(
            row.get("name"),
            "live_publisher",
            float(row.get("validation_priority_score") or 0),
            publisher_count=row.get("publisher_count"),
            current_article_count=row.get("current_article_count"),
            newest_published_at=row.get("newest_published_at"),
        )
    for row in social_rows:
        social_score = float(
            row.get("open_x_score")
            if row.get("open_x_score") is not None
            else row.get("x_score")
            or 0
        )
        novelty = float(row.get("novelty_score") or 0)
        add(row.get("name"), "live_social", 0.75 * social_score + 0.25 * novelty)
    for row in related_rows:
        value = max(0.0, float(row.get("value") or 0))
        add(
            row.get("query") or row.get("name"),
            "live_search_discovery",
            65.0 + min(30.0, value / 10.0),
        )
    for term in configured_terms:
        add(term, "configured_seed", 5.0)

    publisher = sorted(
        (
            row
            for row in candidates.values()
            if "live_publisher" in row["origins"]
        ),
        key=lambda row: (float(row["priority"]), str(row["name"])),
        reverse=True,
    )
    supporting = sorted(
        (
            row
            for row in candidates.values()
            if row["origins"] & {"live_social", "live_search_discovery"}
        ),
        key=lambda row: (float(row["priority"]), str(row["name"])),
        reverse=True,
    )
    publisher_quota = min(len(publisher), max(1, round(maximum * 0.67))) if publisher else 0
    supporting_quota = (
        min(len(supporting), max(1, maximum - publisher_quota))
        if supporting
        else 0
    )
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    def take(rows: Iterable[dict[str, Any]], count: int | None = None) -> None:
        added = 0
        for row in rows:
            if row["id"] in selected_ids:
                continue
            selected.append(row)
            selected_ids.add(row["id"])
            added += 1
            if len(selected) >= maximum or (count is not None and added >= count):
                break

    take(publisher, publisher_quota)
    take(supporting, supporting_quota)
    live_remaining = sorted(
        (
            row
            for row in candidates.values()
            if row["origins"] & LIVE_DISCOVERY_ORIGINS
        ),
        key=lambda row: (float(row["priority"]), str(row["name"])),
        reverse=True,
    )
    take(live_remaining)
    if len(selected) < maximum:
        configured = sorted(
            candidates.values(),
            key=lambda row: (float(row["priority"]), str(row["name"])),
            reverse=True,
        )
        take(configured)

    selected.sort(
        key=lambda row: (
            int(
                "live_publisher" in row["origins"]
                and int(row.get("current_article_count") or 0) > 0
            ),
            int("live_publisher" in row["origins"]),
            float(row["priority"]),
            str(row["name"]),
        ),
        reverse=True,
    )
    output: list[dict[str, Any]] = []
    for rank, original in enumerate(selected[:maximum], 1):
        row = dict(original)
        row["origins"] = _origin_sort(row.get("origins") or [])
        row["priority"] = round(float(row.get("priority") or 0), 1)
        row["rank"] = rank
        row["seed_only"] = row["origins"] == ["configured_seed"]
        output.append(row)
    return output


def candidate_plan_fingerprint(plan: Iterable[dict[str, Any]]) -> str:
    payload = sorted(
        (
            {
                "id": str(row.get("id") or slugify(str(row.get("name") or ""))),
                "origins": sorted(str(value) for value in row.get("origins") or []),
            }
            for row in plan
        ),
        key=lambda row: row["id"],
    )
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def select_instagram_targets(
    validation_plan: Iterable[dict[str, Any]],
    *,
    google_rows: Iterable[dict[str, Any]] = (),
    commercial_rows: Iterable[dict[str, Any]] = (),
    social_rows: Iterable[dict[str, Any]] = (),
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Keep Instagram focused on the same live-first candidates as search."""

    maximum = max(1, int(limit))
    rows_by_id: dict[str, dict[str, Any]] = {}
    for row in [*google_rows, *commercial_rows, *social_rows]:
        name = canonical_name(str(row.get("name") or ""))
        if name:
            rows_by_id.setdefault(slugify(name), dict(row))

    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    plan = list(validation_plan)
    for item in plan:
        if item.get("seed_only"):
            continue
        trend_id = str(item.get("id") or slugify(str(item.get("name") or "")))
        if trend_id in seen:
            continue
        row = dict(rows_by_id.get(trend_id) or {})
        row.update({"id": trend_id, "name": item.get("name")})
        output.append(row)
        seen.add(trend_id)
        if len(output) >= maximum:
            return output

    for item in plan:
        trend_id = str(item.get("id") or slugify(str(item.get("name") or "")))
        if trend_id in seen:
            continue
        output.append({"id": trend_id, "name": item.get("name")})
        seen.add(trend_id)
        if len(output) >= maximum:
            break
    return output


def annotate_discovery_provenance(
    trends: Iterable[dict[str, Any]],
    validation_plan: Iterable[dict[str, Any]],
    *,
    commercial_rows: Iterable[dict[str, Any]] = (),
    social_rows: Iterable[dict[str, Any]] = (),
    fallback_kind: str = "",
) -> list[dict[str, Any]]:
    plan_by_id = {
        str(row.get("id") or slugify(str(row.get("name") or ""))): dict(row)
        for row in validation_plan
    }
    publisher_ids = {
        slugify(canonical_name(str(row.get("name") or "")))
        for row in commercial_rows
        if row.get("name")
    }
    social_ids = {
        slugify(canonical_name(str(row.get("name") or "")))
        for row in social_rows
        if row.get("name")
    }
    output: list[dict[str, Any]] = []
    for original in trends:
        trend = dict(original)
        trend_id = str(trend.get("id") or trend.get("canonical_slug") or "")
        plan = plan_by_id.get(trend_id) or {}
        origins = set(str(value) for value in plan.get("origins") or [])
        if trend_id in publisher_ids:
            origins.add("live_publisher")
        if trend_id in social_ids:
            origins.add("live_social")
        if fallback_kind == "demo" or trend.get("is_demo"):
            origins = {"demo"}
        elif fallback_kind == "stale" or trend.get("is_stale"):
            origins.add("historical")
        ordered = _origin_sort(origins)
        primary = ordered[0] if ordered else "historical"
        trend.update(
            {
                "discovery_origins": ordered or ["historical"],
                "primary_discovery_origin": primary,
                "discovery_origin_label": ORIGIN_LABELS.get(primary, primary),
                "live_discovered": bool(origins & LIVE_DISCOVERY_ORIGINS),
                "validation_selected": bool(plan),
                "validation_rank": int(plan.get("rank") or 0) or None,
                "seed_only": ordered == ["configured_seed"],
            }
        )
        output.append(trend)
    return output
