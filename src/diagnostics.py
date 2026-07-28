from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable


SOURCE_NAMES = {
    "google_trends": "Google Trends",
    "x_apify": "X via Apify",
    "instagram": "Instagram panel",
    "shopify": "Product catalogue",
    "openrouter": "OpenRouter / Qwen",
    "supabase": "Supabase history",
    "gemini": "Gemini blog research",
}


def safe_error(exc: BaseException, secrets: Iterable[str] = ()) -> str:
    """Return a useful, bounded error message without echoing configured secrets."""
    message = str(exc).strip() or "No additional detail was returned."
    for secret in secrets:
        value = str(secret or "")
        if value:
            message = message.replace(value, "[redacted]")
    return f"{type(exc).__name__}: {message}"[:900]


def hybrid_explanation(meta: dict[str, Any]) -> str:
    """Explain why a snapshot is not fully live without treating CSV as a failure."""
    mode = str(meta.get("mode", "demo")).lower()
    if mode == "demo":
        return "The trend signals and catalogue are illustrative until real sources are refreshed."

    statuses = meta.get("source_status") or {}
    catalogue_source = str(meta.get("catalogue_source", "")).lower()
    expected: list[str] = []
    attention: list[str] = []

    if catalogue_source == "csv" or "csv snapshot" in str(
        statuses.get("shopify", "")
    ).lower():
        expected.append("the catalogue is an uploaded CSV snapshot")

    for key in (
        "google_trends",
        "x_apify",
        "instagram",
        "openrouter",
        "supabase",
        "gemini",
    ):
        value = str(statuses.get(key, "")).strip()
        lowered = value.lower()
        if not value:
            continue
        if "failed" in lowered:
            attention.append(f"{SOURCE_NAMES[key]} failed on the last refresh")
        elif "stale" in lowered:
            attention.append(
                f"{SOURCE_NAMES[key]} is stale and excluded from decisions"
            )
        elif "partial" in lowered:
            attention.append(f"{SOURCE_NAMES[key]} completed only part of the last refresh")
        elif "not configured" in lowered:
            attention.append(f"{SOURCE_NAMES[key]} was not configured on the last refresh")
        elif lowered in {"demo", "not used"} or "no data" in lowered:
            attention.append(f"{SOURCE_NAMES[key]} used no live data on the last refresh")
        elif "skipped" in lowered:
            attention.append(f"{SOURCE_NAMES[key]} enrichment was skipped")

    if str(statuses.get("trend_fallback", "")).lower() == "demo":
        attention.append("the trend radar fell back to illustrative data")

    if expected and not attention:
        return (
            "The catalogue is an uploaded CSV snapshot. This is expected and does not mean "
            "OpenRouter failed; check Data & Setup for each source's last-refresh status."
        )

    parts: list[str] = []
    if expected:
        parts.append("Expected: " + ", ".join(expected) + ".")
    if attention:
        shown = attention[:3]
        suffix = f" (+{len(attention) - 3} more)" if len(attention) > 3 else ""
        parts.append("Needs attention: " + "; ".join(shown) + suffix + ".")
    if not parts:
        parts.append("At least one source is not fully live.")
    return " ".join(parts) + " See Data & Setup → Diagnostics."


