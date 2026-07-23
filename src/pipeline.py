from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.analysis.listening import build_listening_plan, deduplicate_posts
from src.analysis.matching import match_products
from src.analysis.trends import (
    build_topic_clusters,
    consolidate_filter_audit,
    discover_x_candidates,
    extract_x_signals,
    generic_trend_reason,
    merge_trend_signals,
    score_google_series,
)
from src.config import Settings
from src.connectors.apify_x import ApifyXConnector
from src.connectors.google_trends import GoogleTrendsConnector
from src.connectors.openrouter import OpenRouterConnector
from src.connectors.shopify import ShopifyConnector
from src.demo_data import demo_products, demo_trends
from src.storage import load_snapshot, load_trend_presence, save_snapshot


DISCOVERY_SEEDS = [
    "fashion trends",
    "designer bags",
    "shoe trends",
    "fashion colours",
    "vintage fashion",
    "outfit ideas",
]


def _parse_utc(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _google_cache_state(
    snapshot: dict[str, Any] | None,
    settings: Settings,
) -> tuple[dict[str, Any], float | None]:
    cache = dict((snapshot or {}).get("google_cache") or {})
    if (
        str(cache.get("market") or "").upper() != settings.google_geo.upper()
        or str(cache.get("timeframe") or "") != settings.google_timeframe
        or not isinstance(cache.get("series"), dict)
        or not cache.get("series")
    ):
        return {}, None
    collected = _parse_utc(cache.get("collected_at"))
    if collected is None:
        return {}, None
    age_hours = max(
        0.0,
        (datetime.now(tz=timezone.utc) - collected).total_seconds() / 3600,
    )
    return cache, age_hours


def _openrouter(settings: Settings) -> OpenRouterConnector:
    return OpenRouterConnector(
        api_key=settings.openrouter_api_key,
        model=settings.openrouter_model,
        api_url=settings.openrouter_api_url,
        timeout=settings.openrouter_timeout,
        site_url=settings.openrouter_site_url,
        app_name=settings.openrouter_app_name,
    )


def refresh_snapshot(
    settings: Settings,
    *,
    use_llm: bool = True,
    persist: bool = True,
    catalog_source: str = "auto",
    catalog_products: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if catalog_source not in {"auto", "shopify_api", "csv"}:
        raise ValueError("catalog_source must be 'auto', 'shopify_api', or 'csv'.")
    warnings: list[str] = []
    filtered_terms: list[dict[str, str]] = []
    source_status: dict[str, str] = {}
    existing_snapshot = load_snapshot(settings.snapshot_path)
    existing_meta = (existing_snapshot or {}).get("meta") or {}

    posts: list[dict[str, Any]] = []
    x_collection: dict[str, Any] = {
        "mode": settings.apify_x_listening_mode,
        "planned": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped_capacity": 0,
        "collected": 0,
        "unique": 0,
        "duplicates_removed": 0,
        "usage_usd": None,
        "semantic_clustering": "local fashion ontology + lexical similarity",
        "expert_accounts": len(settings.x_expert_accounts),
    }
    if settings.apify_configured:
        try:
            apify = ApifyXConnector(
                settings.apify_token,
                settings.apify_x_task_id,
                timeout_seconds=settings.apify_timeout_seconds,
                memory_mb=settings.apify_x_memory_mb,
            )
            if settings.topic_plan_enabled:
                listening_plan = build_listening_plan(
                    language=settings.x_language,
                    results_per_query=settings.apify_results_per_query,
                    expert_results_per_query=settings.apify_expert_results_per_query,
                    expert_accounts=settings.x_expert_accounts,
                )
                result = apify.run_listening_plan(
                    listening_plan,
                    base_task_input=settings.apify_x_task_input,
                    max_total_charge_usd=settings.apify_max_total_charge_usd,
                )
                posts, duplicate_stats = deduplicate_posts(result["posts"])
                x_collection.update(
                    {
                        "planned": result["planned"],
                        "succeeded": result["succeeded"],
                        "failed": result["failed"],
                        "skipped_capacity": result.get("skipped_capacity", 0),
                        "collected": duplicate_stats["collected"],
                        "unique": duplicate_stats["unique"],
                        "duplicates_removed": duplicate_stats["duplicates_removed"],
                        "usage_usd": result.get("usage_usd"),
                    }
                )
                warnings.extend(result.get("warnings") or [])
                if result["succeeded"]:
                    state = (
                        "live"
                        if not result["failed"] and not result.get("skipped_capacity")
                        else "partial"
                    )
                    source_status["x_apify"] = (
                        f"{state} · {result['succeeded']}/{result['planned']} searches · "
                        f"{len(posts):,} unique posts"
                    )
                elif result.get("skipped_capacity"):
                    source_status["x_apify"] = (
                        f"blocked · Apify memory full · 0/{result['planned']} searches"
                    )
                else:
                    source_status["x_apify"] = "failed · all planned searches failed"
            else:
                raw_posts = apify.run(settings.apify_x_task_input)
                posts, duplicate_stats = deduplicate_posts(raw_posts)
                x_collection.update(
                    {
                        "planned": 1,
                        "succeeded": 1,
                        "collected": duplicate_stats["collected"],
                        "unique": duplicate_stats["unique"],
                        "duplicates_removed": duplicate_stats["duplicates_removed"],
                    }
                )
                source_status["x_apify"] = f"live · saved-task input · {len(posts):,} unique posts"
        except Exception as exc:
            source_status["x_apify"] = "failed"
            warnings.append(f"X/Apify: {exc}")
    else:
        source_status["x_apify"] = "not configured"

    candidates = discover_x_candidates(posts, audit=filtered_terms)
    semantic_clusters = build_topic_clusters(candidates, audit=filtered_terms)
    semantic_error = ""
    openrouter = _openrouter(settings) if settings.openrouter_configured and use_llm else None
    if openrouter is not None and candidates:
        try:
            model_clusters = openrouter.cluster_topic_phrases(candidates)
            semantic_clusters = build_topic_clusters(
                candidates,
                llm_clusters=model_clusters,
                audit=filtered_terms,
            )
            x_collection["semantic_clustering"] = "Qwen semantic grouping + local validation"
        except Exception as exc:
            semantic_error = str(exc)
            warnings.append(
                "OpenRouter semantic grouping: "
                f"{exc}. The local fashion ontology and lexical clustering were used."
            )
    x_rows = extract_x_signals(
        posts,
        clusters=semantic_clusters,
        historical_presence=load_trend_presence(settings.snapshot_path, weeks=4),
        audit=filtered_terms,
    )

    trends_connector = GoogleTrendsConnector(
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
    initial_candidates = [
        *(row.get("name", "") for row in x_rows[:6]),
        *settings.fashion_terms,
    ]
    initial_candidates = [
        str(term).strip()
        for term in dict.fromkeys(initial_candidates)
        if str(term).strip()
    ]
    candidates: list[str] = []
    for term in initial_candidates:
        reason = generic_trend_reason(term)
        if reason:
            filtered_terms.append(
                {
                    "term": term,
                    "source": "Google candidate",
                    "reason": reason,
                }
            )
        else:
            candidates.append(term)

    google_result: dict[str, Any] = {}
    google_series: dict[str, list[dict[str, Any]]] = {}
    related: list[dict[str, Any]] = []
    google_cache, google_cache_age_hours = _google_cache_state(
        existing_snapshot,
        settings,
    )
    google_cache_out = dict(google_cache)
    used_google_cache = False
    collected_google_live = False
    fresh_cache = bool(
        google_cache
        and google_cache_age_hours is not None
        and google_cache_age_hours <= max(0, settings.google_cache_hours)
    )

    if fresh_cache:
        used_google_cache = True
        google_series = dict(google_cache.get("series") or {})
        related = list(google_cache.get("related") or [])
        original_provider = str(google_cache.get("provider") or "live source")
        google_result = {
            "provider": f"cache · {original_provider}",
            "usage_usd": None,
            "attempts": [{"provider": "cache", "status": "succeeded"}],
            "cache_age_hours": round(float(google_cache_age_hours or 0), 1),
            "memory_mb": 0,
        }
        source_status["google_trends"] = (
            f"cached live · {settings.google_geo} · {len(google_series)} terms · "
            f"{float(google_cache_age_hours or 0):.1f}h old"
        )
    else:
        try:
            google_result = trends_connector.collect(
                candidates[: max(2, settings.google_max_terms)],
                discovery_seeds=(
                    DISCOVERY_SEEDS if settings.enable_google_related_queries else []
                ),
            )
            google_series = dict(google_result.get("series") or {})
            related = list(google_result.get("related") or [])
            warnings.extend(google_result.get("warnings") or [])
            provider = str(google_result.get("provider") or "unknown route")
            collected_google_live = bool(google_series)
            source_status["google_trends"] = (
                f"live · {provider} · {settings.google_geo} · {len(google_series)} terms"
                if google_series
                else f"no data · {provider} · {settings.google_geo}"
            )
        except Exception as exc:
            stale_cache_allowed = bool(
                google_cache
                and google_cache_age_hours is not None
                and google_cache_age_hours
                <= max(1, settings.google_stale_cache_days) * 24
            )
            if stale_cache_allowed:
                used_google_cache = True
                google_series = dict(google_cache.get("series") or {})
                related = list(google_cache.get("related") or [])
                original_provider = str(
                    google_cache.get("provider") or "previous live source"
                )
                google_result = {
                    "provider": f"stale cache · {original_provider}",
                    "usage_usd": None,
                    "attempts": [
                        {"provider": "live routes", "status": "failed"},
                        {"provider": "cache", "status": "succeeded"},
                    ],
                    "cache_age_hours": round(float(google_cache_age_hours or 0), 1),
                    "memory_mb": 0,
                }
                source_status["google_trends"] = (
                    f"cached after live failure · {settings.google_geo} · "
                    f"{len(google_series)} terms · {float(google_cache_age_hours or 0):.1f}h old"
                )
                warnings.append(
                    f"Google Trends ({settings.google_geo}) live refresh failed: {exc} "
                    "The most recent saved live Google Trends data was retained instead of using demo data."
                )
            else:
                source_status["google_trends"] = f"failed · {settings.google_geo}"
                warnings.append(f"Google Trends ({settings.google_geo}): {exc}")

    validated_related: list[str] = []
    for row in related[:30]:
        term = str(row.get("query") or "").strip()
        reason = generic_trend_reason(term)
        if reason:
            filtered_terms.append(
                {
                    "term": term,
                    "source": "Google related query",
                    "reason": reason,
                }
            )
        elif term and term not in candidates and term not in validated_related:
            validated_related.append(term)

    if (
        collected_google_live
        and google_series
        and validated_related
        and settings.google_related_validation_terms > 0
    ):
        try:
            expansion = trends_connector.collect(
                validated_related[
                    : max(0, settings.google_related_validation_terms)
                ],
                discovery_seeds=[],
            )
            google_series.update(expansion.get("series") or {})
            warnings.extend(expansion.get("warnings") or [])
            primary_usage = google_result.get("usage_usd")
            expansion_usage = expansion.get("usage_usd")
            usage_values = [
                float(value)
                for value in (primary_usage, expansion_usage)
                if value is not None
            ]
            if usage_values:
                google_result["usage_usd"] = round(sum(usage_values), 6)
            google_result["attempts"] = [
                *(google_result.get("attempts") or []),
                *(expansion.get("attempts") or []),
            ]
            google_result["related_terms_validated"] = len(
                expansion.get("series") or {}
            )
        except Exception as exc:
            warnings.append(
                "Google related-query validation: "
                f"{exc}. The primary Google timelines were retained."
            )

    if collected_google_live and google_series:
        provider = str(google_result.get("provider") or "unknown route")
        source_status["google_trends"] = (
            f"live · {provider} · {settings.google_geo} · {len(google_series)} terms"
        )
        google_cache_out = {
            "collected_at": datetime.now(tz=timezone.utc).isoformat(),
            "market": settings.google_geo,
            "timeframe": settings.google_timeframe,
            "provider": provider,
            "series": google_series,
            "related": related,
        }
        google_cache_age_hours = 0.0
    google_result["used_cache"] = used_google_cache
    google_rows = score_google_series(google_series, audit=filtered_terms)
    trends = merge_trend_signals(
        google_rows,
        x_rows,
        audit=filtered_terms,
    )
    if not trends:
        trends = demo_trends()
        source_status["trend_fallback"] = "demo"
        warnings.append("No live trend rows were available, so the radar uses demo trend data.")

    if openrouter is not None:
        try:
            trends = openrouter.enrich_trends(trends)
            source_status["openrouter"] = (
                f"live · {settings.openrouter_model}"
                + (" · local semantic fallback" if semantic_error else " · semantic grouping + enrichment")
            )
        except Exception as exc:
            if not semantic_error and candidates:
                source_status["openrouter"] = "partial · semantic grouping live; enrichment failed"
            else:
                source_status["openrouter"] = "failed · deterministic labels kept"
            warnings.append(f"OpenRouter: {exc}")
    else:
        source_status["openrouter"] = "not configured" if not settings.openrouter_configured else "skipped"

    selected_catalog_source = catalog_source
    if selected_catalog_source == "auto":
        if (
            existing_meta.get("catalogue_source") == "csv"
            and (existing_snapshot or {}).get("products")
        ):
            selected_catalog_source = "csv"
            catalog_products = list((existing_snapshot or {}).get("products") or [])
        else:
            selected_catalog_source = "shopify_api"

    actual_catalog_source = selected_catalog_source
    if selected_catalog_source == "csv":
        if catalog_products is None and existing_meta.get("catalogue_source") == "csv":
            catalog_products = list((existing_snapshot or {}).get("products") or [])
        products = list(catalog_products or [])
        if products:
            source_status["shopify"] = f"CSV snapshot · {len(products):,} products"
            warnings.extend(
                f"Catalogue CSV: {warning}"
                for warning in existing_meta.get("catalogue_warnings", [])
            )
        else:
            products = demo_products()
            actual_catalog_source = "demo"
            source_status["shopify"] = "CSV unavailable · demo catalogue"
            warnings.append(
                "CSV was selected, but no imported catalogue was available. Upload a product CSV in Data & Setup."
            )
    elif settings.shopify_configured:
        try:
            products = ShopifyConnector(
                shop=settings.shopify_shop,
                client_id=settings.shopify_client_id,
                client_secret=settings.shopify_client_secret,
                admin_access_token=settings.shopify_admin_access_token,
                api_version=settings.shopify_api_version,
                storefront_url=settings.shopify_storefront_url,
            ).fetch_products(max_products=settings.shopify_max_products)
            source_status["shopify"] = f"API live · {len(products):,} products"
        except Exception as exc:
            products = demo_products()
            actual_catalog_source = "demo"
            source_status["shopify"] = "failed · demo catalogue"
            warnings.append(f"Shopify: {exc}")
    else:
        products = demo_products()
        actual_catalog_source = "demo"
        source_status["shopify"] = "not configured · demo catalogue"
    recommendations = match_products(trends, products)

    google_status = str(source_status.get("google_trends", ""))
    fully_live = (
        (google_status.startswith("live") or google_status.startswith("cached live"))
        and str(source_status.get("x_apify", "")).startswith("live")
        and str(source_status.get("shopify", "")).startswith("API live")
    )
    filtered_audit = consolidate_filter_audit(filtered_terms)
    snapshot = {
        "meta": {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "mode": "live" if fully_live else "hybrid",
            "region": settings.google_geo,
            "catalogue_source": actual_catalog_source,
            "catalogue_filename": (
                existing_meta.get("catalogue_filename", "")
                if actual_catalog_source == "csv"
                else ""
            ),
            "catalogue_format": (
                existing_meta.get("catalogue_format", "")
                if actual_catalog_source == "csv"
                else ""
            ),
            "catalogue_source_rows": (
                existing_meta.get("catalogue_source_rows", 0)
                if actual_catalog_source == "csv"
                else 0
            ),
            "catalogue_warnings": (
                existing_meta.get("catalogue_warnings", [])
                if actual_catalog_source == "csv"
                else []
            ),
            "source_status": source_status,
            "google_trends": {
                "provider": google_result.get("provider", "unavailable"),
                "market": settings.google_geo,
                "timeframe": settings.google_timeframe,
                "terms_returned": len(google_series),
                "related_queries_returned": len(related),
                "usage_usd": google_result.get("usage_usd"),
                "api_requests": int(google_result.get("requests_used") or 0),
                "api_request_ceiling": int(
                    google_result.get("request_ceiling") or 0
                ),
                "attempts": google_result.get("attempts", []),
                "used_cache": bool(google_result.get("used_cache")),
                "cache_age_hours": google_result.get(
                    "cache_age_hours",
                    round(float(google_cache_age_hours), 1)
                    if google_cache_age_hours is not None
                    else None,
                ),
                "term_ceiling": settings.google_max_terms,
            },
            "x_listening": x_collection,
            "filtered_terms": filtered_audit,
            "raw_counts": {
                "x_posts_collected": int(x_collection.get("collected") or len(posts)),
                "x_posts_aggregated": len(posts),
                "x_duplicates_removed": int(x_collection.get("duplicates_removed") or 0),
                "x_searches_planned": int(x_collection.get("planned") or 0),
                "x_searches_succeeded": int(x_collection.get("succeeded") or 0),
                "x_searches_skipped_capacity": int(
                    x_collection.get("skipped_capacity") or 0
                ),
                "x_topic_clusters": len(x_rows),
                "google_terms": len(google_rows),
                "google_related_queries": len(related),
                "filtered_generic_terms": len(filtered_audit),
                "shopify_products": len(products),
                "recommendations": len(recommendations),
            },
            "warnings": warnings,
            "methodology_version": "0.4",
            "quality_filter_version": "2.0",
            "privacy": (
                "Raw X posts and author identifiers are not persisted. Author identifiers are "
                "hashed in memory for breadth calculations; only aggregate topic evidence is saved."
            ),
        },
        "google_cache": google_cache_out,
        "trends": trends,
        "products": products,
        "recommendations": recommendations,
    }
    if persist:
        save_snapshot(snapshot, settings.snapshot_path)
    return snapshot
