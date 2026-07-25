from __future__ import annotations

import hashlib
import hmac
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image, ImageChops

from src.analysis.listening import build_listening_plan
from src.analysis.matching import match_products
from src.analysis.trends import (
    generic_term_catalogue,
    merge_trend_signals,
    sanitize_snapshot_trends,
    score_google_series,
)
from src.config import Settings, load_settings
from src.connectors.apify_x import ApifyXConnector
from src.connectors.catalog_csv import SIMPLE_CSV_TEMPLATE, parse_product_csv
from src.connectors.google_trends import GoogleTrendsConnector
from src.connectors.openrouter import OpenRouterConnector
from src.connectors.shopify import ShopifyConnector
from src.demo_data import demo_snapshot
from src.diagnostics import (
    diagnostic_report,
    hybrid_explanation,
    safe_error,
    source_diagnostic_rows,
)
from src.pipeline import refresh_snapshot
from src.storage import load_snapshot, save_snapshot


ROOT = Path(__file__).resolve().parent
PINK = "#ff3f98"
INK = "#111111"
LILAC = "#9a8fd8"
SAND = "#c8aa82"
PALETTE = [PINK, INK, LILAC, "#e8a846", "#6f8e84", "#d46262"]
CATALOGUE_CSV = "Upload CSV"
CATALOGUE_API = "Shopify API"
CATALOGUE_SELECTOR_KEY = "catalogue_source_selector_v2"
APP_BUILD = "2026.07.25.1"
DECISION_COLORS = {
    "Act now": PINK,
    "Test this week": "#e8a846",
    "Watch": "#77736f",
}

