from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from src.analysis.freshness import parse_utc
from src.analysis.trends import (
    canonical_name,
    generic_trend_reason,
    infer_category,
    slugify,
)


SPONSORED_CUES = (
    "sponsor content",
    "sponsored content",
    "sponsored by",
    "paid content",
    "advertisement",
    "anniversary sale",
    "promo code",
)


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, float(value)))


def _is_sponsored(value: Any) -> bool:
    lowered = str(value or "").casefold()
    return any(cue in lowered for cue in SPONSORED_CUES)


def _short_excerpt(value: Any, *, words: int = 18) -> str:
    return " ".join(str(value or "").strip().split()[: max(1, words)])


def _age_days(value: Any, *, now: datetime) -> float | None:
    published = parse_utc(value)
    if published is None:
        return None
    return max(0.0, (now - published).total_seconds() / 86_400)


def _freshness_score(value: Any, *, now: datetime, lookback_days: int) -> float:
    age = _age_days(value, now=now)
    if age is None:
        return 20.0
    if age <= 2:
        return 100.0
    if age <= 7:
        return 85.0
    if age <= 14:
        return 65.0
    if age <= lookback_days:
        return 45.0
    return 0.0


def build_editorial_evidence(
    articles: Iterable[dict[str, Any]],
    model_results: Iterable[dict[str, Any]],
    deterministic_evidence: Iterable[dict[str, Any]] = (),
    *,
    now: datetime | None = None,
    lookback_days: int = 21,
) -> list[dict[str, Any]]:
    """Combine GPT article extraction with a deterministic title/heading fallback."""

    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    maximum_age = max(7, int(lookback_days))
    article_by_id = {
        str(row.get("article_id") or ""): dict(row)
        for row in articles
        if str(row.get("article_id") or "")
    }
    article_urls = {
        str(row.get("url") or "")
        for row in article_by_id.values()
        if str(row.get("url") or "")
    }
    candidates: list[dict[str, Any]] = []

    for original in deterministic_evidence:
        row = dict(original)
        if _is_sponsored(row.get("article_title")):
            continue
        age = _age_days(row.get("published_at"), now=reference)
        if age is not None and age > maximum_age:
            continue
        name = canonical_name(
            str(row.get("trend_name") or row.get("explicit_label") or "")
        )
        if generic_trend_reason(name, trusted_source=True):
            continue
        row.update(
            {
                "trend_name": name,
                "trend_id": slugify(name),
                "google_query": str(row.get("google_query") or name),
                "model_relevance_score": float(
                    row.get("model_relevance_score") or 0.72
                ),
                "extraction_method": "publisher title / heading fallback",
                "article_role": "section",
                "why_it_is_a_trend": (
                    "The publisher explicitly named this trend in its title or section heading."
                ),
            }
        )
        candidates.append(row)

    for result in model_results:
        if not isinstance(result, dict):
            continue
        article = article_by_id.get(str(result.get("article_id") or ""))
        if not article or _is_sponsored(article.get("title")):
            continue
        age = _age_days(article.get("published_at"), now=reference)
        if age is not None and age > maximum_age:
            continue
        for extracted in result.get("trends") or []:
            if not isinstance(extracted, dict):
                continue
            name = canonical_name(str(extracted.get("name") or ""))
            if generic_trend_reason(name, trusted_source=True):
                continue
            try:
                confidence = float(extracted.get("confidence") or 0)
            except (TypeError, ValueError):
                confidence = 0.0
            if confidence < 0.45:
                continue
            candidates.append(
                {
                    "trend_id": slugify(name),
                    "trend_name": name,
                    "explicit_label": _short_excerpt(
                        extracted.get("evidence_excerpt") or name
                    ),
                    "evidence_kind": "GPT article extraction",
                    "publisher": article.get("publisher"),
                    "publisher_id": article.get("publisher_id"),
                    "publisher_group": article.get("publisher_group"),
                    "publisher_weight": article.get("publisher_weight", 1.0),
                    "article_title": article.get("title"),
                    "published_at": article.get("published_at"),
                    "url": article.get("url"),
                    "collected_at": article.get("collected_at"),
                    "acquisition": article.get("acquisition"),
                    "explicit": True,
                    "google_query": str(
                        extracted.get("google_query") or name
                    )[:100],
                    "category_hint": extracted.get("category"),
                    "article_role": extracted.get("article_role"),
                    "why_it_is_a_trend": str(
                        extracted.get("why_it_is_a_trend") or ""
                    )[:320],
                    "model_relevance_score": round(_clamp(confidence, 0, 1), 3),
                    "extraction_method": "OpenAI recent-article scan",
                }
            )

    # Prefer a model-supported row when it duplicates the fallback extraction
    # for the same trend, publisher and article. Independent articles remain.
    best: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in candidates:
        url = str(row.get("url") or "")
        if article_urls and url and url not in article_urls and not row.get("published_at"):
            # A title-only search fallback without a date is too weak for a
            # recent-editorial claim when actual article pages were available.
            continue
        identity = (
            str(row.get("publisher_group") or row.get("publisher_id") or ""),
            str(row.get("trend_id") or ""),
            url,
        )
        if not all(identity):
            continue
        current = best.get(identity)
        if current is None or float(row.get("model_relevance_score") or 0) > float(
            current.get("model_relevance_score") or 0
        ):
            best[identity] = row
    return list(best.values())


