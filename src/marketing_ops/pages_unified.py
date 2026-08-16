from __future__ import annotations

import hashlib
import html
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .campaign_ops import (
    campaign_checklist,
    campaign_tasks,
    create_campaign_tasks,
    readiness_summary,
)
from .config import MarketingSettings
from .connectors.base import Connector
from .metric_dictionary import metric_rows
from .models import ApprovalStatus, Permission, RiskLevel, Role, TaskStatus, UserIdentity
from .pages_overview import _load_trends
from .permissions import has_permission, permission_matrix_rows
from .reporting import csv_export_bundle, monthly_report_pdf
from .signals import detect_business_signals
from .store import OperationalStore
from .ui_common import (
    data_banner,
    dataframe,
    kpi_card,
    page_header,
    reporting_controls,
    section,
    section_copy,
    source_badges,
    trust_row,
    workflow_status,
)


PALETTE = ["#6842d8", "#ff4f9a", "#2f8f83", "#ff786f", "#f1b947", "#9b6ab0"]
DONE_STATES = {"Completed", "Implemented", "Approved", "Cancelled"}


def _hkd(value: float, decimals: int = 0) -> str:
    return f"HK${value:,.{decimals}f}"


def _subnav(label: str, options: list[str], *, key: str) -> str:
    return st.radio(label, options, horizontal=True, key=key)


def _plot_style(fig: go.Figure, *, height: int = 350) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=24, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#ffffff",
        font=dict(family="Avenir Next, Inter, sans-serif", color="#5f4566"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="#321641", font_color="#ffffff"),
    )
    fig.update_xaxes(gridcolor="#f1e7f0", zeroline=False)
    fig.update_yaxes(gridcolor="#f1e7f0", zeroline=False)
    return fig


def _create_signal_task(store: OperationalStore, identity: UserIdentity, signal: Any) -> str:
    due = date.today() + timedelta(days=3 if signal.severity.value == "Critical" else 7)
    return store.create_task_from_signal(identity, signal, due_date=due.isoformat())


def _signal_queue(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity, *, limit: int = 5) -> None:
    signals = detect_business_signals(dataset)[:limit]
    for index, signal in enumerate(signals):
        with st.container(border=True):
            left, right = st.columns([4, 1.2])
            with left:
                st.markdown(
                    f'<div class="signal-{signal.severity.value.lower()}">'
                    f'<div class="signal-meta">{html.escape(signal.severity.value)} · {html.escape(signal.source_system)} · {html.escape(signal.owner_role.value)}</div>'
                    f'<div class="signal-head">{html.escape(signal.title)}</div></div>',
                    unsafe_allow_html=True,
                )
                st.write(signal.evidence)
                st.caption(f"Next: {signal.recommended_action}")
            with right:
                st.write("")
                if has_permission(identity.role, Permission.MANAGE_TASKS):
                    if st.button("Add to workboard", key=f"unified_signal_{index}_{signal.deduplication_key}", type="primary", width="stretch"):
                        task_id = _create_signal_task(store, identity, signal)
                        st.success(f"Task ready · {task_id[:8]}")
                else:
                    st.caption("Review only")


def render_home(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity, root: Path) -> None:
    del root  # Trend Intelligence remains available from Work → Content & SEO.
    page_header(
        "Administrator overview",
        "HULA at a glance.",
        "Commercial performance, the few issues that matter now, and the work already moving—without the technical detail unless you open it.",
    )
    data_banner(dataset["meta"])
    reporting_controls(dataset["meta"], key="admin_overview")

    values = dataset["executive"]
    critical_findings = sum(row["severity"] == "Critical" for row in dataset["data_quality_findings"])
    open_tasks = [task for task in store.list_tasks() if task.get("status") not in DONE_STATES]
    pending = store.list_approvals(status="Pending")
    cols = st.columns(4)
    with cols[0]:
        kpi_card(
            "Total sales",
            _hkd(values["commerce_revenue"]),
            source="Shopify / POS",
            definition="Booked commerce source of truth; attribution claims are kept separate.",
            delta=f"{values['yoy_pct']:+.1f}% year on year",
            tone="violet",
        )
    with cols[1]:
        kpi_card(
            "Orders",
            f"{values['orders']:,}",
            source="Shopify / POS",
            definition="Included orders under the current commerce definition.",
            delta=f"AOV {_hkd(values['aov'])}",
            tone="pink",
        )
    with cols[2]:
        kpi_card(
            "Paid-media spend",
            _hkd(values["paid_spend"]),
            source="Google + Meta",
            definition="Media cost only. Platform-attributed value remains separate from booked revenue.",
            delta=f"Platform ROAS {values['blended_roas']:.2f}x",
            tone="teal",
        )
    with cols[3]:
        kpi_card(
            "Open actions",
            str(len(open_tasks)),
            source="Workboard",
            definition="Tasks not completed or cancelled, with a named owner and due date.",
            delta=f"{len(pending)} awaiting approval · {critical_findings} data warning(s)",
            tone="coral",
            warning=bool(critical_findings or pending),
        )

    section("Performance snapshot", "Sales")
    left, right = st.columns([1.85, 1])
    with left:
        stores = pd.DataFrame(dataset["stores"])
        fig = px.bar(
            stores,
            x="location",
            y="revenue",
            color="location",
            color_discrete_sequence=PALETTE,
            text_auto=".3s",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False)
        st.plotly_chart(_plot_style(fig, height=300), width="stretch")
    with right:
        st.markdown("**Customer pulse**")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("New customers", f"{values['new_customers']:,}")
            st.metric("Repeat revenue", f"{values['repeat_revenue_share']:.1f}%")
        with c2:
            st.metric("Repeat customers", f"{values['repeat_customers']:,}")
            st.metric("Realized CLV", f"HK${values['historical_realized_clv'] / 1_000:.1f}k")
        st.caption("Customer metrics use Shopify commerce definitions. Platform attribution is not added to sales.")

    section("Priority actions", "Today")
    section_copy("Only the highest-impact signals appear here. Open Work for evidence, ownership, approvals and the full queue.")
    _signal_queue(dataset, store, identity, limit=3)

    campaigns = store.list_campaigns()
    section("Work in motion", "Campaigns")
    if not campaigns:
        st.info("No campaign is in progress. Create one from Work when it has a clear commercial objective.")
    else:
        rows = []
        for campaign in campaigns[:4]:
            tasks = campaign_tasks(store, campaign["id"])
            readiness = readiness_summary(tasks)
            rows.append(
                {
                    "Campaign": campaign["name"],
                    "Market": campaign["geography"],
                    "Status": campaign["status"],
                    "Readiness": f"{readiness['pct']}%",
                    "Owner": campaign["owner"],
                }
            )
        dataframe(rows, height=220)


