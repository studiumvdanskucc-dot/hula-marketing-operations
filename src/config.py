from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from src.analysis.listening import (
    DEFAULT_EXPERT_ACCOUNTS,
    DEFAULT_PRIORITY_COMMERCIAL_ACCOUNTS,
    clean_expert_accounts,
)


DEFAULT_FASHION_TERMS = (
    "east west bag",
    "ballet flats",
    "mary jane shoes",
    "fisherman sandals",
    "raffia bag",
    "vintage chanel",
    "butter yellow fashion",
    "polka dot outfit",
    "leopard print",
    "scarf styling",
    "capri pants",
    "drop waist dress",
    "crochet dress",
    "boho chic",
    "nautical fashion",
    "charm jewellery",
    "maxi skirt",
    "jelly shoes",
    "suede bag",
    "statement belt",
)


def _streamlit_secret(name: str) -> Any:
    try:
        import streamlit as st

        return st.secrets.get(name)
    except Exception:
        return None


def setting(name: str, default: Any = "") -> Any:
    value = os.getenv(name)
    if value is not None:
        return value
    value = _streamlit_secret(name)
    return default if value is None else value


def as_bool(value: Any, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


def as_terms(value: Any) -> list[str]:
    if not value:
        return list(DEFAULT_FASHION_TERMS)
    if isinstance(value, list):
        terms = value
    else:
        terms = str(value).replace("\n", ",").split(",")
    cleaned = [str(term).strip() for term in terms if str(term).strip()]
    return list(dict.fromkeys(cleaned)) or list(DEFAULT_FASHION_TERMS)


def as_accounts(
    value: Any,
    default: tuple[str, ...] = DEFAULT_EXPERT_ACCOUNTS,
) -> list[str]:
    if not value:
        return list(default)
    if isinstance(value, list):
        accounts = value
    else:
        accounts = str(value).replace("\n", ",").split(",")
    return clean_expert_accounts(accounts) or list(default)


@dataclass(frozen=True)
class Settings:
    app_password: str = ""
    shopify_shop: str = ""
    shopify_client_id: str = ""
    shopify_client_secret: str = ""
    shopify_admin_access_token: str = ""
    shopify_api_version: str = "2026-07"
    shopify_storefront_url: str = "https://thehula.com"
    shopify_max_products: int = 750
    apify_token: str = ""
    apify_x_task_id: str = ""
    apify_x_task_input: dict[str, Any] = field(default_factory=dict)
    apify_timeout_seconds: int = 480
    apify_x_memory_mb: int = 512
    apify_x_listening_mode: str = "topic_plan"
    apify_results_per_query: int = 50
    apify_expert_results_per_query: int = 35
    apify_max_total_charge_usd: float = 0.25
    x_language: str = "en"
    x_expert_accounts: list[str] = field(
        default_factory=lambda: list(DEFAULT_EXPERT_ACCOUNTS)
    )
    x_priority_accounts: list[str] = field(
        default_factory=lambda: list(DEFAULT_PRIORITY_COMMERCIAL_ACCOUNTS)
    )
    instagram_enabled: bool = True
    apify_instagram_actor_id: str = "apify~instagram-hashtag-analytics-scraper"
    instagram_hashtag_max_terms: int = 8
    instagram_max_total_charge_usd: float = 0.25
    commercial_sources_enabled: bool = True
    commercial_timeout_seconds: int = 25
    commercial_max_workers: int = 4
    openrouter_api_key: str = ""
    openrouter_api_url: str = "https://openrouter.ai/api/v1/chat/completions"
    openrouter_model: str = "qwen/qwen3-vl-32b-instruct"
    openrouter_timeout: int = 180
    openrouter_site_url: str = ""
    openrouter_app_name: str = "HULA Trend Intelligence"
    google_geo: str = "WORLDWIDE"
    google_timeframe: str = "today 1-m"
    google_discovery_timeframe: str = "now 7-d"
    google_category: int = 0
    google_anchor_term: str = "designer fashion"
    enable_google_related_queries: bool = True
    google_provider: str = "auto"
    serpapi_api_key: str = ""
    serpapi_endpoint: str = "https://serpapi.com/search.json"
    serpapi_timeout_seconds: int = 75
    google_max_terms: int = 24
    google_max_discovery_seeds: int = 2
    google_related_validation_terms: int = 4
    google_cache_hours: int = 24
    google_stale_cache_days: int = 3
    google_connect_timeout_seconds: int = 10
    google_read_timeout_seconds: int = 35
    fashion_terms: list[str] = field(default_factory=lambda: list(DEFAULT_FASHION_TERMS))
    snapshot_path: str = "data/latest_snapshot.json"
    supabase_url: str = ""
    supabase_secret_key: str = ""
    supabase_snapshot_table: str = "hula_trend_snapshots"
    supabase_blog_table: str = "hula_blog_drafts"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_seconds: int = 180
    gemini_grounding_enabled: bool = True

    @property
    def shopify_configured(self) -> bool:
        new_auth = bool(
            self.shopify_shop and self.shopify_client_id and self.shopify_client_secret
        )
        legacy_auth = bool(self.shopify_shop and self.shopify_admin_access_token)
        return new_auth or legacy_auth

    @property
    def apify_configured(self) -> bool:
        return bool(self.apify_token and self.apify_x_task_id)

    @property
    def instagram_configured(self) -> bool:
        return bool(
            self.instagram_enabled
            and self.apify_token
            and self.apify_instagram_actor_id
        )

    @property
    def topic_plan_enabled(self) -> bool:
        return self.apify_x_listening_mode.strip().lower() != "task_input"

    @property
    def openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key and self.openrouter_model)

    @property
    def serpapi_configured(self) -> bool:
        return bool(self.serpapi_api_key)

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)

    @property
    def gemini_configured(self) -> bool:
        return bool(self.gemini_api_key and self.gemini_model)


