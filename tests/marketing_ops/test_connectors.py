from __future__ import annotations

from collections import deque
from datetime import date
from typing import Any

from src.marketing_ops.connectors.base import SyncWindow
from src.marketing_ops.connectors.ga4 import GA4ReadOnlyConnector
from src.marketing_ops.connectors.meta_ads import MetaAdsReadOnlyConnector
from src.marketing_ops.connectors.search_console import SearchConsoleReadOnlyConnector
from src.marketing_ops.connectors.shopify_read import ShopifyReadOnlyConnector
from src.marketing_ops.models import ConnectionState


class FakeResponse:
    def __init__(self, body: dict[str, Any], status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.text = str(body)

    def json(self) -> dict[str, Any]:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)


class FakeSession:
    def __init__(self, *responses: FakeResponse) -> None:
        self.responses = deque(responses)
        self.calls: list[dict[str, Any]] = []

    def request(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return self.responses.popleft()


def test_unconfigured_connector_never_calls_network() -> None:
    session = FakeSession()
    connector = ShopifyReadOnlyConnector("", "", "2026-07", session=session)
    result = connector.test_connection()
    assert not result.success
    assert result.state is ConnectionState.NOT_CONFIGURED
    assert session.calls == []


def test_shopify_client_credentials_are_a_supported_configuration() -> None:
    connector = ShopifyReadOnlyConnector(
        "hula.myshopify.com",
        "",
        "2026-07",
        client_id="client-id",
        client_secret="client-secret",
        session=FakeSession(),
    )
    assert connector.validate_config().valid


def test_shopify_read_only_connection_and_normalization() -> None:
    session = FakeSession(
        FakeResponse({"data": {"shop": {"name": "HULA", "currencyCode": "HKD", "timezoneAbbreviation": "HKT", "plan": {"displayName": "Shopify"}}}}),
        FakeResponse({"data": {"orders": {"pageInfo": {"hasNextPage": False, "endCursor": "end"}, "nodes": [{"id": "gid://shopify/Order/1", "name": "#1", "createdAt": "2026-07-01T00:00:00Z", "updatedAt": "2026-07-01T00:00:00Z", "cancelledAt": None, "displayFinancialStatus": "PAID", "currencyCode": "HKD", "currentTotalPriceSet": {"shopMoney": {"amount": "1000", "currencyCode": "HKD"}}, "totalDiscountsSet": {"shopMoney": {"amount": "50", "currencyCode": "HKD"}}, "refunds": [{"totalRefundedSet": {"shopMoney": {"amount": "100", "currencyCode": "HKD"}}}], "lineItems": {"nodes": [{"id": "line"}]}}]}}}),
    )
    connector = ShopifyReadOnlyConnector("hula.myshopify.com", "token-secret", "2026-07", session=session)
    health = connector.test_connection()
    assert health.success
    sync = connector.sync(SyncWindow(date(2026, 7, 1), date(2026, 7, 31)))
    assert sync.success
    assert sync.records[0]["source_amount"] == 1000
    assert sync.records[0]["refund_amount"] == 100
    assert all(call["method"] == "POST" for call in session.calls)


def test_ga4_sync_parses_dimension_and_metric_headers() -> None:
    session = FakeSession(FakeResponse({"dimensionHeaders": [{"name": "date"}, {"name": "sessionDefaultChannelGroup"}], "metricHeaders": [{"name": "sessions"}, {"name": "totalRevenue"}], "rows": [{"dimensionValues": [{"value": "20260701"}, {"value": "Organic Search"}], "metricValues": [{"value": "12"}, {"value": "100.5"}]}], "rowCount": 1, "metadata": {"dataLossFromOtherRow": False}}))
    connector = GA4ReadOnlyConnector("12345", "access-secret", session=session)
    result = connector.sync(SyncWindow(date(2026, 7, 1), date(2026, 7, 2)))
    assert result.success
    assert result.records[0]["sessionDefaultChannelGroup"] == "Organic Search"
    assert result.records[0]["totalRevenue"] == "100.5"


def test_search_console_paginates_and_keeps_dimensions() -> None:
    first_rows = [{"keys": ["2026-07-01", f"query-{i}", "https://thehula.com/page", "hkg", "DESKTOP"], "clicks": 1, "impressions": 10, "ctr": .1, "position": 5} for i in range(25000)]
    session = FakeSession(FakeResponse({"rows": first_rows}), FakeResponse({"rows": []}))
    connector = SearchConsoleReadOnlyConnector("sc-domain:thehula.com", "access-secret", session=session)
    result = connector.sync(SyncWindow(date(2026, 7, 1), date(2026, 7, 1)))
    assert result.success
    assert len(result.records) == 25000
    assert result.records[0]["country"] == "hkg"
    assert session.calls[1]["json"]["startRow"] == 25000


def test_meta_ads_connection_and_read_only_insights_normalization() -> None:
    session = FakeSession(
        FakeResponse(
            {
                "id": "act_12345",
                "name": "HULA",
                "account_status": 1,
                "currency": "HKD",
                "timezone_name": "Asia/Hong_Kong",
            }
        ),
        FakeResponse(
            {
                "data": [
                    {
                        "date_start": "2026-07-01",
                        "date_stop": "2026-07-01",
                        "campaign_id": "campaign-1",
                        "campaign_name": "Focus Sales",
                        "spend": "100.50",
                        "impressions": "1000",
                        "clicks": "50",
                        "actions": [
                            {"action_type": "purchase", "value": "3"},
                            {"action_type": "omni_purchase", "value": "2"},
                        ],
                        "action_values": [
                            {"action_type": "purchase", "value": "12000"},
                            {"action_type": "omni_purchase", "value": "10000"},
                        ],
                        "attribution_setting": "7d_click",
                    }
                ]
            }
        ),
    )
    connector = MetaAdsReadOnlyConnector("12345", "meta-secret", "v26.0", session=session)

    health = connector.test_connection()
    assert health.success
    assert health.detail["currency"] == "HKD"

    result = connector.sync(SyncWindow(date(2026, 7, 1), date(2026, 7, 1)))
    assert result.success
    assert result.records[0]["purchase_count"] == 2
    assert result.records[0]["attributed_purchase_value"] == 10_000
    assert result.records[0]["management_attribution_window"] == "7d_click"
    assert session.calls[1]["method"] == "GET"
    assert session.calls[1]["headers"]["Authorization"] == "Bearer meta-secret"
    assert "access_token" not in session.calls[1]["params"]
