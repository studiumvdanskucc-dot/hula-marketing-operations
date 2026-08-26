from __future__ import annotations

from src.marketing_ops.config import load_marketing_settings


def test_confirmed_defaults_and_unresolved_controls_are_distinct(monkeypatch) -> None:
    for name in (
        "HULA_FORECAST_RETURN_RATE",
        "HULA_FORECAST_RETURN_RATE_CONFIRMED",
        "HULA_VARIABLE_COST_RATE_OF_RETAINED",
        "HULA_VARIABLE_COST_CONFIRMED",
        "HULA_PLATFORM_GMV_ROAS_FLOOR",
        "HULA_CONTRIBUTION_ROAS_FLOOR",
        "HULA_CONTRIBUTION_ROAS_SCALE_TARGET",
        "HULA_MINIMUM_PAID_PURCHASES",
        "HULA_MAX_PAID_CAC_HKD",
        "HULA_PAYBACK_WINDOW_DAYS",
        "HULA_GOOGLE_MONTHLY_CAP_HKD",
        "HULA_META_MONTHLY_CAP_HKD",
        "HULA_MAX_INTERNAL_REALLOCATION_PCT",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = load_marketing_settings()
    assert settings.retained_margin_rate == 0.31
    assert not settings.retained_margin_confirmed
    assert settings.returns_refunds_confirmed
    assert settings.forecast_return_rate == 0.10
    assert not settings.forecast_return_rate_confirmed
    assert settings.variable_cost_rate_of_retained == 0.10
    assert settings.variable_cost_confirmed
    assert settings.platform_gmv_roas_floor == 4.0
    assert settings.contribution_roas_floor == 1.0
    assert settings.contribution_roas_scale_target is None
    assert settings.google_monthly_cap_hkd is None
    assert settings.major_change_approvers == ("Sarah", "Elena", "Tiffany")


def test_approved_decision_inputs_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv("HULA_RETAINED_MARGIN_RATE", "0.32")
    monkeypatch.setenv("HULA_RETAINED_MARGIN_CONFIRMED", "true")
    monkeypatch.setenv("HULA_RETURNS_REFUNDS_CONFIRMED", "true")
    monkeypatch.setenv("HULA_FORECAST_RETURN_RATE", "0.08")
    monkeypatch.setenv("HULA_FORECAST_RETURN_RATE_CONFIRMED", "true")
    monkeypatch.setenv("HULA_VARIABLE_COST_RATE_OF_RETAINED", "0.06")
    monkeypatch.setenv("HULA_VARIABLE_COST_CONFIRMED", "true")
    monkeypatch.setenv("HULA_PLATFORM_GMV_ROAS_FLOOR", "3.8")
    monkeypatch.setenv("HULA_CONTRIBUTION_ROAS_FLOOR", "1.15")
    monkeypatch.setenv("HULA_CONTRIBUTION_ROAS_SCALE_TARGET", "1.6")
    monkeypatch.setenv("HULA_MINIMUM_PAID_PURCHASES", "12")
    monkeypatch.setenv("HULA_GOOGLE_MONTHLY_CAP_HKD", "50000")
    monkeypatch.setenv("HULA_MAJOR_CHANGE_APPROVERS", "Sarah, Elena, Tiffany")
    settings = load_marketing_settings()
    assert settings.retained_margin_rate == 0.32
    assert settings.retained_margin_confirmed
    assert settings.returns_refunds_confirmed
    assert settings.forecast_return_rate == 0.08
    assert settings.forecast_return_rate_confirmed
    assert settings.variable_cost_rate_of_retained == 0.06
    assert settings.variable_cost_confirmed
    assert settings.platform_gmv_roas_floor == 3.8
    assert settings.contribution_roas_floor == 1.15
    assert settings.contribution_roas_scale_target == 1.6
    assert settings.minimum_paid_purchases == 12
    assert settings.google_monthly_cap_hkd == 50_000
    assert settings.major_change_approvers == ("Sarah", "Elena", "Tiffany")
