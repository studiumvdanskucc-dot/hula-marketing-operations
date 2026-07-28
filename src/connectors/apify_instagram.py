from __future__ import annotations

import hashlib
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.analysis.freshness import parse_utc, validate_fresh_posts


class ApifyInstagramError(RuntimeError):
    pass


DEFAULT_ACTOR_ID = "apify~instagram-post-scraper"


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


def _number(value: Any) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24] if value else ""


def _publisher_key(value: str) -> str:
    """Canonicalise the same publisher handle across Instagram and X."""

    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _handle(value: Any) -> str:
    return str(value or "").strip().lstrip("@").casefold()


def _image_urls(record: dict[str, Any]) -> list[str]:
    output: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value.startswith(("https://", "http://")):
            output.append(value)
        elif isinstance(value, dict):
            add(
                value.get("displayUrl")
                or value.get("url")
                or value.get("imageUrl")
                or value.get("thumbnailUrl")
            )

    add(record.get("displayUrl"))
    add(record.get("imageUrl"))
    for value in record.get("images") or []:
        add(value)
    for child in record.get("childPosts") or []:
        add(child)
    return list(dict.fromkeys(output))[:10]


def normalize_instagram_post(
    record: dict[str, Any],
    *,
    account_weights: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Normalize one public Instagram post into the governed evidence schema."""

    caption = str(
        record.get("caption")
        or record.get("text")
        or record.get("description")
        or ""
    ).strip()
    alt = str(record.get("alt") or "").strip()
    hashtags = [
        str(value).strip().lstrip("#")
        for value in record.get("hashtags") or []
        if str(value).strip()
    ]
    text_parts = [caption]
    if hashtags:
        text_parts.append(" ".join(f"#{value}" for value in hashtags))
    if alt and alt.casefold() not in caption.casefold():
        text_parts.append(f"Image description: {alt}")
    text = "\n".join(part for part in text_parts if part).strip()
    if not text:
        return None

    created = parse_utc(
        record.get("timestamp")
        or record.get("createdAt")
        or record.get("created_at")
        or record.get("date")
    )
    username = _handle(
        record.get("ownerUsername")
        or record.get("username")
        or (record.get("owner") or {}).get("username")
    )
    weights = {_handle(key): float(value) for key, value in (account_weights or {}).items()}
    expert_weight = max(1.0, min(3.0, weights.get(username, 1.0)))
    media_urls = _image_urls(record)
    likes = _number(record.get("likesCount") or record.get("likes"))
    comments = _number(record.get("commentsCount") or record.get("comments"))
    views = _number(
        record.get("videoPlayCount")
        or record.get("videoViewCount")
        or record.get("views")
    )
    raw_id = str(
        record.get("id")
        or record.get("shortCode")
        or record.get("shortcode")
        or record.get("url")
        or ""
    ).strip()
    created_text = created.isoformat() if created is not None else ""
    post_basis = raw_id or "|".join((username, created_text, text.casefold()))
    url = str(record.get("url") or record.get("inputUrl") or "").strip()
    if not url and record.get("shortCode"):
        url = f"https://www.instagram.com/p/{record['shortCode']}/"
    is_priority = expert_weight >= 3

    return {
        "text": text,
        "created_at": created_text,
        "likes": likes,
        "reshares": 0,
        "replies": comments,
        "views": views,
        "engagement": likes + comments,
        "language": "",
        "author_hash": _hash(_publisher_key(username)),
        "post_hash": _hash(f"instagram|{post_basis}"),
        "is_probable_promo": bool(record.get("isSponsored")),
        "is_repost": False,
        "is_pinned": bool(record.get("isPinned") or record.get("is_pinned")),
        "is_expert": True,
        "expert_tier": (
            "commercial-priority" if is_priority else "instagram-specialist"
        ),
        "expert_tiers": [
            "commercial-priority" if is_priority else "instagram-specialist"
        ],
        "expert_weight": expert_weight,
        "evidence_channels": ["expert", "visual"] if media_urls else ["expert"],
        "listening_group": "instagram-commercial-panel",
        "listening_groups": ["instagram-commercial-panel"],
        "platform": "instagram",
        "source_account": username,
        "source_url": url,
        "media_urls": media_urls,
        "visual_terms": [],
    }


class ApifyInstagramConnector:
    base_url = "https://api.apify.com/v2"

    def __init__(
        self,
        token: str,
        *,
        actor_id: str = DEFAULT_ACTOR_ID,
        timeout_seconds: int = 480,
        memory_mb: int = 512,
    ) -> None:
        self.token = str(token or "").strip()
        self.actor_id = str(actor_id or DEFAULT_ACTOR_ID).strip().replace("/", "~")
        self.timeout_seconds = max(75, int(timeout_seconds))
        self.memory_mb = max(128, int(memory_mb))
        self.session = _session()

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
            raise ApifyInstagramError(
                f"Instagram Actor lookup failed ({response.status_code})."
            )
        actor = response.json().get("data") or {}
        return {
            "ok": True,
            "actor_name": actor.get("name") or self.actor_id,
            "actor_username": actor.get("username") or "apify",
        }

    @staticmethod
    def build_input(
        accounts: Iterable[str],
        *,
        results_per_profile: int = 15,
        cutoff: datetime | None = None,
    ) -> dict[str, Any]:
        profiles = [
            _handle(account)
            for account in accounts
            if _handle(account)
        ]
        cutoff_at = (
            cutoff
            or datetime.now(tz=timezone.utc) - timedelta(days=14)
        ).astimezone(timezone.utc)
        return {
            "username": list(dict.fromkeys(profiles)),
            "resultsLimit": max(1, int(results_per_profile)),
            "skipPinnedPosts": True,
            "onlyPostsNewerThan": cutoff_at.date().isoformat(),
            "dataDetailLevel": "basicData",
        }

    def collect(
        self,
        accounts: Iterable[str],
        *,
        account_weights: dict[str, float],
        results_per_profile: int = 15,
        max_total_charge_usd: float = 0.75,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
        actor_input = self.build_input(
            accounts,
            results_per_profile=results_per_profile,
            cutoff=reference - timedelta(days=14),
        )
        platform_timeout = max(60, self.timeout_seconds - 15)
        params: dict[str, Any] = {
            "waitForFinish": 60,
            "timeout": platform_timeout,
            "memory": self.memory_mb,
            "restartOnError": "false",
            "maxItems": max(
                1,
                len(actor_input["username"]) * max(1, int(results_per_profile)),
            ),
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
            raise ApifyInstagramError(
                f"Instagram Actor could not start ({response.status_code})"
                + (f": {detail[:220]}" if detail else ".")
            )
        run = response.json().get("data") or {}
        run_id = str(run.get("id") or "")
        if not run_id:
            raise ApifyInstagramError("Apify did not return an Instagram run ID.")

        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            status = str(run.get("status") or "")
            if status == "SUCCEEDED":
                break
            if status in {"FAILED", "ABORTED", "TIMED-OUT"}:
                raise ApifyInstagramError(
                    f"Instagram Actor ended with status {status}."
                )
            time.sleep(3)
            status_response = self.session.get(
                f"{self.base_url}/actor-runs/{run_id}",
                headers=self.headers,
                timeout=30,
            )
            if not status_response.ok:
                raise ApifyInstagramError(
                    f"Instagram run status failed ({status_response.status_code})."
                )
            run = status_response.json().get("data") or {}
        else:
            self.session.post(
                f"{self.base_url}/actor-runs/{run_id}/abort",
                headers=self.headers,
                timeout=30,
            )
            raise ApifyInstagramError(
                "Instagram collection exceeded the app timeout and was stopped."
            )

        dataset_id = str(run.get("defaultDatasetId") or "")
        raw_items = self._dataset_items(dataset_id) if dataset_id else []
        normalized = [
            post
            for record in raw_items
            if (
                post := normalize_instagram_post(
                    record,
                    account_weights=account_weights,
                )
            )
            and not post.get("is_pinned")
        ]
        posts, freshness = validate_fresh_posts(normalized, now=reference)
        counts = Counter(str(post.get("source_account") or "unknown") for post in posts)
        requested = list(actor_input["username"])
        returned = sorted(handle for handle in counts if handle != "unknown")
        usage = run.get("usageTotalUsd")
        try:
            usage_usd = round(float(usage), 6) if usage is not None else None
        except (TypeError, ValueError):
            usage_usd = None
        return {
            "posts": posts,
            "freshness": freshness,
            "requested_profiles": requested,
            "returned_profiles": returned,
            "missing_profiles": sorted(set(requested) - set(returned)),
            "profile_counts": dict(sorted(counts.items())),
            "run_id": run_id,
            "usage_usd": usage_usd,
            "items_returned": len(raw_items),
            "items_accepted": len(posts),
            "actor_input": {
                "resultsLimit": actor_input["resultsLimit"],
                "skipPinnedPosts": True,
                "onlyPostsNewerThan": actor_input["onlyPostsNewerThan"],
                "dataDetailLevel": actor_input["dataDetailLevel"],
            },
        }

    def _dataset_items(self, dataset_id: str) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self.session.get(
                f"{self.base_url}/datasets/{dataset_id}/items",
                headers=self.headers,
                params={
                    "clean": "true",
                    "format": "json",
                    "limit": 1000,
                    "offset": offset,
                },
                timeout=60,
            )
            if not response.ok:
                raise ApifyInstagramError(
                    f"Instagram dataset download failed ({response.status_code})."
                )
            batch = response.json()
            if not isinstance(batch, list):
                break
            output.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < 1000:
                break
            offset += len(batch)
        return output
