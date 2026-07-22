from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.connectors.apify_runtime import (
    ApifyCapacityError,
    TERMINAL_RUN_STATUSES,
    abort_run,
    abort_target_runs,
    actor_memory_mb,
    apify_error_detail,
    capacity_message,
    is_capacity_failure,
    target_run_report,
)


class ApifyError(RuntimeError):
    pass


TEXT_FIELDS = ("text", "fullText", "full_text", "tweetText", "content", "body")
DATE_FIELDS = ("createdAt", "created_at", "date", "timestamp", "publishedAt")
POST_ID_FIELDS = ("id", "tweet_id", "tweetId", "rest_id", "status_id")
LIKE_FIELDS = ("likeCount", "likes", "favorite_count", "favoriteCount")
RESHARE_FIELDS = (
    "retweetCount",
    "retweets",
    "retweet_count",
    "repostCount",
    "shares",
)
REPLY_FIELDS = ("replyCount", "replies", "reply_count")
VIEW_FIELDS = ("viewCount", "views", "view_count", "impressions")
LANGUAGE_FIELDS = ("lang", "language")
AUTHOR_ID_FIELDS = ("user_id", "userId", "author_id", "authorId")
AUTHOR_NAME_FIELDS = (
    "username",
    "userName",
    "screen_name",
    "screenName",
    "handle",
)
PROMOTIONAL_MARKERS = (
    "affiliate",
    "discount code",
    "free shipping",
    "link in bio",
    "shop now",
    "sponsored",
    "use code",
)


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _record_candidates(record: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [record]
    for nested in ("tweet", "data", "item", "legacy"):
        value = record.get(nested)
        if isinstance(value, dict):
            candidates.append(value)
    return candidates


def _first(record: dict[str, Any], fields: tuple[str, ...], default: Any = None) -> Any:
    for candidate in _record_candidates(record):
        for field in fields:
            value = candidate.get(field)
            if value not in (None, ""):
                return value
    return default


def _author_identifier(record: dict[str, Any]) -> str:
    for candidate in _record_candidates(record):
        for field in (*AUTHOR_ID_FIELDS, *AUTHOR_NAME_FIELDS):
            value = candidate.get(field)
            if value not in (None, ""):
                return str(value)
        for nested in ("user", "author", "account", "user_info"):
            value = candidate.get(nested)
            if not isinstance(value, dict):
                continue
            for field in ("id", "rest_id", *AUTHOR_ID_FIELDS, *AUTHOR_NAME_FIELDS):
                identifier = value.get(field)
                if identifier not in (None, ""):
                    return str(identifier)
    return ""


def _number(value: Any) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _iso_date(value: Any) -> str:
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    if value:
        return str(value)
    return datetime.now(tz=timezone.utc).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24] if value else ""


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def normalize_post(record: dict[str, Any]) -> dict[str, Any] | None:
    text = str(_first(record, TEXT_FIELDS, "")).strip()
    if not text:
        return None
    created_at = _iso_date(_first(record, DATE_FIELDS))
    likes = _number(_first(record, LIKE_FIELDS, 0))
    reshares = _number(_first(record, RESHARE_FIELDS, 0))
    replies = _number(_first(record, REPLY_FIELDS, 0))
    views = _number(_first(record, VIEW_FIELDS, 0))
    author_hash = _hash(_author_identifier(record).strip().lower())
    raw_post_id = str(_first(record, POST_ID_FIELDS, "")).strip()
    post_basis = raw_post_id or "|".join((text.lower(), created_at, author_hash))
    lowered = text.lower()
    promo_hits = sum(marker in lowered for marker in PROMOTIONAL_MARKERS)
    is_repost = _truthy(_first(record, ("is_retweet", "isRetweet", "retweeted"), False))
    if lowered.startswith("rt @"):
        is_repost = True
    return {
        "text": text,
        "created_at": created_at,
        "likes": likes,
        "reshares": reshares,
        "replies": replies,
        "views": views,
        "engagement": likes + (2 * reshares) + replies,
        "language": str(_first(record, LANGUAGE_FIELDS, "")),
        "author_hash": author_hash,
        "post_hash": _hash(post_basis),
        "is_probable_promo": promo_hits >= 2,
        "is_repost": is_repost,
    }


