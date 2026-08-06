from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.config import Settings
from src.pipeline import refresh_snapshot


def _article(article_id: str, publisher: str, group: str, url: str) -> dict:
    now = datetime.now(tz=timezone.utc)
    return {
        "article_id": article_id,
        "publisher": publisher,
        "publisher_id": group,
        "publisher_group": group,
        "publisher_weight": 1.0,
        "title": f"{publisher}: Drop-Waist Dresses Are Back",
        "url": url,
        "published_at": (now - timedelta(days=2)).isoformat(),
        "collected_at": now.isoformat(),
        "acquisition": "publisher page",
        "headings": ["Drop-Waist Dresses"],
        "paragraphs": ["Drop-waist dresses are returning for fall."],
    }


def _series(days: int, *, step_days: int = 1) -> list[dict]:
    end = datetime.now(tz=timezone.utc).date()
    start = end - timedelta(days=(days - 1) * step_days)
    return [
        {
            "date": (start + timedelta(days=index * step_days)).isoformat(),
            "value": 18 + (index % 9) * 3 + index * 0.7,
            "raw_value": min(100, 18 + (index % 9) * 3 + index * 0.7),
        }
        for index in range(days)
    ]


def test_refresh_uses_editorial_articles_then_google_and_never_social(
    tmp_path, monkeypatch
) -> None:
    articles = [
        _article("elle-1", "ELLE", "elle", "https://elle.example/drop-waist"),
        _article(
            "mc-1",
            "Marie Claire",
            "marie-claire",
            "https://marie.example/drop-waist",
        ),
    ]

    def fake_collect(self, *, now=None):
        return {
            "articles": articles,
            "evidence": [],
            "source_status": {
                "elle": {
                    "publisher": "ELLE",
                    "state": "LIVE",
                    "errors": [],
                    "articles_loaded": 1,
                    "discovery_methods": ["publisher page"],
                },
                "marie-claire": {
                    "publisher": "Marie Claire",
                    "state": "LIVE",
                    "errors": [],
                    "articles_loaded": 1,
                    "discovery_methods": ["publisher page"],
                },
            },
            "publishers_requested": 7,
            "publishers_live": 2,
            "publishers_partial": 0,
            "publishers_failed": 5,
            "articles_loaded": 2,
        }

    class FakeOpenAI:
        usage_log = []

        def extract_editorial_trends(self, rows, *, batch_size=5):
            return [
                {
                    "article_id": row["article_id"],
                    "trends": [
                        {
                            "name": "Drop-Waist Dresses",
                            "google_query": "drop waist dress",
                            "category": "clothing",
                            "article_role": "central",
                            "evidence_excerpt": "Drop-waist dresses are returning for fall.",
                            "why_it_is_a_trend": "The article presents the silhouette as current.",
                            "confidence": 0.94,
                        }
                    ],
                }
                for row in rows
            ]

        def cluster_topic_phrases(self, candidates):
            return [
                {
                    "name": "Drop-Waist Dresses",
                    "aliases": ["Drop-Waist Dresses"],
                }
            ]

        def enrich_trends(self, trends):
            return trends

    google_calls: list[tuple[str, ...]] = []

    def fake_google_collect(self, terms, discovery_seeds=None):
        google_calls.append(tuple(terms))
        points = (
            _series(53, step_days=7)
            if self.timeframe == "today 12-m"
            else _series(90)
        )
        return {
            "series": {term: points for term in terms},
            "related": [],
            "warnings": [],
            "provider": "offline Google fixture",
            "requests_used": 1,
            "request_ceiling": 1,
        }

    monkeypatch.setattr(
        "src.pipeline.CommercialSourceCollector.collect", fake_collect
    )
    monkeypatch.setattr("src.pipeline._openai", lambda settings: FakeOpenAI())
    monkeypatch.setattr(
        "src.pipeline.GoogleTrendsConnector.collect", fake_google_collect
    )
    monkeypatch.setattr(
        "src.pipeline._collect_x",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("X must not run in editorial pipeline 4.0")
        ),
    )
    monkeypatch.setattr(
        "src.pipeline._collect_instagram_hashtags",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Instagram must not run in editorial pipeline 4.0")
        ),
    )

    snapshot = refresh_snapshot(
        Settings(
            snapshot_path=str(tmp_path / "snapshot.json"),
            openai_api_key="test-openai-key",
            serpapi_api_key="test-serpapi-key",
        ),
        persist=False,
        catalog_source="csv",
        catalog_products=[
            {
                "id": "drop-waist-product",
                "title": "Drop-Waist Dress",
                "status": "ACTIVE",
                "inventory": 1,
                "tags": ["drop waist dress"],
            }
        ],
        generate_editorial=False,
    )

    trend = snapshot["trends"][0]
    assert snapshot["meta"]["discovery_pipeline_version"] == "4.0"
    assert snapshot["meta"]["raw_counts"]["x_posts_collected"] == 0
    assert snapshot["meta"]["raw_counts"]["instagram_hashtags_returned"] == 0
    assert snapshot["meta"]["google_trends"]["seed_terms_used"] == 0
    assert google_calls == [
        ("drop waist dress",),
        ("drop waist dress",),
    ]
    assert trend["name"] == "Drop-Waist Dresses"
    assert trend["publisher_count"] == 2
    assert trend["google_query"] == "drop waist dress"
    assert trend["recent_chart_ready"] is True
    assert trend["chart_ready"] is True
    assert trend["business_action"] == "Test this week"
    assert snapshot["meta"]["editorial_articles"][0].get("paragraphs") is None