def render_viewer_overview(dataset: dict[str, Any], identity: UserIdentity) -> None:
    """Single, deliberately read-only view for HULA leadership and sales."""

    page_header(
        "Business overview",
        "HULA performance at a glance.",
        "Sales, customers and the most important changes—without campaign controls, integrations or technical administration.",
    )
    data_banner(dataset["meta"])
    reporting_controls(dataset["meta"], key="viewer_overview")
    values = dataset["executive"]
    cols = st.columns(4)
    with cols[0]:
        kpi_card("Total sales", _hkd(values["commerce_revenue"]), source="Shopify / POS", definition="Booked commerce source of truth.", delta=f"{values['yoy_pct']:+.1f}% year on year", tone="violet")
    with cols[1]:
        kpi_card("Orders", f"{values['orders']:,}", source="Shopify / POS", definition="Included commerce orders.", delta=f"AOV {_hkd(values['aov'])}", tone="pink")
    with cols[2]:
        kpi_card("New customers", f"{values['new_customers']:,}", source="Shopify", definition="Customers whose first included order is in the period.", delta=f"{values['repeat_customers']:,} returning", tone="teal")
    with cols[3]:
        kpi_card("Repeat revenue", f"{values['repeat_revenue_share']:.1f}%", source="Shopify", definition="Share of revenue from returning customers.", delta=f"Realized CLV {_hkd(values['historical_realized_clv'])}", tone="coral")

    section("Sales by location", "Commerce")
    left, right = st.columns([1.75, 1])
    with left:
        stores = pd.DataFrame(dataset["stores"])
        fig = px.bar(stores, x="location", y="revenue", color="location", color_discrete_sequence=PALETTE, text_auto=".3s")
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False)
        st.plotly_chart(_plot_style(fig, height=305), width="stretch")
    with right:
        st.markdown("**Online store**")
        online = dataset["online_summary"]
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Sales", f"HK${online['revenue'] / 1_000:,.0f}k")
            st.metric("Orders", f"{online['orders']:,}")
        with c2:
            st.metric("Add to carts", f"{online['add_to_carts']:,}")
            st.metric("Conversion", f"{online['conversion_rate_pct']:.2f}%")
        st.caption("The location table currently has an unresolved reconciliation difference. The Administrator view contains the evidence.")

    section("What needs attention", "Three items")
    for signal in detect_business_signals(dataset)[:3]:
        with st.container(border=True):
            left, right = st.columns([3.2, 1])
            with left:
                st.markdown(f"**{signal.title}**")
                st.caption(signal.why_it_matters)
            with right:
                st.caption(f"{signal.severity.value} · {signal.owner_role.value}")
                st.write(signal.recommended_action)
    st.caption(f"Signed in as {identity.display_name} · Viewer. This page is read-only.")


def _campaign_hero(campaign: dict[str, Any]) -> None:
    channels = "".join(f"<span>{html.escape(str(channel))}</span>" for channel in campaign.get("channels") or [])
    budget = _hkd(float(campaign.get("budget_hkd") or 0)) if campaign.get("budget_hkd") else "Budget TBD"
    st.markdown(
        '<div class="campaign-hero">'
        f'<h3>{html.escape(campaign["name"])}</h3>'
        f'<p>{html.escape(campaign.get("objective") or "Objective not yet defined")}</p>'
        '<div class="campaign-meta">'
        f'<span>{html.escape(campaign.get("status") or "Draft")}</span>'
        f'<span>{html.escape(campaign.get("geography") or "Geography TBD")}</span>'
        f'<span>{html.escape(str(campaign.get("start_date") or "Start TBD"))}</span>'
        f'<span>{html.escape(budget)}</span>{channels}</div></div>',
        unsafe_allow_html=True,
    )


