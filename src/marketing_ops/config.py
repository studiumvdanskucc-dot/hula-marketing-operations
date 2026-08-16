from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _secret(name: str) -> Any:
    try:
        import streamlit as st

        return st.secrets.get(name)
    except Exception:
        return None


def _setting(name: str, default: Any = "") -> Any:
    value = os.getenv(name)
    if value is not None:
        return value
    value = _secret(name)
    return default if value is None else value


def _bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default


@dataclass(frozen=True)
class MarketingSettings:
    app_env: str = "development"
    app_name: str = "HULA Marketing Operations"
    app_timezone: str = "Asia/Hong_Kong"
    app_currency: str = "HKD"
    demo_mode: bool = True
    database_path: str = "data/marketing_operations_demo.sqlite3"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    auth_enabled: bool = False
    demo_user_name: str = "Tereza"
    default_role: str = "Administrator"
    feature_flags: dict[str, bool] = field(default_factory=dict)
    shopify_store_domain: str = ""
    shopify_access_token: str = ""
    shopify_client_id: str = ""
    shopify_client_secret: str = ""
    shopify_api_version: str = "2026-07"
    google_access_token: str = ""
    ga4_property_id: str = ""
    gsc_site_url: str = ""
    google_ads_customer_id: str = ""
    google_ads_developer_token: str = ""
    google_ads_api_version: str = "v25"
    meta_access_token: str = ""
    meta_ad_account_id: str = ""
    meta_api_version: str = "v26.0"
    klaviyo_private_api_key: str = ""
    klaviyo_api_revision: str = "2026-01-15"
    gbp_account_id: str = ""
    gbp_location_ids: tuple[str, ...] = ()
    merchant_account_id: str = ""
    pagespeed_api_key: str = ""
    crawler_base_url: str = "https://thehula.com"
    crawler_max_pages: int = 1000
    crawler_requests_per_second: int = 1
    job_worker_enabled: bool = True
    report_reference_period: str = "2026-07"

    @property
    def writes_enabled(self) -> bool:
        return any(
            enabled
            for name, enabled in self.feature_flags.items()
            if name.startswith("ENABLE_")
        )


def load_marketing_settings() -> MarketingSettings:
    flags = {
        "ENABLE_SHOPIFY_WRITES": _bool(_setting("ENABLE_SHOPIFY_WRITES", False)),
        "ENABLE_GOOGLE_ADS_WRITES": _bool(
            _setting("ENABLE_GOOGLE_ADS_WRITES", False)
        ),
        "ENABLE_META_ADS_WRITES": _bool(_setting("ENABLE_META_ADS_WRITES", False)),
        "ENABLE_KLAVIYO_WRITES": _bool(_setting("ENABLE_KLAVIYO_WRITES", False)),
        "ENABLE_GBP_WRITES": _bool(_setting("ENABLE_GBP_WRITES", False)),
        "ENABLE_MERCHANT_WRITES": _bool(_setting("ENABLE_MERCHANT_WRITES", False)),
        "ENABLE_AUTOMATIC_PUBLISHING": _bool(
            _setting("ENABLE_AUTOMATIC_PUBLISHING", False)
        ),
        "ENABLE_AUTOMATIC_BUDGET_CHANGES": _bool(
            _setting("ENABLE_AUTOMATIC_BUDGET_CHANGES", False)
        ),
        "REQUIRE_APPROVAL_FOR_ALL_WRITES": _bool(
            _setting("REQUIRE_APPROVAL_FOR_ALL_WRITES", True), True
        ),
        "REQUIRE_SECOND_APPROVER_FOR_HIGH_RISK": _bool(
            _setting("REQUIRE_SECOND_APPROVER_FOR_HIGH_RISK", True), True
        ),
    }
    locations = tuple(
        item.strip()
        for item in str(_setting("GBP_LOCATION_IDS", "")).split(",")
        if item.strip()
    )
    return MarketingSettings(
        app_env=str(_setting("APP_ENV", "development")),
        app_name=str(_setting("MARKETING_APP_NAME", "HULA Marketing Operations")),
        app_timezone=str(_setting("APP_TIMEZONE", "Asia/Hong_Kong")),
        app_currency=str(_setting("APP_CURRENCY", "HKD")),
        demo_mode=_bool(_setting("DEMO_MODE", True), True),
        database_path=str(
            _setting("MARKETING_DATABASE_PATH", "data/marketing_operations_demo.sqlite3")
        ),
        supabase_url=str(_setting("SUPABASE_URL", "")),
        supabase_anon_key=str(_setting("SUPABASE_ANON_KEY", "")),
        auth_enabled=_bool(_setting("MARKETING_AUTH_ENABLED", False)),
        demo_user_name=str(_setting("DEMO_USER_NAME", "Tereza")),
        default_role=str(_setting("DEMO_DEFAULT_ROLE", "Administrator")),
        feature_flags=flags,
        shopify_store_domain=str(
            _setting("SHOPIFY_STORE_DOMAIN", _setting("SHOPIFY_SHOP", ""))
        ),
        shopify_access_token=str(_setting("SHOPIFY_ADMIN_ACCESS_TOKEN", "")),
        shopify_client_id=str(_setting("SHOPIFY_CLIENT_ID", "")),
        shopify_client_secret=str(_setting("SHOPIFY_CLIENT_SECRET", "")),
        shopify_api_version=str(_setting("SHOPIFY_API_VERSION", "2026-07")),
        google_access_token=str(_setting("GOOGLE_OAUTH_ACCESS_TOKEN", "")),
        ga4_property_id=str(_setting("GA4_PROPERTY_ID", "")),
        gsc_site_url=str(_setting("GSC_SITE_URL", "")),
        google_ads_customer_id=str(_setting("GOOGLE_ADS_CUSTOMER_ID", "")),
        google_ads_developer_token=str(_setting("GOOGLE_ADS_DEVELOPER_TOKEN", "")),
        google_ads_api_version=str(_setting("GOOGLE_ADS_API_VERSION", "v25")),
        meta_access_token=str(_setting("META_SYSTEM_USER_ACCESS_TOKEN", "")),
        meta_ad_account_id=str(_setting("META_AD_ACCOUNT_ID", "")),
        meta_api_version=str(_setting("META_API_VERSION", "v26.0")),
        klaviyo_private_api_key=str(_setting("KLAVIYO_PRIVATE_API_KEY", "")),
        klaviyo_api_revision=str(_setting("KLAVIYO_API_REVISION", "2026-01-15")),
        gbp_account_id=str(_setting("GBP_ACCOUNT_ID", "")),
        gbp_location_ids=locations,
        merchant_account_id=str(_setting("MERCHANT_CENTER_ACCOUNT_ID", "")),
        pagespeed_api_key=str(_setting("PAGESPEED_API_KEY", "")),
        crawler_base_url=str(_setting("CRAWLER_BASE_URL", "https://thehula.com")),
        crawler_max_pages=_int(_setting("CRAWLER_MAX_PAGES", 1000), 1000),
        crawler_requests_per_second=_int(
            _setting("CRAWLER_REQUESTS_PER_SECOND", 1), 1
        ),
        job_worker_enabled=_bool(_setting("JOB_WORKER_ENABLED", True), True),
        report_reference_period=str(_setting("REPORT_REFERENCE_PERIOD", "2026-07")),
    )


def resolve_database_path(settings: MarketingSettings, root: Path) -> Path:
    path = Path(settings.database_path)
    return path if path.is_absolute() else root / path
