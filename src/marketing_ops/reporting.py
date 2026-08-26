from __future__ import annotations

import csv
import html
import io
import json
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .decision_engine import evaluate_paid_media, policy_from_mapping
from .metrics import format_hkd
from .metric_dictionary import metric_rows


PINK = colors.HexColor("#FF3F98")
INK = colors.HexColor("#171717")
MIST = colors.HexColor("#F5F3F0")
GREY = colors.HexColor("#66615D")

try:
    pdfmetrics.registerFont(TTFont("HulaSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("HulaSansBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
    FONT = "HulaSans"
    FONT_BOLD = "HulaSansBold"
except Exception:
    FONT = "Helvetica"
    FONT_BOLD = "Helvetica-Bold"


_PDF_TRANSLATION = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2192": "->",
        "\u2026": "...",
        "\u00b7": "-",
    }
)


def _clean(value: Any) -> str:
    return str(value).translate(_PDF_TRANSLATION)


def _paragraph(value: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(html.escape(_clean(value)).replace("\n", "<br/>"), style)


def _wrapped_table(
    rows: list[list[Any]],
    *,
    col_widths: list[float],
    font_size: float = 7.5,
) -> Table:
    header_style = ParagraphStyle(
        "TableHeader",
        fontName=FONT_BOLD,
        fontSize=font_size,
        leading=font_size + 2,
        textColor=colors.white,
    )
    body_style = ParagraphStyle(
        "TableBody",
        fontName=FONT,
        fontSize=font_size,
        leading=font_size + 2,
        textColor=INK,
    )
    wrapped = [
        [_paragraph(cell, header_style if index == 0 else body_style) for cell in row]
        for index, row in enumerate(rows)
    ]
    table = Table(wrapped, repeatRows=1, colWidths=col_widths)
    table.setStyle(_report_table_style(font_size=font_size))
    return table


def _table_rows(rows: Iterable[Mapping[str, Any]], columns: list[str]) -> list[list[str]]:
    return [columns] + [[str(row.get(column, "")) for column in columns] for row in rows]


def monthly_report_pdf(
    dataset: Mapping[str, Any],
    *,
    commentary: str = "",
    approved: bool = False,
    version: str = "Draft 1",
) -> bytes:
    """Generate a structured management PDF from stored records.

    This deliberately does not take screenshots of Streamlit. Fixture/source
    labels are repeated in the document so it cannot be mistaken for live data.
    """
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="HULA Marketing Operations Monthly Report",
        author="HULA Marketing Operations",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="HulaTitle", parent=styles["Title"], fontName=FONT, fontSize=28, leading=31, textColor=INK, alignment=TA_LEFT, spaceAfter=8))
    styles.add(ParagraphStyle(name="HulaH1", parent=styles["Heading1"], fontName=FONT, fontSize=17, leading=21, textColor=INK, spaceBefore=12, spaceAfter=7))
    styles.add(ParagraphStyle(name="HulaH2", parent=styles["Heading2"], fontName=FONT_BOLD, fontSize=10, leading=13, textColor=GREY, spaceBefore=8, spaceAfter=4, uppercase=True))
    styles.add(ParagraphStyle(name="HulaBody", parent=styles["BodyText"], fontName=FONT, fontSize=8.5, leading=12, textColor=INK))
    styles.add(ParagraphStyle(name="HulaNote", parent=styles["BodyText"], fontName=FONT, fontSize=7.5, leading=10, textColor=GREY, backColor=MIST, borderPadding=7))

    story: list[Any] = []
    meta = dataset["meta"]
    executive = dataset["executive"]
    status = "Approved" if approved else "Internal draft — approval required before distribution"
    story.extend(
        [
            _paragraph("HULA Marketing Operations", styles["HulaTitle"]),
            _paragraph(f"Monthly management report - {meta['period']}", styles["HulaH1"]),
            _paragraph(f"{version} - {status}", styles["HulaBody"]),
            Spacer(1, 6),
            _paragraph(f"DATA STATUS: {meta['notice']} Accurate as of {meta['generated_at']}. Currency: HKD. Timezone: Asia/Hong_Kong.", styles["HulaNote"]),
            Spacer(1, 10),
        ]
    )
    headline = [
        ["Shopify GMV", format_hkd(executive["gmv"])],
        ["HULA retained revenue", format_hkd(executive.get("retained_revenue"))],
        ["Contribution", format_hkd(executive.get("contribution"))],
        ["Paid-media spend", format_hkd(executive["paid_spend"], 2)],
        ["Platform paid revenue", format_hkd(executive["platform_paid_revenue"], 2)],
        ["Blended paid ROAS", f"{executive['blended_roas']:.2f}x"],
        ["Channel-chart coverage", f"{executive['channel_chart_coverage_pct']:.2f}%"],
        ["Paid CAC", "Unavailable"],
        ["Spend / all new customers (proxy)", format_hkd(executive["spend_per_all_new_customer"], 2)],
        ["New customers", f"{executive['new_customers']:,}"],
        ["Orders", f"{executive['orders']:,}"],
    ]
    table = Table(headline, colWidths=[75 * mm, 55 * mm])
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), MIST), ("TEXTCOLOR", (0, 0), (-1, -1), INK), ("FONTNAME", (0, 0), (0, -1), FONT_BOLD), ("FONTNAME", (1, 0), (1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D8D4CF")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    story.extend([_paragraph("1. Executive summary", styles["HulaH1"]), table, Spacer(1, 8)])
    if commentary.strip():
        story.append(_paragraph(commentary, styles["HulaBody"]))
    else:
        story.append(_paragraph("Fixture view: July commerce revenue was HK$2.49m, paid-media spend HK$30.4k, and platform-attributed Google/Meta revenue HK$233.9k. Location totals, channel coverage and order allocation require reconciliation before this becomes a trusted baseline.", styles["HulaBody"]))

    story.extend([_paragraph("2. Profitability and paid-media decisions", styles["HulaH1"]), _paragraph("GMV, Shopify net revenue, HULA retained revenue and contribution answer different questions. The current scenario uses a configurable 31% retained margin, payment fees plus shipping at 10% of retained margin, and a separate provisional 10% return provision for platform claims. SCALE and all external actions remain blocked.", styles["HulaNote"])])
    policy = policy_from_mapping(dataset.get("profitability_policy") or {})
    decision_rows = [["Campaign", "Decision", "Window", "Platform ROAS", "Purchases", "Contribution ROAS", "Break-even platform", "Confidence"]]
    for card in dataset.get("paid_media_recommendations") or []:
        selected = next(row for row in card["windows"] if row["days"] == card["selected_days"])
        result = evaluate_paid_media(
            attributed_gmv=float(selected["attributed_gmv"]),
            spend=float(selected["spend"]),
            purchases=int(selected["purchases"]),
            order_values=card["order_values"],
            median_order_value=card.get("median_order_value"),
            inventory_available=card.get("inventory_available"),
            channel=card["channel"],
            policy=policy,
        )
        ratio = lambda value: "-" if value is None else f"{value:.2f}x"
        decision_rows.append([card["campaign"], result.decision, f"{card['selected_days']} days", ratio(result.platform_roas), str(selected["purchases"]), ratio(result.contribution_roas), ratio(result.break_even_gmv_roas), result.confidence])
    story.extend([Spacer(1, 6), _wrapped_table(decision_rows, col_widths=[40 * mm, 18 * mm, 15 * mm, 21 * mm, 15 * mm, 21 * mm, 25 * mm, 17 * mm], font_size=5.8)])
    story.append(_paragraph("Claim excess is unavailable until paid-platform claims and actual Shopify orders use the same dates, eligibility and channel scope. Klaviyo remains separate from paid acquisition.", styles["HulaNote"]))

    story.append(PageBreak())
    story.extend([_paragraph("3. Shopify revenue and customers", styles["HulaH1"]), _paragraph("Shopify/Report Pundit commerce is the source of truth. Platform and analytics attribution are shown separately and must not be added together.", styles["HulaBody"])])
    store_data = [["Location", "Orders", "Revenue", "MoM"]] + [[row["location"], f"{row['orders']:,}", format_hkd(row["revenue"], 2), f"{row['mom_pct']:+.1f}%"] for row in dataset["stores"]]
    store_table = _wrapped_table(store_data, col_widths=[50 * mm, 25 * mm, 45 * mm, 25 * mm])
    story.extend([Spacer(1, 6), store_table, _paragraph("Customer view: 167 new customers and 176 repeat buyers in the agency fixture. The displayed HK$182 is paid spend divided by all 167 new customers, including in-store and potentially organic customers, so it is an efficiency proxy rather than paid CAC.", styles["HulaNote"])])

    story.extend([_paragraph("4. Google Ads", styles["HulaH1"]), _paragraph("Google Ads platform attribution - read-only operating view", styles["HulaNote"])])
    google_rows = [["Campaign", "Spend", "Purchases", "Value", "ROAS", "Pacing"]] + [[row["campaign"], format_hkd(row["spend"]), str(row["purchases"]), format_hkd(row["purchase_value"]), f"{row['roas']:.2f}x", f"{row['budget_pacing_pct']}%"] for row in dataset["google_campaigns"]]
    google_table = _wrapped_table(google_rows, col_widths=[55 * mm, 23 * mm, 18 * mm, 29 * mm, 18 * mm, 18 * mm], font_size=6.8)
    story.extend([google_table, _paragraph("No budget, bidding, conversion, keyword, or status change is executed by this report.", styles["HulaNote"])])

    story.extend([_paragraph("5. Organic search and SEO", styles["HulaH1"]), _paragraph("Priorities use a transparent weighted score; no keyword volume is invented.", styles["HulaBody"])])
    seo_rows = [["Query", "Page", "Impr.", "CTR", "Pos.", "Score"]] + [[row["query"], row["page"], f"{row['impressions']:,}", f"{row['ctr']:.2f}%", f"{row['position']:.1f}", f"{row['score']:.1f}"] for row in dataset["seo_opportunities"]]
    seo_table = _wrapped_table(seo_rows, col_widths=[35 * mm, 64 * mm, 22 * mm, 17 * mm, 15 * mm, 18 * mm], font_size=6.2)
    story.append(seo_table)

    story.extend([_paragraph("6. AI referral traffic", styles["HulaH1"]), _paragraph("Only observable referral and onsite behavior is measured; the platform cannot see private prompts or know why an assistant cited HULA.", styles["HulaNote"])])
    ai_rows = [["Source", "Sessions", "Engagement", "Product views", "ATC", "Purchases", "Revenue"]] + [[row["source"], str(row["sessions"]), f"{row['engagement_rate']:.1f}%", str(row["product_views"]), str(row["add_to_carts"]), str(row["purchases"]), format_hkd(row["revenue"])] for row in dataset["ai_referrals"]]
    ai_table = _wrapped_table(ai_rows, col_widths=[24 * mm, 20 * mm, 24 * mm, 26 * mm, 14 * mm, 19 * mm, 27 * mm], font_size=7)
    story.extend([ai_table, PageBreak()])

    story.extend([_paragraph("7. Google Business Profile", styles["HulaH1"])])
    gbp_rows = [["Location", "Views", "Clicks", "Calls", "Directions", "Rating", "Unanswered"]] + [[row["location"], f"{row['views']:,}", f"{row['website_clicks']:,}", str(row["calls"]), f"{row['directions']:,}", f"{row['rating']:.1f}", str(row["unanswered"])] for row in dataset["gbp"]]
    gbp_table = _wrapped_table(gbp_rows, col_widths=[27 * mm, 23 * mm, 22 * mm, 18 * mm, 25 * mm, 18 * mm, 25 * mm], font_size=7)
    story.append(gbp_table)

    story.extend([_paragraph("8. Meta Ads", styles["HulaH1"]), _paragraph("Meta platform attribution - the supplied report states a seven-day window; click/view mix still needs confirmation", styles["HulaNote"])])
    meta_rows = [["Campaign", "Spend", "Frequency", "CTR", "Purchases", "Value", "ROAS"]] + [[row["campaign"], format_hkd(row["spend"]), f"{row['frequency']:.2f}", f"{row['ctr']:.2f}%", str(row["purchases"]), format_hkd(row["purchase_value"]), f"{row['roas']:.2f}x"] for row in dataset["meta_campaigns"]]
    meta_table = _wrapped_table(meta_rows, col_widths=[47 * mm, 25 * mm, 22 * mm, 18 * mm, 21 * mm, 26 * mm, 18 * mm], font_size=7)
    story.append(meta_table)

    story.extend([_paragraph("9. Klaviyo", styles["HulaH1"]), _paragraph("Klaviyo platform-attributed values; the supplied report states a 90-day attribution window. Verify the current account setting. These values can overlap paid and direct revenue.", styles["HulaNote"])])
    klaviyo_rows = [["Campaign / flow", "Type", "Recipients", "Open", "Click", "Orders", "Revenue"]] + [[row["name"], row["type"], f"{row['recipients']:,}", f"{row['open_rate']:.1f}%", f"{row['click_rate']:.1f}%", str(row["orders"]), format_hkd(row["revenue"])] for row in dataset["klaviyo"]]
    klaviyo_table = _wrapped_table(klaviyo_rows, col_widths=[47 * mm, 25 * mm, 22 * mm, 18 * mm, 18 * mm, 17 * mm, 29 * mm], font_size=6.7)
    story.extend([klaviyo_table, PageBreak()])

    story.extend([_paragraph("10-14. Opportunities, completed work, risks, and actions", styles["HulaH1"]), _paragraph("The first priorities are to resolve data reconciliation, close the highest-impression SEO click-through gaps, refresh fatigued paid creative, and verify unavailable-product promotion. Each item must be converted to an owned task with evidence and a measurement date.", styles["HulaBody"])])
    action_rows = [["Action", "Owner", "Due", "Status"]] + [[row["title"], row["owner"], row["due"], row["status"]] for row in dataset["report_actions"]]
    action_table = _wrapped_table(action_rows, col_widths=[80 * mm, 40 * mm, 28 * mm, 30 * mm], font_size=7.2)
    story.extend([Spacer(1, 6), action_table])

    story.extend([_paragraph("15. Data-quality appendix", styles["HulaH1"])])
    finding_rows = [["Severity", "Finding", "Evidence", "Required fix"]] + [[row["severity"], row["finding"], row["evidence"], row["required_fix"]] for row in dataset.get("data_quality_findings") or []]
    finding_table = _wrapped_table(finding_rows, col_widths=[20 * mm, 42 * mm, 58 * mm, 58 * mm], font_size=5.9)
    story.extend([finding_table, Spacer(1, 7)])
    def numeric(value: Any) -> str:
        if value is None:
            return "-"
        return f"{float(value):,.3f}".rstrip("0").rstrip(".")
    reconciliation_rows = [["Metric", "Agency", "Platform", "Difference", "Status"]] + [[row["Metric"], numeric(row["Agency report"]), numeric(row["New platform"]), numeric(row["Absolute difference"]), row["Status"]] for row in dataset["reconciliation"]]
    reconciliation_table = _wrapped_table(reconciliation_rows, col_widths=[54 * mm, 31 * mm, 31 * mm, 31 * mm, 31 * mm], font_size=6.6)
    story.extend([reconciliation_table, _paragraph("This document separates Shopify booked revenue, platform-attributed revenue, and analytics event incidence. They overlap and are never added as if mutually exclusive. The report provides no supported 347-checkout count or complete session-to-purchase funnel.", styles["HulaNote"]), _paragraph(f"Generated {datetime.now(timezone.utc).isoformat()} - {status}", styles["HulaBody"])])

    document.build(story, onFirstPage=_page_decor, onLaterPages=_page_decor)
    return buffer.getvalue()


def _report_table_style(font_size: float = 7.5) -> TableStyle:
    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), INK),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), FONT),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D8D4CF")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, MIST]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )


