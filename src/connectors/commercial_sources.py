from __future__ import annotations

import json
import html as html_lib
import hashlib
import math
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from threading import Lock
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
    feed_urls: tuple[str, ...] = ()
    sitemap_urls: tuple[str, ...] = ()
    article_urls: tuple[str, ...] = ()
    search_query: str = ""
    publisher_group: str = ""

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
        max_articles=4,
        max_age_days=550,
        kind="taxonomy",
        search_query="site:tag-walk.com/en/trends/woman fashion trends",
    ),
    CommercialSource(
        "trendalytics",
        "Trendalytics",
        ("https://blog.trendalytics.co/all",),
        3.0,
        max_articles=14,
        max_age_days=240,
        feed_urls=("https://blog.trendalytics.co/rss.xml",),
        search_query="site:blog.trendalytics.co fashion trends forecast",
    ),
    CommercialSource(
        "heuritech",
        "Heuritech",
        ("https://heuritech.com/blog/", "https://heuritech.com/market-reports/"),
        3.0,
        max_articles=8,
        max_age_days=365,
        article_urls=("https://heuritech.com/fashion-trends-2026/",),
        search_query="site:heuritech.com fashion trends forecast",
    ),
    CommercialSource(
        "whowhatwear",
        "Who What Wear",
        ("https://www.whowhatwear.com/fashion/trends",),
        2.0,
        max_articles=20,
        max_age_days=120,
        sitemap_urls=("https://www.whowhatwear.com/sitemap-news.xml",),
        article_urls=(
            "https://www.whowhatwear.com/fashion/trends/editor-favorite-fall-trends-2026",
        ),
        search_query="site:whowhatwear.com/fashion fashion trend",
        publisher_group="whowhatwear",
    ),
    CommercialSource(
        "whowhatwear-uk",
        "Who What Wear UK",
        ("https://www.whowhatwear.com/uk/fashion/trends",),
        2.0,
        max_articles=15,
        max_age_days=120,
        search_query="site:whowhatwear.com/uk/fashion fashion trend",
        publisher_group="whowhatwear",
    ),
    CommercialSource(
        "data-but-make-it-fashion",
        "Data But Make It Fashion",
        ("https://www.databutmakeitfashion.com/archive",),
        3.0,
        max_articles=18,
        max_age_days=240,
        feed_urls=("https://www.databutmakeitfashion.com/feed",),
        article_urls=(
            "https://www.databutmakeitfashion.com/p/of-course-florals-are-trending-for",
        ),
        search_query="site:databutmakeitfashion.com/p fashion trend",
    ),
    CommercialSource(
        "vogue",
        "Vogue",
        ("https://www.vogue.com/fashion",),
        2.0,
        max_articles=14,
        max_age_days=180,
        sitemap_urls=("https://www.vogue.com/sitemap.xml",),
        article_urls=("https://www.vogue.com/article/fall-2026-shoe-trends",),
        search_query="site:vogue.com/article fashion trend runway",
    ),
    CommercialSource(
        "elle",
        "ELLE",
        ("https://www.elle.com/fashion/trend-reports/",),
        2.0,
        max_articles=14,
        max_age_days=180,
        article_urls=(
            "https://www.elle.com/fashion/trend-reports/a70407937/best-spring-2026-fashion-trends/",
        ),
        search_query="site:elle.com/fashion/trend-reports fashion trends",
    ),
    CommercialSource(
        "harpers-bazaar",
        "Harper's Bazaar",
        ("https://www.harpersbazaar.com/fashion/trends/",),
        2.0,
        max_articles=14,
        max_age_days=180,
        search_query="site:harpersbazaar.com/fashion/trends fashion trend",
    ),
    CommercialSource(
        "instyle",
        "InStyle",
        ("https://www.instyle.com/fashion-5341673",),
        2.0,
        max_articles=16,
        max_age_days=180,
        search_query="site:instyle.com fashion trend",
    ),
    CommercialSource(
        "refinery29",
        "Refinery29",
        ("https://www.refinery29.com/en-us/fashion-trends",),
        2.0,
        max_articles=14,
        max_age_days=180,
        search_query="site:refinery29.com fashion trends",
    ),
    CommercialSource(
        "teen-vogue",
        "Teen Vogue",
        ("https://www.teenvogue.com/fashion/trends",),
        2.0,
        max_articles=14,
        max_age_days=180,
        search_query="site:teenvogue.com/fashion/trends fashion trend",
    ),
    CommercialSource(
        "lyst-index",
        "Lyst Index",
        ("https://www.lyst.com/data/the-lyst-index/",),
        3.0,
        max_articles=2,
        max_age_days=550,
        kind="lyst",
        search_query="site:lyst.com/the-lyst-index hottest products",
    ),
)


