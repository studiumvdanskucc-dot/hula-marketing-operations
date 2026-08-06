from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.analysis.discovery import (
    annotate_discovery_provenance,
    build_validation_plan,
    candidate_plan_fingerprint,
    consolidate_commercial_evidence,
    enrich_commercial_priorities,
    select_instagram_targets,
)
from src.connectors.commercial_sources import score_commercial_evidence
from src.config import Settings
from src.pipeline import _collect_google


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def publisher_row(
    name: str,
    *,
    days_old: int,
    publisher: str = "Who What Wear",
    domain: str = "whowhatwear.example",
) -> dict:
    return {
        "id": name.casefold().replace(" ", "-"),
        "name": name,
        "commercial_score": 42.0,
        "publisher_count": 1,
        "commercial_evidence": [
            {
                "publisher": publisher,
                "publisher_group": publisher.casefold(),
                "publisher_weight": 2.0,
                "url": f"https://{domain}/fashion/{name.casefold().replace(' ', '-')}",
                "article_title": f"Current report about {name}",
                "published_at": (NOW - timedelta(days=days_old)).isoformat(),
                "evidence_kind": "trend-labelled heading",
                "explicit_label": name,
                "trend_name": name,
            }
        ],
    }


def test_recent_publisher_discoveries_are_validated_before_old_seeds() -> None:
    rows = enrich_commercial_priorities(
        [
            publisher_row("Layered Tops", days_old=1),
            publisher_row("Purple", days_old=100),
        ],
        now=NOW,
    )
    plan = build_validation_plan(
        rows,
        [
            {
                "name": "Mary Janes",
                "x_score": 99,
                "novelty_score": 90,
            }
        ],
        configured_terms=["Leopard Print", "Ballet Flats"],
        limit=4,
    )

    assert plan[0]["name"] == "Layered Tops"
    assert plan[0]["origins"] == ["live_publisher"]
    assert plan[0]["current_article_count"] == 1
    assert all(not row["seed_only"] for row in plan[:3])


def test_candidate_fingerprint_changes_when_live_shortlist_changes() -> None:
    first = build_validation_plan(
        [publisher_row("Layered Tops", days_old=1)],
        [],
        limit=3,
    )
    second = build_validation_plan(
        [publisher_row("Modern Pencil Skirts", days_old=1)],
        [],
        limit=3,
    )

    assert candidate_plan_fingerprint(first) == candidate_plan_fingerprint(first)
    assert candidate_plan_fingerprint(first) != candidate_plan_fingerprint(second)


def test_alias_clusters_are_applied_before_publisher_breadth_is_scored() -> None:
    evidence = [
        publisher_row(
            "Layered Camisoles",
            days_old=1,
            publisher="Who What Wear",
            domain="whowhatwear.example",
        )["commercial_evidence"][0],
        publisher_row(
            "Layered Tops",
            days_old=2,
            publisher="Teen Vogue",
            domain="teenvogue.example",
        )["commercial_evidence"][0],
    ]
    consolidated = consolidate_commercial_evidence(
        evidence,
        [
            {
                "name": "Layered Tops",
                "aliases": ["layered camisoles", "layered tops"],
            }
        ],
    )
    scored = score_commercial_evidence(consolidated, now=NOW)

    assert len(scored) == 1
    assert scored[0]["name"] == "Layered Tops"
    assert scored[0]["publisher_count"] == 2
    assert set(scored[0]["aliases"]) == {"Layered Camisoles", "Layered Tops"}


def test_instagram_targets_follow_live_validation_plan_not_seed_order() -> None:
    plan = [
        {
            "id": "layered-tops",
            "name": "Layered Tops",
            "origins": ["live_publisher"],
            "seed_only": False,
        },
        {
            "id": "leopard-print",
            "name": "Leopard Print",
            "origins": ["configured_seed"],
            "seed_only": True,
        },
    ]
    targets = select_instagram_targets(plan, limit=1)

    assert targets == [{"id": "layered-tops", "name": "Layered Tops"}]


def test_provenance_keeps_seed_only_rows_out_of_live_discovery_counts() -> None:
    trends = annotate_discovery_provenance(
        [
            {"id": "layered-tops", "name": "Layered Tops"},
            {"id": "leopard-print", "name": "Leopard Print"},
        ],
        [
            {
                "id": "layered-tops",
                "name": "Layered Tops",
                "origins": ["live_publisher"],
                "rank": 1,
            },
            {
                "id": "leopard-print",
                "name": "Leopard Print",
                "origins": ["configured_seed"],
                "rank": 2,
            },
        ],
        commercial_rows=[{"id": "layered-tops", "name": "Layered Tops"}],
    )

    assert trends[0]["live_discovered"] is True
    assert trends[0]["discovery_origin_label"] == "Live publisher discovery"
    assert trends[1]["live_discovered"] is False
    assert trends[1]["seed_only"] is True


def test_fresh_cache_is_invalidated_when_live_candidates_change(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_collect(self, terms, discovery_seeds=None):
        selected = list(terms)
        calls.append(selected)
        start = NOW.date() - timedelta(days=20)
        return {
            "series": {
                term: [
                    {
                        "date": (start + timedelta(days=index)).isoformat(),
                        "value": 20 + index,
                        "raw_value": 20 + index,
                    }
                    for index in range(21)
                ]
                for term in selected
            },
            "warnings": [],
            "provider": "offline test",
            "requests_used": 1,
            "request_ceiling": 1,
        }

    monkeypatch.setattr(
        "src.pipeline.GoogleTrendsConnector.collect",
        fake_collect,
    )
    settings = Settings(
        serpapi_api_key="test-key",
        enable_google_related_queries=False,
        google_max_terms=2,
        google_cache_hours=24,
    )
    old_cache = {
        "schema_version": "4.0",
        "collected_at": datetime.now(tz=timezone.utc).isoformat(),
        "market": "WORLDWIDE",
        "context_timeframe": settings.google_timeframe,
        "discovery_timeframe": settings.google_discovery_timeframe,
        "provider": "old cache",
        "context_series": {
            "Leopard Print": [
                {
                    "date": (NOW.date() - timedelta(days=index)).isoformat(),
                    "value": 50,
                }
                for index in range(21)
            ]
        },
        "recent_series": {},
        "related": [],
        "candidate_input_fingerprint": "old-candidate-set",
        "validation_plan": [
            {
                "id": "leopard-print",
                "name": "Leopard Print",
                "origins": ["configured_seed"],
            }
        ],
    }

    rows, meta, cache, status, fresh = _collect_google(
        settings,
        x_rows=[],
        commercial_rows=enrich_commercial_priorities(
            [publisher_row("Layered Tops", days_old=1)],
            now=NOW,
        ),
        existing_snapshot={"google_cache": old_cache},
        warnings=[],
        filtered_terms=[],
    )

    assert len(calls) == 2
    assert all("Layered Tops" in call for call in calls)
    assert meta["used_cache"] is False
    assert meta["cache_candidate_match"] is False
    assert "Layered Tops" in cache["context_series"]
    assert status.startswith("LIVE")
    assert fresh is True
    assert any(row["name"] == "Layered Tops" for row in rows)
