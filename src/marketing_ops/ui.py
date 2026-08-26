from __future__ import annotations

from pathlib import Path
from typing import Callable

import streamlit as st

from .auth import SupabaseAuthenticator, demo_identity
from .config import MarketingSettings, load_marketing_settings, resolve_database_path
from .connectors.registry import build_connector_registry
from .decision_engine import contribution_value, retained_revenue_proxy
from .demo_data import demo_dataset
from .models import Role, UserIdentity
from .pages_unified import (
    render_home,
    render_performance,
    render_settings,
    render_viewer_overview,
    render_work,
)
from .store import OperationalStore
from .ui_common import inject_styles


APP_BUILD = "2026.08.26-marketing.6"


def _apply_business_policy(
    dataset: dict, settings: MarketingSettings
) -> dict:
    """Apply configured rules without converting unresolved inputs into facts."""

    values = dataset["executive"]
    # Shopify net revenue already includes actual discounts and refunds. Use it
    # for the accounting bridge so refunds are not provisioned a second time.
    net_revenue = values.get("net_revenue")
    values["retained_revenue"] = retained_revenue_proxy(
        net_revenue, settings.retained_margin_rate
    )
    if settings.retained_margin_rate is None:
        values["retained_revenue_status"] = "Unavailable — retained-margin rate is not set"
    elif settings.retained_margin_confirmed:
        values["retained_revenue_status"] = "Configured retained-margin rule"
    else:
        values["retained_revenue_status"] = (
            "Provisional 31% of Shopify net revenue — configurable"
        )

    values["contribution"] = contribution_value(
        net_revenue,
        settings.retained_margin_rate,
        settings.variable_cost_rate_of_retained,
    )
    if values["contribution"] is None:
        values["contribution_status"] = "Unavailable until the retained-margin and cost rates are set"
    elif not settings.retained_margin_confirmed:
        values["contribution_status"] = (
            "Provisional — actual refunds deducted once; payment fees + shipping are 10% of retained margin"
        )
    else:
        values["contribution_status"] = (
            "Configured calculation from Shopify net revenue after actual refunds"
        )
    dataset["profitability_policy"].update(
        {
            "retained_margin_rate": settings.retained_margin_rate,
            "retained_margin_confirmed": settings.retained_margin_confirmed,
            "returns_refunds_confirmed": settings.returns_refunds_confirmed,
            "forecast_return_rate": settings.forecast_return_rate,
            "forecast_return_rate_confirmed": settings.forecast_return_rate_confirmed,
            "variable_cost_rate_of_retained": settings.variable_cost_rate_of_retained,
            "variable_cost_confirmed": settings.variable_cost_confirmed,
            "platform_gmv_roas_floor": settings.platform_gmv_roas_floor,
            "contribution_roas_floor": settings.contribution_roas_floor,
            "contribution_roas_scale_target": settings.contribution_roas_scale_target,
            "minimum_purchases": settings.minimum_paid_purchases,
            "max_paid_cac_hkd": settings.max_paid_cac_hkd,
            "payback_window_days": settings.payback_window_days,
            "google_monthly_cap_hkd": settings.google_monthly_cap_hkd,
            "meta_monthly_cap_hkd": settings.meta_monthly_cap_hkd,
            "max_internal_reallocation_pct": settings.max_internal_reallocation_pct,
            "normalized_click_window_days": settings.normalized_click_window_days,
            "major_change_approvers": list(settings.major_change_approvers),
        }
    )
    return dataset


@st.cache_resource(show_spinner=False)
def _store(path: str, seed_demo: bool) -> OperationalStore:
    return OperationalStore(path, seed_demo=seed_demo)


def _identity(settings: MarketingSettings) -> UserIdentity:
    if settings.demo_mode:
        return demo_identity(settings)

    if not settings.auth_enabled:
        st.error("Production mode requires MARKETING_AUTH_ENABLED=true and configured Supabase Auth.")
        st.stop()
    existing = st.session_state.get("marketing_auth_session")
    if existing:
        return existing.identity
    authenticator = SupabaseAuthenticator(settings.supabase_url, settings.supabase_anon_key)
    st.title("HULA Marketing Operations")
    st.write("Sign in with your invited HULA account.")
    with st.form("marketing_login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", type="primary")
    if submitted:
        try:
            session = authenticator.authenticate(email, password)
            st.session_state["marketing_auth_session"] = session
            st.rerun()
        except Exception as exc:
            st.error(str(exc))
    st.stop()


def _sidebar(settings: MarketingSettings, identity: UserIdentity, root: Path) -> tuple[str, UserIdentity]:
    logo = root / "assets" / "hula_logo.png"
    if logo.exists():
        st.sidebar.image(str(logo), width=118)
    st.sidebar.markdown(
        '<div class="sidebar-brand"><div class="sidebar-kicker">Marketing OS</div>'
        '<h2>HULA</h2></div>',
        unsafe_allow_html=True,
    )
    if settings.demo_mode:
        st.sidebar.markdown('<div class="mode-pill"><span class="mode-dot"></span>Fixture data</div>', unsafe_allow_html=True)
    else:
        st.sidebar.markdown('<div class="mode-pill live"><span class="mode-dot"></span>Live workspace</div>', unsafe_allow_html=True)

    st.sidebar.markdown(
        f'<div class="account-card"><strong>{identity.display_name}</strong><span>{identity.role.value}</span></div>',
        unsafe_allow_html=True,
    )
    if not identity.demo and st.sidebar.button("Sign out"):
        st.session_state.pop("marketing_auth_session", None)
        st.rerun()

    if identity.role is Role.VIEWER:
        page = "Overview"
        st.sidebar.markdown('<div class="static-nav active"><span>Overview</span></div>', unsafe_allow_html=True)
        st.sidebar.caption("Read-only business view")
    else:
        pages = ["Overview", "Work", "Performance", "Settings"]
        page = st.sidebar.radio("Navigation", pages, label_visibility="collapsed")

    st.sidebar.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="safety-note"><span class="safety-dot"></span><div><strong>External actions off</strong><br>Contribution rules and approvals remain required.</div></div>', unsafe_allow_html=True)
    st.sidebar.caption(f"Build {APP_BUILD} · HKT · HKD")
    return page, identity


def run_marketing_operations(root: Path | None = None) -> None:
    root = root or Path(__file__).resolve().parents[2]
    settings = load_marketing_settings()
    inject_styles()
    identity = _identity(settings)
    page, identity = _sidebar(settings, identity, root)
    database_path = resolve_database_path(settings, root)
    store = _store(str(database_path), settings.demo_mode)
    dataset = _apply_business_policy(demo_dataset(), settings)
    connectors = build_connector_registry(settings)

    if identity.role is Role.VIEWER:
        routes: dict[str, Callable[[], None]] = {
            "Overview": lambda: render_viewer_overview(dataset, identity, settings),
        }
    else:
        routes = {
            "Overview": lambda: render_home(dataset, store, identity, root, settings),
            "Work": lambda: render_work(dataset, store, identity, root, settings),
            "Performance": lambda: render_performance(dataset, store, identity, settings),
            "Settings": lambda: render_settings(dataset, store, identity, settings, connectors),
        }
    try:
        routes[page]()
    except Exception as exc:
        st.error("This page could not be rendered. Other Marketing Operations pages and the Trend Intelligence app remain available.")
        if settings.app_env == "development":
            st.exception(exc)
