from __future__ import annotations

import time
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


SHOP_QUERY = """
query MarketingOpsConnectionTest {
  shop { name currencyCode timezoneAbbreviation plan { displayName } }
}
"""


ORDERS_QUERY = """
query MarketingOpsOrders($first: Int!, $after: String, $query: String!) {
  orders(first: $first, after: $after, query: $query, sortKey: CREATED_AT) {
    pageInfo { hasNextPage endCursor }
    nodes {
      id name createdAt updatedAt cancelledAt displayFinancialStatus
      currencyCode currentTotalPriceSet { shopMoney { amount currencyCode } }
      totalDiscountsSet { shopMoney { amount currencyCode } }
      totalShippingPriceSet { shopMoney { amount currencyCode } }
      totalTaxSet { shopMoney { amount currencyCode } }
      refunds { id createdAt totalRefundedSet { shopMoney { amount currencyCode } } }
      lineItems(first: 100) {
        nodes { id title quantity vendor product { id handle } variant { id sku } }
      }
    }
  }
}
"""


class ShopifyReadOnlyConnector(ReadOnlyHttpConnector):
    provider = "Shopify"

    def __init__(
        self,
        store_domain: str,
        access_token: str,
        api_version: str,
        *,
        client_id: str = "",
        client_secret: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(known_secrets=(access_token, client_secret), **kwargs)
        clean = store_domain.strip().removeprefix("https://").removeprefix("http://").strip("/")
        if clean and "." not in clean:
            clean = f"{clean}.myshopify.com"
        self.store_domain = clean
        self.access_token = access_token.strip()
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.api_version = api_version.strip() or "2026-07"
        self._temporary_token = ""
        self._temporary_token_expires_at = 0.0

    @property
    def endpoint(self) -> str:
        return f"https://{self.store_domain}/admin/api/{self.api_version}/graphql.json"

    def validate_config(self) -> ConfigValidationResult:
        missing = []
        if not self.store_domain:
            missing.append("SHOPIFY_STORE_DOMAIN")
        if not self.access_token and not (self.client_id and self.client_secret):
            missing.append("SHOPIFY_ADMIN_ACCESS_TOKEN or SHOPIFY_CLIENT_ID + SHOPIFY_CLIENT_SECRET")
        if self.store_domain and not self.store_domain.endswith(".myshopify.com"):
            return ConfigValidationResult(False, ConnectionState.INCOMPLETE, message="Use the permanent *.myshopify.com domain, not the storefront URL.")
        return ConfigValidationResult(
            not missing,
            ConnectionState.CONNECTED if not missing else ConnectionState.NOT_CONFIGURED,
            tuple(missing),
            "Read-only configuration is complete." if not missing else "Shopify credentials are incomplete.",
        )

    def _access_token(self) -> str:
        if self.access_token:
            return self.access_token
        if self._temporary_token and time.time() < self._temporary_token_expires_at - 60:
            return self._temporary_token
        response = self.session.post(
            f"https://{self.store_domain}/admin/oauth/access_token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            raise RuntimeError(
                f"Shopify client-credentials request failed with HTTP {response.status_code}."
            )
        body = response.json()
        token = str(body.get("access_token") or "")
        if not token:
            raise RuntimeError("Shopify did not return an access token.")
        self._temporary_token = token
        self._temporary_token_expires_at = time.time() + int(body.get("expires_in") or 86_399)
        return token

    def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        body = self._request_json(
            "POST",
            self.endpoint,
            headers={
                "X-Shopify-Access-Token": self._access_token(),
                "Content-Type": "application/json",
            },
            payload={"query": query, "variables": variables or {}},
        )
        if body.get("errors"):
            raise RuntimeError(f"Shopify GraphQL returned {body['errors']!s:.500}")
        return body.get("data") or {}

    def test_connection(self) -> ConnectionTestResult:
        validation = self.validate_config()
        if not validation.valid:
            return self.not_configured(self.provider, validation.missing)
        try:
            shop = self._graphql(SHOP_QUERY).get("shop") or {}
            return ConnectionTestResult(
                True,
                ConnectionState.HEALTHY,
                "Authenticated read-only Shopify query succeeded.",
                account_label=str(shop.get("name") or self.store_domain),
                api_version=self.api_version,
                permissions=("read_products", "read_inventory", "read_locations", "read_orders (verify in Shopify)"),
                detail={"currency": shop.get("currencyCode"), "timezone": shop.get("timezoneAbbreviation"), "plan": (shop.get("plan") or {}).get("displayName")},
            )
        except Exception as exc:
            return ConnectionTestResult(False, ConnectionState.ERROR, str(exc), api_version=self.api_version)

    def sync(self, window: SyncWindow) -> SyncResult:
        validation = self.validate_config()
        if not validation.valid:
            return SyncResult(False, self.provider, (), error=validation.message)
        cursor = window.cursor
        records: list[dict[str, Any]] = []
        try:
            while True:
                query_filter = (
                    f"created_at:>={window.start_date.isoformat()} "
                    f"created_at:<={window.end_date.isoformat()}"
                )
                orders = self._graphql(
                    ORDERS_QUERY,
                    {"first": 100, "after": cursor, "query": query_filter},
                ).get("orders") or {}
                for order in orders.get("nodes") or []:
                    money = ((order.get("currentTotalPriceSet") or {}).get("shopMoney") or {})
                    discount = ((order.get("totalDiscountsSet") or {}).get("shopMoney") or {})
                    refunds = sum(
                        float((((refund.get("totalRefundedSet") or {}).get("shopMoney") or {}).get("amount") or 0))
                        for refund in order.get("refunds") or []
                    )
                    records.append(
                        {
                            "source_entity_id": order.get("id"),
                            "order_name": order.get("name"),
                            "created_at": order.get("createdAt"),
                            "updated_at": order.get("updatedAt"),
                            "cancelled": bool(order.get("cancelledAt")),
                            "financial_status": order.get("displayFinancialStatus"),
                            "source_amount": float(money.get("amount") or 0),
                            "source_currency": money.get("currencyCode") or order.get("currencyCode"),
                            "discount_amount": float(discount.get("amount") or 0),
                            "refund_amount": refunds,
                            "line_count": len(((order.get("lineItems") or {}).get("nodes") or [])),
                            "schema_api_version": self.api_version,
                        }
                    )
                page = orders.get("pageInfo") or {}
                cursor = page.get("endCursor")
                if not page.get("hasNextPage"):
                    break
            return SyncResult(True, self.provider, tuple(records), next_cursor=cursor, schema_version=self.api_version)
        except Exception as exc:
            return SyncResult(False, self.provider, tuple(records), next_cursor=cursor, error=str(exc), schema_version=self.api_version)

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(read=("shop", "orders", "refunds", "order line aggregates"), write=())
