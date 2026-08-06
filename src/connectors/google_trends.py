from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class GoogleTrendsError(RuntimeError):
    pass


DEFAULT_SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
WORLDWIDE_GEO_ALIASES = {"", "GLOBAL", "WORLD", "WORLDWIDE", "ALL"}


def normalize_google_geo(value: Any) -> str:
    """Return a Google Trends country code, or blank for worldwide data."""

    cleaned = str(value or "").strip().upper()
    return "" if cleaned in WORLDWIDE_GEO_ALIASES else cleaned


def google_market_label(value: Any) -> str:
    """Return a human-readable market label without changing the API value."""

    return normalize_google_geo(value) or "Worldwide"


def _batches(terms: list[str], anchor: str, batch_size: int = 4) -> list[list[str]]:
    """Build Google Trends comparisons of one anchor plus at most four terms."""

    cleaned = [
        term
        for term in dict.fromkeys(str(term).strip() for term in terms)
        if term and term != anchor
    ]
    return [
        [anchor, *cleaned[index : index + batch_size]]
        for index in range(0, len(cleaned), batch_size)
    ]


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _point_date(point: dict[str, Any]) -> str:
    raw = point.get("timestamp") or point.get("time")
    try:
        stamp = float(raw)
        if stamp > 10_000_000_000:
            stamp /= 1000
        return datetime.fromtimestamp(stamp, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return str(point.get("date") or "")


def normalize_serpapi_interest(
    payloads: list[dict[str, Any]],
    requested_batches: list[list[str]],
    anchor_term: str,
) -> dict[str, list[dict[str, Any]]]:
    """Normalize SerpApi's Google Trends timelines and align comparison batches.

    Google normalizes each comparison independently. Repeating one anchor in every
    request gives the app a stable approximation for comparing terms across batches.
    """

    series: dict[str, list[dict[str, Any]]] = {}
    for index, payload in enumerate(payloads):
        batch = requested_batches[index] if index < len(requested_batches) else []
        timeline = (payload.get("interest_over_time") or {}).get("timeline_data") or []
        if not batch or not isinstance(timeline, list):
            continue

        raw_points: dict[str, list[tuple[str, float]]] = {term: [] for term in batch}
        for point in timeline:
            if not isinstance(point, dict):
                continue
            date = _point_date(point)
            values = point.get("values") or []
            by_query: dict[str, float] = {}
            for value in values:
                if not isinstance(value, dict):
                    continue
                query = str(value.get("query") or "").strip().casefold()
                number = _as_float(
                    value.get("extracted_value", value.get("value", 0))
                )
                if query:
                    by_query[query] = number

            for term in batch:
                number = by_query.get(term.casefold())
                if number is not None:
                    raw_points[term].append((date, number))

        anchor_values = [value for _, value in raw_points.get(anchor_term, []) if value > 0]
        anchor_mean = sum(anchor_values) / len(anchor_values) if anchor_values else 0.0
        calibration = 50.0 / anchor_mean if anchor_mean else 1.0
        for term in batch:
            if term == anchor_term or not raw_points.get(term):
                continue
            points = [
                {
                    "date": date,
                    "value": round(value * calibration, 2),
                    "raw_value": round(value, 2),
                }
                for date, value in raw_points[term]
            ]
            if len(points) > len(series.get(term, [])):
                series[term] = points
    return series


def normalize_serpapi_related(
    payloads: list[dict[str, Any]],
    seeds: list[str],
    *,
    limit: int = 15,
) -> list[dict[str, Any]]:
    discoveries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, payload in enumerate(payloads):
        if index >= len(seeds):
            break
        seed = seeds[index]
        related = payload.get("related_queries") or {}
        rows = related.get("rising") or related.get("top") or []
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            query = str(row.get("query") or "").strip()
            key = (seed.casefold(), query.casefold())
            if not query or key in seen or count >= max(1, int(limit)):
                continue
            seen.add(key)
            count += 1
            discoveries.append(
                {
                    "query": query,
                    "value": row.get("extracted_value", row.get("value", 0)),
                    "seed": seed,
                }
            )
    return discoveries


def _friendly_failure(provider: str, exc: BaseException) -> str:
    detail = str(exc).strip() or "No additional detail was returned."
    lowered = detail.lower()
    if "api key" in lowered or "401" in lowered or "403" in lowered:
        return f"{provider} rejected the API key."
    if "429" in lowered or "limit" in lowered or "quota" in lowered:
        return f"{provider} reached its request allowance or was rate-limited."
    if "timed out" in lowered or "timeout" in lowered:
        return f"{provider} timed out."
    return f"{provider} failed: {type(exc).__name__}: {detail[:260]}"


class GoogleTrendsConnector:
    """Google Trends connector using SerpApi as the reliable default route.

    SerpApi performs the Google-facing request outside Streamlit and returns
    structured JSON. This avoids Apify Actor memory and the archived pytrends
    package's fragile cookie/bootstrap request. Automatic mode never silently
    switches back to that route when the SerpApi key is missing.
    """

    def __init__(
        self,
        geo: str = "WORLDWIDE",
        timeframe: str = "today 3-m",
        category: int = 0,
        anchor_term: str = "designer fashion",
        *,
        provider: str = "auto",
        serpapi_api_key: str = "",
        serpapi_endpoint: str = DEFAULT_SERPAPI_ENDPOINT,
        serpapi_timeout_seconds: int = 75,
        max_terms: int = 12,
        max_discovery_seeds: int = 2,
        connect_timeout_seconds: int = 10,
        read_timeout_seconds: int = 35,
    ) -> None:
        self.geo = normalize_google_geo(geo)
        self.market = google_market_label(geo)
        self.timeframe = str(timeframe or "today 3-m").strip()
        self.category = int(category or 0)
        self.anchor_term = str(anchor_term or "designer fashion").strip()
        self.provider = str(provider or "auto").strip().lower()
        self.serpapi_api_key = str(serpapi_api_key or "").strip()
        self.serpapi_endpoint = str(
            serpapi_endpoint or DEFAULT_SERPAPI_ENDPOINT
        ).strip()
        self.serpapi_timeout_seconds = max(20, int(serpapi_timeout_seconds))
        self.max_terms = max(2, min(28, int(max_terms)))
        self.max_discovery_seeds = max(0, min(4, int(max_discovery_seeds)))
        self.connect_timeout_seconds = max(3, int(connect_timeout_seconds))
        self.read_timeout_seconds = max(10, int(read_timeout_seconds))
        self.session = _session()

    def _provider_order(self) -> list[str]:
        if self.provider not in {"auto", "serpapi"}:
            raise GoogleTrendsError(
                "GOOGLE_TRENDS_PROVIDER must be 'auto' or 'serpapi'."
            )
        if not self.serpapi_api_key:
            raise GoogleTrendsError(
                "SERPAPI_API_KEY is missing. Add the free SerpApi key to Streamlit Secrets; "
                "Google Trends no longer uses an Apify Actor."
            )
        return ["serpapi"]

    def _serpapi_request(self, *, query: str, data_type: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "engine": "google_trends",
            "q": query,
            "date": self.timeframe,
            "data_type": data_type,
            "hl": "en",
            "tz": -480 if self.geo == "HK" else 0,
            "api_key": self.serpapi_api_key,
            "output": "json",
        }
        # Google Trends treats an omitted geo as worldwide. Sending the literal
        # word "WORLDWIDE" is not valid, so only country-scoped requests carry
        # the parameter.
        if self.geo:
            params["geo"] = self.geo
        if self.category:
            params["cat"] = self.category
        response = self.session.get(
            self.serpapi_endpoint,
            params=params,
            timeout=(self.connect_timeout_seconds, self.serpapi_timeout_seconds),
        )
        if not response.ok:
            detail = ""
            try:
                detail = str((response.json() or {}).get("error") or "")
            except (ValueError, TypeError):
                detail = response.text[:220]
            raise GoogleTrendsError(
                f"SerpApi request failed ({response.status_code})"
                + (f": {detail}" if detail else ".")
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise GoogleTrendsError("SerpApi returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise GoogleTrendsError("SerpApi returned an invalid response object.")
        if payload.get("error"):
            raise GoogleTrendsError(str(payload["error"]))
        status = str((payload.get("search_metadata") or {}).get("status") or "")
        if status and status.casefold() not in {"success", "cached"}:
            raise GoogleTrendsError(f"SerpApi search ended with status {status}.")
        return payload

    def _collect_serpapi(
        self,
        terms: list[str],
        discovery_seeds: list[str],
    ) -> dict[str, Any]:
        bounded_terms = terms[: self.max_terms]
        comparison_batches = _batches(bounded_terms, self.anchor_term)
        timeline_payloads: list[dict[str, Any]] = []
        successful_batches: list[list[str]] = []
        warnings: list[str] = []
        for batch in comparison_batches:
            try:
                timeline_payloads.append(
                    self._serpapi_request(
                        query=",".join(batch),
                        data_type="TIMESERIES",
                    )
                )
                successful_batches.append(batch)
            except Exception as exc:
                warnings.append(
                    f"Google Trends comparison for {', '.join(batch[1:])}: "
                    f"{_friendly_failure('SerpApi', exc)}"
                )
            time.sleep(0.15)

        series = normalize_serpapi_interest(
            timeline_payloads,
            successful_batches,
            self.anchor_term,
        )
        if not series:
            detail = warnings[-1] if warnings else "No timeline data was returned."
            raise GoogleTrendsError(detail)

        seeds = discovery_seeds[: self.max_discovery_seeds]
        related_payloads: list[dict[str, Any]] = []
        successful_seeds: list[str] = []
        for seed in seeds:
            try:
                related_payloads.append(
                    self._serpapi_request(query=seed, data_type="RELATED_QUERIES")
                )
                successful_seeds.append(seed)
            except Exception as exc:
                warnings.append(
                    f"Google Trends related queries for '{seed}': "
                    f"{_friendly_failure('SerpApi', exc)}"
                )
            time.sleep(0.15)

        return {
            "series": series,
            "related": normalize_serpapi_related(
                related_payloads,
                successful_seeds,
            ),
            "warnings": warnings,
            "provider": "SerpApi Google Trends",
            "usage_usd": None,
            "requests_used": len(timeline_payloads) + len(related_payloads),
            "request_ceiling": len(comparison_batches) + len(seeds),
            "terms_requested": len(bounded_terms),
        }

    def collect(
        self,
        terms: list[str],
        *,
        discovery_seeds: list[str] | None = None,
    ) -> dict[str, Any]:
        cleaned_terms = [
            term
            for term in dict.fromkeys(str(term).strip() for term in terms)
            if term
        ]
        seeds = [
            seed
            for seed in dict.fromkeys(
                str(seed).strip() for seed in (discovery_seeds or [])
            )
            if seed
        ]
        if not cleaned_terms:
            raise GoogleTrendsError("At least one Google Trends term is required.")

        attempts: list[dict[str, str]] = []
        for provider in self._provider_order():
            try:
                result = self._collect_serpapi(cleaned_terms, seeds)
                attempts.append({"provider": provider, "status": "succeeded"})
                result["attempts"] = attempts
                result["market"] = self.market
                result["timeframe"] = self.timeframe
                return result
            except Exception as exc:
                note = _friendly_failure("SerpApi Google Trends", exc)
                attempts.append(
                    {"provider": provider, "status": "failed", "detail": note}
                )
                raise GoogleTrendsError(note) from exc
        raise GoogleTrendsError("No Google Trends provider was available.")

    def discover_related(
        self,
        seeds: list[str],
        *,
        limit: int = 15,
    ) -> dict[str, Any]:
        """Discover rising phrases without spending timeline requests."""

        cleaned = [
            seed
            for seed in dict.fromkeys(str(seed).strip() for seed in seeds)
            if seed
        ][: self.max_discovery_seeds]
        if not cleaned:
            return {
                "related": [],
                "warnings": [],
                "provider": "SerpApi Google Trends",
                "requests_used": 0,
                "request_ceiling": 0,
                "market": self.market,
                "timeframe": self.timeframe,
            }
        self._provider_order()
        payloads: list[dict[str, Any]] = []
        successful: list[str] = []
        warnings: list[str] = []
        for seed in cleaned:
            try:
                payloads.append(
                    self._serpapi_request(
                        query=seed,
                        data_type="RELATED_QUERIES",
                    )
                )
                successful.append(seed)
            except Exception as exc:
                warnings.append(
                    f"Google Trends related queries for '{seed}': "
                    f"{_friendly_failure('SerpApi', exc)}"
                )
            time.sleep(0.15)
        if not payloads:
            detail = warnings[-1] if warnings else "No related-query data was returned."
            raise GoogleTrendsError(detail)
        return {
            "related": normalize_serpapi_related(
                payloads,
                successful,
                limit=max(1, int(limit)),
            ),
            "warnings": warnings,
            "provider": "SerpApi Google Trends",
            "requests_used": len(payloads),
            "request_ceiling": len(cleaned),
            "market": self.market,
            "timeframe": self.timeframe,
        }

    def test_connection(self) -> dict[str, Any]:
        result = self.collect(
            ["designer fashion", "ballet flats"],
            discovery_seeds=[],
        )
        points = sum(len(rows) for rows in result.get("series", {}).values())
        return {
            "ok": bool(points),
            "provider": result.get("provider"),
            "market": result.get("market"),
            "points": points,
            "requests_used": result.get("requests_used", 0),
            "attempts": result.get("attempts", []),
        }

    def fetch_interest(
        self, terms: list[str]
    ) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
        result = self.collect(terms, discovery_seeds=[])
        return result["series"], list(result.get("warnings") or [])

    def related_queries(
        self, seeds: list[str], limit: int = 15
    ) -> tuple[list[dict[str, Any]], list[str]]:
        result = self.collect(seeds, discovery_seeds=seeds)
        rows = list(result.get("related") or [])
        return rows[: max(1, int(limit)) * max(1, len(seeds))], list(
            result.get("warnings") or []
        )
