from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .demo_data import demo_dataset
from .metrics import format_hkd
from .models import Permission, Role, Signal, UserIdentity
from .permissions import has_permission
from .reporting import csv_export_bundle, monthly_report_pdf
from .signals import detect_business_signals
from .store import OperationalStore
from .ui_common import (
    data_banner,
    dataframe,
    hkd_metric,
    metric,
    page_header,
    section,
    signal_card,
    source_badges,
)


def render_today(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header(
        "Marketing command centre",
        "Know what deserves attention today.",
        "One evidence-backed queue for data risks, performance changes, approvals, deadlines and the next safest action.",
    )
    data_banner(dataset["meta"])
    signals = detect_business_signals(dataset)
    tasks = store.list_tasks()
    approvals = store.list_approvals(status="Pending")
    jobs = store.list_jobs()
    overdue = [task for task in tasks if task.get("due_date") and task["due_date"] < date.today().isoformat() and task.get("status") not in {"Completed", "Cancelled"}]
    cols = st.columns(4)
    with cols[0]:
        metric("Critical signals", sum(item.severity.value == "Critical" for item in signals), source="Deterministic rules", definition="Rules, thresholds and evidence—not an opaque AI score.")
    with cols[1]:
        metric("Open tasks", len([task for task in tasks if task.get("status") not in {"Completed", "Cancelled"}]), source="Operational store", definition="Owned work not yet completed or cancelled.")
    with cols[2]:
        metric("Awaiting approval", len(approvals), source="Approval log", definition="Pending requests; high-risk self-approval is blocked.")
    with cols[3]:
        metric("Overdue", len(overdue), source="Operational store", definition="Open tasks with a due date before today.")

    section("Priority queue", "What changed and what to do")

    def create(signal: Signal) -> str:
        due = (date.today() + timedelta(days=3 if signal.severity.value == "Critical" else 7)).isoformat()
        return store.create_task_from_signal(identity, signal, due_date=due)

    for index, signal in enumerate(signals[:6]):
        signal_card(signal, identity=identity, on_create_task=create, key=f"today_signal_{index}_{signal.deduplication_key}")

    section("Owned work and decisions", "Execution")
    left, right = st.columns(2)
    with left:
        st.markdown("**Tasks due first**")
        dataframe(
            [
                {"Task": task["title"], "Severity": task["severity"], "Owner": task["owner"], "Due": task["due_date"], "Status": task["status"], "Data": task["data_mode"]}
                for task in tasks[:8]
            ],
            height=315,
        )
    with right:
        st.markdown("**Approvals and background work**")
        if approvals:
            dataframe([{"Request": row["summary"], "Risk": row["risk_level"], "Requester": row["requested_by_name"], "Status": row["status"]} for row in approvals], height=180)
        else:
            st.info("No approval is waiting in this local/demo workspace.")
        if jobs:
            dataframe([{"Job": row["job_type"], "Status": row["status"], "Progress": f"{row['progress_pct']}%", "Requested": row["requested_at"][:16]} for row in jobs[:5]], height=150)
        else:
            st.caption("No background job has been queued.")


def render_executive(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header(
        "Executive overview",
        "One commerce truth. Several attribution views.",
        "Revenue, customers, paid efficiency and risks are separated by source so overlapping platform attribution is never double-counted.",
    )
    data_banner(dataset["meta"])
    values = dataset["executive"]
    cols = st.columns(4)
    with cols[0]:
        hkd_metric("Commerce revenue", values["commerce_revenue"], delta=f"{values['yoy_pct']:+.1f}% YoY", source="Shopify booked revenue", definition="Booked commerce source of truth; excludes attribution claims.")
    with cols[1]:
        hkd_metric("Paid-media spend", values["paid_spend"], delta=f"{values['mom_pct']:+.1f}% revenue MoM", source="Google + Meta spend", definition="Media cost only; agency fees are not included.")
    with cols[2]:
        metric("Blended paid ROAS", f"{values['blended_roas']:.2f}x", source="Platform attribution", definition="Google + Meta attributed revenue divided by Google + Meta spend.")
    with cols[3]:
        metric("MER", f"{values['mer']:.1f}x", source="Shopify / paid spend", definition="Shopify net revenue divided by total paid-media spend.")
    cols = st.columns(4)
    with cols[0]:
        metric("Orders", f"{values['orders']:,}", source="Shopify", definition="Included commerce orders under the current fixture definition.")
    with cols[1]:
        hkd_metric("Average order value", values["aov"], source="Shopify", definition="Commerce revenue divided by orders; report input is retained for parity.")
    with cols[2]:
        metric("New customers", f"{values['new_customers']:,}", source="Shopify", definition="Customers whose first included order falls in the selected period.")
    with cols[3]:
        hkd_metric("Historical realized CLV", values["historical_realized_clv"], source="Shopify historical", definition="Historical average realized revenue—not predictive lifetime value.")

    section("Revenue and spend over the month", "Commerce source of truth")
    daily = pd.DataFrame(dataset["daily"])
    if daily.empty:
        st.info(dataset.get("daily_status") or "No complete report-sourced daily series is available.")
    else:
        daily["date"] = pd.to_datetime(daily["date"])
        fig = go.Figure()
        fig.add_trace(go.Bar(x=daily["date"], y=daily["commerce_revenue"], name="Shopify commerce revenue", marker_color="#6842d8"))
        fig.add_trace(go.Scatter(x=daily["date"], y=daily["google_spend"] + daily["meta_spend"], name="Paid spend", line=dict(color="#ff4f9a", width=3), yaxis="y2"))
        fig.update_layout(margin=dict(l=0, r=0, t=25, b=0), height=390, legend=dict(orientation="h"), yaxis=dict(title="Revenue (HKD)"), yaxis2=dict(title="Spend (HKD)", overlaying="y", side="right", showgrid=False), plot_bgcolor="white")
        st.plotly_chart(fig, width="stretch")

    section("Attribution views", "Do not add these together")
    attr = [{"View": "Shopify booked commerce", "Revenue (HKD)": values["commerce_revenue"], "Meaning": "Booked source of truth — no attribution window"}]
    attr.extend({"View": row["channel"], "Revenue (HKD)": row["reported_revenue"], "Meaning": f"{row['source']} · {row['attribution_window']} · {row['classification']}"} for row in dataset["channel_revenue"])
    attr_df = pd.DataFrame(attr)
    fig = px.bar(attr_df, x="View", y="Revenue (HKD)", color="View", color_discrete_sequence=["#151515", "#6f8e84", "#ff3f98", "#9a8fd8", "#c8aa82"])
    fig.update_layout(showlegend=False, height=350, margin=dict(l=0, r=0, t=15, b=0), plot_bgcolor="white")
    st.plotly_chart(fig, width="stretch")
    dataframe(attr)

    section("Location performance", "Shopify / POS")
    dataframe(dataset["stores"], column_config={"revenue": st.column_config.NumberColumn("Revenue", format="HK$ %.2f"), "mom_pct": st.column_config.NumberColumn("MoM", format="%.1f%%")})

    section("Reconciliation gate", "Data quality")
    dataframe(dataset["reconciliation"], height=280)
    st.warning("The supplied report's store rows exceed the headline revenue by HK$30,146.56 and allocate five fewer orders. This must be explained before July is treated as a live baseline.")


def render_revenue_customers(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header(
        "Revenue and customer intelligence",
        "See who buys, where value is created, and where the journey leaks.",
        "Commerce, funnel and privacy-safe customer segments are shown together without pretending that unavailable identity links exist.",
    )
    data_banner(dataset["meta"])
    values = dataset["executive"]
    cols = st.columns(4)
    with cols[0]:
        hkd_metric("Gross sales", values["gross_sales"], source="Shopify fixture", definition="Sales before discounts and refunds under the fixture definition.")
    with cols[1]:
        hkd_metric("Net revenue", values["net_revenue"], source="Shopify fixture", definition="Commerce amount after included discounts/refunds; tax and shipping treatment must be signed off.")
    with cols[2]:
        hkd_metric("Refunds", values["refunds"], source="Shopify fixture", definition="Refund value assigned to the fixture period.")
    with cols[3]:
        metric("Repeat revenue share", f"{values['repeat_revenue_share']:.1f}%", source="Shopify fixture", definition="Revenue from customers classified as returning under the chosen definition.")

    section("Commerce by location")
    stores = pd.DataFrame(dataset["stores"])
    fig = px.bar(stores, x="location", y="revenue", color="mom_pct", color_continuous_scale=["#d64848", "#f6f4f1", "#6f8e84"], color_continuous_midpoint=0)
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white", coloraxis_colorbar_title="MoM %")
    st.plotly_chart(fig, width="stretch")

    section("Online behaviour", "Analytics events and Shopify summary kept separate")
    left, right = st.columns(2)
    with left:
        st.markdown("**Analytics event incidence**")
        dataframe(dataset["session_behaviour"])
        st.caption("These report rows are not asserted to be unique-user funnel transitions.")
    with right:
        st.markdown("**Shopify Online Store summary**")
        summary = dataset["online_summary"]
        dataframe([{"Add to carts": summary["add_to_carts"], "Online orders": summary["orders"], "Conversion rate": summary["conversion_rate_pct"], "Checkout count": "Unavailable", "Revenue": summary["revenue"]}])
        st.caption(summary["note"])

    section("Privacy-safe customer segments", "Configurable RFM and lifecycle logic")
    dataframe(dataset["customer_segments"], height=290, column_config={"revenue": st.column_config.NumberColumn("Revenue", format="HK$ %.0f"), "aov": st.column_config.NumberColumn("AOV", format="HK$ %.0f"), "repeat_rate": st.column_config.NumberColumn("Repeat rate", format="%.1f%%")})
    st.info("Audience activation is disabled. Any future export must verify consent, suppression, minimum audience size and the exact segment-definition version.")


def _load_trends(root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = root / "data" / "latest_snapshot.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], {"mode": "unavailable"}
    trends = payload.get("trends") or []
    ordered = sorted(trends, key=lambda row: float(row.get("hula_opportunity_score") or row.get("confidence_score") or row.get("confidence") or 0), reverse=True)
    return ordered, payload.get("meta") or {}


def render_trend_radar(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity, root: Path) -> None:
    page_header(
        "Trend radar handoff",
        "Turn approved fashion evidence into governed marketing work.",
        "This summary reads the existing Trend Intelligence snapshot. The full evidence and methodology remain in the original app.",
    )
    trends, meta = _load_trends(root)
    source_badges("Existing Trend Intelligence", mode="fixture" if str(meta.get("mode")) != "live" else "live")
    catalogue_source = str(meta.get("catalogue_source", "unknown"))
    if "demo" in catalogue_source.lower() or str(meta.get("mode", "")).lower() != "live":
        st.warning(f"Trend snapshot mode: {meta.get('mode', 'unknown')}; catalogue source: {catalogue_source}. Product matches from demo inventory are non-actionable.")
    if not trends:
        st.info("No trend snapshot is available. Run the existing Trend Intelligence app independently.")
        return
    for index, trend in enumerate(trends[:10]):
        name = str(trend.get("name") or trend.get("trend") or "Unnamed trend")
        score = float(trend.get("hula_opportunity_score") or trend.get("confidence_score") or trend.get("confidence") or 0)
        if score <= 1:
            score *= 100
        evidence = trend.get("evidence") or trend.get("evidence_rows") or []
        with st.container(border=True):
            cols = st.columns([3, 1, 1])
            with cols[0]:
                st.subheader(name)
                st.write(trend.get("summary") or trend.get("reason") or "Open Trend Intelligence for the complete evidence trail.")
            with cols[1]:
                st.metric("Opportunity", f"{score:.0f}/100")
            with cols[2]:
                st.metric("Evidence rows", len(evidence) if isinstance(evidence, list) else "—")
            st.caption(f"Decision: {trend.get('decision') or trend.get('recommendation_tier') or 'Review'} · Data remains governed by Trend Intelligence methodology {meta.get('methodology_version', meta.get('methodology', 'unknown'))}.")
            if has_permission(identity.role, Permission.MANAGE_CAMPAIGNS):
                left, right = st.columns(2)
                with left:
                    if st.button("Send to Campaign Planner", key=f"trend_campaign_{index}"):
                        campaign_id = store.create_campaign(identity, name=f"Trend opportunity — {name}", objective="Validate and activate an evidence-backed trend", audience="To be defined after inventory and customer evidence review", geography="Hong Kong", channels=["Content", "Google Ads", "Meta Ads", "Klaviyo"], owner=identity.display_name, source_trend=name, products="Verify live Shopify availability before selection")
                        st.success(f"Campaign draft created ({campaign_id[:8]}…). No external system was changed.")
                with right:
                    if has_permission(identity.role, Permission.MANAGE_CONTENT) and st.button("Send to Content Planner", key=f"trend_content_{index}"):
                        content_id = store.create_content_item(identity, title=f"HULA perspective: {name}", content_type="Trend report", owner=identity.display_name, business_objective="Connect fashion intelligence to available HULA inventory", audience="Luxury resale shoppers", primary_keyword=name, search_intent="Inspirational / commercial", related_products="Live inventory verification required", source_evidence=[{"trend": name, "snapshot_generated_at": meta.get("generated_at"), "data_mode": meta.get("mode")}])
                        st.success(f"Content idea created ({content_id[:8]}…).")
            else:
                st.caption(f"The {identity.role.value} role can review but cannot create campaign/content records.")


def render_reports(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header(
        "Reports and exports",
        "Replace the screenshot PDF with a governed monthly report.",
        "Generate a structured management document with attribution notes, data-quality warnings, owners and deadlines.",
    )
    data_banner(dataset["meta"])
    commentary = st.text_area("Executive commentary", value="July remained seasonally softer month on month while year-on-year commerce revenue improved. Before this fixture becomes a trusted baseline, reconcile the store/location total and five unallocated orders.", height=150)
    version = st.text_input("Report version", value="July 2026 · Draft 1")
    can_approve = identity.role in {Role.APPROVER, Role.ADMINISTRATOR}
    approved = st.checkbox("Mark this export approved for distribution", disabled=not can_approve)
    if not can_approve:
        st.caption("Only an Approver / Manager or Administrator can mark a report approved.")
    pdf = monthly_report_pdf(dataset, commentary=commentary, approved=approved, version=version)
    csv_bundle = csv_export_bundle(dataset)
    cols = st.columns(2)
    with cols[0]:
        st.download_button("Download structured PDF", data=pdf, file_name="HULA_Marketing_Operations_July_2026.pdf", mime="application/pdf", width="stretch")
    with cols[1]:
        st.download_button("Download source tables (ZIP)", data=csv_bundle, file_name="HULA_Marketing_Operations_July_2026_tables.zip", mime="application/zip", width="stretch")
    st.caption("The PDF is generated from stored records, not screenshots. It remains clearly labelled as fixture data until authenticated source syncs reconcile.")

    section("Report contents", "Required management pack")
    dataframe([
        {"Section": "Executive Summary", "Status": "Implemented", "Source": "Governed metric layer"},
        {"Section": "Shopify Revenue & Customers", "Status": "Implemented with fixture", "Source": "Shopify/POS"},
        {"Section": "Google / Meta / Klaviyo / GBP", "Status": "Implemented with fixture", "Source": "Platform attribution"},
        {"Section": "Organic & AI referrals", "Status": "Implemented with fixture", "Source": "Search Console / GA4"},
        {"Section": "Actions, risks and owners", "Status": "Implemented", "Source": "Operational store"},
        {"Section": "Data-quality appendix", "Status": "Implemented", "Source": "Reconciliation rules"},
    ])
    section("Reconciliation before distribution", "Control")
    dataframe(dataset["reconciliation"], height=300)