def _campaign_workroom(store: OperationalStore, identity: UserIdentity) -> None:
    campaigns = store.list_campaigns()
    if not campaigns:
        st.info("No campaign exists yet. Use New campaign to create one.")
        return
    labels = {f"{row['name']} · {row['status']}": row for row in campaigns}
    selected = labels[st.selectbox("Campaign", list(labels), key="unified_campaign_select")]
    _campaign_hero(selected)
    tasks = campaign_tasks(store, selected["id"])
    readiness = readiness_summary(tasks)

    cols = st.columns(4)
    with cols[0]:
        kpi_card("Launch readiness", f"{readiness['pct']}%", source="Campaign gates", definition="Completed checklist steps divided by generated campaign steps.", delta=readiness["label"], tone="violet")
    with cols[1]:
        kpi_card("Checklist steps", str(readiness["total"] or len(campaign_checklist(selected))), source="Workboard", definition="Core controls plus tasks required by the campaign's selected channels.", delta="Generated from campaign scope", tone="pink")
    with cols[2]:
        kpi_card("Blocked", str(readiness["blocked"]), source="Workboard", definition="Rejected or verification-failed steps that stop launch readiness.", delta="Resolve before approval", tone="coral", warning=bool(readiness["blocked"]))
    with cols[3]:
        kpi_card("Owner", str(selected.get("owner") or "Unassigned"), source="Campaign record", definition="One accountable campaign owner; channel specialists retain their task ownership.", delta=str(selected.get("geography") or ""), tone="teal")

    section("Campaign checklist", "Generated, then owned")
    if not tasks:
        preview = campaign_checklist(selected)
        dataframe(
            [{"Stage": row["stage"], "Channel": row["channel"], "What needs to be done": row["task"], "Owner": row["owner"], "Due": row["due_date"], "Launch gate": "Yes" if row["gate"] else "No"} for row in preview],
            height=390,
        )
        if has_permission(identity.role, Permission.MANAGE_TASKS):
            if st.button("Create this campaign workboard", type="primary", key=f"create_checklist_{selected['id']}"):
                created = create_campaign_tasks(store, identity, selected)
                st.success(f"Campaign workboard ready with {len(set(created))} owned steps.")
                st.rerun()
        else:
            st.caption("Only the Administrator can create the checklist.")
        return

    dataframe(
        [{"Task": row["title"].replace(f"{selected['name']} — ", ""), "Stage": row["problem_type"].replace("Campaign / ", ""), "Owner": row["owner"], "Due": row["due_date"], "Status": row["status"], "Severity": row["severity"]} for row in tasks],
        height=360,
    )
    if has_permission(identity.role, Permission.MANAGE_TASKS):
        left, middle, right = st.columns([2.4, 1.2, 1])
        task_prefix = f"{selected['name']} — "
        task_labels = {f"{row['title'].replace(task_prefix, '')} · {row['status']}": row for row in tasks}
        with left:
            task = task_labels[st.selectbox("Update a campaign step", list(task_labels), key="campaign_task_update")]
        with middle:
            allowed_statuses = list(TaskStatus)
            if identity.demo:
                allowed_statuses = [item for item in allowed_statuses if item not in {TaskStatus.APPROVED, TaskStatus.SCHEDULED, TaskStatus.IMPLEMENTED}]
            status = st.selectbox("New status", allowed_statuses, format_func=lambda item: item.value, key="campaign_task_status")
        with right:
            st.write("")
            st.write("")
            rejection_reason = st.text_input("Rejection reason", key="campaign_task_rejection") if status is TaskStatus.REJECTED else ""
            if st.button("Save status", key="campaign_task_save", width="stretch"):
                try:
                    store.update_task_status(identity, task["id"], status, rejection_reason=rejection_reason)
                    st.success("Campaign step updated.")
                    st.rerun()
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))

    pending_for_campaign = [row for row in store.list_approvals(status="Pending") if row.get("object_id") == selected["id"]]
    section("Launch decision", "Approval gate")
    if pending_for_campaign:
        st.info("A launch approval is already waiting for a manager decision.")
    elif has_permission(identity.role, Permission.REQUEST_APPROVAL):
        if st.button("Request campaign launch approval", key=f"campaign_approval_{selected['id']}"):
            approval_id = store.create_approval(
                identity,
                object_type="campaign",
                object_id=selected["id"],
                summary=f"Launch review: {selected['name']}",
                risk_level=RiskLevel.HIGH,
                before_snapshot={"status": selected["status"], "readiness_pct": readiness["pct"]},
                proposed_diff={"status": "Approved for manual launch", "external_writes": False},
            )
            st.success(f"Approval requested · {approval_id[:8]}. This does not launch anything.")


def _new_campaign(store: OperationalStore, identity: UserIdentity) -> None:
    if not has_permission(identity.role, Permission.MANAGE_CAMPAIGNS):
        st.info(f"The {identity.role.value} role can review campaigns but cannot create one.")
        return
    section("Create a campaign", "One brief across every channel")
    section_copy("Choose only the channels the campaign actually needs. The app will create the relevant work—not twenty separate dashboards.")
    with st.form("unified_campaign_create", clear_on_submit=True):
        name = st.text_input("Campaign name", placeholder="e.g. September designer drop")
        objective = st.text_area("Commercial objective", placeholder="What should change, for whom, and how will success be measured?")
        c1, c2 = st.columns(2)
        with c1:
            audience = st.text_input("Audience", placeholder="Named, consent-safe segment")
            geography = st.selectbox("Geography", ["Hong Kong", "Singapore", "United Kingdom", "United States", "Australia", "Other"])
            start = st.date_input("Start", value=date.today() + timedelta(days=21), key="unified_campaign_start")
        with c2:
            owner = st.text_input("Owner", value=identity.display_name)
            budget = st.number_input("Working budget (HKD)", min_value=0.0, value=0.0, step=500.0)
            end = st.date_input("End", value=date.today() + timedelta(days=45), key="unified_campaign_end")
        channels = st.multiselect("Channels", ["Google Ads", "Meta Ads", "Klaviyo", "Blog / SEO", "Landing page", "Stores / GBP", "Organic social"], default=["Klaviyo", "Blog / SEO"])
        products = st.text_area("Products / collections", placeholder="Live availability will be verified before launch")
        submitted = st.form_submit_button("Create campaign and prepare checklist", type="primary")
    if submitted:
        if not name.strip() or not objective.strip() or not audience.strip():
            st.error("Campaign name, objective and audience are required.")
        elif end < start:
            st.error("End cannot be before start.")
        else:
            campaign_id = store.create_campaign(
                identity,
                name=name,
                objective=objective,
                audience=audience,
                geography=geography,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
                budget_hkd=budget,
                products=products,
                channels=channels,
                owner=owner,
                utm_plan="utm_source={channel}&utm_medium={medium}&utm_campaign={campaign_slug}",
            )
            campaign = next(row for row in store.list_campaigns() if row["id"] == campaign_id)
            created = create_campaign_tasks(store, identity, campaign)
            st.success(f"Campaign created with {len(set(created))} owned checklist steps. No external system was changed.")