st.set_page_config(
    page_title="HULA Trend Intelligence",
    page_icon="◯",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Caveat:wght@500;600&family=Manrope:wght@300;400;500;600;700&display=swap');
        :root { --pink:#ff3f98; --ink:#111; --paper:#fff; --mist:#f5f4f1; --line:#dedbd5; }
        html, body, [class*="css"] { font-family:'Manrope', sans-serif; color:var(--ink); }
        .stApp { background:#fff; }
        .block-container { padding-top:2.3rem; padding-bottom:5rem; max-width:1500px; }
        [data-testid="stSidebar"] { background:#fff; border-right:1px solid #e7e4df; min-width:255px; }
        [data-testid="stSidebar"] .block-container { padding-top:1.35rem; }
        [data-testid="stSidebar"] [data-testid="stImage"] img { object-fit:contain !important; aspect-ratio:auto !important; }
        [data-testid="stSidebar"] [role="radiogroup"] label { padding:.48rem .25rem; }
        [data-testid="stSidebar"] [role="radiogroup"] label p { font-size:.76rem; letter-spacing:.12em; font-weight:600; }
        [data-testid="stMetric"] { border:1px solid var(--line); padding:1.1rem 1.2rem; background:#fff; min-height:125px; }
        [data-testid="stMetricLabel"] p { letter-spacing:.07em; text-transform:uppercase; font-size:.68rem; color:#6f6b67; }
        [data-testid="stMetricValue"] { font-weight:400; }
        [data-testid="stImage"] img { background:#f3f1ed; object-fit:cover; }
        .brand-lockup { text-align:center; margin:-.1rem 0 1.8rem; }
        .brand-lockup .data { font-size:.66rem; text-transform:uppercase; letter-spacing:.15em; }
        .brand-lockup .teri { display:block; font-family:'Caveat', cursive; font-size:1.48rem; line-height:1; color:var(--pink); transform:rotate(-3deg); margin-top:.15rem; }
        .eyebrow { font-size:.68rem; letter-spacing:.16em; text-transform:uppercase; color:#746f6b; margin-bottom:.6rem; }
        .page-title { font-size:clamp(2.25rem,4vw,4.9rem); font-weight:300; letter-spacing:-.055em; line-height:1.01; max-width:1000px; margin:0 0 .8rem; }
        .page-subtitle { max-width:780px; color:#625e5a; font-size:1rem; line-height:1.6; margin:0 0 1.7rem; }
        .pink-rule { width:82px; height:7px; background:var(--pink); margin:1.1rem 0 2.1rem; }
        .section-kicker { font-size:.7rem; letter-spacing:.15em; text-transform:uppercase; color:#746f6b; margin-top:2.2rem; }
        .section-title { font-size:1.72rem; font-weight:400; letter-spacing:-.035em; margin:.25rem 0 1.25rem; }
        .trend-card { border-top:3px solid #111; padding:1.15rem .2rem 1rem; min-height:190px; }
        .trend-card.hot { border-top-color:var(--pink); }
        .trend-rank { font-size:.66rem; letter-spacing:.13em; color:#7a7570; text-transform:uppercase; }
        .trend-name { font-size:1.35rem; letter-spacing:-.035em; margin:.55rem 0 .65rem; }
        .trend-score { font-size:2.35rem; font-weight:300; line-height:1; }
        .trend-score span { font-size:.72rem; color:#777; }
        .micro { color:#706c68; font-size:.76rem; line-height:1.45; }
        .pill { display:inline-block; border:1px solid #d9d5d0; border-radius:999px; padding:.28rem .55rem; margin:.15rem .2rem .15rem 0; font-size:.64rem; letter-spacing:.05em; text-transform:uppercase; }
        .pill.pink { background:#fff0f7; border-color:#ffc3df; color:#b30055; }
        .mode-banner { border-left:7px solid var(--pink); background:#fff4f9; padding:.8rem 1rem; margin:0 0 1.6rem; font-size:.82rem; }
        .editorial-box { background:#111; color:#fff; padding:2rem; min-height:260px; }
        .editorial-box .label { color:#ff8ac0; font-size:.68rem; letter-spacing:.15em; text-transform:uppercase; }
        .editorial-box h3 { font-weight:300; font-size:2rem; letter-spacing:-.04em; margin:.7rem 0; }
        .editorial-box p { color:#d7d4d2; line-height:1.65; }
        .score-row { display:flex; justify-content:space-between; border-top:1px solid #e4e1dc; padding:.55rem 0; font-size:.77rem; }
        .source-card { border:1px solid #dedbd5; padding:1rem; min-height:130px; }
        .source-name { font-size:.76rem; letter-spacing:.1em; text-transform:uppercase; }
        .source-state { font-size:1.1rem; margin:.65rem 0 .25rem; }
        .dot { width:9px; height:9px; border-radius:50%; display:inline-block; margin-right:.4rem; background:#aaa; }
        .dot.live { background:#27a05a; } .dot.demo { background:#e8a846; } .dot.fail { background:#d64848; }
        .method-note { border:1px solid #dedbd5; background:#f8f7f5; padding:1.2rem; color:#5f5b57; line-height:1.6; font-size:.82rem; }
        .decision-key { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.7rem; margin:.2rem 0 1rem; }
        .decision-item { border:1px solid #dedbd5; padding:.8rem .9rem; font-size:.76rem; line-height:1.45; background:#fff; }
        .decision-swatch { display:inline-block; width:11px; height:11px; border-radius:50%; margin-right:.45rem; }
        .decision-item strong { display:block; margin-bottom:.25rem; font-size:.8rem; }
        .st-key-product-trend-picker details { border:2px solid #111 !important; border-left:7px solid var(--pink) !important; background:#fff !important; }
        .st-key-product-trend-picker summary { min-height:4.1rem; padding:.85rem 1rem !important; align-items:center; }
        .st-key-product-trend-picker summary p { font-size:1rem !important; font-weight:650 !important; letter-spacing:.025em; }
        .st-key-product-trend-picker [data-testid="stExpanderDetails"] { border-top:1px solid #dedbd5; padding-top:.8rem; }
        .stButton > button, .stDownloadButton > button { border-radius:0 !important; min-height:2.9rem; border:1px solid #111; font-weight:600; letter-spacing:.03em; }
        .stButton > button[kind="primary"] { background:#111; color:#fff; }
        .stButton > button:hover, .stDownloadButton > button:hover { border-color:var(--pink); color:var(--pink); }
        div[data-testid="stProgress"] > div > div > div { background-color:var(--pink); }
        div[data-testid="stVerticalBlockBorderWrapper"] { border-radius:0; }
        footer, #MainMenu { visibility:hidden; }
        @media (max-width: 780px) { .page-title { font-size:2.4rem; } .block-container { padding-top:1.3rem; } .decision-key { grid-template-columns:1fr; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def cropped_logo() -> bytes:
    image = Image.open(ROOT / "assets" / "hula_logo.png").convert("RGB")
    background = Image.new("RGB", image.size, "white")
    difference = ImageChops.difference(image, background).convert("L")
    difference = difference.point(lambda pixel: 255 if pixel > 22 else 0)
    box = difference.getbbox()
    if box:
        left, top, right, bottom = box
        padding = 22
        box = (
            max(0, left - padding),
            max(0, top - padding),
            min(image.width, right + padding),
            min(image.height, bottom + padding),
        )
        image = image.crop(box)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def require_password(settings: Settings) -> None:
    if not settings.app_password:
        return
    expected = hashlib.sha256(settings.app_password.encode()).digest()
    if st.session_state.get("authenticated"):
        return
    left, centre, right = st.columns([1, 1.2, 1])
    with centre:
        st.image(cropped_logo(), width=130)
        st.markdown("### HULA Trend Intelligence")
        with st.form("login"):
            supplied = st.text_input("Team password", type="password")
            submitted = st.form_submit_button("Enter", type="primary", width="stretch")
        if submitted:
            actual = hashlib.sha256(supplied.encode()).digest()
            if hmac.compare_digest(actual, expected):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("That password is not correct.")
    st.stop()


def hk_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        parsed = datetime.now(tz=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo("Asia/Hong_Kong"))


def page_header(eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="eyebrow">{html.escape(eyebrow)}</div>
        <h1 class="page-title">{html.escape(title)}</h1>
        <div class="pink-rule"></div>
        <p class="page-subtitle">{html.escape(subtitle)}</p>
        """,
        unsafe_allow_html=True,
    )


def section_header(kicker: str, title: str) -> None:
    st.markdown(
        f'<div class="section-kicker">{html.escape(kicker)}</div><div class="section-title">{html.escape(title)}</div>',
        unsafe_allow_html=True,
    )


def plot_layout(figure: go.Figure, height: int = 430) -> go.Figure:
    figure.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=35, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Manrope, sans-serif", color=INK, size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="white", font_color=INK),
    )
    figure.update_xaxes(showgrid=False, zeroline=False, linecolor="#d9d5d0")
    figure.update_yaxes(gridcolor="#ece9e5", zeroline=False)
    return figure


def business_decision(trend: dict) -> str:
    """Translate the evidence score into one plain-language business action."""

    score = float(trend.get("score") or 0)
    sources = set(trend.get("sources") or [])
    cross_source = "Google Trends" in sources and bool(
        sources & {"Open X topics", "Expert fashion panel", "Visual validation"}
    )
    confidence = str(trend.get("confidence") or "")
    if score >= 75 and cross_source and confidence in {"High", "Medium"}:
        return "Act now"
    if score >= 55:
        return "Test this week"
    return "Watch"


def decision_legend() -> None:
    st.markdown(
        f"""
        <div class="decision-key">
          <div class="decision-item"><strong><span class="decision-swatch" style="background:{DECISION_COLORS['Act now']}"></span>ACT NOW</strong>Strong signal confirmed across search and conversation.</div>
          <div class="decision-item"><strong><span class="decision-swatch" style="background:{DECISION_COLORS['Test this week']}"></span>TEST THIS WEEK</strong>Promising enough for a small content or merchandising test.</div>
          <div class="decision-item"><strong><span class="decision-swatch" style="background:{DECISION_COLORS['Watch']}"></span>WATCH</strong>Keep monitoring; evidence is not strong enough to prioritise.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def radar_rank_chart(trends: list[dict], *, limit: int = 10) -> go.Figure:
    """A business-first ranking without overlapping labels or raw growth outliers."""

    rows = sorted(
        trends,
        key=lambda row: float(row.get("score") or 0),
        reverse=True,
    )[:limit]
    ordered_names = [str(row.get("name") or "Untitled trend") for row in rows]
    figure = go.Figure()
    for decision in ("Act now", "Test this week", "Watch"):
        selected = [row for row in rows if business_decision(row) == decision]
        if not selected:
            continue
        figure.add_trace(
            go.Bar(
                x=[float(row.get("score") or 0) for row in selected],
                y=[str(row.get("name") or "Untitled trend") for row in selected],
                orientation="h",
                name=decision,
                marker=dict(color=DECISION_COLORS[decision]),
                text=[f"{float(row.get('score') or 0):.0f}" for row in selected],
                textposition="outside",
                cliponaxis=False,
                customdata=[
                    [
                        decision,
                        str(row.get("confidence") or "—"),
                        " + ".join(row.get("sources") or []) or "One available source",
                    ]
                    for row in selected
                ],
                hovertemplate=(
                    "<b>%{y}</b><br>Priority score: %{x:.0f}/100"
                    "<br>Decision: %{customdata[0]}"
                    "<br>Confidence: %{customdata[1]}"
                    "<br>Evidence: %{customdata[2]}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        barmode="overlay",
        bargap=0.34,
        xaxis=dict(
            title="Priority score (0–100)",
            range=[0, 108],
            dtick=20,
            showgrid=True,
            gridcolor="#ece9e5",
            zeroline=False,
        ),
        yaxis=dict(
            title="",
            categoryorder="array",
            categoryarray=list(reversed(ordered_names)),
            tickfont=dict(size=13),
        ),
    )
    return plot_layout(figure, max(430, 64 * len(rows) + 120))


def mode_banner(meta: dict) -> None:
    mode = str(meta.get("mode", "demo")).lower()
    if mode == "live":
        return
    label = "DEMO MODE" if mode == "demo" else "HYBRID MODE"
    copy = hybrid_explanation(meta)
    st.markdown(
        f'<div class="mode-banner"><strong>{label}</strong> · {html.escape(copy)}</div>',
        unsafe_allow_html=True,
    )


def catalogue_choice(snapshot: dict) -> str:
    source = str((snapshot.get("meta") or {}).get("catalogue_source", ""))
    return CATALOGUE_CSV if source == "csv" else CATALOGUE_API


def catalogue_refresh_args(snapshot: dict) -> tuple[str, list[dict] | None]:
    # This key belongs to the radio widget below. Read it, but never assign to it
    # directly: Streamlit raises an exception if widget-owned state is changed
    # after the widget has been instantiated during the current run.
    choice = st.session_state.get(CATALOGUE_SELECTOR_KEY, catalogue_choice(snapshot))
    if choice == CATALOGUE_CSV:
        meta = snapshot.get("meta") or {}
        if meta.get("catalogue_source") == "csv":
            return "csv", list(snapshot.get("products") or [])
        return "csv", None
    return "shopify_api", None


def trend_cards(trends: list[dict], count: int = 4) -> None:
    columns = st.columns(min(count, 4))
    for index, trend in enumerate(trends[:count]):
        with columns[index % len(columns)]:
            sources = " + ".join(trend.get("sources", [])) or "Demo sources"
            st.markdown(
                f"""
                <div class="trend-card {'hot' if index == 0 else ''}">
                  <div class="trend-rank">#{index + 1} · {html.escape(str(trend.get('stage', '')))}</div>
                  <div class="trend-name">{html.escape(str(trend.get('name', '')))}</div>
                  <div class="trend-score">{float(trend.get('score', 0)):.0f}<span> / 100</span></div>
                  <div style="margin:.7rem 0"><span class="pill pink">{html.escape(str(trend.get('confidence', '')))} confidence</span></div>
                  <div class="micro">{html.escape(sources)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def product_lookup(snapshot: dict) -> dict[str, dict]:
    return {str(product.get("id")): product for product in snapshot.get("products", [])}


def recommendation_rows(snapshot: dict, trend_id: str | None = None) -> list[dict]:
    rows = snapshot.get("recommendations", [])
    if trend_id:
        rows = [row for row in rows if str(row.get("trend_id")) == trend_id]
    return sorted(rows, key=lambda row: float(row.get("opportunity_score", 0)), reverse=True)


def product_image(product: dict) -> None:
    source = product.get("image_url")
    if source and str(source).startswith("assets/"):
        source = ROOT / str(source)
    if source:
        st.image(source, width="stretch")
    else:
        st.markdown(
            '<div style="height:260px;background:#f2f0ec;display:flex;align-items:center;justify-content:center;color:#918b85;font-size:.72rem;letter-spacing:.12em">NO IMAGE</div>',
            unsafe_allow_html=True,
        )


def format_price(product: dict) -> str:
    if product.get("is_demo"):
        return "Example catalogue item"
    currency = str(product.get("currency") or "HKD")
    amount = float(product.get("price") or 0)
    return f"{currency} {amount:,.0f}"


def render_product_grid(snapshot: dict, rows: list[dict], count: int = 6) -> None:
    products = product_lookup(snapshot)
    selected = rows[:count]
    if not selected:
        st.info("No in-stock catalogue match cleared the minimum relevance threshold.")
        return
    for start in range(0, len(selected), 3):
        columns = st.columns(3)
        for column, recommendation in zip(columns, selected[start : start + 3]):
            product = products.get(str(recommendation.get("product_id")))
            if not product:
                continue
            with column:
                with st.container(border=True):
                    product_image(product)
                    badge = "DEMO · " if product.get("is_demo") else ""
                    st.caption(f"{badge}{product.get('vendor', '')} · {product.get('product_type', '')}")
                    st.markdown(f"#### {product.get('title', 'Untitled product')}")
                    st.caption(format_price(product))
                    score = float(recommendation.get("opportunity_score", 0))
                    st.markdown(f"**Opportunity score · {score:.0f}/100**")
                    st.progress(max(0.0, min(1.0, score / 100)))
                    st.markdown(
                        f"""
                        <span class="pill">Trend {float(recommendation.get('trend_score', 0)):.0f}</span>
                        <span class="pill">Match {float(recommendation.get('match_score', 0)):.0f}</span>
                        <span class="pill">Ready {float(recommendation.get('readiness_score', 0)):.0f}</span>
                        """,
                        unsafe_allow_html=True,
                    )
                    st.caption(str(recommendation.get("reason", "")))
                    links = st.columns(2)
                    if product.get("product_url"):
                        links[0].link_button("View product", product["product_url"], width="stretch")
                    if product.get("admin_url"):
                        links[1].link_button("Open Shopify", product["admin_url"], width="stretch")


def line_chart(trends: list[dict], selected_ids: list[str] | None = None) -> go.Figure:
    figure = go.Figure()
    filtered = trends
    if selected_ids:
        filtered = [trend for trend in trends if str(trend.get("id")) in selected_ids]
    for index, trend in enumerate(filtered):
        points = trend.get("series") or []
        if not points:
            continue
        figure.add_trace(
            go.Scatter(
                x=[point.get("date") for point in points],
                y=[point.get("value") for point in points],
                mode="lines",
                name=str(trend.get("name")),
                line=dict(color=PALETTE[index % len(PALETTE)], width=3),
                hovertemplate="%{x}<br>Relative interest: %{y}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_yaxes(title="Anchor-calibrated relative search interest", rangemode="tozero")
    return plot_layout(figure)


def this_week(snapshot: dict) -> None:
    meta = snapshot.get("meta", {})
    trends = snapshot.get("trends", [])
    updated = hk_time(str(meta.get("generated_at", "")))
    week_label = f"WEEK {updated.isocalendar().week} · GLOBAL FASHION"
    page_header(
        week_label,
        "What HULA should talk about now.",
        "A weekly view of rising fashion demand, social conversation and the pre-owned HULA pieces ready to meet it.",
    )
    mode_banner(meta)
    top_score = float(trends[0].get("score", 0)) if trends else 0
    high_confidence = sum(1 for trend in trends if trend.get("confidence") == "High")
    unique_products = len({row.get("product_id") for row in snapshot.get("recommendations", [])})
    metrics = st.columns(4)
    metrics[0].metric("Strongest signal", f"{top_score:.0f}/100", trends[0].get("name") if trends else "—")
    metrics[1].metric("Cross-source trends", high_confidence, "Google + open X agreement")
    metrics[2].metric("Promotable products", unique_products, "in-stock catalogue matches")
    metrics[3].metric("Updated", updated.strftime("%d %b · %H:%M"), "Hong Kong time")

    section_header("01 · Signal board", "This week's strongest opportunities")
    trend_cards(trends, 4)
    filtered_count = len((meta.get("filtered_terms") or []))
    if filtered_count:
        st.caption(
            f"Quality control removed {filtered_count} irrelevant or overly broad term(s) before this page was built. "
            "The complete list is in Data & Setup."
        )

    section_header("02 · Momentum", "Search interest over the last 13 weeks")
    st.plotly_chart(
        line_chart(trends[:5]),
        width="stretch",
        config={"displayModeBar": False},
    )
    st.caption("Google Trends values are relative indices, not absolute search volumes. Live multi-query batches are approximately aligned with one repeated anchor term; demo mode uses illustrative series.")

    section_header("03 · Catalogue opportunity", "Products to put in front of people now")
    top_recommendations = []
    seen_products: set[str] = set()
    for recommendation in recommendation_rows(snapshot):
        product_id = str(recommendation.get("product_id"))
        if product_id not in seen_products:
            top_recommendations.append(recommendation)
            seen_products.add(product_id)
        if len(top_recommendations) == 6:
            break
    render_product_grid(snapshot, top_recommendations)

    section_header("04 · Direction", "The editorial idea behind the numbers")
    left, right = st.columns([1.05, 1], gap="large")
    top = trends[0] if trends else {}
    with left:
        st.markdown(
            f"""
            <div class="editorial-box">
              <div class="label">Lead story</div>
              <h3>{html.escape(str(top.get('name', 'A trend worth watching')))}</h3>
              <p>{html.escape(str(top.get('why_now', 'Connect live sources to generate an evidence-led rationale.')))}</p>
              <div class="pill pink">{html.escape(str(top.get('stage', '')))}</div>
              <div class="pill">{html.escape(str(top.get('category', '')))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("#### Recommended content ladder")
        for number, angle in enumerate(top.get("content_angles", [])[:3], 1):
            st.markdown(f"**0{number}** · {angle}")
        st.info("Use the Campaign Studio to turn this signal into a Reel, email or store activation brief.")


def trend_radar(snapshot: dict) -> None:
    trends = snapshot.get("trends", [])
    page_header(
        "TREND RADAR · EXTERNAL SIGNALS",
        "Know what to act on first.",
        "A plain-language priority view for this week. The score combines the available search, open-conversation and expert evidence; the colour tells the team what to do next.",
    )
    meta = snapshot.get("meta", {})
    mode_banner(meta)
    if not trends:
        st.warning(
            "No specific, actionable trend rows are available. Broad labels were removed; run a refresh to collect a new set."
        )
        return
    google_status = str((meta.get("source_status") or {}).get("google_trends", ""))
    if not google_status.startswith("live") and "manual CSV" not in google_status:
        st.warning(
            "Google search evidence was unavailable on the last refresh. The radar still ranks the other evidence, "
            "but no trend can receive the green-light 'Act now' decision until search demand is confirmed."
        )

    section_header("Priority view", "What to do with each trend")
    decision_legend()
    st.plotly_chart(
        radar_rank_chart(trends),
        width="stretch",
        config={"displayModeBar": False},
    )
    st.caption(
        "The score is always 0–100. Raw growth percentages are kept in Analyst detail below, where they cannot distort the chart scale."
    )

    decisions = [business_decision(trend) for trend in trends]
    summary = st.columns(3)
    summary[0].metric("Act now", decisions.count("Act now"), "cross-source confirmation")
    summary[1].metric("Test this week", decisions.count("Test this week"), "small controlled test")
    summary[2].metric("Watch", decisions.count("Watch"), "not yet a priority")

    section_header("Ranked view", "The decision list")
    table = pd.DataFrame(
        [
            {
                "Rank": index + 1,
                "Trend": trend.get("name"),
                "Decision": business_decision(trend),
                "Priority score": f"{float(trend.get('score') or 0):.0f}/100",
                "Google demand": (
                    f"{float(trend.get('google_score')):.0f}/100"
                    if trend.get("google_score") is not None
                    else "Not available"
                ),
                "X conversation": (
                    f"{float(trend.get('x_score')):.0f}/100"
                    if trend.get("x_score") is not None
                    else "Not available"
                ),
                "Confidence": trend.get("confidence"),
            }
            for index, trend in enumerate(trends)
        ]
    )
    st.dataframe(table, hide_index=True, width="stretch")

    with st.expander("Analyst detail · raw growth and evidence checks"):
        technical = pd.DataFrame(
            [
                {
                    "Trend": trend.get("name"),
                    "Search vs baseline": f"{float(trend.get('search_momentum', 0)):+.0f}%",
                    "X posts week on week": f"{float(trend.get('mention_growth', 0)):+.0f}%",
                    "Independent authors week on week": f"{float(trend.get('author_growth', 0)):+.0f}%",
                    "Current independent authors": int(trend.get("unique_authors", 0)),
                    "Expert mentions": int(trend.get("expert_mentions", 0)),
                    "Evidence quality": f"{float(trend.get('evidence_quality', 0)):.0f}/100",
                }
                for trend in trends
            ]
        )
        st.dataframe(technical, hide_index=True, width="stretch")
        st.caption(
            "Very large percentages often happen when the previous week had only one or two mentions. "
            "They are useful evidence, but they are not shown as chart axes."
        )

    section_header("Deep dive", "Inspect one signal")
    selected_name = st.selectbox("Trend", [trend.get("name") for trend in trends], key="radar_trend")
    selected = next(trend for trend in trends if trend.get("name") == selected_name)
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.plotly_chart(
            line_chart([selected]), width="stretch", config={"displayModeBar": False}
        )
    with right:
        st.markdown(f"### {selected.get('name')}")
        st.write(selected.get("why_now"))
        st.markdown(
            f"""
            <div class="score-row"><span>Combined signal</span><strong>{float(selected.get('score', 0)):.0f}</strong></div>
            <div class="score-row"><span>Google component</span><strong>{float(selected.get('google_score') or 0):.0f}</strong></div>
            <div class="score-row"><span>Open X component</span><strong>{float(selected.get('x_score') or 0):.0f}</strong></div>
            <div class="score-row"><span>Expert-panel component</span><strong>{float(selected.get('expert_score') or 0):.0f}</strong></div>
            <div class="score-row"><span>Independent authors</span><strong>{int(selected.get('unique_authors') or 0)}</strong></div>
            <div class="score-row"><span>Evidence quality</span><strong>{float(selected.get('evidence_quality') or 0):.0f}</strong></div>
            <div class="score-row"><span>Confidence</span><strong>{html.escape(str(selected.get('confidence', '')))}</strong></div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Evidence quality penalises duplicated, promotional and author-dominated conversation. "
            "Expert-panel confirmation is scored separately from open topic discovery."
        )


def product_trend_picker(trends: list[dict]) -> str:
    names = [str(trend.get("name") or "") for trend in trends if trend.get("name")]
    selected = str(st.session_state.get("product_trend_choice") or names[0])
    if selected not in names:
        st.session_state.pop("product_trend_choice", None)
        selected = names[0]
    trend_by_name = {str(trend.get("name")): trend for trend in trends}
    st.caption("Click the panel below to open the full trend list.")
    with st.container(key="product-trend-picker"):
        with st.expander(f"CHOOSE A TREND  ▾  ·  CURRENT: {selected}"):
            selected = st.radio(
                "Available trends",
                names,
                index=names.index(selected),
                key="product_trend_choice",
                label_visibility="collapsed",
                format_func=lambda name: (
                    f"{name}  ·  {business_decision(trend_by_name[name])}"
                ),
            )
            st.caption(
                "Select one trend; the product ranking below updates immediately."
            )
    return selected


def product_match_page(snapshot: dict) -> None:
    trends = snapshot.get("trends", [])
    page_header(
        "PRODUCT MATCH · CATALOGUE",
        "Turn a signal into a sellable edit.",
        "Rank in-stock HULA pieces by trend fit, external momentum, content readiness and catalogue freshness.",
    )
    mode_banner(snapshot.get("meta", {}))
    if not trends:
        return
    selected_name = product_trend_picker(trends)
    trend = next(item for item in trends if item.get("name") == selected_name)
    with st.expander("Adjust recommendation weights"):
        columns = st.columns(4)
        trend_weight = columns[0].slider("Trend strength", 0, 100, 45, help="External Google + X evidence")
        match_weight = columns[1].slider("Catalogue fit", 0, 100, 35, help="Title, tags, description and product type")
        readiness_weight = columns[2].slider("Content readiness", 0, 100, 15, help="In stock, imagery and product copy")
        freshness_weight = columns[3].slider("Newness", 0, 100, 5, help="How recently the item entered the catalogue")
        st.caption("The app normalises these values automatically. HULA's one-of-one inventory is treated as fully available when stock is 1.")
    custom_rows = match_products(
        [trend],
        snapshot.get("products", []),
        weights={
            "trend": trend_weight,
            "match": match_weight,
            "readiness": readiness_weight,
            "freshness": freshness_weight,
        },
    )
    top = st.columns(3)
    top[0].metric("Trend signal", f"{float(trend.get('score', 0)):.0f}/100", trend.get("stage"))
    top[1].metric("Eligible matches", len(custom_rows), "in stock and relevant")
    best = float(custom_rows[0].get("opportunity_score", 0)) if custom_rows else 0
    top[2].metric("Best opportunity", f"{best:.0f}/100", "human review still required")
    section_header("Recommended edit", f"Best HULA pieces for {selected_name}")
    render_product_grid(snapshot, custom_rows, count=9)
    st.markdown(
        '<div class="method-note"><strong>Guardrail:</strong> a high score means “good candidate for review”, not guaranteed sales. Before publishing, confirm condition, exact stock, provenance claims, margin and whether the item has appeared too recently in another campaign.</div>',
        unsafe_allow_html=True,
    )


def fallback_campaign(trend: dict, products: list[dict], channel: str, objective: str) -> dict:
    names = [str(product.get("title")) for product in products[:4]]
    joined = ", ".join(names[:-1]) + (f" and {names[-1]}" if len(names) > 1 else (names[0] if names else "the HULA edit"))
    return {
        "campaign_name": f"The {trend.get('name')} Edit",
        "insight": trend.get("why_now", "The signal is strengthening across the selected sources."),
        "hook": f"The trend is everywhere. The best version may already exist.",
        "caption": (
            f"{trend.get('name')} is having a moment — and HULA already has the pieces. "
            f"Discover {joined}. Pre-owned, one of a kind and available while it lasts."
        ),
        "shot_list": [
            "Open on the strongest silhouette in a clean, gallery-like frame",
            "Cut to three fast close-ups: texture, hardware and styling detail",
            "Show each selected piece worn or moving, not only on a rail",
            "Finish with the full HULA edit and a direct availability CTA",
        ],
        "story_frames": [
            f"Frame 1: '{trend.get('name')} is rising' with one evidence point",
            "Frame 2: product poll — which piece would you wear?",
            "Frame 3: link or Soho-store CTA",
        ],
        "cta": "Shop the edit online or visit HULA Soho before the one-of-one pieces are gone.",
        "proof_points": [f"Objective: {objective}", f"Format: {channel}", "Pre-owned designer fashion", "One-of-one availability"],
        "avoid": ["Do not call an item rare, runway or archival without verified product evidence."],
    }


def campaign_markdown(brief: dict) -> str:
    shot_list = "\n".join(f"- {item}" for item in brief.get("shot_list", []))
    story_frames = "\n".join(f"- {item}" for item in brief.get("story_frames", []))
    proof = "\n".join(f"- {item}" for item in brief.get("proof_points", []))
    avoid = "\n".join(f"- {item}" for item in brief.get("avoid", []))
    return f"""# {brief.get('campaign_name', 'HULA Campaign')}

## Insight
{brief.get('insight', '')}

## Hook
{brief.get('hook', '')}

## Caption
{brief.get('caption', '')}

## Shot list
{shot_list}

## Story frames
{story_frames}

## CTA
{brief.get('cta', '')}

## Proof points
{proof}

## Avoid
{avoid}
"""


def campaign_studio(snapshot: dict, settings: Settings) -> None:
    trends = snapshot.get("trends", [])
    products_by_id = product_lookup(snapshot)
    page_header(
        "CAMPAIGN STUDIO · QWEN",
        "From evidence to an idea worth making.",
        "Choose the signal and products; the studio turns them into a HULA-ready brief without inventing provenance or rarity.",
    )
    mode_banner(snapshot.get("meta", {}))
    if not trends:
        return
    selected_name = st.selectbox("Trend", [trend.get("name") for trend in trends], key="campaign_trend")
    trend = next(item for item in trends if item.get("name") == selected_name)
    rows = recommendation_rows(snapshot, str(trend.get("id")))
    candidate_ids = [str(row.get("product_id")) for row in rows if str(row.get("product_id")) in products_by_id]
    selected_ids = st.multiselect(
        "Products",
        candidate_ids,
        default=candidate_ids[:3],
        format_func=lambda product_id: f"{products_by_id[product_id].get('vendor')} · {products_by_id[product_id].get('title')}",
    )
    left, right = st.columns(2)
    channel = left.selectbox("Format", ["Instagram Reel", "Instagram carousel", "Email", "Blog post", "Soho store activation"])
    objective = right.selectbox("Objective", ["Drive product discovery", "Bring visits to Soho", "Sell one-of-one pieces", "Build fashion authority", "Re-engage VIPs"])
    selected_products = [products_by_id[product_id] for product_id in selected_ids]
    if st.button("Generate campaign brief", type="primary", disabled=not selected_products):
        with st.spinner("Building the brief from the selected evidence and products…"):
            if settings.openrouter_configured:
                try:
                    connector = OpenRouterConnector(
                        api_key=settings.openrouter_api_key,
                        model=settings.openrouter_model,
                        api_url=settings.openrouter_api_url,
                        timeout=settings.openrouter_timeout,
                        site_url=settings.openrouter_site_url,
                        app_name=settings.openrouter_app_name,
                    )
                    brief = connector.campaign_brief(trend, selected_products, channel, objective)
                    st.session_state.campaign_source = settings.openrouter_model
                    st.session_state.pop("campaign_last_error", None)
                except Exception as exc:
                    detail = safe_error(exc, [settings.openrouter_api_key])
                    st.session_state.campaign_last_error = {
                        "at": datetime.now(tz=timezone.utc).isoformat(),
                        "detail": detail,
                    }
                    st.warning(
                        "Qwen was unavailable, so a deterministic fallback brief was created. "
                        + detail
                    )
                    brief = fallback_campaign(trend, selected_products, channel, objective)
                    st.session_state.campaign_source = "fallback template"
            else:
                brief = fallback_campaign(trend, selected_products, channel, objective)
                st.session_state.campaign_source = "fallback template"
                st.session_state.campaign_last_error = {
                    "at": datetime.now(tz=timezone.utc).isoformat(),
                    "detail": (
                        "OpenRouter is not configured in the copy of the app currently running. "
                        "Open Data & Setup to confirm whether the key is loaded."
                    ),
                }
            st.session_state.campaign_brief = brief
    brief = st.session_state.get("campaign_brief")
    if brief:
        section_header("Generated direction", str(brief.get("campaign_name", "Campaign brief")))
        st.caption(f"Generated with {st.session_state.get('campaign_source', 'the configured model')}. Review every factual product claim before publishing.")
        first, second = st.columns([1, 1], gap="large")
        with first:
            st.markdown("#### Insight")
            st.write(brief.get("insight", ""))
            st.markdown("#### Hook")
            st.info(brief.get("hook", ""))
            st.markdown("#### Caption")
            st.text_area("Editable caption", value=brief.get("caption", ""), height=190, label_visibility="collapsed")
        with second:
            st.markdown("#### Shot list")
            for index, item in enumerate(brief.get("shot_list", []), 1):
                st.markdown(f"**{index:02d}** · {item}")
            st.markdown("#### CTA")
            st.write(brief.get("cta", ""))
        st.download_button(
            "Download brief (.md)",
            data=campaign_markdown(brief),
            file_name=f"hula-{str(trend.get('id'))}-campaign-brief.md",
            mime="text/markdown",
        )
        last_error = st.session_state.get("campaign_last_error")
        if (
            st.session_state.get("campaign_source") == "fallback template"
            and isinstance(last_error, dict)
        ):
            with st.expander("Why the fallback template was used", expanded=True):
                st.error(str(last_error.get("detail", "No error detail was recorded.")))
                st.caption(
                    "The selected products and the deterministic brief remain available; no partial AI response is published."
                )
    else:
        st.markdown(
            '<div class="method-note">No OpenRouter key yet? The page still works with a deterministic HULA template. Once Qwen is connected, it will create a more tailored brief from aggregated trend evidence and selected product metadata only—never customer or order data.</div>',
            unsafe_allow_html=True,
        )


def status_class(value: str) -> str:
    lowered = value.lower()
    if "live" in lowered:
        return "live"
    if "failed" in lowered:
        return "fail"
    return "demo"


def data_setup(snapshot: dict, settings: Settings) -> None:
    page_header(
        "DATA & SETUP · CONNECTIONS",
        "Know exactly what the score is built from.",
        "Connect each source, test access and refresh on demand. Secrets are read from Streamlit or environment settings and are never displayed here.",
    )
    meta = snapshot.get("meta", {})
    status = meta.get("source_status", {})
    notice = st.session_state.pop("catalogue_notice", "")
    if notice:
        st.success(notice)
    cards = st.columns(4)
    if meta.get("catalogue_source") == "csv":
        catalogue_detail = f"Imported: {len(snapshot.get('products', [])):,} normalised products"
    else:
        catalogue_detail = f"API credentials: {'added' if settings.shopify_configured else 'missing'}"
    google_meta = meta.get("google_trends") or {}
    google_route = str(
        google_meta.get("provider")
        or (
            "SerpApi proxy"
            if settings.serpapi_configured
            else "add SERPAPI_API_KEY"
        )
    )
    definitions = [
        (
            "Google Trends",
            str(status.get("google_trends", "ready on refresh")),
            (
                f"Market: {settings.google_geo.title()} · Route: {google_route} · "
                f"Credentials: {'added' if settings.serpapi_configured else 'missing'}"
            ),
        ),
        (
            "X via Apify",
            str(status.get("x_apify", "configured" if settings.apify_configured else "not configured")),
            (
                f"Credentials: {'added' if settings.apify_configured else 'missing'} · "
                f"Mode: {'rolling topic plan' if settings.topic_plan_enabled else 'saved-task input'}"
            ),
        ),
        (
            "Catalogue",
            str(status.get("shopify", "configured" if settings.shopify_configured else "not configured")),
            catalogue_detail,
        ),
        (
            "OpenRouter",
            str(status.get("openrouter", "configured" if settings.openrouter_configured else "not configured")),
            f"Credentials: {'added' if settings.openrouter_configured else 'missing'}",
        ),
    ]
    for column, (name, value, detail) in zip(cards, definitions):
        with column:
            css_class = status_class(value)
            st.markdown(
                f"""
                  <div class="source-card">
                  <div class="source-name">{html.escape(name)}</div>
                  <div class="source-state"><span class="dot {css_class}"></span>{html.escape(value)}</div>
                  <div class="micro">{html.escape(detail)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    section_header("Diagnostics", "Expected hybrid inputs versus genuine failures")
    st.write(
        "The table separates settings loaded **now** from the status saved by the **last refresh**. "
        "An uploaded catalogue is intentionally hybrid; it is not an OpenRouter error."
    )
    diagnostics = source_diagnostic_rows(
        meta,
        google_configured=settings.serpapi_configured,
        apify_configured=settings.apify_configured,
        shopify_configured=settings.shopify_configured,
        openrouter_configured=settings.openrouter_configured,
    )
    st.dataframe(pd.DataFrame(diagnostics), hide_index=True, width="stretch")
    report = diagnostic_report(
        meta,
        app_build=APP_BUILD,
        google_configured=settings.serpapi_configured,
        apify_configured=settings.apify_configured,
        shopify_configured=settings.shopify_configured,
        openrouter_configured=settings.openrouter_configured,
        openrouter_model=settings.openrouter_model,
        google_provider=settings.google_provider,
        google_geo=settings.google_geo,
    )
    st.download_button(
        "Download safe diagnostic report",
        data=json.dumps(report, ensure_ascii=False, indent=2),
        file_name="hula-trend-intelligence-diagnostics.json",
        mime="application/json",
        help="Contains statuses and errors, but never API keys, tokens or passwords.",
    )

    section_header("Apify X run capacity", "Find and release memory held by X jobs")
    st.write(
        "Apify's memory limit measures **all Actor containers that are running at the same time**—not "
        "the number of posts or search terms. This build runs X jobs sequentially and stops timed-out "
        "jobs automatically. Google Trends now uses a lightweight API proxy and consumes no Apify memory."
    )
    capacity_actions = st.columns(2)
    with capacity_actions[0]:
        if st.button(
            "Check active HULA runs",
            disabled=not bool(settings.apify_token),
            width="stretch",
        ):
            try:
                x_report = (
                    ApifyXConnector(
                        settings.apify_token,
                        settings.apify_x_task_id,
                        timeout_seconds=settings.apify_timeout_seconds,
                        memory_mb=settings.apify_x_memory_mb,
                    ).active_run_report()
                    if settings.apify_configured
                    else {"count": 0, "known_memory_mb": 0, "memory_complete": True}
                )
                st.session_state.apify_capacity_result = {
                    "ok": True,
                    "x": x_report,
                }
            except Exception as exc:
                st.session_state.apify_capacity_result = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.apify_token]),
                }
    with capacity_actions[1]:
        if st.button(
            "Stop active HULA runs",
            disabled=not bool(settings.apify_token),
            width="stretch",
            help=(
                "Stops currently running jobs for the configured HULA X task only. "
                "Use this after an Apify 402 memory-limit error."
            ),
        ):
            try:
                x_stopped = (
                    ApifyXConnector(
                        settings.apify_token,
                        settings.apify_x_task_id,
                        timeout_seconds=settings.apify_timeout_seconds,
                        memory_mb=settings.apify_x_memory_mb,
                    ).stop_active_runs()
                    if settings.apify_configured
                    else {"found": 0, "stopped": 0, "failed": 0}
                )
                stopped = int(x_stopped.get("stopped") or 0)
                failed = int(x_stopped.get("failed") or 0)
                st.session_state.apify_capacity_result = {
                    "ok": failed == 0,
                    "stopped": True,
                    "detail": (
                        f"Stopped {stopped} active HULA run(s). Wait about 15 seconds for Apify to release "
                        "the memory, then check capacity again."
                        + (f" {failed} run(s) could not be stopped." if failed else "")
                    ),
                }
            except Exception as exc:
                st.session_state.apify_capacity_result = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.apify_token]),
                }
    capacity_result = st.session_state.get("apify_capacity_result")
    if isinstance(capacity_result, dict):
        if capacity_result.get("stopped") or not capacity_result.get("ok"):
            (st.success if capacity_result.get("ok") else st.error)(
                str(capacity_result.get("detail") or "No detail was returned.")
            )
        elif capacity_result.get("ok"):
            x_report = capacity_result.get("x") or {}
            active_x = int(x_report.get("count") or 0)
            known_memory = int(x_report.get("known_memory_mb") or 0)
            capacity_metrics = st.columns(2)
            capacity_metrics[0].metric("Active HULA X runs", active_x)
            capacity_metrics[1].metric(
                "Known reserved memory",
                f"{known_memory / 1024:.1f} GB",
            )
            if active_x:
                st.warning(
                    "Active HULA jobs are still reserving Apify memory. If no refresh is intentionally "
                    "running elsewhere, use **Stop active HULA runs** before trying again."
                )
            else:
                st.success(
                    "No active HULA X runs were found. If Apify still reports 16 GB in "
                    "use, an unrelated Actor run or build must be stopped from the Apify Console."
                )
    elif not settings.apify_token:
        st.caption("Add APIFY_TOKEN to enable capacity checks.")

    section_header("X listening design", "Topic discovery first, expert validation second")
    listening_plan = build_listening_plan(
        language=settings.x_language,
        results_per_query=settings.apify_results_per_query,
        expert_results_per_query=settings.apify_expert_results_per_query,
        expert_accounts=settings.x_expert_accounts,
    )
    open_searches = sum(not row.get("is_expert") for row in listening_plan)
    expert_searches = sum(bool(row.get("is_expert")) for row in listening_plan)
    max_posts = sum(int((row.get("input") or {}).get("max_results") or 0) for row in listening_plan)
    design_metrics = st.columns(4)
    design_metrics[0].metric("Rolling searches", len(listening_plan), "current + previous week")
    design_metrics[1].metric("Open topic searches", open_searches, "five balanced topic families")
    design_metrics[2].metric("Expert searches", expert_searches, f"{len(settings.x_expert_accounts)} accounts")
    design_metrics[3].metric("Maximum results", f"{max_posts:,}", "before cross-query deduplication")
    st.write(
        "The app runs each topic against a **current seven-day window** and a separate "
        "**previous seven-day window**. Hashtags are accepted when they occur naturally, but the "
        "search does not depend on hashtags or profiles alone. Expert accounts validate ideas discovered "
        "in the open conversation; they do not decide the trend by themselves."
    )
    plan_table = pd.DataFrame(
        [
            {
                "Search": row.get("group_label"),
                "Window": row.get("window_label"),
                "Role": "Expert validation" if row.get("is_expert") else "Open discovery",
                "Result cap": int((row.get("input") or {}).get("max_results") or 0),
            }
            for row in listening_plan
        ]
    )
    with st.expander("Preview the searches that will run"):
        st.dataframe(plan_table, hide_index=True, width="stretch")
        st.caption(
            "The saved ScrapeBadger Task supplies the Actor and any extra options. At refresh time, "
            "the app safely overrides only Advanced Search mode, query, Latest ordering and result cap."
        )
    listening_meta = meta.get("x_listening") or {}
    if listening_meta:
        completed = int(listening_meta.get("succeeded") or 0)
        planned = int(listening_meta.get("planned") or 0)
        unique = int(listening_meta.get("unique") or 0)
        duplicates = int(listening_meta.get("duplicates_removed") or 0)
        clustering = str(listening_meta.get("semantic_clustering") or "not recorded")
        st.info(
            f"Last refresh: {completed}/{planned} searches completed, {unique:,} unique posts remained "
            f"after removing {duplicates:,} cross-query duplicates. Topic grouping: {clustering}."
        )

    section_header("Trend quality filter", "Fashion signals in; unrelated noise out")
    st.write(
        "The app rejects category-only labels before they reach the landing page, radar, product matching or Qwen. "
        "A descriptor plus a product stays valid: **black bags** and **red trousers** pass; **bags** and **trousers** do not."
    )
    filtered_rows = list(meta.get("filtered_terms") or [])
    if filtered_rows:
        filtered_table = pd.DataFrame(
            [
                {
                    "Filtered term": row.get("term"),
                    "Why it was removed": row.get("reason"),
                    "Found in": row.get("source"),
                }
                for row in filtered_rows
            ]
        )
        st.dataframe(filtered_table, hide_index=True, width="stretch")
        st.caption(
            f"Last snapshot: {len(filtered_rows)} irrelevant or overly broad term(s) removed. This is the complete audit list for that refresh."
        )
    else:
        st.success("No irrelevant or overly broad terms had to be removed from the current snapshot.")
    permanent_blocklist = generic_term_catalogue()
    with st.expander(
        f"View the complete permanent single-term blocklist ({len(permanent_blocklist)})"
    ):
        st.write(", ".join(permanent_blocklist))
        st.caption(
            "These words are blocked only when they appear alone or as an entirely generic phrase. "
            "Adding a meaningful colour, material, shape, era or aesthetic makes the term eligible again."
        )

    section_header("Product catalogue", "Choose CSV upload or the live Shopify API")
    default_catalogue = catalogue_choice(snapshot)
    selected_catalogue = st.radio(
        "Catalogue source",
        [CATALOGUE_CSV, CATALOGUE_API],
        index=0 if default_catalogue == CATALOGUE_CSV else 1,
        horizontal=True,
        key=CATALOGUE_SELECTOR_KEY,
        help="CSV is a saved snapshot. The API reads the newest active Shopify products on every refresh.",
    )
    if selected_catalogue == CATALOGUE_CSV:
        intro, template = st.columns([2.1, 1], gap="large")
        with intro:
            st.write(
                "Upload the Shopify product export you already have. The app also accepts a simple one-product-per-row CSV. "
                "It stores the normalised catalogue in the dashboard snapshot, so Wednesday trend refreshes keep using it until you upload a replacement or switch to the API."
            )
            uploaded_catalogue = st.file_uploader(
                "Product catalogue CSV",
                type=["csv"],
                key="product_catalogue_csv",
            )
        with template:
            if meta.get("catalogue_source") == "csv":
                current_name = meta.get("catalogue_filename") or "uploaded CSV"
                st.info(
                    f"Currently using **{current_name}** with **{len(snapshot.get('products', [])):,} products**."
                )
            st.download_button(
                "Download simple CSV template",
                data=SIMPLE_CSV_TEMPLATE,
                file_name="hula_product_catalogue_template.csv",
                mime="text/csv",
                width="stretch",
            )

        if uploaded_catalogue is not None:
            try:
                import_result = parse_product_csv(
                    uploaded_catalogue.getvalue(),
                    storefront_url=settings.shopify_storefront_url,
                )
                active_count = sum(
                    1 for product in import_result.products if product.get("status") == "ACTIVE"
                )
                in_stock_count = sum(
                    1
                    for product in import_result.products
                    if product.get("status") == "ACTIVE" and int(product.get("inventory") or 0) > 0
                )
                st.success(
                    f"Detected {import_result.source_format}: {import_result.source_rows:,} rows became "
                    f"{len(import_result.products):,} products."
                )
                preview_metrics = st.columns(3)
                preview_metrics[0].metric("Products", f"{len(import_result.products):,}")
                preview_metrics[1].metric("Active", f"{active_count:,}")
                preview_metrics[2].metric("Active + in stock", f"{in_stock_count:,}")
                preview = pd.DataFrame(
                    [
                        {
                            "Title": product.get("title"),
                            "Designer": product.get("vendor"),
                            "Type": product.get("product_type"),
                            "Status": product.get("status"),
                            "Stock": product.get("inventory"),
                            "Price": f"{product.get('currency', 'HKD')} {float(product.get('price') or 0):,.0f}",
                        }
                        for product in import_result.products[:20]
                    ]
                )
                st.dataframe(preview, hide_index=True, width="stretch", height=260)
                st.caption("Previewing the first 20 normalised products. The original CSV is not edited.")
                for warning in import_result.warnings:
                    st.warning(warning)
                if st.button("Use this CSV catalogue", type="primary", key="apply_catalogue_csv"):
                    updated_snapshot = dict(snapshot)
                    updated_snapshot["products"] = import_result.products
                    updated_snapshot["recommendations"] = match_products(
                        snapshot.get("trends", []), import_result.products
                    )
                    updated_meta = dict(meta)
                    updated_meta["generated_at"] = datetime.now(tz=timezone.utc).isoformat()
                    updated_meta["mode"] = "hybrid"
                    updated_meta["catalogue_source"] = "csv"
                    updated_meta["catalogue_filename"] = Path(uploaded_catalogue.name).name
                    updated_meta["catalogue_format"] = import_result.source_format
                    updated_meta["catalogue_source_rows"] = import_result.source_rows
                    updated_meta["catalogue_warnings"] = import_result.warnings
                    prior_warnings = [
                        str(warning)
                        for warning in updated_meta.get("warnings", [])
                        if not str(warning).startswith("Catalogue CSV:")
                    ]
                    updated_meta["warnings"] = [
                        *prior_warnings,
                        *(f"Catalogue CSV: {warning}" for warning in import_result.warnings),
                    ]
                    updated_meta["source_status"] = {
                        **status,
                        "shopify": f"CSV snapshot · {len(import_result.products):,} products",
                    }
                    raw_counts = dict(updated_meta.get("raw_counts", {}))
                    raw_counts["shopify_products"] = len(import_result.products)
                    raw_counts["catalogue_products"] = len(import_result.products)
                    raw_counts["recommendations"] = len(updated_snapshot["recommendations"])
                    updated_meta["raw_counts"] = raw_counts
                    updated_snapshot["meta"] = updated_meta
                    save_snapshot(updated_snapshot, settings.snapshot_path)
                    st.session_state.snapshot = updated_snapshot
                    st.session_state.catalogue_notice = (
                        f"{len(import_result.products):,} products imported from {Path(uploaded_catalogue.name).name}."
                    )
                    st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        st.write(
            "Use the live API when the HULA-owned Shopify app is installed. Each refresh reads active products, "
            "inventory, prices, tags and images without changing the store."
        )
        if not settings.shopify_configured:
            st.warning(
                "Shopify API credentials are not configured yet. You can switch to Upload CSV and use the catalogue immediately."
            )
        if st.button(
            "Test Shopify API",
            disabled=not settings.shopify_configured,
            width="stretch",
        ):
            try:
                result = ShopifyConnector(
                    settings.shopify_shop,
                    settings.shopify_client_id,
                    settings.shopify_client_secret,
                    settings.shopify_admin_access_token,
                    settings.shopify_api_version,
                    settings.shopify_storefront_url,
                ).test_connection()
                st.success(f"Connected to {result.get('shop_name')}.")
            except Exception as exc:
                st.error(str(exc))

    section_header("Connection checks", "Test the other services without exposing credentials")
    tests = st.columns(3)
    with tests[0]:
        if st.button(f"Test Google Trends ({settings.google_geo.title()})", width="stretch"):
            try:
                result = GoogleTrendsConnector(
                    geo=settings.google_geo,
                    timeframe=settings.google_timeframe,
                    category=settings.google_category,
                    anchor_term=settings.google_anchor_term,
                    provider=settings.google_provider,
                    serpapi_api_key=settings.serpapi_api_key,
                    serpapi_endpoint=settings.serpapi_endpoint,
                    serpapi_timeout_seconds=settings.serpapi_timeout_seconds,
                    max_terms=settings.google_max_terms,
                    max_discovery_seeds=settings.google_max_discovery_seeds,
                    connect_timeout_seconds=settings.google_connect_timeout_seconds,
                    read_timeout_seconds=settings.google_read_timeout_seconds,
                ).test_connection()
                requests_used = int(result.get("requests_used") or 0)
                st.session_state.google_test_result = {
                    "ok": True,
                    "detail": (
                        f"Live {result.get('market')} data received through {result.get('provider')} "
                        f"({int(result.get('points') or 0)} timeline points · "
                        f"{requests_used} API search)."
                    ),
                }
            except Exception as exc:
                st.session_state.google_test_result = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.serpapi_api_key]),
                }
        google_test = st.session_state.get("google_test_result")
        if isinstance(google_test, dict):
            (st.success if google_test.get("ok") else st.error)(
                str(google_test.get("detail", "No diagnostic detail was returned."))
            )
        st.caption(
            "Uses SerpApi's lightweight Google Trends endpoint, not an Apify Actor or the fragile "
            "Google webpage route. This small test uses one SerpApi search."
        )
    with tests[1]:
        if st.button("Test Apify task", disabled=not settings.apify_configured, width="stretch"):
            try:
                result = ApifyXConnector(
                    settings.apify_token,
                    settings.apify_x_task_id,
                    timeout_seconds=settings.apify_timeout_seconds,
                    memory_mb=settings.apify_x_memory_mb,
                ).test_connection()
                actor = result.get("actor_reference") or result.get("actor_name") or "actor not reported"
                st.session_state.apify_test_result = {
                    "ok": True,
                    "detail": f"Found task: {result.get('task_name')} · Actor: {actor}.",
                    "compatible": bool(result.get("scrapebadger_compatible")),
                }
            except Exception as exc:
                st.session_state.apify_test_result = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.apify_token]),
                }
        apify_test = st.session_state.get("apify_test_result")
        if isinstance(apify_test, dict):
            (st.success if apify_test.get("ok") else st.error)(
                str(apify_test.get("detail", "No diagnostic detail was returned."))
            )
            if apify_test.get("ok") and not apify_test.get("compatible"):
                st.warning(
                    "The task exists, but it is not confirmed as scrape.badger/twitter-tweets-scraper. "
                    "The rolling query plan requires that Actor's Advanced Search input fields."
                )
    with tests[2]:
        if st.button("Test OpenRouter", disabled=not settings.openrouter_configured, width="stretch"):
            try:
                result = OpenRouterConnector(
                    settings.openrouter_api_key,
                    settings.openrouter_model,
                    settings.openrouter_api_url,
                    settings.openrouter_timeout,
                    settings.openrouter_site_url,
                    settings.openrouter_app_name,
                ).test_connection()
                st.session_state.openrouter_test_result = {
                    "ok": True,
                    "detail": f"Connected successfully to {result.get('model')}.",
                }
            except Exception as exc:
                st.session_state.openrouter_test_result = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.openrouter_api_key]),
                }
        openrouter_test = st.session_state.get("openrouter_test_result")
        if isinstance(openrouter_test, dict):
            (st.success if openrouter_test.get("ok") else st.error)(
                str(openrouter_test.get("detail", "No diagnostic detail was returned."))
            )

    section_header("Live refresh", "Run the full evidence pipeline")
    include_llm = st.checkbox("Use Qwen to label and enrich trends", value=settings.openrouter_configured)
    catalog_source, catalog_products = catalogue_refresh_args(snapshot)
    refresh_ready = not (
        (catalog_source == "csv" and not catalog_products)
        or (catalog_source == "shopify_api" and not settings.shopify_configured)
    )
    if not refresh_ready and catalog_source == "csv":
        st.info("Upload and apply a product CSV before refreshing with the CSV source.")
    elif not refresh_ready:
        st.info("Add the Shopify API settings or switch to Upload CSV before running a full refresh.")
    refresh_label = (
        "Refresh trends using uploaded catalogue"
        if catalog_source == "csv"
        else "Refresh trends + Shopify catalogue"
    )
    if st.button(refresh_label, type="primary", disabled=not refresh_ready):
        with st.spinner(
            "Running current/previous topic searches, grouping evidence and matching the catalogue…"
        ):
            try:
                refreshed = refresh_snapshot(
                    settings,
                    use_llm=include_llm,
                    persist=True,
                    catalog_source=catalog_source,
                    catalog_products=catalog_products,
                )
                st.session_state.snapshot = refreshed
                st.session_state.catalogue_notice = "Refresh complete. The dashboard now uses the new snapshot."
                st.rerun()
            except Exception as exc:
                st.error(
                    "Refresh stopped safely: "
                    + safe_error(
                        exc,
                        [
                            settings.apify_token,
                            settings.serpapi_api_key,
                            settings.openrouter_api_key,
                            settings.shopify_client_secret,
                            settings.shopify_admin_access_token,
                        ],
                    )
                )
    st.caption(
        "The scheduled GitHub workflow runs every Wednesday at 09:17 Hong Kong time and keeps the last selected catalogue source."
    )

    with st.expander("Manual Google Trends CSV fallback"):
        st.write("Upload a Google Trends export with a date column first and one or more keyword columns. This remains available if the API allowance is temporarily exhausted.")
        uploaded = st.file_uploader("Google Trends CSV", type=["csv"], label_visibility="collapsed")
        if uploaded is not None and st.button("Use uploaded search data"):
            try:
                csv_text = uploaded.getvalue().decode("utf-8-sig")
                first_line = csv_text.splitlines()[0].lower() if csv_text.splitlines() else ""
                skiprows = 1 if first_line.startswith(("category:", "web search", "youtube search")) else 0
                frame = pd.read_csv(io.StringIO(csv_text), skiprows=skiprows)
                if len(frame.columns) < 2:
                    raise ValueError("The CSV needs a date column and at least one keyword column.")
                date_column = frame.columns[0]
                series = {}
                for column in frame.columns[1:]:
                    numeric = pd.to_numeric(frame[column].astype(str).str.replace("<1", "0", regex=False), errors="coerce").fillna(0)
                    series[
                        str(column)
                        .replace(": (Hong Kong)", "")
                        .replace(": (Worldwide)", "")
                    ] = [
                        {"date": str(date), "value": float(value)}
                        for date, value in zip(frame[date_column], numeric)
                    ]
                google_rows = score_google_series(series)
                manual_trends = merge_trend_signals(google_rows, [])
                if not manual_trends:
                    raise ValueError("No usable numeric trend series were found.")
                updated_snapshot = dict(snapshot)
                updated_snapshot["trends"] = manual_trends
                updated_snapshot["recommendations"] = match_products(manual_trends, snapshot.get("products", []))
                updated_meta = dict(snapshot.get("meta", {}))
                updated_meta["generated_at"] = datetime.now(tz=timezone.utc).isoformat()
                updated_meta["mode"] = "hybrid"
                updated_meta["source_status"] = {**updated_meta.get("source_status", {}), "google_trends": "manual CSV"}
                updated_snapshot["meta"] = updated_meta
                save_snapshot(updated_snapshot, settings.snapshot_path)
                st.session_state.snapshot = updated_snapshot
                st.success("Manual search data applied.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    section_header("External signal", "How the fashion trend score is assembled")
    signal_method = st.columns(4)
    for column, number, title, copy in [
        (signal_method[0], "45%", "Google Trends HK", "Local search-demand momentum."),
        (signal_method[1], "30%", "Open X topics", "Independent-author and post growth across broad topic searches."),
        (signal_method[2], "15%", "Expert panel", "Separate confirmation from trusted fashion sources."),
        (signal_method[3], "10%", "Visual validation", "Reserved for TikTok or Pinterest evidence when available."),
    ]:
        with column:
            st.metric(title, number)
            st.caption(copy)
    st.caption(
        "The score automatically reweights across sources that actually supplied evidence; an unavailable "
        "visual source is never treated as a zero. X evidence is reduced when duplicates, promotional posts "
        "or one dominant author make a topic less trustworthy."
    )

    section_header("Product opportunity", "How the catalogue recommendation score works")
    method = st.columns(4)
    for column, number, title, copy in [
        (method[0], "45%", "Trend strength", "Google momentum, X growth and cross-source agreement."),
        (method[1], "35%", "Catalogue fit", "Text similarity across title, type, brand, tags and description."),
        (method[2], "15%", "Content readiness", "In stock, image present and enough product information."),
        (method[3], "5%", "Freshness", "A light preference for recently added pieces."),
    ]:
        with column:
            st.metric(title, number)
            st.caption(copy)
    st.markdown(
        '<div class="method-note"><strong>Data minimisation:</strong> raw X posts and author identifiers are held only during the refresh. Author identifiers are one-way hashed in memory to count independent sources, then discarded; the snapshot stores aggregates only. A product CSV is normalised into product fields and the raw upload is not retained separately. The API requests read-only Shopify scopes and does not read customers, orders or payment data. Qwen receives aggregated candidate phrases, trend evidence and selected product metadata only.</div>',
        unsafe_allow_html=True,
    )
    warnings = meta.get("warnings", [])
    if warnings:
        with st.expander(f"Refresh notes ({len(warnings)})"):
            for warning in warnings:
                st.write(f"• {warning}")


def sidebar(snapshot: dict, settings: Settings) -> str:
    with st.sidebar:
        st.image(cropped_logo(), width=112)
        st.markdown(
            '<div class="brand-lockup"><span class="data">Data Sciences</span><span class="teri">by Teri</span></div>',
            unsafe_allow_html=True,
        )
        page = st.radio(
            "Navigation",
            ["THIS WEEK", "TREND RADAR", "PRODUCT MATCH", "CAMPAIGN STUDIO", "DATA & SETUP"],
            label_visibility="collapsed",
        )
        st.divider()
        meta = snapshot.get("meta", {})
        updated = hk_time(str(meta.get("generated_at", "")))
        st.caption(f"DATASET · {str(meta.get('mode', 'demo')).upper()}")
        st.caption(f"Updated {updated.strftime('%d %b %Y, %H:%M')} HKT")
        catalog_source, catalog_products = catalogue_refresh_args(snapshot)
        refresh_disabled = bool(
            (catalog_source == "csv" and not catalog_products)
            or (catalog_source == "shopify_api" and not settings.shopify_configured)
        )
        if st.button(
            "Refresh data",
            type="primary",
            width="stretch",
            disabled=refresh_disabled,
        ):
            with st.spinner("Running the weekly topic, expert, search and catalogue pipeline…"):
                try:
                    st.session_state.snapshot = refresh_snapshot(
                        settings,
                        persist=True,
                        catalog_source=catalog_source,
                        catalog_products=catalog_products,
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        selected_label = "CSV snapshot" if catalog_source == "csv" else "Shopify API"
        st.caption(f"Catalogue · {selected_label}")
        st.caption("Next scheduled refresh: Wednesday · 09:17 HKT")
        st.caption(f"Build {APP_BUILD}")
    return page


def main() -> None:
    inject_styles()
    settings = load_settings()
    require_password(settings)
    if "snapshot" not in st.session_state:
        stored = load_snapshot(ROOT / settings.snapshot_path)
        st.session_state.snapshot = sanitize_snapshot_trends(stored or demo_snapshot())
    snapshot = sanitize_snapshot_trends(st.session_state.snapshot)
    st.session_state.snapshot = snapshot
    page = sidebar(snapshot, settings)
    if page == "THIS WEEK":
        this_week(snapshot)
    elif page == "TREND RADAR":
        trend_radar(snapshot)
    elif page == "PRODUCT MATCH":
        product_match_page(snapshot)
    elif page == "CAMPAIGN STUDIO":
        campaign_studio(snapshot, settings)
    else:
        data_setup(snapshot, settings)


if __name__ == "__main__":
    main()
