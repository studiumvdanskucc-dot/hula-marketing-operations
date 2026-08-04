from __future__ import annotations

import json
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.analysis.freshness import parse_utc
from src.analysis.trends import canonical_name, generic_trend_reason, slugify


class CommercialSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommercialSource:
    key: str
    name: str
    index_urls: tuple[str, ...]
    weight: float
    max_articles: int = 4
    max_age_days: int = 180
    kind: str = "articles"

    @property
    def hosts(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                urlparse(url).netloc.casefold().removeprefix("www.")
                for url in self.index_urls
            )
        )


COMMERCIAL_SOURCES: tuple[CommercialSource, ...] = (
    CommercialSource(
        "tagwalk",
        "Tagwalk",
        ("https://www.tag-walk.com/en/trends",),
        3.0,
        max_articles=1,
        max_age_days=550,
        kind="taxonomy",
    ),
    CommercialSource(
        "trendalytics",
        "Trendalytics",
        ("https://blog.trendalytics.co/all",),
        3.0,
        max_age_days=240,
    ),
    CommercialSource(
        "heuritech",
        "Heuritech",
        ("https://heuritech.com/blog/", "https://heuritech.com/market-reports/"),
        3.0,
        max_articles=3,
        max_age_days=365,
    ),
    CommercialSource(
        "whowhatwear",
        "Who What Wear",
        ("https://www.whowhatwear.com/fashion/trends",),
        2.0,
        max_articles=5,
        max_age_days=120,
    ),
    CommercialSource(
        "whowhatwear-uk",
        "Who What Wear UK",
        ("https://www.whowhatwear.com/uk/fashion/trends",),
        2.0,
        max_articles=5,
        max_age_days=120,
    ),
    CommercialSource(
        "data-but-make-it-fashion",
        "Data But Make It Fashion",
        ("https://www.databutmakeitfashion.com/",),
        3.0,
        max_articles=4,
        max_age_days=240,
    ),
    CommercialSource(
        "vogue",
        "Vogue",
        ("https://www.vogue.com/fashion/trends",),
        2.0,
        max_articles=5,
        max_age_days=180,
    ),
    CommercialSource(
        "elle",
        "ELLE",
        ("https://www.elle.com/fashion/trend-reports/",),
        2.0,
        max_articles=5,
        max_age_days=180,
    ),
    CommercialSource(
        "lyst-index",
        "Lyst Index",
        ("https://www.lyst.com/data/the-lyst-index/",),
        3.0,
        max_articles=3,
        max_age_days=550,
    ),
)


TREND_REPORT_CUES = {
    "trend",
    "trends",
    "forecast",
    "runway",
    "fashion week",
    "what to wear",
    "must-have",
    "must have",
    "lyst index",
    "hottest products",
}

ARTICLE_PATH_CUES = (
    "/article/",
    "/fashion/",
    "/trend",
    "/insight",
    "/report",
    "/blog/",
    "/p/",
    "/data/the-lyst-index/",
)

PAGE_EXCLUSIONS = (
    "/author/",
    "/authors/",
    "/category/",
    "/tag/",
    "/privacy",
    "/terms",
    "/login",
    "/account",
    "/search",
    "mailto:",
    "javascript:",
)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_label(value: str) -> str:
    label = _clean_text(value)
    label = re.sub(r"^\s*(?:#?\d{1,2}|[ivx]{1,5})[.)\-:]\s*", "", label, flags=re.I)
    label = re.sub(r"^trend\s*(?:#?\d{1,2})?\s*[:\-]\s*", "", label, flags=re.I)
    label = re.sub(r"^(?:the|a|an)\s+", "", label, flags=re.I)
    label = re.sub(r"\s+(?:fashion|style)\s+trend$", "", label, flags=re.I)
    label = label.strip(" \t\r\n:–—-|•")
    return _clean_text(label)


def _is_trend_report_title(title: str) -> bool:
    lowered = title.casefold()
    return any(cue in lowered for cue in TREND_REPORT_CUES)


