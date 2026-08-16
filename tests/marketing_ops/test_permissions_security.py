from __future__ import annotations

import pytest

from src.marketing_ops.config import MarketingSettings
from src.marketing_ops.models import Permission, RiskLevel, Role
from src.marketing_ops.permissions import can_execute_risk, has_permission, require_permission
from src.marketing_ops.security import redact_customer_text, redact_mapping, redact_text, safe_exception


def test_role_permissions_are_explicit() -> None:
    assert list(Role) == [Role.VIEWER, Role.ADMINISTRATOR]
    assert has_permission(Role.VIEWER, Permission.VIEW_DASHBOARDS)
    assert not has_permission(Role.VIEWER, Permission.MANAGE_TASKS)
    assert has_permission(Role.ADMINISTRATOR, Permission.REVIEW_PAID_MEDIA)
    assert has_permission(Role.ADMINISTRATOR, Permission.DECIDE_APPROVAL)
    assert has_permission(Role.ADMINISTRATOR, Permission.MANAGE_ROLES)
    with pytest.raises(PermissionError):
        require_permission(Role.VIEWER, Permission.MANAGE_CONTENT)


def test_risk_execution_is_limited_by_role() -> None:
    assert not can_execute_risk(Role.VIEWER, RiskLevel.LOW)
    assert not can_execute_risk(Role.VIEWER, RiskLevel.MEDIUM)
    assert not can_execute_risk(Role.VIEWER, RiskLevel.HIGH)
    assert can_execute_risk(Role.ADMINISTRATOR, RiskLevel.LOW)
    assert can_execute_risk(Role.ADMINISTRATOR, RiskLevel.MEDIUM)
    assert can_execute_risk(Role.ADMINISTRATOR, RiskLevel.HIGH)


def test_any_external_enable_flag_triggers_write_warning() -> None:
    settings = MarketingSettings(feature_flags={"ENABLE_AUTOMATIC_PUBLISHING": True})
    assert settings.writes_enabled


def test_error_redaction_removes_known_and_pattern_secrets() -> None:
    secret = "known-secret-value-123456"
    error = RuntimeError(f"GET https://example.test?access_token={secret} Authorization: Bearer abc.def.ghi")
    safe = safe_exception(error, (secret,))
    assert secret not in safe
    assert "abc.def.ghi" not in safe
    assert "[redacted]" in safe


def test_mapping_and_customer_redaction() -> None:
    payload = redact_mapping({"api_key": "secret", "nested": {"Authorization": "Bearer token-value"}, "safe": "keep"})
    assert payload["api_key"] == "[redacted]"
    assert payload["nested"]["Authorization"] == "[redacted]"
    assert payload["safe"] == "keep"
    text, changed = redact_customer_text("Email me at person@example.com or +852 9123 4567")
    assert changed
    assert "person@example.com" not in text
    assert "9123 4567" not in text