def _usage_usd(run: dict[str, Any]) -> float | None:
    for value in (
        run.get("usageTotalUsd"),
        (run.get("usage") or {}).get("totalUsd")
        if isinstance(run.get("usage"), dict)
        else None,
    ):
        try:
            return round(float(value), 6)
        except (TypeError, ValueError):
            continue
    return None


class ApifyXConnector:
    base_url = "https://api.apify.com/v2"

    def __init__(
        self,
        token: str,
        task_id: str,
        timeout_seconds: int = 480,
        memory_mb: int = 512,
    ) -> None:
        self.token = token
        self.task_id = task_id
        self.timeout_seconds = max(75, int(timeout_seconds))
        self.memory_mb = actor_memory_mb(memory_mb, 512)
        self.session = _session()

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def test_connection(self) -> dict[str, Any]:
        response = self.session.get(
            f"{self.base_url}/actor-tasks/{quote(self.task_id, safe='~')}",
            headers=self.headers,
            timeout=30,
        )
        if not response.ok:
            raise ApifyError(f"Apify task lookup failed ({response.status_code}).")
        task = response.json().get("data") or {}
        actor_username = str(task.get("actUsername") or "")
        actor_name = str(task.get("actName") or "")
        actor_reference = "/".join(value for value in (actor_username, actor_name) if value)
        return {
            "ok": True,
            "task_name": task.get("name", self.task_id),
            "actor_name": actor_name,
            "actor_username": actor_username,
            "actor_reference": actor_reference,
            "scrapebadger_compatible": actor_reference.lower()
            == "scrape.badger/twitter-tweets-scraper",
        }

    def _task_path(self) -> str:
        return f"actor-tasks/{quote(self.task_id, safe='~')}"

    def active_run_report(self) -> dict[str, Any]:
        return target_run_report(
            self.session,
            self.base_url,
            self.headers,
            self._task_path(),
        )

    def stop_active_runs(self) -> dict[str, int]:
        return abort_target_runs(
            self.session,
            self.base_url,
            self.headers,
            self._task_path(),
        )

    def _abort_run(self, run_id: str) -> bool:
        return abort_run(self.session, self.base_url, self.headers, run_id)

    def _run_with_meta(
        self,
        task_input: dict[str, Any] | None = None,
        *,
        max_items: int | None = None,
        max_total_charge_usd: float | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        platform_timeout = max(60, self.timeout_seconds - 15)
        params: dict[str, Any] = {
            "waitForFinish": 60,
            "timeout": platform_timeout,
            "memory": self.memory_mb,
            "restartOnError": "false",
        }
        if max_items and max_items > 0:
            params["maxItems"] = int(max_items)
        if max_total_charge_usd and max_total_charge_usd > 0:
            params["maxTotalChargeUsd"] = float(max_total_charge_usd)
        response = self.session.post(
            f"{self.base_url}/{self._task_path()}/runs",
            headers=self.headers,
            params=params,
            json=task_input or {},
            timeout=75,
        )
        if not response.ok:
            error_type, detail = apify_error_detail(response)
            if is_capacity_failure(response.status_code, error_type, detail):
                raise ApifyCapacityError(capacity_message(detail))
            raise ApifyError(
                f"Apify task could not start ({response.status_code})"
                + (f": {detail[:220]}" if detail else ".")
            )
        run = response.json().get("data") or {}
        run_id = run.get("id")
        if not run_id:
            raise ApifyError("Apify did not return a run ID.")
        deadline = time.monotonic() + self.timeout_seconds
        last_status = str(run.get("status") or "")
        try:
            while time.monotonic() < deadline:
                last_status = str(run.get("status") or "")
                if last_status == "SUCCEEDED":
                    dataset_id = run.get("defaultDatasetId")
                    posts = self._dataset_items(str(dataset_id)) if dataset_id else []
                    return posts, {
                        "run_id": run_id,
                        "status": last_status,
                        "dataset_id": dataset_id,
                        "usage_usd": _usage_usd(run),
                        "items": len(posts),
                        "memory_mb": self.memory_mb,
                    }
                if last_status in {"FAILED", "ABORTED", "TIMED-OUT"}:
                    raise ApifyError(f"Apify task ended with status {last_status}.")
                time.sleep(3)
                status_response = self.session.get(
                    f"{self.base_url}/actor-runs/{run_id}",
                    headers=self.headers,
                    timeout=30,
                )
                if not status_response.ok:
                    raise ApifyError(
                        f"Apify run status failed ({status_response.status_code})."
                    )
                run = status_response.json().get("data") or {}
            stopped = self._abort_run(str(run_id))
            last_status = "ABORTED" if stopped else last_status
            raise ApifyError(
                "Apify task exceeded the app timeout and was stopped automatically."
                if stopped
                else (
                    "Apify task exceeded the app timeout and could not be stopped automatically. "
                    "Stop it from Data & Setup before refreshing again."
                )
            )
        except BaseException:
            if last_status not in TERMINAL_RUN_STATUSES:
                self._abort_run(str(run_id))
            raise

    def run(self, task_input: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        posts, _ = self._run_with_meta(task_input)
        return posts

    def run_listening_plan(
        self,
        plan: list[dict[str, Any]],
        *,
        base_task_input: dict[str, Any] | None = None,
        max_total_charge_usd: float = 0.25,
    ) -> dict[str, Any]:
        """Run independent query windows and keep useful partial results on failure."""

        all_posts: list[dict[str, Any]] = []
        runs: list[dict[str, Any]] = []
        warnings: list[str] = []
        skipped_for_capacity = 0
        for index, specification in enumerate(plan):
            search_input = {
                **(base_task_input or {}),
                **dict(specification.get("input") or {}),
            }
            max_results = int(search_input.get("max_results") or 0)
            try:
                posts, run_meta = self._run_with_meta(
                    search_input,
                    max_items=max_results or None,
                    max_total_charge_usd=max_total_charge_usd,
                )
                channel = "expert" if specification.get("is_expert") else "open"
                for post in posts:
                    post["listening_group"] = str(specification.get("group", "topic"))
                    post["listening_groups"] = [post["listening_group"]]
                    post["listening_window"] = str(specification.get("window", ""))
                    post["is_expert"] = channel == "expert"
                    post["evidence_channels"] = [channel]
                all_posts.extend(posts)
                runs.append(
                    {
                        "id": specification.get("id"),
                        "group": specification.get("group"),
                        "window": specification.get("window"),
                        "status": "succeeded",
                        "items": len(posts),
                        "usage_usd": run_meta.get("usage_usd"),
                    }
                )
            except ApifyCapacityError as exc:
                label = str(specification.get("id", "search"))
                remaining = max(0, len(plan) - index - 1)
                warnings.append(
                    f"X listening stopped at {label}: {exc} "
                    f"The remaining {remaining} search(es) were not attempted."
                )
                runs.append(
                    {
                        "id": specification.get("id"),
                        "group": specification.get("group"),
                        "window": specification.get("window"),
                        "status": "failed",
                        "items": 0,
                        "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    }
                )
                skipped_for_capacity = remaining
                runs.extend(
                    {
                        "id": row.get("id"),
                        "group": row.get("group"),
                        "window": row.get("window"),
                        "status": "skipped_capacity",
                        "items": 0,
                    }
                    for row in plan[index + 1 :]
                )
                break
            except Exception as exc:
                label = str(specification.get("id", "search"))
                warnings.append(f"X search {label}: {exc}")
                runs.append(
                    {
                        "id": specification.get("id"),
                        "group": specification.get("group"),
                        "window": specification.get("window"),
                        "status": "failed",
                        "items": 0,
                        "error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    }
                )
        usage_values = [float(run["usage_usd"]) for run in runs if run.get("usage_usd") is not None]
        return {
            "posts": all_posts,
            "runs": runs,
            "warnings": warnings,
            "planned": len(plan),
            "succeeded": sum(run.get("status") == "succeeded" for run in runs),
            "failed": sum(run.get("status") == "failed" for run in runs),
            "skipped_capacity": skipped_for_capacity,
            "usage_usd": round(sum(usage_values), 6) if usage_values else None,
        }

    def _dataset_items(self, dataset_id: str) -> list[dict[str, Any]]:
        raw_items: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self.session.get(
                f"{self.base_url}/datasets/{dataset_id}/items",
                headers=self.headers,
                params={"clean": "true", "format": "json", "limit": 1000, "offset": offset},
                timeout=60,
            )
            if not response.ok:
                raise ApifyError(
                    f"Apify dataset download failed ({response.status_code})."
                )
            batch = response.json()
            if not isinstance(batch, list):
                break
            raw_items.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 1000:
                break
            offset += len(batch)
        return [post for item in raw_items if (post := normalize_post(item))]
