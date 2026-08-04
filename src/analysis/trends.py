from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.analysis.freshness import google_display_series, parse_utc, validate_series


CANONICAL_PHRASES = {
    "east west bag": "East–West Bags",
    "eastwest bag": "East–West Bags",
    "elongated bag": "East–West Bags",
    "ballet flat": "Ballet Flats",
    "ballet flats": "Ballet Flats",
    "ballet pump": "Ballet Flats",
    "ballet pumps": "Ballet Flats",
    "balletcore shoe": "Ballet Flats",
    "balletcore shoes": "Ballet Flats",
    "mary jane": "Mary Janes",
    "mary janes": "Mary Janes",
    # The X phrase extractor can shorten "Mary Jane shoes" to "jane". HULA
    # explicitly treats that fashion shorthand as the shoe trend, not a person.
    "jane": "Mary Janes",
    "fisherman sandal": "Fisherman Sandals",
    "fisherman sandals": "Fisherman Sandals",
    "butter yellow": "Butter Yellow",
    "buttery yellow": "Butter Yellow",
    "polka dot": "Polka Dots",
    "polka dots": "Polka Dots",
    "leopard print": "Leopard Print",
    "animal print": "Animal Print",
    "raffia bag": "Raffia Bags",
    "raffia bags": "Raffia Bags",
    "woven bag": "Woven Bags",
    "woven bags": "Woven Bags",
    "scarf styling": "Scarf Styling",
    "scarf top": "Scarf Styling",
    "head scarf": "Scarf Styling",
    "capri pant": "Capri Pants",
    "capri pants": "Capri Pants",
    "pedal pusher": "Capri Pants",
    "pedal pushers": "Capri Pants",
    "drop waist": "Drop-Waist Dresses",
    "drop waist dress": "Drop-Waist Dresses",
    "dropped waist": "Drop-Waist Dresses",
    "crochet dress": "Crochet Dressing",
    "crochet dresses": "Crochet Dressing",
    "boho chic": "Boho Chic",
    "bohemian fashion": "Boho Chic",
    "nautical fashion": "Nautical Dressing",
    "sailor style": "Nautical Dressing",
    "charm jewellery": "Charm Jewellery",
    "charm jewelry": "Charm Jewellery",
    "bag charm": "Bag Charms",
    "bag charms": "Bag Charms",
    "maxi skirt": "Maxi Skirts",
    "maxi skirts": "Maxi Skirts",
    "jelly shoe": "Jelly Shoes",
    "jelly shoes": "Jelly Shoes",
    "suede bag": "Suede Bags",
    "suede bags": "Suede Bags",
    "statement belt": "Statement Belts",
    "statement belts": "Statement Belts",
    "vintage chanel": "Vintage Chanel",
    "barrel jean": "Barrel Jeans",
    "barrel jeans": "Barrel Jeans",
    "balloon jean": "Barrel Jeans",
    "quiet luxury": "Quiet Luxury",
    "archive fashion": "Designer Archives",
    "designer archive": "Designer Archives",
    "designer archives": "Designer Archives",
    "preowned fashion": "Pre-Owned Fashion",
    "pre owned fashion": "Pre-Owned Fashion",
    "pre loved fashion": "Pre-Owned Fashion",
    "preloved fashion": "Pre-Owned Fashion",
    "resale fashion": "Pre-Owned Fashion",
}

GENERIC_STOPWORDS = {
    "about", "after", "again", "also", "another", "because", "been", "before",
    "being", "best", "but", "buy", "can", "could", "designer", "every",
    "fashion", "fashionable", "for", "from", "get", "getting", "good", "great",
    "have", "here", "how", "into", "its", "just", "latest", "like", "look",
    "looks", "more", "most", "must", "new", "now", "one", "only", "our", "out",
    "people", "really", "right", "season", "shop", "shopping", "should", "some",
    "style", "styled", "styling", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "thing", "this", "those", "today", "trend", "trends",
    "trending", "very", "want", "wear", "wearing", "what", "when", "where", "which",
    "while", "who", "will", "with", "women", "your",
}

FASHION_CONTEXT = {
    "aesthetic", "archive", "bag", "bags", "ballet", "belt", "belts", "blazer",
    "boho", "boot", "boots", "bracelet", "capri", "cardigan", "charm", "chic",
    "coat", "colour", "color", "core", "corset", "crochet", "denim", "dress",
    "dresses", "earring", "earrings", "flat", "flats", "handbag", "heel", "heels",
    "jacket", "jane", "jean", "jeans", "jewellery", "jewelry", "lace", "leather",
    "leopard", "loafer", "loafers", "maxi", "metallic", "mini", "necklace", "outfit",
    "pants", "polka", "preloved", "print", "pump", "pumps", "raffia", "resale",
    "sandal", "sandals", "scarf", "sheer", "shoe", "shoes", "silhouette", "silk",
    "skirt", "sneaker", "sneakers", "suede", "tote", "trouser", "trousers", "tweed",
    "vintage", "waist", "woven",
}

EXACT_TREND_BLOCKLIST = {
    # The user-approved permanent exact-name list.
    "accessories", "accessory", "aesthetic", "amazon", "apparel", "bag", "bags",
    "chic", "classic", "clothes", "clothing", "color", "colour", "design", "ebay",
    "element", "etsy", "fashion", "footwear", "garment", "garments", "handbag",
    "handbags", "instagram", "jewellery", "jewelry", "outfit", "outfits", "pattern",
    "patterns", "pinterest", "platform", "print", "prints", "shopify", "shoe",
    "shoes", "silhouette", "silhouettes", "style", "styles", "tiktok", "trend",
    "trends", "twitter", "viral", "wear", "x",
    # Department/category nouns are never actionable by themselves. Specific
    # combinations such as pencil skirt, ballet flats and capri pants remain valid.
    "dress", "dresses", "flat", "flats", "mini", "outfit idea", "outfit ideas",
    "pant", "pants", "polka", "skirt", "skirts", "trouser", "trousers",
}

# User-approved exceptions that can represent a recognisable movement even
# without another descriptor. Singular department nouns are deliberately not
# inferred from these exceptions.
STANDALONE_TREND_ALLOWLIST = {"jeans", "loafers", "sandals"}

# Phrases that remain commercially meaningful despite using an otherwise
# generic modifier. Keep this list deliberately small and auditable.
SPECIFIC_PHRASE_ALLOWLIST = {"designer bags"}

