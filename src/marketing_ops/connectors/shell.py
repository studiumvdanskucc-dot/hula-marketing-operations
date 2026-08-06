from __future__ import annotations

from dataclasses import dataclass

from src.marketing_ops.models import ConnectionState

from .base import CapabilitySet, ConfigValidationResult, ConnectionTestResult, SyncResult, SyncWindow


@dataclass(frozen=True)
class RequiredSetting:
    name: str
    configured: bool


class ProviderShell:
    """Honest configuration/health shell for a later read connector.

    The shell never claims that data was synchronized. It is present so account
    ownership, API version, permissions, and readiness can be reviewed before a
    connector implementation is enabled.
    """

    def __init__(self, provider: str, api_version: str, required: tuple[RequiredSetting, ...], read_capabilities: tuple[str, ...], permission_note: str) -> None:
        self.provider = provider
        self.api_version = api_version
        self.required = required
        self.read_capabilities = read_capabilities
        self.permission_note = permission_note

    def validate_config(self) -> ConfigValidationResult:
        missing = tuple(setting.name for setting in self.required if not setting.configured)
        return ConfigValidationResult(not missing, ConnectionState.CONNECTED if not missing else ConnectionState.NOT_CONFIGURED, missing, "Configuration fields are present; an authenticated data query is still required." if not missing else f"Add {', '.join(missing)}.")

    def test_connection(self) -> ConnectionTestResult:
        validation = self.validate_config()
        if not validation.valid:
            return ConnectionTestResult(False, ConnectionState.NOT_CONFIGURED, validation.message, api_version=self.api_version)
        return ConnectionTestResult(False, ConnectionState.DEGRADED, "Configuration is complete, but this release contains a health shell only. No live data query was attempted.", api_version=self.api_version, permissions=(self.permission_note,))

    def sync(self, window: SyncWindow) -> SyncResult:
        return SyncResult(False, self.provider, (), error="Read sync is not implemented in this first-release shell.", schema_version=self.api_version)

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(read=self.read_capabilities, write=())