# Build 2026.08.06.4 deliberately narrows live discovery to consumer-facing
# editorial publishers. Each regional or sister edition can still be collected,
# but ``publisher_group`` is the identity used for independent-source overlap.
# The 21-day window is the product requirement: these pages discover ideas;
# Google Trends measures whether search behaviour is moving with them.
EDITORIAL_PUBLISHERS: tuple[CommercialSource, ...] = (
    CommercialSource(
        "whowhatwear",
        "Who What Wear",
        ("https://www.whowhatwear.com/fashion/trends",),
        1.0,
        max_articles=12,
        max_age_days=21,
        sitemap_urls=("https://www.whowhatwear.com/sitemap-news.xml",),
        article_urls=(
            "https://www.whowhatwear.com/fashion/trends/ransitional-trends-for-fall-2026",
        ),
        search_query=(
            "site:whowhatwear.com/fashion/trends OR site:whowhatwear.com/fashion/"
            " fashion trend"
        ),
        publisher_group="whowhatwear",
    ),
    CommercialSource(
        "vogue",
        "Vogue",
        ("https://www.vogue.com/fashion/trends",),
        1.0,
        max_articles=10,
        max_age_days=21,
        sitemap_urls=("https://www.vogue.com/sitemap.xml",),
        article_urls=(
            "https://www.vogue.com/article/fall-winter-2026-fashion-trends",
        ),
        search_query="site:vogue.com/article fashion trend",
        publisher_group="vogue",
    ),
    CommercialSource(
        "elle",
        "ELLE",
        ("https://www.elle.com/fashion/trend-reports/",),
        1.0,
        max_articles=10,
        max_age_days=21,
        article_urls=(
            "https://www.elle.com/fashion/trend-reports/a73229879/pre-fall-fashion-trends/",
        ),
        search_query="site:elle.com/fashion/trend-reports fashion trend",
        publisher_group="elle",
    ),
    CommercialSource(
        "harpers-bazaar",
        "Harper's Bazaar",
        ("https://www.harpersbazaar.com/fashion/trends/",),
        1.0,
        max_articles=10,
        max_age_days=21,
        search_query="site:harpersbazaar.com/fashion/trends fashion trend",
        publisher_group="harpers-bazaar",
    ),
    CommercialSource(
        "marie-claire",
        "Marie Claire",
        (
            "https://www.marieclaire.com/fashion/fall-fashion/",
            "https://www.marieclaire.com/fashion/",
        ),
        1.0,
        max_articles=10,
        max_age_days=21,
        article_urls=(
            "https://www.marieclaire.com/fashion/drop-waist-trend-fall-2026/",
        ),
        search_query="site:marieclaire.com/fashion fashion trend",
        publisher_group="marie-claire",
    ),
    CommercialSource(
        "glamour",
        "Glamour",
        ("https://www.glamour.com/fashion",),
        1.0,
        max_articles=10,
        max_age_days=21,
        article_urls=(
            "https://www.glamour.com/story/dakota-johnson-granny-tote-fall-bag-trend",
        ),
        search_query="site:glamour.com/story fashion trend",
        publisher_group="glamour",
    ),
    CommercialSource(
        "instyle",
        "InStyle",
        ("https://www.instyle.com/fashion-5341673",),
        1.0,
        max_articles=10,
        max_age_days=21,
        search_query="site:instyle.com fashion trend",
        publisher_group="instyle",
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
    label = re.sub(r"^(?:shop|buy|wear|try|of course)\s+", "", label, flags=re.I)
    label = re.sub(r"^(?:this|these|that|those)\s+", "", label, flags=re.I)
    label = re.sub(
        r"^(?:(?:and|or|with|including|especially|such as|like|via|through)\s+)+",
        "",
        label,
        flags=re.I,
    )
    label = re.sub(
        r"^(?:driven by (?:a |an |the )?(?:resurgence|rise|return) in|"
        r"bottom options like|options like)\s+",
        "",
        label,
        flags=re.I,
    )
    label = re.sub(
        r"^pausing\s+.+?\s+(?:and\s+)?wearing\s+",
        "",
        label,
        flags=re.I,
    )
    label = re.sub(r"^(?:from|towards?)\s+", "", label, flags=re.I)
    label = re.sub(
        r"^(?:a |an |the )?resurgence (?:in|of) (?:the )?",
        "",
        label,
        flags=re.I,
    )
    label = re.sub(r"^(?:the|a|an)\s+", "", label, flags=re.I)
    label = re.sub(
        r"^(?:best|biggest|dated|editor[- ]favorite|favourite|favorite|"
        r"hottest|key|latest|new|prettier|top|unexpected|viral)\s+",
        "",
        label,
        flags=re.I,
    )
    label = re.sub(r"\s+(?:fashion|style)\s+trend$", "", label, flags=re.I)
    label = re.sub(r"\s+outfit$", "", label, flags=re.I)
    label = re.sub(
        r"\s*[|–—-]\s*(?:trendalytics|vogue|elle|who what wear).*$",
        "",
        label,
        flags=re.I,
    )
    label = label.strip(" \t\r\n:–—-|•")
    return _clean_text(label)


def _is_trend_report_title(title: str) -> bool:
    lowered = title.casefold()
    return any(cue in lowered for cue in TREND_REPORT_CUES)


def _is_multi_trend_report_title(title: str) -> bool:
    lowered = _clean_text(title).casefold()
    return bool(
        re.search(
            r"\b(?:\d{1,2}|these|top|biggest|key)\b.{0,45}\btrends\b",
            lowered,
        )
        or re.search(r"\btrends\s+(?:i|we|to|that|set|from|for)\b", lowered)
        or "fashion week trends" in lowered
    )


def _candidate_from_singular_trend(title: str) -> list[str]:
    cleaned = _clean_text(title)
    candidates: list[str] = []
    patterns = (
        r"(?:this|the|a|an)\s+([A-Za-z][A-Za-z'’\-–\s]{1,70}?)\s+(?:fashion|style|shoe|bag|colour|color|dress|jewellery|jewelry|accessory)?\s*trend\b",
        r"(?:^|[:–—|])\s*([A-Za-z][A-Za-z'’\-–\s]{1,70}?)\s+(?:fashion|style|shoe|bag|colour|color|dress|jewellery|jewelry|accessory)?\s*trend\b",
        r"([A-Za-z][A-Za-z'’\-–\s]{1,70}?)\s+(?:is|are)\s+(?:back|rising|trending|taking over|everywhere)\b",
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
            if label and len(label.split()) <= 6:
                candidates.append(label)
    return candidates


def _candidate_from_url_slug(url: str, title: str) -> list[str]:
    """Use a publisher's own descriptive URL when the headline says trend.

    Commerce headlines often hide the named item behind phrases such as "this
    unexpected pant trend", while the canonical URL explicitly says
    ``boardwalk-pant-trend``. We only use the slug when either the title or URL
    explicitly identifies the page as a trend page.
    """

    path = urlparse(str(url or "")).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1].casefold()
    if not slug or "trend" not in f"{slug} {title.casefold()}":
        return []
    match = re.search(r"(?:^|/)([a-z0-9-]{2,80}?)-(?:fashion-)?trends?(?:-|$)", path.casefold())
    if not match:
        return []
    label = re.sub(r"-(?:19|20)\d{2}$", "", match.group(1))
    label = re.sub(
        r"^(?:best|biggest|editor-favorite|fall|spring|summer|winter|pre-fall)-",
        "",
        label,
    )
    cleaned = _clean_label(label.replace("-", " "))
    cleaned = re.sub(r"\s+(?:on the )?runway$", "", cleaned, flags=re.I)
    if (
        not cleaned
        or len(cleaned.split()) > 3
        or cleaned[0].isdigit()
        or re.match(r"^(?:19|20)\d{2}\b", cleaned)
        or cleaned.casefold() in {"fashion week", "street style", "runway fashion"}
    ):
        return []
    return [cleaned]


def _candidate_from_declarations(paragraphs: Iterable[str]) -> list[str]:
    """Extract only phrases explicitly introduced as a trend/look/aesthetic."""

    candidates: list[str] = []
    patterns = (
        r"(?:called|dubbed|known as|referred to as)\s+(?:the\s+)?[\"“']?([A-Za-z0-9][A-Za-z0-9'’\-–\s]{1,60}?)[\"”']?(?=[,.;:]|\s+(?:trend|look|aesthetic|style)\b)",
        r"[\"“]([A-Za-z0-9][A-Za-z0-9'’\-–\s]{1,50}?)[\"”]\s+(?:trend|look|aesthetic|style)\b",
    )
    for paragraph in list(paragraphs)[:35]:
        text = _clean_text(paragraph)
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                label = _clean_label(match.group(1))
                if 1 <= len(label.split()) <= 8:
                    candidates.append(label)
    return candidates


def _candidate_from_quantified_text(paragraphs: Iterable[str]) -> list[str]:
    """Extract terms that a data publisher directly attaches to numeric growth."""

    candidates: list[str] = []
    patterns = (
        r"\b((?:[A-Za-z][A-Za-z'’\-–]*\s+){0,6}[A-Za-z][A-Za-z'’\-–]*)\s*\(\s*\+?[\d,]+(?:\.\d+)?%[^)]*\)",
        r"\b(?:searches|demand|interest|adoption|buzz)\s+for\s+([A-Za-z][A-Za-z'’\-–\s]{1,45}?)\s+(?:was|were|is|are|has|have|rose|grew|increased|surged|climbed|up)\b",
        r"\b([A-Za-z][A-Za-z'’\-–\s]{1,45}?)\s+(?:rose|grew|increased|surged|climbed|was up|were up|is up|are up)\s+\+?\d+(?:\.\d+)?%",
    )
    for paragraph in list(paragraphs)[:80]:
        text = _clean_text(paragraph)
        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.I):
                label = _clean_label(match.group(1))
                # Prevent a regex from swallowing the preceding sentence.
                label = re.split(r"[.;:]", label)[-1].strip()
                label = re.split(
                    r"\b(?:while|whereas|alongside|through|including|like|via)\b",
                    label,
                    flags=re.I,
                )[-1].strip()
                words = label.split()
                if len(words) > 5:
                    label = " ".join(words[-5:])
                label = _clean_label(label)
                if 1 <= len(label.split()) <= 7:
                    candidates.append(label)
    return candidates


def extract_explicit_trend_labels(
    *,
    title: str,
    headings: Iterable[str],
    taxonomy_text: Iterable[str] = (),
    paragraphs: Iterable[str] = (),
    url: str = "",
    reference_year: int | None = None,
    quantified: bool = False,
) -> list[dict[str, str]]:
    """Extract publisher-explicit labels without open-ended body mining."""

    candidates: list[tuple[str, str, str]] = []
    for label in _candidate_from_singular_trend(title):
        candidates.append((label, "article title", title))
    for label in _candidate_from_url_slug(url, title):
        candidates.append((label, "publisher URL label", url))

    title_is_report = _is_trend_report_title(title)
    if title_is_report:
        for heading in headings:
            heading_text = _clean_text(heading)
            if not heading_text or len(heading_text) > 90:
                continue
            if re.search(
                r"(?:related posts|read more|shop(?:\s+the)?|why trust|meet the|download|subscribe|newsletter|contents|jump to|in the magazine|more great|latest videos|about the author|frequently asked|key takeaways|what's inside|what’s inside)",
                heading_text,
                flags=re.I,
            ):
                continue
            year_match = re.match(r"^((?:19|20)\d{2})\b", heading_text)
            if year_match and reference_year and int(year_match.group(1)) < reference_year - 1:
                continue
            heading_candidates = [heading_text]
            if re.match(r"^\s*(?:#?\d{1,2}|[ivx]{1,5})[.)\-:]", heading_text, re.I):
                without_number = re.sub(
                    r"^\s*(?:#?\d{1,2}|[ivx]{1,5})[.)\-:]\s*",
                    "",
                    heading_text,
                    flags=re.I,
                )
                if " & " in without_number:
                    heading_candidates = without_number.split(" & ")
            for heading_candidate in heading_candidates:
                label = _clean_label(heading_candidate)
                if label and not _is_trend_report_title(label):
                    candidates.append((label, "trend-labelled heading", heading_text))

        for label in _candidate_from_declarations(paragraphs):
            candidates.append((label, "explicit article declaration", label))
        if quantified:
            for label in _candidate_from_quantified_text(paragraphs):
                candidates.append((label, "quantified publisher signal", label))

    for raw in taxonomy_text:
        text = _clean_text(raw)
        match = re.search(r"see all\s+(.+?)\s+looks", text, flags=re.I)
        label = _clean_label(match.group(1) if match else text)
        if label:
            candidates.append((label, "runway taxonomy", text))

    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for candidate, evidence_kind, explicit_text in candidates:
        candidate_text = _clean_label(candidate)
        product_groups = {
            token
            for token in re.findall(
                r"\b(?:bags?|belts?|blazers?|boots?|coats?|dresses?|flats?|"
                r"jackets?|jeans?|loafers?|pants?|pumps?|sandals?|shirts?|"
                r"shoes?|skirts?|sneakers?|tops?|totes?|trousers?)\b",
                candidate_text.casefold(),
            )
        }
        if (
            len(candidate_text.split()) > 7
            or len(product_groups) > 1
            or re.match(
                r"^(?:how to|is (?:the|this)|why |what |we need|fashion people|"
                r"paris couture week|fashion week|fashion director)",
                candidate_text,
                flags=re.I,
            )
            or re.search(r"\b(?:styling tips?|outfit ideas?)\b", candidate_text, re.I)
            or re.match(
                r"^(?:spring|summer|fall|autumn|winter)\s+"
                r"(?:bags?|coats?|colour|color|dresses?|fashion|jackets?|"
                r"pants?|shoes?|skirts?|sneakers?|style|tops?|trousers?)$",
                candidate_text,
                flags=re.I,
            )
        ):
            continue
        name = canonical_name(candidate_text)
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
        self.heading_rows: list[dict[str, str]] = []
        self.paragraphs: list[str] = []
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
        if lower in {"title", "h1", "h2", "h3", "h4", "a", "time", "p"}:
            self._captures.append(
                {
                    "tag": lower,
                    "text": [],
                    "size": 0,
                    "href": attributes.get("href", ""),
                    "datetime": attributes.get("datetime", ""),
                    "class": attributes.get("class", ""),
                    "id": attributes.get("id", ""),
                }
            )
        elif lower == "script" and "ld+json" in attributes.get("type", "").casefold():
            self._captures.append({"tag": "script", "text": [], "size": 0})

    def handle_data(self, data: str) -> None:
        for capture in self._captures:
            # Bound malformed or script-heavy publisher pages. Nested inline
            # tags still contribute to their containing heading/paragraph, but
            # one unclosed element cannot grow without limit.
            remaining = 5_000 - int(capture.get("size") or 0)
            if remaining > 0:
                part = data[:remaining]
                capture["text"].append(part)
                capture["size"] = int(capture.get("size") or 0) + len(part)

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
                if len(self.headings) < 400:
                    self.headings.append(text)
                    self.heading_rows.append(
                        {
                            "tag": lower,
                            "text": text,
                            "class": str(capture.get("class") or ""),
                            "id": str(capture.get("id") or ""),
                        }
                    )
            elif lower == "p" and text:
                if len(self.paragraphs) < 120:
                    self.paragraphs.append(text[:1_200])
            elif lower == "a" and text and capture.get("href"):
                if len(self.links) < 2_000:
                    self.links.append((text[:500], str(capture["href"])))
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
    requested = urljoin(requested_url, requested_url)
    url = requested
    for candidate in (page.canonical, structured_url):
        absolute = urljoin(requested_url, _clean_text(candidate))
        if not absolute:
            continue
        candidate_parts = urlparse(absolute)
        requested_parts = urlparse(requested)
        same_host = (
            candidate_parts.netloc.casefold().removeprefix("www.")
            == requested_parts.netloc.casefold().removeprefix("www.")
        )
        # Some CMS templates expose the organisation/homepage URL as the first
        # JSON-LD URL on every article. Never replace a specific requested page
        # with that root URL.
        if same_host and (
            candidate_parts.path.rstrip("/")
            or not requested_parts.path.rstrip("/")
        ):
            url = absolute
            break
    return {
        "title": _clean_text(title),
        "published_at": _clean_text(published),
        "url": url,
    }


def _source_headings(
    source: CommercialSource,
    page: _PageParser,
    url: str,
) -> list[str]:
    """Select editorial trend headings, excluding product cards and navigation."""

    rows = list(page.heading_rows)
    if source.key == "heuritech":
        return [
            row["text"]
            for row in rows
            if re.match(r"^\s*\d{1,2}[.)\-:]\s+", row["text"])
        ]
    if source.key in {"whowhatwear", "whowhatwear-uk"}:
        title = _page_metadata(page, url).get("title") or page.title
        if not _is_multi_trend_report_title(title):
            return []
        return [
            row["text"]
            for row in rows
            if "article-body__section" in row.get("class", "")
        ]
    if source.key == "vogue":
        return [
            row["text"]
            for row in rows
            if row.get("tag") == "h2"
            and not re.search(
                r"product|commerce|price|brand|caption",
                row.get("class", ""),
                flags=re.I,
            )
        ]
    if source.key == "trendalytics":
        return [
            row["text"]
            for row in rows
            if row.get("tag") in {"h2", "h3"}
            and not row.get("class")
            and ":" not in row["text"]
            and len(row["text"].split()) <= 8
            and not re.match(
                r"^(?:by the numbers|high[- ]growth|key takeaways|download|related posts)",
                row["text"],
                flags=re.I,
            )
        ]
    if source.key == "data-but-make-it-fashion":
        # Substack headings include subtitles and paywall/navigation text. The
        # post title plus quantified body statements are the auditable signals.
        return []
    if source.key == "elle":
        return [
            row["text"]
            for row in rows
            if re.match(r"^\s*\d{1,2}[.)\-:]\s+", row["text"])
            or re.search(
                r"full-item-title|article-body__section",
                row.get("class", ""),
                flags=re.I,
            )
        ]
    return list(page.headings)


def _same_source_host(source: CommercialSource, url: str) -> bool:
    host = urlparse(url).netloc.casefold().removeprefix("www.")
    return any(host == allowed or host.endswith("." + allowed) for allowed in source.hosts)


def _clean_link_title(value: str) -> str:
    title = _clean_text(value)
    title = re.split(r"\s+(?:By\s+[A-Z]|Sponsor Content|Created With)\b", title, maxsplit=1)[0]
    return title[:240]


def _fashion_article_score(title: str, url: str) -> int:
    lowered = f"{title} {url}".casefold()
    if any(
        cue in lowered
        for cue in (
            "/privacy", "/terms", "/author", "/login", "request a demo",
            "newsletter", "promo code", "horoscope",
        )
    ):
        return -100
    fashion_cues = (
        "fashion", "trend", "runway", "style", "wear", "dress", "denim",
        "bag", "handbag", "shoe", "flat", "sandal", "boot", "jacket",
        "skirt", "trouser", "pant", "blouse", "shirt", "jewellery",
        "jewelry", "accessory", "apparel", "menswear", "womenswear",
        "fabric", "colour", "color", "print", "silhouette", "streetwear",
    )
    non_fashion = ("beauty", "wellness", "makeup", "fragrance", "skin care", "home decor")
    if any(cue in lowered for cue in non_fashion) and not any(
        cue in lowered for cue in fashion_cues[5:]
    ):
        return -50
    score = 0
    score += 12 if "trend" in lowered else 0
    score += 7 if any(cue in lowered for cue in ("forecast", "runway", "fashion week")) else 0
    score += 4 if any(cue in lowered for cue in fashion_cues[5:]) else 0
    score += 2 if any(cue in url.casefold() for cue in ARTICLE_PATH_CUES) else 0
    score += 1 if re.search(r"\b20(?:25|26|27)\b", title) else 0
    return score


def _article_links(
    source: CommercialSource,
    page: _PageParser,
    index_url: str,
) -> list[tuple[str, str]]:
    ranked: list[tuple[int, int, str, str]] = []
    seen: set[str] = set()
    for position, (text, href) in enumerate(page.links):
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
        title = _clean_link_title(text)
        text_lower = title.casefold()
        path_match = any(cue in lowered for cue in ARTICLE_PATH_CUES)
        title_match = any(cue in text_lower for cue in TREND_REPORT_CUES)
        if not (path_match and (title_match or len(title.split()) >= 4)):
            continue
        if len(title.split()) <= 2 and re.search(
            r"/(?:trends?|runway|spring|summer|fall|winter)/?$", lowered
        ):
            continue
        score = _fashion_article_score(title, absolute)
        if score <= 0:
            continue
        seen.add(absolute)
        ranked.append((score, -position, title, absolute))
    ranked.sort(reverse=True)
    return [(title, url) for _, _, title, url in ranked[: source.max_articles]]


def _xml_local(tag: str) -> str:
    return str(tag or "").rsplit("}", 1)[-1].casefold()


def _xml_child_text(node: ET.Element, *names: str) -> str:
    wanted = {name.casefold() for name in names}
    for child in node.iter():
        if _xml_local(child.tag) in wanted and _clean_text(child.text):
            return _clean_text(child.text)
    return ""


def parse_feed_entries(xml_text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(str(xml_text or ""))
    except ET.ParseError:
        return []
    output: list[dict[str, str]] = []
    for node in root.iter():
        if _xml_local(node.tag) not in {"item", "entry"}:
            continue
        title = _xml_child_text(node, "title")
        url = _xml_child_text(node, "link")
        if not url:
            for child in node:
                if _xml_local(child.tag) == "link" and child.attrib.get("href"):
                    url = _clean_text(child.attrib["href"])
                    break
        published = _xml_child_text(node, "pubdate", "published", "updated", "date")
        if title and url:
            output.append({"title": title, "url": url, "published_at": published})
    return output


def parse_sitemap(xml_text: str) -> tuple[list[dict[str, str]], list[str]]:
    try:
        root = ET.fromstring(str(xml_text or ""))
    except ET.ParseError:
        return [], []
    entries: list[dict[str, str]] = []
    children: list[str] = []
    if _xml_local(root.tag) == "sitemapindex":
        for node in root:
            if _xml_local(node.tag) == "sitemap":
                url = _xml_child_text(node, "loc")
                if url:
                    children.append(url)
        return entries, children
    for node in root:
        if _xml_local(node.tag) != "url":
            continue
        url = _xml_child_text(node, "loc")
        if not url:
            continue
        entries.append(
            {
                "url": url.split("#", 1)[0],
                "title": _xml_child_text(node, "title"),
                "published_at": _xml_child_text(
                    node, "publication_date", "lastmod"
                ),
            }
        )
    return entries, children


def _recent_sitemap_children(urls: Iterable[str], now: datetime) -> list[str]:
    current = now.strftime("%Y-%m")
    previous_month = (now.replace(day=1).timestamp() - 86400)
    previous = datetime.fromtimestamp(previous_month, tz=timezone.utc).strftime("%Y-%m")
    scored: list[tuple[int, str]] = []
    for url in urls:
        lowered = url.casefold()
        score = 3 if "sitemap-news" in lowered else 2 if current in lowered else 1 if previous in lowered else 0
        if score:
            scored.append((score, url))
    return [url for _, url in sorted(scored, reverse=True)[:2]]


def _taxonomy_links(page: _PageParser, index_url: str) -> list[tuple[str, str]]:
    ranked: list[tuple[int, int, str, str]] = []
    for position, (text, href) in enumerate(page.links):
        absolute = urljoin(index_url, href).split("#", 1)[0]
        match = re.search(
            r"/en/trends/woman/(?:resort|fall-winter|pre-fall|spring-summer)-(\d{2,4})",
            absolute.casefold(),
        )
        if not match:
            continue
        raw_year = int(match.group(1))
        year = 2000 + raw_year if raw_year < 100 else raw_year
        ranked.append((year, -position, _clean_text(text), absolute))
    ranked.sort(reverse=True)
    output: list[tuple[str, str]] = []
    seen: set[str] = set()
    for _, _, title, url in ranked:
        if url in seen:
            continue
        seen.add(url)
        output.append((title, url))
    return output


def extract_lyst_product_labels(html: str) -> list[str]:
    labels: list[str] = []
    for match in re.finditer(
        r"<div\b[^>]*class=[\"'][^\"']*\bproduct-text\b[^\"']*[\"'][^>]*>(.*?)</div>",
        str(html or ""),
        flags=re.I | re.S,
    ):
        value = re.sub(r"<[^>]+>", " ", match.group(1))
        label = _clean_label(html_lib.unescape(value))
        if label:
            labels.append(label)
    return list(dict.fromkeys(labels))


def _lyst_report_links(page: _PageParser, index_url: str) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    seen: set[str] = set()
    for text, href in page.links:
        absolute = urljoin(index_url, href).split("#", 1)[0]
        if not re.search(r"/(?:data/)?the-lyst-index/q\d", absolute.casefold()):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        output.append((_clean_link_title(text) or "Latest Lyst Index", absolute))
    return output


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.7,
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
            "Accept": "text/html,application/xhtml+xml,application/xml,text/xml;q=0.9,*/*;q=0.5",
            "Accept-Language": "en-GB,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        }
    )
    return session


class CommercialSourceCollector:
    """Collect named trends from each approved publisher with layered discovery.

    Category HTML is the first route, publisher-owned feeds/sitemaps are the
    second, and a domain-restricted SerpApi query is used only when a publisher
    still yields no evidence. Each source runs in isolation and reports exactly
    which route worked.
    """

    def __init__(
        self,
        *,
        sources: Iterable[CommercialSource] = COMMERCIAL_SOURCES,
        timeout_seconds: int = 20,
        max_workers: int = 4,
        session: requests.Session | None = None,
        serpapi_api_key: str = "",
        serpapi_endpoint: str = "https://serpapi.com/search.json",
    ) -> None:
        self.sources = tuple(sources)
        self.timeout_seconds = max(8, int(timeout_seconds))
        self.max_workers = max(1, min(6, int(max_workers)))
        self._provided_session = session
        self.serpapi_api_key = str(serpapi_api_key or "").strip()
        self.serpapi_endpoint = str(serpapi_endpoint or "").strip()
        self._article_documents: list[dict[str, Any]] = []
        self._article_lock = Lock()

    def _source_session(self) -> requests.Session:
        return self._provided_session or _session()

    def _fetch(
        self,
        session: requests.Session,
        url: str,
        *,
        allow_xml: bool = False,
    ) -> tuple[str, str]:
        response = session.get(url, timeout=self.timeout_seconds)
        if not response.ok:
            raise CommercialSourceError(f"HTTP {response.status_code} for {url}")
        headers = getattr(response, "headers", {}) or {}
        content_type = str(headers.get("Content-Type") or "")
        accepted = "html" in content_type.casefold() or (
            allow_xml and "xml" in content_type.casefold()
        )
        if content_type and not accepted:
            raise CommercialSourceError(
                f"Unsupported response type {content_type[:80]} for {url}"
            )
        text = str(getattr(response, "text", "") or "")
        if len(text) > 4_000_000:
            raise CommercialSourceError(f"Response exceeded 4 MB for {url}")
        return text, str(getattr(response, "url", "") or url)

    @staticmethod
    def _base_status(source: CommercialSource) -> dict[str, Any]:
        return {
            "publisher": source.name,
            "state": "FAILED",
            "pages_requested": 0,
            "pages_loaded": 0,
            "articles_found": 0,
            "articles_loaded": 0,
            "evidence_rows": 0,
            "named_trends": 0,
            "search_fallback_used": False,
            "search_requests": 0,
            "search_results": 0,
            "discovery_methods": [],
            "errors": [],
        }

    @staticmethod
    def _publisher_evidence(
        source: CommercialSource,
        labels: Iterable[dict[str, str]],
        *,
        title: str,
        url: str,
        published_at: str,
        collected_at: str,
        acquisition: str,
    ) -> list[dict[str, Any]]:
        group = source.publisher_group or source.key
        return [
            {
                **label,
                "publisher": source.name,
                "publisher_id": source.key,
                "publisher_group": group,
                "publisher_weight": source.weight,
                "article_title": title,
                "published_at": published_at,
                "url": url,
                "collected_at": collected_at,
                "acquisition": acquisition,
                "explicit": True,
            }
            for label in labels
        ]

    def _record_article_document(
        self,
        source: CommercialSource,
        page: _PageParser,
        *,
        title: str,
        url: str,
        published_at: str,
        collected_at: str,
        acquisition: str,
        labels: Iterable[dict[str, str]],
    ) -> None:
        """Keep bounded article text in memory for GPT extraction.

        Full article text is never written to the weekly snapshot. The refresh
        passes this short-lived representation to the extraction model and then
        persists only article metadata, short evidence excerpts and source URLs.
        """

        paragraphs: list[str] = []
        seen: set[str] = set()
        character_count = 0
        for raw in page.paragraphs[:120]:
            paragraph = _clean_text(raw)
            fingerprint = paragraph.casefold()
            if len(paragraph) < 30 or fingerprint in seen:
                continue
            if any(
                cue in fingerprint
                for cue in (
                    "when you purchase through links",
                    "sign up for our newsletter",
                    "all products featured",
                    "latest videos from",
                )
            ):
                continue
            remaining = 12_000 - character_count
            if remaining <= 0:
                break
            paragraph = paragraph[:remaining]
            paragraphs.append(paragraph)
            seen.add(fingerprint)
            character_count += len(paragraph)

        final_url = str(url or "")
        article_id = (
            f"{source.key}-"
            + hashlib.sha256(final_url.encode("utf-8")).hexdigest()[:12]
        )
        document = {
            "article_id": article_id,
            "publisher": source.name,
            "publisher_id": source.key,
            "publisher_group": source.publisher_group or source.key,
            "publisher_weight": source.weight,
            "title": _clean_text(title),
            "url": final_url,
            "published_at": str(published_at or ""),
            "collected_at": collected_at,
            "acquisition": acquisition,
            "headings": list(
                dict.fromkeys(
                    _source_headings(source, page, final_url)
                )
            )[:40],
            "paragraphs": paragraphs,
            "deterministic_labels": [
                dict(row) for row in labels if isinstance(row, dict)
            ],
        }
        with self._article_lock:
            self._article_documents.append(document)

    def _article_evidence(
        self,
        session: requests.Session,
        source: CommercialSource,
        url: str,
        fallback_title: str,
        fallback_published: str,
        *,
        collected_at: str,
        now: datetime,
        acquisition: str,
    ) -> list[dict[str, Any]]:
        html, final_url = self._fetch(session, url)
        page = parse_page(html)
        metadata = _page_metadata(page, final_url)
        title = metadata["title"] or fallback_title
        published = parse_utc(metadata["published_at"] or fallback_published)
        if published is not None:
            age_days = max(0.0, (now - published).total_seconds() / 86400)
            if age_days > source.max_age_days:
                return []
        final_published = published.isoformat() if published else ""
        final_url = metadata["url"] or final_url
        headings = _source_headings(source, page, final_url)
        labels = extract_explicit_trend_labels(
            title=title,
            headings=headings,
            paragraphs=page.paragraphs,
            url=final_url,
            reference_year=now.year,
            quantified=source.key in {
                "trendalytics",
                "data-but-make-it-fashion",
            },
        )
        if not labels and fallback_title:
            # RSS, sitemap and category-link titles are publisher-owned labels.
            # They remain useful when the article body is a JS shell or bot wall,
            # but still have to pass the same explicit-title specificity filter.
            labels = extract_explicit_trend_labels(
                title=fallback_title,
                headings=(),
                url=url,
                reference_year=now.year,
            )
        self._record_article_document(
            source,
            page,
            title=title,
            url=final_url,
            published_at=final_published,
            collected_at=collected_at,
            acquisition=acquisition,
            labels=labels,
        )
        return self._publisher_evidence(
            source,
            labels,
            title=title,
            url=final_url,
            published_at=final_published,
            collected_at=collected_at,
            acquisition=acquisition,
        )

    def _taxonomy_evidence(
        self,
        session: requests.Session,
        source: CommercialSource,
        title: str,
        url: str,
        *,
        collected_at: str,
        now: datetime,
    ) -> list[dict[str, Any]]:
        html, final_url = self._fetch(session, url)
        page = parse_page(html)
        metadata = _page_metadata(page, final_url)
        taxonomy = [
            text
            for text, _ in page.links
            if re.search(r"see all\s+.+?\s+looks", text, flags=re.I)
        ]
        labels = extract_explicit_trend_labels(
            title=metadata["title"] or title or "Tagwalk runway trends",
            headings=(),
            taxonomy_text=taxonomy,
            url=metadata["url"] or final_url,
            reference_year=now.year,
        )
        return self._publisher_evidence(
            source,
            labels,
            title=metadata["title"] or title or "Tagwalk Trends",
            url=metadata["url"] or final_url,
            published_at="",
            collected_at=collected_at,
            acquisition="publisher taxonomy",
        )

    def _lyst_evidence(
        self,
        session: requests.Session,
        source: CommercialSource,
        title: str,
        url: str,
        *,
        collected_at: str,
        now: datetime,
    ) -> list[dict[str, Any]]:
        html, final_url = self._fetch(session, url)
        page = parse_page(html)
        metadata = _page_metadata(page, final_url)
        labels = extract_explicit_trend_labels(
            title=metadata["title"] or title,
            headings=(),
            taxonomy_text=extract_lyst_product_labels(html),
            url=metadata["url"] or final_url,
            reference_year=now.year,
        )
        # The Lyst product list is a commercial ranking, not runway taxonomy.
        for label in labels:
            if label.get("evidence_kind") == "runway taxonomy":
                label["evidence_kind"] = "Lyst hottest product"
        return self._publisher_evidence(
            source,
            labels,
            title=metadata["title"] or title or "Latest Lyst Index",
            url=metadata["url"] or final_url,
            published_at=metadata["published_at"],
            collected_at=collected_at,
            acquisition="publisher index report",
        )

    def _search_candidates(
        self,
        session: requests.Session,
        source: CommercialSource,
    ) -> list[dict[str, str]]:
        if not self.serpapi_api_key or not source.search_query:
            return []
        response = session.get(
            self.serpapi_endpoint,
            params={
                "engine": "google",
                "q": source.search_query,
                "num": min(10, source.max_articles),
                "hl": "en",
                "api_key": self.serpapi_api_key,
                "output": "json",
            },
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            raise CommercialSourceError(
                f"Domain-search fallback failed ({response.status_code})"
            )
        payload = response.json()
        if payload.get("error"):
            raise CommercialSourceError(str(payload["error"])[:220])
        output: list[dict[str, str]] = []
        for row in payload.get("organic_results") or []:
            if not isinstance(row, dict):
                continue
            url = str(row.get("link") or "").split("#", 1)[0]
            title = _clean_link_title(str(row.get("title") or ""))
            if not url or not title or not _same_source_host(source, url):
                continue
            if _fashion_article_score(title, url) <= 0:
                continue
            output.append(
                {
                    "title": title,
                    "url": url,
                    "published_at": str(row.get("date") or ""),
                    "acquisition": "domain-search fallback",
                }
            )
        return output[: source.max_articles]

    @staticmethod
    def _rank_candidates(
        source: CommercialSource,
        rows: Iterable[dict[str, str]],
    ) -> list[dict[str, str]]:
        best: dict[str, dict[str, str]] = {}
        for row in rows:
            url = str(row.get("url") or "").split("#", 1)[0]
            title = _clean_link_title(str(row.get("title") or ""))
            if not url or not _same_source_host(source, url):
                continue
            score = _fashion_article_score(title, url)
            if str(row.get("acquisition") or "") == "configured publisher report":
                score += 100
            if score <= 0:
                continue
            candidate = {
                "title": title,
                "url": url,
                "published_at": str(row.get("published_at") or ""),
                "acquisition": str(row.get("acquisition") or "publisher page"),
                "score": str(score),
            }
            current = best.get(url)
            if current is None or int(candidate["score"]) > int(current["score"]):
                best[url] = candidate
        ordered = sorted(
            best.values(),
            key=lambda row: (
                int(row.get("score") or 0),
                parse_utc(row.get("published_at"))
                or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        return ordered[: source.max_articles]

    def _collect_source(
        self,
        source: CommercialSource,
        *,
        now: datetime,
        collected_at: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        session = self._source_session()
        status = self._base_status(source)
        evidence: list[dict[str, Any]] = []
        candidates: list[dict[str, str]] = [
            {
                "title": url.rsplit("/", 1)[-1].replace("-", " "),
                "url": url,
                "published_at": "",
                "acquisition": "configured publisher report",
            }
            for url in source.article_urls
        ]
        index_pages: list[tuple[str, _PageParser]] = []
        if source.article_urls:
            status["discovery_methods"].append("configured current report")

        for url in source.index_urls:
            status["pages_requested"] += 1
            try:
                html, final_url = self._fetch(session, url)
                page = parse_page(html)
                index_pages.append((final_url, page))
                status["pages_loaded"] += 1
                status["discovery_methods"].append("category/archive HTML")
            except Exception as exc:
                status["errors"].append(str(exc)[:260])

        if source.kind == "taxonomy":
            taxonomy_jobs: list[tuple[str, str]] = []
            for final_url, page in index_pages:
                taxonomy_jobs.extend(_taxonomy_links(page, final_url))
            status["articles_found"] = min(len(taxonomy_jobs), source.max_articles)
            for title, url in taxonomy_jobs[: source.max_articles]:
                status["pages_requested"] += 1
                try:
                    rows = self._taxonomy_evidence(
                        session,
                        source,
                        title,
                        url,
                        collected_at=collected_at,
                        now=now,
                    )
                    status["pages_loaded"] += 1
                    status["articles_loaded"] += 1
                    evidence.extend(rows)
                except Exception as exc:
                    status["errors"].append(str(exc)[:260])
        elif source.kind == "lyst":
            report_links: list[tuple[str, str]] = []
            for final_url, page in index_pages:
                report_links.extend(_lyst_report_links(page, final_url))
            status["articles_found"] = min(len(report_links), source.max_articles)
            for title, url in report_links[: source.max_articles]:
                status["pages_requested"] += 1
                try:
                    rows = self._lyst_evidence(
                        session,
                        source,
                        title,
                        url,
                        collected_at=collected_at,
                        now=now,
                    )
                    status["pages_loaded"] += 1
                    status["articles_loaded"] += 1
                    evidence.extend(rows)
                except Exception as exc:
                    status["errors"].append(str(exc)[:260])
        else:
            for final_url, page in index_pages:
                candidates.extend(
                    {
                        "title": title,
                        "url": url,
                        "published_at": "",
                        "acquisition": "category/archive HTML",
                    }
                    for title, url in _article_links(source, page, final_url)
                )

            for feed_url in source.feed_urls:
                status["pages_requested"] += 1
                try:
                    xml_text, _ = self._fetch(session, feed_url, allow_xml=True)
                    entries = parse_feed_entries(xml_text)
                    status["pages_loaded"] += 1
                    status["discovery_methods"].append("publisher RSS")
                    candidates.extend(
                        {**entry, "acquisition": "publisher RSS"}
                        for entry in entries
                    )
                except Exception as exc:
                    status["errors"].append(str(exc)[:260])

            for sitemap_url in source.sitemap_urls:
                status["pages_requested"] += 1
                try:
                    xml_text, _ = self._fetch(session, sitemap_url, allow_xml=True)
                    entries, children = parse_sitemap(xml_text)
                    status["pages_loaded"] += 1
                    status["discovery_methods"].append("publisher sitemap")
                    candidates.extend(
                        {**entry, "acquisition": "publisher sitemap"}
                        for entry in entries
                    )
                    for child_url in _recent_sitemap_children(children, now):
                        status["pages_requested"] += 1
                        child_text, _ = self._fetch(
                            session, child_url, allow_xml=True
                        )
                        child_entries, _ = parse_sitemap(child_text)
                        status["pages_loaded"] += 1
                        candidates.extend(
                            {**entry, "acquisition": "publisher sitemap"}
                            for entry in child_entries
                        )
                except Exception as exc:
                    status["errors"].append(str(exc)[:260])

            ranked = self._rank_candidates(source, candidates)
            status["articles_found"] = len(ranked)
            for candidate in ranked:
                status["pages_requested"] += 1
                try:
                    rows = self._article_evidence(
                        session,
                        source,
                        candidate["url"],
                        candidate["title"],
                        candidate["published_at"],
                        collected_at=collected_at,
                        now=now,
                        acquisition=candidate["acquisition"],
                    )
                    status["pages_loaded"] += 1
                    status["articles_loaded"] += 1
                    evidence.extend(rows)
                except Exception as exc:
                    status["errors"].append(str(exc)[:260])

        named_before_search = len({row.get("trend_id") for row in evidence})
        search_threshold = min(4, max(2, source.max_articles // 2))
        if (
            named_before_search < search_threshold
            and self.serpapi_api_key
            and source.search_query
        ):
            status["search_fallback_used"] = True
            try:
                status["search_requests"] += 1
                search_rows = self._search_candidates(session, source)
                status["search_results"] = len(search_rows)
                status["discovery_methods"].append("domain-restricted search")
                for candidate in search_rows:
                    status["pages_requested"] += 1
                    try:
                        rows = self._article_evidence(
                            session,
                            source,
                            candidate["url"],
                            candidate["title"],
                            candidate["published_at"],
                            collected_at=collected_at,
                            now=now,
                            acquisition=candidate["acquisition"],
                        )
                        if not rows:
                            labels = extract_explicit_trend_labels(
                                title=candidate["title"],
                                headings=(),
                                url=candidate["url"],
                                reference_year=now.year,
                            )
                            rows = self._publisher_evidence(
                                source,
                                labels,
                                title=candidate["title"],
                                url=candidate["url"],
                                published_at=candidate["published_at"],
                                collected_at=collected_at,
                                acquisition="publisher-domain search title",
                            )
                        status["articles_loaded"] += 1
                        status["pages_loaded"] += 1
                        evidence.extend(rows)
                    except Exception as exc:
                        # A descriptive, publisher-domain search title remains
                        # traceable evidence when the destination blocks bots.
                        labels = extract_explicit_trend_labels(
                            title=candidate["title"],
                            headings=(),
                            url=candidate["url"],
                            reference_year=now.year,
                        )
                        evidence.extend(
                            self._publisher_evidence(
                                source,
                                labels,
                                title=candidate["title"],
                                url=candidate["url"],
                                published_at=candidate["published_at"],
                                collected_at=collected_at,
                                acquisition="publisher-domain search title",
                            )
                        )
                        status["errors"].append(str(exc)[:260])
            except Exception as exc:
                status["errors"].append(str(exc)[:260])

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for row in evidence:
            identity = (str(row.get("trend_id") or ""), str(row.get("url") or ""))
            if not all(identity) or identity in seen:
                continue
            seen.add(identity)
            deduped.append(row)
        status["evidence_rows"] = len(deduped)
        status["named_trends"] = len({row.get("trend_id") for row in deduped})
        status["discovery_methods"] = list(dict.fromkeys(status["discovery_methods"]))
        if deduped:
            status["state"] = "LIVE" if not status["errors"] else "PARTIAL"
        elif status["pages_loaded"] or status["search_results"]:
            status["state"] = "PARTIAL"
        else:
            status["state"] = "FAILED"
        return deduped, status

    def collect(self, *, now: datetime | None = None) -> dict[str, Any]:
        reference = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
        collected_at = reference.isoformat()
        with self._article_lock:
            self._article_documents = []
        evidence: list[dict[str, Any]] = []
        statuses: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_map = {
                executor.submit(
                    self._collect_source,
                    source,
                    now=reference,
                    collected_at=collected_at,
                ): source
                for source in self.sources
            }
            for future in as_completed(future_map):
                source = future_map[future]
                try:
                    rows, status = future.result()
                    evidence.extend(rows)
                    statuses[source.key] = status
                except Exception as exc:
                    status = self._base_status(source)
                    status["errors"] = [str(exc)[:260]]
                    statuses[source.key] = status

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

        article_documents: list[dict[str, Any]] = []
        seen_articles: set[str] = set()
        with self._article_lock:
            recorded_articles = list(self._article_documents)
        for row in recorded_articles:
            identity = str(row.get("url") or row.get("article_id") or "")
            if not identity or identity in seen_articles:
                continue
            seen_articles.add(identity)
            article_documents.append(row)
        article_documents.sort(
            key=lambda row: (
                parse_utc(row.get("published_at"))
                or datetime.min.replace(tzinfo=timezone.utc),
                str(row.get("publisher") or ""),
            ),
            reverse=True,
        )

        return {
            "evidence": deduped_evidence,
            "articles": article_documents,
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
            "publishers_with_evidence": sum(
                int(row.get("named_trends") or 0) > 0 for row in statuses.values()
            ),
            "publishers_without_evidence": sum(
                not int(row.get("named_trends") or 0) for row in statuses.values()
            ),
            "articles_loaded": sum(
                int(row.get("articles_loaded") or 0) for row in statuses.values()
            ),
            "evidence_rows": len(deduped_evidence),
            "named_trends": len(
                {str(row.get("trend_id") or "") for row in deduped_evidence}
            ),
            "collected_at": collected_at,
        }

    def test_connection(self) -> dict[str, Any]:
        result = self.collect()
        return {
            "ok": bool(result.get("evidence_rows"))
            and int(result.get("publishers_with_evidence") or 0)
            == int(result.get("publishers_requested") or 0),
            "publishers_live": result.get("publishers_live", 0),
            "publishers_partial": result.get("publishers_partial", 0),
            "publishers_failed": result.get("publishers_failed", 0),
            "publishers_with_evidence": result.get("publishers_with_evidence", 0),
            "publishers_without_evidence": result.get("publishers_without_evidence", 0),
            "evidence_rows": result.get("evidence_rows", 0),
            "named_trends": result.get("named_trends", 0),
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
            str(
                item.get("publisher_group")
                or item.get("publisher_id")
                or item.get("publisher")
                or ""
            )
            for item in items
            if item.get("publisher_group")
            or item.get("publisher_id")
            or item.get("publisher")
        }
        publisher_names = list(
            dict.fromkeys(
                str(item.get("publisher") or "")
                for item in items
                if item.get("publisher")
            )
        )
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
                "publisher_names": publisher_names,
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
