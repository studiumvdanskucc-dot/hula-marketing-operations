from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.mark.parametrize(
    "page",
    [
        "THIS WEEK",
        "EDITORIAL RADAR",
        "PRODUCT MATCH",
        "CAMPAIGN STUDIO",
        "WEDNESDAY BLOG",
        "DATA & SETUP",
    ],
)
def test_each_dashboard_page_renders(page: str) -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.radio[0].set_value(page).run()
    assert not app.exception


def test_csv_catalogue_route_renders() -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.radio[0].set_value("DATA & SETUP").run()
    app.radio[0].set_value("Upload CSV").run()
    assert not app.exception
    assert len(app.get("file_uploader")) >= 1


def test_csv_import_button_saves_without_widget_state_exception(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SNAPSHOT_PATH", str(tmp_path / "latest_snapshot.json"))
    payload = b'''Handle,Title,Vendor,Type,Variant Price,Image Src,Status,CreatedAt (product.metafields.custom.createdat),Brand (product.metafields.wk_custom_field.brand)
toteme-top,[WW58076] Toteme | Sleeveless Top,nataliesj92,Sleeveless Top,700,https://example.com/top.jpg,active,'1783567690,Toteme
'''
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.radio[0].set_value("DATA & SETUP").run()
    app.radio[0].set_value("Upload CSV").run()
    app.get("file_uploader")[0].upload("products_export.csv", payload, "text/csv").run()

    next(button for button in app.button if button.label == "Use this CSV catalogue").click().run()

    assert not app.exception
    assert len(app.session_state["snapshot"]["products"]) == 1
    assert app.session_state["snapshot"]["products"][0]["vendor"] == "Toteme"
    assert any("1 products imported" in success.value for success in app.success)


def test_catalogue_widget_state_is_never_assigned_directly() -> None:
    """Widget-owned state must only be changed by the radio widget itself."""
    app_source = APP_PATH.read_text(encoding="utf-8")
    assert "catalogue_source_choice" not in app_source
    tree = ast.parse(app_source)
    forbidden_assignments = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute)
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "st"
                and target.value.attr == "session_state"
                and isinstance(target.slice, ast.Name)
                and target.slice.id == "CATALOGUE_SELECTOR_KEY"
            ):
                forbidden_assignments.append(target.lineno)

    assert forbidden_assignments == []


def test_editorial_consensus_build_is_visible_in_sidebar() -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert any("Build 2026.08.06.4" in caption.value for caption in app.sidebar.caption)


def test_pre_repair_snapshot_is_marked_stale_until_full_refresh(
    tmp_path, monkeypatch
) -> None:
    snapshot_path = tmp_path / "pre-repair.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "meta": {
                    "generated_at": "2026-08-05T00:00:00+00:00",
                    "mode": "live",
                    "discovery_pipeline_version": "3.0",
                },
                "trends": [
                    {
                        "id": "legacy-trend",
                        "name": "Legacy Trend",
                        "decision_ready": True,
                    }
                ],
                "products": [],
                "recommendations": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SNAPSHOT_PATH", str(snapshot_path))
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()

    assert not app.exception
    assert any("DATASET · STALE" in caption.value for caption in app.sidebar.caption)
    assert app.session_state["snapshot"]["meta"]["discovery_refresh_required"] is True
    assert all(
        trend.get("decision_ready") is False
        for trend in app.session_state["snapshot"]["trends"]
    )


def test_data_setup_shows_safe_diagnostics() -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.radio[0].set_value("DATA & SETUP").run()
    assert not app.exception
    assert any(
        button.label == "Download safe diagnostic report" for button in app.get("download_button")
    )
    labels = {button.label for button in app.button}
    assert "Test publisher pages" in labels
    assert "Test OpenAI article extraction" in labels
    assert "Test Google Trends" in labels
    assert "Check active HULA runs" not in labels
    assert "Stop active HULA runs" not in labels
    assert "Test hashtag Actor" not in labels
    assert "Test Apify task" not in labels
    assert "Test Supabase history" in labels
    assert "Test Gemini fallback" in labels
