from __future__ import annotations

from .models import Permission, RiskLevel, Role


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset(
        {Permission.VIEW_DASHBOARDS, Permission.EXPORT_REPORTS}
    ),
    Role.ADMINISTRATOR: frozenset(Permission),
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require_permission(role: Role, permission: Permission) -> None:
    if not has_permission(role, permission):
        raise PermissionError(
            f"The {role.value} role is not allowed to perform {permission.value}."
        )


def can_execute_risk(role: Role, risk: RiskLevel) -> bool:
    mapping = {
        RiskLevel.LOW: Permission.EXECUTE_LOW_RISK,
        RiskLevel.MEDIUM: Permission.EXECUTE_MEDIUM_RISK,
        RiskLevel.HIGH: Permission.EXECUTE_HIGH_RISK,
    }
    return has_permission(role, mapping[risk])


def permission_matrix_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for permission in Permission:
        row = {"Permission": permission.value.replace("_", " ").title()}
        for role in Role:
            row[role.value] = "Yes" if has_permission(role, permission) else "—"
        rows.append(row)
    return rows