def load_settings() -> Settings:
    return Settings(
        app_password=str(setting("APP_PASSWORD", "")),
        shopify_shop=str(setting("SHOPIFY_SHOP", "")),
        shopify_client_id=str(setting("SHOPIFY_CLIENT_ID", "")),
        shopify_client_secret=str(setting("SHOPIFY_CLIENT_SECRET", "")),
        shopify_admin_access_token=str(setting("SHOPIFY_ADMIN_ACCESS_TOKEN", "")),
        shopify_api_version=str(setting("SHOPIFY_API_VERSION", "2026-07")),
        shopify_storefront_url=str(
            setting("SHOPIFY_STOREFRONT_URL", "https://thehula.com")
        ).rstrip("/"),
        shopify_max_products=as_int(setting("SHOPIFY_MAX_PRODUCTS", 750), 750),
        apify_token=str(setting("APIFY_TOKEN", "")),
        apify_x_task_id=str(setting("APIFY_X_TASK_ID", "")),
        apify_x_task_input=as_json(setting("APIFY_X_TASK_INPUT_JSON", ""), {}),
        apify_timeout_seconds=as_int(setting("APIFY_TIMEOUT_SECONDS", 480), 480),
        apify_x_memory_mb=as_int(setting("APIFY_X_MEMORY_MB", 512), 512),
        apify_x_listening_mode=str(
            setting("APIFY_X_LISTENING_MODE", "topic_plan")
        ),
        apify_results_per_query=as_int(
            setting("APIFY_RESULTS_PER_QUERY", 50), 50
        ),
        apify_expert_results_per_query=as_int(
            setting("APIFY_EXPERT_RESULTS_PER_QUERY", 35), 35
        ),
        apify_max_total_charge_usd=as_float(
            setting("APIFY_MAX_TOTAL_CHARGE_USD", 0.25), 0.25
        ),
        x_language=str(setting("X_LANGUAGE", "en")),
        x_expert_accounts=as_accounts(setting("X_EXPERT_ACCOUNTS", "")),
        x_priority_accounts=as_accounts(
            setting("X_PRIORITY_ACCOUNTS", ""),
            DEFAULT_PRIORITY_COMMERCIAL_ACCOUNTS,
        ),
        instagram_enabled=as_bool(setting("INSTAGRAM_ENABLED", True), True),
        apify_instagram_actor_id=str(
            setting(
                "APIFY_INSTAGRAM_ACTOR_ID",
                "apify~instagram-hashtag-analytics-scraper",
            )
        ),
        instagram_hashtag_max_terms=as_int(
            setting("INSTAGRAM_HASHTAG_MAX_TERMS", 8), 8
        ),
        instagram_max_total_charge_usd=as_float(
            setting("INSTAGRAM_MAX_TOTAL_CHARGE_USD", 0.25), 0.25
        ),
        commercial_sources_enabled=as_bool(
            setting("COMMERCIAL_SOURCES_ENABLED", True), True
        ),
        commercial_timeout_seconds=as_int(
            setting("COMMERCIAL_TIMEOUT_SECONDS", 25), 25
        ),
        commercial_max_workers=as_int(
            setting("COMMERCIAL_MAX_WORKERS", 4), 4
        ),
        openrouter_api_key=str(setting("OPENROUTER_API_KEY", "")),
        openrouter_api_url=str(
            setting(
                "OPENROUTER_API_URL",
                "https://openrouter.ai/api/v1/chat/completions",
            )
        ),
        openrouter_model=str(
            setting("OPENROUTER_MODEL", "qwen/qwen3-vl-32b-instruct")
        ),
        openrouter_timeout=as_int(setting("OPENROUTER_TIMEOUT", 180), 180),
        openrouter_site_url=str(setting("OPENROUTER_SITE_URL", "")),
        openrouter_app_name=str(
            setting("OPENROUTER_APP_NAME", "HULA Trend Intelligence")
        ),
        google_geo=str(setting("GOOGLE_TRENDS_GEO", "WORLDWIDE")),
        google_timeframe=str(setting("GOOGLE_TRENDS_TIMEFRAME", "today 1-m")),
        google_discovery_timeframe=str(
            setting("GOOGLE_TRENDS_DISCOVERY_TIMEFRAME", "now 7-d")
        ),
        google_category=as_int(setting("GOOGLE_TRENDS_CATEGORY", 0), 0),
        google_anchor_term=str(
            setting("GOOGLE_TRENDS_ANCHOR_TERM", "designer fashion")
        ),
        enable_google_related_queries=as_bool(
            setting("GOOGLE_TRENDS_RELATED_QUERIES", True), True
        ),
        google_provider=str(setting("GOOGLE_TRENDS_PROVIDER", "auto")),
        serpapi_api_key=str(setting("SERPAPI_API_KEY", "")),
        serpapi_endpoint=str(
            setting("SERPAPI_ENDPOINT", "https://serpapi.com/search.json")
        ),
        serpapi_timeout_seconds=as_int(
            setting("SERPAPI_TIMEOUT_SECONDS", 75), 75
        ),
        google_max_terms=as_int(setting("GOOGLE_TRENDS_MAX_TERMS", 24), 24),
        google_max_discovery_seeds=as_int(
            setting("GOOGLE_TRENDS_MAX_DISCOVERY_SEEDS", 2), 2
        ),
        google_related_validation_terms=as_int(
            setting("GOOGLE_TRENDS_RELATED_VALIDATION_TERMS", 4), 4
        ),
        google_cache_hours=as_int(
            setting("GOOGLE_TRENDS_CACHE_HOURS", 24), 24
        ),
        google_stale_cache_days=as_int(
            setting("GOOGLE_TRENDS_STALE_CACHE_DAYS", 3), 3
        ),
        google_connect_timeout_seconds=as_int(
            setting("GOOGLE_TRENDS_CONNECT_TIMEOUT_SECONDS", 10), 10
        ),
        google_read_timeout_seconds=as_int(
            setting("GOOGLE_TRENDS_READ_TIMEOUT_SECONDS", 35), 35
        ),
        fashion_terms=as_terms(setting("FASHION_TERMS", "")),
        snapshot_path=str(setting("SNAPSHOT_PATH", "data/latest_snapshot.json")),
        supabase_url=str(setting("SUPABASE_URL", "")).rstrip("/"),
        supabase_secret_key=str(setting("SUPABASE_SECRET_KEY", "")),
        supabase_snapshot_table=str(
            setting("SUPABASE_SNAPSHOT_TABLE", "hula_trend_snapshots")
        ),
        supabase_blog_table=str(
            setting("SUPABASE_BLOG_TABLE", "hula_blog_drafts")
        ),
        gemini_api_key=str(setting("GEMINI_API_KEY", "")),
        gemini_model=str(setting("GEMINI_MODEL", "gemini-3.6-flash")),
        gemini_api_url=str(
            setting(
                "GEMINI_API_URL",
                "https://generativelanguage.googleapis.com/v1beta",
            )
        ).rstrip("/"),
        gemini_timeout_seconds=as_int(
            setting("GEMINI_TIMEOUT_SECONDS", 180), 180
        ),
        gemini_grounding_enabled=as_bool(
            setting("GEMINI_GROUNDING_ENABLED", True), True
        ),
    )
