from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.analysis.freshness import (
    parse_utc,
    source_freshness_state,
    validate_fresh_posts,
)
from src.analysis.evidence_scoring import (
    METHODOLOGY_VERSION,
    analysis_period,
    apply_hula_opportunity_scores,
    normalise_exclusion_reason,
    upgrade_trends_to_v2,
)
from src.analysis.discovery import (
    annotate_discovery_provenance,
    build_validation_plan,
    candidate_plan_fingerprint,
    consolidate_commercial_evidence,
    enrich_commercial_priorities,
    select_instagram_targets,
)
from src.analysis.listening import build_listening_plan, deduplicate_posts
from src.analysis.matching import match_products
from src.analysis.trends import (
    build_topic_clusters,
    canonical_name,
    consolidate_filter_audit,
    discover_x_candidates,
    extract_x_signals,
    merge_trend_signals,
    score_google_windows,
    slugify,
)
from src.config import Settings
from src.connectors.apify_instagram_hashtags import (
    InstagramHashtagAnalyticsConnector,
)
from src.connectors.apify_x import ApifyXConnector
from src.connectors.commercial_sources import (
    CommercialSourceCollector,
    score_commercial_evidence,
)
from src.connectors.gemini_research import GeminiResearchConnector
from src.connectors.google_trends import GoogleTrendsConnector
from src.connectors.openrouter import OpenRouterConnector
from src.connectors.openai_responses import OpenAIResponsesConnector
from src.connectors.shopify import ShopifyConnector
from src.connectors.supabase_store import SupabaseStore
from src.demo_data import demo_products, demo_trends
from src.editorial.blog_generator import generate_researched_blog
from src.storage import load_snapshot, load_trend_presence, save_snapshot


DISCOVERY_SEEDS = [
    "women's fashion trends",
    "designer bag trends",
    "shoe trends",
    "runway trends",
    "jewellery trends",
    "vintage fashion trends",
]

GOOGLE_CACHE_SCHEMA_VERSION = "4.0"


def _openrouter(settings: Settings) -> OpenRouterConnector:
    return OpenRouterConnector(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        api_url=settings.openrouter_api_url,
        timeout=settings.openrouter_timeout,
        site_url=settings.openrouter_site_url,
        app_name=settings.openrouter_app_name,
    )


def _openai(settings: Settings) -> OpenAIResponsesConnector:
    return OpenAIResponsesConnector(
        settings.openai_api_key,
        api_url=settings.openai_api_url,
        luna_model=settings.openai_luna_model,
        terra_model=settings.openai_terra_model,
        sol_model=settings.openai_sol_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )


def _gemini(settings: Settings) -> GeminiResearchConnector:
    return GeminiResearchConnector(
        settings.gemini_api_key,
        model=settings.gemini_model,
        api_url=settings.gemini_api_url,
        timeout_seconds=settings.gemini_timeout_seconds,
        grounding_enabled=settings.gemini_grounding_enabled,
    )


def _supabase(settings: Settings) -> SupabaseStore:
    return SupabaseStore(
        settings.supabase_url,
        settings.supabase_secret_key,
        snapshot_table=settings.supabase_snapshot_table,
        blog_table=settings.supabase_blog_table,
    )


def _cache_state(
    snapshot: dict[str, Any] | None,
    settings: Settings,
) -> tuple[dict[str, Any], float | None]:
    cache = dict((snapshot or {}).get("google_cache") or {})
    compatible = (
        str(cache.get("schema_version") or "") == GOOGLE_CACHE_SCHEMA_VERSION
        and
        str(cache.get("market") or "").upper() == settings.google_geo.upper()
        and str(cache.get("context_timeframe") or "") == settings.google_timeframe
        and str(cache.get("discovery_timeframe") or "")
        == settings.google_discovery_timeframe
        and isinstance(cache.get("context_series"), dict)
        and bool(cache.get("context_series"))
    )
    if not compatible:
        return {}, None
    collected = parse_utc(cache.get("collected_at"))
    if collected is None:
        return {}, None
    age_hours = max(
        0.0,
        (datetime.now(tz=timezone.utc) - collected).total_seconds() / 3600,
    )
    return cache, age_hours


def _status(state: str, detail: str) -> str:
    return f"{state} · {detail}" if detail else state


