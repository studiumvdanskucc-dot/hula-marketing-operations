from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.config import Settings
from src.connectors.catalog_csv import CatalogCsvError, parse_product_csv
from src.pipeline import refresh_snapshot
from src.storage import save_snapshot


def test_shopify_export_collapses_variants_and_sums_inventory() -> None:
    payload = b'''Handle,Title,Body (HTML),Vendor,Type,Tags,Published,Variant SKU,Variant Inventory Qty,Variant Price,Image Src,Image Alt Text,Status
east-west-bag,East-West Bag,"<p>Soft <strong>leather</strong> bag.</p>",Chanel,Bag,"black, shoulder bag",TRUE,WB1,1,12000,https://example.com/bag.jpg,Black bag,active
east-west-bag,,,,,,,WB2,2,12500,,,
silk-dress,Silk Dress,Printed dress,Prada,Dress,"silk, print",TRUE,WD1,0,5400,https://example.com/dress.jpg,Silk dress,active
'''

    result = parse_product_csv(payload)

    assert result.source_format == "Shopify product export"
    assert result.source_rows == 3
    assert len(result.products) == 2
    bag = result.products[0]
    assert bag["title"] == "East-West Bag"
    assert bag["inventory"] == 3
    assert bag["price"] == 12000
    assert bag["description"] == "Soft leather bag."
    assert bag["tags"] == ["black", "shoulder bag"]
    assert bag["image_url"] == "https://example.com/bag.jpg"
    assert bag["status"] == "ACTIVE"


def test_simple_csv_accepts_friendly_headers_and_defaults_missing_inventory() -> None:
    payload = b'''Product Name,Brand,Category,Price,Currency,Keywords,Image URL
Charm Belt,Chanel,Accessories,"HK$ 8,800",HKD,"gold; chain; charm",https://example.com/belt.jpg
Raffia Tote,Loewe,Bag,4200,HKD,"raffia, summer",https://example.com/tote.jpg
'''

    result = parse_product_csv(payload)

    assert result.source_format == "standard product CSV"
    assert len(result.products) == 2
    assert result.products[0]["inventory"] == 1
    assert result.products[0]["price"] == 8800
    assert result.products[0]["status"] == "ACTIVE"
    assert result.products[0]["tags"] == ["gold", "chain", "charm"]
    assert any("Inventory was missing" in warning for warning in result.warnings)


def test_hula_shopify_export_prefers_designer_metafield_and_parses_epoch_date() -> None:
    payload = b'''Handle,Title,Vendor,Type,Variant Price,Image Src,Status,CreatedAt (product.metafields.custom.createdat),Brand (product.metafields.wk_custom_field.brand)
toteme-top,[WW58076] Toteme | Sleeveless Top,nataliesj92,Sleeveless Top,700,https://example.com/top.jpg,active,'1783567690,Toteme
'''

    result = parse_product_csv(payload)

    assert result.products[0]["vendor"] == "Toteme"
    assert result.products[0]["created_at"] == "2026-07-09T03:28:10+00:00"
    assert not any("created-date" in warning for warning in result.warnings)


def test_csv_requires_a_title_or_shopify_handle() -> None:
    with pytest.raises(CatalogCsvError, match="title or Shopify Handle"):
        parse_product_csv(b"sku,price\nWA1,1000\n")


def test_csv_rejects_payloads_above_configured_upload_limit(monkeypatch) -> None:
    monkeypatch.setattr("src.connectors.catalog_csv.MAX_CSV_SIZE_BYTES", 8)

    with pytest.raises(CatalogCsvError, match="smaller than 150 MB"):
        parse_product_csv(b"123456789")


def test_csv_row_limit_can_handle_large_export_guard() -> None:
    payload = b"title,price\nBag 1,100\nBag 2,200\n"

    with pytest.raises(CatalogCsvError, match="safety limit is 1"):
        parse_product_csv(payload, max_rows=1)


def test_weekly_refresh_keeps_the_persisted_csv_catalogue(tmp_path, monkeypatch) -> None:
    snapshot_path = tmp_path / "latest.json"
    csv_product = {
        "id": "csv:test-bag",
        "title": "Test Bag",
        "status": "ACTIVE",
        "inventory": 1,
        "tags": ["east west bag"],
        "is_demo": False,
    }
    save_snapshot(
        {
            "meta": {
                "generated_at": "2026-07-21T00:00:00+00:00",
                "catalogue_source": "csv",
                "catalogue_filename": "products.csv",
                "catalogue_warnings": [],
            },
            "products": [csv_product],
            "trends": [],
            "recommendations": [],
        },
        snapshot_path,
        archive=False,
    )
    monkeypatch.setattr(
        "src.pipeline.GoogleTrendsConnector.collect",
        lambda self, terms, discovery_seeds=None: {
            "series": {},
            "related": [],
            "warnings": [],
            "provider": "offline test",
            "usage_usd": None,
            "attempts": [],
        },
    )
    settings = Settings(
        snapshot_path=str(snapshot_path),
        enable_google_related_queries=False,
    )

    refreshed = refresh_snapshot(settings, persist=False, catalog_source="auto")

    assert refreshed["meta"]["catalogue_source"] == "csv"
    assert refreshed["meta"]["catalogue_filename"] == "products.csv"
    assert refreshed["products"] == [csv_product]
    assert refreshed["meta"]["source_status"]["shopify"].startswith(
        "LIVE · CSV snapshot"
    )


def test_repeated_refresh_reuses_fresh_google_cache(tmp_path, monkeypatch) -> None:
    snapshot_path = tmp_path / "latest.json"
    dates = [
        (datetime.now(tz=timezone.utc) - timedelta(weeks=2 - index)).date().isoformat()
        for index in range(3)
    ]
    save_snapshot(
        {
            "meta": {
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                "catalogue_source": "csv",
                "catalogue_filename": "products.csv",
                "catalogue_warnings": [],
            },
                "google_cache": {
                    "schema_version": "3.0",
                    "collected_at": datetime.now(tz=timezone.utc).isoformat(),
                "market": "WORLDWIDE",
                "context_timeframe": "today 1-m",
                "discovery_timeframe": "now 7-d",
                "provider": "SerpApi Google Trends",
                "context_series": {
                    "black bags": [
                        {"date": date, "value": value}
                        for date, value in zip(dates, (20, 35, 60))
                    ]
                },
                "recent_series": {},
                "related": [],
            },
            "products": [
                {
                    "id": "csv:black-bag",
                    "title": "Black Bag",
                    "status": "ACTIVE",
                    "inventory": 1,
                    "tags": ["black bags"],
                }
            ],
            "trends": [],
            "recommendations": [],
        },
        snapshot_path,
        archive=False,
    )

    def should_not_run(*args, **kwargs):
        raise AssertionError("Fresh Google cache should avoid another Actor run")

    monkeypatch.setattr("src.pipeline.GoogleTrendsConnector.collect", should_not_run)
    settings = Settings(
        snapshot_path=str(snapshot_path),
        enable_google_related_queries=False,
        google_cache_hours=24,
        serpapi_api_key="test-key",
    )

    refreshed = refresh_snapshot(settings, persist=False, catalog_source="auto")

    assert refreshed["meta"]["source_status"]["google_trends"].startswith("LIVE")
    assert refreshed["meta"]["google_trends"]["used_cache"] is True
    assert refreshed["google_cache"]["context_series"]["black bags"]