def _candidate_from_singular_trend(title: str) -> list[str]:
    cleaned = _clean_text(title)
    candidates: list[str] = []
    patterns = (
        r"(?:this|the|a|an)\s+([A-Za-z][A-Za-z'’\-–\s]{1,70}?)\s+(?:fashion|style|shoe|bag|colour|color|dress|jewellery|jewelry|accessory)?\s*trend\b",
        r"(?:^|[:–—|])\s*([A-Za-z][A-Za-z'’\-–\s]{1,70}?)\s+(?:fashion|style|shoe|bag|colour|color|dress|jewellery|jewelry|accessory)?\s*trend\b",
        r"([A-Za-z][A-Za-z'’\-–\s]{1,70}?)\s+is\s+(?:back|rising|trending|taking over|everywhere)\b",
        r"(?:rise|return|revival)\s+of\s+([A-Za-z][A-Za-z'’\-–\s]{1,70})\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, cleaned, flags=re.I):
            label = _clean_label(match.group(1))
            label = re.sub(
                r"^(?:(?:hyper[ -]specific|beautiful|comfortable|cool|current|"
                r"dated|elegant|essential|everyday|fresh|good|great|hot|key|major|"
                r"biggest|best|modern|new|latest|nice|popular|pretty|seasonal|stylish|"
                r"timeless|top|unexpected|viral)\s+)+",
                "",
                label,
                flags=re.I,
            )
            if label:
                candidates.append(label)
    return candidates


def extract_explicit_trend_labels(
    *,
    title: str,
    headings: Iterable[str],
    taxonomy_text: Iterable[str] = (),
) -> list[dict[str, str]]:
    """Extract only publisher-explicit labels, never ordinary article body text."""

    candidates: list[tuple[str, str, str]] = []
    for label in _candidate_from_singular_trend(title):
        candidates.append((label, "article title", title))

    title_is_report = _is_trend_report_title(title)
    if title_is_report:
        for heading in headings:
            heading_text = _clean_text(heading)
            if not heading_text or len(heading_text) > 90:
                continue
            if re.search(
                r"(?:related posts|read more|shop the|why trust|meet the|download|subscribe|newsletter|contents|jump to|in the magazine)",
                heading_text,
                flags=re.I,
            ):
                continue
            label = _clean_label(heading_text)
            if label and not _is_trend_report_title(label):
                candidates.append((label, "trend-labelled heading", heading_text))

    for raw in taxonomy_text:
        text = _clean_text(raw)
        match = re.search(r"see all\s+(.+?)\s+looks", text, flags=re.I)
        label = _clean_label(match.group(1) if match else text)
        if label:
            candidates.append((label, "runway taxonomy", text))

    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate, evidence_kind, explicit_text in candidates:
        name = canonical_name(candidate)
        reason = generic_trend_reason(name, trusted_source=True)
        key = slugify(name)
        if reason or key in seen:
            continue
        seen.add(key)
        output.append(
            {
                "trend_id": key,
                "trend_name": name,
                "explicit_label": explicit_text,
                "evidence_kind": evidence_kind,
            }
        )
    return output


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._captures: list[dict[str, Any]] = []
        self.title = ""
        self.headings: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.time_values: list[str] = []
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.json_ld: list[Any] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.casefold()
        attributes = {str(key).casefold(): str(value or "") for key, value in attrs}
        if lower == "meta":
            key = attributes.get("property") or attributes.get("name") or attributes.get("itemprop")
            content = attributes.get("content")
            if key and content:
                self.meta[key.casefold()] = _clean_text(content)
        elif lower == "link" and "canonical" in attributes.get("rel", "").casefold():
            self.canonical = attributes.get("href", "")
        if lower in {"title", "h1", "h2", "h3", "h4", "a", "time"}:
            self._captures.append(
                {
                    "tag": lower,
                    "text": [],
                    "href": attributes.get("href", ""),
                    "datetime": attributes.get("datetime", ""),
                }
            )
        elif lower == "script" and "ld+json" in attributes.get("type", "").casefold():
            self._captures.append({"tag": "script", "text": []})

    def handle_data(self, data: str) -> None:
        for capture in self._captures:
            capture["text"].append(data)

    def handle_endtag(self, tag: str) -> None:
        lower = tag.casefold()
        for index in range(len(self._captures) - 1, -1, -1):
            capture = self._captures[index]
            if capture.get("tag") != lower:
                continue
            self._captures.pop(index)
            text = _clean_text("".join(capture.get("text") or []))
            if lower == "title" and text:
                self.title = text
            elif lower in {"h1", "h2", "h3", "h4"} and text:
                self.headings.append(text)
            elif lower == "a" and text and capture.get("href"):
                self.links.append((text, str(capture["href"])))
            elif lower == "time":
                value = str(capture.get("datetime") or text)
                if value:
                    self.time_values.append(value)
            elif lower == "script" and text:
                try:
                    self.json_ld.append(json.loads(text))
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass
            break


def parse_page(html: str) -> _PageParser:
    parser = _PageParser()
    parser.feed(str(html or ""))
    return parser


def _json_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _json_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _json_objects(nested)


def _page_metadata(page: _PageParser, requested_url: str) -> dict[str, str]:
    structured = list(_json_objects(page.json_ld))
    headline = next(
        (_clean_text(row.get("headline")) for row in structured if row.get("headline")),
        "",
    )
    published = next(
        (
            _clean_text(row.get("datePublished") or row.get("dateCreated"))
            for row in structured
            if row.get("datePublished") or row.get("dateCreated")
        ),
        "",
    )
    structured_url = next(
        (_clean_text(row.get("url")) for row in structured if isinstance(row.get("url"), str)),
        "",
    )
    title = (
        page.meta.get("og:title")
        or page.meta.get("twitter:title")
        or headline
        or page.title
        or (page.headings[0] if page.headings else "")
    )
    published = (
        page.meta.get("article:published_time")
        or page.meta.get("datepublished")
        or page.meta.get("parsely-pub-date")
        or published
        or (page.time_values[0] if page.time_values else "")
    )
    url = page.canonical or structured_url or requested_url
    return {
        "title": _clean_text(title),
        "published_at": _clean_text(published),
        "url": urljoin(requested_url, _clean_text(url)),
    }


def _same_source_host(source: CommercialSource, url: str) -> bool:
    host = urlparse(url).netloc.casefold().removeprefix("www.")
    return any(host == allowed or host.endswith("." + allowed) for allowed in source.hosts)


def _article_links(
    source: CommercialSource,
    page: _PageParser,
    index_url: str,
) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text, href in page.links:
        absolute = urljoin(index_url, href).split("#", 1)[0]
        lowered = absolute.casefold()
        if not absolute.startswith(("https://", "http://")):
            continue
        if not _same_source_host(source, absolute):
            continue
        if any(part in lowered for part in PAGE_EXCLUSIONS):
            continue
        if absolute.rstrip("/") == index_url.rstrip("/") or absolute in seen:
            continue
        text_lower = text.casefold()
        path_match = any(cue in lowered for cue in ARTICLE_PATH_CUES)
        title_match = any(cue in text_lower for cue in TREND_REPORT_CUES)
        if not (path_match and (title_match or len(text.split()) >= 4)):
            continue
        seen.add(absolute)
        output.append((_clean_text(text), absolute))
        if len(output) >= source.max_articles:
            break
    return output


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (compatible; HULA-Trend-Intelligence/1.0; "
                "+https://thehula.com)"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-GB,en;q=0.8",
        }
    )
    return session


