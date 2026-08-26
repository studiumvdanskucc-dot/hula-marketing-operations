from __future__ import annotations

import io
import zipfile

from src.marketing_ops.demo_data import demo_dataset
from src.marketing_ops.reporting import csv_export_bundle, monthly_report_pdf


def test_structured_pdf_generates_without_screenshot() -> None:
    pdf = monthly_report_pdf(demo_dataset(), commentary="Fixture commentary", approved=False, version="Test")
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 10_000


def test_csv_bundle_contains_governed_tables_and_notice() -> None:
    payload = csv_export_bundle(demo_dataset())
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = set(archive.namelist())
        assert "reconciliation.csv" in names
        assert "google_campaigns.csv" in names
        assert "business_rule_register.csv" in names
        assert "access_readiness.csv" in names
        assert "profitability_policy.json" in names
        assert "paid_media_recommendations.json" in names
        assert "metadata.json" in names
        assert "fixture" in archive.read("README.txt").decode().lower()
