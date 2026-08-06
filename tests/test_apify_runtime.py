from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.config import Settings
from src.connectors.apify_runtime import (
    ApifyCapacityError,
    actor_memory_mb,
    is_capacity_failure,
)
from src.connectors.apify_x import ApifyXConnector
from src.pipeline import _cache_state


class FakeResponse:
    def __init__(self, status_code: int, payload: dict) -> None:
        self.status_code = status_code
        self._payload = payload

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._payload


class RunSession:
    def __init__(self, run_payload: dict) -> None:
        self.run_payload = run_payload
        self.post_calls: list[dict] = []

    def post(self, url, **kwargs):
        self.post_calls.append({"url": url, **kwargs})
        if url.endswith("/abort"):
            return FakeResponse(200, {"data": {"status": "ABORTED"}})
        return FakeResponse(201, {"data": self.run_payload})

    def get(self, url, **kwargs):
        return FakeResponse(200, {"data": self.run_payload})


def test_actor_memory_accepts_only_apify_power_of_two_values() -> None:
    assert actor_memory_mb(512, 512) == 512
    assert actor_memory_mb("1024", 512) == 1024
    assert actor_memory_mb(750, 512) == 512
    assert actor_memory_mb(64, 1024) == 1024


def test_memory_limit_402_is_classified_as_capacity_failure() -> None:
    assert is_capacity_failure(
        402,
        "actor-memory-limit-exceeded",
        "By launching this job you will exceed the memory limit",
    )
    assert not is_capacity_failure(401, "invalid-token", "No access")


def test_x_run_forces_low_memory_and_server_timeout(monkeypatch) -> None:
    connector = ApifyXConnector("token", "owner~task", timeout_seconds=480, memory_mb=512)
    session = RunSession(
        {
            "id": "run-x",
            "status": "SUCCEEDED",
            "defaultDatasetId": "dataset-x",
        }
    )
    connector.session = session
    monkeypatch.setattr(connector, "_dataset_items", lambda dataset_id: [])

    _, meta = connector._run_with_meta({"query": "fashion"}, max_items=20)

    params = session.post_calls[0]["params"]
    assert params["memory"] == 512
    assert params["timeout"] == 465
    assert params["restartOnError"] == "false"
    assert meta["memory_mb"] == 512


def test_x_timeout_aborts_the_remote_run(monkeypatch) -> None:
    connector = ApifyXConnector("token", "owner~task", timeout_seconds=75, memory_mb=512)
    session = RunSession({"id": "stuck-x", "status": "RUNNING"})
    connector.session = session
    ticks = iter((0.0, 100.0))
    monkeypatch.setattr("src.connectors.apify_x.time.monotonic", lambda: next(ticks))

    with pytest.raises(RuntimeError, match="stopped automatically"):
        connector._run_with_meta({"query": "fashion"})

    assert any(call["url"].endswith("/stuck-x/abort") for call in session.post_calls)


def test_x_plan_stops_after_first_capacity_error(monkeypatch) -> None:
    connector = ApifyXConnector("token", "owner~task")

    def blocked(*args, **kwargs):
        raise ApifyCapacityError("memory allowance is full")

    monkeypatch.setattr(connector, "_run_with_meta", blocked)
    plan = [
        {"id": f"search-{index}", "input": {"max_results": 10}}
        for index in range(3)
    ]
    result = connector.run_listening_plan(plan)

    assert result["failed"] == 1
    assert result["skipped_capacity"] == 2
    assert len(result["warnings"]) == 1
    assert [row["status"] for row in result["runs"]] == [
        "failed",
        "skipped_capacity",
        "skipped_capacity",
    ]


def test_google_cache_is_scoped_to_market_and_timeframe() -> None:
    snapshot = {
        "google_cache": {
            "schema_version": "3.0",
            "collected_at": datetime.now(tz=timezone.utc).isoformat(),
            "market": "HK",
            "context_timeframe": "today 3-m",
            "discovery_timeframe": "now 7-d",
            "context_series": {
                "black bags": [{"date": "2026-07-01", "value": 50}]
            },
            "recent_series": {},
        }
    }
    cache, age = _cache_state(snapshot, Settings(google_geo="HK"))
    assert cache["market"] == "HK"
    assert age is not None and age < 1

    wrong_market, _ = _cache_state(snapshot, Settings(google_geo="US"))
    assert wrong_market == {}

    legacy = {"google_cache": {**snapshot["google_cache"], "schema_version": "2.0"}}
    rejected_legacy, _ = _cache_state(legacy, Settings(google_geo="HK"))
    assert rejected_legacy == {}
