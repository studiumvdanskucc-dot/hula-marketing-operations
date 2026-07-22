from __future__ import annotations

from src.analysis.matching import match_products
from src.demo_data import demo_products, demo_snapshot, demo_trends


def test_demo_snapshot_has_ranked_recommendations() -> None:
    snapshot = demo_snapshot()
    assert len(snapshot["trends"]) >= 5
    assert len(snapshot["products"]) >= 6
    assert snapshot["recommendations"]
    scores = [row["opportunity_score"] for row in snapshot["recommendations"]]
    assert all(0 <= score <= 100 for score in scores)


def test_out_of_stock_products_are_not_recommended() -> None:
    trends = demo_trends()[:1]
    products = demo_products()[:1]
    products[0]["inventory"] = 0
    assert match_products(trends, products) == []


def test_one_of_one_inventory_is_treated_as_available() -> None:
    trend = next(item for item in demo_trends() if item["id"] == "east-west-bags")
    product = next(item for item in demo_products() if item["id"] == "demo-1")
    rows = match_products([trend], [product])
    assert rows
    assert rows[0]["readiness_score"] == 100
    assert rows[0]["opportunity_score"] > 50