# A trusted publisher/report may explicitly introduce a colour, material or
# aesthetic as a named trend. Raw social phrase extraction cannot do so.
TRUSTED_STANDALONE_ALLOWLIST = {
    "beige", "black", "blue", "brown", "burgundy", "camel", "check",
    "crochet", "denim", "feather", "floral", "fringe", "fringed", "fringes",
    "frill", "fur", "gray", "green", "grey", "khaki", "lace", "ladylike",
    "leather", "lingerie", "metallic", "minimal", "orange", "pink", "preppy",
    "purple", "raffia", "red", "romantic", "satin", "sheer", "silk", "stripes",
    "suede", "tailoring", "tweed", "utility", "white", "yellow",
}

GENERIC_FASHION_FILLERS = {
    "a", "all", "an", "best", "designer", "designers", "fashion", "fashionable",
    "female", "for", "idea", "ideas", "latest", "look", "looks", "luxury",
    "male", "men", "mens", "must", "new", "of", "s", "season", "style",
    "styles", "the", "trend", "trends", "trending", "wear", "woman", "women",
    "womens",
}

# These words make a headline sound editorial but do not make a category more
# actionable. For example, ``pretty dress`` and ``new skirt`` must not evade
# the exact-name blocklist merely by adding a vague adjective.
NON_SPECIFIC_DESCRIPTOR_TOKENS = {
    "beautiful", "best", "big", "biggest", "comfortable", "cool", "current",
    "dated", "elegant", "essential", "everyday", "favourite", "favorite",
    "fresh", "good", "great", "hot", "key", "large", "latest", "long",
    "major", "modern", "new", "nice", "popular", "pretty", "seasonal",
    "short", "small", "specific", "stylish", "timeless", "top", "unexpected",
    "viral",
}

# A candidate must contain at least one concrete fashion-domain cue. This is
# intentionally stricter than the broad-term filter: posts from fashion sources
# can still mention unrelated ideas such as interiors, wellness or kindness.
FASHION_PRODUCT_TOKENS = {
    "accessory", "accessories", "apparel", "bag", "bags", "belt", "belts",
    "blazer", "blazers", "blouse", "blouses", "boot", "boots", "bracelet",
    "bracelets", "cardigan", "cardigans", "clutch", "clutches", "coat",
    "coats", "corset", "corsets", "dress", "dresses", "earring", "earrings",
    "flat", "flats", "footwear", "gown", "gowns", "handbag", "handbags",
    "heel", "heels", "jacket", "jackets", "jean", "jeans", "jewellery",
    "jewelry", "loafer", "loafers", "necklace", "necklaces", "outfit",
    "outfits", "pant", "pants", "pump", "pumps", "sandal", "sandals",
    "scarf", "scarves", "shirt", "shirts", "shoe", "shoes", "silhouette",
    "silhouettes", "skirt", "skirts", "sneaker", "sneakers", "suit", "suits",
    "sweater", "sweaters", "tie", "ties", "top", "tops", "tote", "totes",
    "trainer", "trainers", "trouser", "trousers", "vest", "vests", "watch",
    "watches", "collar", "collars", "cuff", "cuffs", "hem", "hems",
    "neckline", "necklines", "pocket", "pockets", "shoulder", "shoulders",
    "sleeve", "sleeves",
}

FASHION_STYLE_TOKENS = {
    "animal", "archive", "asymmetrical", "athleisure", "babydoll", "ballet",
    "balletcore", "barrel", "boho", "bohemian", "bold", "burgundy", "bustier",
    "capri", "charm", "check", "coastal", "color", "colour", "coquette",
    "corsetry", "crochet", "denim", "drape", "drop", "feather", "floral",
    "frill", "fringe", "fringed", "fur", "gorpcore", "lace", "ladylike",
    "leather", "leopard", "lingerie", "maxi", "metallic", "minimalist",
    "maximalist", "nautical", "polka", "polo", "preloved", "preowned",
    "peplum", "preppy", "print", "puff", "puffed", "raffia", "resale",
    "romantic", "ruched", "ruffle", "ruffled", "satin", "sheer", "silk",
    "stripe", "stripes", "street", "streetwear", "suede", "tailoring",
    "transparent", "tweed", "utility", "vintage", "volume", "waist", "woven",
    "y2k",
}

FASHION_DOMAIN_TOKENS = {
    "couture", "fashion", "menswear", "runway", "sartorial", "streetwear",
    "wardrobe", "womenswear",
}

CATEGORY_RULES = {
    "Bags": {"bag", "bags", "handbag", "tote", "clutch", "raffia", "suede", "woven"},
    "Shoes": {"shoe", "shoes", "sandal", "sandals", "flat", "flats", "ballet", "boot", "boots", "loafer", "loafers", "heel", "heels", "pump", "pumps"},
    "Jewellery & Accessories": {"jewellery", "jewelry", "charm", "earring", "earrings", "necklace", "bracelet", "belt", "belts", "scarf"},
    "Ready-to-Wear": {"dress", "dresses", "skirt", "pants", "trousers", "jacket", "coat", "blazer", "cardigan", "denim", "jeans", "tweed", "crochet", "lace", "sheer"},
}

SOURCE_WEIGHTS = {
    "google": 0.35,
    "open_x": 0.20,
    "commercial": 0.35,
    "instagram": 0.10,
}


def slugify(value: str) -> str:
    value = value.lower().replace("–", "-").replace("—", "-")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "trend"


def _clean_phrase(value: str) -> str:
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    value = value.replace("_", " ").replace("-", " ").lower()
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def generic_trend_reason(value: str, *, trusted_source: bool = False) -> str:
    """Explain why a label is too broad or unrelated to fashion.

    A descriptor plus a product remains valid (``black bags`` or ``red
    trousers``). Category-only, vague-only, source/platform and non-fashion
    labels are removed before scoring.
    """

    phrase = _clean_phrase(value)
    if not phrase:
        return "Empty label"
    # Known ontology phrases are curated fashion concepts. This includes the
    # explicit Jane -> Mary Janes shorthand requested for HULA.
    if phrase in CANONICAL_PHRASES:
        return ""
    if phrase in EXACT_TREND_BLOCKLIST:
        return "Exact broad or non-actionable trend label"
    tokens = set(phrase.split())
    if len(tokens) == 1:
        if phrase in STANDALONE_TREND_ALLOWLIST:
            return ""
        if trusted_source and phrase in TRUSTED_STANDALONE_ALLOWLIST:
            return ""
        return "Standalone category or vague style label"
    if phrase in SPECIFIC_PHRASE_ALLOWLIST:
        return ""
    if not (
        tokens & FASHION_PRODUCT_TOKENS
        or tokens & FASHION_STYLE_TOKENS
        or tokens & FASHION_DOMAIN_TOKENS
    ):
        return "No clear fashion product, material, silhouette or style signal"
    if tokens & FASHION_PRODUCT_TOKENS:
        descriptors = tokens - FASHION_PRODUCT_TOKENS
        descriptors -= GENERIC_FASHION_FILLERS
        descriptors -= NON_SPECIFIC_DESCRIPTOR_TOKENS
        descriptors -= FASHION_DOMAIN_TOKENS
        if not descriptors:
            return "Category label has only vague or editorial descriptors"
    return ""


