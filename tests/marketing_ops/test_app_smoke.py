from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[2] / "apps" / "marketing_operations.py"


PAGES = [
    "⌂  Home",
    "◉  Campaigns",
    "✦  Content & SEO",
    "↗  Performance",
    "⚙  Settings",
]


def navigation(app: AppTest):
    return next(item for item in app.radio if item.label == "Navigation")


def subnav(app: AppTest, label: str):
    return next(item for item in app.radio if item.label == label)


def test_all_marketing_pages_render_without_credentials(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "marketing.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    assert not app.exception
    for page in PAGES:
        navigation(app).set_value(page).run()
        assert not app.exception, page


def test_every_consolidated_subview_renders(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "marketing.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    groups = {
        "◉  Campaigns": ("Campaign view", ["Workroom", "New campaign", "Approvals", "Experiments"]),
        "✦  Content & SEO": ("Content view", ["SEO opportunities", "Content studio", "Site & catalogue", "Trend handoff"]),
        "↗  Performance": ("Performance view", ["Business truth", "Paid media", "Email & local", "Customers & discovery", "Data quality"]),
        "⚙  Settings": ("Settings view", ["Connections", "Metric definitions", "Reports", "Governance"]),
    }
    for page, (label, views) in groups.items():
        navigation(app).set_value(page).run()
        for view in views:
            subnav(app, label).set_value(view).run()
            assert not app.exception, f"{page} / {view}"


def test_reports_and_integrations_expose_honest_controls(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "marketing.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    navigation(app).set_value("⚙  Settings").run()
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
    monkeypatch.setenv("MARKETING_DATABASE_PATH", str(tmp_path / "marketing.sqlite3"))
    app = AppTest.from_file(APP_PATH, default_timeout=45).run()
    navigation(app).set_value("↗  Performance").run()
    markdown = " ".join(item.value for item in app.markdown)
    assert "Checkout count" in markdown or any(metric.label == "Checkout count" for metric in app.metric)
    assert "98,280" not in markdown
    assert "347" not in markdown
    subnav(app, "Performance view").set_value("Data quality").run()
    assert app.get("dataframe")
