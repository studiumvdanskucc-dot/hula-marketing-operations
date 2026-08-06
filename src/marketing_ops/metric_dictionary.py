from __future__ import annotations

from typing import Any


# These definitions are intentionally business-readable. A metric is not allowed
# into the executive layer until its scope, source and attribution treatment are
# explicit here.
CORE_METRICS: tuple[dict[str, Any], ...] = (
    {
        "Metric": "Commerce revenue",
        "Status": "Defined",
        "Formula": "Sum of included Shopify/POS booked sales for the reporting period",
        "Source": "Shopify orders + POS locations",
        "Scope": "Online and physical-store commerce; refunds, tax, shipping and test-order policy require sign-off",
        "Attribution window": "Not applicable — booked commerce",
        "Use": "Primary revenue source of truth",
    },
    {
        "Metric": "Revenue by location",
        "Status": "Needs reconciliation",
        "Formula": "Included commerce revenue grouped by normalized location",
        "Source": "Shopify orders + POS location mapping",
        "Scope": "Same included order population as Commerce revenue",
        "Attribution window": "Not applicable — booked commerce",
        "Use": "Do not distribute until the location sum matches the headline",
    },
    {
        "Metric": "Google Ads attributed revenue",
        "Status": "Needs account confirmation",
        "Formula": "Google Ads primary purchase conversion value",
        "Source": "Google Ads",
        "Scope": "Platform-attributed conversions only; may overlap other channels",
        "Attribution window": "Use the account conversion-action setting and display it beside the value",
        "Use": "Paid-search optimization, never booked revenue",
    },
    {
        "Metric": "Meta attributed revenue",
        "Status": "Defined from report",
        "Formula": "Meta purchase conversion value",
        "Source": "Meta Ads",
        "Scope": "Platform-attributed conversions; may overlap Shopify, GA4 and Klaviyo",
        "Attribution window": "7 days, according to the supplied agency report",
        "Use": "Paid-social optimization, never booked revenue",
    },
    {
        "Metric": "Klaviyo attributed revenue",
        "Status": "Defined from report",
        "Formula": "Klaviyo campaign and flow conversion value",
        "Source": "Klaviyo",
        "Scope": "Platform-attributed email conversions; can overlap paid and direct revenue",
        "Attribution window": "90 days, according to the supplied agency report",
        "Use": "Email optimization; never add to Meta/Google as exclusive channel revenue",
    },
    {
        "Metric": "Paid-media ROAS",
        "Status": "Defined with limitation",
        "Formula": "Platform-attributed Google + Meta revenue / Google + Meta spend",
        "Source": "Google Ads + Meta Ads",
        "Scope": "A blended platform view; windows must be disclosed and aligned before direct comparison",
        "Attribution window": "Mixed until Google is confirmed; Meta report uses 7 days",
        "Use": "Directional paid efficiency",
    },
    {
        "Metric": "Marketing efficiency ratio (MER)",
        "Status": "Defined with limitation",
        "Formula": "Shopify/POS commerce revenue / paid-media spend",
        "Source": "Shopify + Google Ads + Meta Ads",
        "Scope": "All commerce revenue relative to paid spend; not incremental ROAS",
        "Attribution window": "Not applicable to numerator",
        "Use": "Blended business-level efficiency context",
    },
    {
        "Metric": "Spend per all new customer",
        "Status": "Defined as proxy — not CAC",
        "Formula": "Google + Meta spend / all Shopify new customers",
        "Source": "Paid platforms + Shopify",
        "Scope": "Includes in-store and potentially organic new customers",
        "Attribution window": "Not applicable",
        "Use": "Efficiency proxy only; the agency's HK$182 must not be labelled paid CAC",
    },
    {
        "Metric": "True paid CAC",
        "Status": "Not yet measurable",
        "Formula": "Paid-media spend / deduplicated new customers causally attributed to paid media",
        "Source": "Shopify customer identity + governed attribution model",
        "Scope": "Paid-acquired first-time customers only",
        "Attribution window": "Must be agreed before use",
        "Use": "Do not display until paid-acquired customer identity is reliable",
    },
    {
        "Metric": "Online conversion rate",
        "Status": "Defined from report",
        "Formula": "Online Store orders / online sessions",
        "Source": "Shopify Online Store + analytics sessions",
        "Scope": "Online Store only",
        "Attribution window": "Same reporting period",
        "Use": "Website conversion; never combine with physical-store rows",
    },
    {
        "Metric": "Physical-store conversion rate",
        "Status": "Not available from web analytics",
        "Formula": "Requires a store traffic denominator or another agreed footfall measure",
        "Source": "POS + store footfall system (not supplied)",
        "Scope": "Physical stores only",
        "Attribution window": "Not applicable",
        "Use": "Show as unavailable, not 0.00%",
    },
    {
        "Metric": "Session behaviour events",
        "Status": "Defined as event incidence, not a funnel",
        "Formula": "Event/session counts and share of 57,585 session starts",
        "Source": "Agency report analytics page",
        "Scope": "Session start, page view, view item and add-to-cart event rows shown in the report",
        "Attribution window": "1–31 July 2026",
        "Use": "Do not append Shopify orders or an invented checkout count to create a funnel",
    },
)


def metric_rows() -> list[dict[str, Any]]:
    return [dict(row) for row in CORE_METRICS]


def metric_by_name(name: str) -> dict[str, Any]:
    return next(dict(row) for row in CORE_METRICS if row["Metric"] == name)

