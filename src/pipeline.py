from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.analysis.freshness import (
    parse_utc,
    source_freshness_state,
    validate_fresh_posts,
)
from src.analysis.listening import build_listening_plan, deduplicate_posts
from src.analysis.matching import match_products
from src.analysis.trends import (
    build_topic_clusters,
    consolidate_filter_audit,
    discover_x_candidates,
    extract_x_signals,
    generic_trend_reason,
    merge_trend_signals,
    score_google_windows,
)
from src.config import Settings
from src.connectors.apify_instagram import ApifyInstagramConnector
from src.connectors.apify_x import ApifyXConnector
from src.connectors.gemini_research import GeminiResearchConnector
from src.connectors.google_trends import GoogleTrendsConnector
from src.connectors.openrouter import OpenRouterConnector
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


def _openrouter(settings: Settings) -> OpenRouterConnector:
    return OpenRouterConnector(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        api_url=settings.openrouter_api_url,
        timeout=settings.openrouter_timeout,
        site_url=settings.openrouter_site_url,
        app_name=settings.openrouter_app_name,
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
            or freshness.get("rejected")
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
        )
        return posts, summary, _status(state, detail)
    except Exception as exc:
        warnings.append(f"X/Apify: {exc}")
        return [], summary, _status("FAILED", type(exc).__name__)


