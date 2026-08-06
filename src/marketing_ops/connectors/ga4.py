from __future__ import annotations

from typing import Any

from src.marketing_ops.models import ConnectionState

from .base import CapabilitySet, ConfigValidationResult, ConnectionTestResult, ReadOnlyHttpConnector, SyncResult, SyncWindow


class GA4ReadOnlyConnector(ReadOnlyHttpConnector):
    provider = "Google Analytics 4"
    api_version = "Data API v1 (REST v1beta resource)"

    def __init__(self, property_id: str, access_token: str, **kwargs: Any) -> None:
        super().__init__(known_secrets=(access_token,), **kwargs)
        self.property_id = property_id.strip().removeprefix("properties/")
        self.access_token = access_token.strip()

    @property
    def endpoint(self) -> str:
        return f"https://analyticsdata.googleapis.com/v1beta/properties/{self.property_id}:runReport"

    def validate_config(self) -> ConfigValidationResult:
        missing = tuple(name for name, value in (("GA4_PROPERTY_ID", self.property_id), ("GOOGLE_OAUTH_ACCESS_TOKEN", self.access_token)) if not value)
        if self.property_id and not self.property_id.isdigit():
            return ConfigValidationResult(False, ConnectionState.INCOMPLETE, message="GA4_PROPERTY_ID must be the numeric property ID.")
        return ConfigValidationResult(not missing, ConnectionState.CONNECTED if not missing else ConnectionState.NOT_CONFIGURED, missing, "Read-only configuration is complete." if not missing else "GA4 configuration is incomplete.")

    def _run_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", self.endpoint, headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}, payload=payload)

    def test_connection(self) -> ConnectionTestResult:
        validation = self.validate_config()
        if not validation.valid:
            return self.not_configured(self.provider, validation.missing)
        try:
            body = self._run_report({"dateRanges": [{"startDate": "7daysAgo", "endDate": "yesterday"}], "metrics": [{"name": "sessions"}], "limit": 1})
            return ConnectionTestResult(True, ConnectionState.HEALTHY, "Authenticated GA4 read-only report succeeded.", account_label=f"Property {self.property_id}", api_version=self.api_version, permissions=("analytics.readonly",), detail={"row_count": body.get("rowCount", 0), "metadata_present": bool(body.get("metadata"))})
        except Exception as exc:
            return ConnectionTestResult(False, ConnectionState.ERROR, str(exc), api_version=self.api_version)

    def sync(self, window: SyncWindow) -> SyncResult:
        validation = self.validate_config()
        if not validation.valid:
            return SyncResult(False, self.provider, (), error=validation.message, schema_version=self.api_version)
        payload = {
            "dateRanges": [{"startDate": window.start_date.isoformat(), "endDate": window.end_date.isoformat()}],
            "dimensions": [{"name": "date"}, {"name": "sessionDefaultChannelGroup"}],
            "metrics": [{"name": "sessions"}, {"name": "activeUsers"}, {"name": "engagedSessions"}, {"name": "ecommercePurchases"}, {"name": "totalRevenue"}],
            "limit": 100000,
        }
        try:
            body = self._run_report(payload)
            dimensions = [item.get("name") for item in body.get("dimensionHeaders") or []]
            metrics = [item.get("name") for item in body.get("metricHeaders") or []]
            rows = []
            for row in body.get("rows") or []:
                record = {name: value.get("value") for name, value in zip(dimensions, row.get("dimensionValues") or [])}
                record.update({name: value.get("value") for name, value in zip(metrics, row.get("metricValues") or [])})
                record["schema_api_version"] = self.api_version
                rows.append(record)
            metadata = body.get("metadata") or {}
            warnings = (
                "GA4 metadata reports data loss from the aggregated other row.",
            ) if metadata.get("dataLossFromOtherRow") else ()
            return SyncResult(True, self.provider, tuple(rows), warnings=warnings, schema_version=self.api_version)
        except Exception as exc:
            return SyncResult(False, self.provider, (), error=str(exc), schema_version=self.api_version)

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(read=("standard reports", "ecommerce metrics", "traffic attribution", "funnel events"), write=())