class CommercialSourceCollector:
    """Collect explicit trend labels from approved public publisher pages."""

    def __init__(
        self,
        *,
        sources: Iterable[CommercialSource] = COMMERCIAL_SOURCES,
        timeout_seconds: int = 15,
        max_workers: int = 6,
        session: requests.Session | None = None,
    ) -> None:
        self.sources = tuple(sources)
        self.timeout_seconds = max(5, int(timeout_seconds))
        self.max_workers = max(1, min(12, int(max_workers)))
        self.session = session or _session()

    def _fetch(self, url: str) -> tuple[str, str]:
        response = self.session.get(url, timeout=self.timeout_seconds)
        if not response.ok:
            raise CommercialSourceError(f"HTTP {response.status_code} for {url}")
        content_type = str(response.headers.get("Content-Type") or "")
        if content_type and "html" not in content_type.casefold():
            raise CommercialSourceError(f"Non-HTML response for {url}")
        return response.text, str(response.url or url)

    def _article_evidence(
        self,
        source: CommercialSource,
        url: str,
        fallback_title: str,
        *,
        collected_at: str,
        now: datetime,
    ) -> list[dict[str, Any]]:
        html, final_url = self._fetch(url)
        page = parse_page(html)
        metadata = _page_metadata(page, final_url)
        title = metadata["title"] or fallback_title
        published = parse_utc(metadata["published_at"])
        if published is not None:
            age_days = max(0.0, (now - published).total_seconds() / 86400)
            if age_days > source.max_age_days:
                return []
        labels = extract_explicit_trend_labels(title=title, headings=page.headings)
        return [
            {
                **label,
                "publisher": source.name,
                "publisher_id": source.key,
                "publisher_weight": source.weight,
                "article_title": title,
                "published_at": published.isoformat() if published else "",
                "url": metadata["url"] or final_url,
                "collected_at": collected_at,
                "explicit": True,
            }
            for label in labels
        ]

    def collect(self, *, now: datetime | None = None) -> dict[str, Any]:
        reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
        collected_at = reference.isoformat()
        evidence: list[dict[str, Any]] = []
        statuses: dict[str, dict[str, Any]] = {}
        article_jobs: list[tuple[CommercialSource, str, str]] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(self._fetch, url): (source, url)
                for source in self.sources
                for url in source.index_urls
            }
            index_results: dict[str, list[tuple[str, str, _PageParser]]] = {}
            for future in as_completed(future_map):
                source, requested = future_map[future]
                status = statuses.setdefault(
                    source.key,
                    {
                        "publisher": source.name,
                        "state": "FAILED",
                        "pages_requested": len(source.index_urls),
                        "pages_loaded": 0,
                        "articles_loaded": 0,
                        "evidence_rows": 0,
                        "errors": [],
                    },
                )
                try:
                    html, final_url = future.result()
                    page = parse_page(html)
                    index_results.setdefault(source.key, []).append(
                        (requested, final_url, page)
                    )
                    status["pages_loaded"] += 1
                except Exception as exc:
                    status["errors"].append(str(exc)[:260])

        source_by_key = {source.key: source for source in self.sources}
        for key, pages in index_results.items():
            source = source_by_key[key]
            if source.kind == "taxonomy":
                for _, final_url, page in pages:
                    taxonomy = [
                        text
                        for text, _ in page.links
                        if re.search(r"see all\s+.+?\s+looks", text, flags=re.I)
                    ]
                    if not taxonomy:
                        taxonomy = [
                            heading
                            for heading in page.headings
                            if 1 <= len(heading.split()) <= 6
                        ]
                    metadata = _page_metadata(page, final_url)
                    labels = extract_explicit_trend_labels(
                        title=metadata["title"] or "Tagwalk runway trends",
                        headings=(),
                        taxonomy_text=taxonomy,
                    )
                    evidence.extend(
                        {
                            **label,
                            "publisher": source.name,
                            "publisher_id": source.key,
                            "publisher_weight": source.weight,
                            "article_title": metadata["title"] or "Tagwalk Trends",
                            "published_at": "",
                            "url": metadata["url"] or final_url,
                            "collected_at": collected_at,
                            "explicit": True,
                        }
                        for label in labels
                    )
                continue

            links: list[tuple[str, str]] = []
            for _, final_url, page in pages:
                links.extend(_article_links(source, page, final_url))
            deduped: list[tuple[str, str]] = []
            seen_urls: set[str] = set()
            for title, url in links:
                if url not in seen_urls:
                    deduped.append((title, url))
                    seen_urls.add(url)
                if len(deduped) >= source.max_articles:
                    break
            article_jobs.extend((source, url, title) for title, url in deduped)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(
                    self._article_evidence,
                    source,
                    url,
                    title,
                    collected_at=collected_at,
                    now=reference,
                ): (source, url)
                for source, url, title in article_jobs
            }
            for future in as_completed(future_map):
                source, _ = future_map[future]
                status = statuses[source.key]
                try:
                    rows = future.result()
                    status["articles_loaded"] += 1
                    evidence.extend(rows)
                except Exception as exc:
                    status["errors"].append(str(exc)[:260])

        deduped_evidence: list[dict[str, Any]] = []
        seen_evidence: set[tuple[str, str, str]] = set()
        for row in evidence:
            identity = (
                str(row.get("publisher_id") or ""),
                str(row.get("trend_id") or ""),
                str(row.get("url") or ""),
            )
            if not all(identity) or identity in seen_evidence:
                continue
            seen_evidence.add(identity)
            deduped_evidence.append(row)

        for source in self.sources:
            status = statuses.setdefault(
                source.key,
                {
                    "publisher": source.name,
                    "state": "FAILED",
                    "pages_requested": len(source.index_urls),
                    "pages_loaded": 0,
                    "articles_loaded": 0,
                    "evidence_rows": 0,
                    "errors": ["No response was returned."],
                },
            )
            rows = sum(
                row.get("publisher_id") == source.key for row in deduped_evidence
            )
            status["evidence_rows"] = rows
            loaded = int(status.get("pages_loaded") or 0)
            article_loaded = int(status.get("articles_loaded") or 0)
            if loaded and rows:
                status["state"] = "LIVE" if not status["errors"] else "PARTIAL"
            elif loaded or article_loaded:
                status["state"] = "PARTIAL"
            else:
                status["state"] = "FAILED"

        return {
            "evidence": deduped_evidence,
            "source_status": statuses,
            "publishers_requested": len(self.sources),
            "publishers_live": sum(
                row.get("state") == "LIVE" for row in statuses.values()
            ),
            "publishers_partial": sum(
                row.get("state") == "PARTIAL" for row in statuses.values()
            ),
            "publishers_failed": sum(
                row.get("state") == "FAILED" for row in statuses.values()
            ),
            "articles_loaded": sum(
                int(row.get("articles_loaded") or 0) for row in statuses.values()
            ),
            "evidence_rows": len(deduped_evidence),
            "collected_at": collected_at,
        }

    def test_connection(self) -> dict[str, Any]:
        result = self.collect()
        return {
            "ok": bool(result.get("publishers_live") or result.get("publishers_partial")),
            "publishers_live": result.get("publishers_live", 0),
            "publishers_partial": result.get("publishers_partial", 0),
            "publishers_failed": result.get("publishers_failed", 0),
            "source_status": result.get("source_status", {}),
        }


