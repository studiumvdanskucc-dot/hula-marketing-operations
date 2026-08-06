from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol, runtime_checkable

import requests

from src.marketing_ops.models import ConnectionState, utc_now
from src.marketing_ops.security import safe_exception


@dataclass(frozen=True)
class ConfigValidationResult:
    valid: bool
    state: ConnectionState
    missing: tuple[str, ...] = ()
    message: str = ""


@dataclass(frozen=True)
class ConnectionTestResult:
    success: bool
    state: ConnectionState
    message: str
    checked_at: str = field(default_factory=utc_now)
    account_label: str = ""
    api_version: str = ""
    permissions: tuple[str, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SyncWindow:
    start_date: date
    end_date: date
    cursor: str | None = None


@dataclass(frozen=True)
class SyncResult:
    success: bool
    provider: str
    records: tuple[dict[str, Any], ...]
    fetched_at: str = field(default_factory=utc_now)
    next_cursor: str | None = None
    warnings: tuple[str, ...] = ()
    error: str = ""
    schema_version: str = "1"


@dataclass(frozen=True)
class CapabilitySet:
    read: tuple[str, ...]
    write: tuple[str, ...] = ()
    enabled_writes: tuple[str, ...] = ()


@runtime_checkable
class Connector(Protocol):
    provider: str

    def validate_config(self) -> ConfigValidationResult: ...
    def test_connection(self) -> ConnectionTestResult: ...
    def sync(self, window: SyncWindow) -> SyncResult: ...
    def capabilities(self) -> CapabilitySet: ...


class ReadOnlyHttpConnector:
    provider = "base"

    def __init__(
        self,
        *,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        session: requests.Session | None = None,
        known_secrets: tuple[str, ...] = (),
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.session = session or requests.Session()
        self._known_secrets = tuple(secret for secret in known_secrets if secret)

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    response.raise_for_status()
                if response.status_code >= 400:
                    detail = ""
                    try:
                        body = response.json()
                        detail = str(body.get("errors") or body.get("error") or body)[:500]
                    except Exception:
                        detail = response.text[:500]
                    raise requests.HTTPError(
                        f"HTTP {response.status_code}: {detail}", response=response
                    )
                body = response.json()
                if not isinstance(body, dict):
                    raise ValueError("Provider response was not a JSON object.")
                return body
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
                last_error = exc
                retryable = not isinstance(exc, requests.HTTPError) or (
                    exc.response is not None
                    and (exc.response.status_code == 429 or exc.response.status_code >= 500)
                )
                if not retryable or attempt >= self.max_retries:
                    break
                retry_after = 0.0
                if isinstance(exc, requests.HTTPError) and exc.response is not None:
                    try:
                        retry_after = float(exc.response.headers.get("Retry-After", 0))
                    except (TypeError, ValueError):
                        retry_after = 0.0
                delay = max(retry_after, min(8.0, 0.4 * (2**attempt)))
                delay += random.uniform(0, 0.2)
                time.sleep(delay)
            except (ValueError, TypeError) as exc:
                last_error = exc
                break
        if last_error is None:
            last_error = RuntimeError("Provider request failed without detail.")
        raise RuntimeError(safe_exception(last_error, self._known_secrets)) from None

    @staticmethod
    def not_configured(provider: str, missing: tuple[str, ...]) -> ConnectionTestResult:
        return ConnectionTestResult(
            success=False,
            state=ConnectionState.NOT_CONFIGURED,
            message=f"{provider} is not configured. Add: {', '.join(missing)}.",
        )
