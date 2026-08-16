from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .models import Permission, UserIdentity
from .permissions import has_permission
from .store import OperationalStore
from .ui_common import data_banner, dataframe, hkd_metric, metric, page_header, section, source_badges


def render_seo_opportunities(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Organic growth", "Prioritise SEO work by evidence—not by guesswork.", "Search demand, current position, CTR gap, conversion value, inventory and implementation effort remain visible as separate factors.")
    data_banner(dataset["meta"])
    opportunities = dataset["seo_opportunities"]
    total_impressions = sum(row["impressions"] for row in opportunities)
    total_clicks = sum(row["clicks"] for row in opportunities)
    cols = st.columns(4)
    with cols[0]:
        metric("Priority opportunities", len(opportunities), source="Search Console + Shopify", definition="Fixture rows above the configured review threshold.")
    with cols[1]:
        metric("Impressions represented", f"{total_impressions:,}", source="Search Console fixture", definition="Impressions for these query/page pairs only.")
    with cols[2]:
        metric("Weighted CTR", f"{100 * total_clicks / total_impressions:.2f}%", source="Search Console fixture", definition="Total clicks divided by total impressions for displayed rows.")
    with cols[3]:
        metric("Top score", f"{max(row['score'] for row in opportunities):.1f}/100", source="Transparent rule", definition="Weighted factor score; no hidden AI component.")
    section("Opportunity board")
    for index, row in enumerate(opportunities):
        with st.container(border=True):
            left, middle, right = st.columns([3, 1, 1])
            with left:
                st.subheader(row["query"])
                st.code(row["page"], language=None)
                st.write(row["action"])
            with middle:
                st.metric("Score", f"{row['score']:.1f}")
                st.metric("Position", f"{row['position']:.1f}")
            with right:
                st.metric("Impressions", f"{row['impressions']:,}")
                st.metric("CTR", f"{row['ctr']:.2f}%")
            with st.expander("Why this score?"):
                contributions = row["factor_contributions"]
                contribution_df = pd.DataFrame([{"Factor": key.replace("_", " ").title(), "Contribution": value} for key, value in contributions.items()])
                fig = px.bar(contribution_df, x="Contribution", y="Factor", orientation="h", color_discrete_sequence=["#ff3f98"])
                fig.update_layout(height=300, margin=dict(l=0, r=0, t=5, b=0), showlegend=False, plot_bgcolor="white")
                st.plotly_chart(fig, width="stretch")
                st.caption("Factor contributions sum to the displayed score. Missing factors would be named and remaining weights renormalised.")
            if has_permission(identity.role, Permission.MANAGE_TASKS) and st.button("Create SEO task", key=f"seo_task_{index}"):
                task_id = store.create_task(identity, title=f"SEO: {row['query']}", description=row["action"], problem_type="SEO opportunity", source_system="Google Search Console", source_entity=row["page"], evidence={"query": row["query"], "impressions": row["impressions"], "clicks": row["clicks"], "ctr": row["ctr"], "position": row["position"], "score": row["score"], "factor_contributions": row["factor_contributions"]}, severity="High", recommended_action=row["action"], owner="Marketing", due_date="2026-08-14", success_measure="Measure CTR and qualified sessions after 14 and 30 days.", deduplication_key=f"seo:{row['page']}:{row['query']}:2026-07", data_mode="fixture")
                st.success(f"Task created ({task_id[:8]}…).")


def render_technical_seo(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Site health", "Turn technical SEO findings into a small, owned queue.", "Crawler and PageSpeed work is designed as a background job with host limits, robots awareness, retries and cancellation—not a long Streamlit button request.")
    data_banner(dataset["meta"])
    issues = dataset["technical_issues"]
    cols = st.columns(4)
    with cols[0]: metric("Priority issues", len(issues), source="Fixture crawl", definition="Grouped issue types, not raw URL-row count.")
    with cols[1]: metric("Affected URL instances", sum(item["affected_urls"] for item in issues), source="Fixture crawl", definition="May include the same URL in more than one issue group.")
    with cols[2]: metric("Mobile LCP", "4.1 s", source="PageSpeed fixture", definition="Lab LCP for priority product template; live field/lab context must be retained.")
    with cols[3]: metric("Crawl mode", "Rate-limited", source="Worker policy", definition="1 request/second, HULA host only, maximum pages configurable.")
    section("Prioritised findings")
    dataframe(issues, height=280)
    section("Template PageSpeed snapshot", "Fixture only")
    pagespeed = [
        {"Template": "Homepage", "Mobile performance": 72, "LCP s": 3.1, "INP ms": 180, "CLS": 0.08, "Status": "Needs improvement"},
        {"Template": "Collection", "Mobile performance": 65, "LCP s": 3.8, "INP ms": 210, "CLS": 0.11, "Status": "Needs improvement"},
        {"Template": "Product", "Mobile performance": 58, "LCP s": 4.1, "INP ms": 260, "CLS": 0.14, "Status": "Poor"},
        {"Template": "Journal", "Mobile performance": 76, "LCP s": 2.9, "INP ms": 160, "CLS": 0.05, "Status": "Needs improvement"},
    ]
    dataframe(pagespeed)
    if has_permission(identity.role, Permission.MANAGE_TASKS):
        if st.button("Queue controlled priority crawl", type="primary"):
            key = f"priority-crawl:{date.today().isoformat()}:fixture"
            job_id = store.enqueue_job(identity, "site_crawl", {"base_url": "https://thehula.com", "scope": "priority_urls", "max_pages": 50, "requests_per_second": 1, "respect_robots": True, "data_mode": "fixture"}, idempotency_key=key)
            st.success(f"Job queued ({job_id[:8]}…). No crawl runs inside this Streamlit request; the worker is not started automatically in demo mode.")


def render_catalogue_seo(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Catalogue quality", "Make valuable inventory easier to discover and safer to promote.", "Recommendations connect product availability, metadata, traffic and paid use. They remain drafts until a human verifies the live product.")
    data_banner(dataset["meta"])
    issues = dataset["catalogue_issues"]
    cols = st.columns(4)
    with cols[0]: metric("Items needing review", len(issues), source="Shopify fixture", definition="Illustrative catalogue quality records.")
    with cols[1]: hkd_metric("Inventory value represented", sum(item["value_hkd"] for item in issues), source="Shopify fixture", definition="Listed value, not realized margin.")
    with cols[2]: metric("Unavailable in marketing", sum("unavailable" in item["issue"].lower() for item in issues), source="Shopify + paid fixture", definition="Must be verified live before any change.")
    with cols[3]: metric("External writes", "OFF", source="Feature flags", definition="No product, collection or metadata change can execute.")
    dataframe(issues, height=310, column_config={"value_hkd": st.column_config.NumberColumn("Value", format="HK$ %.0f"), "conversion_rate": st.column_config.NumberColumn("Conversion", format="%.2f%%")})
    st.info("Authentication and condition claims must be reviewed by a named HULA expert and supported with original evidence. The AI may structure a draft but may not invent product facts.")


def render_google_ads(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Paid search", "See spend, value and pacing before proposing a change.", "Google Ads platform attribution is separated from commerce truth. All recommendations are review-only; bidding, budgets and status remain untouched.")
    data_banner(dataset["meta"])
    rows = dataset["google_campaigns"]
    spend = sum(row["spend"] for row in rows)
    value = sum(row["purchase_value"] for row in rows)
    purchases = sum(row["purchases"] for row in rows)
    clicks = sum(row["clicks"] for row in rows)
    impressions = sum(row["impressions"] for row in rows)
    cols = st.columns(5)
    with cols[0]: hkd_metric("Spend", spend, source="Google Ads platform", definition="Cost in the Google Ads account timezone/currency fixture.")
    with cols[1]: hkd_metric("Purchase value", value, source="Google Ads attribution", definition="Platform-attributed conversion value; not booked revenue.")
    with cols[2]: metric("ROAS", f"{value/spend:.2f}x", source="Google Ads attribution", definition="Platform purchase value divided by spend.")
    with cols[3]: metric("Purchases", purchases, source="Google Ads conversion action", definition="Primary purchase conversions; configuration must be confirmed.")
    with cols[4]: metric("CTR", f"{100*clicks/impressions:.2f}%", source="Google Ads", definition="Clicks divided by impressions for displayed campaigns.")
    campaign_df = pd.DataFrame(rows)
    fig = px.scatter(campaign_df, x="spend", y="roas", size="purchase_value", color="budget_pacing_pct", hover_name="campaign", color_continuous_scale=["#6f8e84", "#f6f4f1", "#ff3f98"])
    fig.add_hline(y=5, line_dash="dash", annotation_text="Illustrative 5x review line")
    fig.update_layout(height=390, margin=dict(l=0, r=0, t=15, b=0), plot_bgcolor="white")
    st.plotly_chart(fig, width="stretch")
    dataframe(rows, height=270, column_config={"spend": st.column_config.NumberColumn("Spend", format="HK$ %.2f"), "purchase_value": st.column_config.NumberColumn("Purchase value", format="HK$ %.2f"), "roas": st.column_config.NumberColumn("ROAS", format="%.2fx"), "budget_pacing_pct": st.column_config.ProgressColumn("Pacing", min_value=0, max_value=140, format="%d%%")})
    st.warning("No budget, bid, targeting, conversion, keyword, ad or status mutation is implemented or enabled.")


def render_meta_ads(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Paid social", "Spot creative fatigue and conversion gaps early.", "Frequency, CTR, landing behavior and purchases are reviewed together. The fixture does not prove the Meta account's live attribution window.")
    data_banner(dataset["meta"])
    rows = dataset["meta_campaigns"]
    spend = sum(row["spend"] for row in rows)
    value = sum(row["purchase_value"] for row in rows)
    cols = st.columns(5)
    with cols[0]: hkd_metric("Spend", spend, source="Meta platform", definition="Fixture spend across displayed campaigns.")
    with cols[1]: hkd_metric("Purchase value", value, source="Meta attribution", definition="Platform-attributed value; not commerce truth.")
    with cols[2]: metric("ROAS", f"{value/spend:.2f}x", source="Meta attribution", definition="Platform purchase value divided by spend.")
    with cols[3]: metric("Purchases", sum(row["purchases"] for row in rows), source="Meta purchase action", definition="Attributed purchase actions in the fixture.")
    with cols[4]: metric("Fatigue watch", sum(row["frequency"] >= 3.5 and row["ctr"] < 0.8 for row in rows), source="Deterministic rule", definition="Frequency ≥3.5 and CTR <0.8% in the selected window.")
    fig = px.scatter(pd.DataFrame(rows), x="frequency", y="ctr", size="spend", color="purchases", hover_name="campaign", color_continuous_scale=["#d64848", "#ff3f98", "#6f8e84"])
    fig.add_vline(x=3.5, line_dash="dash", annotation_text="Frequency watch")
    fig.add_hline(y=0.8, line_dash="dash", annotation_text="CTR watch")
    fig.update_layout(height=390, margin=dict(l=0, r=0, t=15, b=0), plot_bgcolor="white")
    st.plotly_chart(fig, width="stretch")
    dataframe(rows, height=260)
    st.warning("All Meta actions are proposals only. Creating or editing an ad, audience, budget or status is not implemented in this release.")


def render_klaviyo(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Lifecycle marketing", "Find the next customer message without creating consent risk.", "Campaign and flow performance is tied to segment purpose, deliverability and inventory. No campaign is sent and no live flow is changed.")
    data_banner(dataset["meta"])
    rows = dataset["klaviyo"]
    campaigns = [row for row in rows if "Campaign" in row["type"]]
    flows = [row for row in rows if row["type"] == "Flow"]
    cols = st.columns(4)
    with cols[0]: hkd_metric("Displayed attributed revenue", sum(row["revenue"] for row in rows), source="Klaviyo fixture", definition="Only displayed rows; not the report's full Klaviyo total.")
    with cols[1]: hkd_metric("Campaign value", sum(row["revenue"] for row in campaigns), source="Klaviyo fixture", definition="Displayed campaign examples only.")
    with cols[2]: hkd_metric("Flow value", sum(row["revenue"] for row in flows), source="Klaviyo fixture", definition="Displayed flow examples only.")
    with cols[3]: metric("No-revenue brand drops", sum(row["revenue"] == 0 and "Campaign" in row["type"] for row in rows), source="Deterministic review", definition="Engagement and revenue should be reviewed together.")
    fig = px.scatter(pd.DataFrame(rows), x="click_rate", y="revenue_per_recipient", size="recipients", color="type", hover_name="name", color_discrete_sequence=["#ff3f98", "#9a8fd8", "#6f8e84"])
    fig.update_layout(height=390, margin=dict(l=0, r=0, t=15, b=0), plot_bgcolor="white", xaxis_title="Click rate (%)", yaxis_title="Revenue / recipient (HKD)")
    st.plotly_chart(fig, width="stretch")
    dataframe(rows, height=300, column_config={"revenue": st.column_config.NumberColumn("Revenue", format="HK$ %.0f"), "revenue_per_recipient": st.column_config.NumberColumn("Revenue/recipient", format="HK$ %.2f"), "open_rate": st.column_config.NumberColumn("Open", format="%.1f%%"), "click_rate": st.column_config.NumberColumn("Click", format="%.1f%%")})
    st.info("Before any audience activation: verify consent, suppression, recent-purchase exclusions and minimum audience size. This release cannot send a message.")


def render_local_marketing(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Local marketing", "Protect trust at every HULA location.", "Store visibility, direction requests and reviews are compared by location. Review replies remain drafts until approved.")
    data_banner(dataset["meta"])
    rows = dataset["gbp"]
    cols = st.columns(4)
    with cols[0]: metric("Profile views", f"{sum(row['views'] for row in rows):,}", source="GBP fixture", definition="Displayed location profile views.")
    with cols[1]: metric("Directions", f"{sum(row['directions'] for row in rows):,}", source="GBP fixture", definition="Direction requests; not verified store visits.")
    with cols[2]: metric("Reviews", sum(row["reviews"] for row in rows), source="GBP fixture", definition="Review count across displayed locations.")
    with cols[3]: metric("Unanswered", sum(row["unanswered"] for row in rows), source="GBP fixture", definition="Requires live review verification before response drafting.")
    dataframe(rows, height=230)
    section("Review response workflow")
    st.markdown("New review → classify service risk → draft specific response → internal review → approval → public reply → verify provider receipt")
    st.warning("Public replies are disabled. The app does not have a Google Business Profile write adapter in this release.")


def render_merchant_feed(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Product feed health", "Keep unique inventory eligible and accurate.", "Product approval, availability and price mismatches are reviewed without replacing HULA's existing feed-management method.")
    data_banner(dataset["meta"])
    rows = dataset["merchant"]
    fig = px.pie(pd.DataFrame(rows), values="products", names="status", color="status", color_discrete_map={"Approved": "#6f8e84", "Pending": "#e5a33b", "Disapproved": "#d64848"}, hole=.58)
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")
    dataframe(rows)
    st.info("Merchant API v1 read connector is represented by a health shell. These counts are fixtures, and no feed/product write is possible.")


def render_ai_discovery(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("AI discovery", "Measure observable AI referrals—nothing private.", "Sessions, engagement and ecommerce actions are classified from referral/source data. The app cannot see prompts or prove why an assistant mentioned HULA.")
    data_banner(dataset["meta"])
    rows = dataset["ai_referrals"]
    cols = st.columns(4)
    with cols[0]: metric("Sessions", sum(row["sessions"] for row in rows), source="GA4 referral fixture", definition="Sessions matching configurable AI referral-source rules.")
    with cols[1]: metric("Product views", sum(row["product_views"] for row in rows), source="GA4 fixture", definition="Observed product-view events from those sessions.")
    with cols[2]: metric("Add to carts", sum(row["add_to_carts"] for row in rows), source="GA4 fixture", definition="Observed add-to-cart events.")
    with cols[3]: hkd_metric("Revenue", sum(row["revenue"] for row in rows), source="GA4 fixture", definition="Observed purchase revenue; zero in the reference fixture.")
    fig = px.bar(pd.DataFrame(rows), x="source", y="sessions", color="engagement_rate", color_continuous_scale=["#f6f4f1", "#ff3f98", "#151515"])
    fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white", coloraxis_colorbar_title="Engagement %")
    st.plotly_chart(fig, width="stretch")
    dataframe(rows)
    st.caption("Referral classification should be versioned because referrer patterns can change. Direct or dark traffic is not relabelled as AI traffic without evidence.")