def _collect_x(
    settings: Settings,
    warnings: list[str],
    *,
    validation_terms: list[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    summary: dict[str, Any] = {
        "mode": settings.apify_x_listening_mode,
        "planned": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped_capacity": 0,
        "collected": 0,
        "unique": 0,
        "duplicates_removed": 0,
        "freshness": {},
        "usage_usd": None,
        "expert_accounts": len(settings.x_expert_accounts),
        "priority_commercial_accounts": len(settings.x_priority_accounts),
        "validation_terms": list(validation_terms or []),
    }
    if not settings.apify_configured:
        return [], summary, "NOT CONFIGURED"

    try:
        connector = ApifyXConnector(
            settings.apify_token,
            settings.apify_x_task_id,
            timeout_seconds=settings.apify_timeout_seconds,
            memory_mb=settings.apify_x_memory_mb,
        )
        if settings.topic_plan_enabled:
            plan = build_listening_plan(
                language=settings.x_language,
                results_per_query=settings.apify_results_per_query,
                expert_results_per_query=settings.apify_expert_results_per_query,
                expert_accounts=settings.x_expert_accounts,
                priority_accounts=settings.x_priority_accounts,
                validation_terms=validation_terms or [],
            )
            result = connector.run_listening_plan(
                plan,
                base_task_input=settings.apify_x_task_input,
                max_total_charge_usd=settings.apify_max_total_charge_usd,
            )
            raw_posts = list(result.get("posts") or [])
            summary.update(
                {
                    "planned": int(result.get("planned") or 0),
                    "succeeded": int(result.get("succeeded") or 0),
                    "failed": int(result.get("failed") or 0),
                    "skipped_capacity": int(
                        result.get("skipped_capacity") or 0
                    ),
                    "usage_usd": result.get("usage_usd"),
                    "runs": result.get("runs") or [],
                }
            )
            warnings.extend(result.get("warnings") or [])
        else:
            raw_posts = connector.run(settings.apify_x_task_input)
            summary.update({"planned": 1, "succeeded": 1})

        unique_posts, duplicate_stats = deduplicate_posts(raw_posts)
        posts, freshness = validate_fresh_posts(unique_posts)
        summary.update(duplicate_stats)
        summary["freshness"] = freshness
        summary["unique"] = len(posts)
        partial = bool(
            summary.get("failed")
            or summary.get("skipped_capacity")
        )
        state = source_freshness_state(
            configured=True,
            succeeded=bool(summary.get("succeeded")),
            accepted=len(posts),
            rejected=int(freshness.get("rejected") or 0),
            partial=partial,
            newest_at=freshness.get("newest_post"),
        )
        detail = (
            f"{summary.get('succeeded', 0)}/{summary.get('planned', 0)} searches"
            f" · {len(posts):,} dated posts"
            + (
                f" · {len(validation_terms or [])} live publisher terms tested"
                if validation_terms
                else ""
            )
        )
        return posts, summary, _status(state, detail)
    except Exception as exc:
        warnings.append(f"X/Apify: {exc}")
        return [], summary, _status("FAILED", type(exc).__name__)


def _collect_commercial_sources(
    settings: Settings,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], str]:
    if not settings.commercial_sources_enabled:
        return [], [], {}, "NOT CONFIGURED"
    try:
        result = CommercialSourceCollector(
            timeout_seconds=settings.commercial_timeout_seconds,
            max_workers=settings.commercial_max_workers,
            serpapi_api_key=settings.serpapi_api_key,
            serpapi_endpoint=settings.serpapi_endpoint,
        ).collect()
        evidence = list(result.pop("evidence", []))
        rows = enrich_commercial_priorities(score_commercial_evidence(evidence))
        live = int(result.get("publishers_live") or 0)
        partial = int(result.get("publishers_partial") or 0)
        failed = int(result.get("publishers_failed") or 0)
        state = "LIVE" if live and not failed and not partial else "PARTIAL"
        if not live and not partial:
            state = "FAILED"
        for key, detail in (result.get("source_status") or {}).items():
            if str(detail.get("state") or "") in {"FAILED", "PARTIAL"} and not int(
                detail.get("named_trends") or 0
            ):
                errors = detail.get("errors") or []
                warnings.append(
                    f"Commercial source {detail.get('publisher') or key}: "
                    + (
                        str(errors[0])
                        if errors
                        else "the page loaded but yielded no explicit named trends"
                    )
                )
        status = _status(
            state,
            f"{live + partial}/{int(result.get('publishers_requested') or 0)} publishers"
            f" · {int(result.get('publishers_with_evidence') or 0)} with named evidence"
            f" · {int(result.get('named_trends') or 0)} named trends"
            f" · {len(evidence)} evidence rows",
        )
        return evidence, rows, result, status
    except Exception as exc:
        warnings.append(f"Commercial websites: {exc}")
        return [], [], {}, _status("FAILED", type(exc).__name__)


def _collect_instagram_hashtags(
    settings: Settings,
    qualified_trends: list[dict[str, Any]],
    warnings: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    summary: dict[str, Any] = {
        "hashtags_requested": [],
        "hashtags_returned": [],
        "missing_hashtags": [],
        "items_returned": 0,
        "items_normalized": 0,
        "unmatched_items": 0,
        "returned_fields": [],
        "usage_usd": None,
        "privacy_mode": "aggregate metadata; top/latest posts disabled",
    }
    if not settings.instagram_configured:
        return [], summary, "NOT CONFIGURED"
    if not qualified_trends:
        return [], summary, _status("PARTIAL", "no qualified trend hashtags")
    try:
        result = InstagramHashtagAnalyticsConnector(
            settings.apify_token,
            actor_id=settings.apify_instagram_actor_id,
            timeout_seconds=settings.apify_timeout_seconds,
            memory_mb=settings.apify_x_memory_mb,
        ).collect(
            qualified_trends,
            max_terms=settings.instagram_hashtag_max_terms,
            max_total_charge_usd=settings.instagram_max_total_charge_usd,
        )
        rows = list(result.pop("metrics", []))
        summary.update(result)
        returned = len(result.get("hashtags_returned") or [])
        requested = len(result.get("hashtags_requested") or [])
        state = "LIVE" if rows and returned == requested else "PARTIAL"
        if result.get("missing_hashtags"):
            warnings.append(
                "Instagram hashtag metadata missing for: "
                + ", ".join(result["missing_hashtags"])
            )
        if int(result.get("items_returned") or 0) and not rows:
            warnings.append(
                "Instagram returned aggregate dataset rows, but none matched the requested "
                "hashtags. Returned field names: "
                + ", ".join(result.get("returned_fields") or ["not reported"])
            )
        return rows, summary, _status(
            state,
            f"{returned}/{requested} aggregate hashtags"
            f" · {int(result.get('items_returned') or 0)} dataset rows",
        )
    except Exception as exc:
        warnings.append(f"Instagram hashtag metadata: {exc}")
        return [], summary, _status("FAILED", type(exc).__name__)


def _history_presence(
    settings: Settings,
    warnings: list[str],
) -> dict[str, int]:
    if settings.supabase_configured:
        try:
            return _supabase(settings).recent_trend_presence(weeks=4)
        except Exception as exc:
            warnings.append(
                f"Supabase trend history: {exc}. Local snapshot history was used."
            )
    return load_trend_presence(settings.snapshot_path, weeks=4)


def _collect_google(
    settings: Settings,
    *,
    x_rows: list[dict[str, Any]],
    commercial_rows: list[dict[str, Any]],
    existing_snapshot: dict[str, Any] | None,
    warnings: list[str],
    filtered_terms: list[dict[str, str]],
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
    str,
    bool,
]:
    cache, cache_age_hours = _cache_state(existing_snapshot, settings)
    base_validation_plan = build_validation_plan(
        commercial_rows,
        x_rows,
        configured_terms=settings.fashion_terms,
        limit=settings.google_max_terms,
    )
    candidate_fingerprint = candidate_plan_fingerprint(base_validation_plan)
    cache_candidate_match = bool(
        cache
        and str(cache.get("candidate_input_fingerprint") or "")
        == candidate_fingerprint
    )
    fresh_cache = bool(
        cache
        and cache_age_hours is not None
        and cache_age_hours <= max(0, settings.google_cache_hours)
        and cache_candidate_match
    )
    context_series: dict[str, list[dict[str, Any]]] = {}
    recent_series: dict[str, list[dict[str, Any]]] = {}
    related: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    request_count = 0
    request_ceiling = 0
    provider = "unavailable"
    google_fresh = False
    used_cache = False
    status = "NOT CONFIGURED"
    cache_out = dict(cache)
    validation_plan = list(base_validation_plan)

    if not settings.serpapi_configured:
        meta = {
            "provider": provider,
            "market": settings.google_geo,
            "context_timeframe": settings.google_timeframe,
            "discovery_timeframe": settings.google_discovery_timeframe,
            "terms_returned": 0,
            "used_cache": False,
            "cache_age_hours": None,
            "api_requests": 0,
            "api_request_ceiling": 0,
            "attempts": [],
            "candidate_input_fingerprint": candidate_fingerprint,
            "cache_candidate_match": False,
            "validation_plan": validation_plan,
        }
        return [], meta, cache_out, status, google_fresh

    if fresh_cache:
        context_series = dict(cache.get("context_series") or {})
        recent_series = dict(cache.get("recent_series") or {})
        related = list(cache.get("related") or [])
        validation_plan = list(
            cache.get("validation_plan") or base_validation_plan
        )
        provider = str(cache.get("provider") or "SerpApi Google Trends")
        used_cache = True
        google_fresh = True
        status = _status(
            "LIVE",
            f"cache {float(cache_age_hours or 0):.1f}h old · "
            f"{len(context_series)} candidate-matched terms",
        )
    else:
        discovery = GoogleTrendsConnector(
            geo=settings.google_geo,
            timeframe=settings.google_discovery_timeframe,
            category=settings.google_category,
            anchor_term=settings.google_anchor_term,
            provider=settings.google_provider,
            serpapi_api_key=settings.serpapi_api_key,
            serpapi_endpoint=settings.serpapi_endpoint,
            serpapi_timeout_seconds=settings.serpapi_timeout_seconds,
            max_terms=settings.google_max_terms,
            max_discovery_seeds=settings.google_max_discovery_seeds,
            connect_timeout_seconds=settings.google_connect_timeout_seconds,
            read_timeout_seconds=settings.google_read_timeout_seconds,
        )
        context = GoogleTrendsConnector(
            geo=settings.google_geo,
            timeframe=settings.google_timeframe,
            category=settings.google_category,
            anchor_term=settings.google_anchor_term,
            provider=settings.google_provider,
            serpapi_api_key=settings.serpapi_api_key,
            serpapi_endpoint=settings.serpapi_endpoint,
            serpapi_timeout_seconds=settings.serpapi_timeout_seconds,
            max_terms=settings.google_max_terms,
            max_discovery_seeds=settings.google_max_discovery_seeds,
            connect_timeout_seconds=settings.google_connect_timeout_seconds,
            read_timeout_seconds=settings.google_read_timeout_seconds,
        )
        try:
            if settings.enable_google_related_queries:
                discovery_result = discovery.discover_related(
                    DISCOVERY_SEEDS,
                    limit=12,
                )
                related = list(discovery_result.get("related") or [])
                warnings.extend(discovery_result.get("warnings") or [])
                request_count += int(discovery_result.get("requests_used") or 0)
                request_ceiling += int(
                    discovery_result.get("request_ceiling") or 0
                )
                attempts.append(
                    {
                        "stage": "rising related queries",
                        "status": "succeeded",
                        "requests": int(
                            discovery_result.get("requests_used") or 0
                        ),
                    }
                )
        except Exception as exc:
            warnings.append(
                f"Google rising-query discovery: {exc}. Known publisher and social candidates were still validated."
            )
            attempts.append(
                {
                    "stage": "rising related queries",
                    "status": "failed",
                    "detail": str(exc)[:260],
                }
            )

        validation_plan = build_validation_plan(
            commercial_rows,
            x_rows,
            related_rows=related,
            configured_terms=settings.fashion_terms,
            limit=settings.google_max_terms,
        )
        candidates = [str(row.get("name") or "") for row in validation_plan]
        try:
            context_result = context.collect(candidates, discovery_seeds=[])
            context_series = dict(context_result.get("series") or {})
            warnings.extend(context_result.get("warnings") or [])
            request_count += int(context_result.get("requests_used") or 0)
            request_ceiling += int(context_result.get("request_ceiling") or 0)
            provider = str(
                context_result.get("provider") or "SerpApi Google Trends"
            )
            attempts.append(
                {
                    "stage": "90-day validation",
                    "status": "succeeded",
                    "requests": int(context_result.get("requests_used") or 0),
                }
            )
        except Exception as exc:
            attempts.append(
                {
                    "stage": "90-day validation",
                    "status": "failed",
                    "detail": str(exc)[:260],
                }
            )
            warnings.append(f"Google 90-day validation: {exc}")

        try:
            recent_result = discovery.collect(candidates, discovery_seeds=[])
            recent_series = dict(recent_result.get("series") or {})
            warnings.extend(recent_result.get("warnings") or [])
            request_count += int(recent_result.get("requests_used") or 0)
            request_ceiling += int(recent_result.get("request_ceiling") or 0)
            provider = str(
                recent_result.get("provider") or provider or "SerpApi Google Trends"
            )
            attempts.append(
                {
                    "stage": "seven-day acceleration",
                    "status": "succeeded",
                    "requests": int(recent_result.get("requests_used") or 0),
                }
            )
        except Exception as exc:
            attempts.append(
                {
                    "stage": "seven-day acceleration",
                    "status": "failed",
                    "detail": str(exc)[:260],
                }
            )
            warnings.append(f"Google seven-day acceleration: {exc}")

        if context_series:
            google_fresh = True
            state = "LIVE" if recent_series else "PARTIAL"
            status = _status(
                state,
                f"{len(context_series)} 90-day terms"
                + (
                    f" · {len(recent_series)} seven-day terms"
                    if recent_series
                    else " · seven-day acceleration unavailable"
                ),
            )
            cache_out = {
                "schema_version": GOOGLE_CACHE_SCHEMA_VERSION,
                "collected_at": datetime.now(tz=timezone.utc).isoformat(),
                "market": settings.google_geo,
                "context_timeframe": settings.google_timeframe,
                "discovery_timeframe": settings.google_discovery_timeframe,
                "provider": provider,
                "context_series": context_series,
                "recent_series": recent_series,
                "related": related,
                "candidate_input_fingerprint": candidate_fingerprint,
                "validation_plan": validation_plan,
            }
            cache_age_hours = 0.0
        else:
            stale_allowed = bool(
                cache
                and cache_age_hours is not None
                and cache_age_hours
                <= max(1, settings.google_stale_cache_days) * 24
            )
            if stale_allowed:
                allowed_ids = {
                    str(row.get("id") or "") for row in base_validation_plan
                }
                context_series = {
                    term: points
                    for term, points in dict(
                        cache.get("context_series") or {}
                    ).items()
                    if slugify(canonical_name(str(term))) in allowed_ids
                }
                recent_series = {
                    term: points
                    for term, points in dict(
                        cache.get("recent_series") or {}
                    ).items()
                    if slugify(canonical_name(str(term))) in allowed_ids
                }
                related = list(cache.get("related") or [])
                provider = str(cache.get("provider") or "previous live source")
                used_cache = True
                status = _status(
                    "STALE",
                    f"live refresh failed · cache {float(cache_age_hours or 0):.1f}h old",
                )
                warnings.append(
                    "Google Trends live refresh failed. A recent cache is shown as STALE "
                    "and cannot make a trend decision-ready."
                )
            else:
                status = _status("FAILED", "no usable current timeline")

    rows = score_google_windows(
        context_series,
        recent_series,
        audit=filtered_terms,
    )
    for row in rows:
        row["google_fresh"] = google_fresh
        row["google_cache_used"] = used_cache
    meta = {
        "provider": provider,
        "market": settings.google_geo,
        "context_timeframe": settings.google_timeframe,
        "discovery_timeframe": settings.google_discovery_timeframe,
        "terms_returned": len(context_series),
        "recent_terms_returned": len(recent_series),
        "related_queries_returned": len(related),
        "used_cache": used_cache,
        "cache_age_hours": (
            round(float(cache_age_hours), 1)
            if cache_age_hours is not None
            else None
        ),
        "api_requests": request_count,
        "api_request_ceiling": request_ceiling,
        "attempts": attempts,
        "candidate_input_fingerprint": candidate_fingerprint,
        "cache_candidate_match": cache_candidate_match,
        "validation_plan": validation_plan,
        "seed_terms_used": sum(
            bool(row.get("seed_only")) for row in validation_plan
        ),
        "chart_ready_terms": sum(bool(row.get("chart_ready")) for row in rows),
        "flat_or_invalid_terms": sum(
            not bool(row.get("chart_ready")) for row in rows
        ),
    }
    return rows, meta, cache_out, status, google_fresh


def _catalogue(
    settings: Settings,
    *,
    catalog_source: str,
    catalog_products: list[dict[str, Any]] | None,
    existing_snapshot: dict[str, Any] | None,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], str, str, dict[str, Any]]:
    existing_meta = (existing_snapshot or {}).get("meta") or {}
    selected = catalog_source
    if selected == "auto":
        if (
            existing_meta.get("catalogue_source") == "csv"
            and (existing_snapshot or {}).get("products")
        ):
            selected = "csv"
            catalog_products = list(
                (existing_snapshot or {}).get("products") or []
            )
        else:
            selected = "shopify_api"

    actual = selected
    catalogue_meta: dict[str, Any] = {
        "catalogue_filename": "",
        "catalogue_format": "",
        "catalogue_source_rows": 0,
        "catalogue_warnings": [],
    }
    if selected == "csv":
        if (
            catalog_products is None
            and existing_meta.get("catalogue_source") == "csv"
        ):
            catalog_products = list(
                (existing_snapshot or {}).get("products") or []
            )
        products = list(catalog_products or [])
        catalogue_meta = {
            "catalogue_filename": existing_meta.get("catalogue_filename", ""),
            "catalogue_format": existing_meta.get("catalogue_format", ""),
            "catalogue_source_rows": existing_meta.get(
                "catalogue_source_rows", 0
            ),
            "catalogue_warnings": existing_meta.get(
                "catalogue_warnings", []
            ),
        }
        if products:
            return (
                products,
                actual,
                _status("LIVE", f"CSV snapshot · {len(products):,} products"),
                catalogue_meta,
            )
        products = demo_products()
        actual = "demo"
        warnings.append(
            "CSV was selected, but no imported catalogue was available."
        )
        return (
            products,
            actual,
            _status("FAILED", "CSV unavailable · demo catalogue"),
            catalogue_meta,
        )

    if settings.shopify_configured:
        try:
            products = ShopifyConnector(
                shop=settings.shopify_shop,
                client_id=settings.shopify_client_id,
                client_secret=settings.shopify_client_secret,
                admin_access_token=settings.shopify_admin_access_token,
                api_version=settings.shopify_api_version,
                storefront_url=settings.shopify_storefront_url,
            ).fetch_products(max_products=settings.shopify_max_products)
            return (
                products,
                "shopify_api",
                _status("LIVE", f"Shopify API · {len(products):,} products"),
                catalogue_meta,
            )
        except Exception as exc:
            warnings.append(f"Shopify: {exc}")
            return (
                demo_products(),
                "demo",
                _status("FAILED", "Shopify unavailable · demo catalogue"),
                catalogue_meta,
            )
    return (
        demo_products(),
        "demo",
        _status("NOT CONFIGURED", "demo catalogue"),
        catalogue_meta,
    )


def _blog_products(
    trend: dict[str, Any],
    products: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = {str(product.get("id")): product for product in products}
    rows = [
        row
        for row in recommendations
        if str(row.get("trend_id")) == str(trend.get("id"))
    ]
    rows.sort(
        key=lambda row: float(row.get("opportunity_score") or 0),
        reverse=True,
    )
    return [
        lookup[str(row.get("product_id"))]
        for row in rows
        if str(row.get("product_id")) in lookup
    ][:5]


def refresh_snapshot(
    settings: Settings,
    *,
    use_llm: bool = True,
    persist: bool = True,
    catalog_source: str = "auto",
    catalog_products: list[dict[str, Any]] | None = None,
    generate_editorial: bool = False,
) -> dict[str, Any]:
    if catalog_source not in {"auto", "shopify_api", "csv"}:
        raise ValueError(
            "catalog_source must be 'auto', 'shopify_api', or 'csv'."
        )

    warnings: list[str] = []
    filtered_terms: list[dict[str, str]] = []
    source_status: dict[str, str] = {}
    existing_snapshot = load_snapshot(settings.snapshot_path)
    existing_meta = (existing_snapshot or {}).get("meta") or {}

    openai = (
        _openai(settings)
        if settings.openai_configured and use_llm
        else None
    )
    openrouter = (
        _openrouter(settings)
        if settings.openrouter_configured and use_llm and openai is None
        else None
    )
    analyst = openai or openrouter
    extra_openai_usage: list[dict[str, Any]] = []

    commercial_evidence, commercial_rows, commercial_collection, source_status[
        "commercial_websites"
    ] = _collect_commercial_sources(
        settings,
        warnings,
    )
    live_publisher_terms = [
        str(row.get("name") or "")
        for row in commercial_rows[:12]
        if row.get("name")
    ]
    x_posts, x_collection, source_status["x_apify"] = _collect_x(
        settings,
        warnings,
        validation_terms=live_publisher_terms,
    )

    all_posts, combined_duplicate_stats = deduplicate_posts(x_posts)
    all_posts, combined_freshness = validate_fresh_posts(all_posts)

    x_candidates = discover_x_candidates(all_posts, audit=filtered_terms)
    publisher_candidates = [
        {
            "phrase": str(row.get("name") or ""),
            "name": str(row.get("name") or ""),
            "count": max(
                3,
                3 * int(row.get("article_count") or 1)
                + round(float(row.get("validation_priority_score") or 0) / 10),
            ),
        }
        for row in commercial_rows
        if row.get("name")
    ]
    # Publisher discoveries lead semantic grouping. Previously the first 70
    # model inputs were all X phrases, so publisher aliases were never seen.
    candidates = [*publisher_candidates, *x_candidates]
    maximum_clusters = max(35, min(180, len(candidates)))
    semantic_clusters = build_topic_clusters(
        candidates,
        max_clusters=maximum_clusters,
        audit=filtered_terms,
    )
    semantic_error = ""
    if analyst is not None and candidates:
        try:
            model_candidates = [
                *publisher_candidates[:45],
                *x_candidates[:25],
            ]
            model_clusters = analyst.cluster_topic_phrases(model_candidates)
            semantic_clusters = build_topic_clusters(
                candidates,
                llm_clusters=model_clusters,
                max_clusters=maximum_clusters,
                audit=filtered_terms,
            )
        except Exception as exc:
            semantic_error = str(exc)
            warnings.append(
                f"Model semantic grouping: {exc}. Local grouping was used."
            )

    raw_commercial_trend_count = len(commercial_rows)
    commercial_evidence = consolidate_commercial_evidence(
        commercial_evidence,
        semantic_clusters,
    )
    commercial_rows = enrich_commercial_priorities(
        score_commercial_evidence(commercial_evidence)
    )
    commercial_collection["canonical_trends"] = len(commercial_rows)
    commercial_collection["aliases_merged"] = max(
        0,
        raw_commercial_trend_count - len(commercial_rows),
    )

    social_rows = extract_x_signals(
        all_posts,
        clusters=semantic_clusters,
        historical_presence=_history_presence(settings, warnings),
        audit=filtered_terms,
    )
    google_rows, google_meta, google_cache, source_status[
        "google_trends"
    ], google_fresh = _collect_google(
        settings,
        x_rows=social_rows,
        commercial_rows=commercial_rows,
        existing_snapshot=existing_snapshot,
        warnings=warnings,
        filtered_terms=filtered_terms,
    )
    validation_plan = list(google_meta.get("validation_plan") or [])
    qualified_for_instagram = select_instagram_targets(
        validation_plan,
        google_rows=google_rows,
        commercial_rows=commercial_rows,
        social_rows=social_rows,
        limit=settings.instagram_hashtag_max_terms,
    )
    instagram_rows, instagram_collection, source_status[
        "instagram_hashtags"
    ] = _collect_instagram_hashtags(
        settings,
        qualified_for_instagram,
        warnings,
    )
    trends = merge_trend_signals(
        google_rows,
        social_rows,
        commercial_rows=commercial_rows,
        instagram_rows=instagram_rows,
        audit=filtered_terms,
    )
    if openai is not None and trends:
        try:
            trends = openai.review_evidence(trends)
        except Exception as exc:
            warnings.append(
                f"Luna evidence relevance review: {exc}. Deterministic source filters were retained."
            )
    if not google_fresh:
        for trend in trends:
            trend["google_stale"] = trend.get("google_score") is not None

    # Every public number is now calculated from stored evidence. The legacy
    # merge above remains useful for alias alignment and backward-compatible
    # fields; this v2 pass owns confidence, completeness, caps and ordering.
    trends = upgrade_trends_to_v2(trends)

    if analyst is not None and trends:
        try:
            trends = analyst.enrich_trends(trends)
            analyst_key = "openai" if openai is not None else "openrouter"
            analyst_model = (
                settings.openai_sol_model
                if openai is not None
                else settings.openrouter_model
            )
            source_status[analyst_key] = _status(
                "LIVE",
                analyst_model
                + (
                    " · local semantic fallback"
                    if semantic_error
                    else " · evidence-locked synthesis"
                ),
            )
        except Exception as exc:
            analyst_key = "openai" if openai is not None else "openrouter"
            source_status[analyst_key] = _status(
                "PARTIAL",
                "deterministic trend fields retained",
            )
            warnings.append(f"Model synthesis: {exc}")
    else:
        source_status["openai"] = (
            "NOT CONFIGURED"
            if not settings.openai_configured
            else _status("STANDBY", "disabled for this refresh")
        )
        if not settings.openai_configured:
            source_status["openrouter"] = (
                "NOT CONFIGURED"
                if not settings.openrouter_configured
                else _status("STANDBY", "disabled for this refresh")
            )
    if openai is not None:
        source_status["openrouter"] = _status(
            "STANDBY",
            "not required · OpenAI used",
        )

    fallback_kind = ""
    if not trends:
        prior_trends = list((existing_snapshot or {}).get("trends") or [])
        if prior_trends:
            trends = [
                {
                    **trend,
                    "decision_ready": False,
                    "confidence": "Exploratory",
                    "is_stale": True,
                }
                for trend in prior_trends
            ]
            fallback_kind = "stale"
            source_status["trend_fallback"] = _status(
                "STALE",
                "previous aggregate snapshot",
            )
            warnings.append(
                "No current cross-source rows were available. The prior radar is "
                "shown only as a stale watchlist."
            )
        else:
            trends = [
                {
                    **trend,
                    "decision_ready": False,
                    "confidence": "Exploratory",
                    "is_demo": True,
                }
                for trend in demo_trends()
            ]
            fallback_kind = "demo"
            source_status["trend_fallback"] = _status(
                "PARTIAL",
                "illustrative data",
            )

    if trends and not all(
        isinstance(trend.get("score_breakdown"), dict) for trend in trends
    ):
        trends = upgrade_trends_to_v2(trends)

    trends = annotate_discovery_provenance(
        trends,
        validation_plan,
        commercial_rows=commercial_rows,
        social_rows=social_rows,
        fallback_kind=fallback_kind,
    )

    products, actual_catalog_source, source_status[
        "shopify"
    ], catalogue_meta = _catalogue(
        settings,
        catalog_source=catalog_source,
        catalog_products=catalog_products,
        existing_snapshot=existing_snapshot,
        warnings=warnings,
    )
    recommendations = match_products(trends, products)
    trends, recommendations = apply_hula_opportunity_scores(
        trends,
        recommendations,
        products,
    )

    editorial = dict((existing_snapshot or {}).get("editorial") or {})
    if generate_editorial:
        ready = [trend for trend in trends if trend.get("decision_ready")]
        if (settings.openai_configured or settings.gemini_configured) and ready:
            lead = ready[0]
            selected_products = _blog_products(
                lead,
                products,
                recommendations,
            )
            if selected_products:
                try:
                    blog_writer = openai or (
                        _openai(settings)
                        if settings.openai_configured
                        else _gemini(settings)
                    )
                    blog = generate_researched_blog(
                        blog_writer,
                        lead,
                        selected_products,
                        reason="This week's strongest product trend",
                        stores=["Online", "HULA Soho", "The Hub"],
                    )
                    if (
                        isinstance(blog_writer, OpenAIResponsesConnector)
                        and blog_writer is not openai
                    ):
                        extra_openai_usage.extend(blog_writer.usage_log)
                    editorial["latest_blog"] = blog
                    writer_key = "openai" if settings.openai_configured else "gemini"
                    writer_model = (
                        settings.openai_sol_model
                        if settings.openai_configured
                        else settings.gemini_model
                    )
                    source_status[writer_key] = _status(
                        "LIVE",
                        f"{writer_model} · evidence-locked Wednesday draft",
                    )
                except Exception as exc:
                    writer_key = "openai" if settings.openai_configured else "gemini"
                    source_status[writer_key] = _status(
                        "FAILED",
                        "previous draft retained",
                    )
                    warnings.append(f"Evidence-locked Wednesday blog: {exc}")
            else:
                source_status["gemini"] = _status(
                    "PARTIAL",
                    "no matched products for an automatic draft",
                )
        elif not settings.openai_configured and not settings.gemini_configured:
            source_status["gemini"] = "NOT CONFIGURED"
        else:
            source_status["gemini"] = _status(
                "PARTIAL",
                "no decision-ready trend",
            )
    else:
        writer_configured = settings.openai_configured or settings.gemini_configured
        writer_key = "openai" if settings.openai_configured else "gemini"
        source_status[writer_key] = (
            _status("LIVE", "configured · evidence-locked generation available")
            if writer_configured
            else "NOT CONFIGURED"
        )

    if settings.supabase_configured:
        source_status["supabase"] = _status(
            "LIVE",
            "configured · aggregate history ready",
        )
    else:
        source_status["supabase"] = "NOT CONFIGURED"

    live_signal = sum(
        str(source_status.get(key) or "").startswith(("LIVE", "PARTIAL"))
        for key in (
            "google_trends",
            "x_apify",
            "commercial_websites",
            "instagram_hashtags",
        )
    ) >= 2
    if fallback_kind == "stale":
        mode = "stale"
    elif fallback_kind == "demo":
        mode = "demo"
    elif (
        live_signal
        and actual_catalog_source == "shopify_api"
        and source_status["shopify"].startswith("LIVE")
    ):
        mode = "live"
    else:
        mode = "hybrid"

    filtered_audit = consolidate_filter_audit(filtered_terms)
    generated_at = datetime.now(tz=timezone.utc).isoformat()
    snapshot = {
        "meta": {
            "generated_at": generated_at,
            "mode": mode,
            "region": settings.google_geo,
            "catalogue_source": actual_catalog_source,
            **catalogue_meta,
            "source_status": source_status,
            "google_trends": google_meta,
            "x_listening": x_collection,
            "commercial_collection": commercial_collection,
            "commercial_evidence": commercial_evidence,
            "commercial_discoveries": commercial_rows,
            "validation_plan": validation_plan,
            "provenance_summary": {
                "live_discovered": sum(
                    bool(trend.get("live_discovered")) for trend in trends
                ),
                "seed_only": sum(bool(trend.get("seed_only")) for trend in trends),
                "historical": sum(
                    trend.get("primary_discovery_origin") == "historical"
                    for trend in trends
                ),
                "demo": sum(
                    trend.get("primary_discovery_origin") == "demo"
                    for trend in trends
                ),
            },
            "instagram_hashtag_collection": instagram_collection,
            "combined_social_freshness": {
                **combined_freshness,
                **combined_duplicate_stats,
            },
            "filtered_terms": filtered_audit,
            "raw_counts": {
                "x_posts_collected": int(x_collection.get("collected") or 0),
                "x_posts_accepted": len(x_posts),
                "commercial_evidence_rows": len(commercial_evidence),
                "commercial_trends": len(commercial_rows),
                "commercial_named_trends": int(
                    commercial_collection.get("named_trends") or 0
                ),
                "commercial_publishers_live": int(
                    commercial_collection.get("publishers_live") or 0
                ),
                "instagram_hashtags_returned": len(instagram_rows),
                "social_posts_aggregated": len(all_posts),
                "social_duplicates_removed": int(
                    combined_duplicate_stats.get("duplicates_removed") or 0
                ),
                "social_topic_clusters": len(social_rows),
                "google_terms": len(google_rows),
                "google_chart_ready_terms": int(
                    google_meta.get("chart_ready_terms") or 0
                ),
                "validation_candidates": len(validation_plan),
                "configured_seed_candidates": sum(
                    bool(row.get("seed_only")) for row in validation_plan
                ),
                "live_discovered_trends": sum(
                    bool(trend.get("live_discovered")) for trend in trends
                ),
                "filtered_generic_terms": len(filtered_audit),
                "shopify_products": len(products),
                "recommendations": len(recommendations),
            },
            "warnings": warnings,
            "openai_usage": [
                *(list(openai.usage_log) if openai is not None else []),
                *extra_openai_usage,
            ],
            "methodology_version": METHODOLOGY_VERSION,
            "discovery_pipeline_version": "3.0",
            "quality_filter_version": "4.0",
            "google_display_schema_version": "2.0",
            "privacy": (
                "Raw X posts are not persisted. Instagram is queried only for aggregate "
                "hashtag counts with top/latest post collection disabled; no Instagram "
                "captions, accounts or images enter the pipeline. Commercial evidence "
                "stores only public publisher titles, trend-labelled headings, dates and "
                "URLs. Writing models receive only stored evidence and selected public "
                "product metadata; live-search grounding is not used for the blog. "
                "No customers, orders or payments are accessed."
            ),
        },
        "analysis_period": analysis_period(
            datetime.now(tz=timezone.utc),
            geography=settings.google_geo,
        ),
        "methodology_version": METHODOLOGY_VERSION,
        "google_cache": google_cache,
        "trends": trends,
        "products": products,
        "recommendations": recommendations,
        "editorial": editorial,
        "excluded_candidates": [
            {
                "candidate": str(row.get("term") or row.get("candidate") or ""),
                "reason": normalise_exclusion_reason(row.get("reason")),
            }
            for row in filtered_audit
        ],
    }

    if persist:
        save_snapshot(snapshot, settings.snapshot_path)
        if settings.supabase_configured:
            try:
                remote = _supabase(settings)
                source_status["supabase"] = _status(
                    "LIVE",
                    "weekly aggregate saved",
                )
                snapshot["meta"]["source_status"] = source_status
                remote.save_snapshot(snapshot)
                latest_blog = editorial.get("latest_blog")
                if generate_editorial and isinstance(latest_blog, dict):
                    remote.save_blog(latest_blog)
            except Exception as exc:
                source_status["supabase"] = _status(
                    "FAILED",
                    type(exc).__name__,
                )
                warnings.append(f"Supabase persistence: {exc}")
            snapshot["meta"]["source_status"] = source_status
            snapshot["meta"]["warnings"] = warnings
            save_snapshot(snapshot, settings.snapshot_path)
    return snapshot