def generic_term_catalogue() -> list[str]:
    """Return the permanent exact-name blocklist for transparent UI display."""

    return sorted(EXACT_TREND_BLOCKLIST)


def _audit_filtered(
    audit: list[dict[str, str]] | None,
    term: str,
    source: str,
    reason: str | None = None,
) -> None:
    if audit is None:
        return
    cleaned = _clean_phrase(term)
    if not cleaned:
        return
    audit.append(
        {
            "term": str(term).strip(),
            "source": source,
            "reason": reason or generic_trend_reason(term),
        }
    )


def consolidate_filter_audit(
    rows: Iterable[dict[str, Any]],
) -> list[dict[str, str]]:
    """Deduplicate quality-control rows while retaining every observed source."""

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        term = str(row.get("term") or "").strip()
        if not term:
            continue
        key = _clean_phrase(term)
        current = grouped.setdefault(
            key,
            {
                "term": term,
                "reason": str(row.get("reason") or generic_trend_reason(term)),
                "sources": set(),
            },
        )
        source = str(row.get("source") or "Trend pipeline").strip()
        if source:
            current["sources"].add(source)
    return [
        {
            "term": row["term"],
            "reason": row["reason"],
            "source": ", ".join(sorted(row["sources"])),
        }
        for _, row in sorted(grouped.items())
    ]


def sanitize_snapshot_trends(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Remove broad or non-fashion labels before any page renders."""

    trends = list(snapshot.get("trends") or [])
    snapshot_meta = snapshot.get("meta") or {}
    audit = list(snapshot_meta.get("filtered_terms") or [])
    display_schema_current = str(
        snapshot_meta.get("google_display_schema_version") or ""
    ) == "2.0"
    google_status = str(
        (snapshot_meta.get("source_status") or {}).get("google_trends") or ""
    ).casefold()
    kept: list[dict[str, Any]] = []
    removed_ids: set[str] = set()
    remapped_ids: dict[str, str] = {}
    quality_changed = False
    for trend in trends:
        name = str(trend.get("name") or "")
        reason = generic_trend_reason(name)
        if reason:
            removed_ids.add(str(trend.get("id") or ""))
            _audit_filtered(audit, name, "Stored snapshot", reason)
        else:
            canonical = CANONICAL_PHRASES.get(_clean_phrase(name), name)
            normalised = dict(trend)
            if canonical != name:
                old_id = str(trend.get("id") or "")
                new_id = slugify(canonical)
                normalised["name"] = canonical
                normalised["id"] = new_id
                if old_id:
                    remapped_ids[old_id] = new_id

            series = list(normalised.get("series") or [])
            if series:
                cleaned, quality = validate_series(series)
                normalised["series"] = cleaned
                has_raw_index = bool(cleaned) and all(
                    point.get("raw_value") is not None for point in cleaned
                )
                can_display = bool(
                    has_raw_index
                    or display_schema_current
                    or "manual csv" in google_status
                )
                display_series, display_quality = google_display_series(cleaned)
                if can_display:
                    normalised["display_series"] = display_series
                    normalised["chart_ready"] = bool(
                        display_quality["chart_ready"]
                    )
                else:
                    normalised["display_series"] = []
                    normalised["chart_ready"] = False
                    display_quality = {
                        **display_quality,
                        "chart_ready": False,
                        "issue": (
                            "This older snapshot does not preserve Google's raw "
                            "0–100 display index; refresh it before charting"
                        ),
                    }
                quality = display_quality
                normalised["series_quality"] = quality
                normalised["series_issue"] = str(quality["issue"])
                if not quality["score_ready"]:
                    normalised["google_score"] = None
                    normalised["decision_ready"] = False

            has_google = normalised.get("google_score") is not None
            has_confirmation = any(
                normalised.get(component) is not None
                for component in (
                    "x_score",
                    "commercial_score",
                    "instagram_score",
                    "expert_score",
                    "visual_score",
                )
            )
            if normalised.get("decision_ready") and not (
                has_google and has_confirmation
            ):
                normalised["decision_ready"] = False
            if "decision_ready" in normalised:
                normalised["missing_components"] = [
                    label
                    for component, label in (
                        ("google_score", "Google Trends"),
                        ("x_score", "Open X"),
                        ("commercial_score", "commercial reports"),
                        ("instagram_score", "Instagram hashtag metadata"),
                    )
                    if normalised.get(component) is None
                ]
            quality_changed = quality_changed or normalised != trend
            kept.append(normalised)
    if (
        not removed_ids
        and not remapped_ids
        and not quality_changed
        and len(kept) == len(trends)
    ):
        return snapshot

    updated = dict(snapshot)
    updated["trends"] = kept
    recommendations: list[dict[str, Any]] = []
    for row in snapshot.get("recommendations") or []:
        trend_id = str(row.get("trend_id") or "")
        if trend_id in removed_ids:
            continue
        if trend_id in remapped_ids:
            row = {**row, "trend_id": remapped_ids[trend_id]}
        recommendations.append(row)
    updated["recommendations"] = recommendations
    meta = dict(snapshot.get("meta") or {})
    meta["filtered_terms"] = consolidate_filter_audit(audit)
    raw_counts = dict(meta.get("raw_counts") or {})
    raw_counts["filtered_generic_terms"] = len(meta["filtered_terms"])
    raw_counts["recommendations"] = len(updated["recommendations"])
    meta["raw_counts"] = raw_counts
    meta["quality_filter_version"] = "4.0"
    updated["meta"] = meta
    return updated


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {_clean_phrase(phrase)} " in f" {_clean_phrase(text)} "


def canonical_name(value: str) -> str:
    phrase = _clean_phrase(value)
    if phrase in CANONICAL_PHRASES:
        return CANONICAL_PHRASES[phrase]
    phrase_tokens = phrase.split()
    for source, target in CANONICAL_PHRASES.items():
        source_tokens = source.split()
        if len(source_tokens) >= 2 and len(phrase_tokens) >= 2 and _contains_phrase(phrase, source):
            return target
    return " ".join(word.capitalize() for word in phrase_tokens)


def _parse_datetime(value: Any) -> datetime | None:
    return parse_utc(value)


def _rank_scores(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [70.0]
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    for rank, index in enumerate(order):
        ranks[index] = 100 * rank / (len(values) - 1)
    return ranks


def discover_x_candidates(
    posts: list[dict[str, Any]],
    *,
    max_phrases: int = 70,
    audit: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Extract aggregated fashion phrases; raw post text never leaves this function."""

    texts = [str(post.get("text", "")).lower() for post in posts if post.get("text")]
    if not texts:
        return []
    hashtag_counts: Counter[str] = Counter()
    for text in texts:
        for hashtag in re.findall(r"#([a-zA-Z][a-zA-Z0-9_]{2,40})", text):
            phrase = _clean_phrase(hashtag)
            reason = generic_trend_reason(phrase)
            if reason:
                _audit_filtered(audit, phrase, "X hashtag", reason)
            elif phrase and phrase not in GENERIC_STOPWORDS:
                hashtag_counts[phrase] += 1

    candidates: Counter[str] = Counter()
    cleaned_texts = [_clean_phrase(text) for text in texts]
    for phrase in CANONICAL_PHRASES:
        count = sum(_contains_phrase(text, phrase) for text in cleaned_texts)
        if count:
            candidates[phrase] += count * 3

    min_df = 2 if len(texts) >= 10 else 1
    try:
        vectorizer = CountVectorizer(
            ngram_range=(1, 3),
            stop_words=sorted(GENERIC_STOPWORDS),
            min_df=min_df,
            max_features=1000,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9]{2,}\b",
        )
        matrix = vectorizer.fit_transform(texts)
        totals = np.asarray(matrix.sum(axis=0)).ravel()
        for phrase, count in zip(vectorizer.get_feature_names_out(), totals):
            tokens = set(phrase.split())
            if tokens & FASHION_CONTEXT and not tokens <= GENERIC_STOPWORDS:
                candidates[_clean_phrase(phrase)] += int(count)
    except ValueError:
        pass

    candidates.update({phrase: count * 2 for phrase, count in hashtag_counts.items()})
    output: list[dict[str, Any]] = []
    for phrase, count in candidates.most_common(max_phrases * 2):
        reason = generic_trend_reason(phrase)
        if reason:
            _audit_filtered(audit, phrase, "X phrase extraction", reason)
            continue
        tokens = phrase.split()
        if not phrase or (len(tokens) == 1 and phrase in GENERIC_STOPWORDS):
            continue
        output.append(
            {
                "phrase": phrase,
                "name": canonical_name(phrase),
                "count": int(count),
            }
        )
        if len(output) >= max_phrases:
            break
    return output