def _action_for(
    source: str,
    status: str,
    *,
    configured_now: bool,
    catalogue_source: str,
) -> str:
    lowered = status.lower()
    if source == "shopify" and catalogue_source == "csv":
        return (
            "Expected. Product matching uses your real uploaded catalogue, but a CSV snapshot "
            "keeps the dataset in Hybrid Mode."
        )
    if "live" in lowered or lowered.startswith("api live"):
        return "Working on the last completed refresh."
    if "stale" in lowered:
        return "Shown only as historical context; stale evidence cannot make a trend decision-ready."
    if "partial" in lowered:
        return "Some planned searches completed and were retained; inspect Refresh notes for the failed query windows."
    if "manual csv" in lowered:
        return "A manual search-data snapshot is active; refresh the file when needed."
    if "failed" in lowered:
        return f"Run the {SOURCE_NAMES[source]} connection test below and read the saved error detail."
    if "not configured" in lowered or lowered in {"demo", "not used", ""}:
        if configured_now:
            return "Credentials are loaded now; run its connection test or a refresh to update this older status."
        if source == "google_trends":
            return "Add SERPAPI_API_KEY in Streamlit Secrets, restart the app, then run the Google Trends test."
        if source == "instagram":
            return "Add APIFY_TOKEN; the maintained Instagram Actor does not require a separate saved task."
        if source == "supabase":
            return "Add SUPABASE_URL and SUPABASE_SECRET_KEY, then run supabase/schema.sql once."
        if source == "gemini":
            return "Add GEMINI_API_KEY and GEMINI_MODEL in Streamlit Secrets."
        return "Add the required settings, restart Streamlit, then run the connection test."
    if "skipped" in lowered:
        return "The connection may be available, but enrichment was disabled for that refresh."
    if "no data" in lowered:
        return "The connector responded but returned no usable rows; inspect Refresh notes."
    return "Review Refresh notes or run the relevant connection test."


def source_diagnostic_rows(
    meta: dict[str, Any],
    *,
    google_configured: bool,
    apify_configured: bool,
    shopify_configured: bool,
    openrouter_configured: bool,
    instagram_configured: bool = False,
    supabase_configured: bool = False,
    gemini_configured: bool = False,
) -> list[dict[str, str]]:
    statuses = meta.get("source_status") or {}
    catalogue_source = str(meta.get("catalogue_source", "")).lower()
    configured = {
        "google_trends": google_configured,
        "x_apify": apify_configured,
        "instagram": instagram_configured,
        "shopify": catalogue_source == "csv" or shopify_configured,
        "openrouter": openrouter_configured,
        "supabase": supabase_configured,
        "gemini": gemini_configured,
    }
    rows: list[dict[str, str]] = []
    for source in (
        "google_trends",
        "x_apify",
        "instagram",
        "shopify",
        "openrouter",
        "supabase",
        "gemini",
    ):
        status = str(statuses.get(source, "not yet tested"))
        rows.append(
            {
                "Source": SOURCE_NAMES[source],
                "Configured now": "Yes" if configured[source] else "No",
                "Last refresh": status,
                "Meaning / next action": _action_for(
                    source,
                    status,
                    configured_now=configured[source],
                    catalogue_source=catalogue_source,
                ),
            }
        )
    return rows


def diagnostic_report(
    meta: dict[str, Any],
    *,
    app_build: str,
    google_configured: bool,
    apify_configured: bool,
    shopify_configured: bool,
    openrouter_configured: bool,
    openrouter_model: str,
    google_provider: str = "auto",
    google_geo: str = "WORLDWIDE",
    instagram_configured: bool = False,
    supabase_configured: bool = False,
    gemini_configured: bool = False,
) -> dict[str, Any]:
    """Create a shareable report that intentionally excludes every secret value."""
    return {
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "app_build": app_build,
        "dataset_mode": meta.get("mode"),
        "dataset_generated_at": meta.get("generated_at"),
        "catalogue_source": meta.get("catalogue_source"),
        "configuration_loaded": {
            "google_trends": google_configured,
            "apify": apify_configured,
            "instagram": instagram_configured,
            "shopify_api": shopify_configured,
            "openrouter": openrouter_configured,
            "openrouter_model": openrouter_model,
            "google_trends_provider": google_provider,
            "google_trends_market": google_geo,
            "supabase": supabase_configured,
            "gemini": gemini_configured,
        },
        "last_google_trends_run": meta.get("google_trends") or {},
        "last_refresh_source_status": meta.get("source_status") or {},
        "last_refresh_counts": meta.get("raw_counts") or {},
        "x_listening_summary": meta.get("x_listening") or {},
        "instagram_collection_summary": meta.get("instagram_collection") or {},
        "last_refresh_notes": meta.get("warnings") or [],
        "privacy": (
            "No API keys, tokens, passwords, client secrets or raw X/Instagram "
            "posts are included."
        ),
    }
