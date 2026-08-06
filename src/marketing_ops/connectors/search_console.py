from __future__ import annotations

from typing import Any
from urllib.parse import quote

from src.marketing_ops.models import ConnectionState

from .base import CapabilitySet, ConfigValidationResult, ConnectionTestResult, ReadOnlyHttpConnector, SyncResult, SyncWindow


class SearchConsoleReadOnlyConnector(ReadOnlyHttpConnector):
    provider = "Google Search Console"
    api_version = "v1"

    def __init__(self, site_url: str, access_token: str, **kwargs: Any) -> None:
        super().__init__(known_secrets=(access_token,), **kwargs)
        self.site_url = site_url.strip()
        self.access_token = access_token.strip()

    @property
    def endpoint(self) -> str:
        return f"https://www.googleapis.com/webmasters/v3/sites/{quote(self.site_url, safe='')}/searchAnalytics/query"

    def validate_config(self) -> ConfigValidationResult:
        missing = tuple(name for name, value in (("GSC_SITE_URL", self.site_url), ("GOOGLE_OAUTH_ACCESS_TOKEN", self.access_token)) if not value)
        if self.site_url and not (self.site_url.startswith("sc-domain:") or self.site_url.startswith("http")):
            return ConfigValidationResult(False, ConnectionState.INCOMPLETE, message="GSC_SITE_URL must be an exact sc-domain: or URL-prefix property identifier.")
        return ConfigValidationResult(not missing, ConnectionState.CONNECTED if not missing else ConnectionState.NOT_CONFIGURED, missing, "Read-only configuration is complete." if not missing else "Search Console configuration is incomplete.")

    def _query(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", self.endpoint, headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}, payload=payload)

    def test_connection(self) -> ConnectionTestResult:
        validation = self.validate_config()
        if not validation.valid:
            return self.not_configured(self.provider, validation.missing)
        try:
            body = self._query({"startDate": "2026-07-01", "endDate": "2026-07-02", "dimensions": ["date"], "rowLimit": 1, "dataState": "final"})
            return ConnectionTestResult(True, ConnectionState.HEALTHY, "Authenticated Search Console read-only query succeeded.", account_label=self.site_url, api_version=self.api_version, permissions=("webmasters.readonly",), detail={"rows_returned": len(body.get("rows") or [])})
        except Exception as exc:
            return ConnectionTestResult(False, ConnectionState.ERROR, str(exc), api_version=self.api_version)

    def sync(self, window: SyncWindow) -> SyncResult:
        validation = self.validate_config()
        if not validation.valid:
            return SyncResult(False, self.provider, (), error=validation.message, schema_version=self.api_version)
        rows: list[dict[str, Any]] = []
        start_row = int(window.cursor or 0)
        try:
            while True:
                body = self._query({"startDate": window.start_date.isoformat(), "endDate": window.end_date.isoformat(), "dimensions": ["date", "query", "page", "country", "device"], "rowLimit": 25000, "startRow": start_row, "dataState": "final"})
                batch = body.get("rows") or []
                for item in batch:
                    keys = item.get("keys") or []
                    keys += [None] * (5 - len(keys))
                    rows.append({"date": keys[0], "query": keys[1], "page": keys[2], "country": keys[3], "device": keys[4], "clicks": item.get("clicks"), "impressions": item.get("impressions"), "ctr": item.get("ctr"), "position": item.get("position"), "schema_api_version": self.api_version})
                if len(batch) < 25000:
                    break
                start_row += len(batch)
            return SyncResult(True, self.provider, tuple(rows), next_cursor=str(start_row), warnings=("Search Console returns top rows; totals can differ by grouping.",), schema_version=self.api_version)
        except Exception as exc:
            return SyncResult(False, self.provider, tuple(rows), next_cursor=str(start_row), error=str(exc), schema_version=self.api_version)

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(read=("search analytics", "query/page/device/country dimensions", "sitemap metadata", "URL inspection (separate quota)"), write=())
