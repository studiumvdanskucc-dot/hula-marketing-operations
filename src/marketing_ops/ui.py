from __future__ import annotations

import html
from pathlib import Path
from typing import Callable

import streamlit as st

from .auth import SupabaseAuthenticator, demo_identity
from .config import MarketingSettings, load_marketing_settings, resolve_database_path
from .connectors.registry import build_connector_registry
from .demo_data import demo_dataset
from .models import Role, UserIdentity
from .pages_unified import (
    render_campaigns,
    render_content_seo,
    render_home,
    render_performance,
    render_settings,
)
from .store import OperationalStore
from .ui_common import default_date_range, inject_styles


APP_BUILD = "2026.08.06-marketing.2"


@st.cache_resource(show_spinner=False)
def _store(path: str, seed_demo: bool) -> OperationalStore:
    return OperationalStore(path, seed_demo=seed_demo)


def _identity(settings: MarketingSettings) -> UserIdentity:
    if settings.demo_mode:
        selected = st.session_state.get("marketing_demo_role")
        if not isinstance(selected, Role):
            selected = next((role for role in Role if role.value == settings.default_role), Role.MARKETING_OPERATOR)
        return demo_identity(settings, selected)

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
        st.sidebar.image(str(logo), width=154)
    st.sidebar.markdown(
        '<div class="sidebar-brand"><div class="sidebar-kicker">Marketing operating system</div>'
        '<h2>HULA, run in-house.</h2><p>From trustworthy data to an approved campaign action.</p></div>',
        unsafe_allow_html=True,
    )
    if settings.demo_mode:
        st.sidebar.markdown('<div class="mode-pill"><span class="mode-dot"></span>Fixture mode · no live accounts</div>', unsafe_allow_html=True)
        default_role = next((index for index, role in enumerate(Role) if role == identity.role), 1)
        selected_role = st.sidebar.selectbox(
            "Preview permissions",
            list(Role),
            index=default_role,
            format_func=lambda role: role.value,
            key="marketing_demo_role",
            help="Demo-only. Production roles come from authenticated membership.",
        )
        identity = demo_identity(settings, selected_role)
    else:
        st.sidebar.markdown('<div class="mode-pill live"><span class="mode-dot"></span>Authenticated production</div>', unsafe_allow_html=True)
    st.sidebar.caption(f"Signed in as {identity.display_name} · {identity.role.value}")
    if not identity.demo and st.sidebar.button("Sign out"):
        st.session_state.pop("marketing_auth_session", None)
        st.rerun()

    pages = [
        "⌂  Home",
        "◉  Campaigns",
        "✦  Content & SEO",
        "↗  Performance",
        "⚙  Settings",
    ]
    page = st.sidebar.radio("Navigation", pages, label_visibility="collapsed")
    with st.sidebar.expander("Reporting controls"):
        selected_dates = st.date_input(
            "Period",
            value=default_date_range(),
            help="The bundled fixture covers July 2026. Live marts will filter to the selected dates.",
        )
        comparison = st.selectbox("Compare with", ["Previous period", "Previous month", "Previous year", "No comparison"])
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
            st.session_state["marketing_date_range"] = tuple(selected_dates)
        st.session_state["marketing_comparison"] = comparison
    st.sidebar.markdown("---")
    st.sidebar.caption("Trend Intelligence remains a separate preserved app and feeds approved signals into Content & SEO.")
    st.sidebar.caption(f"Build {APP_BUILD} · HKT · HKD")
    st.sidebar.caption("Live external actions: OFF")
    return page, identity


def run_marketing_operations(root: Path | None = None) -> None:
    root = root or Path(__file__).resolve().parents[2]
    settings = load_marketing_settings()
    inject_styles()
    identity = _identity(settings)
    page, identity = _sidebar(settings, identity, root)
    database_path = resolve_database_path(settings, root)
    store = _store(str(database_path), settings.demo_mode)
    dataset = demo_dataset()
    connectors = build_connector_registry(settings)

    routes: dict[str, Callable[[], None]] = {
        "⌂  Home": lambda: render_home(dataset, store, identity, root),
        "◉  Campaigns": lambda: render_campaigns(dataset, store, identity),
        "✦  Content & SEO": lambda: render_content_seo(dataset, store, identity, root),
        "↗  Performance": lambda: render_performance(dataset, store, identity),
        "⚙  Settings": lambda: render_settings(dataset, store, identity, settings, connectors),
    }
    try:
        routes[page]()
    except Exception as exc:
        st.error("This page could not be rendered. Other Marketing Operations pages and the Trend Intelligence app remain available.")
        if settings.app_env == "development":
            st.exception(exc)