def score_commercial_evidence(
    evidence: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Turn explicit article/report evidence into one score per named trend."""

    reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for original in evidence:
        row = dict(original)
        name = canonical_name(str(row.get("trend_name") or row.get("explicit_label") or ""))
        if generic_trend_reason(name, trusted_source=True):
            continue
        row["trend_name"] = name
        row["trend_id"] = slugify(name)
        grouped.setdefault(row["trend_id"], []).append(row)

    rows: list[dict[str, Any]] = []
    for trend_id, items in grouped.items():
        publishers = {
            str(item.get("publisher_id") or item.get("publisher") or "")
            for item in items
            if item.get("publisher_id") or item.get("publisher")
        }
        authority = sum(
            max(1.0, min(3.0, float(item.get("publisher_weight") or 1.0)))
            for item in items
        )
        recency_values: list[float] = []
        for item in items:
            published = parse_utc(item.get("published_at"))
            if published is None:
                recency_values.append(0.45)
                continue
            age_days = max(0.0, (reference - published).total_seconds() / 86400)
            recency_values.append(math.exp(-age_days / 120.0))
        recency = 100 * sum(recency_values) / max(1, len(recency_values))
        breadth = min(100.0, 25.0 + 22.5 * max(0, len(publishers) - 1))
        authority_score = min(100.0, 18.0 * authority)
        commercial_score = 0.52 * breadth + 0.30 * authority_score + 0.18 * recency
        ordered = sorted(
            items,
            key=lambda item: (
                parse_utc(item.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),
                float(item.get("publisher_weight") or 0),
            ),
            reverse=True,
        )
        rows.append(
            {
                "id": trend_id,
                "name": ordered[0]["trend_name"],
                "commercial_score": round(commercial_score, 1),
                "commercial_source_score": round(commercial_score, 1),
                "publisher_count": len(publishers),
                "article_count": len(items),
                "commercial_priority_mentions": sum(
                    float(item.get("publisher_weight") or 0) >= 3 for item in items
                ),
                "commercial_evidence": ordered,
                "aliases": list(
                    dict.fromkeys(
                        str(item.get("explicit_label") or item.get("trend_name") or "")
                        for item in items
                        if item.get("explicit_label") or item.get("trend_name")
                    )
                ),
            }
        )
    return sorted(rows, key=lambda row: float(row["commercial_score"]), reverse=True)