def _approvals(store: OperationalStore, identity: UserIdentity) -> None:
    approvals = store.list_approvals()
    section("Decisions", "No launch by accident")
    if not approvals:
        st.info("No approval has been requested yet.")
        return
    dataframe([{"Request": row["summary"], "Risk": row["risk_level"], "Requester": row["requested_by_name"], "Status": row["status"], "Decision by": row["decided_by_name"] or "—"} for row in approvals], height=300)
    pending = [row for row in approvals if row["status"] == ApprovalStatus.PENDING.value]
    if pending and has_permission(identity.role, Permission.DECIDE_APPROVAL):
        labels = {f"{row['summary']} · {row['id'][:8]}": row for row in pending}
        selected = labels[st.selectbox("Pending request", list(labels), key="unified_approval_select")]
        decision = st.radio("Decision", [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED], format_func=lambda item: item.value, horizontal=True, key="unified_approval_decision")
        comment = st.text_area("Decision comment", key="unified_approval_comment")
        if st.button("Record decision", type="primary", key="unified_approval_save"):
            try:
                store.decide_approval(identity, selected["id"], decision, comment)
                st.success("Decision recorded. Approval does not execute an external action.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))


def _experiments(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    section("Test before scaling", "Experiments")
    records = store.list_experiments() or dataset["experiments"]
    dataframe(records, height=280)
    if not has_permission(identity.role, Permission.MANAGE_TASKS):
        return
    with st.expander("Create an experiment"):
        with st.form("unified_experiment", clear_on_submit=True):
            name = st.text_input("Experiment name")
            hypothesis = st.text_area("Hypothesis", placeholder="If we change X for audience Y, metric Z should improve because…")
            c1, c2 = st.columns(2)
            with c1:
                entity = st.text_input("Page / campaign")
                baseline = st.text_input("Baseline")
                control = st.text_area("Control")
            with c2:
                audience = st.text_input("Test audience")
                target = st.text_input("Success threshold")
                variant = st.text_area("Variant")
            submitted = st.form_submit_button("Create experiment")
        if submitted and name.strip() and hypothesis.strip():
            experiment_id = store.create_experiment(identity, name=name, hypothesis=hypothesis, affected_entity=entity, baseline_metric=baseline, target_metric=target, audience=audience, control_description=control, variant_description=variant, confidence_limitation="Directional until the pre-agreed sample and measurement window are reached.", owner=identity.display_name)
            st.success(f"Experiment created · {experiment_id[:8]}")


def _task_workboard(store: OperationalStore, identity: UserIdentity) -> None:
    tasks = store.list_tasks()
    section("Owned work", "Workboard")
    dataframe(
        [
            {
                "Task": row["title"],
                "Area": row["problem_type"],
                "Priority": row["severity"],
                "Owner": row["owner"],
                "Due": row["due_date"],
                "Status": row["status"],
            }
            for row in tasks
        ],
        height=310,
    )
    if not tasks or not has_permission(identity.role, Permission.MANAGE_TASKS):
        return
    with st.expander("Update a task"):
        labels = {f"{row['title']} · {row['status']}": row for row in tasks}
        selected = labels[st.selectbox("Task", list(labels), key="work_task_select")]
        allowed = list(TaskStatus)
        if identity.demo:
            allowed = [item for item in allowed if item not in {TaskStatus.APPROVED, TaskStatus.SCHEDULED, TaskStatus.IMPLEMENTED}]
        status = st.selectbox("Status", allowed, format_func=lambda item: item.value, key="work_task_status")
        rejection_reason = st.text_input("Reason", key="work_task_reason") if status is TaskStatus.REJECTED else ""
        if st.button("Save task", type="primary", key="work_task_save"):
            try:
                store.update_task_status(identity, selected["id"], status, rejection_reason=rejection_reason)
                st.success("Task updated.")
                st.rerun()
            except (ValueError, PermissionError) as exc:
                st.error(str(exc))


def _work_actions(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    signals = detect_business_signals(dataset)
    tasks = store.list_tasks()
    open_tasks = [row for row in tasks if row.get("status") not in DONE_STATES]
    pending = store.list_approvals(status="Pending")
    cols = st.columns(3)
    with cols[0]:
        kpi_card("Priority signals", str(len([item for item in signals if item.severity.value in {"Critical", "High"}])), source="Rules engine", definition="Deterministic critical and high-priority signals.", delta="Ranked by impact and confidence", tone="coral", warning=True)
    with cols[1]:
        kpi_card("Open tasks", str(len(open_tasks)), source="Workboard", definition="Tasks not completed or cancelled.", delta="Every accepted item keeps an owner", tone="violet")
    with cols[2]:
        kpi_card("Awaiting approval", str(len(pending)), source="Approval log", definition="Pending human decisions; approval never executes an external action in this release.", delta="External actions remain off", tone="teal")

    section("Recommendations", "Prioritized")
    section_copy("Each recommendation keeps its source, evidence, confidence, proposed action and success measure. Nothing is executed automatically.")
    _signal_queue(dataset, store, identity, limit=5)
    _task_workboard(store, identity)
    with st.expander("Approvals"):
        _approvals(store, identity)
    with st.expander("Experiments"):
        _experiments(dataset, store, identity)


def render_work(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity, root: Path) -> None:
    if identity.role is not Role.ADMINISTRATOR:
        st.error("Work is available only to the Administrator.")
        return
    page_header(
        "Administrator workspace",
        "Turn insight into controlled work.",
        "Recommendations, campaigns, content, SEO and approvals stay connected here; specialist responsibilities remain workflow labels, not extra application roles.",
    )
    data_banner(dataset["meta"])
    view = _subnav("Work view", ["Actions", "Campaigns", "Content & SEO"], key="work_subnav")
    if view == "Actions":
        _work_actions(dataset, store, identity)
    elif view == "Campaigns":
        _campaign_workroom(store, identity)
        with st.expander("Create a campaign"):
            _new_campaign(store, identity)
    else:
        content_view = _subnav(
            "Content & SEO view",
            ["SEO opportunities", "Content studio", "Site & catalogue", "Trend handoff"],
            key="work_content_subnav",
        )
        if content_view == "SEO opportunities":
            _seo_opportunities(dataset, store, identity)
        elif content_view == "Content studio":
            _content_studio(store, identity)
        elif content_view == "Site & catalogue":
            _site_catalogue(dataset, store, identity)
        else:
            _trend_handoff(dataset, store, identity, root)


def render_campaigns(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header(
        "Campaign workroom",
        "One campaign. Every channel. Clear ownership.",
        "Start with the commercial goal, then let the app build the minimum channel checklist, approvals and measurement plan required to deliver it.",
    )
    data_banner(dataset["meta"])
    view = _subnav("Campaign view", ["Workroom", "New campaign", "Approvals", "Experiments"], key="campaign_subnav")
    if view == "Workroom":
        _campaign_workroom(store, identity)
    elif view == "New campaign":
        _new_campaign(store, identity)
    elif view == "Approvals":
        _approvals(store, identity)
    else:
        _experiments(dataset, store, identity)


def _seo_opportunities(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    rows = dataset["seo_opportunities"]
    total_impressions = sum(row["impressions"] for row in rows)
    total_clicks = sum(row["clicks"] for row in rows)
    cols = st.columns(3)
    with cols[0]:
        kpi_card("Priority opportunities", str(len(rows)), source="Search Console", definition="Query/page pairs selected by a transparent weighted rule.", delta="No invented search volume", tone="violet")
    with cols[1]:
        kpi_card("Impressions represented", f"{total_impressions:,}", source="Search Console", definition="Impressions for the displayed query/page pairs only.", delta="July fixture", tone="pink")
    with cols[2]:
        kpi_card("Weighted click-through", f"{100 * total_clicks / total_impressions:.2f}%", source="Search Console", definition="Displayed clicks divided by displayed impressions.", delta="Prioritise reachable CTR gains", tone="teal")

    existing_content = store.list_content_items()
    existing_keywords = {str(item.get("primary_keyword") or "").lower() for item in existing_content}
    for index, row in enumerate(rows):
        with st.container(border=True):
            left, middle, action = st.columns([3.7, 1.1, 1.35])
            with left:
                st.subheader(row["query"])
                st.caption(row["page"])
                st.write(row["action"])
                source_badges("Search Console", "Shopify relevance", "Transparent score", mode="fixture")
            with middle:
                st.metric("Score", f"{row['score']:.0f}/100")
                st.caption(f"{row['impressions']:,} impressions · {row['clicks']} clicks · position {row['position']:.1f}")
            with action:
                already = row["query"].lower() in existing_keywords
                if already:
                    st.success("Brief exists")
                elif has_permission(identity.role, Permission.MANAGE_CONTENT):
                    if st.button("Prepare brief", key=f"prepare_seo_{index}", type="primary", width="stretch"):
                        scaffold = (
                            f"CONTENT BRIEF\n\nObjective\nImprove qualified organic clicks for: {row['query']}\n\n"
                            f"Evidence\n{row['impressions']:,} impressions; {row['clicks']} clicks; {row['ctr']:.2f}% CTR; average position {row['position']:.1f}.\n\n"
                            f"Recommended change\n{row['action']}\n\n"
                            "Required checks\n- Confirm current Search Console values\n- Verify live HULA inventory and links\n- Map factual/authentication claims to evidence\n- Obtain brand and SEO review\n- Measure CTR and qualified sessions after 14 and 30 days\n"
                        )
                        content_id = store.create_content_item(
                            identity,
                            title=f"SEO refresh — {row['query']}",
                            content_type="Collection-page copy" if "/collections/" in row["page"] else "Blog article",
                            owner=identity.display_name,
                            business_objective="Increase qualified organic clicks and useful product discovery",
                            audience="Searchers matching the documented query intent",
                            primary_keyword=row["query"],
                            search_intent="Commercial investigation",
                            related_products="Verify live inventory before linking",
                            source_evidence=[{"source": "Search Console fixture", "page": row["page"], "impressions": row["impressions"], "clicks": row["clicks"], "position": row["position"]}],
                            body=scaffold,
                            status="Brief",
                            due_date=(date.today() + timedelta(days=10)).isoformat(),
                        )
                        st.success(f"Controlled brief ready · {content_id[:8]}")


CONTENT_STEPS = ["Idea", "Research", "Brief", "Draft", "Evidence check", "Brand review", "Product check", "SEO review", "Awaiting Approval"]


def _content_studio(store: OperationalStore, identity: UserIdentity) -> None:
    items = store.list_content_items()
    if not items:
        st.info("Create a brief from SEO Opportunities or add a content item below.")
    else:
        dataframe([{"Title": row["title"], "Type": row["content_type"], "Keyword": row["primary_keyword"], "Owner": row["owner"], "Due": row["due_date"], "Status": row["status"]} for row in items], height=250)
        labels = {f"{row['title']} · {row['status']}": row for row in items}
        item = labels[st.selectbox("Open content item", list(labels), key="unified_content_select")]
        workflow_status(item["status"], CONTENT_STEPS)
        body_key = f"unified_content_body_{item['id']}"
        if body_key not in st.session_state:
            st.session_state[body_key] = item["body"]
        left, right = st.columns([2.2, 1])
        with left:
            body = st.text_area("Draft / brief", height=460, key=body_key)
        with right:
            st.markdown("**Required before approval**")
            st.checkbox("Claims mapped to evidence", key=f"unified_claims_{item['id']}")
            st.checkbox("Expert review for authentication facts", key=f"unified_expert_{item['id']}")
            st.checkbox("Live products and links verified", key=f"unified_products_{item['id']}")
            st.checkbox("SEO and brand review complete", key=f"unified_seo_{item['id']}")
            st.caption(f"Keyword: {item['primary_keyword'] or 'Not set'}")
            st.caption(f"Products: {item['related_products'] or 'Not set'}")
            source_badges("AI may draft", "Human approves", "Auto-publish off", mode="fixture")
        if has_permission(identity.role, Permission.MANAGE_CONTENT):
            current = CONTENT_STEPS.index(item["status"]) if item["status"] in CONTENT_STEPS else 0
            new_status = st.selectbox("Workflow stage", CONTENT_STEPS, index=current, key="unified_content_status")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Save draft", type="primary", key="unified_content_save", width="stretch"):
                    store.update_content(identity, item["id"], body=body, status=new_status)
                    st.success("Draft saved. Nothing was published.")
            with c2:
                if has_permission(identity.role, Permission.REQUEST_APPROVAL) and st.button("Request review", key="unified_content_review", width="stretch"):
                    approval_id = store.create_approval(identity, object_type="content", object_id=item["id"], summary=f"Review content: {item['title']}", risk_level=RiskLevel.MEDIUM, before_snapshot={"status": item["status"]}, proposed_diff={"status": "Approved", "body": body})
                    st.success(f"Review requested · {approval_id[:8]}")

    if has_permission(identity.role, Permission.MANAGE_CONTENT):
        with st.expander("Add a content idea"):
            with st.form("unified_content_create", clear_on_submit=True):
                title = st.text_input("Working title")
                c1, c2 = st.columns(2)
                with c1:
                    content_type = st.selectbox("Type", ["Blog article", "Collection-page copy", "Designer guide", "Trend report", "FAQ", "Email content", "Landing page", "Store/local content"])
                    objective = st.text_input("Business objective")
                    audience = st.text_input("Audience")
                with c2:
                    keyword = st.text_input("Keyword / topic")
                    products = st.text_input("Products / collections")
                    due = st.date_input("Due", value=date.today() + timedelta(days=10), key="unified_content_due")
                submitted = st.form_submit_button("Create idea")
            if submitted and title.strip():
                content_id = store.create_content_item(identity, title=title, content_type=content_type, owner=identity.display_name, business_objective=objective, audience=audience, primary_keyword=keyword, related_products=products, due_date=due.isoformat())
                st.success(f"Content item created · {content_id[:8]}")


def _site_catalogue(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    section("Site health", "Technical SEO")
    dataframe(dataset["technical_issues"], height=260)
    section("Catalogue opportunities", "Shopify + Merchant")
    dataframe(dataset["catalogue_issues"], height=300, column_config={"value_hkd": st.column_config.NumberColumn("Value", format="HK$ %.0f"), "conversion_rate": st.column_config.NumberColumn("Conversion", format="%.2f%%")})
    section("Merchant feed", "Product distribution")
    dataframe(dataset["merchant"])
    st.caption("All rows are fixture examples until live crawls and commerce integrations complete. External changes remain off.")
    if has_permission(identity.role, Permission.MANAGE_TASKS):
        if st.button("Create the priority SEO workboard", type="primary", key="site_catalogue_workboard"):
            task_ids: list[str] = []
            due = (date.today() + timedelta(days=14)).isoformat()
            for row in dataset["technical_issues"]:
                task_ids.append(store.create_task(identity, title=row["issue"], description=row["evidence"], problem_type="Technical SEO", source_system="Site audit fixture", evidence=row, severity=row["severity"], recommended_action=row["action"], owner=row["owner"], due_date=due, deduplication_key=f"technical-seo:{row['issue'].lower().replace(' ', '-')}"[:160], data_mode="fixture"))
            for row in dataset["catalogue_issues"]:
                task_ids.append(store.create_task(identity, title=f"Catalogue: {row['product']} — {row['issue']}", description=row["recommendation"], problem_type="Catalogue SEO", source_system="Shopify fixture", evidence=row, severity="High" if "unavailable" in row["issue"].lower() else "Medium", recommended_action=row["recommendation"], owner="Marketing", due_date=due, deduplication_key=f"catalogue-seo:{row['product'].lower().replace(' ', '-')}:{row['issue'].lower().replace(' ', '-')}"[:160], data_mode="fixture"))
            st.success(f"Priority workboard ready with {len(set(task_ids))} owned fixes. Nothing was changed in Shopify.")


def _trend_handoff(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity, root: Path) -> None:
    trends, meta = _load_trends(root)
    source_badges("Trend Intelligence", mode="live" if str(meta.get("mode")) == "live" else "fixture")
    if not trends:
        st.info("No Trend Intelligence snapshot is available. Run the preserved Trend Intelligence app to generate one.")
        return
    if str(meta.get("mode", "")).lower() != "live" or "demo" in str(meta.get("catalogue_source", "")).lower():
        st.warning("The current trend snapshot or catalogue is not live. Use it for workflow demonstration, not campaign activation.")
    for index, trend in enumerate(trends[:8]):
        name = str(trend.get("name") or trend.get("trend") or "Unnamed trend")
        score = float(trend.get("hula_opportunity_score") or trend.get("confidence_score") or trend.get("confidence") or 0)
        if score <= 1:
            score *= 100
        with st.container(border=True):
            cols = st.columns([3.2, .9, 1.25, 1.25])
            with cols[0]:
                st.subheader(name)
                st.write(trend.get("summary") or trend.get("reason") or "Open Trend Intelligence for the full evidence trail.")
            with cols[1]:
                st.metric("Opportunity", f"{score:.0f}/100")
            with cols[2]:
                if has_permission(identity.role, Permission.MANAGE_CAMPAIGNS) and st.button("Create campaign", key=f"unified_trend_campaign_{index}", width="stretch"):
                    campaign_id = store.create_campaign(identity, name=f"Trend test — {name}", objective="Validate and activate an evidence-backed fashion opportunity", audience="Define after inventory and customer review", geography="Hong Kong", channels=["Blog / SEO", "Klaviyo", "Meta Ads"], owner=identity.display_name, source_trend=name, products="Verify live availability")
                    st.success(f"Campaign draft ready · {campaign_id[:8]}")
            with cols[3]:
                if has_permission(identity.role, Permission.MANAGE_CONTENT) and st.button("Create content brief", key=f"unified_trend_content_{index}", width="stretch"):
                    content_id = store.create_content_item(
                        identity,
                        title=f"HULA perspective — {name}",
                        content_type="Trend report",
                        owner=identity.display_name,
                        business_objective="Connect a verified fashion signal to available HULA inventory",
                        audience="Luxury resale shoppers",
                        primary_keyword=name,
                        search_intent="Inspirational / commercial",
                        related_products="Verify live Shopify inventory before selection",
                        source_evidence=[{"trend": name, "snapshot_generated_at": meta.get("generated_at"), "data_mode": meta.get("mode")}],
                        body=f"TREND CONTENT BRIEF\n\nSignal\n{name}\n\nWhy now\n{trend.get('summary') or trend.get('reason') or 'Review the full Trend Intelligence evidence.'}\n\nRequired checks\n- Review the full evidence trail\n- Match only live HULA inventory\n- Verify fashion and authentication claims\n- Obtain brand/SEO approval\n- Measure qualified sessions and product engagement\n",
                        status="Brief",
                        due_date=(date.today() + timedelta(days=10)).isoformat(),
                    )
                    st.success(f"Content brief ready · {content_id[:8]}")


def render_content_seo(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity, root: Path) -> None:
    page_header(
        "Content & SEO studio",
        "Find the opportunity. Make the brief. Prove the result.",
        "This is the in-house replacement for repetitive SEO and blog coordination: evidence becomes a controlled draft, a named review and a measured follow-up.",
    )
    data_banner(dataset["meta"])
    view = _subnav("Content view", ["SEO opportunities", "Content studio", "Site & catalogue", "Trend handoff"], key="content_subnav")
    if view == "SEO opportunities":
        _seo_opportunities(dataset, store, identity)
    elif view == "Content studio":
        _content_studio(store, identity)
    elif view == "Site & catalogue":
        _site_catalogue(dataset, store, identity)
    else:
        _trend_handoff(dataset, store, identity, root)


def _business_truth(dataset: dict[str, Any]) -> None:
    values = dataset["executive"]
    online = dataset["online_summary"]
    cols = st.columns(4)
    with cols[0]:
        kpi_card("Commerce revenue", _hkd(values["commerce_revenue"]), source="Shopify / POS", definition="Headline booked commerce for the reporting period.", delta=f"{values['yoy_pct']:+.1f}% YoY", tone="violet")
    with cols[1]:
        kpi_card("Online Store revenue", _hkd(online["revenue"]), source="Shopify", definition="Online Store row only; physical-store revenue is not mixed into web conversion.", delta="84 online orders", tone="pink")
    with cols[2]:
        kpi_card("Channel-chart coverage", f"{values['channel_chart_coverage_pct']:.1f}%", source="Agency report", definition="Displayed channel rows divided by headline revenue; rows also use overlapping attribution.", delta="46.3% is not represented", tone="coral", warning=True)
    with cols[3]:
        kpi_card("Paid CAC", "Unavailable", source="Governed metric", definition="Paid-acquired new customers are not reliably identified in the supplied report.", delta=f"Proxy only: {_hkd(values['spend_per_all_new_customer'], 2)} per all new customer", tone="teal", warning=True)

    section("Booked revenue by location", "Commerce truth")
    stores = pd.DataFrame(dataset["stores"])
    fig = px.bar(stores, x="location", y="revenue", color="location", text_auto=".3s", color_discrete_sequence=PALETTE)
    fig.update_traces(textposition="outside")
    st.plotly_chart(_plot_style(fig, height=350), width="stretch")
    trust_row("Reconciliation is blocking distribution", "Location rows exceed headline commerce revenue by HK$30,146.56 and contain five fewer orders. The app keeps that gap visible until explained.", warning=True)

    section("Attribution views", "Never add these together")
    section_copy("The agency's channel chart is not a complete, mutually exclusive revenue split. Each row is displayed with its own source and window.")
    channels = pd.DataFrame(dataset["channel_revenue"])
    fig = px.bar(channels, x="channel", y="reported_revenue", color="channel", color_discrete_sequence=PALETTE, text_auto=".3s")
    fig.update_traces(textposition="outside")
    st.plotly_chart(_plot_style(fig, height=330), width="stretch")
    dataframe(dataset["channel_revenue"], column_config={"reported_revenue": st.column_config.NumberColumn("Reported revenue", format="HK$ %.2f"), "spend": st.column_config.NumberColumn("Spend", format="HK$ %.2f")})
    trust_row("Coverage and overlap are separate problems", "The four channel rows total HK$1,337,083.87—53.69% of headline revenue—while Klaviyo's 90-day and Meta's seven-day claims can overlap.", warning=True)

    section("Online behaviour", "Two source views kept separate")
    left, right = st.columns([1.45, 1])
    with left:
        st.markdown("**Analytics event incidence**")
        behavior = pd.DataFrame(dataset["session_behaviour"])
        fig = px.bar(behavior, x="count", y="event", orientation="h", color="event", color_discrete_sequence=PALETTE, text="share_of_session_starts_pct")
        fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(behavior["event"].tolist())))
        st.plotly_chart(_plot_style(fig, height=310), width="stretch")
        st.caption("These are the report's event/session rows. They are not asserted to be unique-user funnel steps.")
    with right:
        st.markdown("**Shopify Online Store summary**")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Add to carts", f"{online['add_to_carts']:,}")
            st.metric("Online orders", f"{online['orders']:,}")
        with c2:
            st.metric("Reported conversion", f"{online['conversion_rate_pct']:.2f}%")
            st.metric("Checkout count", "Unavailable")
        st.info(online["note"])


def _paid_media(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    google = dataset["google_campaigns"]
    meta = dataset["meta_campaigns"]
    google_spend = sum(row["spend"] for row in google)
    google_value = sum(row["purchase_value"] for row in google)
    meta_spend = sum(row["spend"] for row in meta)
    meta_value = sum(row["purchase_value"] for row in meta)
    cols = st.columns(4)
    with cols[0]:
        kpi_card("Google spend", _hkd(google_spend), source="Google Ads", definition="Platform cost for displayed campaigns.", delta="Attribution setting must be confirmed", tone="violet")
    with cols[1]:
        kpi_card("Google ROAS", f"{google_value / google_spend:.2f}x", source="Google Ads", definition="Google-attributed purchase value divided by Google spend.", delta="Platform view, not booked revenue", tone="pink")
    with cols[2]:
        kpi_card("Meta spend", _hkd(meta_spend), source="Meta Ads", definition="Platform cost for displayed campaigns.", delta="July report fixture", tone="teal")
    with cols[3]:
        kpi_card("Meta ROAS", f"{meta_value / meta_spend:.2f}x", source="Meta Ads", definition="Meta-attributed purchase value divided by Meta spend.", delta="Seven-day window in supplied report", tone="coral")
    section("Google Ads", "Specialist review")
    dataframe(google, height=300, column_config={"spend": st.column_config.NumberColumn("Spend", format="HK$ %.2f"), "purchase_value": st.column_config.NumberColumn("Attributed value", format="HK$ %.2f"), "roas": st.column_config.NumberColumn("ROAS", format="%.2fx")})
    section("Meta Ads", "Creative and conversion review")
    dataframe(meta, height=300, column_config={"spend": st.column_config.NumberColumn("Spend", format="HK$ %.2f"), "purchase_value": st.column_config.NumberColumn("Attributed value", format="HK$ %.2f"), "roas": st.column_config.NumberColumn("ROAS", format="%.2fx")})
    st.warning("Recommendations can become tasks, but bidding, budgets, audiences, conversion settings and live status remain under the paid-media specialist's approval.")
    _signal_queue(dataset, store, identity, limit=3)


def _email_local(dataset: dict[str, Any]) -> None:
    section("Email performance", "Klaviyo — 90-day attribution")
    trust_row("Platform-attributed, not exclusive revenue", "The supplied report attributes purchases within 90 days of an email. These values may overlap Meta, Google, direct and Shopify revenue.", warning=True)
    dataframe(dataset["klaviyo"], height=330, column_config={"revenue": st.column_config.NumberColumn("Attributed revenue", format="HK$ %.2f"), "open_rate": st.column_config.NumberColumn("Open rate", format="%.1f%%"), "click_rate": st.column_config.NumberColumn("Click rate", format="%.1f%%")})
    section("Store visibility", "Google Business Profile")
    dataframe(dataset["gbp"], height=240)
    st.caption("Directions and calls are interactions—not proven store visits or revenue. Review text must be verified before a response is drafted.")


def _discovery(dataset: dict[str, Any]) -> None:
    section("AI referral traffic", "Observable sessions only")
    dataframe(dataset["ai_referrals"], height=240, column_config={"revenue": st.column_config.NumberColumn("Revenue", format="HK$ %.0f"), "engagement_rate": st.column_config.NumberColumn("Engagement", format="%.1f%%")})
    st.caption("The app can observe referral sessions; it cannot see private prompts or know why an assistant cited HULA.")
    section("Customer segments", "Privacy-safe planning")
    dataframe(dataset["customer_segments"], height=300, column_config={"revenue": st.column_config.NumberColumn("Revenue", format="HK$ %.0f"), "aov": st.column_config.NumberColumn("AOV", format="HK$ %.0f"), "repeat_rate": st.column_config.NumberColumn("Repeat rate", format="%.1f%%")})
    st.info("Audience activation is disabled. Consent, suppressions, minimum audience size and segment-version checks are required first.")


def _quality(dataset: dict[str, Any]) -> None:
    section("Report logic findings", "What must be fixed")
    dataframe(dataset["data_quality_findings"], height=380)
    section("Reconciliation", "One source population")
    dataframe(dataset["reconciliation"], height=330)
    section("Metric dictionary", "Definition before dashboard")
    dataframe(metric_rows(), height=500)


def render_performance(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header(
        "Performance",
        "Explore the numbers behind the overview.",
        "Commerce, customers and channel attribution remain separate, with definitions and reconciliation available when you need them.",
    )
    data_banner(dataset["meta"])
    reporting_controls(dataset["meta"], key="performance")
    view = _subnav("Performance view", ["Business truth", "Paid media", "Email & local", "Customers & discovery", "Data quality"], key="performance_subnav")
    if view == "Business truth":
        _business_truth(dataset)
    elif view == "Paid media":
        _paid_media(dataset, store, identity)
    elif view == "Email & local":
        _email_local(dataset)
    elif view == "Customers & discovery":
        _discovery(dataset)
    else:
        _quality(dataset)


def _connections(
    dataset: dict[str, Any],
    store: OperationalStore,
    identity: UserIdentity,
    settings: MarketingSettings,
    connectors: dict[str, Connector],
) -> None:
    if settings.writes_enabled:
        st.error("One or more external-write flags are enabled. Review the environment immediately.")
    else:
        st.success("External publishing, sending and budget changes are OFF.")
    rows = []
    for name, connector in connectors.items():
        validation = connector.validate_config()
        rows.append({"Provider": name, "State": validation.state.value, "Read capability": ", ".join(connector.capabilities().read), "Write mode": "Disabled", "Missing": ", ".join(validation.missing), "Last successful sync": "Never in this build", "Data shown": "Fixture"})
    dataframe(rows, height=360)
    selected_name = st.selectbox("Test a read-only connection", list(connectors), key="unified_connection")
    connector = connectors[selected_name]
    validation = connector.validate_config()
    st.caption(validation.message)
    if st.button("Test connection", disabled=not validation.valid, type="primary", key="unified_connection_test"):
        with st.spinner(f"Checking {selected_name}…"):
            st.session_state[f"unified_connection_result_{selected_name}"] = connector.test_connection()
    result = st.session_state.get(f"unified_connection_result_{selected_name}")
    if result:
        (st.success if result.success else st.warning)(result.message)
        st.json({"state": result.state.value, "checked_at": result.checked_at, "account": result.account_label, "api_version": result.api_version, "permissions": list(result.permissions), "detail": result.detail})
    if has_permission(identity.role, Permission.MANAGE_TASKS) and validation.valid and selected_name in {"Shopify", "Google Analytics 4", "Google Search Console"}:
        if st.button("Queue read-only sync", key="unified_queue_sync"):
            digest = hashlib.sha256(f"{selected_name}:{date.today().isoformat()}".encode()).hexdigest()[:20]
            job_id = store.enqueue_job(identity, f"sync_{selected_name.lower().replace(' ', '_')}", {"provider": selected_name, "mode": "read_only", "window": "last_7_complete_days"}, idempotency_key=f"sync:{digest}")
            st.success(f"Read-only job queued · {job_id[:8]}")


def _reports(dataset: dict[str, Any], identity: UserIdentity) -> None:
    section("Management report", "Structured, not screenshots")
    commentary = st.text_area("Executive commentary", value="July performance must remain a draft baseline until location revenue, channel coverage and order allocation are reconciled. Platform attribution is shown separately from booked commerce.", height=140, key="unified_report_commentary")
    version = st.text_input("Report version", value="July 2026 · Measurement-corrected draft", key="unified_report_version")
    can_approve = identity.role is Role.ADMINISTRATOR
    approved = st.checkbox("Approved for distribution", disabled=not can_approve, key="unified_report_approved")
    pdf = monthly_report_pdf(dataset, commentary=commentary, approved=approved, version=version)
    csv_bundle = csv_export_bundle(dataset)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Download management PDF", data=pdf, file_name="HULA_Marketing_Operations_July_2026.pdf", mime="application/pdf", width="stretch")
    with c2:
        st.download_button("Download governed source tables", data=csv_bundle, file_name="HULA_Marketing_Operations_July_2026_tables.zip", mime="application/zip", width="stretch")
    st.caption("The export is clearly labelled fixture/draft until live sources reconcile.")


def _governance(store: OperationalStore) -> None:
    section("Access permissions", "Two access levels")
    dataframe(permission_matrix_rows(), height=390)
    section("Audit history", "Who decided what")
    events = store.list_audit_events()
    dataframe([{"When": row["created_at"], "Actor": row["actor_id"], "Role": row["actor_role"], "Action": row["action"], "Entity": f"{row['entity_type']} · {row['entity_id'][:8]}", "Detail": row["detail"]} for row in events], height=360)


def render_settings(
    dataset: dict[str, Any],
    store: OperationalStore,
    identity: UserIdentity,
    settings: MarketingSettings,
    connectors: dict[str, Connector],
) -> None:
    if identity.role is not Role.ADMINISTRATOR:
        st.error("Settings are available only to the Administrator.")
        return
    page_header(
        "Settings",
        "Connections, definitions and control.",
        "Manage data sources, metric contracts, reports, access and the audit history away from the daily workspace.",
    )
    data_banner(dataset["meta"])
    view = _subnav("Settings view", ["Connections", "Metric definitions", "Reports", "Governance"], key="settings_subnav")
    if view == "Connections":
        _connections(dataset, store, identity, settings, connectors)
    elif view == "Metric definitions":
        section("Metric dictionary", "Contract before calculation")
        dataframe(metric_rows(), height=600)
    elif view == "Reports":
        _reports(dataset, identity)
    else:
        _governance(store)
