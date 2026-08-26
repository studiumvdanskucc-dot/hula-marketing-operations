from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "apps" / "marketing_operations.py"


PAGES = [
    "Overview",
    "Work",
    "Performance",
    "Settings",
]


def navigation(app: AppTest):
    return next(item for item in app.radio if item.label == "Navigation")


def subnav(app: AppTest, label: str):
    return next(item for item in app.radio if item.label == label)


def test_all_marketing_pages_render_without_credentials(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_DEFAULT_ROLE", "Administrator")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "marketing.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    assert not app.exception
    for page in PAGES:
        navigation(app).set_value(page).run()
        assert not app.exception, page


def test_every_consolidated_subview_renders(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_DEFAULT_ROLE", "Administrator")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "marketing.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    groups = {
        "Work": ("Work view", ["Actions", "Campaigns", "Content & SEO"]),
        "Performance": ("Performance view", ["Business truth", "Paid media", "Email & local", "Customers & discovery", "Data quality"]),
        "Settings": ("Settings view", ["Connections", "Metric definitions", "Reports", "Governance"]),
    }
    for page, (label, views) in groups.items():
        navigation(app).set_value(page).run()
        for view in views:
            subnav(app, label).set_value(view).run()
            assert not app.exception, f"{page} / {view}"
    navigation(app).set_value("Work").run()
    subnav(app, "Work view").set_value("Content & SEO").run()
    for view in ["SEO opportunities", "Content studio", "Site & catalogue", "Trend handoff"]:
        subnav(app, "Content & SEO view").set_value(view).run()
        assert not app.exception, f"Work / Content & SEO / {view}"


def test_reports_and_integrations_expose_honest_controls(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_DEFAULT_ROLE", "Administrator")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "marketing.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    navigation(app).set_value("Settings").run()
    subnav(app, "Settings view").set_value("Reports").run()
    downloads = {button.label for button in app.get("download_button")}
    assert "Download management PDF" in downloads
    assert "Download governed source tables" in downloads
    subnav(app, "Settings view").set_value("Connections").run()
    assert any("External publishing, sending and budget changes are OFF" in item.value for item in app.success)
    frames = app.get("dataframe")
    assert frames


def test_performance_keeps_source_views_separate(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_DEFAULT_ROLE", "Administrator")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "marketing.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    navigation(app).set_value("Performance").run()
    markdown = " ".join(item.value for item in app.markdown)
    assert "Checkout count" in markdown or any(metric.label == "Checkout count" for metric in app.metric)
    assert "98,280" not in markdown
    assert "347" not in markdown
    subnav(app, "Performance view").set_value("Data quality").run()
    assert app.get("dataframe")


def test_paid_media_decision_card_exposes_evidence_and_fail_closed_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_DEFAULT_ROLE", "Administrator")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "decisions.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    navigation(app).set_value("Performance").run()
    subnav(app, "Performance view").set_value("Paid media").run()
    assert not app.exception
    copy = " ".join(item.value for item in app.markdown)
    assert "Recommendation: REVIEW" in copy
    assert "Purchases behind result" in copy
    assert "Large-order dependency" in copy
    assert "Inventory check" in copy
    assert "7d" in copy and "14d" in copy and "28d" in copy and "56d" in copy
    assert "Claim excess indicator" in copy


def test_governance_shows_questionnaire_owners_caps_and_automation_boundary(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_DEFAULT_ROLE", "Administrator")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "governance.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    navigation(app).set_value("Settings").run()
    subnav(app, "Settings view").set_value("Governance").run()
    assert not app.exception
    copy = " ".join(item.value for item in app.markdown)
    assert "Business rule register" in copy
    assert "Google monthly cap" in copy
    assert "3 of 3" in copy
    assert "Automation boundary" in copy
    assert "Ownership and exit readiness" in copy


def test_viewer_gets_one_read_only_overview(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_DEFAULT_ROLE", "Viewer")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "viewer.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    assert not app.exception
    assert not any(item.label == "Navigation" for item in app.radio)
    copy = " ".join(item.value for item in app.markdown)
    assert "HULA performance at a glance" in copy
    captions = " ".join(item.value for item in app.caption)
    assert "read-only" in captions.lower()
    assert not app.button


def test_collapsed_sidebar_keeps_reopen_control_visible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_DEFAULT_ROLE", "Administrator")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "sidebar.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    assert not app.exception
    styles = " ".join(item.value for item in app.markdown if "stExpandSidebarButton" in item.value)
    assert '[data-testid="stExpandSidebarButton"]' in styles
    assert "visibility:visible !important" in styles
    assert '[data-testid="stToolbar"]' in styles
