from __future__ import annotations

from src.marketing_ops.config import MarketingSettings

from .base import Connector
from .ga4 import GA4ReadOnlyConnector
from .search_console import SearchConsoleReadOnlyConnector
from .shell import ProviderShell, RequiredSetting
from .shopify_read import ShopifyReadOnlyConnector


def build_connector_registry(settings: MarketingSettings) -> dict[str, Connector]:
    google_token = bool(settings.google_access_token)
    return {
        "Shopify": ShopifyReadOnlyConnector(
            settings.shopify_store_domain,
            settings.shopify_access_token,
            settings.shopify_api_version,
            client_id=settings.shopify_client_id,
            client_secret=settings.shopify_client_secret,
        ),
        "Google Analytics 4": GA4ReadOnlyConnector(settings.ga4_property_id, settings.google_access_token),
        "Google Search Console": SearchConsoleReadOnlyConnector(settings.gsc_site_url, settings.google_access_token),
        "Google Ads": ProviderShell("Google Ads", settings.google_ads_api_version, (RequiredSetting("GOOGLE_ADS_CUSTOMER_ID", bool(settings.google_ads_customer_id)), RequiredSetting("GOOGLE_ADS_DEVELOPER_TOKEN", bool(settings.google_ads_developer_token)), RequiredSetting("Google OAuth credentials", google_token)), ("campaign reporting", "search terms", "conversion metrics", "budget pacing"), "Google Ads reporting access; no mutate operations"),
        "Meta Ads": ProviderShell("Meta Ads", settings.meta_api_version, (RequiredSetting("META_AD_ACCOUNT_ID", bool(settings.meta_ad_account_id)), RequiredSetting("META_SYSTEM_USER_ACCESS_TOKEN", bool(settings.meta_access_token))), ("campaign/ad set/ad insights", "creative metadata", "placement performance"), "ads_read; ads_management not requested"),
        "Klaviyo": ProviderShell("Klaviyo", settings.klaviyo_api_revision, (RequiredSetting("KLAVIYO_PRIVATE_API_KEY", bool(settings.klaviyo_private_api_key)),), ("campaign reports", "flow reports", "form/segment metrics"), "Scoped read-only private-key permissions"),
        "Google Business Profile": ProviderShell("Google Business Profile", "Performance v1 / Reviews v4", (RequiredSetting("GBP_ACCOUNT_ID", bool(settings.gbp_account_id)), RequiredSetting("GBP_LOCATION_IDS", bool(settings.gbp_location_ids)), RequiredSetting("Google OAuth credentials", google_token)), ("location performance", "reviews", "profile health"), "Business Profile read access"),
        "Merchant Center": ProviderShell("Merchant Center", "Merchant API v1", (RequiredSetting("MERCHANT_CENTER_ACCOUNT_ID", bool(settings.merchant_account_id)), RequiredSetting("Google OAuth credentials", google_token)), ("product status", "account/product issues", "feed freshness"), "Merchant Center read access"),
        "PageSpeed Insights": ProviderShell("PageSpeed Insights", "v5", (RequiredSetting("PAGESPEED_API_KEY", bool(settings.pagespeed_api_key)),), ("mobile and desktop lab metrics", "priority URL diagnostics"), "Read-only API key restricted to the API"),
    }
