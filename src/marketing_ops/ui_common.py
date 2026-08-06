from __future__ import annotations

import html
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from .metrics import format_hkd
from .models import DataMode, Permission, Severity, Signal, UserIdentity
from .permissions import has_permission


PINK = "#ff4f9a"
INK = "#321641"
MIST = "#fff7fb"
SAGE = "#2f8f83"


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --pink:#ff4f9a; --pink-soft:#ffe4f0; --plum:#321641; --violet:#6842d8;
            --teal:#2f8f83; --teal-soft:#ddf6ef; --coral:#ff786f; --butter:#fff1bd;
            --paper:#ffffff; --canvas:#fffafd; --line:#eadfea; --muted:#765f79;
        }
        html, body, [class*="css"] {
            font-family:"Avenir Next","Inter","Segoe UI",sans-serif;
            color:var(--plum);
        }
        .stApp {
            background:
                radial-gradient(circle at 96% 4%, rgba(255,79,154,.10), transparent 25rem),
                radial-gradient(circle at 73% 12%, rgba(104,66,216,.07), transparent 22rem),
                var(--canvas);
        }
        .block-container { max-width:1440px; padding:2.3rem 3rem 5rem; }

        [data-testid="stSidebar"] {
            background:linear-gradient(165deg,#fff 0%,#fff5fa 58%,#f2ecff 100%);
            border-right:1px solid var(--line);
            min-width:318px;
        }
        [data-testid="stSidebar"] > div:first-child { padding:1.55rem 1.15rem; }
        [data-testid="stSidebar"] [role="radiogroup"] { gap:.38rem; }
        [data-testid="stSidebar"] [role="radiogroup"] label {
            padding:.78rem .9rem;
            border:1px solid transparent;
            border-radius:14px;
            transition:all .18s ease;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
            background:#fff;
            border-color:#f0dce7;
            transform:translateX(2px);
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
            background:linear-gradient(120deg,var(--plum),#5b2b71);
            box-shadow:0 10px 24px rgba(50,22,65,.16);
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p { color:#fff !important; }
        [data-testid="stSidebar"] [role="radiogroup"] label p {
            font-size:.98rem;
            letter-spacing:-.01em;
            font-weight:650;
            color:var(--plum);
        }
        .sidebar-brand { margin:.15rem 0 1rem; }
        .sidebar-brand h2 { margin:.3rem 0 .18rem; font-size:1.25rem; letter-spacing:-.035em; color:var(--plum); }
        .sidebar-brand p { margin:0; color:var(--muted); font-size:.78rem; line-height:1.45; }
        .sidebar-kicker { font-size:.68rem; letter-spacing:.14em; text-transform:uppercase; color:var(--pink); font-weight:800; }
        .mode-pill { display:inline-flex; align-items:center; gap:.42rem; border-radius:999px; padding:.42rem .66rem; background:var(--butter); color:#684f00; font-size:.72rem; font-weight:750; margin:.2rem 0 .8rem; }
        .mode-pill.live { background:var(--teal-soft); color:#145f56; }
        .mode-dot { width:7px; height:7px; border-radius:50%; background:currentColor; }

        .hero-panel {
            position:relative; overflow:hidden;
            background:linear-gradient(125deg,#4a1d59 0%,#6b36a6 48%,#ff4f9a 125%);
            color:white; border-radius:26px; padding:2.45rem 2.7rem; margin:0 0 1.35rem;
            box-shadow:0 18px 55px rgba(73,30,89,.17);
        }
        .hero-panel:after { content:""; position:absolute; width:260px; height:260px; border:52px solid rgba(255,255,255,.09); border-radius:50%; right:-78px; top:-104px; }
        .ops-eyebrow { position:relative; z-index:1; font-size:.72rem; letter-spacing:.14em; text-transform:uppercase; color:#ffd5e8; font-weight:800; margin-bottom:.7rem; }
        .ops-title { position:relative; z-index:1; font-size:clamp(2.25rem,4vw,4.15rem); font-weight:650; letter-spacing:-.06em; line-height:1.02; margin:0 0 .8rem; max-width:980px; color:white; }
        .ops-subtitle { position:relative; z-index:1; max-width:880px; color:#f9edf8; line-height:1.62; margin:0; font-size:1.03rem; }
        .pink-rule { display:none; }

        .data-banner { border:1px solid #f1d18a; border-left:7px solid #e9a319; border-radius:14px; background:#fff8df; padding:.88rem 1rem; margin:.25rem 0 1.45rem; font-size:.82rem; line-height:1.5; color:#5b4612; }
        .data-banner.live { border-color:#a8dfce; border-left-color:var(--teal); background:#ecfaf5; color:#155f55; }
        .section-label { font-size:.7rem; text-transform:uppercase; letter-spacing:.13em; color:var(--pink); font-weight:800; margin:2.2rem 0 .42rem; }
        .section-title { font-size:1.7rem; letter-spacing:-.04em; font-weight:700; color:var(--plum); margin:0 0 1rem; }
        .section-copy { color:var(--muted); font-size:.9rem; line-height:1.55; margin:-.45rem 0 1rem; max-width:880px; }

        .kpi-card { min-height:176px; border:1px solid var(--line); border-radius:19px; padding:1.05rem 1.12rem; background:rgba(255,255,255,.94); box-shadow:0 9px 24px rgba(74,29,89,.055); }
        .kpi-card.pink { border-top:5px solid var(--pink); }
        .kpi-card.violet { border-top:5px solid var(--violet); }
        .kpi-card.teal { border-top:5px solid var(--teal); }
        .kpi-card.coral { border-top:5px solid var(--coral); }
        .kpi-top { display:flex; justify-content:space-between; align-items:flex-start; gap:.5rem; }
        .kpi-label { color:var(--muted); font-size:.77rem; font-weight:750; line-height:1.25; }
        .kpi-source { flex:0 0 auto; background:#f5eef7; color:#6a4771; padding:.22rem .42rem; border-radius:999px; font-size:.57rem; font-weight:800; letter-spacing:.035em; text-transform:uppercase; }
        .kpi-value { margin:.7rem 0 .25rem; color:var(--plum); font-size:clamp(1.65rem,2.4vw,2.35rem); font-weight:750; letter-spacing:-.055em; line-height:1; }
        .kpi-delta { min-height:1.2rem; color:var(--teal); font-size:.72rem; font-weight:750; }
        .kpi-delta.warn { color:#b4542b; }
        .kpi-definition { border-top:1px solid #f0e7ef; padding-top:.55rem; margin-top:.45rem; color:#745f77; font-size:.69rem; line-height:1.38; }

        .loop-strip { display:grid; grid-template-columns:repeat(5,1fr); gap:.55rem; margin:.7rem 0 1.2rem; }
        .loop-step { position:relative; border-radius:15px; padding:.8rem .75rem; background:#fff; border:1px solid var(--line); text-align:center; color:var(--plum); font-size:.76rem; font-weight:750; }
        .loop-step strong { display:block; color:var(--pink); font-size:.64rem; letter-spacing:.08em; margin-bottom:.15rem; }

        .scope-card { border:1px solid var(--line); border-radius:18px; padding:1rem; background:#fff; min-height:146px; }
        .scope-icon { width:38px; height:38px; display:grid; place-items:center; border-radius:12px; background:var(--pink-soft); color:var(--pink); font-weight:850; margin-bottom:.65rem; }
        .scope-title { font-size:.96rem; font-weight:750; color:var(--plum); margin-bottom:.25rem; }
        .scope-state { color:var(--teal); font-size:.7rem; font-weight:800; text-transform:uppercase; letter-spacing:.06em; }
        .scope-copy { color:var(--muted); font-size:.72rem; line-height:1.42; margin-top:.32rem; }

        .source-badge { display:inline-block; border:1px solid #dfd0e1; border-radius:999px; padding:.25rem .5rem; font-size:.6rem; letter-spacing:.045em; text-transform:uppercase; margin:.1rem .2rem .1rem 0; background:white; font-weight:750; }
        .source-badge.fixture { color:#735400; background:#fff6d9; border-color:#edd188; }
        .source-badge.live { color:#126b5e; background:#e7f8f2; border-color:#9ed8c6; }
        .signal-head { font-size:1.08rem; font-weight:750; letter-spacing:-.025em; margin:.2rem 0 .5rem; color:var(--plum); }
        .signal-meta { font-size:.68rem; color:#765f79; text-transform:uppercase; letter-spacing:.075em; font-weight:750; }
        .signal-critical { border-left:6px solid #d6455d; padding-left:.9rem; }
        .signal-high { border-left:6px solid var(--pink); padding-left:.9rem; }
        .signal-medium { border-left:6px solid #e6a52b; padding-left:.9rem; }
        .signal-low, .signal-info { border-left:6px solid var(--teal); padding-left:.9rem; }
        .plain-box { background:#fff; border:1px solid var(--line); border-radius:15px; padding:1rem; line-height:1.55; font-size:.82rem; }
        .metric-note { color:#756078; font-size:.7rem; line-height:1.45; margin-top:.35rem; }
        .workflow { display:flex; flex-wrap:wrap; gap:.42rem; margin:.4rem 0 1rem; }
        .workflow span { border:1px solid #e3d4e5; border-radius:999px; padding:.4rem .62rem; font-size:.66rem; font-weight:750; color:#765f79; }
        .workflow span.active { border-color:var(--pink); background:var(--pink-soft); color:#9e255c; }
        .campaign-hero { border-radius:20px; padding:1.25rem 1.4rem; color:white; background:linear-gradient(110deg,#6842d8,#9b4dba 58%,#ff668f); margin:.65rem 0 1rem; }
        .campaign-hero h3 { color:white; margin:0 0 .35rem; font-size:1.45rem; letter-spacing:-.035em; }
        .campaign-hero p { color:#f8ebff; margin:.2rem 0; font-size:.82rem; line-height:1.45; }
        .campaign-meta { display:flex; gap:.45rem; flex-wrap:wrap; margin-top:.8rem; }
        .campaign-meta span { background:rgba(255,255,255,.16); border:1px solid rgba(255,255,255,.25); border-radius:999px; padding:.3rem .55rem; font-size:.67rem; font-weight:750; }
        .trust-row { display:flex; gap:.7rem; align-items:flex-start; border-radius:16px; padding:.9rem 1rem; background:#fff; border:1px solid var(--line); }
        .trust-mark { flex:0 0 auto; width:31px; height:31px; border-radius:10px; background:var(--teal-soft); color:var(--teal); display:grid; place-items:center; font-weight:900; }
        .trust-row.warn .trust-mark { background:#fff0d1; color:#ad7000; }
        .trust-row strong { display:block; font-size:.83rem; color:var(--plum); margin-bottom:.18rem; }
        .trust-row span { color:var(--muted); font-size:.72rem; line-height:1.42; }

        [data-testid="stMetric"] { border:1px solid var(--line); border-radius:17px; padding:1rem 1.05rem; background:white; min-height:122px; }
        [data-testid="stMetricLabel"] p { color:#765f79; font-size:.72rem; font-weight:700; }
        [data-testid="stMetricValue"] { font-weight:700; letter-spacing:-.04em; color:var(--plum); }
        div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:18px; border-color:var(--line); background:rgba(255,255,255,.86); }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { gap:.35rem; background:#f5edf7; border-radius:15px; padding:.3rem; }
        [data-testid="stTabs"] [data-baseweb="tab"] { border-radius:11px; padding:.55rem .8rem; color:#755c79; font-weight:700; }
        [data-testid="stTabs"] [aria-selected="true"] { background:#fff; color:var(--plum); box-shadow:0 4px 12px rgba(50,22,65,.08); }
        .stButton > button, .stDownloadButton > button { border-radius:12px !important; min-height:2.7rem; border:1px solid var(--plum); font-weight:700; color:var(--plum); background:#fff; }
        .stButton > button[kind="primary"] { background:linear-gradient(110deg,var(--plum),#5b2c70); color:white; border:0; }
        .stButton > button:hover, .stDownloadButton > button:hover { border-color:var(--pink); color:var(--pink); box-shadow:0 6px 16px rgba(255,79,154,.10); }
        [data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:14px; overflow:hidden; }
        footer, #MainMenu, [data-testid="stToolbar"], [data-testid="stAppDeployButton"] { visibility:hidden; }
        header[data-testid="stHeader"] { background:transparent; }
        @media (max-width:980px) { .loop-strip { grid-template-columns:1fr 1fr; } .block-container { padding:1.4rem 1.2rem 4rem; } }
        @media (max-width:780px) { .ops-title { font-size:2.3rem; } .hero-panel { padding:1.6rem; border-radius:20px; } .loop-strip { grid-template-columns:1fr; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        '<div class="hero-panel">'
        f'<div class="ops-eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1 class="ops-title">{html.escape(title)}</h1>'
        f'<p class="ops-subtitle">{html.escape(subtitle)}</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def section(title: str, label: str = "") -> None:
    if label:
        st.markdown(f'<div class="section-label">{html.escape(label)}</div>', unsafe_allow_html=True)
    st.markdown(f'<h2 class="section-title">{html.escape(title)}</h2>', unsafe_allow_html=True)


def section_copy(copy: str) -> None:
    st.markdown(f'<p class="section-copy">{html.escape(copy)}</p>', unsafe_allow_html=True)


def data_banner(meta: dict[str, Any]) -> None:
    mode = str(meta.get("mode", "demo"))
    css = "live" if mode == DataMode.LIVE.value else ""
    st.markdown(
        f'<div class="data-banner {css}"><strong>{html.escape(mode.upper())} DATA · {html.escape(str(meta.get("period", "")))}</strong><br>'
        f'{html.escape(str(meta.get("notice", "")))} Last updated: {html.escape(str(meta.get("generated_at", "Unknown")))}.</div>',
        unsafe_allow_html=True,
    )


def source_badges(*labels: str, mode: str = "fixture") -> None:
    badges = "".join(f'<span class="source-badge {html.escape(mode)}">{html.escape(label)}</span>' for label in labels)
    st.markdown(badges, unsafe_allow_html=True)


def metric(
    label: str,
    value: str | int | float,
    *,
    delta: str | None = None,
    source: str,
    definition: str,
    mode: str = "fixture",
) -> None:
    st.metric(label, value, delta=delta)
    source_badges(source, mode=mode)
    st.markdown(f'<div class="metric-note">{html.escape(definition)}</div>', unsafe_allow_html=True)


def hkd_metric(label: str, value: float, **kwargs: Any) -> None:
    metric(label, format_hkd(value), **kwargs)


def kpi_card(
    label: str,
    value: str,
    *,
    source: str,
    definition: str,
    delta: str = "",
    tone: str = "pink",
    warning: bool = False,
) -> None:
    safe_tone = tone if tone in {"pink", "violet", "teal", "coral"} else "pink"
    delta_class = " warn" if warning else ""
    st.markdown(
        f'<div class="kpi-card {safe_tone}">'
        '<div class="kpi-top">'
        f'<div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-source">{html.escape(source)}</div>'
        '</div>'
        f'<div class="kpi-value">{html.escape(value)}</div>'
        f'<div class="kpi-delta{delta_class}">{html.escape(delta) if delta else "&nbsp;"}</div>'
        f'<div class="kpi-definition">{html.escape(definition)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def operating_loop() -> None:
    steps = [
        ("01", "Measure"),
        ("02", "Decide"),
        ("03", "Create"),
        ("04", "Approve"),
        ("05", "Learn"),
    ]
    markup = '<div class="loop-strip">' + "".join(
        f'<div class="loop-step"><strong>{number}</strong>{label}</div>' for number, label in steps
    ) + "</div>"
    st.markdown(markup, unsafe_allow_html=True)


def scope_card(icon: str, title: str, state: str, copy: str) -> None:
    st.markdown(
        '<div class="scope-card">'
        f'<div class="scope-icon">{html.escape(icon)}</div>'
        f'<div class="scope-title">{html.escape(title)}</div>'
        f'<div class="scope-state">{html.escape(state)}</div>'
        f'<div class="scope-copy">{html.escape(copy)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def trust_row(title: str, copy: str, *, warning: bool = False) -> None:
    css = " warn" if warning else ""
    mark = "!" if warning else "✓"
    st.markdown(
        f'<div class="trust-row{css}"><div class="trust-mark">{mark}</div><div>'
        f'<strong>{html.escape(title)}</strong><span>{html.escape(copy)}</span>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def dataframe(rows: list[dict[str, Any]], *, height: int | None = None, column_config: dict[str, Any] | None = None) -> None:
    if not rows:
        st.info("No records are available for the selected view.")
        return
    options: dict[str, Any] = {
        "width": "stretch",
        "hide_index": True,
        "column_config": column_config,
    }
    if height is not None:
        options["height"] = height
    st.dataframe(pd.DataFrame(rows), **options)


def permission_guard(identity: UserIdentity, permission: Permission, action_label: str) -> bool:
    allowed = has_permission(identity.role, permission)
    if not allowed:
        st.caption(f"{action_label} is unavailable to the {identity.role.value} role.")
    return allowed


def signal_card(
    signal: Signal,
    *,
    identity: UserIdentity,
    on_create_task: Any,
    key: str,
) -> None:
    css = signal.severity.value.lower()
    with st.container(border=True):
        st.markdown(f'<div class="signal-{css}"><div class="signal-meta">{html.escape(signal.severity.value)} · {html.escape(signal.source_system)} · confidence {signal.confidence:.0%}</div><div class="signal-head">{html.escape(signal.title)}</div></div>', unsafe_allow_html=True)
        st.write(signal.description)
        cols = st.columns(2)
        with cols[0]:
            st.markdown("**Why it matters**")
            st.write(signal.why_it_matters)
            st.markdown("**Evidence**")
            st.write(signal.evidence)
        with cols[1]:
            st.markdown("**Recommended action**")
            st.write(signal.recommended_action)
            st.markdown("**Success measure**")
            st.write(signal.success_measure)
        with st.expander("Step-by-step playbook and safeguards"):
            for index, step in enumerate(signal.playbook, 1):
                st.write(f"{index}. {step}")
            st.caption(f"Owner: {signal.owner_role.value} · Freshness: {signal.data_freshness} · Rule: {signal.rule_id} v{signal.rule_version} · Data mode: {signal.data_mode.value}")
        if permission_guard(identity, Permission.MANAGE_TASKS, "Create task"):
            if st.button("Create owned task", key=key, type="primary"):
                task_id = on_create_task(signal)
                st.success(f"Task created ({task_id[:8]}…). It remains fixture/demo work and cannot trigger a live action.")


def workflow_status(current: str, steps: list[str]) -> None:
    markup = '<div class="workflow">' + "".join(f'<span class="{"active" if step == current else ""}">{html.escape(step)}</span>' for step in steps) + "</div>"
    st.markdown(markup, unsafe_allow_html=True)


def default_date_range() -> tuple[date, date]:
    return date(2026, 7, 1), date(2026, 7, 31)