def _page_decor(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setStrokeColor(PINK)
    canvas.setLineWidth(3)
    canvas.line(17 * mm, A4[1] - 10 * mm, 50 * mm, A4[1] - 10 * mm)
    canvas.setFont(FONT, 7)
    canvas.setFillColor(GREY)
    canvas.drawRightString(A4[0] - 17 * mm, 9 * mm, f"HULA Marketing Operations - {document.page}")
    canvas.restoreState()


def csv_export_bundle(dataset: Mapping[str, Any]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in (
            "stores",
            "session_behaviour",
            "channel_revenue",
            "data_quality_findings",
            "customer_segments",
            "google_campaigns",
            "meta_campaigns",
            "seo_opportunities",
            "technical_issues",
            "catalogue_issues",
            "klaviyo",
            "gbp",
            "merchant",
            "ai_referrals",
            "reconciliation",
            "business_rule_register",
            "attribution_claims",
            "automation_boundaries",
            "access_readiness",
            "ownership_checklist",
        ):
            rows = dataset.get(name) or []
            if not rows:
                continue
            text_buffer = io.StringIO()
            fieldnames = sorted({str(key) for row in rows for key in row.keys() if not isinstance(row.get(key), (dict, list, tuple))})
            writer = csv.DictWriter(text_buffer, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            archive.writestr(f"{name}.csv", text_buffer.getvalue().encode("utf-8-sig"))
        definitions = metric_rows()
        definition_buffer = io.StringIO()
        definition_writer = csv.DictWriter(definition_buffer, fieldnames=list(definitions[0]))
        definition_writer.writeheader()
        definition_writer.writerows(definitions)
        archive.writestr("metric_dictionary.csv", definition_buffer.getvalue().encode("utf-8-sig"))
        archive.writestr("online_summary.json", json.dumps(dataset.get("online_summary") or {}, indent=2, ensure_ascii=False))
        archive.writestr("profitability_policy.json", json.dumps(dataset.get("profitability_policy") or {}, indent=2, ensure_ascii=False))
        archive.writestr("paid_media_recommendations.json", json.dumps(dataset.get("paid_media_recommendations") or [], indent=2, ensure_ascii=False))
        archive.writestr("metadata.json", json.dumps(dataset.get("meta") or {}, indent=2, ensure_ascii=False))
        archive.writestr("README.txt", "HULA Marketing Operations fixture export. Values are not live. Attribution sources overlap and must not be summed. Analytics event incidence and the Shopify Online Store summary are separate source views; no complete checkout funnel is claimed.\n")
    return buffer.getvalue()
