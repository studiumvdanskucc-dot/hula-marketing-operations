from __future__ import annotations

from datetime import datetime, timezone

from src.connectors.commercial_sources import (
    COMMERCIAL_SOURCES,
    CommercialSourceCollector,
    _page_metadata,
    _source_headings,
    extract_explicit_trend_labels,
    parse_feed_entries,
    parse_page,
    parse_sitemap,
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


def test_whowhatwear_adapter_uses_editorial_sections_not_product_cards() -> None:
    source = next(row for row in COMMERCIAL_SOURCES if row.key == "whowhatwear")
    page = parse_page(
        """
        <html><head><title>17 Fall 2026 Trends to Know</title></head><body>
        <h3 class="article-body__section">Croc-Effect Bags</h3>
        <h3 class="article-body__section">Tapestry Designs</h3>
        <h3 class="product-card">Example Brand Handbag</h3>
        </body></html>
        """
    )
    headings = _source_headings(source, page, "https://www.whowhatwear.com/fashion/trends/example")
    labels = extract_explicit_trend_labels(title=page.title, headings=headings)
    assert {row["trend_name"] for row in labels} == {
        "Croc Effect Bags",
        "Tapestry Designs",
    }


def test_vogue_adapter_keeps_h2_trends_and_rejects_h3_product_names() -> None:
    source = next(row for row in COMMERCIAL_SOURCES if row.key == "vogue")
    page = parse_page(
        """
        <html><head><title>Top Fall 2026 Shoe Trends</title></head><body>
        <h2>The Kitten Heel</h2>
        <h3 class="UnifiedProductCardName">Example 95 Pumps</h3>
        <h2>The T-strap</h2>
        </body></html>
        """
    )
    headings = _source_headings(source, page, "https://www.vogue.com/article/fall-2026-shoe-trends")
    assert headings == ["The Kitten Heel", "The T-strap"]


def test_publisher_feed_and_news_sitemap_are_parsed() -> None:
    feed = parse_feed_entries(
        """<rss><channel><item><title>Five Denim Trends</title>
        <link>https://publisher.example/denim</link>
        <pubDate>Mon, 03 Aug 2026 16:06:04 GMT</pubDate></item></channel></rss>"""
    )
    assert feed[0]["url"] == "https://publisher.example/denim"
    entries, children = parse_sitemap(
        """<urlset xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
        <url><loc>https://publisher.example/report</loc><news:news>
        <news:publication_date>2026-08-03</news:publication_date>
        <news:title>Current Fashion Trends</news:title></news:news></url></urlset>"""
    )
    assert children == []
    assert entries == [
        {
            "url": "https://publisher.example/report",
            "title": "Current Fashion Trends",
            "published_at": "2026-08-03",
        }
    ]


def test_configured_current_report_cannot_be_pushed_out_by_sitemap_noise() -> None:
    source = next(row for row in COMMERCIAL_SOURCES if row.key == "whowhatwear")
    ranked = CommercialSourceCollector._rank_candidates(
        source,
        [
            {
                "title": "editor favorite fall trends 2026",
                "url": source.article_urls[0],
                "published_at": "",
                "acquisition": "configured publisher report",
            },
            *[
                {
                    "title": f"Fashion Week Runway Trends Report {index}",
                    "url": f"https://www.whowhatwear.com/fashion/runway/report-{index}",
                    "published_at": f"2026-08-{index + 1:02d}",
                    "acquisition": "publisher sitemap",
                }
                for index in range(25)
            ],
        ],
    )
    assert ranked[0]["url"] == source.article_urls[0]
