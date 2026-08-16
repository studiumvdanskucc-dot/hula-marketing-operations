from __future__ import annotations

import pytest

from src.marketing_ops.models import ApprovalStatus, RiskLevel, Role, TaskStatus, UserIdentity
from src.marketing_ops.store import OperationalStore


def user(name: str, role: Role) -> UserIdentity:
    return UserIdentity(name, f"{name}@example.test", name, role, demo=True)


def test_task_deduplication_and_fixture_action_guard(tmp_path) -> None:
    store = OperationalStore(tmp_path / "ops.sqlite3")
    operator = user("administrator", Role.ADMINISTRATOR)
    fields = dict(
        title="Fix SEO title",
        description="Evidence",
        problem_type="SEO",
        source_system="GSC",
        evidence={"impressions": 1000},
        severity="High",
        recommended_action="Draft a better title",
        owner="operator",
        deduplication_key="seo:one",
        data_mode="fixture",
    )
    first = store.create_task(operator, **fields)
    second = store.create_task(operator, **fields)
    assert first == second
    with pytest.raises(ValueError, match="Fixture/demo"):
        store.update_task_status(operator, first, TaskStatus.IMPLEMENTED)


def test_rejection_requires_reason(tmp_path) -> None:
    store = OperationalStore(tmp_path / "ops.sqlite3")
    operator = user("administrator", Role.ADMINISTRATOR)
    task = store.create_task(operator, title="Review", description="x", problem_type="Manual", source_system="Internal", evidence={}, severity="Medium", recommended_action="review", owner="operator")
    with pytest.raises(ValueError, match="reason"):
        store.update_task_status(operator, task, TaskStatus.REJECTED)
    store.update_task_status(operator, task, TaskStatus.REJECTED, rejection_reason="Not relevant to current inventory")
    assert store.list_tasks()[0]["status"] == "Rejected"


def test_second_approval_cannot_be_self_approved(tmp_path) -> None:
    store = OperationalStore(tmp_path / "ops.sqlite3")
    requester = user("administrator", Role.ADMINISTRATOR)
    other = user("independent-reviewer", Role.ADMINISTRATOR)
    approval = store.create_approval(requester, object_type="external_action", object_id="123", summary="Publish", risk_level=RiskLevel.HIGH)
    with pytest.raises(PermissionError, match="requester"):
        store.decide_approval(requester, approval, ApprovalStatus.APPROVED, "I approve")
    store.decide_approval(other, approval, ApprovalStatus.APPROVED, "Independent review complete")
    assert store.list_approvals()[0]["status"] == "Approved"


def test_viewer_cannot_mutate(tmp_path) -> None:
    store = OperationalStore(tmp_path / "ops.sqlite3")
    viewer = user("viewer", Role.VIEWER)
    with pytest.raises(PermissionError):
        store.create_task(viewer, title="No", description="No", problem_type="No", source_system="No", evidence={}, severity="Low", recommended_action="No", owner="No")


def test_audit_log_records_workflow_changes(tmp_path) -> None:
    store = OperationalStore(tmp_path / "ops.sqlite3")
    operator = user("administrator", Role.ADMINISTRATOR)
    task = store.create_task(operator, title="Audit me", description="x", problem_type="Manual", source_system="Internal", evidence={}, severity="Low", recommended_action="x", owner="operator")
    store.update_task_status(operator, task, TaskStatus.IN_PROGRESS)
    actions = [row["action"] for row in store.list_audit_events()]
    assert "task.created" in actions
    assert "task.status_changed" in actions
