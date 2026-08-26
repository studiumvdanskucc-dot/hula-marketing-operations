from __future__ import annotations

import json
from typing import Any

from src.marketing_ops.models import ConnectionState

from .base import (
    CapabilitySet,
    ConfigValidationResult,
    ConnectionTestResult,
    ReadOnlyHttpConnector,
    SyncResult,
    SyncWindow,
)


PURCHASE_ACTION_PRIORITY = (
    "omni_purchase",
    "purchase",
    "offsite_conversion.fb_pixel_purchase",
)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _preferred_action_value(items: list[dict[str, Any]] | None) -> float:
    by_type = {
        str(item.get("action_type") or ""): _number(item.get("value"))
        for item in items or []
    }
    for action_type in PURCHASE_ACTION_PRIORITY:
        if action_type in by_type:
            return by_type[action_type]
    return 0.0


class MetaAdsReadOnlyConnector(ReadOnlyHttpConnector):
    """Read-only Meta campaign insights using one explicit attribution window."""

    provider = "Meta Ads"

    def __init__(
        self,
        ad_account_id: str,
        access_token: str,
        api_version: str,
        **kwargs: Any,
    ) -> None:
        super().__init__(known_secrets=(access_token,), **kwargs)
        clean_id = ad_account_id.strip()
        self.ad_account_id = (
            clean_id if not clean_id or clean_id.startswith("act_") else f"act_{clean_id}"
        )
        self.access_token = access_token.strip()
        self.api_version = api_version.strip() or "v26.0"

    @property
    def base_url(self) -> str:
        return f"https://graph.facebook.com/{self.api_version}"

    @property
    def account_endpoint(self) -> str:
        return f"{self.base_url}/{self.ad_account_id}"

    @property
    def insights_endpoint(self) -> str:
        return f"{self.account_endpoint}/insights"

    def validate_config(self) -> ConfigValidationResult:
        missing = tuple(
            name
            for name, value in (
                ("META_AD_ACCOUNT_ID", self.ad_account_id),
                ("META_SYSTEM_USER_ACCESS_TOKEN", self.access_token),
            )
            if not value
        )
        if self.ad_account_id and not self.ad_account_id.removeprefix("act_").isdigit():
            return ConfigValidationResult(
                False,
                ConnectionState.INCOMPLETE,
                message="META_AD_ACCOUNT_ID must be the numeric account ID (with or without act_).",
            )
        return ConfigValidationResult(
            not missing,
            ConnectionState.CONNECTED if not missing else ConnectionState.NOT_CONFIGURED,
            missing,
            "Read-only configuration is complete."
            if not missing
            else "Meta Ads configuration is incomplete.",
        )

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        body = self._request_json(
            "GET",
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
            params=params,
        )
        if body.get("error"):
            raise RuntimeError(f"Meta Graph API returned {body['error']!s:.500}")
        return body

    def test_connection(self) -> ConnectionTestResult:
        validation = self.validate_config()
        if not validation.valid:
            return self.not_configured(self.provider, validation.missing)
        try:
            account = self._get(
                self.account_endpoint,
                {
                    "fields": "id,name,account_status,currency,timezone_name",
                },
            )
            return ConnectionTestResult(
                True,
                ConnectionState.HEALTHY,
                "Authenticated Meta Ads read-only account query succeeded.",
                account_label=str(account.get("name") or self.ad_account_id),
                api_version=self.api_version,
                permissions=("ads_read",),
                detail={
                    "account_id": account.get("id"),
                    "account_status": account.get("account_status"),
                    "currency": account.get("currency"),
                    "timezone": account.get("timezone_name"),
                },
            )
        except Exception as exc:
            return ConnectionTestResult(
                False,
                ConnectionState.ERROR,
                str(exc),
                api_version=self.api_version,
            )

    def sync(self, window: SyncWindow) -> SyncResult:
        validation = self.validate_config()
        if not validation.valid:
            return SyncResult(
                False,
                self.provider,
                (),
                error=validation.message,
                schema_version=self.api_version,
            )

        records: list[dict[str, Any]] = []
        cursor = window.cursor
        try:
            while True:
                params: dict[str, Any] = {
                    "level": "campaign",
                    "time_increment": 1,
                    "time_range": json.dumps(
                        {
                            "since": window.start_date.isoformat(),
                            "until": window.end_date.isoformat(),
                        }
                    ),
                    "action_attribution_windows": json.dumps(["7d_click"]),
                    "fields": (
                        "date_start,date_stop,campaign_id,campaign_name,spend,"
                        "impressions,clicks,actions,action_values,attribution_setting"
                    ),
                    "limit": 500,
                }
                if cursor:
                    params["after"] = cursor
                body = self._get(self.insights_endpoint, params)
                for item in body.get("data") or []:
                    records.append(
                        {
                            "date_start": item.get("date_start"),
                            "date_stop": item.get("date_stop"),
                            "source_entity_id": item.get("campaign_id"),
                            "campaign_name": item.get("campaign_name"),
                            "spend": _number(item.get("spend")),
                            "impressions": int(_number(item.get("impressions"))),
                            "clicks": int(_number(item.get("clicks"))),
                            "purchase_count": _preferred_action_value(item.get("actions")),
                            "attributed_purchase_value": _preferred_action_value(
                                item.get("action_values")
                            ),
                            "management_attribution_window": "7d_click",
                            "account_attribution_setting": item.get(
                                "attribution_setting"
                            ),
                            "schema_api_version": self.api_version,
                        }
                    )
                paging = body.get("paging") or {}
                next_cursor = (paging.get("cursors") or {}).get("after")
                if not next_cursor or next_cursor == cursor:
                    break
                cursor = str(next_cursor)
            return SyncResult(
                True,
                self.provider,
                tuple(records),
                next_cursor=cursor,
                warnings=(
                    "Meta values are platform-attributed claims using a 7-day click query; they are not booked Shopify revenue.",
                    "Purchase action types are selected by priority and never summed to avoid counting overlapping Meta action rows twice.",
                ),
                schema_version=self.api_version,
            )
        except Exception as exc:
            return SyncResult(
                False,
                self.provider,
                tuple(records),
                next_cursor=cursor,
                error=str(exc),
                schema_version=self.api_version,
            )

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(
            read=(
                "campaign insights",
                "spend and delivery",
                "7-day click purchase claims",
            ),
            write=(),
        )
