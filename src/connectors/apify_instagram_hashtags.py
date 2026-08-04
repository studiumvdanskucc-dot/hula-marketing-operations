from __future__ import annotations

import math
import re
import time
from typing import Any, Iterable
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.analysis.trends import canonical_name, generic_trend_reason, slugify


class InstagramHashtagError(RuntimeError):
    pass


DEFAULT_ACTOR_ID = "apify~instagram-hashtag-analytics-scraper"


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def hashtag_for_trend(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())[:80]


def parse_compact_number(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if math.isfinite(number) and number >= 0 else 0.0
    raw = str(value or "").strip().casefold().replace(",", "")
    if not raw:
        return 0.0
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*([kmbg]?)", raw)
    if not match:
        return 0.0
    number = max(0.0, float(match.group(1)))
    multiplier = {
        "": 1.0,
        "k": 1_000.0,
        "m": 1_000_000.0,
        "b": 1_000_000_000.0,
        "g": 1_000_000_000.0,
    }[match.group(2)]
    return number * multiplier


def normalize_hashtag_metric(
    record: dict[str, Any],
    *,
    trend_by_hashtag: dict[str, dict[str, str]],
) -> dict[str, Any] | None:
    hashtag = hashtag_for_trend(
        record.get("name")
        or record.get("id")
        or record.get("hashtag")
        or record.get("searchTerm")
        or record.get("query")
    )
    trend = trend_by_hashtag.get(hashtag)
    if not hashtag or trend is None:
        return None
    related_rows: list[dict[str, Any]] = []
    related_source = (
        record.get("related")
        or record.get("relatedHashtags")
        or record.get("frequent")
        or []
    )
    for item in related_source:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            continue
        related = hashtag_for_trend(
            item.get("hash") or item.get("name") or item.get("hashtag")
        )
        if not related:
            continue
        related_rows.append(
            {
                "hashtag": related,
                "posts_count": int(
                    parse_compact_number(
                        item.get("info")
                        or item.get("postsCount")
                        or item.get("posts")
                    )
                ),
            }
        )
        if len(related_rows) >= 8:
            break
    return {
        "id": trend["id"],
        "name": trend["name"],
        "hashtag": hashtag,
        "posts_count": int(
            parse_compact_number(
                record.get("postsCount")
                or record.get("postCount")
                or record.get("totalPosts")
                or record.get("mediaCount")
                or record.get("posts")
            )
        ),
        "posts_per_day": round(
            parse_compact_number(
                record.get("postsPerDay")
                or record.get("averagePostsPerDay")
                or record.get("postFrequency")
            ),
            2,
        ),
        "related_hashtags": related_rows,
        "metric_scope": "public aggregate hashtag metadata",
    }


def _rank_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [65.0]
    order = sorted(range(len(values)), key=lambda index: values[index])
    output = [0.0] * len(values)
    for rank, index in enumerate(order):
        output[index] = 20.0 + 70.0 * rank / (len(values) - 1)
    return output


def score_hashtag_metrics(metrics: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in metrics]
    if not rows:
        return []
    lifetime_rank = _rank_scores(
        [math.log1p(float(row.get("posts_count") or 0)) for row in rows]
    )
    daily_values = [float(row.get("posts_per_day") or 0) for row in rows]
    has_daily = any(value > 0 for value in daily_values)
    daily_rank = _rank_scores([math.log1p(value) for value in daily_values])
    for index, row in enumerate(rows):
        if has_daily:
            score = 0.70 * daily_rank[index] + 0.30 * lifetime_rank[index]
        else:
            score = lifetime_rank[index]
        row["instagram_score"] = round(score, 1)
        row["instagram_hashtag_score"] = round(score, 1)
        row["activity_available"] = bool(row.get("posts_per_day"))
        row["directional_only"] = True
    return sorted(
        rows,
        key=lambda row: float(row.get("instagram_score") or 0),
        reverse=True,
    )


class InstagramHashtagAnalyticsConnector:
    """Collect aggregate hashtag reach without returning or storing posts."""

    base_url = "https://api.apify.com/v2"

    def __init__(
        self,
        token: str,
        *,
        actor_id: str = DEFAULT_ACTOR_ID,
        timeout_seconds: int = 480,
        memory_mb: int = 512,
        session: requests.Session | None = None,
    ) -> None:
        self.token = str(token or "").strip()
        self.actor_id = str(actor_id or DEFAULT_ACTOR_ID).strip().replace("/", "~")
        self.timeout_seconds = max(75, int(timeout_seconds))
        self.memory_mb = max(128, int(memory_mb))
        self.session = session or _session()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/acts/{quote(self.actor_id, safe='~')}",
            headers=self.headers,
            timeout=30,
        )
        if not response.ok:
            raise InstagramHashtagError(
                f"Instagram hashtag Actor lookup failed ({response.status_code})."
            )
        actor = response.json().get("data") or {}
        return {
            "ok": True,
            "actor_name": actor.get("name") or self.actor_id,
            "actor_username": actor.get("username") or "apify",
            "mode": "aggregate hashtag metadata only",
        }

    @staticmethod
    def build_input(hashtags: Iterable[str]) -> dict[str, Any]:
        cleaned = [hashtag_for_trend(value) for value in hashtags]
        cleaned = [value for value in dict.fromkeys(cleaned) if value]
        return {
            "hashtags": cleaned,
            "includeLatestPosts": False,
            "includeTopPosts": False,
        }

    def _dataset_items(self, dataset_id: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self.session.get(
                f"{self.base_url}/datasets/{dataset_id}/items",
                headers=self.headers,
                params={"clean": "true", "format": "json", "limit": 250, "offset": offset},
                timeout=60,
            )
            if not response.ok:
                raise InstagramHashtagError(
                    f"Instagram hashtag dataset failed ({response.status_code})."
                )
            page = response.json()
            if not isinstance(page, list):
                break
            output.extend(item for item in page if isinstance(item, dict))
            if len(page) < 250:
                break
            offset += len(page)
        return output

    def collect(
        self,
        trends: Iterable[dict[str, Any]],
        *,
        max_terms: int = 8,
        max_total_charge_usd: float = 0.25,
    ) -> dict[str, Any]:
        trend_by_hashtag: dict[str, dict[str, str]] = {}
        for row in trends:
            name = canonical_name(str(row.get("name") or ""))
            if generic_trend_reason(name):
                continue
            hashtag = hashtag_for_trend(name)
            if hashtag and hashtag not in trend_by_hashtag:
                trend_by_hashtag[hashtag] = {"id": slugify(name), "name": name}
            if len(trend_by_hashtag) >= max(1, int(max_terms)):
                break
        actor_input = self.build_input(trend_by_hashtag)
        if not actor_input["hashtags"]:
            return {
                "metrics": [],
                "hashtags_requested": [],
                "hashtags_returned": [],
                "usage_usd": None,
                "items_returned": 0,
            }

        params: dict[str, Any] = {
            "waitForFinish": 60,
            "timeout": max(60, self.timeout_seconds - 15),
            "memory": self.memory_mb,
            "restartOnError": "false",
            "maxItems": len(actor_input["hashtags"]),
        }
        if max_total_charge_usd > 0:
            params["maxTotalChargeUsd"] = float(max_total_charge_usd)
        response = self.session.post(
            f"{self.base_url}/acts/{quote(self.actor_id, safe='~')}/runs",
            headers=self.headers,
            params=params,
            json=actor_input,
            timeout=75,
        )
        if not response.ok:
            detail = ""
            try:
                detail = str((response.json().get("error") or {}).get("message") or "")
            except (TypeError, ValueError):
                detail = response.text[:220]
            raise InstagramHashtagError(
                f"Instagram hashtag Actor could not start ({response.status_code})"
                + (f": {detail[:220]}" if detail else ".")
            )
        run = response.json().get("data") or {}
        run_id = str(run.get("id") or "")
        if not run_id:
            raise InstagramHashtagError("Apify did not return a hashtag run ID.")

        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            status = str(run.get("status") or "")
            if status == "SUCCEEDED":
                break
            if status in {"FAILED", "ABORTED", "TIMED-OUT"}:
                raise InstagramHashtagError(
                    f"Instagram hashtag Actor ended with status {status}."
                )
            time.sleep(3)
            status_response = self.session.get(
                f"{self.base_url}/actor-runs/{run_id}",
                headers=self.headers,
                timeout=30,
            )
            if not status_response.ok:
                raise InstagramHashtagError(
                    f"Instagram hashtag run status failed ({status_response.status_code})."
                )
            run = status_response.json().get("data") or {}
        else:
            self.session.post(
                f"{self.base_url}/actor-runs/{run_id}/abort",
                headers=self.headers,
                timeout=30,
            )
            raise InstagramHashtagError(
                "Instagram hashtag collection exceeded the app timeout and was stopped."
            )

        dataset_id = str(run.get("defaultDatasetId") or "")
        raw_items = self._dataset_items(dataset_id) if dataset_id else []
        normalized = [
            metric
            for record in raw_items
            if (
                metric := normalize_hashtag_metric(
                    record,
                    trend_by_hashtag=trend_by_hashtag,
                )
            )
        ]
        # A retried Actor run can occasionally return the same hashtag twice.
        # Keep the richest aggregate row without ever retaining post-level data.
        metric_by_hashtag: dict[str, dict[str, Any]] = {}
        for metric in normalized:
            hashtag = str(metric.get("hashtag") or "")
            current = metric_by_hashtag.get(hashtag)
            value = (
                float(metric.get("posts_per_day") or 0),
                int(metric.get("posts_count") or 0),
            )
            current_value = (
                float((current or {}).get("posts_per_day") or 0),
                int((current or {}).get("posts_count") or 0),
            )
            if current is None or value > current_value:
                metric_by_hashtag[hashtag] = metric
        metrics = list(metric_by_hashtag.values())
        usage = run.get("usageTotalUsd")
        try:
            usage_usd = round(float(usage), 6) if usage is not None else None
        except (TypeError, ValueError):
            usage_usd = None
        returned = sorted(str(row.get("hashtag") or "") for row in metrics)
        requested = list(actor_input["hashtags"])
        return {
            "metrics": score_hashtag_metrics(metrics),
            "hashtags_requested": requested,
            "hashtags_returned": returned,
            "missing_hashtags": sorted(set(requested) - set(returned)),
            "usage_usd": usage_usd,
            "run_id": run_id,
            "items_returned": len(raw_items),
            "items_normalized": len(metrics),
            "unmatched_items": max(0, len(raw_items) - len(normalized)),
            "returned_fields": sorted(
                {
                    str(key)
                    for item in raw_items
                    for key in item.keys()
                }
            )[:30],
            "privacy_mode": "aggregate metadata; top/latest posts disabled",
        }