def _collect_instagram(
    settings: Settings,
    warnings: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    summary: dict[str, Any] = {
        "requested_profiles": settings.instagram_accounts,
        "returned_profiles": [],
        "missing_profiles": [],
        "profile_counts": {},
        "items_returned": 0,
        "items_accepted": 0,
        "freshness": {},
        "usage_usd": None,
    }
    if not settings.instagram_configured:
        return [], summary, "NOT CONFIGURED"
    try:
        result = ApifyInstagramConnector(
            settings.apify_token,
            actor_id=settings.apify_instagram_actor_id,
            timeout_seconds=settings.apify_timeout_seconds,
            memory_mb=settings.apify_x_memory_mb,
        ).collect(
            settings.instagram_accounts,
            account_weights=settings.instagram_account_weights,
            results_per_profile=settings.instagram_results_per_profile,
            max_total_charge_usd=settings.instagram_max_total_charge_usd,
        )
        posts = list(result.pop("posts", []))
        summary.update(result)
        freshness = result.get("freshness") or {}
        partial = bool(
            result.get("missing_profiles")
            or freshness.get("rejected")
            or not posts
        )
        state = source_freshness_state(
            configured=True,
            succeeded=True,
            accepted=len(posts),
            rejected=int(freshness.get("rejected") or 0),
            partial=partial,
            newest_at=freshness.get("newest_post"),
        )
        detail = (
            f"{len(result.get('returned_profiles') or [])}/"
            f"{len(settings.instagram_accounts)} profiles · {len(posts):,} dated posts"
        )
        if result.get("missing_profiles"):
            warnings.append(
                "Instagram profiles with no current-window results: "
                + ", ".join(result["missing_profiles"])
            )
        return posts, summary, _status(state, detail)
    except Exception as exc:
        warnings.append(f"Instagram/Apify: {exc}")
        return [], summary, _status("FAILED", type(exc).__name__)


def _apply_visual_terms(
    posts: list[dict[str, Any]],
    connector: OpenRouterConnector | None,
    *,
    max_posts: int,
    warnings: list[str],
) -> int:
    if connector is None or not posts:
        return 0
    try:
        terms_by_post = connector.extract_instagram_visual_terms(
            posts,
            max_posts=max_posts,
        )
        enriched = 0
        for post in posts:
            terms = terms_by_post.get(str(post.get("post_hash"))) or []
            if not terms:
                continue
            post["visual_terms"] = terms
            post["text"] = (
                f"{post.get('text', '')}\nVisual trend labels: "
                + ", ".join(terms)
            )
            enriched += 1
        return enriched
    except Exception as exc:
        warnings.append(
            f"Instagram visual reading: {exc}. Caption evidence was retained."
        )
        return 0


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


def _clean_candidate_terms(
    terms: list[str],
    *,
    limit: int,
    filtered_terms: list[dict[str, str]],
    source: str,
) -> list[str]:
    output: list[str] = []
    for raw in terms:
        term = str(raw or "").strip()
        if not term:
            continue
        reason = generic_trend_reason(term)
        if reason:
            filtered_terms.append(
                {"term": term, "source": source, "reason": reason}
            )
            continue
        if term.casefold() not in {value.casefold() for value in output}:
            output.append(term)
        if len(output) >= max(1, limit):
            break
    return output


def _collect_google(
    settings: Settings,
    *,
    x_rows: list[dict[str, Any]],
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
    fresh_cache = bool(
        cache
        and cache_age_hours is not None
        and cache_age_hours <= max(0, settings.google_cache_hours)
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
        }
        return [], meta, cache_out, status, google_fresh

    if fresh_cache:
        context_series = dict(cache.get("context_series") or {})
        recent_series = dict(cache.get("recent_series") or {})
        related = list(cache.get("related") or [])
        provider = str(cache.get("provider") or "SerpApi Google Trends")
        used_cache = True
        google_fresh = True
        status = _status(
            "LIVE",
            f"cache {float(cache_age_hours or 0):.1f}h old · "
            f"{len(context_series)} validated terms",
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
                f"Google rising-query discovery: {exc}. Known social candidates were still validated."
            )
            attempts.append(
                {
                    "stage": "rising related queries",
                    "status": "failed",
                    "detail": str(exc)[:260],
                }
            )

        related_terms = [
            str(row.get("query") or "")
            for row in related
            if isinstance(row, dict)
        ]
        initial_terms = [
            *(str(row.get("name") or "") for row in x_rows),
            *related_terms,
            *settings.fashion_terms,
        ]
        candidates = _clean_candidate_terms(
            initial_terms,
            limit=settings.google_max_terms,
            filtered_terms=filtered_terms,
            source="Google validation candidate",
        )
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
                    "stage": "one-month validation",
                    "status": "succeeded",
                    "requests": int(context_result.get("requests_used") or 0),
                }
            )
        except Exception as exc:
            attempts.append(
                {
                    "stage": "one-month validation",
                    "status": "failed",
                    "detail": str(exc)[:260],
                }
            )
            warnings.append(f"Google one-month validation: {exc}")

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
                f"{len(context_series)} one-month terms"
                + (
                    f" · {len(recent_series)} seven-day terms"
                    if recent_series
                    else " · seven-day acceleration unavailable"
                ),
            )
            cache_out = {
                "collected_at": datetime.now(tz=timezone.utc).isoformat(),
                "market": settings.google_geo,
                "context_timeframe": settings.google_timeframe,
                "discovery_timeframe": settings.google_discovery_timeframe,
                "provider": provider,
                "context_series": context_series,
                "recent_series": recent_series,
                "related": related,
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
                context_series = dict(cache.get("context_series") or {})
                recent_series = dict(cache.get("recent_series") or {})
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

    openrouter = (
        _openrouter(settings)
        if settings.openrouter_configured and use_llm
        else None
    )

    x_posts, x_collection, source_status["x_apify"] = _collect_x(
        settings,
        warnings,
    )
    instagram_posts, instagram_collection, source_status[
        "instagram"
    ] = _collect_instagram(settings, warnings)
    visual_posts_enriched = _apply_visual_terms(
        instagram_posts,
        openrouter,
        max_posts=settings.instagram_visual_max_posts,
        warnings=warnings,
    )

    all_posts, combined_duplicate_stats = deduplicate_posts(
        [*x_posts, *instagram_posts]
    )
    all_posts, combined_freshness = validate_fresh_posts(all_posts)

    candidates = discover_x_candidates(all_posts, audit=filtered_terms)
    semantic_clusters = build_topic_clusters(
        candidates,
        audit=filtered_terms,
    )
    semantic_error = ""
    if openrouter is not None and candidates:
        try:
            model_clusters = openrouter.cluster_topic_phrases(candidates)
            semantic_clusters = build_topic_clusters(
                candidates,
                llm_clusters=model_clusters,
                audit=filtered_terms,
            )
        except Exception as exc:
            semantic_error = str(exc)
            warnings.append(
                f"OpenRouter semantic grouping: {exc}. Local grouping was used."
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
        existing_snapshot=existing_snapshot,
        warnings=warnings,
        filtered_terms=filtered_terms,
    )
    trends = merge_trend_signals(
        google_rows,
        social_rows,
        audit=filtered_terms,
    )
    if not google_fresh:
        for trend in trends:
            trend["decision_ready"] = False
            trend["confidence"] = "Exploratory"
            trend["google_stale"] = trend.get("google_score") is not None

    if openrouter is not None and trends:
        try:
            trends = openrouter.enrich_trends(trends)
            source_status["openrouter"] = _status(
                "LIVE",
                settings.openrouter_model
                + (
                    " · local semantic fallback"
                    if semantic_error
                    else " · semantic + visual enrichment"
                ),
            )
        except Exception as exc:
            source_status["openrouter"] = _status(
                "PARTIAL",
                "deterministic trend fields retained",
            )
            warnings.append(f"OpenRouter enrichment: {exc}")
    else:
        source_status["openrouter"] = (
            "NOT CONFIGURED"
            if not settings.openrouter_configured
            else _status("PARTIAL", "disabled for this refresh")
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

    editorial = dict((existing_snapshot or {}).get("editorial") or {})
    if generate_editorial:
        ready = [trend for trend in trends if trend.get("decision_ready")]
        if settings.gemini_configured and ready:
            lead = ready[0]
            selected_products = _blog_products(
                lead,
                products,
                recommendations,
            )
            if selected_products:
                try:
                    blog = generate_researched_blog(
                        _gemini(settings),
                        lead,
                        selected_products,
                        reason="This week's strongest product trend",
                        stores=["Online", "HULA Soho", "The Hub"],
                    )
                    editorial["latest_blog"] = blog
                    source_status["gemini"] = _status(
                        "LIVE",
                        f"{settings.gemini_model} · grounded Wednesday draft",
                    )
                except Exception as exc:
                    source_status["gemini"] = _status(
                        "FAILED",
                        "previous draft retained",
                    )
                    warnings.append(f"Gemini Wednesday blog: {exc}")
            else:
                source_status["gemini"] = _status(
                    "PARTIAL",
                    "no matched products for an automatic draft",
                )
        elif not settings.gemini_configured:
            source_status["gemini"] = "NOT CONFIGURED"
        else:
            source_status["gemini"] = _status(
                "PARTIAL",
                "no decision-ready trend",
            )
    else:
        source_status["gemini"] = (
            _status("LIVE", "configured · generation available on demand")
            if settings.gemini_configured
            else "NOT CONFIGURED"
        )

    if settings.supabase_configured:
        source_status["supabase"] = _status(
            "LIVE",
            "configured · aggregate history ready",
        )
    else:
        source_status["supabase"] = "NOT CONFIGURED"

    live_signal = (
        source_status["google_trends"].startswith(("LIVE", "PARTIAL"))
        and (
            source_status["x_apify"].startswith(("LIVE", "PARTIAL"))
            or source_status["instagram"].startswith(("LIVE", "PARTIAL"))
        )
    )
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
            "instagram_collection": {
                **instagram_collection,
                "visual_posts_enriched": visual_posts_enriched,
            },
            "combined_social_freshness": {
                **combined_freshness,
                **combined_duplicate_stats,
            },
            "filtered_terms": filtered_audit,
            "raw_counts": {
                "x_posts_collected": int(x_collection.get("collected") or 0),
                "x_posts_accepted": len(x_posts),
                "instagram_posts_returned": int(
                    instagram_collection.get("items_returned") or 0
                ),
                "instagram_posts_accepted": len(instagram_posts),
                "instagram_profiles_returned": len(
                    instagram_collection.get("returned_profiles") or []
                ),
                "social_posts_aggregated": len(all_posts),
                "social_duplicates_removed": int(
                    combined_duplicate_stats.get("duplicates_removed") or 0
                ),
                "social_topic_clusters": len(social_rows),
                "google_terms": len(google_rows),
                "google_chart_ready_terms": int(
                    google_meta.get("chart_ready_terms") or 0
                ),
                "filtered_generic_terms": len(filtered_audit),
                "shopify_products": len(products),
                "recommendations": len(recommendations),
            },
            "warnings": warnings,
            "methodology_version": "0.5",
            "quality_filter_version": "3.0",
            "privacy": (
                "Raw X and Instagram posts are not persisted. Public Instagram "
                "captions and a capped set of public post images may be sent to Qwen "
                "for visual taxonomy; Gemini receives only public trend and selected "
                "product metadata. No customers, orders or payments are accessed."
            ),
        },
        "google_cache": google_cache,
        "trends": trends,
        "products": products,
        "recommendations": recommendations,
        "editorial": editorial,
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
