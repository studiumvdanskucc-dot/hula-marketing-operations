from __future__ import annotations

import hashlib
from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from .config import MarketingSettings
from .connectors.base import Connector
from .models import (
    ApprovalStatus,
    Permission,
    RiskLevel,
    Role,
    TaskStatus,
    UserIdentity,
)
from .permissions import has_permission, permission_matrix_rows
from .store import OperationalStore
from .ui_common import data_banner, dataframe, page_header, section, source_badges, workflow_status


def render_campaign_planner(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Integrated planning", "Build one campaign plan across every channel.", "Objective, audience, products, creative, paid media, email, content, tracking and approvals remain children of one accountable campaign record.")
    data_banner(dataset["meta"])
    campaigns = store.list_campaigns()
    section("Campaign workspace", "Current records")
    dataframe([
        {"Campaign": row["name"], "Objective": row["objective"], "Audience": row["audience"], "Geography": row["geography"], "Dates": f"{row['start_date'] or 'TBD'} → {row['end_date'] or 'TBD'}", "Budget": row["budget_hkd"], "Channels": ", ".join(row["channels"]), "Status": row["status"], "Owner": row["owner"]}
        for row in campaigns
    ], height=270, column_config={"Budget": st.column_config.NumberColumn("Budget", format="HK$ %.0f")})

    if not has_permission(identity.role, Permission.MANAGE_CAMPAIGNS):
        st.info(f"The {identity.role.value} role can review campaigns but cannot create one.")
        return
    section("Create a governed campaign draft", "No channel action is executed")
    with st.form("campaign_create_form", clear_on_submit=True):
        name = st.text_input("Campaign name", placeholder="e.g. September designer drop")
        objective = st.text_area("Commercial objective", placeholder="What should change, for whom, and how will success be measured?")
        c1, c2 = st.columns(2)
        with c1:
            audience = st.text_input("Target audience", placeholder="Use a named, consent-safe segment")
            geography = st.selectbox("Geography", ["Hong Kong", "Singapore", "United Kingdom", "United States", "Australia", "Other"])
            start_date = st.date_input("Start date", value=date.today() + timedelta(days=14))
        with c2:
            owner = st.text_input("Owner", value=identity.display_name)
            budget = st.number_input("Total working budget (HKD)", min_value=0.0, value=0.0, step=500.0)
            end_date = st.date_input("End date", value=date.today() + timedelta(days=44))
        channels = st.multiselect("Planned channels", ["Google Ads", "Meta Ads", "Klaviyo", "Blog / SEO", "Landing page", "Stores / GBP", "Organic social"], default=["Klaviyo", "Blog / SEO"])
        products = st.text_area("Products / collections", placeholder="Names only; live availability must be verified before launch")
        utm_plan = st.text_input("UTM convention", value="utm_source={channel}&utm_medium={medium}&utm_campaign={campaign_slug}")
        submitted = st.form_submit_button("Create campaign draft", type="primary")
    if submitted:
        if not name.strip() or not objective.strip() or not audience.strip():
            st.error("Campaign name, objective and audience are required.")
        elif end_date < start_date:
            st.error("End date cannot be before start date.")
        else:
            campaign_id = store.create_campaign(identity, name=name, objective=objective, audience=audience, geography=geography, start_date=start_date.isoformat(), end_date=end_date.isoformat(), budget_hkd=budget, products=products, channels=channels, owner=owner, utm_plan=utm_plan)
            st.success(f"Campaign draft created ({campaign_id[:8]}…). No paid, email or Shopify system was changed.")

    section("Launch control", "Required checklist")
    dataframe([
        {"Control": "Objective and primary KPI", "Owner": "Campaign owner", "Gate": "Required"},
        {"Control": "Live inventory / landing-page availability", "Owner": "Merchandising", "Gate": "Required"},
        {"Control": "Audience consent and suppressions", "Owner": "Marketing operator", "Gate": "Required"},
        {"Control": "Paid tracking and conversion health", "Owner": "Paid media specialist", "Gate": "Required"},
        {"Control": "UTM and measurement baseline", "Owner": "Marketing operator", "Gate": "Required"},
        {"Control": "Administrator approval", "Owner": "Administrator", "Gate": "Required before launch"},
    ])


def render_content_planner(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Editorial calendar", "Connect every content item to a commercial reason.", "Business objective, audience, keyword intent, products, evidence, owner, approval and measurement dates travel together.")
    data_banner(dataset["meta"])
    items = store.list_content_items()
    if items:
        dataframe([{"Title": row["title"], "Type": row["content_type"], "Objective": row["business_objective"], "Keyword": row["primary_keyword"], "Owner": row["owner"], "Due": row["due_date"], "Status": row["status"], "AI draft": "Yes" if row["ai_draft"] else "No"} for row in items], height=260)
    else:
        st.info("No content item exists yet. Create the first controlled idea below.")
    if not has_permission(identity.role, Permission.MANAGE_CONTENT):
        st.caption(f"The {identity.role.value} role cannot create content records.")
        return
    section("Add an editorial item")
    with st.form("content_planner_form", clear_on_submit=True):
        title = st.text_input("Working title")
        c1, c2 = st.columns(2)
        with c1:
            content_type = st.selectbox("Content type", ["Blog article", "Collection-page copy", "Designer guide", "Trend report", "FAQ", "Email content", "Landing page", "Store/local content"])
            objective = st.text_input("Business objective")
            audience = st.text_input("Audience")
            due = st.date_input("Due date", value=date.today() + timedelta(days=10))
        with c2:
            keyword = st.text_input("Primary keyword / cluster")
            intent = st.selectbox("Search intent", ["Informational", "Commercial investigation", "Transactional", "Local", "Inspirational", "Not search-led"])
            products = st.text_input("Related products / collections", placeholder="Availability verification required")
            owner = st.text_input("Owner", value=identity.display_name)
        source_url = st.text_input("Evidence/source URL (optional)")
        submitted = st.form_submit_button("Create content idea", type="primary")
    if submitted:
        if not title.strip():
            st.error("A working title is required.")
        else:
            sources = [{"url": source_url, "added_by": identity.display_name}] if source_url else []
            content_id = store.create_content_item(identity, title=title, content_type=content_type, owner=owner, business_objective=objective, audience=audience, primary_keyword=keyword, search_intent=intent, related_products=products, source_evidence=sources, due_date=due.isoformat())
            st.success(f"Content idea created ({content_id[:8]}…).")


CONTENT_STEPS = ["Idea", "Research", "Brief", "Draft", "Evidence check", "Brand review", "Product check", "SEO review", "Awaiting Approval", "Approved", "Shopify draft", "Published", "Measuring", "Update / retire"]


def render_content_studio(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Controlled drafting", "Build content with evidence, review and an audit trail.", "AI text is always a draft. Authentication claims, product facts, links and availability must be checked before approval; publication is disabled.")
    data_banner(dataset["meta"])
    items = store.list_content_items()
    if not items:
        st.info("Create an item in Content Planner first.")
        return
    labels = {f"{row['title']} · {row['status']} · {row['id'][:8]}": row for row in items}
    selected_label = st.selectbox("Content item", list(labels))
    item = labels[selected_label]
    workflow_status(item["status"], CONTENT_STEPS)
    left, right = st.columns([2, 1])
    with left:
        body = st.text_area("Draft body", value=item["body"], height=480, help="Drafts are stored locally in demo mode. Do not include customer data.")
    with right:
        st.markdown("**Evidence and controls**")
        st.write(f"Primary keyword: {item['primary_keyword'] or 'Not set'}")
        st.write(f"Intent: {item['search_intent'] or 'Not set'}")
        st.write(f"Products: {item['related_products'] or 'Not set'}")
        st.write(f"AI draft: {'Yes — requires review' if item['ai_draft'] else 'No / not marked'}")
        if item["source_evidence"]:
            dataframe(item["source_evidence"])
        else:
            st.warning("No source evidence has been attached.")
        st.markdown("**Pre-approval checklist**")
        st.checkbox("Claims mapped to evidence", key=f"claim_check_{item['id']}")
        st.checkbox("Named expert reviewed authentication facts", key=f"expert_check_{item['id']}")
        st.checkbox("Live product availability verified", key=f"product_check_{item['id']}")
        st.checkbox("Internal links and SEO reviewed", key=f"seo_check_{item['id']}")
    if has_permission(identity.role, Permission.MANAGE_CONTENT):
        allowed_steps = CONTENT_STEPS
        if str(dataset.get("meta", {}).get("mode")) in {"demo", "fixture"}:
            allowed_steps = CONTENT_STEPS[:9]
            st.caption("Fixture/demo content can progress through Awaiting Approval, but it cannot be marked approved, drafted in Shopify or published as live work.")
        current_index = allowed_steps.index(item["status"]) if item["status"] in allowed_steps else 0
        new_status = st.selectbox("Move workflow to", allowed_steps, index=current_index)
        if st.button("Save draft and status", type="primary"):
            store.update_content(identity, item["id"], body=body, status=new_status)
            st.success("Content version saved locally. No Shopify change was made.")
        if has_permission(identity.role, Permission.REQUEST_APPROVAL) and st.button("Request content approval"):
            approval_id = store.create_approval(identity, object_type="content", object_id=item["id"], summary=f"Review content: {item['title']}", risk_level=RiskLevel.MEDIUM, before_snapshot={"status": item["status"], "body": item["body"]}, proposed_diff={"status": "Approved", "body": body})
            st.success(f"Approval requested ({approval_id[:8]}…). This does not publish content.")
    else:
        st.caption(f"The {identity.role.value} role is read-only in Content Studio.")


def render_experiments(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Experiments and CRO", "Record a hypothesis before looking at the result.", "Baseline, target, audience, control, variant and confidence limitations keep small-sample ecommerce tests honest.")
    data_banner(dataset["meta"])
    records = store.list_experiments()
    combined = records or dataset["experiments"]
    dataframe(combined, height=260)
    if not has_permission(identity.role, Permission.MANAGE_TASKS):
        return
    section("Create an experiment record")
    with st.form("experiment_form", clear_on_submit=True):
        name = st.text_input("Experiment name")
        hypothesis = st.text_area("Hypothesis", placeholder="If we change X for audience Y, metric Z will improve because…")
        c1, c2 = st.columns(2)
        with c1:
            entity = st.text_input("Affected page / campaign")
            baseline = st.text_input("Baseline metric")
            control = st.text_area("Control")
        with c2:
            audience = st.text_input("Audience")
            target = st.text_input("Target metric")
            variant = st.text_area("Variant")
        limitation = st.text_input("Confidence limitation", value="Treat as directional until the pre-agreed minimum sample is reached.")
        submitted = st.form_submit_button("Create experiment", type="primary")
    if submitted:
        if not name.strip() or not hypothesis.strip():
            st.error("Name and hypothesis are required.")
        else:
            experiment_id = store.create_experiment(identity, name=name, hypothesis=hypothesis, affected_entity=entity, baseline_metric=baseline, target_metric=target, audience=audience, control_description=control, variant_description=variant, confidence_limitation=limitation, owner=identity.display_name)
            st.success(f"Experiment created ({experiment_id[:8]}…).")


def render_tasks_approvals(dataset: dict[str, Any], store: OperationalStore, identity: UserIdentity) -> None:
    page_header("Governed work", "Move from signal to action without losing accountability.", "Tasks, rejections, approvals, playbooks and audit events retain the evidence, actor, status and reason for every decision.")
    data_banner(dataset["meta"])
    tabs = st.tabs(["Tasks", "Approvals", "Playbooks", "Permission matrix", "Audit log"])
    with tabs[0]:
        tasks = store.list_tasks()
        dataframe([{"ID": row["id"][:8], "Task": row["title"], "Type": row["problem_type"], "Severity": row["severity"], "Owner": row["owner"], "Due": row["due_date"], "Status": row["status"], "Data": row["data_mode"]} for row in tasks], height=300)
        if tasks and has_permission(identity.role, Permission.MANAGE_TASKS):
            labels = {f"{row['title']} · {row['id'][:8]}": row for row in tasks}
            selected = labels[st.selectbox("Update task", list(labels), key="task_update_select")]
            status = st.selectbox("New status", list(TaskStatus), format_func=lambda item: item.value)
            rejection = st.text_input("Rejection reason (required when rejected)")
            if st.button("Update task status"):
                try:
                    store.update_task_status(identity, selected["id"], status, rejection_reason=rejection)
                    st.success("Task status updated and audited.")
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
        with st.expander("Create a manual task"):
            if has_permission(identity.role, Permission.MANAGE_TASKS):
                with st.form("manual_task_form", clear_on_submit=True):
                    title = st.text_input("Task title")
                    description = st.text_area("Plain-language description")
                    owner = st.text_input("Owner", value=identity.display_name)
                    due = st.date_input("Due date", value=date.today() + timedelta(days=7))
                    submitted = st.form_submit_button("Create task")
                if submitted and title.strip():
                    task_id = store.create_task(identity, title=title, description=description, problem_type="Manual", source_system="Internal", evidence={"entered_by": identity.display_name}, severity="Medium", recommended_action=description, owner=owner, due_date=due.isoformat(), data_mode="demo")
                    st.success(f"Task created ({task_id[:8]}…).")
    with tabs[1]:
        approvals = store.list_approvals()
        dataframe([{"ID": row["id"][:8], "Request": row["summary"], "Object": f"{row['object_type']} · {row['object_id'][:8]}", "Risk": row["risk_level"], "Requester": row["requested_by_name"], "Status": row["status"], "Decider": row["decided_by_name"] or ""} for row in approvals], height=260)
        pending = [row for row in approvals if row["status"] == ApprovalStatus.PENDING.value]
        if pending and has_permission(identity.role, Permission.DECIDE_APPROVAL):
            labels = {f"{row['summary']} · {row['id'][:8]}": row for row in pending}
            selected = labels[st.selectbox("Pending request", list(labels), key="approval_decision_select")]
            decision = st.radio("Decision", [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED], format_func=lambda item: item.value, horizontal=True)
            comment = st.text_area("Decision comment")
            if st.button("Record decision", type="primary"):
                try:
                    store.decide_approval(identity, selected["id"], decision, comment)
                    st.success("Decision recorded. Approval alone does not execute an external action.")
                except (ValueError, PermissionError) as exc:
                    st.error(str(exc))
        elif pending:
            st.caption(f"The {identity.role.value} role cannot decide approvals.")
    with tabs[2]:
        playbooks = [
            {"Playbook": "High-impression / low-CTR SEO", "Trigger": "CTR gap with positions 4–20", "Owner": "Marketing", "Approval": "Brand/SEO review", "Measure": "14/30-day CTR and qualified sessions"},
            {"Playbook": "Creative fatigue", "Trigger": "Frequency rises while CTR falls", "Owner": "Paid media", "Approval": "Administrator if budget/status changes", "Measure": "7/14-day frequency, CTR, purchases, ROAS"},
            {"Playbook": "Unavailable product in marketing", "Trigger": "Active promotion + zero inventory", "Owner": "Paid media", "Approval": "Administrator review", "Measure": "No spend/traffic to unavailable SKU"},
            {"Playbook": "Review response", "Trigger": "Unanswered review", "Owner": "Marketing", "Approval": "Administrator before public reply", "Measure": "Response within three business days"},
            {"Playbook": "Revenue reconciliation", "Trigger": "Absolute or percentage tolerance breached", "Owner": "Data owner", "Approval": "Metric owner sign-off", "Measure": "Explained difference within tolerance"},
        ]
        dataframe(playbooks)
    with tabs[3]:
        dataframe(permission_matrix_rows(), height=430)
    with tabs[4]:
        events = store.list_audit_events()
        dataframe([{"When": row["created_at"], "Actor": row["actor_id"], "Role": row["actor_role"], "Action": row["action"], "Entity": f"{row['entity_type']} · {row['entity_id'][:8]}", "Detail": row["detail"]} for row in events], height=400)


def render_integrations(
    dataset: dict[str, Any],
    store: OperationalStore,
    identity: UserIdentity,
    settings: MarketingSettings,
    connectors: dict[str, Connector],
) -> None:
    page_header("System health", "Know exactly what is connected—and what is not.", "Account identifiers, permissions, API versions, freshness and redacted errors are visible. Secret values never appear here.")
    data_banner(dataset["meta"])
    if settings.writes_enabled:
        st.error("One or more external-write flags are enabled. This build contains no external action adapter, so live writes still cannot execute; review the environment immediately.")
    else:
        st.success("All external-write feature flags are OFF. Automatic publishing and budget changes are disabled.")
    rows = []
    for name, connector in connectors.items():
        validation = connector.validate_config()
        capabilities = connector.capabilities()
        rows.append({"Provider": name, "State": validation.state.value, "API version": getattr(connector, "api_version", "Provider-managed"), "Read capability": ", ".join(capabilities.read), "Write mode": "Disabled", "Missing configuration": ", ".join(validation.missing), "Last successful sync": "Never in this build", "Data shown elsewhere": "Fixture"})
    dataframe(rows, height=370)

    section("Connection tests", "Explicit and read-only")
    selected_name = st.selectbox("Provider to test", list(connectors))
    connector = connectors[selected_name]
    validation = connector.validate_config()
    st.write(validation.message)
    source_badges(validation.state.value, str(getattr(connector, "api_version", "Provider-managed")), mode="fixture")
    if st.button("Test selected connection", disabled=not validation.valid, type="primary"):
        with st.spinner(f"Running one explicit read-only {selected_name} health check…"):
            result = connector.test_connection()
        st.session_state[f"connection_result_{selected_name}"] = result
    result = st.session_state.get(f"connection_result_{selected_name}")
    if result:
        if result.success:
            st.success(result.message)
        else:
            st.warning(result.message)
        st.json({"state": result.state.value, "checked_at": result.checked_at, "account": result.account_label, "api_version": result.api_version, "permissions": list(result.permissions), "detail": result.detail})

    if has_permission(identity.role, Permission.MANAGE_TASKS) and validation.valid and selected_name in {"Shopify", "Google Analytics 4", "Google Search Console", "Meta Ads"}:
        if st.button("Queue read-only resync"):
            digest = hashlib.sha256(f"{selected_name}:{date.today().isoformat()}".encode()).hexdigest()[:20]
            job_id = store.enqueue_job(identity, f"sync_{selected_name.lower().replace(' ', '_')}", {"provider": selected_name, "mode": "read_only", "window": "last_7_complete_days"}, idempotency_key=f"sync:{digest}")
            st.success(f"Read-only sync job queued ({job_id[:8]}…). A separate worker and live credentials are required to execute it.")

    section("Feature flags", "Server-side controls")
    dataframe([{"Flag": name, "Value": "ON" if value else "OFF", "Policy": "Must remain OFF in first release" if name.startswith("ENABLE_") else "Required safeguard"} for name, value in settings.feature_flags.items()])
    section("API versions pinned for this build", "26 August 2026")
    dataframe([
        {"Provider": "Shopify Admin GraphQL", "Pinned": "2026-07", "Status": "Latest stable observed at build time"},
        {"Provider": "GA4 Data API", "Pinned": "v1 / REST v1beta resource", "Status": "Official runReport API"},
        {"Provider": "Search Console", "Pinned": "v1 (webmasters v3 REST base)", "Status": "OAuth read-only"},
        {"Provider": "Google Ads", "Pinned": "v25", "Status": "Health shell; latest major released 22 July 2026"},
        {"Provider": "Meta Marketing API", "Pinned": "v26.0", "Status": "Read-only campaign-insights connector"},
        {"Provider": "Klaviyo", "Pinned": "2026-01-15 stable", "Status": "Health shell; beta campaign revisions deliberately avoided"},
        {"Provider": "Merchant API", "Pinned": "v1", "Status": "v1beta retired"},
        {"Provider": "PageSpeed Insights", "Pinned": "v5", "Status": "Health shell"},
    ])