def score_editorial_consensus(
    evidence: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    lookback_days: int = 21,
) -> list[dict[str, Any]]:
    """Rank concrete trends primarily by independent publisher overlap."""

    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    maximum_age = max(7, int(lookback_days))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for original in evidence:
        row = dict(original)
        name = canonical_name(str(row.get("trend_name") or ""))
        if generic_trend_reason(name, trusted_source=True):
            continue
        age = _age_days(row.get("published_at"), now=reference)
        if age is not None and age > maximum_age:
            continue
        row["trend_name"] = name
        row["trend_id"] = slugify(name)
        grouped[row["trend_id"]].append(row)

    output: list[dict[str, Any]] = []
    for trend_id, raw_rows in grouped.items():
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in sorted(
            raw_rows,
            key=lambda item: float(item.get("model_relevance_score") or 0),
            reverse=True,
        ):
            identity = (
                str(row.get("publisher_group") or row.get("publisher_id") or ""),
                str(row.get("url") or ""),
            )
            if not all(identity) or identity in seen:
                continue
            seen.add(identity)
            deduped.append(row)
        if not deduped:
            continue

        current_rows = [
            row
            for row in deduped
            if (
                (age := _age_days(row.get("published_at"), now=reference))
                is not None
                and age <= maximum_age
            )
        ]
        # Undated pages remain traceable supporting context, but cannot prove
        # that separate publishers covered a trend inside the recent window.
        if not current_rows:
            continue
        name = canonical_name(str(current_rows[0].get("trend_name") or trend_id))
        publisher_groups = {
            str(row.get("publisher_group") or row.get("publisher_id") or "")
            for row in current_rows
        }
        publisher_groups.discard("")
        publisher_names = list(
            dict.fromkeys(
                str(row.get("publisher") or "")
                for row in current_rows
                if row.get("publisher")
            )
        )
        publisher_count = len(publisher_groups)
        article_count = len({str(row.get("url") or "") for row in current_rows})
        dates = [
            parsed
            for row in current_rows
            if (parsed := parse_utc(row.get("published_at"))) is not None
        ]
        newest = max(dates) if dates else None
        publisher_score = {
            0: 0.0,
            1: 25.0,
            2: 58.0,
            3: 80.0,
            4: 92.0,
        }.get(publisher_count, 100.0)
        freshness_by_group: dict[str, float] = {}
        for row in current_rows:
            group = str(row.get("publisher_group") or row.get("publisher_id") or "")
            freshness_by_group[group] = max(
                freshness_by_group.get(group, 0.0),
                _freshness_score(
                    row.get("published_at"),
                    now=reference,
                    lookback_days=maximum_age,
                ),
            )
        freshness_score = statistics.mean(freshness_by_group.values())
        repetition_score = min(100.0, 25.0 + 15.0 * max(0, article_count - 1))
        extraction_score = 100 * statistics.mean(
            max(0.0, min(1.0, float(row.get("model_relevance_score") or 0.7)))
            for row in current_rows
        )
        consensus_score = (
            0.55 * publisher_score
            + 0.25 * freshness_score
            + 0.10 * repetition_score
            + 0.10 * extraction_score
        )
        query_votes = Counter(
            str(row.get("google_query") or name).strip()
            for row in current_rows
            if str(row.get("google_query") or name).strip()
        )
        google_query = sorted(
            query_votes,
            key=lambda query: (-query_votes[query], len(query), query.casefold()),
        )[0]
        aliases = list(
            dict.fromkeys(
                [
                    name,
                    google_query,
                    *(
                        str(row.get("original_trend_name") or "")
                        for row in current_rows
                    ),
                ]
            )
        )
        aliases = [alias for alias in aliases if alias]
        overlap_label = (
            "Strong editorial consensus"
            if publisher_count >= 3
            else "Confirmed by two publishers"
            if publisher_count == 2
            else "Single-publisher discovery"
        )
        output.append(
            {
                "id": trend_id,
                "name": name,
                "aliases": aliases,
                "google_query": google_query,
                "category": infer_category(name),
                "publisher_count": publisher_count,
                "publisher_names": publisher_names,
                "publisher_groups": sorted(publisher_groups),
                "article_count": article_count,
                "current_article_count": len(current_rows),
                "newest_published_at": newest.isoformat() if newest else "",
                "editorial_consensus_score": round(_clamp(consensus_score), 1),
                "commercial_score": round(_clamp(consensus_score), 1),
                "validation_priority_score": round(_clamp(consensus_score), 1),
                "publisher_freshness_score": round(freshness_score, 1),
                "overlap_label": overlap_label,
                "consensus_reason": (
                    f"{publisher_count} independent publisher"
                    f"{'s' if publisher_count != 1 else ''} named this across "
                    f"{article_count} recent article"
                    f"{'s' if article_count != 1 else ''}."
                ),
                "commercial_evidence": deduped,
            }
        )
    output.sort(
        key=lambda row: (
            int(row.get("publisher_count") or 0),
            float(row.get("editorial_consensus_score") or 0),
            int(row.get("article_count") or 0),
        ),
        reverse=True,
    )
    return output


