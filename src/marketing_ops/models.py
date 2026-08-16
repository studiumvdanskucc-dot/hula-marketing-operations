from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Role(StrEnum):
    VIEWER = "Viewer"
    ADMINISTRATOR = "Administrator"

    # Compatibility aliases for modules and historical local fixtures created
    # before the two-access-level redesign. Enum iteration exposes only Viewer
    # and Administrator; these aliases must never be presented as user roles.
    MARKETING_OPERATOR = "Administrator"
    PAID_MEDIA_SPECIALIST = "Administrator"
    APPROVER = "Administrator"


class Responsibility(StrEnum):
    """Workflow ownership labels, deliberately separate from access roles."""

    ADMINISTRATOR = "Administrator"
    MARKETING = "Marketing"
    PAID_MEDIA_SPECIALIST = "Paid-media specialist"
    DATA_OWNER = "Data owner"


class Permission(StrEnum):
    VIEW_DASHBOARDS = "view_dashboards"
    EXPORT_REPORTS = "export_reports"
    MANAGE_TASKS = "manage_tasks"
    MANAGE_CAMPAIGNS = "manage_campaigns"
    MANAGE_CONTENT = "manage_content"
    REVIEW_PAID_MEDIA = "review_paid_media"
    REQUEST_APPROVAL = "request_approval"
    DECIDE_APPROVAL = "decide_approval"
    MANAGE_INTEGRATIONS = "manage_integrations"
    MANAGE_ROLES = "manage_roles"
    EXECUTE_LOW_RISK = "execute_low_risk"
    EXECUTE_MEDIUM_RISK = "execute_medium_risk"
    EXECUTE_HIGH_RISK = "execute_high_risk"


class DataMode(StrEnum):
    DEMO = "demo"
    FIXTURE = "fixture"
    LIVE = "live"
    PARTIAL = "partial"


class Severity(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class TaskStatus(StrEnum):
    DETECTED = "Detected"
    REVIEWED = "Reviewed"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    PLANNED = "Planned"
    IN_PROGRESS = "In Progress"
    AWAITING_REVIEW = "Awaiting Review"
    AWAITING_APPROVAL = "Awaiting Approval"
    APPROVED = "Approved"
    SCHEDULED = "Scheduled"
    IMPLEMENTED = "Implemented"
    VERIFICATION_FAILED = "Verification Failed"
    MEASURING = "Measuring"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class ApprovalStatus(StrEnum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"


class RiskLevel(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ConnectionState(StrEnum):
    NOT_CONFIGURED = "Not configured"
    INCOMPLETE = "Configuration incomplete"
    AUTH_REQUIRED = "Authentication required"
    CONNECTED = "Connected"
    SYNCING = "Syncing"
    HEALTHY = "Healthy"
    DEGRADED = "Degraded"
    STALE = "Stale"
    PERMISSION_INSUFFICIENT = "Permission insufficient"
    ERROR = "Error"
    DISABLED = "Disabled"


@dataclass(frozen=True)
class MetricDefinition:
    business_name: str
    technical_name: str
    formula: str
    source_system: str
    attribution: str = "Not applicable"
    cadence: str = "Daily"
    limitations: str = ""
    owner: str = "Marketing Operations"


@dataclass(frozen=True)
class MetricValue:
    name: str
    value: float
    source_badge: str
    period: str
    freshness: str
    currency: str = "HKD"
    comparison_pct: float | None = None
    definition: str = ""


@dataclass(frozen=True)
class Signal:
    rule_id: str
    rule_version: str
    title: str
    description: str
    why_it_matters: str
    evidence: str
    recommended_action: str
    playbook: tuple[str, ...]
    success_measure: str
    source_system: str
    source_entity: str
    severity: Severity
    confidence: float
    data_period: str
    data_freshness: str
    owner_role: Responsibility
    deduplication_key: str
    expiry_date: str | None = None
    data_mode: DataMode = DataMode.DEMO
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["severity"] = self.severity.value
        payload["owner_role"] = self.owner_role.value
        payload["data_mode"] = self.data_mode.value
        payload["playbook"] = list(self.playbook)
        return payload


@dataclass(frozen=True)
class UserIdentity:
    user_id: str
    email: str
    display_name: str
    role: Role
    demo: bool = False


@dataclass(frozen=True)
class AuditEvent:
    actor_id: str
    actor_role: str
    action: str
    entity_type: str
    entity_id: str
    detail: dict[str, Any]
    created_at: str = field(default_factory=utc_now)
