from __future__ import annotations

import copy
from functools import lru_cache
from typing import Any

from .metrics import (
    blended_roas,
    marketing_efficiency_ratio,
    reconciliation_row,
    seo_opportunity_score,
)


REFERENCE_PERIOD = "1–31 July 2026"
REFERENCE_AS_OF = "6 August 2026, 09:00 HKT"


def _seo_opportunities() -> list[dict[str, Any]]:
    raw = [
        {
            "query": "preowned vs preloved",
            "page": "/blogs/journal/preowned-vs-preloved",
            "impressions": 31_589,
            "clicks": 19,
            "position": 8.9,
            "ctr": 0.06,
            "factors": {
                "demand": 96,
                "position_opportunity": 82,
                "ctr_gap": 99,
                "conversion_value": 38,
                "inventory_relevance": 74,
                "trend_relevance": 62,
                "content_gap": 88,
                "business_priority": 90,
            },
            "action": "Rewrite the title and description, add a concise answer block, and link to current authenticated collections.",
            "effort": "Low",
        },
        {
            "query": "gucci symbols meaning",
            "page": "/blogs/journal/gucci-symbols",
            "impressions": 24_870,
            "clicks": 146,
            "position": 9.7,
            "ctr": 0.59,
            "factors": {
                "demand": 88,
                "position_opportunity": 79,
                "ctr_gap": 91,
                "conversion_value": 45,
                "inventory_relevance": 83,
                "trend_relevance": 55,
                "content_gap": 70,
                "business_priority": 84,
            },
            "action": "Refresh the snippet, add expert-authored examples, and link to available Gucci pieces.",
            "effort": "Medium",
        },
        {
            "query": "sell designer clothes hong kong",
            "page": "/pages/sell-with-us",
            "impressions": 8_410,
            "clicks": 158,
            "position": 6.4,
            "ctr": 1.88,
            "factors": {
                "demand": 73,
                "position_opportunity": 86,
                "ctr_gap": 64,
                "conversion_value": 96,
                "inventory_relevance": 100,
                "trend_relevance": 46,
                "content_gap": 72,
                "business_priority": 100,
            },
            "action": "Strengthen the consignment value proposition and add location-specific proof and FAQs.",
            "effort": "Medium",
        },
        {
            "query": "chanel bag hong kong pre owned",
            "page": "/collections/chanel",
            "impressions": 12_208,
            "clicks": 311,
            "position": 5.8,
            "ctr": 2.55,
            "factors": {
                "demand": 82,
                "position_opportunity": 77,
                "ctr_gap": 48,
                "conversion_value": 93,
                "inventory_relevance": 88,
                "trend_relevance": 78,
                "content_gap": 58,
                "business_priority": 96,
            },
            "action": "Add a stronger collection introduction and expert authentication module; verify inventory first.",
            "effort": "Medium",
        },
    ]
    output = []
    for item in raw:
        score = seo_opportunity_score(item.pop("factors"))
        output.append(
            {
                **item,
                "score": score.score,
                "factor_contributions": score.weighted_contributions,
                "data_mode": "fixture",
            }
        )
    return output


