from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.analysis.freshness import parse_utc


class SupabaseStoreError(RuntimeError):
    pass


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


class SupabaseStore:
    """Small server-side PostgREST client for aggregate HULA history."""

    def __init__(
        self,
        url: str,
        secret_key: str,
        *,
        snapshot_table: str = "hula_trend_snapshots",
        blog_table: str = "hula_blog_drafts",
        timeout_seconds: int = 45,
    ) -> None:
        self.url = str(url or "").rstrip("/")
        self.secret_key = str(secret_key or "")
        self.snapshot_table = str(snapshot_table or "hula_trend_snapshots")
        self.blog_table = str(blog_table or "hula_blog_drafts")
        self.timeout_seconds = max(10, int(timeout_seconds))
        self.session = _session()

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "apikey": self.secret_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "HULA-Trend-Intelligence/2026.07",
        }
        # Legacy service_role keys are JWTs. New sb_secret_ keys authenticate
        # through the apikey header and must not be treated as a user JWT.
        if self.secret_key and not self.secret_key.startswith("sb_secret_"):
            headers["Authorization"] = f"Bearer {self.secret_key}"
        return headers

    def _endpoint(self, table: str) -> str:
        if not self.url:
            raise SupabaseStoreError("SUPABASE_URL is missing.")
        if not self.secret_key:
            raise SupabaseStoreError("SUPABASE_SECRET_KEY is missing.")
        return f"{self.url}/rest/v1/{table}"

    def _raise(self, response: requests.Response, operation: str) -> None:
        if response.ok:
            return
        detail = ""
        try:
            payload = response.json()
            detail = str(payload.get("message") or payload.get("hint") or "")
        except (TypeError, ValueError):
            detail = response.text[:240]
        if response.status_code in {404, 406} or "schema cache" in detail.casefold():
            raise SupabaseStoreError(
                f"{operation} could not find the HULA tables. Run supabase/schema.sql "
                "once in the Supabase SQL Editor."
            )
        raise SupabaseStoreError(
            f"{operation} failed ({response.status_code})"
            + (f": {detail[:260]}" if detail else ".")
        )

    def test_connection(self) -> dict[str, Any]:
        response = self.session.get(
            self._endpoint(self.snapshot_table),
            headers=self.headers,
            params={"select": "id", "limit": 1},
            timeout=self.timeout_seconds,
        )
        self._raise(response, "Supabase connection test")
        rows = response.json()
        return {
            "ok": True,
            "snapshot_table": self.snapshot_table,
            "rows_visible": len(rows) if isinstance(rows, list) else 0,
        }

    def save_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        meta = snapshot.get("meta") or {}
        generated_at = parse_utc(meta.get("generated_at")) or datetime.now(
            tz=timezone.utc
        )
        row = {
            "week_start": (
                generated_at.date() - timedelta(days=generated_at.weekday())
            ).isoformat(),
            "generated_at": generated_at.isoformat(),
            "mode": str(meta.get("mode") or "hybrid"),
            "source_status": meta.get("source_status") or {},
            "payload": snapshot,
        }
        headers = {
            **self.headers,
            "Prefer": "resolution=merge-duplicates,return=representation",
        }
        response = self.session.post(
            self._endpoint(self.snapshot_table),
            headers=headers,
            params={"on_conflict": "week_start"},
            json=[row],
            timeout=self.timeout_seconds,
        )
        self._raise(response, "Supabase snapshot save")
        rows = response.json() if response.content else []
        saved = rows[0] if isinstance(rows, list) and rows else row
        return {
            "ok": True,
            "id": saved.get("id"),
            "week_start": row["week_start"],
            "generated_at": row["generated_at"],
        }

    def load_latest_snapshot(self) -> dict[str, Any] | None:
        response = self.session.get(
            self._endpoint(self.snapshot_table),
            headers=self.headers,
            params={
                "select": "payload,generated_at",
                "order": "generated_at.desc",
                "limit": 1,
            },
            timeout=self.timeout_seconds,
        )
        self._raise(response, "Supabase latest-snapshot read")
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            return None
        payload = rows[0].get("payload")
        return payload if isinstance(payload, dict) else None

    def recent_trend_presence(self, *, weeks: int = 4) -> dict[str, int]:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max(1, weeks) * 7 + 2)
        response = self.session.get(
            self._endpoint(self.snapshot_table),
            headers=self.headers,
            params={
                "select": "payload",
                "generated_at": f"gte.{cutoff.isoformat()}",
                "order": "generated_at.desc",
                "limit": max(1, weeks + 1),
            },
            timeout=self.timeout_seconds,
        )
        self._raise(response, "Supabase trend-history read")
        rows = response.json()
        presence: Counter[str] = Counter()
        for row in rows if isinstance(rows, list) else []:
            payload = row.get("payload") or {}
            for trend in payload.get("trends") or []:
                trend_id = str(trend.get("id") or "").strip()
                if trend_id:
                    presence[trend_id] += 1
        return dict(presence)

    def save_blog(self, blog: dict[str, Any]) -> dict[str, Any]:
        generated_at = parse_utc(blog.get("generated_at")) or datetime.now(
            tz=timezone.utc
        )
        row = {
            "generated_at": generated_at.isoformat(),
            "trend_id": str(blog.get("trend_id") or ""),
            "reason": str(blog.get("reason") or ""),
            "title": str(blog.get("title") or "Untitled HULA draft"),
            "draft": blog,
        }
        response = self.session.post(
            self._endpoint(self.blog_table),
            headers={**self.headers, "Prefer": "return=representation"},
            json=[row],
            timeout=self.timeout_seconds,
        )
        self._raise(response, "Supabase blog save")
        rows = response.json() if response.content else []
        saved = rows[0] if isinstance(rows, list) and rows else row
        return {
            "ok": True,
            "id": saved.get("id"),
            "generated_at": row["generated_at"],
        }