def build_editorial_validation_plan(
    rows: Iterable[dict[str, Any]],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    for row in sorted(
        rows,
        key=lambda item: (
            int(item.get("publisher_count") or 0),
            float(item.get("editorial_consensus_score") or 0),
        ),
        reverse=True,
    ):
        query = str(row.get("google_query") or row.get("name") or "").strip()
        query_key = query.casefold()
        if not query or query_key in seen_queries:
            continue
        seen_queries.add(query_key)
        plan.append(
            {
                "rank": len(plan) + 1,
                "id": str(row.get("id") or ""),
                "name": str(row.get("name") or ""),
                "query": query,
                "priority": float(row.get("editorial_consensus_score") or 0),
                "publisher_count": int(row.get("publisher_count") or 0),
                "article_count": int(row.get("article_count") or 0),
                "current_article_count": int(row.get("current_article_count") or 0),
                "origins": ["recent_editorial_publishers"],
                "seed_only": False,
            }
        )
        if len(plan) >= max(1, int(limit)):
            break
    return plan


def editorial_plan_fingerprint(plan: Iterable[dict[str, Any]]) -> str:
    compact = [
        {
            "id": str(row.get("id") or ""),
            "query": str(row.get("query") or "").casefold(),
            "publisher_count": int(row.get("publisher_count") or 0),
        }
        for row in plan
    ]
    payload = json.dumps(compact, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def merge_editorial_google_signals(
    editorial_rows: Iterable[dict[str, Any]],
    google_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    google_by_id = {
        str(row.get("editorial_id") or row.get("id") or ""): dict(row)
        for row in google_rows
        if str(row.get("editorial_id") or row.get("id") or "")
    }
    output: list[dict[str, Any]] = []
    for original in editorial_rows:
        editorial = dict(original)
        trend_id = str(editorial.get("id") or "")
        google = google_by_id.get(trend_id) or {}
        publisher_count = int(editorial.get("publisher_count") or 0)
        article_count = int(editorial.get("article_count") or 0)
        name = str(editorial.get("name") or "")
        sources = list(editorial.get("publisher_names") or [])
        if google:
            sources.append("Google Trends")
        output.append(
            {
                "id": trend_id,
                "name": name,
                "trend_name": name,
                "category": editorial.get("category") or infer_category(name),
                "aliases": list(editorial.get("aliases") or []),
                "google_query": editorial.get("google_query") or name,
                "query": google.get("query") or editorial.get("google_query") or name,
                "editorial_consensus_score": editorial.get(
                    "editorial_consensus_score"
                ),
                "commercial_score": editorial.get("commercial_score"),
                "publisher_count": publisher_count,
                "publisher_names": list(editorial.get("publisher_names") or []),
                "publisher_groups": list(editorial.get("publisher_groups") or []),
                "commercial_article_count": article_count,
                "article_count": article_count,
                "current_article_count": int(
                    editorial.get("current_article_count") or 0
                ),
                "newest_published_at": editorial.get("newest_published_at"),
                "publisher_freshness_score": editorial.get(
                    "publisher_freshness_score"
                ),
                "validation_priority_score": editorial.get(
                    "validation_priority_score"
                ),
                "overlap_label": editorial.get("overlap_label"),
                "consensus_reason": editorial.get("consensus_reason"),
                "commercial_evidence": list(
                    editorial.get("commercial_evidence") or []
                ),
                "google_score": google.get("google_score"),
                "google_fresh": google.get("google_fresh"),
                "google_cache_used": google.get("google_cache_used"),
                "google_stale": google.get("google_stale", False),
                "search_interest": google.get("search_interest"),
                "search_baseline": google.get("search_baseline"),
                "search_momentum": google.get("search_momentum"),
                "search_momentum_7d": google.get("search_momentum_7d"),
                "search_slope": google.get("search_slope"),
                "series": list(google.get("series") or []),
                "display_series": list(google.get("display_series") or []),
                "recent_series": list(google.get("recent_series") or []),
                "recent_display_series": list(
                    google.get("recent_display_series") or []
                ),
                "chart_ready": bool(google.get("chart_ready")),
                "recent_chart_ready": bool(google.get("recent_chart_ready")),
                "series_quality": dict(google.get("series_quality") or {}),
                "recent_series_quality": dict(
                    google.get("recent_series_quality") or {}
                ),
                "series_issue": str(google.get("series_issue") or ""),
                "sources": list(dict.fromkeys(sources)),
                "why_now": editorial.get("consensus_reason"),
                "content_angles": [
                    f"The HULA edit: pre-owned pieces aligned with {name.lower()}",
                    f"How to wear {name.lower()} without buying new",
                    f"From archive to now: the circular-fashion case for {name.lower()}",
                ],
                "live_discovered": True,
                "seed_only": False,
                "discovery_origins": ["live_publisher"],
                "primary_discovery_origin": "live_publisher",
                "discovery_origin_label": "Recent editorial discovery",
            }
        )
    return output


def apply_editorial_decision_rules(
    trends: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Turn publisher overlap plus Google movement into plain actions."""

    output: list[dict[str, Any]] = []
    for original in trends:
        trend = dict(original)
        publishers = int(trend.get("publisher_count") or 0)
        current_articles = int(trend.get("current_article_count") or 0)
        metrics = dict(trend.get("google_trends_metrics") or {})
        wow = metrics.get("week_over_week_change_percent")
        yoy = metrics.get("year_over_year_change_percent")
        google_score = (trend.get("score_breakdown") or {}).get("google_trends")
        google_available = google_score is not None and not trend.get("google_stale")
        breakout_single = bool(
            publishers == 1
            and google_available
            and wow is not None
            and float(wow) >= 20
        )
        confirmed = publishers >= 2 and google_available
        decision_ready = bool(current_articles and (confirmed or breakout_single))

        editorial_score = float(trend.get("editorial_consensus_score") or 0)
        measured_google = float(google_score or 0)
        ranking_score = 0.70 * editorial_score + 0.30 * measured_google
        if (
            decision_ready
            and publishers >= 3
            and ranking_score >= 70
            and (wow is None or float(wow) >= -10)
        ):
            action = "Act now"
        elif decision_ready:
            action = "Test this week"
        else:
            action = "Watch"

        clauses = [
            f"{publishers} independent publisher"
            f"{'s' if publishers != 1 else ''} named the trend across "
            f"{int(trend.get('article_count') or trend.get('commercial_article_count') or 0)} recent article"
            f"{'s' if int(trend.get('article_count') or trend.get('commercial_article_count') or 0) != 1 else ''}"
        ]
        if wow is not None:
            clauses.append(f"Google interest is {float(wow):+.0f}% week on week")
        if yoy is not None:
            clauses.append(f"{float(yoy):+.0f}% versus the comparable year-ago window")
        elif not google_available:
            clauses.append("Google movement is not yet measurable")
        trend.update(
            {
                "decision_ready": decision_ready,
                "business_action": action,
                "ranking_score": round(_clamp(ranking_score), 1),
                "why_now": "; ".join(clauses).capitalize() + ".",
            }
        )
        output.append(trend)
    action_rank = {"Act now": 3, "Test this week": 2, "Watch": 1}
    output.sort(
        key=lambda row: (
            action_rank.get(str(row.get("business_action") or "Watch"), 0),
            float(row.get("ranking_score") or 0),
            int(row.get("publisher_count") or 0),
        ),
        reverse=True,
    )
    return output