def _candidate_rows(
    candidates: Iterable[dict[str, Any] | str],
    *,
    audit: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if isinstance(candidate, dict):
            phrase = _clean_phrase(str(candidate.get("phrase") or candidate.get("name") or ""))
            count = int(candidate.get("count") or 1)
        else:
            phrase = _clean_phrase(str(candidate))
            count = 1
        reason = generic_trend_reason(phrase)
        if reason:
            _audit_filtered(audit, phrase, "Topic candidate", reason)
            continue
        if phrase and phrase not in seen:
            rows.append({"phrase": phrase, "count": count, "name": canonical_name(phrase)})
            seen.add(phrase)
    return rows


def build_topic_clusters(
    candidates: Iterable[dict[str, Any] | str],
    *,
    llm_clusters: list[dict[str, Any]] | None = None,
    max_clusters: int = 35,
    audit: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Group aliases using a fashion ontology, lexical similarity and optional Qwen mapping."""

    rows = _candidate_rows(candidates, audit=audit)
    if not rows:
        return []
    parent = list(range(len(rows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_canonical: dict[str, int] = {}
    for index, row in enumerate(rows):
        key = slugify(str(row["name"]))
        if key in by_canonical:
            union(index, by_canonical[key])
        else:
            by_canonical[key] = index

    phrases = [str(row["phrase"]) for row in rows]
    if len(phrases) > 1:
        try:
            word_matrix = TfidfVectorizer(ngram_range=(1, 2)).fit_transform(phrases)
            char_matrix = TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5)
            ).fit_transform(phrases)
            similarity = 0.45 * cosine_similarity(word_matrix) + 0.55 * cosine_similarity(char_matrix)
            for left in range(len(rows)):
                left_tokens = set(phrases[left].split())
                for right in range(left + 1, len(rows)):
                    right_tokens = set(phrases[right].split())
                    shared = left_tokens & right_tokens
                    both_specific = min(len(left_tokens), len(right_tokens)) >= 2
                    if (
                        similarity[left, right] >= 0.84
                        or (both_specific and shared and similarity[left, right] >= 0.68)
                    ):
                        union(left, right)
        except ValueError:
            pass

    phrase_index = {str(row["phrase"]): index for index, row in enumerate(rows)}
    model_names: dict[int, str] = {}
    for cluster in llm_clusters or []:
        if not isinstance(cluster, dict):
            continue
        aliases = [
            _clean_phrase(str(alias))
            for alias in cluster.get("aliases", [])
            if _clean_phrase(str(alias)) in phrase_index
        ]
        if not aliases:
            continue
        anchor = phrase_index[aliases[0]]
        for alias in aliases[1:]:
            union(anchor, phrase_index[alias])
        model_name = str(cluster.get("name") or "").strip()
        if model_name:
            model_names[anchor] = model_name[:80]

    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        grouped[find(index)].append(index)

    output: list[dict[str, Any]] = []
    for root, indices in grouped.items():
        ranked = sorted(indices, key=lambda index: int(rows[index]["count"]), reverse=True)
        known_names = [
            str(rows[index]["name"])
            for index in ranked
            if _clean_phrase(str(rows[index]["phrase"])) in CANONICAL_PHRASES
        ]
        model_name = ""
        for model_root, label in model_names.items():
            if find(model_root) == root:
                model_name = label
                break
        if model_name:
            reason = generic_trend_reason(model_name)
            if reason:
                _audit_filtered(audit, model_name, "Qwen topic label", reason)
                model_name = ""
        name = model_name or (known_names[0] if known_names else str(rows[ranked[0]]["name"]))
        reason = generic_trend_reason(name)
        if reason:
            _audit_filtered(audit, name, "Topic cluster", reason)
            continue
        aliases = [str(rows[index]["phrase"]) for index in ranked]
        known_aliases = [
            phrase for phrase, target in CANONICAL_PHRASES.items() if target == name
        ]
        aliases = list(dict.fromkeys([*aliases, *known_aliases, _clean_phrase(name)]))
        output.append(
            {
                "name": name,
                "aliases": aliases,
                "candidate_weight": sum(int(rows[index]["count"]) for index in indices),
            }
        )
    output.sort(key=lambda cluster: int(cluster["candidate_weight"]), reverse=True)
    return output[:max_clusters]


def _post_window(
    post: dict[str, Any],
    *,
    current_start: datetime,
    previous_start: datetime,
) -> str:
    created = _parse_datetime(post.get("created_at"))
    if created is None:
        return "invalid"
    if created >= current_start:
        return "current"
    if created >= previous_start:
        return "previous"
    return "outside"


def _channels(post: dict[str, Any]) -> set[str]:
    values = {str(value) for value in post.get("evidence_channels", []) if str(value)}
    if not values:
        values.add("expert" if post.get("is_expert") else "open")
    return values


def _author_key(post: dict[str, Any]) -> str:
    return str(post.get("author_hash") or f"unknown:{post.get('post_hash', id(post))}")


def _expert_weight(post: dict[str, Any]) -> float:
    try:
        return max(1.0, min(3.0, float(post.get("expert_weight") or 1.0)))
    except (TypeError, ValueError):
        return 1.0


def _is_priority_expert(post: dict[str, Any]) -> bool:
    tiers = {
        str(value)
        for value in (
            post.get("expert_tiers")
            or ([post.get("expert_tier")] if post.get("expert_tier") else [])
        )
    }
    return "commercial-priority" in tiers or _expert_weight(post) > 1.0


def _weighted_author_breadth(posts: list[dict[str, Any]]) -> float:
    author_weights: dict[str, float] = {}
    for post in posts:
        key = _author_key(post)
        author_weights[key] = max(author_weights.get(key, 0.0), _expert_weight(post))
    return sum(author_weights.values())


def _growth(current: float, previous: float) -> float:
    return 100 * ((current + 1) / (previous + 1) - 1)


def extract_x_signals(
    posts: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    max_phrases: int = 35,
    clusters: list[dict[str, Any]] | None = None,
    historical_presence: dict[str, int] | None = None,
    audit: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    if not posts:
        return []
    now = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    current_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)
    topic_clusters = clusters or build_topic_clusters(
        discover_x_candidates(
            posts,
            max_phrases=max_phrases * 2,
            audit=audit,
        ),
        max_clusters=max_phrases,
        audit=audit,
    )
    history = historical_presence or {}
    rows: list[dict[str, Any]] = []

    for cluster in topic_clusters[:max_phrases]:
        name = str(cluster.get("name") or "").strip()
        reason = generic_trend_reason(name)
        if reason:
            _audit_filtered(audit, name, "X trend cluster", reason)
            continue
        aliases = [
            _clean_phrase(str(alias))
            for alias in cluster.get("aliases", [])
            if _clean_phrase(str(alias))
        ]
        if not name or not aliases:
            continue
        buckets: dict[str, list[dict[str, Any]]] = {
            "current_open": [],
            "previous_open": [],
            "current_expert": [],
            "previous_expert": [],
            "current_visual": [],
            "previous_visual": [],
        }
        for post in posts:
            if post.get("is_repost"):
                continue
            text = _clean_phrase(str(post.get("text", "")))
            if not any(_contains_phrase(text, alias) for alias in aliases):
                continue
            window = _post_window(
                post,
                current_start=current_start,
                previous_start=previous_start,
            )
            if window not in {"current", "previous"}:
                continue
            channels = _channels(post)
            if "open" in channels:
                buckets[f"{window}_open"].append(post)
            if "expert" in channels:
                buckets[f"{window}_expert"].append(post)
            if "visual" in channels:
                buckets[f"{window}_visual"].append(post)

        current = buckets["current_open"]
        previous = buckets["previous_open"]
        current_expert = buckets["current_expert"]
        previous_expert = buckets["previous_expert"]
        current_visual = buckets["current_visual"]
        previous_visual = buckets["previous_visual"]
        if not any(
            (
                current,
                previous,
                current_expert,
                previous_expert,
                current_visual,
                previous_visual,
            )
        ):
            continue

        current_authors = {_author_key(post) for post in current}
        previous_authors = {_author_key(post) for post in previous}
        expert_authors = {_author_key(post) for post in current_expert}
        visual_authors = {_author_key(post) for post in current_visual}
        previous_visual_authors = {
            _author_key(post) for post in previous_visual
        }
        priority_expert = [post for post in current_expert if _is_priority_expert(post)]
        previous_priority_expert = [
            post for post in previous_expert if _is_priority_expert(post)
        ]
        priority_expert_authors = {
            _author_key(post) for post in priority_expert
        }
        weighted_expert_mentions = sum(
            _expert_weight(post) for post in current_expert
        )
        previous_weighted_expert_mentions = sum(
            _expert_weight(post) for post in previous_expert
        )
        weighted_expert_authors = _weighted_author_breadth(current_expert)
        previous_weighted_expert_authors = _weighted_author_breadth(
            previous_expert
        )
        engagement = sum(int(post.get("engagement") or 0) for post in current)
        views = sum(int(post.get("views") or 0) for post in current)
        expert_engagement = sum(
            _expert_weight(post) * int(post.get("engagement") or 0)
            for post in current_expert
        )
        expert_views = sum(
            _expert_weight(post) * int(post.get("views") or 0)
            for post in current_expert
        )
        visual_engagement = sum(
            int(post.get("engagement") or 0) for post in current_visual
        )
        visual_views = sum(int(post.get("views") or 0) for post in current_visual)
        raw_return_count = sum(max(1, int(post.get("duplicate_count") or 1)) for post in current)
        duplicate_rate = max(0.0, (raw_return_count - len(current)) / max(raw_return_count, 1))
        spam_rate = sum(bool(post.get("is_probable_promo")) for post in current) / max(len(current), 1)
        author_counts = Counter(_author_key(post) for post in current)
        dominant_author_share = (
            max(author_counts.values(), default=0) / max(len(current), 1)
        )
        open_groups = {
            group
            for post in current
            for group in (post.get("listening_groups") or [post.get("listening_group", "unlabelled")])
            if group
            and not str(group).startswith(("expert", "commercial-priority"))
        }
        real_author_coverage = sum(bool(post.get("author_hash")) for post in current) / max(len(current), 1)
        dominance_penalty = max(0.0, dominant_author_share - 0.35)
        evidence_quality = 100 * max(
            0.0,
            1
            - 0.42 * spam_rate
            - 0.33 * duplicate_rate
            - 0.25 * dominance_penalty
            - 0.15 * (1 - real_author_coverage),
        )
        presence = int(history.get(slugify(name), history.get(name, 0)) or 0)
        novelty_score = max(0.0, 100.0 - 25.0 * min(4, presence))
        rows.append(
            {
                "id": slugify(name),
                "name": name,
                "mentions": len(current),
                "previous_mentions": len(previous),
                "mention_growth": round(_growth(len(current), len(previous)), 1),
                "unique_authors": len(current_authors),
                "previous_unique_authors": len(previous_authors),
                "author_growth": round(_growth(len(current_authors), len(previous_authors)), 1),
                "engagement": engagement,
                "engagement_per_post": round(engagement / max(len(current), 1), 1),
                "engagement_per_1000_views": round(1000 * engagement / views, 2) if views else 0.0,
                "views": views,
                "source_breadth": len(open_groups),
                "expert_mentions": len(current_expert),
                "previous_expert_mentions": len(previous_expert),
                "expert_mention_growth": round(_growth(len(current_expert), len(previous_expert)), 1),
                "expert_authors": len(expert_authors),
                "expert_engagement_per_1000_views": round(1000 * expert_engagement / expert_views, 2) if expert_views else 0.0,
                "visual_mentions": len(current_visual),
                "previous_visual_mentions": len(previous_visual),
                "visual_authors": len(visual_authors),
                "previous_visual_authors": len(previous_visual_authors),
                "visual_growth": round(
                    _growth(len(current_visual), len(previous_visual)),
                    1,
                ),
                "visual_author_growth": round(
                    _growth(len(visual_authors), len(previous_visual_authors)),
                    1,
                ),
                "visual_engagement_per_1000_views": round(
                    1000 * visual_engagement / visual_views,
                    2,
                )
                if visual_views
                else 0.0,
                "commercial_priority_mentions": len(priority_expert),
                "previous_commercial_priority_mentions": len(
                    previous_priority_expert
                ),
                "commercial_priority_authors": len(priority_expert_authors),
                "commercial_weighted_mentions": round(
                    weighted_expert_mentions, 1
                ),
                "previous_commercial_weighted_mentions": round(
                    previous_weighted_expert_mentions, 1
                ),
                "commercial_weighted_authors": round(
                    weighted_expert_authors, 1
                ),
                "previous_commercial_weighted_authors": round(
                    previous_weighted_expert_authors, 1
                ),
                "duplicate_rate": round(duplicate_rate * 100, 1),
                "spam_rate": round(spam_rate * 100, 1),
                "dominant_author_share": round(dominant_author_share * 100, 1),
                "author_coverage": round(real_author_coverage * 100, 1),
                "evidence_quality": round(evidence_quality, 1),
                "novelty_score": round(novelty_score, 1),
                "aliases": list(dict.fromkeys([*aliases, _clean_phrase(name)])),
            }
        )

    if not rows:
        return []
    author_rank = _rank_scores([math.log1p(row["unique_authors"]) for row in rows])
    author_growth_rank = _rank_scores([row["author_growth"] for row in rows])
    post_growth_rank = _rank_scores([row["mention_growth"] for row in rows])
    engagement_rank = _rank_scores([math.log1p(row["engagement_per_1000_views"]) for row in rows])
    volume_rank = _rank_scores([math.log1p(row["mentions"]) for row in rows])
    expert_author_rank = _rank_scores(
        [math.log1p(row["commercial_weighted_authors"]) for row in rows]
    )
    expert_growth_rank = _rank_scores(
        [
            _growth(
                row["commercial_weighted_mentions"],
                row["previous_commercial_weighted_mentions"],
            )
            for row in rows
        ]
    )
    expert_engagement_rank = _rank_scores(
        [math.log1p(row["expert_engagement_per_1000_views"]) for row in rows]
    )
    visual_author_rank = _rank_scores(
        [math.log1p(row["visual_authors"]) for row in rows]
    )
    visual_growth_rank = _rank_scores(
        [row["visual_author_growth"] for row in rows]
    )
    visual_engagement_rank = _rank_scores(
        [math.log1p(row["visual_engagement_per_1000_views"]) for row in rows]
    )

    for index, row in enumerate(rows):
        breadth_score = min(100.0, 25.0 * float(row["source_breadth"]))
        raw_open = (
            0.25 * author_rank[index]
            + 0.20 * author_growth_rank[index]
            + 0.15 * post_growth_rank[index]
            + 0.15 * engagement_rank[index]
            + 0.10 * breadth_score
            + 0.10 * float(row["novelty_score"])
            + 0.05 * volume_rank[index]
        )
        quality_multiplier = 0.65 + 0.35 * float(row["evidence_quality"]) / 100
        if int(row["mentions"]) or int(row["previous_mentions"]):
            row["open_x_score"] = round(raw_open * quality_multiplier, 1)
            row["x_score"] = row["open_x_score"]
        else:
            row["open_x_score"] = None
            row["x_score"] = None
        if int(row["expert_mentions"]) or int(row["previous_expert_mentions"]):
            authority_score = min(
                100.0,
                35.0 * float(row["commercial_priority_authors"])
                + 8.0
                * max(
                    0.0,
                    float(row["expert_authors"])
                    - float(row["commercial_priority_authors"]),
                ),
            )
            raw_expert = (
                0.35 * expert_author_rank[index]
                + 0.15 * expert_growth_rank[index]
                + 0.15 * expert_engagement_rank[index]
                + 0.35 * authority_score
            )
            expert_coverage = min(
                1.0,
                float(row["expert_authors"])
                / max(float(row["expert_mentions"]), 1.0),
            )
            commercial_quality_multiplier = 0.85 + 0.15 * expert_coverage
            row["expert_score"] = round(
                raw_expert * commercial_quality_multiplier, 1
            )
            row["commercial_source_score"] = row["expert_score"]
        else:
            row["expert_score"] = None
            row["commercial_source_score"] = None
        if int(row["visual_mentions"]) or int(row["previous_visual_mentions"]):
            row["visual_score"] = round(
                0.50 * visual_author_rank[index]
                + 0.30 * visual_growth_rank[index]
                + 0.20 * visual_engagement_rank[index],
                1,
            )
        else:
            row["visual_score"] = None
    return sorted(
        rows,
        key=lambda row: (
            float(row.get("open_x_score") or 0),
            float(row.get("expert_score") or 0),
        ),
        reverse=True,
    )


def score_google_series(
    series_by_term: dict[str, list[dict[str, Any]]],
    *,
    audit: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for term, points in series_by_term.items():
        reason = generic_trend_reason(term)
        if reason:
            _audit_filtered(audit, term, "Google Trends term", reason)
            continue
        cleaned_points, quality = validate_series(points)
        if not quality["score_ready"]:
            continue
        values = [float(point["value"]) for point in cleaned_points]
        recent_window = max(2, min(7, len(values) // 6 or 2))
        baseline_window = max(recent_window * 3, 6)
        current_values = values[-recent_window:]
        baseline_values = values[-(recent_window + baseline_window) : -recent_window]
        if not baseline_values:
            baseline_values = values[:-recent_window]
        current = statistics.mean(current_values)
        baseline = statistics.mean(baseline_values) if baseline_values else 0
        momentum = (
            0.0
            if quality["flat"]
            else 100 * (current - baseline) / max(baseline, 5)
        )
        slope_values = values[-min(10, len(values)) :]
        slope = (
            0.0
            if quality["flat"]
            else float(
                np.polyfit(np.arange(len(slope_values)), slope_values, 1)[0]
            )
        )
        name = canonical_name(term)
        display_points, display_quality = google_display_series(cleaned_points)
        rows.append(
            {
                "id": slugify(name),
                "name": name,
                "query": term,
                "search_interest": round(current, 1),
                "search_baseline": round(baseline, 1),
                "search_momentum": round(momentum, 1),
                "search_slope": round(slope, 2),
                "series": cleaned_points,
                "display_series": display_points,
                "aliases": [term],
                "chart_ready": bool(display_quality["chart_ready"]),
                "series_quality": display_quality,
                "series_issue": str(display_quality["issue"]),
            }
        )
    interest_rank = _rank_scores([row["search_interest"] for row in rows])
    momentum_rank = _rank_scores([row["search_momentum"] for row in rows])
    slope_rank = _rank_scores([row["search_slope"] for row in rows])
    for index, row in enumerate(rows):
        row["google_score"] = round(
            0.45 * interest_rank[index]
            + 0.40 * momentum_rank[index]
            + 0.15 * slope_rank[index],
            1,
        )
    return sorted(rows, key=lambda row: row["google_score"], reverse=True)


def score_google_windows(
    context_series: dict[str, list[dict[str, Any]]],
    recent_series: dict[str, list[dict[str, Any]]],
    *,
    audit: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Combine one-month persistence with the last seven days of acceleration."""

    context_rows = score_google_series(context_series, audit=audit)
    recent_rows = score_google_series(recent_series, audit=audit)
    recent_by_id = {str(row.get("id")): row for row in recent_rows}
    output: list[dict[str, Any]] = []
    for row in context_rows:
        updated = dict(row)
        recent = recent_by_id.get(str(row.get("id")))
        if recent:
            updated["google_context_score"] = float(row.get("google_score") or 0)
            updated["google_recent_score"] = float(recent.get("google_score") or 0)
            updated["google_score"] = round(
                0.60 * float(row.get("google_score") or 0)
                + 0.40 * float(recent.get("google_score") or 0),
                1,
            )
            updated["search_momentum_7d"] = float(
                recent.get("search_momentum") or 0
            )
            updated["recent_series"] = list(recent.get("series") or [])
            updated["recent_display_series"] = list(
                recent.get("display_series") or []
            )
            updated["recent_series_quality"] = dict(
                recent.get("series_quality") or {}
            )
        else:
            updated["google_context_score"] = float(row.get("google_score") or 0)
            updated["google_recent_score"] = None
            updated["search_momentum_7d"] = None
            updated["recent_series"] = []
            updated["recent_display_series"] = []
            updated["recent_series_quality"] = {}
        output.append(updated)
    return sorted(
        output,
        key=lambda item: float(item.get("google_score") or 0),
        reverse=True,
    )


def infer_category(name: str) -> str:
    tokens = set(_clean_phrase(name).split())
    category, hits = "Cross-category", 0
    for candidate, words in CATEGORY_RULES.items():
        count = len(tokens & words)
        if count > hits:
            category, hits = candidate, count
    return category


def infer_stage(search_momentum: float, social_growth: float) -> str:
    combined = 0.55 * search_momentum + 0.45 * social_growth
    if combined >= 120:
        return "Emerging"
    if combined >= 25:
        return "Rising"
    if combined <= -25:
        return "Cooling"
    if search_momentum >= 5 or social_growth >= 5:
        return "Established"
    return "Peaking"


def _why_now(row: dict[str, Any]) -> str:
    clauses: list[str] = []
    if row.get("google_score") is not None:
        clauses.append(
            f"Worldwide Google search interest is {float(row.get('search_momentum') or 0):+.0f}% versus its recent baseline"
        )
    if row.get("x_score") is not None:
        clauses.append(
            f"open X discussion is {float(row.get('mention_growth') or 0):+.0f}% week on week across {int(row.get('unique_authors') or 0)} independent authors"
        )
    if row.get("commercial_score") is not None:
        publisher_count = int(row.get("publisher_count") or 0)
        article_count = int(row.get("commercial_article_count") or 0)
        clauses.append(
            f"{publisher_count} approved publisher"
            f"{'' if publisher_count == 1 else 's'} explicitly named it across "
            f"{article_count} current article or report signal"
            f"{'' if article_count == 1 else 's'}"
        )
    if row.get("instagram_score") is not None:
        hashtag = str(row.get("instagram_hashtag") or "")
        post_count = int(row.get("instagram_posts_count") or 0)
        clauses.append(
            f"Instagram aggregate metadata reports {post_count:,} uses of "
            f"#{hashtag}" if hashtag else "Instagram hashtag metadata provides a directional comparison"
        )
    if not clauses:
        return "The available evidence is directional and should be validated before use."
    return "; ".join(clauses).capitalize() + "."


def _content_angles(name: str, category: str) -> list[str]:
    return [
        f"The HULA edit: pre-owned pieces that tap into {name.lower()}",
        f"Three ways to style the {name.lower()} signal without buying new",
        f"Then vs now: how designer archives anticipated {name.lower()}",
        f"Store story: discover the {name.lower()} edit at HULA Soho or The Hub",
    ]


def merge_trend_signals(
    google_rows: list[dict[str, Any]],
    x_rows: list[dict[str, Any]],
    *,
    commercial_rows: list[dict[str, Any]] | None = None,
    instagram_rows: list[dict[str, Any]] | None = None,
    limit: int = 15,
    audit: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(dict)
    source_rows: list[tuple[str, list[dict[str, Any]], str]] = [
        ("google", google_rows, "google_score"),
        ("x", x_rows, "open_x_score"),
    ]
    if commercial_rows is not None:
        source_rows.append(("commercial", commercial_rows, "commercial_score"))
    if instagram_rows is not None:
        source_rows.append(("instagram", instagram_rows, "instagram_score"))
    for source_name, rows, score_key in source_rows:
        for row in rows:
            canonical = canonical_name(str(row.get("name", "")))
            reason = generic_trend_reason(
                canonical,
                trusted_source=source_name == "commercial",
            )
            if reason:
                _audit_filtered(audit, canonical, f"{source_name.title()} trend", reason)
                continue
            key = slugify(canonical)
            current = grouped[key].get(source_name)
            if current is None or float(row.get(score_key) or 0) > float(current.get(score_key) or 0):
                grouped[key][source_name] = row

    merged: list[dict[str, Any]] = []
    for key, evidence in grouped.items():
        google = evidence.get("google") or {}
        social = evidence.get("x") or {}
        commercial = evidence.get("commercial") or {}
        instagram = evidence.get("instagram") or {}
        name = (
            google.get("name")
            or commercial.get("name")
            or social.get("name")
            or instagram.get("name")
            or key
        )
        legacy_commercial = (
            social.get("expert_score")
            if commercial_rows is None and social
            else None
        )
        legacy_instagram = (
            social.get("visual_score")
            if instagram_rows is None and social
            else None
        )
        components = {
            "google": google.get("google_score") if google else None,
            "open_x": (
                social.get("open_x_score")
                if social.get("open_x_score") is not None
                else social.get("x_score")
            )
            if social
            else None,
            "commercial": (
                commercial.get("commercial_score")
                if commercial
                else legacy_commercial
            ),
            "instagram": (
                instagram.get("instagram_score")
                if instagram
                else legacy_instagram
            ),
        }
        available = {
            component: float(value)
            for component, value in components.items()
            if value is not None
        }
        denominator = sum(SOURCE_WEIGHTS[component] for component in available) or 1.0
        score = sum(
            SOURCE_WEIGHTS[component] * value
            for component, value in available.items()
        ) / denominator
        has_google = "google" in available
        has_open_x = "open_x" in available
        has_commercial = "commercial" in available
        has_instagram = "instagram" in available
        has_priority_commercial = bool(
            int(
                commercial.get("commercial_priority_mentions")
                or social.get("commercial_priority_mentions")
                or 0
            )
        )
        publisher_count = int(commercial.get("publisher_count") or 0)
        decision_ready = has_google and (
            has_open_x or has_commercial or has_instagram
        )
        if has_google and has_commercial and (has_open_x or has_instagram):
            confidence = "High"
        elif has_google and has_commercial and publisher_count >= 2:
            confidence = "High"
        elif has_google and has_open_x:
            confidence = "Medium"
        elif has_google and (has_commercial or has_instagram):
            confidence = "Medium"
        else:
            confidence = "Exploratory"
        sources = [
            source
            for source, present in (
                ("Google Trends", has_google),
                ("Open X topics", has_open_x),
                ("Commercial reports", has_commercial),
                ("Instagram hashtag signal", has_instagram),
            )
            if present
        ]
        aliases = list(
            dict.fromkeys(
                [
                    *google.get("aliases", []),
                    *social.get("aliases", []),
                    *commercial.get("aliases", []),
                    str(google.get("query", "")),
                    str(name),
                ]
            )
        )
        aliases = [alias for alias in aliases if alias]
        row = {
            "id": key,
            "name": name,
            "score": round(score, 1),
            "google_score": round(float(components["google"]), 1) if components["google"] is not None else None,
            "x_score": round(float(components["open_x"]), 1) if components["open_x"] is not None else None,
            "open_x_score": round(float(components["open_x"]), 1) if components["open_x"] is not None else None,
            "commercial_score": round(float(components["commercial"]), 1) if components["commercial"] is not None else None,
            "commercial_source_score": round(float(components["commercial"]), 1) if components["commercial"] is not None else None,
            # Compatibility aliases keep older report/export code readable.
            "expert_score": round(float(components["commercial"]), 1) if components["commercial"] is not None else None,
            "instagram_score": round(float(components["instagram"]), 1) if components["instagram"] is not None else None,
            "instagram_hashtag_score": round(float(components["instagram"]), 1) if components["instagram"] is not None else None,
            "visual_score": round(float(components["instagram"]), 1) if components["instagram"] is not None else None,
            "search_interest": google.get("search_interest"),
            "search_baseline": google.get("search_baseline"),
            "search_momentum": float(google.get("search_momentum") or 0),
            "search_momentum_7d": google.get("search_momentum_7d"),
            "mentions": int(social.get("mentions") or 0),
            "previous_mentions": int(social.get("previous_mentions") or 0),
            "mention_growth": float(social.get("mention_growth") or 0),
            "unique_authors": int(social.get("unique_authors") or 0),
            "previous_unique_authors": int(social.get("previous_unique_authors") or 0),
            "author_growth": float(social.get("author_growth") or 0),
            "engagement": int(social.get("engagement") or 0),
            "engagement_per_1000_views": float(social.get("engagement_per_1000_views") or 0),
            "source_breadth": int(social.get("source_breadth") or 0),
            "expert_mentions": int(social.get("expert_mentions") or 0),
            "expert_authors": int(social.get("expert_authors") or 0),
            "visual_mentions": int(social.get("visual_mentions") or 0),
            "visual_authors": int(social.get("visual_authors") or 0),
            "visual_growth": float(social.get("visual_growth") or 0),
            "commercial_priority_mentions": int(
                commercial.get("commercial_priority_mentions")
                or social.get("commercial_priority_mentions")
                or 0
            ),
            "commercial_priority_authors": int(
                social.get("commercial_priority_authors") or 0
            ),
            "commercial_weighted_mentions": float(
                social.get("commercial_weighted_mentions") or 0
            ),
            "duplicate_rate": float(social.get("duplicate_rate") or 0),
            "spam_rate": float(social.get("spam_rate") or 0),
            "evidence_quality": float(social.get("evidence_quality") or 0),
            "novelty_score": float(social.get("novelty_score") or 0),
            "publisher_count": publisher_count,
            "commercial_article_count": int(commercial.get("article_count") or 0),
            "commercial_evidence": list(commercial.get("commercial_evidence") or []),
            "instagram_hashtag": str(instagram.get("hashtag") or ""),
            "instagram_posts_count": int(instagram.get("posts_count") or 0),
            "instagram_posts_per_day": float(instagram.get("posts_per_day") or 0),
            "instagram_related_hashtags": list(instagram.get("related_hashtags") or []),
            "instagram_directional_only": bool(instagram),
            "confidence": confidence,
            "decision_ready": decision_ready,
            "missing_components": [
                label
                for component, label in (
                    ("google", "Google Trends"),
                    ("open_x", "Open X"),
                    ("commercial", "commercial reports"),
                    ("instagram", "Instagram hashtag metadata"),
                )
                if component not in available
            ],
            "sources": sources,
            "aliases": aliases,
            "series": google.get("series", []),
            "display_series": google.get("display_series", []),
            "recent_series": google.get("recent_series", []),
            "chart_ready": bool(google.get("chart_ready")),
            "series_quality": dict(google.get("series_quality") or {}),
            "series_issue": str(google.get("series_issue") or ""),
            "component_weights": {
                component: round(SOURCE_WEIGHTS[component] / denominator, 4)
                for component in available
            },
        }
        row["category"] = infer_category(str(name))
        row["stage"] = infer_stage(
            row["search_momentum"],
            row["author_growth"] or row["mention_growth"],
        )
        row["why_now"] = _why_now(row)
        row["content_angles"] = _content_angles(str(name), row["category"])
        merged.append(row)
    return sorted(merged, key=lambda row: row["score"], reverse=True)[:limit]
