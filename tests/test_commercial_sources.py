from __future__ import annotations

from datetime import datetime, timezone

from src.connectors.commercial_sources import (
    _page_metadata,
    extract_explicit_trend_labels,
    parse_page,
    score_commercial_evidence,
)


def test_article_title_and_trend_headings_are_used_but_body_is_ignored() -> None:
    html = """
    <html>
      <head><title>5 Summer Fashion Trends to Know</title></head>
      <body>
        <h1>5 Summer Fashion Trends to Know</h1>
        <h2>1. Pencil Skirt</h2>
        <h2>2. Polka Dots</h2>
        <h2>3. Pants</h2>
        <p>Ballet flats and barrel jeans appear in ordinary body copy.</p>
      </body>
    </html>
    """
    page = parse_page(html)
    labels = extract_explicit_trend_labels(
        title=page.title,
        headings=page.headings,
    )
    names = {row["trend_name"] for row in labels}
    assert names == {"Pencil Skirt", "Polka Dots"}
    assert "Ballet Flats" not in names
    assert "Barrel Jeans" not in names


def test_full_browser_title_precedes_shorter_h1_without_metadata() -> None:
    page = parse_page(
        """
        <html><head><title>Pre-Fall Report: Studded Ballet Flats Trend</title></head>
        <body><h1>Pre-Fall Report</h1></body></html>
        """
    )
    metadata = _page_metadata(page, "https://example.com/report")
    assert metadata["title"] == "Pre-Fall Report: Studded Ballet Flats Trend"
    labels = extract_explicit_trend_labels(
        title=metadata["title"],
        headings=page.headings,
    )
    assert labels[0]["trend_name"] == "Ballet Flats"


def test_vague_editorial_adjective_cannot_rescue_a_department_noun() -> None:
    labels = extract_explicit_trend_labels(
        title="The Pretty Dress Trend Is Everywhere",
        headings=(),
    )
    assert labels == []

    specific = extract_explicit_trend_labels(
        title="The Puff-Sleeve Trend Is Everywhere",
        headings=(),
    )
    assert specific[0]["trend_name"] == "Puff Sleeve"


def test_commercial_score_counts_unique_publishers_and_keeps_exact_pages() -> None:
    now = datetime(2026, 8, 3, tzinfo=timezone.utc)
    evidence = [
        {
            "trend_name": "Ballet Flats",
            "explicit_label": "Studded Ballet Flats",
            "publisher": "Who What Wear",
            "publisher_id": "whowhatwear",
            "publisher_weight": 2,
            "article_title": "The Ballet-Flat Trend Taking Over Europe",
            "published_at": "2026-08-01T00:00:00+00:00",
            "url": "https://example.com/one",
            "evidence_kind": "article title",
        },
        {
            "trend_name": "Ballet Flats",
            "explicit_label": "Suede Ballet Flats",
            "publisher": "Vogue",
            "publisher_id": "vogue",
            "publisher_weight": 2,
            "article_title": "The Key Shoe Trends",
            "published_at": "2026-07-25T00:00:00+00:00",
            "url": "https://example.com/two",
            "evidence_kind": "trend-labelled heading",
        },
    ]
    rows = score_commercial_evidence(evidence, now=now)
    assert rows[0]["name"] == "Ballet Flats"
    assert rows[0]["publisher_count"] == 2
    assert rows[0]["article_count"] == 2
    assert {row["url"] for row in rows[0]["commercial_evidence"]} == {
        "https://example.com/one",
        "https://example.com/two",
    }


def test_trusted_taxonomy_allows_material_but_not_department_noun() -> None:
    labels = extract_explicit_trend_labels(
        title="Tagwalk Trends",
        headings=(),
        taxonomy_text=("suede", "pants", "polka", "colour block"),
    )
    names = {row["trend_name"] for row in labels}
    assert "Suede" in names
    assert "Colour Block" in names
    assert "Pants" not in names
    assert "Polka" not in names