@lru_cache(maxsize=1)
def _build() -> dict[str, Any]:
    total_revenue = 2_490_383.0
    paid_spend = 30_398.60
    google_value = 148_913.65
    meta_value = 84_986.32
    new_customers = 167
    store_sum = 1_140_489.49 + 959_061.92 + 420_178.15 + 800.0
    channel_chart_sum = 1_002_811.03 + 148_913.65 + 100_372.87 + 84_986.32
    executive = {
        "commerce_revenue": total_revenue,
        "net_revenue": 2_438_910.0,
        "gross_sales": 2_620_882.0,
        "refunds": 51_473.0,
        "discounts": 130_499.0,
        "orders": 409,
        "aov": 5_826.0,
        "median_order_value": 3_820.0,
        "new_customers": new_customers,
        "repeat_customers": 176,
        "repeat_revenue_share": 68.4,
        "historical_realized_clv": 4_061.12,
        "paid_spend": paid_spend,
        "platform_paid_revenue": google_value + meta_value,
        "blended_roas": blended_roas(google_value + meta_value, paid_spend),
        "mer": marketing_efficiency_ratio(total_revenue, paid_spend),
        "spend_per_all_new_customer": paid_spend / new_customers,
        "paid_cac": None,
        "organic_attributed_revenue": 59_000.0,
        "email_attributed_revenue": 1_002_811.03,
        "channel_chart_revenue": channel_chart_sum,
        "channel_chart_coverage_pct": 100 * channel_chart_sum / total_revenue,
        "mom_pct": -34.6,
        "yoy_pct": 22.6,
        "source_freshness": REFERENCE_AS_OF,
    }
    stores = [
        {"location": "Central", "orders": 184, "revenue": 1_140_489.49, "mom_pct": 26.8},
        {"location": "Quarry Bay", "orders": 135, "revenue": 959_061.92, "mom_pct": -31.1},
        {"location": "Online Store", "orders": 84, "revenue": 420_178.15, "mom_pct": -33.5},
        {"location": "Others", "orders": 1, "revenue": 800.0, "mom_pct": -99.4},
    ]
    google_campaigns = [
        {"campaign": "HK | Search | Brand", "classification": "Brand", "status": "Enabled", "spend": 4_210.0, "clicks": 2_016, "impressions": 15_570, "purchases": 12, "purchase_value": 78_420.0, "roas": 18.63, "budget_pacing_pct": 94, "landing_page": "/"},
        {"campaign": "HK | PMax | New Arrivals", "classification": "Performance Max", "status": "Enabled", "spend": 7_840.0, "clicks": 3_414, "impressions": 211_500, "purchases": 11, "purchase_value": 62_993.65, "roas": 8.03, "budget_pacing_pct": 108, "landing_page": "/collections/new-arrivals"},
        {"campaign": "HK | Search | Competitor", "classification": "Competitor", "status": "Enabled", "spend": 2_903.35, "clicks": 1_121, "impressions": 30_820, "purchases": 2, "purchase_value": 7_500.0, "roas": 2.58, "budget_pacing_pct": 121, "landing_page": "/collections/designer-bags"},
    ]
    meta_campaigns = [
        {"campaign": "Focus (Sales)", "status": "Active", "spend": 10_885.0, "reach": 118_420, "impressions": 221_700, "frequency": 1.87, "clicks": 3_312, "ctr": 1.49, "purchases": 17, "purchase_value": 84_986.32, "roas": 7.81, "creative": "So Low I'm Sold"},
        {"campaign": "HULA Awareness", "status": "Active", "spend": 3_110.25, "reach": 55_880, "impressions": 163_800, "frequency": 2.93, "clicks": 2_240, "ctr": 1.37, "purchases": 0, "purchase_value": 0.0, "roas": 0.0, "creative": "HULA Brand Story"},
        {"campaign": "Bags Retargeting", "status": "Active", "spend": 1_450.0, "reach": 8_600, "impressions": 35_500, "frequency": 4.13, "clicks": 210, "ctr": 0.59, "purchases": 0, "purchase_value": 0.0, "roas": 0.0, "creative": "New Arrivals Bags"},
    ]
    session_behaviour = [
        {"event": "Session start", "count": 57_585, "share_of_session_starts_pct": 100.00},
        {"event": "Page view", "count": 56_127, "share_of_session_starts_pct": 97.47},
        {"event": "View item", "count": 35_081, "share_of_session_starts_pct": 60.92},
        {"event": "Add to cart", "count": 851, "share_of_session_starts_pct": 1.48},
    ]
    online_summary = {
        "add_to_carts": 1_459,
        "orders": 84,
        "conversion_rate_pct": 0.15,
        "revenue": 420_178.15,
        "source": "Shopify Online Store summary",
        "note": "This is a separate Shopify summary. It cannot be appended to the analytics event rows as one funnel.",
    }
    klaviyo = [
        {"name": "NEW IN — 25 July", "type": "Campaign", "recipients": 9_842, "open_rate": 45.2, "click_rate": 2.8, "orders": 24, "revenue": 134_812.0, "revenue_per_recipient": 13.70, "status": "Sent"},
        {"name": "Chanel Drop", "type": "VIP Campaign", "recipients": 246, "open_rate": 71.4, "click_rate": 7.1, "orders": 2, "revenue": 7_500.0, "revenue_per_recipient": 30.49, "status": "Sent"},
        {"name": "Hermès Drop", "type": "VIP Campaign", "recipients": 274, "open_rate": 69.0, "click_rate": 6.8, "orders": 0, "revenue": 0.0, "revenue_per_recipient": 0.0, "status": "Sent"},
        {"name": "Welcome Series", "type": "Flow", "recipients": 1_420, "open_rate": 58.1, "click_rate": 5.4, "orders": 19, "revenue": 83_220.0, "revenue_per_recipient": 58.61, "status": "Live"},
        {"name": "Post-Purchase", "type": "Flow", "recipients": 912, "open_rate": 64.3, "click_rate": 4.8, "orders": 21, "revenue": 92_110.0, "revenue_per_recipient": 100.99, "status": "Live"},
    ]
    technical_issues = [
        {"severity": "High", "issue": "Broken product links in editorial", "affected_urls": 7, "evidence": "Fixture crawl found article links returning 404 or unavailable product templates.", "action": "Replace with available collection links and add a weekly availability check.", "owner": "Marketing Operator"},
        {"severity": "High", "issue": "Duplicate meta descriptions", "affected_urls": 19, "evidence": "The same description appears on several designer collections.", "action": "Create unique collection copy based on inventory and search intent.", "owner": "Marketing Operator"},
        {"severity": "Medium", "issue": "Missing image alt text", "affected_urls": 42, "evidence": "Product/editorial images have blank alt attributes in the fixture crawl.", "action": "Draft descriptive, non-keyword-stuffed alt text; review before Shopify update.", "owner": "Content Editor"},
        {"severity": "Medium", "issue": "Slow mobile LCP on product template", "affected_urls": 12, "evidence": "Fixture PageSpeed mobile LCP is 4.1 seconds on priority product URLs.", "action": "Audit hero image size and theme blocking resources with the Shopify developer.", "owner": "Technical Partner"},
    ]
    catalogue_issues = [
        {"product": "Chanel Classic Flap", "designer": "Chanel", "value_hkd": 48_000, "issue": "Missing SEO description", "inventory": "1 available", "traffic": 1_820, "conversion_rate": 0.0, "recommendation": "Draft a specific description and verify condition/authentication facts."},
        {"product": "Loewe Raffia Basket", "designer": "Loewe", "value_hkd": 6_800, "issue": "Used in an active ad but unavailable", "inventory": "0 available", "traffic": 940, "conversion_rate": 0.0, "recommendation": "Remove from creative rotation and link to the available raffia collection."},
        {"product": "Gucci Horsebit Loafers", "designer": "Gucci", "value_hkd": 5_200, "issue": "Missing image alt text", "inventory": "1 available", "traffic": 460, "conversion_rate": 0.43, "recommendation": "Add factual image descriptions after editorial review."},
        {"product": "Prada Nylon Shoulder Bag", "designer": "Prada", "value_hkd": 9_400, "issue": "Inconsistent product type", "inventory": "1 available", "traffic": 78, "conversion_rate": 0.0, "recommendation": "Normalize taxonomy to Shoulder Bags and verify feed mapping."},
    ]
    merchant = [
        {"status": "Approved", "products": 1_124, "share_pct": 91.8, "action": "No action"},
        {"status": "Pending", "products": 38, "share_pct": 3.1, "action": "Monitor processing"},
        {"status": "Disapproved", "products": 62, "share_pct": 5.1, "action": "Review availability and price mismatch fixtures"},
    ]
    customer_segments = [
        {"segment": "VIP / high value", "customers": 94, "revenue": 812_440, "aov": 9_842, "repeat_rate": 78.2, "activation": "Early access; no automatic export"},
        {"segment": "Active repeat", "customers": 176, "revenue": 890_210, "aov": 6_350, "repeat_rate": 63.4, "activation": "Designer affinity drops"},
        {"segment": "Recent first-time", "customers": 167, "revenue": 532_880, "aov": 4_930, "repeat_rate": 0.0, "activation": "Second-purchase education"},
        {"segment": "At risk", "customers": 318, "revenue": 164_280, "aov": 5_210, "repeat_rate": 24.1, "activation": "WE MISS YOU brief; verify suppression"},
        {"segment": "Subscriber, no purchase", "customers": 2_814, "revenue": 0, "aov": 0, "repeat_rate": 0.0, "activation": "Welcome education; consent required"},
    ]
    reconciliation = [
        reconciliation_row("Total commerce revenue", 2_490_383.0, 2_490_383.0, tolerance_pct=0.1, reason="Exact fixture reference.", source_formula="Shopify booked sales fixture"),
        reconciliation_row("Store/location revenue sum", 2_490_383.0, store_sum, tolerance_pct=0.1, reason="Agency store table exceeds its headline by HK$30,146.56; likely mapping or excluded-order issue.", source_formula="Sum of Central + Quarry Bay + Online + Others"),
        reconciliation_row("Orders", 409.0, 404.0, tolerance_pct=0.1, reason="Five headline orders are not allocated to the displayed stores.", source_formula="Sum of report store order rows"),
        reconciliation_row("Revenue represented by channel chart", total_revenue, channel_chart_sum, tolerance_pct=0.1, reason="The four displayed channel rows represent only 53.69% of headline commerce revenue and are not mutually exclusive because attribution windows differ.", source_formula="Email + Google Ads + Direct + Meta rows"),
        reconciliation_row("Google Ads spend", 14_953.35, 14_953.35, tolerance_pct=0.5, reason="Exact fixture reference.", source_formula="Google Ads cost, account timezone"),
        reconciliation_row("Meta purchase value", 84_986.32, 84_986.32, tolerance_pct=0.5, reason="Exact fixture reference; the supplied report states a seven-day attribution window.", source_formula="Meta platform-attributed purchase value"),
        reconciliation_row("Blended paid ROAS", 7.7, blended_roas(google_value + meta_value, paid_spend), tolerance_pct=1.0, reason="Rounding from channel values.", source_formula="(Google + Meta attributed revenue) / paid spend"),
    ]
    channel_revenue = [
        {"channel": "Email", "reported_revenue": 1_002_811.03, "spend": 0.0, "source": "Klaviyo", "attribution_window": "90 days", "classification": "Platform attributed — overlapping"},
        {"channel": "Google Ads", "reported_revenue": 148_913.65, "spend": 14_953.35, "source": "Google Ads", "attribution_window": "Not stated in report", "classification": "Platform attributed — overlapping"},
        {"channel": "Direct", "reported_revenue": 100_372.87, "spend": 0.0, "source": "Agency dashboard", "attribution_window": "Not stated in report", "classification": "Definition requires confirmation"},
        {"channel": "Meta", "reported_revenue": 84_986.32, "spend": 15_445.25, "source": "Meta Ads", "attribution_window": "7 days", "classification": "Platform attributed — overlapping"},
    ]
    data_quality_findings = [
        {"severity": "Critical", "finding": "Location revenue does not reconcile", "evidence": "Displayed location rows exceed headline revenue by HK$30,146.56 and allocate five fewer orders.", "required_fix": "Use one order population and document location/exclusion rules.", "owner": "Data owner"},
        {"severity": "Critical", "finding": "Channel chart is incomplete and overlapping", "evidence": f"Four rows total HK${channel_chart_sum:,.2f}, only {100 * channel_chart_sum / total_revenue:.2f}% of headline revenue; Klaviyo uses 90 days and Meta seven days.", "required_fix": "Present these as separate attribution views, never a mutually exclusive revenue split.", "owner": "Marketing analyst"},
        {"severity": "High", "finding": "HK$182 is not proven paid CAC", "evidence": "HK$30,398.60 paid spend / all 167 new Shopify customers = HK$182.03, including store and potentially organic customers.", "required_fix": "Rename it as an efficiency proxy until paid-acquired customer identity is available.", "owner": "Metric owner"},
        {"severity": "High", "finding": "July report contains an August item", "evidence": "A campaign dated 1 August appears inside the 1–31 July reporting pack.", "required_fix": "Filter campaign activity by send/event timestamp in HKT and disclose late-arriving data separately.", "owner": "Reporting owner"},
        {"severity": "High", "finding": "Store conversion is shown as 0.00%", "evidence": "Physical stores have orders but naturally do not have web sessions or add-to-cart events.", "required_fix": "Show physical-store web conversion as not applicable; use footfall only if a reliable denominator exists.", "owner": "Metric owner"},
        {"severity": "High", "finding": "Unsupported combined online funnel", "evidence": "The report states 57,585 session starts, 35,081 view-item events and 851 analytics add-to-cart events; it does not state 98,280 sessions or 347 checkouts.", "required_fix": "Keep analytics event incidence separate from the Shopify online summary and show checkout as unavailable.", "owner": "Marketing analyst"},
    ]
    return {
        "meta": {
            "mode": "fixture",
            "period": REFERENCE_PERIOD,
            "generated_at": REFERENCE_AS_OF,
            "timezone": "Asia/Hong_Kong",
            "currency": "HKD",
            "notice": "Agency-report parity fixture. These values are not a live HULA connection.",
        },
        "executive": executive,
        "daily": [],
        "daily_status": "A complete report-sourced daily series was not available in the attached PDF; no synthetic series is generated.",
        "stores": stores,
        "session_behaviour": session_behaviour,
        "online_summary": online_summary,
        "funnel": [],
        "channel_revenue": channel_revenue,
        "data_quality_findings": data_quality_findings,
        "customer_segments": customer_segments,
        "google_campaigns": google_campaigns,
        "meta_campaigns": meta_campaigns,
        "seo_opportunities": _seo_opportunities(),
        "technical_issues": technical_issues,
        "catalogue_issues": catalogue_issues,
        "klaviyo": klaviyo,
        "gbp": [
            {"location": "Central", "views": 18_420, "website_clicks": 1_120, "calls": 164, "directions": 1_840, "rating": 4.8, "reviews": 61, "unanswered": 2},
            {"location": "Quarry Bay", "views": 11_310, "website_clicks": 704, "calls": 92, "directions": 1_101, "rating": 4.7, "reviews": 31, "unanswered": 1},
        ],
        "merchant": merchant,
        "ai_referrals": [
            {"source": "ChatGPT", "sessions": 134, "engagement_rate": 62.0, "product_views": 48, "add_to_carts": 2, "checkouts": 0, "purchases": 0, "revenue": 0},
            {"source": "Gemini", "sessions": 28, "engagement_rate": 57.1, "product_views": 9, "add_to_carts": 0, "checkouts": 0, "purchases": 0, "revenue": 0},
            {"source": "Claude", "sessions": 11, "engagement_rate": 54.5, "product_views": 4, "add_to_carts": 0, "checkouts": 0, "purchases": 0, "revenue": 0},
        ],
        "experiments": [
            {"name": "Preowned vs Preloved snippet", "hypothesis": "A clearer answer-led title will lift organic CTR.", "baseline": "0.06% CTR", "target": "0.35% CTR", "status": "Proposed", "limitation": "Wait for sufficient impressions; seasonality may affect comparison."},
            {"name": "VIP access vs discount", "hypothesis": "Early access preserves luxury positioning while maintaining conversion.", "baseline": "Current VIP revenue HK$47,450", "target": "+20% revenue per recipient", "status": "Design", "limitation": "Small audience; directional result only."},
        ],
        "reconciliation": reconciliation,
        "report_actions": [
            {"title": "Prioritise top-impression SEO snippet fixes", "owner": "Marketing Operator", "due": "2026-08-14", "status": "Planned"},
            {"title": "Refresh August Meta creative", "owner": "Paid Media Specialist", "due": "2026-08-10", "status": "In progress"},
            {"title": "Confirm Singapore campaign launch", "owner": "Approver / Manager", "due": "2026-08-12", "status": "Awaiting decision"},
            {"title": "Resolve store revenue mapping difference", "owner": "Data Owner", "due": "2026-08-09", "status": "Detected"},
        ],
    }


def demo_dataset() -> dict[str, Any]:
    """Return an isolated copy so Streamlit widgets cannot mutate the fixture."""
    return copy.deepcopy(_build())
