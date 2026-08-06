from __future__ import annotations

import hashlib
import hmac
import html
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image, ImageChops

from src.analysis.freshness import parse_utc
from src.analysis.evidence_scoring import upgrade_snapshot_to_v2
from src.analysis.listening import (
    build_listening_plan,
)
from src.analysis.matching import match_products
from src.analysis.trends import (
    generic_term_catalogue,
    merge_trend_signals,
    sanitize_snapshot_trends,
    score_google_series,
)
from src.config import Settings, load_settings
from src.connectors.apify_x import ApifyXConnector
from src.connectors.apify_instagram_hashtags import (
    InstagramHashtagAnalyticsConnector,
)
from src.connectors.catalog_csv import SIMPLE_CSV_TEMPLATE, parse_product_csv
from src.connectors.commercial_sources import (
    COMMERCIAL_SOURCES,
    EDITORIAL_PUBLISHERS,
    CommercialSourceCollector,
)
from src.connectors.gemini_research import GeminiResearchConnector
from src.connectors.google_trends import GoogleTrendsConnector
from src.connectors.openrouter import OpenRouterConnector
from src.connectors.openai_responses import OpenAIResponsesConnector
from src.connectors.shopify import ShopifyConnector
from src.connectors.supabase_store import SupabaseStore
from src.demo_data import demo_snapshot
from src.diagnostics import (
    diagnostic_report,
    hybrid_explanation,
    safe_error,
    source_diagnostic_rows,
)
from src.pipeline import refresh_snapshot
from src.editorial.blog_generator import (
    fallback_blog,
    generate_researched_blog,
)
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
APP_BUILD = "2026.08.06.4"
DISCOVERY_PIPELINE_VERSION = "4.0"
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
        .dot.live { background:#27a05a; } .dot.standby { background:#9b9186; } .dot.demo { background:#e8a846; } .dot.fail { background:#d64848; }
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

    if trend.get("business_action") in DECISION_COLORS:
        return str(trend["business_action"])
    if not trend.get("decision_ready"):
        return "Watch"
    score = float(trend.get("confidence_score") or trend.get("score") or 0)
    completeness = float(trend.get("data_completeness_score") or 0)
    domains = int(trend.get("independent_domain_count") or 0)
    evidence = int(trend.get("evidence_count") or 0)
    confidence = str(trend.get("confidence") or "")
    if (
        score >= 75
        and completeness >= 65
        and domains >= 3
        and evidence >= 4
        and confidence == "High"
    ):
        return "Act now"
    if score >= 55 and completeness >= 40 and domains >= 2 and evidence >= 3:
        return "Test this week"
    return "Watch"


def decision_legend() -> None:
    st.markdown(
        f"""
        <div class="decision-key">
          <div class="decision-item"><strong><span class="decision-swatch" style="background:{DECISION_COLORS['Act now']}"></span>ACT NOW</strong>High confidence, current evidence and at least three independent domains.</div>
          <div class="decision-item"><strong><span class="decision-swatch" style="background:{DECISION_COLORS['Test this week']}"></span>TEST THIS WEEK</strong>Promising enough for a small content or merchandising test.</div>
          <div class="decision-item"><strong><span class="decision-swatch" style="background:{DECISION_COLORS['Watch']}"></span>WATCH</strong>Keep monitoring; evidence is not strong enough to prioritise.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def google_direction(trend: dict) -> str:
    momentum = float(trend.get("search_momentum") or 0)
    if momentum >= 10:
        return "Rising"
    if momentum <= -10:
        return "Cooling"
    return "Stable"


def priority_rows(trends: list[dict], *, limit: int = 30) -> pd.DataFrame:
    rows = sorted(
        trends,
        key=lambda row: (
            float(row.get("confidence_score") or row.get("score") or 0),
            float(row.get("data_completeness_score") or 0),
        ),
        reverse=True,
    )[:limit]
    return pd.DataFrame(
        [
            {
                "Rank": index + 1,
                "Trend": row.get("name"),
                "Origin": row.get("discovery_origin_label") or "Not recorded",
                "Decision": business_decision(row).upper(),
                "Confidence": f"{float(row.get('confidence_score') or row.get('score') or 0):.0f}/100",
                "Coverage": f"{float(row.get('data_completeness_score') or 0):.0f}%",
                "HULA opportunity": f"{float(row.get('hula_opportunity_score') or 0):.0f}/100",
                "Momentum": str(row.get("momentum") or "insufficient data").title(),
                "Evidence": int(row.get("evidence_count") or 0),
                "Domains": int(row.get("independent_domain_count") or 0),
                "Missing evidence": ", ".join(row.get("missing_components") or []) or "None",
            }
            for index, row in enumerate(rows)
        ]
    )


def publisher_inventory_rows(snapshot: dict) -> pd.DataFrame:
    """Show every publisher-named trend separately from the action gate."""

    meta = snapshot.get("meta") or {}
    discoveries = list(meta.get("commercial_discoveries") or [])
    trends_by_id = {
        str(row.get("id") or ""): row for row in snapshot.get("trends") or []
    }
    rows: list[dict[str, object]] = []
    for discovery in discoveries:
        trend_id = str(discovery.get("id") or "")
        merged = trends_by_id.get(trend_id) or {}
        evidence = list(discovery.get("commercial_evidence") or [])
        pages = list(
            dict.fromkeys(
                str(row.get("url") or "") for row in evidence if row.get("url")
            )
        )
        publishers = list(discovery.get("publisher_names") or [])
        if not publishers:
            publishers = list(
                dict.fromkeys(
                    str(row.get("publisher") or "")
                    for row in evidence
                    if row.get("publisher")
                )
            )
        if merged.get("decision_ready"):
            validation = "Action-ready"
        elif merged.get("google_score") is not None:
            validation = "Google validated; awaiting another source"
        else:
            validation = "Publisher-discovered; not Google-validated"
        rows.append(
            {
                "Trend": discovery.get("name"),
                "Publisher sites": ", ".join(publishers) or "Not reported",
                "Evidence pages": len(pages),
                "Newest evidence": str(
                    discovery.get("newest_published_at") or ""
                )[:10]
                or "Date not exposed",
                "Fresh pages (14d)": int(
                    discovery.get("current_article_count") or 0
                ),
                "Validation priority": f"{float(discovery.get('validation_priority_score') or 0):.0f}/100",
                "Validation": validation,
                "First source": pages[0] if pages else "",
                "_score": float(
                    discovery.get("validation_priority_score")
                    or discovery.get("commercial_score")
                    or 0
                ),
            }
        )
    rows.sort(key=lambda row: (-float(row["_score"]), str(row["Trend"])))
    for row in rows:
        row.pop("_score", None)
    return pd.DataFrame(rows)


def fresh_discovery_rows(snapshot: dict, *, limit: int = 8) -> pd.DataFrame:
    """Surface new publisher finds without pretending they are action-ready."""

    meta = snapshot.get("meta") or {}
    selected_ids = {
        str(row.get("id") or "")
        for row in meta.get("validation_plan") or []
    }
    trends_by_id = {
        str(row.get("id") or ""): row for row in snapshot.get("trends") or []
    }
    discoveries = sorted(
        (
            row
            for row in meta.get("commercial_discoveries") or []
            if int(row.get("current_article_count") or 0) > 0
        ),
        key=lambda row: float(row.get("validation_priority_score") or 0),
        reverse=True,
    )[: max(1, int(limit))]
    rows: list[dict[str, object]] = []
    for discovery in discoveries:
        trend_id = str(discovery.get("id") or "")
        merged = trends_by_id.get(trend_id) or {}
        evidence = list(discovery.get("commercial_evidence") or [])
        source_url = next(
            (str(row.get("url") or "") for row in evidence if row.get("url")),
            "",
        )
        rows.append(
            {
                "Fresh trend": discovery.get("name"),
                "Found by": ", ".join(discovery.get("publisher_names") or []),
                "Newest evidence": str(
                    discovery.get("newest_published_at") or ""
                )[:10],
                "Selected for validation": "Yes" if trend_id in selected_ids else "No",
                "Confidence now": f"{float(merged.get('confidence_score') or merged.get('score') or 0):.0f}/100",
                "Status": (
                    business_decision(merged)
                    if merged
                    else "Awaiting validation"
                ),
                "Source": source_url,
            }
        )
    return pd.DataFrame(rows)


def guard_legacy_discovery_snapshot(snapshot: dict) -> dict:
    """Prevent pre-repair rankings from looking live before the next refresh."""

    meta = dict(snapshot.get("meta") or {})
    mode = str(meta.get("mode") or "").casefold()
    current = str(meta.get("discovery_pipeline_version") or "")
    if mode not in {"live", "hybrid"} or current == DISCOVERY_PIPELINE_VERSION:
        return snapshot

    guarded = dict(snapshot)
    guarded["trends"] = [
        {
            **trend,
            "decision_ready": False,
            "confidence": "Exploratory",
            "is_stale": True,
            "live_discovered": False,
            "discovery_origins": ["historical"],
            "primary_discovery_origin": "historical",
            "discovery_origin_label": "Historical snapshot — refresh required",
        }
        for trend in snapshot.get("trends") or []
    ]
    source_status = dict(meta.get("source_status") or {})
    source_status["trend_pipeline"] = (
        "STALE · snapshot predates live-discovery repair; run one full refresh"
    )
    meta.update(
        {
            "mode": "stale",
            "discovery_refresh_required": True,
            "source_status": source_status,
        }
    )
    guarded["meta"] = meta
    return guarded


def mode_banner(meta: dict) -> None:
    mode = str(meta.get("mode", "demo")).lower()
    if mode == "live":
        return
    label = (
        "DEMO MODE"
        if mode == "demo"
        else "STALE DATA"
        if mode == "stale"
        else "HYBRID MODE"
    )
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
            sources = " + ".join(trend.get("sources", [])[:4]) or "Evidence pending"
            origin = str(
                trend.get("discovery_origin_label") or "Origin not recorded"
            )
            st.markdown(
                f"""
                <div class="trend-card {'hot' if index == 0 else ''}">
                  <div class="trend-rank">#{index + 1} · {html.escape(str(trend.get('momentum', 'insufficient data')).upper())}</div>
                  <div class="trend-name">{html.escape(str(trend.get('name', '')))}</div>
                  <div class="trend-score">{float(trend.get('confidence_score') or trend.get('score') or 0):.0f}<span> / 100 confidence</span></div>
                  <div style="margin:.7rem 0"><span class="pill pink">{float(trend.get('data_completeness_score') or 0):.0f}% evidence coverage</span></div>
                  <div class="micro">HULA opportunity · {float(trend.get('hula_opportunity_score') or 0):.0f}/100</div>
                  <div class="micro">{html.escape(origin)}</div>
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


def line_chart(
    trends: list[dict],
    selected_ids: list[str] | None = None,
    *,
    series_key: str = "display_series",
    chart_ready_key: str = "chart_ready",
) -> go.Figure:
    figure = go.Figure()
    filtered = trends
    if selected_ids:
        filtered = [trend for trend in trends if str(trend.get("id")) in selected_ids]
    for index, trend in enumerate(filtered):
        points = list(trend.get(series_key) or [])
        if not trend.get(chart_ready_key) or not points:
            continue
        figure.add_trace(
            go.Scatter(
                x=[point.get("date") for point in points],
                y=[point.get("value") for point in points],
                mode="lines",
                name=str(trend.get("name")),
                line=dict(color=PALETTE[index % len(PALETTE)], width=3),
                hovertemplate="%{x}<br>Google index: %{y:.1f}/100<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_yaxes(
        title="Google Trends index (0–100)",
        range=[0, 100],
        dtick=20,
    )
    return plot_layout(figure)


def chart_or_quality_note(
    trends: list[dict],
    *,
    selected_ids: list[str] | None = None,
    series_key: str = "display_series",
    chart_ready_key: str = "chart_ready",
    chart_key: str | None = None,
) -> None:
    figure = line_chart(
        trends,
        selected_ids,
        series_key=series_key,
        chart_ready_key=chart_ready_key,
    )
    if figure.data:
        st.plotly_chart(
            figure,
            width="stretch",
            config={"displayModeBar": False},
            key=chart_key,
        )
        return
    st.info(
        "No trustworthy movement chart is available for this selection. "
        "The app excludes timelines with too few distinct values, excessive "
        "plateaus, isolated spikes or no preserved raw Google 0–100 index."
    )


def this_week(snapshot: dict) -> None:
    meta = snapshot.get("meta", {})
    trends = snapshot.get("trends", [])
    ready_trends = sorted(
        [trend for trend in trends if trend.get("decision_ready")],
        key=lambda row: float(row.get("hula_opportunity_score") or 0),
        reverse=True,
    )
    display_trends = ready_trends or trends
    updated = hk_time(str(meta.get("generated_at", "")))
    week_label = f"WEEK {updated.isocalendar().week} · GLOBAL FASHION"
    page_header(
        week_label,
        "What HULA should talk about now.",
        "A weekly view of rising fashion demand, social conversation and the pre-owned HULA pieces ready to meet it.",
    )
    mode_banner(meta)
    top_score = float(display_trends[0].get("score", 0)) if display_trends else 0
    high_confidence = sum(1 for trend in ready_trends if trend.get("confidence") in {"High", "Medium"})
    unique_products = len({row.get("product_id") for row in snapshot.get("recommendations", [])})
    metrics = st.columns(4)
    metrics[0].metric(
        "Strongest signal",
        f"{top_score:.0f}/100" if ready_trends else "Pending",
        display_trends[0].get("name") if display_trends else "—",
    )
    metrics[1].metric(
        "Cross-source trends",
        high_confidence,
        "independent evidence domains",
    )
    metrics[2].metric("Promotable products", unique_products, "in-stock catalogue matches")
    metrics[3].metric("Updated", updated.strftime("%d %b · %H:%M"), "Hong Kong time")

    section_header(
        "01 · Fresh discovery queue",
        "What publishers introduced most recently",
    )
    fresh = fresh_discovery_rows(snapshot)
    if fresh.empty:
        st.info(
            "No dated publisher discovery from the current 14-day window was stored. "
            "Run a live refresh or inspect publisher dates in Trend Radar."
        )
    else:
        st.dataframe(
            fresh,
            hide_index=True,
            width="stretch",
            column_config={"Source": st.column_config.LinkColumn("Source")},
        )
        st.caption(
            "These are live discoveries selected for targeted validation. They remain "
            "separate from the action list until the evidence gates are cleared."
        )

    section_header("02 · Signal board", "This week's strongest opportunities")
    if not ready_trends and trends:
        st.warning(
            "No trend currently clears the evidence-count, domain and recency gates. "
            "The cards below are a watchlist, not an "
            "action list."
        )
    trend_cards(display_trends, 4)
    filtered_count = len((meta.get("filtered_terms") or []))
    if filtered_count:
        st.caption(
            f"Quality control removed {filtered_count} irrelevant or overly broad term(s) before this page was built. "
            "The complete list is in Data & Setup."
        )

    section_header("03 · Momentum", "Measured Google movement from the stored timeline")
    chart_or_quality_note(display_trends[:5])
    st.caption(
        "The chart shows Google's original 0–100 index with light smoothing, not "
        "the anchor-calibrated values used internally to compare query batches. "
        "It is relative interest, not absolute search volume."
    )

    section_header("04 · Catalogue opportunity", "Products to put in front of people now")
    top_recommendations = []
    seen_products: set[str] = set()
    ready_ids = {str(trend.get("id")) for trend in ready_trends}
    for recommendation in recommendation_rows(snapshot):
        if str(recommendation.get("trend_id")) not in ready_ids:
            continue
        product_id = str(recommendation.get("product_id"))
        if product_id not in seen_products:
            top_recommendations.append(recommendation)
            seen_products.add(product_id)
        if len(top_recommendations) == 6:
            break
    if top_recommendations:
        render_product_grid(snapshot, top_recommendations)
    else:
        st.info(
            "Catalogue recommendations are held back until at least one trend "
            "has enough current, independent evidence."
        )

    section_header("05 · Direction", "The editorial idea behind the numbers")
    left, right = st.columns([1.05, 1], gap="large")
    top = display_trends[0] if display_trends else {}
    with left:
        st.markdown(
            f"""
            <div class="editorial-box">
              <div class="label">Lead story</div>
              <h3>{html.escape(str(top.get('name', 'A trend worth watching')))}</h3>
              <p>{html.escape(str(top.get('why_now', 'Connect live sources to generate an evidence-led rationale.')))}</p>
              <div class="pill pink">{html.escape(str(top.get('momentum', '')))}</div>
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
    ready_trends = [trend for trend in trends if trend.get("decision_ready")]
    watchlist = [trend for trend in trends if not trend.get("decision_ready")]
    page_header(
        "TREND RADAR · EXTERNAL SIGNALS",
        "Know what to act on first.",
        "A traceable priority view for this week. Python calculates confidence from stored editorial, cross-source, search, social, runway and retail evidence.",
    )
    meta = snapshot.get("meta", {})
    mode_banner(meta)
    if not trends:
        st.warning(
            "No specific, actionable trend rows are available. Broad labels were removed; run a refresh to collect a new set."
        )
        return
    commercial_collection = meta.get("commercial_collection") or {}
    publisher_status = commercial_collection.get("source_status") or {}
    publisher_inventory = publisher_inventory_rows(snapshot)
    sites_with_trends = sum(
        int((row or {}).get("named_trends") or 0) > 0
        for row in publisher_status.values()
    )
    raw_counts = meta.get("raw_counts") or {}
    coverage = st.columns(4)
    coverage[0].metric(
        "Publisher sites with evidence",
        f"{sites_with_trends}/{len(COMMERCIAL_SOURCES)}",
    )
    coverage[1].metric(
        "Publisher-named trends",
        int(commercial_collection.get("named_trends") or len(publisher_inventory)),
    )
    coverage[2].metric(
        "Evidence-backed trends",
        sum(int(row.get("evidence_count") or 0) > 0 for row in trends),
    )
    coverage[3].metric("Action-ready trends", len(ready_trends))

    section_header(
        "Publisher inventory",
        "Everything the approved websites explicitly named",
    )
    if publisher_inventory.empty:
        st.error(
            "The last refresh extracted zero named trends from the approved publisher "
            "panel. A page-load success is not counted as evidence; inspect each source "
            "in Data & Setup."
        )
    else:
        st.dataframe(
            publisher_inventory,
            hide_index=True,
            width="stretch",
            height=min(680, 38 * len(publisher_inventory) + 42),
            column_config={
                "First source": st.column_config.LinkColumn("First source page"),
            },
        )
        st.caption(
            "This is the discovery inventory, not an automatic recommendation. Every "
            "row links back to an approved publisher page. The separate action list "
            "below applies evidence-count, independent-domain and recency gates."
        )

    section_header("Priority view", "What to do with each trend")
    decision_legend()
    if ready_trends:
        st.dataframe(
            priority_rows(ready_trends),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info(
            "There are no decision-ready trends yet. Run a fresh evidence collection; "
            "incomplete rows are retained below only for diagnosis."
        )
    st.caption(
        "Missing components are not scored as zero. Available weights are redistributed, "
        "while evidence coverage remains visible and confidence caps still apply."
    )

    decisions = [business_decision(trend) for trend in ready_trends]
    summary = st.columns(3)
    summary[0].metric("Act now", decisions.count("Act now"), "cross-source confirmation")
    summary[1].metric("Test this week", decisions.count("Test this week"), "small controlled test")
    summary[2].metric("Awaiting validation", len(watchlist), "kept out of the action list")

    if watchlist:
        with st.expander(
            f"Watchlist waiting for source confirmation ({len(watchlist)})",
            expanded=True,
        ):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Trend": trend.get("name"),
                            "Origin": trend.get("discovery_origin_label")
                            or "Not recorded",
                            "Confidence": f"{float(trend.get('confidence_score') or trend.get('score') or 0):.0f}/100",
                            "Coverage": f"{float(trend.get('data_completeness_score') or 0):.0f}%",
                            "Evidence": int(trend.get("evidence_count") or 0),
                            "Domains": int(trend.get("independent_domain_count") or 0),
                            "Missing evidence": ", ".join(
                                trend.get("missing_components") or []
                            )
                            or "Confidence gate not yet cleared",
                            "Status": "Not decision-ready",
                        }
                        for trend in watchlist
                    ]
                ),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                "These rows are deliberately separated so a missing value cannot "
                "look like a complete recommendation."
            )

    with st.expander("Analyst detail · measurements and evidence checks"):
        technical = pd.DataFrame(
            [
                {
                    "Trend": trend.get("name"),
                    "Origin": trend.get("discovery_origin_label")
                    or "Not recorded",
                    "Google week on week": (
                        f"{float((trend.get('google_trends_metrics') or {}).get('week_over_week_change_percent')):+.0f}%"
                        if (trend.get("google_trends_metrics") or {}).get("week_over_week_change_percent") is not None
                        else "Not measured"
                    ),
                    "X posts week on week": f"{float(trend.get('mention_growth', 0)):+.0f}%",
                    "Independent domains": int(trend.get("independent_domain_count") or 0),
                    "Evidence items": int(trend.get("evidence_count") or 0),
                    "Coverage": f"{float(trend.get('data_completeness_score') or 0):.0f}%",
                    "Momentum": str(trend.get("momentum") or "insufficient data"),
                }
                for trend in trends
            ]
        )
        if not technical.empty:
            st.dataframe(technical, hide_index=True, width="stretch")
        st.caption(
            "Very large percentages can follow a tiny previous-week baseline. They remain "
            "traceable measurements, but confidence also depends on independent evidence."
        )

    section_header("Deep dive", "Inspect one signal")
    inspectable = sorted(
        trends,
        key=lambda row: float(row.get("score") or 0),
        reverse=True,
    )
    selected_name = st.selectbox(
        "Trend",
        [trend.get("name") for trend in inspectable],
        key="radar_trend",
    )
    selected = next(
        trend for trend in inspectable if trend.get("name") == selected_name
    )
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        chart_or_quality_note([selected])
        if selected.get("series_issue"):
            st.caption(str(selected.get("series_issue")))
    with right:
        def component(value: object) -> str:
            return (
                f"{float(value):.0f}"
                if value is not None
                else "Not collected"
            )

        st.markdown(f"### {selected.get('name')}")
        st.write(selected.get("why_now"))
        st.markdown(
            f"""
            <div class="score-row"><span>Confidence</span><strong>{float(selected.get('confidence_score') or selected.get('score') or 0):.0f}</strong></div>
            <div class="score-row"><span>Evidence coverage</span><strong>{float(selected.get('data_completeness_score') or 0):.0f}%</strong></div>
            <div class="score-row"><span>HULA opportunity</span><strong>{float(selected.get('hula_opportunity_score') or 0):.0f}</strong></div>
            <div class="score-row"><span>Editorial</span><strong>{component((selected.get('score_breakdown') or {}).get('editorial'))}</strong></div>
            <div class="score-row"><span>Cross-source</span><strong>{component((selected.get('score_breakdown') or {}).get('cross_source'))}</strong></div>
            <div class="score-row"><span>Google Trends</span><strong>{component((selected.get('score_breakdown') or {}).get('google_trends'))}</strong></div>
            <div class="score-row"><span>Social</span><strong>{component((selected.get('score_breakdown') or {}).get('social'))}</strong></div>
            <div class="score-row"><span>Runway / celebrity</span><strong>{component((selected.get('score_breakdown') or {}).get('runway_celebrity'))}</strong></div>
            <div class="score-row"><span>Commercial availability</span><strong>{component((selected.get('score_breakdown') or {}).get('commercial'))}</strong></div>
            <div class="score-row"><span>Independent domains</span><strong>{int(selected.get('independent_domain_count') or 0)}</strong></div>
            <div class="score-row"><span>Evidence items</span><strong>{int(selected.get('evidence_count') or 0)}</strong></div>
            <div class="score-row"><span>Confidence band</span><strong>{html.escape(str(selected.get('confidence', '')))}</strong></div>
            <div class="score-row"><span>Discovery origin</span><strong>{html.escape(str(selected.get('discovery_origin_label') or 'Not recorded'))}</strong></div>
            """,
            unsafe_allow_html=True,
        )
        st.caption(
            "Duplicate or syndicated evidence is excluded. An uncollected component stays "
            "explicitly missing; the app never converts it to zero."
        )

    publisher_evidence = list(selected.get("evidence") or [])
    if publisher_evidence:
        section_header(
            "Traceable evidence",
            "Every source and measurement behind this trend",
        )
        evidence_table = pd.DataFrame(
            [
                {
                    "Source": row.get("source_name"),
                    "Type": row.get("evidence_type"),
                    "Article / measurement": row.get("title"),
                    "Published": (
                        str(row.get("published_at") or "")[:10]
                        or "Date not exposed"
                    ),
                    "Position": row.get("supports_or_contradicts"),
                    "Summary": row.get("evidence_summary"),
                    "URL": row.get("source_url"),
                }
                for row in publisher_evidence
            ]
        )
        st.dataframe(
            evidence_table,
            hide_index=True,
            width="stretch",
            column_config={
                "URL": st.column_config.LinkColumn("Source page"),
            },
        )
        st.caption(
            "All URLs are stored with the weekly snapshot. Contradictory evidence is "
            "retained and lowers confidence; missing search data is labelled insufficient."
        )

    warnings = list(selected.get("warnings") or [])
    if warnings:
        with st.expander(f"Scoring warnings ({len(warnings)})"):
            for warning in warnings:
                st.write(f"• {warning}")

    if selected.get("instagram_hashtag"):
        st.caption(
            f"Instagram comparison: #{selected.get('instagram_hashtag')} has "
            f"{int(selected.get('instagram_posts_count') or 0):,} public uses"
            + (
                f" and about {float(selected.get('instagram_posts_per_day') or 0):,.0f} posts/day."
                if selected.get("instagram_posts_per_day")
                else "."
            )
            + " This is directional metadata, not proof that the hashtag caused demand."
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
    all_trends = snapshot.get("trends", [])
    trends = [trend for trend in all_trends if trend.get("decision_ready")]
    page_header(
        "PRODUCT MATCH · CATALOGUE",
        "Turn a signal into a sellable edit.",
        "Rank in-stock HULA pieces by trend fit, external momentum, content readiness and catalogue freshness.",
    )
    mode_banner(snapshot.get("meta", {}))
    if not trends:
        st.info(
            "Product matching opens when at least one trend clears the current-evidence, "
            "independent-domain and minimum-confidence gates."
        )
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
            "Frame 3: link, HULA Soho or The Hub CTA",
        ],
        "cta": "Shop the edit online, visit HULA Soho or discover it at The Hub before the one-of-one pieces are gone.",
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
    trends = [
        trend
        for trend in snapshot.get("trends", [])
        if trend.get("decision_ready")
    ]
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
    channel = left.selectbox(
        "Format",
        [
            "Instagram Reel",
            "Instagram carousel",
            "Email",
            "Blog post",
            "Soho store activation",
            "The Hub store activation",
        ],
    )
    objective = right.selectbox(
        "Objective",
        [
            "Drive product discovery",
            "Bring visits to Soho",
            "Bring visits to The Hub",
            "Sell one-of-one pieces",
            "Build fashion authority",
            "Re-engage VIPs",
        ],
    )
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


def blog_download_markdown(blog: dict) -> str:
    notes = "\n".join(
        f"- {note}" for note in blog.get("editorial_notes") or []
    )
    sources = "\n".join(
        f"- [{source.get('title')}]({source.get('url')})"
        for source in blog.get("sources") or []
    )
    return f"""# {blog.get('title', 'HULA weekly edit')}

{blog.get('dek', '')}

{blog.get('body_markdown', '')}

---

## Editorial QA notes
{notes or '- No additional notes.'}

## Evidence sources
{sources or '- No stored evidence sources were available.'}
"""


def weekly_blog(snapshot: dict, settings: Settings) -> None:
    trends = [
        trend
        for trend in snapshot.get("trends", [])
        if trend.get("decision_ready")
    ]
    page_header(
        "WEDNESDAY BLOG · EVIDENCE-LOCKED",
        "Turn this week's signal into a story worth reading.",
        "Choose the trend, products and business reason. The writer may use only evidence and URLs already stored in this weekly snapshot.",
    )
    mode_banner(snapshot.get("meta", {}))
    if not trends:
        st.info(
            "A draft can be generated once a trend clears the evidence-count, "
            "independent-domain and recency gates."
        )
        return

    products = product_lookup(snapshot)
    selected_name = st.selectbox(
        "Trend",
        [trend.get("name") for trend in trends],
        key="blog_trend",
    )
    trend = next(
        item for item in trends if item.get("name") == selected_name
    )
    matches = recommendation_rows(snapshot, str(trend.get("id")))
    candidate_ids = [
        str(row.get("product_id"))
        for row in matches
        if str(row.get("product_id")) in products
    ]
    selected_ids = st.multiselect(
        "HULA products",
        candidate_ids,
        default=candidate_ids[:5],
        max_selections=5,
        format_func=lambda product_id: (
            f"{products[product_id].get('vendor')} · "
            f"{products[product_id].get('title')}"
        ),
    )
    left, right = st.columns([1.15, 1])
    reason = left.selectbox(
        "Reason for the new blog or post",
        [
            "This week's strongest product trend",
            "New HULA products",
            "Soho store moment",
            "The Hub store moment",
            "Designer or archive story",
            "Circular-fashion education",
        ],
    )
    stores = right.multiselect(
        "Relevant destinations",
        ["Online", "HULA Soho", "The Hub"],
        default=["Online", "HULA Soho", "The Hub"],
    )
    selected_products = [products[product_id] for product_id in selected_ids]
    if st.button(
        "Generate evidence-locked blog",
        type="primary",
        disabled=not selected_products,
    ):
        with st.spinner(
            "Writing from the stored evidence and selected product facts…"
        ):
            try:
                if settings.openai_configured:
                    connector = OpenAIResponsesConnector(
                        settings.openai_api_key,
                        api_url=settings.openai_api_url,
                        luna_model=settings.openai_luna_model,
                        terra_model=settings.openai_terra_model,
                        sol_model=settings.openai_sol_model,
                        timeout_seconds=settings.openai_timeout_seconds,
                    )
                    source = settings.openai_sol_model
                elif settings.gemini_configured:
                    connector = GeminiResearchConnector(
                        settings.gemini_api_key,
                        model=settings.gemini_model,
                        api_url=settings.gemini_api_url,
                        timeout_seconds=settings.gemini_timeout_seconds,
                        grounding_enabled=False,
                    )
                    source = settings.gemini_model
                else:
                    raise RuntimeError(
                        "No writing model is configured in this deployed copy."
                    )
                blog = generate_researched_blog(
                    connector,
                    trend,
                    selected_products,
                    reason=reason,
                    stores=stores,
                )
                st.session_state.pop("blog_generation_error", None)
            except Exception as exc:
                blog = fallback_blog(
                    trend,
                    selected_products,
                    reason=reason,
                    stores=stores,
                )
                source = "safe fallback"
                st.session_state.blog_generation_error = safe_error(
                    exc,
                    [settings.gemini_api_key],
                )
            updated = dict(snapshot)
            editorial = dict(updated.get("editorial") or {})
            editorial["latest_blog"] = blog
            updated["editorial"] = editorial
            save_snapshot(updated, settings.snapshot_path)
            st.session_state.snapshot = updated
            st.session_state.blog_source = source
            if settings.supabase_configured:
                try:
                    store = SupabaseStore(
                        settings.supabase_url,
                        settings.supabase_secret_key,
                        snapshot_table=settings.supabase_snapshot_table,
                        blog_table=settings.supabase_blog_table,
                    )
                    store.save_snapshot(updated)
                    store.save_blog(blog)
                except Exception as exc:
                    st.warning(
                        "The draft was saved locally, but Supabase history could "
                        f"not be updated: {safe_error(exc, [settings.supabase_secret_key])}"
                    )

    blog = (
        (st.session_state.get("snapshot") or snapshot)
        .get("editorial", {})
        .get("latest_blog")
    )
    if not isinstance(blog, dict):
        st.markdown(
            '<div class="method-note"><strong>No draft yet.</strong> The scheduled Wednesday refresh can generate the lead draft automatically, or create one here for any decision-ready trend.</div>',
            unsafe_allow_html=True,
        )
        return

    section_header("Editable draft", str(blog.get("title") or "HULA weekly edit"))
    st.caption(
        f"Generated with {blog.get('model') or st.session_state.get('blog_source', 'the configured model')} · "
        f"{'stored-evidence only' if blog.get('evidence_locked') else 'safe fallback'}"
    )
    title = st.text_input(
        "Title",
        value=str(blog.get("title") or ""),
        key=f"blog_title_{blog.get('generated_at', 'latest')}",
    )
    dek = st.text_area(
        "Dek",
        value=str(blog.get("dek") or ""),
        height=90,
        key=f"blog_dek_{blog.get('generated_at', 'latest')}",
    )
    body = st.text_area(
        "Blog body (Markdown)",
        value=str(blog.get("body_markdown") or ""),
        height=620,
        key=f"blog_body_{blog.get('generated_at', 'latest')}",
    )
    actions = st.columns(2)
    if actions[0].button("Save edited draft", width="stretch"):
        edited = {**blog, "title": title, "dek": dek, "body_markdown": body}
        updated = dict(st.session_state.get("snapshot") or snapshot)
        editorial = dict(updated.get("editorial") or {})
        editorial["latest_blog"] = edited
        updated["editorial"] = editorial
        save_snapshot(updated, settings.snapshot_path)
        st.session_state.snapshot = updated
        if settings.supabase_configured:
            try:
                store = SupabaseStore(
                    settings.supabase_url,
                    settings.supabase_secret_key,
                    snapshot_table=settings.supabase_snapshot_table,
                    blog_table=settings.supabase_blog_table,
                )
                store.save_snapshot(updated)
                store.save_blog(edited)
            except Exception as exc:
                st.warning(
                    "Edited draft saved locally; Supabase history failed: "
                    + safe_error(exc, [settings.supabase_secret_key])
                )
        st.success("Edited draft saved.")
    actions[1].download_button(
        "Download Shopify-ready Markdown",
        data=blog_download_markdown(
            {**blog, "title": title, "dek": dek, "body_markdown": body}
        ),
        file_name=f"hula-{blog.get('trend_id', 'weekly')}-blog.md",
        mime="text/markdown",
        width="stretch",
    )

    error = st.session_state.get("blog_generation_error")
    if error:
        st.error(
            "The configured writer was unavailable, so the safe fallback contains "
            f"no unsupported model-derived claims. {error}"
        )

    claims = list(blog.get("claims") or [])
    sources = list(blog.get("sources") or [])
    section_header("Evidence check", "What may and may not be published as fact")
    metrics = st.columns(3)
    metrics[0].metric(
        "Confirmed claims",
        sum(claim.get("status") == "confirmed" for claim in claims),
    )
    metrics[1].metric(
        "Needs review",
        sum(claim.get("status") != "confirmed" for claim in claims),
    )
    metrics[2].metric("Stored sources", len(sources))
    if claims:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Claim": claim.get("claim"),
                        "Evidence status": claim.get("status"),
                        "Product": claim.get("product_id") or "—",
                        "Sources": ", ".join(
                            str(index)
                            for index in claim.get("source_indices") or []
                        )
                        or "—",
                        "Editorial note": claim.get("evidence_note"),
                    }
                    for claim in claims
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    if sources:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "#": source.get("index"),
                        "Source": source.get("title"),
                        "URL": source.get("url"),
                    }
                    for source in sources
                ]
            ),
            hide_index=True,
            width="stretch",
            column_config={"URL": st.column_config.LinkColumn("URL")},
        )


def status_class(value: str) -> str:
    lowered = value.lower()
    if "live" in lowered:
        return "live"
    if "standby" in lowered:
        return "standby"
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
            "Commercial websites",
            str(
                status.get(
                    "commercial_websites",
                    "ready on refresh"
                    if settings.commercial_sources_enabled
                    else "not configured",
                )
            ),
            (
                f"{len(COMMERCIAL_SOURCES)} approved publishers · public titles, headings, dates and URLs"
            ),
        ),
        (
            "Instagram hashtags",
            str(
                status.get(
                    "instagram_hashtags",
                    "configured"
                    if settings.instagram_configured
                    else "not configured",
                )
            ),
            (
                f"Aggregate metrics for up to {settings.instagram_hashtag_max_terms} qualified trends · "
                f"Credentials: {'added' if settings.instagram_configured else 'missing'}"
            ),
        ),
        (
            "Catalogue",
            str(status.get("shopify", "configured" if settings.shopify_configured else "not configured")),
            catalogue_detail,
        ),
        (
            "OpenAI Responses",
            str(status.get("openai", "configured" if settings.openai_configured else "not configured")),
            (
                f"Luna / Terra / Sol · credentials: "
                f"{'added' if settings.openai_configured else 'missing'}"
            ),
        ),
        (
            "OpenRouter",
            str(status.get("openrouter", "configured" if settings.openrouter_configured else "not configured")),
            f"Credentials: {'added' if settings.openrouter_configured else 'missing'}",
        ),
        (
            "Supabase history",
            str(
                status.get(
                    "supabase",
                    "configured"
                    if settings.supabase_configured
                    else "not configured",
                )
            ),
            f"Credentials: {'added' if settings.supabase_configured else 'missing'}",
        ),
        (
            "Gemini writer fallback",
            str(
                status.get(
                    "gemini",
                    "configured"
                    if settings.gemini_configured
                    else "not configured",
                )
            ),
            (
                f"Model: {settings.gemini_model} · "
                f"Credentials: {'added' if settings.gemini_configured else 'missing'}"
            ),
        ),
    ]
    for start in range(0, len(definitions), 3):
        cards = st.columns(3)
        for column, (name, value, detail) in zip(
            cards,
            definitions[start : start + 3],
        ):
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
        "An uploaded catalogue is intentionally hybrid; it is not a model or source failure."
    )
    diagnostics = source_diagnostic_rows(
        meta,
        google_configured=settings.serpapi_configured,
        apify_configured=settings.apify_configured,
        shopify_configured=settings.shopify_configured,
        openrouter_configured=settings.openrouter_configured,
        instagram_configured=settings.instagram_configured,
        commercial_configured=settings.commercial_sources_enabled,
        supabase_configured=settings.supabase_configured,
        gemini_configured=settings.gemini_configured,
        openai_configured=settings.openai_configured,
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
        instagram_configured=settings.instagram_configured,
        commercial_configured=settings.commercial_sources_enabled,
        supabase_configured=settings.supabase_configured,
        gemini_configured=settings.gemini_configured,
        openai_configured=settings.openai_configured,
        openai_sol_model=settings.openai_sol_model,
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

    section_header(
        "Commercial signal hierarchy",
        "The approved publisher and report panel",
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Publisher": source.name,
                    "Weight": f"{source.weight:.0f}×",
                    "Route": source.index_urls[0],
                    "Evidence": (
                        "Named runway taxonomy"
                        if source.kind == "taxonomy"
                        else "Publisher title, editorial trend heading or quantified report signal"
                    ),
                }
                for source in COMMERCIAL_SOURCES
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={"Route": st.column_config.LinkColumn("Public source")},
    )
    st.caption(
        "Tagwalk, Trendalytics, Heuritech, Data But Make It Fashion and Lyst carry "
        "the higher authority weight. Who What Wear, Who What Wear UK, Vogue and "
        "ELLE provide commercial/editorial confirmation. A source counts only when "
        "its own title, taxonomy, editorial trend heading or quantified report text "
        "explicitly names the trend. RSS, sitemaps and domain-restricted search are "
        "discovery routes; ordinary article prose is not mined indiscriminately."
    )
    publisher_status = (
        (meta.get("commercial_collection") or {}).get("source_status") or {}
    )
    if publisher_status:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Publisher": row.get("publisher") or key,
                        "Last refresh": row.get("state") or "Unknown",
                        "Index pages": (
                            f"{int(row.get('pages_loaded') or 0)}/"
                            f"{int(row.get('pages_requested') or 0)}"
                        ),
                        "Articles loaded": int(row.get("articles_loaded") or 0),
                        "Named trends": int(row.get("named_trends") or 0),
                        "Explicit evidence": int(row.get("evidence_rows") or 0),
                        "Discovery routes": ", ".join(
                            row.get("discovery_methods") or []
                        ),
                        "First error": str((row.get("errors") or [""])[0]),
                    }
                    for key, row in publisher_status.items()
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "A failed source is isolated. Evidence from the remaining publishers "
            "is retained and the commercial weight is renormalised."
        )

    section_header(
        "Live validation queue",
        "The exact candidates sent to search and hashtag enrichment",
    )
    validation_plan = list(meta.get("validation_plan") or [])
    if validation_plan:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Rank": row.get("rank"),
                        "Candidate": row.get("name"),
                        "Origin": ", ".join(row.get("origins") or []),
                        "Priority": f"{float(row.get('priority') or 0):.0f}/100",
                        "Fresh publisher pages": int(
                            row.get("current_article_count") or 0
                        ),
                        "Fallback seed only": "Yes" if row.get("seed_only") else "No",
                    }
                    for row in validation_plan
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        google_cache_match = (meta.get("google_trends") or {}).get(
            "cache_candidate_match"
        )
        st.caption(
            "A 24-hour Google cache is reused only when this live candidate set matches "
            "the cached fingerprint. Last refresh candidate match: "
            + ("yes." if google_cache_match else "no — a new measurement was required.")
        )
    else:
        st.info("Run a live refresh to create the validation queue.")

    section_header(
        "X listening design",
        "Open discovery plus targeted validation of fresh publisher finds",
    )
    last_validation_terms = list(
        (meta.get("x_listening") or {}).get("validation_terms") or []
    )
    if not last_validation_terms:
        last_validation_terms = [
            str(row.get("name") or "")
            for row in (meta.get("commercial_discoveries") or [])[:12]
            if row.get("name")
        ]
    listening_plan = build_listening_plan(
        language=settings.x_language,
        results_per_query=settings.apify_results_per_query,
        expert_results_per_query=settings.apify_expert_results_per_query,
        expert_accounts=settings.x_expert_accounts,
        priority_accounts=settings.x_priority_accounts,
        validation_terms=last_validation_terms,
    )
    open_searches = sum(not row.get("is_expert") for row in listening_plan)
    expert_searches = sum(bool(row.get("is_expert")) for row in listening_plan)
    dynamic_searches = sum(
        bool(row.get("is_dynamic_validation")) for row in listening_plan
    )
    topic_families = len(
        {
            str(row.get("group") or "")
            for row in listening_plan
            if not row.get("is_expert")
        }
    )
    max_posts = sum(int((row.get("input") or {}).get("max_results") or 0) for row in listening_plan)
    design_metrics = st.columns(4)
    design_metrics[0].metric("Rolling searches", len(listening_plan), "current + previous week")
    design_metrics[1].metric(
        "Open topic searches",
        open_searches,
        f"{topic_families} families · {dynamic_searches} targeted",
    )
    monitored_accounts = len(
        {
            *settings.x_expert_accounts,
            *settings.x_priority_accounts,
        }
    )
    design_metrics[2].metric(
        "Source searches",
        expert_searches,
        f"{monitored_accounts} accounts",
    )
    design_metrics[3].metric("Maximum results", f"{max_posts:,}", "before cross-query deduplication")
    st.write(
        "The app runs each topic against a **current seven-day window** and a separate "
        "**previous seven-day window**. Hashtags are accepted when they occur naturally, but the "
        "search does not depend on hashtags or profiles alone. One dynamic family tests the "
        "freshest publisher-discovered names; the other families remain open-ended. X remains "
        "conversation context, while commercial authority comes from the approved websites."
    )
    plan_table = pd.DataFrame(
        [
            {
                "Search": row.get("group_label"),
                "Window": row.get("window_label"),
                "Role": (
                    "Publisher-account context"
                    if row.get("expert_tier") == "commercial-priority"
                    else "Supporting source context"
                    if row.get("is_expert")
                    else "Fresh publisher validation"
                    if row.get("is_dynamic_validation")
                    else "Open discovery"
                ),
                "Evidence weight": (
                    f"{float(row.get('expert_weight') or 1):.0f}×"
                    if row.get("is_expert")
                    else "1×"
                ),
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
        "**Pants, skirt, flats and polka** fail; **capri pants, pencil skirt, ballet flats and polka dots** pass. "
        "The approved standalone exceptions are **jeans, loafers and sandals**. A trusted report may also explicitly introduce a colour, material or aesthetic such as burgundy, suede or boho chic."
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
            "These words are blocked when they appear alone or as an entirely generic phrase. "
            "Specific combinations remain eligible, subject to the source-aware specificity gate."
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
        primary_ai_configured = settings.openai_configured or settings.openrouter_configured
        primary_ai_label = "OpenAI Responses" if settings.openai_configured else "OpenRouter"
        if st.button(f"Test {primary_ai_label}", disabled=not primary_ai_configured, width="stretch"):
            try:
                if settings.openai_configured:
                    connector = OpenAIResponsesConnector(
                        settings.openai_api_key,
                        api_url=settings.openai_api_url,
                        luna_model=settings.openai_luna_model,
                        terra_model=settings.openai_terra_model,
                        sol_model=settings.openai_sol_model,
                        timeout_seconds=settings.openai_timeout_seconds,
                    )
                    secret = settings.openai_api_key
                else:
                    connector = OpenRouterConnector(
                        settings.openrouter_api_key,
                        settings.openrouter_model,
                        settings.openrouter_api_url,
                        settings.openrouter_timeout,
                        settings.openrouter_site_url,
                        settings.openrouter_app_name,
                    )
                    secret = settings.openrouter_api_key
                result = connector.test_connection()
                st.session_state.openrouter_test_result = {
                    "ok": True,
                    "detail": f"Connected successfully to {result.get('model')}.",
                }
            except Exception as exc:
                st.session_state.openrouter_test_result = {
                    "ok": False,
                    "detail": safe_error(exc, [secret]),
                }
        openrouter_test = st.session_state.get("openrouter_test_result")
        if isinstance(openrouter_test, dict):
            (st.success if openrouter_test.get("ok") else st.error)(
                str(openrouter_test.get("detail", "No diagnostic detail was returned."))
            )

    platform_tests = st.columns(4)
    with platform_tests[0]:
        if st.button(
            "Test publisher pages",
            disabled=not settings.commercial_sources_enabled,
            width="stretch",
        ):
            try:
                result = CommercialSourceCollector(
                    timeout_seconds=settings.commercial_timeout_seconds,
                    max_workers=settings.commercial_max_workers,
                    serpapi_api_key=settings.serpapi_api_key,
                    serpapi_endpoint=settings.serpapi_endpoint,
                ).test_connection()
                ok = bool(result.get("ok"))
                st.session_state.commercial_test_result = {
                    "ok": ok,
                    "detail": (
                        f"{int(result.get('publishers_live') or 0)} live, "
                        f"{int(result.get('publishers_partial') or 0)} partial and "
                        f"{int(result.get('publishers_failed') or 0)} failed publishers · "
                        f"{int(result.get('publishers_with_evidence') or 0)}/"
                        f"{len(COMMERCIAL_SOURCES)} sites yielded named evidence · "
                        f"{int(result.get('named_trends') or 0)} named trends and "
                        f"{int(result.get('evidence_rows') or 0)} evidence rows."
                    ),
                    "source_status": result.get("source_status") or {},
                }
            except Exception as exc:
                st.session_state.commercial_test_result = {
                    "ok": False,
                    "detail": safe_error(exc),
                }
        commercial_test = st.session_state.get("commercial_test_result")
        if isinstance(commercial_test, dict):
            (st.success if commercial_test.get("ok") else st.error)(
                str(commercial_test.get("detail", "No diagnostic detail was returned."))
            )
        st.caption(
            "Tests every approved source independently. Direct publisher pages need no "
            "new key; the existing SerpApi key is used only as a domain-restricted fallback."
        )

    with platform_tests[1]:
        if st.button(
            "Test hashtag Actor",
            disabled=not settings.instagram_configured,
            width="stretch",
        ):
            try:
                result = InstagramHashtagAnalyticsConnector(
                    settings.apify_token,
                    actor_id=settings.apify_instagram_actor_id,
                    timeout_seconds=settings.apify_timeout_seconds,
                    memory_mb=settings.apify_x_memory_mb,
                ).test_connection()
                st.session_state.instagram_test_result = {
                    "ok": True,
                    "detail": (
                        f"Actor available: {result.get('actor_username')}/"
                        f"{result.get('actor_name')} · aggregate metadata mode."
                    ),
                }
            except Exception as exc:
                st.session_state.instagram_test_result = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.apify_token]),
                }
        instagram_test = st.session_state.get("instagram_test_result")
        if isinstance(instagram_test, dict):
            (st.success if instagram_test.get("ok") else st.error)(
                str(instagram_test.get("detail", "No diagnostic detail was returned."))
            )
        st.caption("Checks the aggregate hashtag-analytics Actor without starting a paid run.")

    with platform_tests[2]:
        if st.button(
            "Test Supabase history",
            disabled=not settings.supabase_configured,
            width="stretch",
        ):
            try:
                result = SupabaseStore(
                    settings.supabase_url,
                    settings.supabase_secret_key,
                    snapshot_table=settings.supabase_snapshot_table,
                    blog_table=settings.supabase_blog_table,
                ).test_connection()
                st.session_state.supabase_test_result = {
                    "ok": True,
                    "detail": (
                        f"Connected to {result.get('snapshot_table')} · "
                        f"{int(result.get('rows_visible') or 0)} row(s) visible."
                    ),
                }
            except Exception as exc:
                st.session_state.supabase_test_result = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.supabase_secret_key]),
                }
        supabase_test = st.session_state.get("supabase_test_result")
        if isinstance(supabase_test, dict):
            (st.success if supabase_test.get("ok") else st.error)(
                str(supabase_test.get("detail", "No diagnostic detail was returned."))
            )
        st.caption("If the tables are missing, run supabase/schema.sql once.")

    with platform_tests[3]:
        if st.button(
            "Test Gemini fallback",
            disabled=not settings.gemini_configured,
            width="stretch",
        ):
            try:
                result = GeminiResearchConnector(
                    settings.gemini_api_key,
                    model=settings.gemini_model,
                    api_url=settings.gemini_api_url,
                    timeout_seconds=settings.gemini_timeout_seconds,
                    grounding_enabled=False,
                ).test_connection()
                st.session_state.gemini_test_result = {
                    "ok": True,
                    "detail": f"Connected successfully to {result.get('model')}.",
                }
            except Exception as exc:
                st.session_state.gemini_test_result = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.gemini_api_key]),
                }
        gemini_test = st.session_state.get("gemini_test_result")
        if isinstance(gemini_test, dict):
            (st.success if gemini_test.get("ok") else st.error)(
                str(gemini_test.get("detail", "No diagnostic detail was returned."))
            )
        st.caption(
            "Checks the optional fallback writer. Blog generation is evidence-locked "
            "and does not use live Search grounding."
        )

    if isinstance(commercial_test, dict):
        test_sources = commercial_test.get("source_status") or {}
        if test_sources:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Publisher": row.get("publisher") or key,
                            "State": row.get("state"),
                            "Named trends": int(row.get("named_trends") or 0),
                            "Evidence rows": int(row.get("evidence_rows") or 0),
                            "Routes": ", ".join(row.get("discovery_methods") or []),
                            "First error": str((row.get("errors") or [""])[0]),
                        }
                        for key, row in test_sources.items()
                    ]
                ),
                hide_index=True,
                width="stretch",
            )

    section_header("Live refresh", "Run the full evidence pipeline")
    include_llm = st.checkbox(
        "Use the configured model to merge aliases and write evidence-led summaries",
        value=settings.openai_configured or settings.openrouter_configured,
    )
    include_editorial = st.checkbox(
        "Generate the evidence-locked Wednesday blog after ranking",
        value=settings.openai_configured or settings.gemini_configured,
        help=(
            "The writer receives the highest decision-ready trend, its stored evidence "
            "and selected products only after deterministic ranking is complete."
        ),
    )
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
                    generate_editorial=include_editorial,
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
                            settings.gemini_api_key,
                            settings.supabase_secret_key,
                            settings.shopify_client_secret,
                            settings.shopify_admin_access_token,
                        ],
                    )
                )
    st.caption(
        "The scheduled GitHub workflow runs every Wednesday at 09:17 Hong Kong time, "
        "keeps the last selected catalogue source and creates the researched lead draft."
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
                updated_meta["google_display_schema_version"] = "2.0"
                updated_snapshot["meta"] = updated_meta
                updated_snapshot = upgrade_snapshot_to_v2(updated_snapshot)
                save_snapshot(updated_snapshot, settings.snapshot_path)
                st.session_state.snapshot = updated_snapshot
                st.success("Manual search data applied.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    section_header("External signal", "How the fashion trend score is assembled")
    score_parts = [
        ("25%", "Editorial evidence", "Authority-weighted, relevant and recent articles."),
        ("20%", "Cross-source", "Independent domains plus evidence-type diversity."),
        ("20%", "Google Trends", "Current interest, weekly growth, slope and baseline breakout."),
        ("15%", "Social momentum", "Growth, velocity, creator and platform diversity."),
        ("10%", "Runway / celebrity", "Recent recurrence and independently reported adoption."),
        ("10%", "Commercial", "Current availability across independent retail channels."),
    ]
    for start in range(0, len(score_parts), 3):
        signal_method = st.columns(3)
        for column, (number, title, copy) in zip(signal_method, score_parts[start : start + 3]):
            with column:
                st.metric(title, number)
                st.caption(copy)
    st.caption(
        "The score automatically reweights across sources that actually supplied evidence; an unavailable "
        "source is never treated as a zero. Evidence coverage remains separate, and caps prevent one "
        "source, one launch or outdated evidence from looking more certain than it is."
    )

    section_header("Product opportunity", "How the catalogue recommendation score works")
    method = st.columns(3)
    for column, number, title, copy in [
        (method[0], "65%", "Trend confidence", "The evidence-based external score above."),
        (method[1], "25%", "HULA catalogue fit", "Similarity to current in-stock product metadata."),
        (method[2], "10%", "Resale suitability", "How naturally the trend works in luxury resale."),
    ]:
        with column:
            st.metric(title, number)
            st.caption(copy)
    st.markdown(
        '<div class="method-note"><strong>Data minimisation:</strong> raw X posts are held only during the refresh, then discarded. Publisher evidence keeps short labels, selected headings, measurements, dates and source URLs—not copied articles. Instagram requests aggregate metadata only. Shopify access is read-only and excludes customers, orders and payments. Writing models receive stored evidence and selected public-product fields only; Python owns all arithmetic.</div>',
        unsafe_allow_html=True,
    )
    openai_usage = list(meta.get("openai_usage") or [])
    if openai_usage:
        section_header("Model usage", "Last OpenAI refresh")
        usage_frame = pd.DataFrame(openai_usage)
        st.metric(
            "Estimated model cost",
            f"US${sum(float(row.get('estimated_cost_usd') or 0) for row in openai_usage):.4f}",
            "excludes external data services",
        )
        st.dataframe(usage_frame, hide_index=True, width="stretch")
        st.caption(
            "This estimate uses the model-price table bundled with this build. "
            "Verify current official pricing before budgeting."
        )
    warnings = meta.get("warnings", [])
    if warnings:
        with st.expander(f"Refresh notes ({len(warnings)})"):
            for warning in warnings:
                st.write(f"• {warning}")


def _change_label(value: object) -> str:
    if value is None:
        return "Not measurable"
    try:
        return f"{float(value):+.0f}%"
    except (TypeError, ValueError):
        return "Not measurable"


def _google_trends_url(trend: dict, *, timeframe: str = "today 12-m") -> str:
    query = str(trend.get("google_query") or trend.get("query") or trend.get("name") or "")
    return (
        "https://trends.google.com/trends/explore?date="
        + quote(timeframe, safe="")
        + "&q="
        + quote(query, safe="")
    )


def _first_editorial_url(trend: dict) -> str:
    return next(
        (
            str(row.get("url") or row.get("source_url") or "")
            for row in trend.get("commercial_evidence") or []
            if row.get("url") or row.get("source_url")
        ),
        "",
    )


def _editorial_priority_frame(trends: list[dict]) -> pd.DataFrame:
    rows = []
    for index, trend in enumerate(trends, start=1):
        metrics = trend.get("google_trends_metrics") or {}
        rows.append(
            {
                "Rank": index,
                "Trend": trend.get("name"),
                "Action": business_decision(trend).upper(),
                "Publishers": int(trend.get("publisher_count") or 0),
                "Articles": int(
                    trend.get("article_count")
                    or trend.get("commercial_article_count")
                    or 0
                ),
                "Editorial consensus": f"{float(trend.get('editorial_consensus_score') or 0):.0f}/100",
                "Final priority": f"{float(trend.get('ranking_score') or 0):.0f}/100",
                "Google WoW": _change_label(
                    metrics.get("week_over_week_change_percent")
                ),
                "Google YoY": _change_label(
                    metrics.get("year_over_year_change_percent")
                ),
                "HULA opportunity": f"{float(trend.get('hula_opportunity_score') or 0):.0f}/100",
                "Newest article": str(trend.get("newest_published_at") or "")[:10]
                or "Date unavailable",
                "First article": _first_editorial_url(trend),
            }
        )
    return pd.DataFrame(rows)


def _editorial_evidence_frame(trend: dict) -> pd.DataFrame:
    rows = []
    for row in trend.get("commercial_evidence") or []:
        rows.append(
            {
                "Publisher": row.get("publisher") or row.get("source_name"),
                "Article": row.get("article_title") or row.get("title"),
                "Published": str(row.get("published_at") or "")[:10]
                or "Date unavailable",
                "How it was found": row.get("extraction_method")
                or row.get("evidence_kind"),
                "Evidence": row.get("explicit_label")
                or row.get("evidence_summary"),
                "Source": row.get("url") or row.get("source_url"),
            }
        )
    return pd.DataFrame(rows)


def editorial_this_week(snapshot: dict) -> None:
    meta = snapshot.get("meta") or {}
    trends = list(snapshot.get("trends") or [])
    updated = hk_time(str(meta.get("generated_at") or ""))
    page_header(
        f"WEEK {updated.isocalendar().week} · EDITORIAL CONSENSUS",
        "What fashion editors are converging on now.",
        "Recent publisher articles discover the ideas. GPT extracts specific trends. Independent overlap raises priority, and Google Trends shows whether people are searching too.",
    )
    mode_banner(meta)
    raw = meta.get("raw_counts") or {}
    metrics = st.columns(4)
    metrics[0].metric(
        "Articles scanned",
        int(raw.get("editorial_articles_scanned") or 0),
        f"last {21} days",
    )
    metrics[1].metric(
        "Publisher overlaps",
        int(raw.get("editorial_overlap_trends") or 0),
        "named by 2+ independent sites",
    )
    metrics[2].metric(
        "Google charts",
        int(raw.get("google_chart_ready_terms") or 0),
        str((meta.get("google_trends") or {}).get("market") or "Worldwide"),
    )
    metrics[3].metric(
        "Updated",
        updated.strftime("%d %b · %H:%M"),
        "Hong Kong time",
    )

    section_header("01 · Weekly ranking", "Overlap first, Google movement second")
    if not trends:
        st.warning("No recent editorial trends are available. Run a live refresh in Data & Setup.")
        return
    ranking = _editorial_priority_frame(trends)
    st.dataframe(
        ranking,
        hide_index=True,
        width="stretch",
        height=min(660, 38 * len(ranking) + 44),
        column_config={
            "First article": st.column_config.LinkColumn("First article"),
        },
    )
    st.caption(
        "A trend rises when separate publishers name the same concrete idea. A single-publisher find can still enter a small test when Google interest accelerates sharply."
    )

    section_header("02 · Signal board", "The strongest editorial opportunities")
    trend_cards(trends, min(4, len(trends)))
    decision_legend()

    section_header("03 · Google movement", "Plot the exact term selected from the articles")
    selected_name = st.selectbox(
        "Trend to plot",
        [str(trend.get("name") or "") for trend in trends],
        key="weekly_editorial_plot",
    )
    selected = next(trend for trend in trends if trend.get("name") == selected_name)
    google_metrics = selected.get("google_trends_metrics") or {}
    summary = st.columns(4)
    summary[0].metric(
        "Google query",
        str(selected.get("google_query") or selected.get("query") or selected_name),
    )
    summary[1].metric(
        "Week on week",
        _change_label(google_metrics.get("week_over_week_change_percent")),
    )
    summary[2].metric(
        "Year on year",
        _change_label(google_metrics.get("year_over_year_change_percent")),
    )
    summary[3].metric(
        "Publisher overlap",
        int(selected.get("publisher_count") or 0),
        str(selected.get("overlap_label") or ""),
    )
    if selected.get("recent_chart_ready"):
        chart_or_quality_note(
            [selected],
            series_key="recent_display_series",
            chart_ready_key="recent_chart_ready",
            chart_key="weekly_editorial_recent_chart",
        )
        st.caption("Recent movement uses the stored 90-day Google Trends timeline.")
    else:
        chart_or_quality_note([selected], chart_key="weekly_editorial_primary_context_chart")
    with st.expander("Show the 12-month Google context"):
        chart_or_quality_note([selected], chart_key="weekly_editorial_12m_chart")
    st.link_button(
        "Open this exact query in Google Trends",
        _google_trends_url(selected),
    )

    section_header("04 · Publisher proof", "The articles behind the selected trend")
    evidence = _editorial_evidence_frame(selected)
    if evidence.empty:
        st.info("No article-level evidence was stored for this trend.")
    else:
        st.dataframe(
            evidence,
            hide_index=True,
            width="stretch",
            column_config={"Source": st.column_config.LinkColumn("Read article")},
        )

    section_header("05 · Catalogue opportunity", "HULA pieces that can answer the signal")
    selected_recommendations = recommendation_rows(snapshot, str(selected.get("id") or ""))
    if selected_recommendations:
        render_product_grid(snapshot, selected_recommendations, count=6)
    else:
        st.info("No current catalogue product cleared the matching threshold for this trend.")


def editorial_trend_radar(snapshot: dict) -> None:
    meta = snapshot.get("meta") or {}
    trends = list(snapshot.get("trends") or [])
    collection = meta.get("editorial_collection") or meta.get("commercial_collection") or {}
    source_rows = collection.get("source_status") or {}
    page_header(
        "EDITORIAL RADAR · RECENT COVERAGE",
        "See where the fashion press agrees.",
        "Every candidate begins in a recent article. The radar keeps single-source discoveries visible, but rewards independent publisher overlap before looking at Google search momentum.",
    )
    mode_banner(meta)
    coverage = st.columns(4)
    coverage[0].metric("Publishers monitored", len(EDITORIAL_PUBLISHERS))
    coverage[1].metric(
        "Publishers with trends",
        sum(int(row.get("named_trends") or 0) > 0 for row in source_rows.values()),
    )
    coverage[2].metric("Concrete trends", len(trends))
    coverage[3].metric(
        "Actionable now",
        sum(bool(trend.get("decision_ready")) for trend in trends),
    )

    section_header("Publisher scan", "What was read during the last refresh")
    if source_rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Publisher": row.get("publisher") or key,
                        "State": row.get("state"),
                        "Articles loaded": int(row.get("articles_loaded") or 0),
                        "Trends extracted": int(row.get("named_trends") or 0),
                        "Routes": ", ".join(row.get("discovery_methods") or []),
                        "First issue": str((row.get("errors") or [""])[0]),
                    }
                    for key, row in source_rows.items()
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info("Run a live refresh to create publisher-level scan diagnostics.")

    section_header("Consensus inventory", "Every specific trend found in the article window")
    if trends:
        st.dataframe(
            _editorial_priority_frame(trends),
            hide_index=True,
            width="stretch",
            height=min(720, 38 * len(trends) + 44),
            column_config={
                "First article": st.column_config.LinkColumn("First article"),
            },
        )
    else:
        st.warning("No trend inventory is available yet.")
        return

    actions = [business_decision(trend) for trend in trends]
    action_metrics = st.columns(3)
    action_metrics[0].metric("Act now", actions.count("Act now"), "3+ publishers + Google")
    action_metrics[1].metric("Test this week", actions.count("Test this week"), "overlap or sharp search acceleration")
    action_metrics[2].metric("Watch", actions.count("Watch"), "promising but not confirmed")

    section_header("Deep dive", "Inspect one trend, its chart and every article")
    selected_name = st.selectbox(
        "Trend",
        [str(trend.get("name") or "") for trend in trends],
        key="editorial_radar_trend",
    )
    selected = next(trend for trend in trends if trend.get("name") == selected_name)
    left, right = st.columns([1.6, 1], gap="large")
    with left:
        chart_range = st.selectbox(
            "Google chart range",
            ["Recent 90 days", "12-month context"],
            key="editorial_chart_range",
        )
        if chart_range == "Recent 90 days" and selected.get("recent_chart_ready"):
            chart_or_quality_note(
                [selected],
                series_key="recent_display_series",
                chart_ready_key="recent_chart_ready",
            )
        else:
            chart_or_quality_note([selected])
        st.link_button("Open in Google Trends", _google_trends_url(selected))
    with right:
        metrics = selected.get("google_trends_metrics") or {}
        st.markdown(f"### {selected.get('name')}")
        st.write(selected.get("why_now"))
        st.markdown(
            f"""
            <div class="score-row"><span>Business action</span><strong>{html.escape(business_decision(selected))}</strong></div>
            <div class="score-row"><span>Independent publishers</span><strong>{int(selected.get('publisher_count') or 0)}</strong></div>
            <div class="score-row"><span>Recent articles</span><strong>{int(selected.get('article_count') or selected.get('commercial_article_count') or 0)}</strong></div>
            <div class="score-row"><span>Editorial consensus</span><strong>{float(selected.get('editorial_consensus_score') or 0):.0f}</strong></div>
            <div class="score-row"><span>Google week on week</span><strong>{html.escape(_change_label(metrics.get('week_over_week_change_percent')))}</strong></div>
            <div class="score-row"><span>Google year on year</span><strong>{html.escape(_change_label(metrics.get('year_over_year_change_percent')))}</strong></div>
            <div class="score-row"><span>Evidence confidence</span><strong>{float(selected.get('confidence_score') or 0):.0f}</strong></div>
            <div class="score-row"><span>HULA opportunity</span><strong>{float(selected.get('hula_opportunity_score') or 0):.0f}</strong></div>
            """,
            unsafe_allow_html=True,
        )

    evidence = _editorial_evidence_frame(selected)
    if not evidence.empty:
        st.dataframe(
            evidence,
            hide_index=True,
            width="stretch",
            column_config={"Source": st.column_config.LinkColumn("Read article")},
        )
    warnings = list(selected.get("warnings") or [])
    if warnings:
        with st.expander(f"Evidence notes ({len(warnings)})"):
            for warning in warnings:
                st.write(f"• {warning}")


def editorial_data_setup(snapshot: dict, settings: Settings) -> None:
    page_header(
        "DATA & SETUP · EDITORIAL CONSENSUS",
        "A simpler pipeline you can actually operate.",
        "Connect OpenAI, SerpApi Google Trends and the HULA catalogue. The publisher scan itself uses public pages and needs no social-scraping account.",
    )
    meta = snapshot.get("meta") or {}
    status = meta.get("source_status") or {}
    notice = st.session_state.pop("catalogue_notice", "")
    if notice:
        st.success(notice)
    catalogue_detail = (
        f"CSV snapshot · {len(snapshot.get('products') or []):,} products"
        if meta.get("catalogue_source") == "csv"
        else f"Shopify credentials: {'added' if settings.shopify_configured else 'missing'}"
    )
    google_meta = meta.get("google_trends") or {}
    cards = [
        (
            "Editorial publishers",
            str(status.get("editorial_publishers", "ready on refresh")),
            f"{len(EDITORIAL_PUBLISHERS)} sites · last {settings.editorial_lookback_days} days",
        ),
        (
            "GPT extraction",
            str(status.get("openai", "configured" if settings.openai_configured else "not configured")),
            f"Recent article scan · key {'added' if settings.openai_configured else 'missing'}",
        ),
        (
            "Google Trends",
            str(status.get("google_trends", "ready on refresh")),
            f"{google_meta.get('market') or settings.google_geo} · SerpApi key {'added' if settings.serpapi_configured else 'missing'}",
        ),
        ("HULA catalogue", str(status.get("shopify", "ready")), catalogue_detail),
        (
            "Supabase history",
            str(status.get("supabase", "configured" if settings.supabase_configured else "not configured")),
            "Optional weekly history",
        ),
        (
            "Wednesday writer",
            str(status.get("gemini", status.get("openai", "not configured"))),
            "Uses the ranked evidence and matched HULA products",
        ),
    ]
    for start in range(0, len(cards), 3):
        columns = st.columns(3)
        for column, (name, value, detail) in zip(columns, cards[start : start + 3]):
            with column:
                st.markdown(
                    f"""
                    <div class="source-card">
                      <div class="source-name">{html.escape(name)}</div>
                      <div class="source-state"><span class="dot {status_class(value)}"></span>{html.escape(value)}</div>
                      <div class="micro">{html.escape(detail)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    section_header("The refresh", "Four understandable steps")
    workflow = st.columns(4)
    for column, number, title, copy in [
        (workflow[0], "01", "Read recent articles", "Open the newest trend-relevant pages from the approved publishers."),
        (workflow[1], "02", "Extract concrete trends", "GPT returns specific items such as long-sleeve white T-shirts—not vague themes."),
        (workflow[2], "03", "Count publisher overlap", "The same publisher group counts once; more independent sites means higher priority."),
        (workflow[3], "04", "Plot Google demand", "Query only the extracted terms and save recent and 12-month charts."),
    ]:
        with column:
            st.metric(title, number)
            st.caption(copy)

    section_header("Publisher panel", "The sites monitored every week")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Publisher": source.name,
                    "Window": f"{source.max_age_days} days",
                    "Article cap": source.max_articles,
                    "Public section": source.index_urls[0],
                    "Independent group": source.publisher_group or source.key,
                }
                for source in EDITORIAL_PUBLISHERS
            ]
        ),
        hide_index=True,
        width="stretch",
        column_config={"Public section": st.column_config.LinkColumn("Public section")},
    )
    source_rows = (
        (meta.get("editorial_collection") or meta.get("commercial_collection") or {}).get("source_status")
        or {}
    )
    if source_rows:
        with st.expander("Last publisher scan detail", expanded=True):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Publisher": row.get("publisher") or key,
                            "State": row.get("state"),
                            "Articles": int(row.get("articles_loaded") or 0),
                            "Trends": int(row.get("named_trends") or 0),
                            "Routes": ", ".join(row.get("discovery_methods") or []),
                            "First issue": str((row.get("errors") or [""])[0]),
                        }
                        for key, row in source_rows.items()
                    ]
                ),
                hide_index=True,
                width="stretch",
            )

    section_header("Trend quality", "Specific fashion signals only")
    st.write(
        "The app accepts concrete garments, accessories, silhouettes, materials, colours and styling ideas. It rejects brands, sale pages, product-card noise and labels such as **fashion**, **pants** or **style** on their own."
    )
    filtered_rows = list(meta.get("filtered_terms") or [])
    if filtered_rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Removed term": row.get("term"),
                        "Reason": row.get("reason"),
                        "Found in": row.get("source"),
                    }
                    for row in filtered_rows
                ]
            ),
            hide_index=True,
            width="stretch",
        )
    with st.expander("View the permanent generic-term blocklist"):
        st.write(", ".join(generic_term_catalogue()))

    section_header("Product catalogue", "Choose CSV upload or the live Shopify API")
    default_catalogue = catalogue_choice(snapshot)
    selected_catalogue = st.radio(
        "Catalogue source",
        [CATALOGUE_CSV, CATALOGUE_API],
        index=0 if default_catalogue == CATALOGUE_CSV else 1,
        horizontal=True,
        key=CATALOGUE_SELECTOR_KEY,
    )
    if selected_catalogue == CATALOGUE_CSV:
        intro, template = st.columns([2.1, 1], gap="large")
        with intro:
            st.write("Upload a Shopify export or the simple HULA template. The normalised catalogue is saved in the dashboard snapshot.")
            uploaded_catalogue = st.file_uploader(
                "Product catalogue CSV",
                type=["csv"],
                key="product_catalogue_csv_editorial",
            )
        with template:
            if meta.get("catalogue_source") == "csv":
                st.info(
                    f"Using **{meta.get('catalogue_filename') or 'uploaded CSV'}** with **{len(snapshot.get('products') or []):,} products**."
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
                st.success(
                    f"{import_result.source_rows:,} rows became {len(import_result.products):,} normalised products."
                )
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
                for warning in import_result.warnings:
                    st.warning(warning)
                if st.button("Use this CSV catalogue", type="primary", key="apply_editorial_catalogue_csv"):
                    updated_snapshot = dict(snapshot)
                    updated_snapshot["products"] = import_result.products
                    updated_snapshot["recommendations"] = match_products(
                        snapshot.get("trends") or [], import_result.products
                    )
                    updated_meta = dict(meta)
                    updated_meta.update(
                        {
                            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                            "mode": "hybrid",
                            "catalogue_source": "csv",
                            "catalogue_filename": Path(uploaded_catalogue.name).name,
                            "catalogue_format": import_result.source_format,
                            "catalogue_source_rows": import_result.source_rows,
                            "catalogue_warnings": import_result.warnings,
                            "source_status": {
                                **status,
                                "shopify": f"CSV snapshot · {len(import_result.products):,} products",
                            },
                        }
                    )
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
        st.write("The live Shopify connector reads active products, inventory, prices, tags and images. It does not write to the store.")
        if not settings.shopify_configured:
            st.warning("Add Shopify credentials or switch to Upload CSV.")
        if st.button("Test Shopify API", disabled=not settings.shopify_configured, width="stretch"):
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
                st.error(safe_error(exc, [settings.shopify_client_secret, settings.shopify_admin_access_token]))

    section_header("Connection checks", "Test the three inputs used by trend discovery")
    checks = st.columns(3)
    with checks[0]:
        if st.button("Test publisher pages", width="stretch"):
            try:
                result = CommercialSourceCollector(
                    sources=EDITORIAL_PUBLISHERS,
                    timeout_seconds=settings.commercial_timeout_seconds,
                    max_workers=settings.commercial_max_workers,
                    serpapi_api_key=settings.serpapi_api_key,
                    serpapi_endpoint=settings.serpapi_endpoint,
                ).test_connection()
                st.session_state.editorial_publisher_test = {
                    "ok": bool(result.get("evidence_rows")),
                    "detail": (
                        f"{int(result.get('publishers_live') or 0)} live, "
                        f"{int(result.get('publishers_partial') or 0)} partial, "
                        f"{int(result.get('publishers_failed') or 0)} failed · "
                        f"{int(result.get('named_trends') or 0)} fallback labels."
                    ),
                }
            except Exception as exc:
                st.session_state.editorial_publisher_test = {"ok": False, "detail": safe_error(exc)}
        result = st.session_state.get("editorial_publisher_test")
        if isinstance(result, dict):
            (st.success if result.get("ok") else st.error)(str(result.get("detail")))
        st.caption("Loads each public publisher independently; one blocked site does not stop the others.")
    with checks[1]:
        if st.button("Test OpenAI article extraction", disabled=not settings.openai_configured, width="stretch"):
            try:
                result = OpenAIResponsesConnector(
                    settings.openai_api_key,
                    api_url=settings.openai_api_url,
                    luna_model=settings.openai_luna_model,
                    terra_model=settings.openai_terra_model,
                    sol_model=settings.openai_sol_model,
                    timeout_seconds=settings.openai_timeout_seconds,
                ).test_connection()
                st.session_state.editorial_openai_test = {"ok": True, "detail": f"Connected to {result.get('model')}."}
            except Exception as exc:
                st.session_state.editorial_openai_test = {"ok": False, "detail": safe_error(exc, [settings.openai_api_key])}
        result = st.session_state.get("editorial_openai_test")
        if isinstance(result, dict):
            (st.success if result.get("ok") else st.error)(str(result.get("detail")))
        st.caption("GPT reads bounded recent-article text and returns structured trend candidates.")
    with checks[2]:
        if st.button("Test Google Trends", disabled=not settings.serpapi_configured, width="stretch"):
            try:
                result = GoogleTrendsConnector(
                    geo=settings.google_geo,
                    timeframe=settings.google_discovery_timeframe,
                    category=settings.google_category,
                    anchor_term=settings.google_anchor_term,
                    provider=settings.google_provider,
                    serpapi_api_key=settings.serpapi_api_key,
                    serpapi_endpoint=settings.serpapi_endpoint,
                    serpapi_timeout_seconds=settings.serpapi_timeout_seconds,
                    max_terms=settings.google_max_terms,
                    max_discovery_seeds=0,
                    connect_timeout_seconds=settings.google_connect_timeout_seconds,
                    read_timeout_seconds=settings.google_read_timeout_seconds,
                ).test_connection()
                st.session_state.editorial_google_test = {
                    "ok": True,
                    "detail": f"{int(result.get('points') or 0)} live timeline points from {result.get('market')}.",
                }
            except Exception as exc:
                st.session_state.editorial_google_test = {"ok": False, "detail": safe_error(exc, [settings.serpapi_api_key])}
        result = st.session_state.get("editorial_google_test")
        if isinstance(result, dict):
            (st.success if result.get("ok") else st.error)(str(result.get("detail")))
        st.caption("Measures only publisher-discovered queries; it does not discover extra seed terms.")

    section_header("Live refresh", "Scan articles, extract trends, plot demand and match HULA products")
    include_llm = st.checkbox(
        "Use GPT to scan article text",
        value=settings.openai_configured,
        disabled=not settings.openai_configured,
    )
    include_editorial = st.checkbox(
        "Generate the evidence-locked Wednesday blog after ranking",
        value=settings.openai_configured or settings.gemini_configured,
    )
    catalog_source, catalog_products = catalogue_refresh_args(snapshot)
    refresh_ready = not (
        (catalog_source == "csv" and not catalog_products)
        or (catalog_source == "shopify_api" and not settings.shopify_configured)
    )
    if not refresh_ready:
        st.info("Apply a product CSV or configure Shopify before running the full refresh.")
    refresh_label = (
        "Run editorial-consensus refresh with CSV catalogue"
        if catalog_source == "csv"
        else "Run editorial-consensus refresh + Shopify"
    )
    if st.button(refresh_label, type="primary", disabled=not refresh_ready):
        with st.spinner("Reading recent fashion articles, extracting trends and plotting Google demand…"):
            try:
                st.session_state.snapshot = refresh_snapshot(
                    settings,
                    use_llm=include_llm,
                    persist=True,
                    catalog_source=catalog_source,
                    catalog_products=catalog_products,
                    generate_editorial=include_editorial,
                )
                st.session_state.catalogue_notice = "Editorial-consensus refresh complete."
                st.rerun()
            except Exception as exc:
                st.error(
                    "Refresh stopped safely: "
                    + safe_error(
                        exc,
                        [
                            settings.openai_api_key,
                            settings.serpapi_api_key,
                            settings.supabase_secret_key,
                            settings.shopify_client_secret,
                            settings.shopify_admin_access_token,
                        ],
                    )
                )
    st.caption("The scheduled workflow remains Wednesday at 09:17 Hong Kong time.")

    section_header("Ranking method", "Simple enough to explain in one minute")
    method = st.columns(3)
    method[0].metric("Editorial ranking", "70%")
    method[0].caption("Independent publisher consensus, freshness, repetition and extraction confidence.")
    method[1].metric("Google validation", "30%")
    method[1].caption("Recent interest, week-on-week change, slope and 12-month context.")
    method[2].metric("Social scraping", "0%")
    method[2].caption("X and Instagram are deliberately not queried or required.")
    st.markdown(
        '<div class="method-note"><strong>Within editorial consensus:</strong> 55% independent publisher overlap, 25% freshness, 10% repeated article coverage and 10% extraction confidence. Same-group editions count once. A saved chart is Google’s relative 0–100 interest index, not absolute search volume.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="method-note"><strong>Data minimisation:</strong> article text is transient model input and is not stored. Weekly files keep source metadata and short excerpts only. Shopify is read-only. No customer, order or payment data is accessed.</div>',
        unsafe_allow_html=True,
    )

    section_header("Operations", "Safe diagnostics and optional output checks")
    safe_report = {
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "app_build": APP_BUILD,
        "pipeline_version": DISCOVERY_PIPELINE_VERSION,
        "dataset_mode": meta.get("mode"),
        "dataset_generated_at": meta.get("generated_at"),
        "catalogue_source": meta.get("catalogue_source"),
        "configuration_loaded": {
            "editorial_publishers": True,
            "openai": settings.openai_configured,
            "google_trends": settings.serpapi_configured,
            "shopify_api": settings.shopify_configured,
            "supabase": settings.supabase_configured,
            "gemini_fallback": settings.gemini_configured,
        },
        "editorial_collection": meta.get("editorial_collection") or {},
        "google_trends": meta.get("google_trends") or {},
        "source_status": meta.get("source_status") or {},
        "raw_counts": meta.get("raw_counts") or {},
        "refresh_notes": meta.get("warnings") or [],
        "privacy": "No API keys, tokens, passwords, client secrets or article bodies are included.",
    }
    st.download_button(
        "Download safe diagnostic report",
        data=json.dumps(safe_report, ensure_ascii=False, indent=2),
        file_name="hula-editorial-consensus-diagnostics.json",
        mime="application/json",
        help="Shareable status information only; secret values and article bodies are excluded.",
    )
    output_checks = st.columns(2)
    with output_checks[0]:
        if st.button(
            "Test Supabase history",
            disabled=not settings.supabase_configured,
            width="stretch",
        ):
            try:
                result = SupabaseStore(
                    settings.supabase_url,
                    settings.supabase_secret_key,
                    snapshot_table=settings.supabase_snapshot_table,
                    blog_table=settings.supabase_blog_table,
                ).test_connection()
                st.session_state.editorial_supabase_test = {
                    "ok": True,
                    "detail": (
                        f"Connected to {result.get('snapshot_table')} · "
                        f"{int(result.get('rows_visible') or 0)} row(s) visible."
                    ),
                }
            except Exception as exc:
                st.session_state.editorial_supabase_test = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.supabase_secret_key]),
                }
        result = st.session_state.get("editorial_supabase_test")
        if isinstance(result, dict):
            (st.success if result.get("ok") else st.error)(str(result.get("detail")))
        st.caption("Optional storage for weekly snapshots and published blog history.")
    with output_checks[1]:
        if st.button(
            "Test Gemini fallback",
            disabled=not settings.gemini_configured,
            width="stretch",
        ):
            try:
                result = GeminiResearchConnector(
                    settings.gemini_api_key,
                    model=settings.gemini_model,
                    api_url=settings.gemini_api_url,
                    timeout_seconds=settings.gemini_timeout_seconds,
                    grounding_enabled=False,
                ).test_connection()
                st.session_state.editorial_gemini_test = {
                    "ok": True,
                    "detail": f"Connected successfully to {result.get('model')}.",
                }
            except Exception as exc:
                st.session_state.editorial_gemini_test = {
                    "ok": False,
                    "detail": safe_error(exc, [settings.gemini_api_key]),
                }
        result = st.session_state.get("editorial_gemini_test")
        if isinstance(result, dict):
            (st.success if result.get("ok") else st.error)(str(result.get("detail")))
        st.caption("Optional evidence-locked fallback for the Wednesday writer.")

    usage = list(meta.get("openai_usage") or [])
    if usage:
        section_header("Model usage", "Last OpenAI refresh")
        st.metric(
            "Estimated OpenAI cost",
            f"US${sum(float(row.get('estimated_cost_usd') or 0) for row in usage):.4f}",
        )
        st.dataframe(pd.DataFrame(usage), hide_index=True, width="stretch")
    warnings = list(meta.get("warnings") or [])
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
            [
                "THIS WEEK",
                "EDITORIAL RADAR",
                "PRODUCT MATCH",
                "CAMPAIGN STUDIO",
                "WEDNESDAY BLOG",
                "DATA & SETUP",
            ],
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
            with st.spinner("Reading recent fashion articles, extracting trends and plotting Google demand…"):
                try:
                    st.session_state.snapshot = refresh_snapshot(
                        settings,
                        persist=True,
                        catalog_source=catalog_source,
                        catalog_products=catalog_products,
                        generate_editorial=True,
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
        selected = stored or demo_snapshot()
        if settings.supabase_configured:
            try:
                remote = SupabaseStore(
                    settings.supabase_url,
                    settings.supabase_secret_key,
                    snapshot_table=settings.supabase_snapshot_table,
                    blog_table=settings.supabase_blog_table,
                ).load_latest_snapshot()
                local_at = parse_utc((selected.get("meta") or {}).get("generated_at"))
                remote_at = parse_utc(
                    ((remote or {}).get("meta") or {}).get("generated_at")
                )
                if remote and (
                    local_at is None or (remote_at is not None and remote_at > local_at)
                ):
                    selected = remote
            except Exception as exc:
                st.session_state.snapshot_boot_warning = safe_error(
                    exc,
                    [settings.supabase_secret_key],
                )
        st.session_state.snapshot = guard_legacy_discovery_snapshot(
            upgrade_snapshot_to_v2(sanitize_snapshot_trends(selected))
        )
    snapshot = guard_legacy_discovery_snapshot(
        upgrade_snapshot_to_v2(sanitize_snapshot_trends(st.session_state.snapshot))
    )
    st.session_state.snapshot = snapshot
    page = sidebar(snapshot, settings)
    boot_warning = st.session_state.pop("snapshot_boot_warning", "")
    if boot_warning:
        st.warning(
            "Supabase history could not be loaded at startup; the newest local "
            f"aggregate is displayed. {boot_warning}"
        )
    if page == "THIS WEEK":
        editorial_this_week(snapshot)
    elif page == "EDITORIAL RADAR":
        editorial_trend_radar(snapshot)
    elif page == "PRODUCT MATCH":
        product_match_page(snapshot)
    elif page == "CAMPAIGN STUDIO":
        campaign_studio(snapshot, settings)
    elif page == "WEDNESDAY BLOG":
        weekly_blog(snapshot, settings)
    else:
        editorial_data_setup(snapshot, settings)


if __name__ == "__main__":
    main()
