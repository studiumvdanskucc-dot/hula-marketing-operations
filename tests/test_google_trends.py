from __future__ import annotations

import pytest

from src.connectors.google_trends import (
    GoogleTrendsConnector,
    GoogleTrendsError,
    normalize_serpapi_interest,
    normalize_serpapi_related,
)


def _timeline(terms: list[str], values: list[list[int]]) -> list[dict]:
    return [
        {
            "timestamp": str(1782864000 + index * 604800),
            "values": [
                {"query": term, "value": str(value), "extracted_value": value}
                for term, value in zip(terms, row)
            ],
        }
        for index, row in enumerate(values)
    ]


def test_serpapi_comparison_batches_are_anchor_calibrated() -> None:
    terms = ["designer fashion", "black bags", "red trousers"]
    payloads = [
        {
            "interest_over_time": {
                "timeline_data": _timeline(
                    terms,
                    [[50, 20, 10], [50, 30, 20], [50, 50, 40]],
                )
            }
        }
    ]
    series = normalize_serpapi_interest(payloads, [terms], "designer fashion")
    assert set(series) == {"black bags", "red trousers"}
    assert [point["value"] for point in series["black bags"]] == [20, 30, 50]


def test_timeline_values_without_query_names_are_not_assigned_by_position() -> None:
    terms = ["designer fashion", "black bags"]
    payloads = [
        {
            "interest_over_time": {
                "timeline_data": [
                    {
                        "timestamp": "1782864000",
                        "values": [
                            {"extracted_value": 50},
                            {"extracted_value": 25},
                        ],
                    }
                ]
            }
        }
    ]
    assert normalize_serpapi_interest(
        payloads,
        [terms],
        "designer fashion",
    ) == {}


def test_serpapi_related_queries_keep_the_seed() -> None:
    rows = normalize_serpapi_related(
        [
            {
                "related_queries": {
                    "rising": [
                        {
                            "query": "black east west bag",
                            "value": "+180%",
                            "extracted_value": 180,
                        }
                    ]
                }
            }
        ],
        ["fashion trends"],
    )
    assert rows[0] == {
        "query": "black east west bag",
        "value": 180,
        "seed": "fashion trends",
    }


def test_auto_provider_requires_and_uses_serpapi_key() -> None:
    connector = GoogleTrendsConnector(serpapi_api_key="key", provider="auto")
    assert connector._provider_order() == ["serpapi"]

    with pytest.raises(GoogleTrendsError, match="SERPAPI_API_KEY is missing"):
        GoogleTrendsConnector(provider="auto")._provider_order()


def test_serpapi_request_uses_hong_kong_not_us() -> None:
    captured = {}

    class Response:
        ok = True

        def json(self):
            return {"search_metadata": {"status": "Success"}}

    class Session:
        def get(self, url, **kwargs):
            captured.update(kwargs.get("params") or {})
            return Response()

    connector = GoogleTrendsConnector(
        geo="HK",
        provider="serpapi",
        serpapi_api_key="key",
    )
    connector.session = Session()
    connector._serpapi_request(query="ballet flats", data_type="TIMESERIES")

    assert captured["geo"] == "HK"
    assert captured["tz"] == -480
    assert captured["engine"] == "google_trends"


def test_worldwide_request_omits_geo_filter() -> None:
    captured = {}

    class Response:
        ok = True

        def json(self):
            return {"search_metadata": {"status": "Success"}}

    class Session:
        def get(self, url, **kwargs):
            captured.update(kwargs.get("params") or {})
            return Response()

    connector = GoogleTrendsConnector(
        geo="WORLDWIDE",
        provider="serpapi",
        serpapi_api_key="key",
    )
    connector.session = Session()
    connector._serpapi_request(query="ballet flats", data_type="TIMESERIES")

    assert "geo" not in captured
    assert captured["tz"] == 0
    assert connector.market == "Worldwide"


def test_serpapi_plan_is_bounded_to_five_lightweight_searches(monkeypatch) -> None:
    connector = GoogleTrendsConnector(
        provider="serpapi",
        serpapi_api_key="key",
        max_terms=12,
        max_discovery_seeds=2,
    )
    calls: list[tuple[str, str]] = []

    def fake_request(*, query: str, data_type: str):
        calls.append((query, data_type))
        if data_type == "RELATED_QUERIES":
            return {
                "related_queries": {
                    "rising": [
                        {"query": f"specific {query}", "extracted_value": 120}
                    ]
                }
            }
        terms = query.split(",")
        return {
            "interest_over_time": {
                "timeline_data": _timeline(
                    terms,
                    [[50, *([20] * (len(terms) - 1))]],
                )
            }
        }

    monkeypatch.setattr(connector, "_serpapi_request", fake_request)
    result = connector._collect_serpapi(
        [f"specific fashion term {index}" for index in range(20)],
        ["fashion trends", "shoe trends", "bag trends"],
    )

    assert len(calls) == 5
    assert [kind for _, kind in calls].count("TIMESERIES") == 3
    assert [kind for _, kind in calls].count("RELATED_QUERIES") == 2
    assert len(result["series"]) == 12
    assert result["requests_used"] == 5
    assert result["request_ceiling"] == 5
