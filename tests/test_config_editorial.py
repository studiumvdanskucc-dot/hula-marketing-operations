from __future__ import annotations

from src.config import load_settings


def test_editorial_google_windows_ignore_legacy_hosted_timeframe_keys(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_TRENDS_TIMEFRAME", "today 3-m")
    monkeypatch.setenv("GOOGLE_TRENDS_DISCOVERY_TIMEFRAME", "now 7-d")

    settings = load_settings()

    assert settings.google_timeframe == "today 12-m"
    assert settings.google_discovery_timeframe == "today 3-m"


def test_editorial_google_windows_have_dedicated_overrides(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_TRENDS_CONTEXT_TIMEFRAME", "today 5-y")
    monkeypatch.setenv("GOOGLE_TRENDS_RECENT_TIMEFRAME", "today 1-m")

    settings = load_settings()

    assert settings.google_timeframe == "today 5-y"
    assert settings.google_discovery_timeframe == "today 1-m"
