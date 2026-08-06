from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .config import MarketingSettings
from .models import Role, UserIdentity
from .security import safe_exception


@dataclass(frozen=True)
class AuthenticatedSession:
    identity: UserIdentity
    access_token: str
    refresh_token: str


class SupabaseAuthenticator:
    """Minimal server-side Supabase Auth adapter.

    Credentials are sent directly to Supabase Auth, never stored in the
    operational database, rendered, or logged. Role membership comes from the
    RLS-protected ``marketing_members`` table.
    """

    def __init__(self, url: str, anon_key: str, *, timeout_seconds: int = 20) -> None:
        self.url = url.rstrip("/")
        self.anon_key = anon_key
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.url and self.anon_key)

    def authenticate(self, email: str, password: str) -> AuthenticatedSession:
        if not self.configured:
            raise RuntimeError("Supabase Auth is not configured.")
        try:
            response = requests.post(
                f"{self.url}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": self.anon_key, "Content-Type": "application/json"},
                json={"email": email, "password": password},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            body = response.json()
            access_token = str(body.get("access_token") or "")
            refresh_token = str(body.get("refresh_token") or "")
            user = body.get("user") or {}
            user_id = str(user.get("id") or "")
            if not access_token or not user_id:
                raise RuntimeError("Supabase Auth response did not include a user session.")
            identity = self._identity(user_id, email, access_token)
            return AuthenticatedSession(identity, access_token, refresh_token)
        except Exception as exc:
            raise RuntimeError(safe_exception(exc, (self.anon_key,))) from None

    def _identity(self, user_id: str, email: str, access_token: str) -> UserIdentity:
        response = requests.get(
            f"{self.url}/rest/v1/marketing_members",
            params={"user_id": f"eq.{user_id}", "active": "eq.true", "select": "display_name,role"},
            headers={
                "apikey": self.anon_key,
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        rows = response.json()
        if not rows:
            raise PermissionError("This account has not been invited to HULA Marketing Operations.")
        row: dict[str, Any] = rows[0]
        try:
            role = Role(str(row.get("role")))
        except ValueError as exc:
            raise PermissionError("This account has an invalid role assignment.") from exc
        return UserIdentity(
            user_id=user_id,
            email=email,
            display_name=str(row.get("display_name") or email),
            role=role,
            demo=False,
        )


def demo_identity(settings: MarketingSettings, role: Role | None = None) -> UserIdentity:
    selected_role = role
    if selected_role is None:
        try:
            selected_role = Role(settings.default_role)
        except ValueError:
            selected_role = Role.MARKETING_OPERATOR
    return UserIdentity(
        user_id=f"demo:{selected_role.value.lower().replace(' ', '-')}",
        email="demo@local.invalid",
        display_name=settings.demo_user_name,
        role=selected_role,
        demo=True,
    )
