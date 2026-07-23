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

BROAD_SINGLE_TOKENS = {
    "accessory", "accessories", "apparel", "bag", "bags", "belt", "belts",
    "blazer", "blazers", "boot", "boots", "bottom", "bottoms", "bracelet",
    "bracelets", "cardigan", "cardigans", "clothes", "clothing", "coat", "coats",
    "dress", "dresses", "earring", "earrings", "fashion", "footwear", "garment",
    "garments", "handbag", "handbags", "heel", "heels", "jacket", "jackets",
    "jean", "jeans", "jewellery", "jewelry", "knitwear", "loafer", "loafers",
    "necklace", "necklaces", "outfit", "outfits", "pant", "pants", "pattern",
    "patterns", "print", "prints", "pump", "pumps", "sandal", "sandals", "scarf",
    "scarves", "shirt", "shirts", "shoe", "shoes", "silhouette", "silhouettes",
    "skirt", "skirts", "sneaker", "sneakers", "style", "styles", "suit", "suits",
    "sweater", "sweaters", "top", "tops", "trainer", "trainers", "trend", "trends",
    "trouser", "trousers", "tshirt", "tshirts", "wear",
}

GENERIC_FASHION_FILLERS = {
    "all", "best", "designer", "designers", "fashion", "fashionable", "female",
    "idea", "ideas", "latest", "look", "looks", "luxury", "male", "men", "mens",
    "must", "new", "season", "style", "styles", "trend", "trends", "trending",
    "wear", "woman", "women", "womens",
}

VAGUE_SINGLE_TOKENS = {
    "aesthetic", "chic", "classic", "color", "colour", "core", "design", "element",
    "mini", "maxi", "platform", "viral",
}

PLATFORM_ONLY_TOKENS = {
    "amazon", "ebay", "etsy", "instagram", "pinterest", "shopify", "tiktok",
    "twitter", "x",
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
    "watches",
}

FASHION_STYLE_TOKENS = {
    "animal", "archive", "athleisure", "ballet", "balletcore", "barrel",
    "boho", "bohemian", "burgundy", "capri", "charm", "coastal", "coquette",
    "corsetry", "crochet", "denim", "drop", "gorpcore", "lace", "leather",
    "leopard", "maxi", "metallic", "minimalist", "maximalist", "nautical",
    "polka", "preloved", "preowned", "print", "raffia", "resale", "satin",
    "sheer", "silk", "street", "streetwear", "suede", "tailoring", "tweed",
    "vintage", "waist", "woven", "y2k",
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
    "google": 0.45,
    "open_x": 0.30,
    "expert": 0.15,
    "visual": 0.10,
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


def generic_trend_reason(value: str) -> str:
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
    tokens = set(phrase.split())
    if len(tokens) == 1 and tokens & BROAD_SINGLE_TOKENS:
        return "Generic product or fashion category"
    if len(tokens) == 1 and tokens & VAGUE_SINGLE_TOKENS:
        return "Vague descriptor without a product or defining attribute"
    if tokens <= BROAD_SINGLE_TOKENS | GENERIC_FASHION_FILLERS:
        return "Only broad fashion/category words"
    if tokens <= PLATFORM_ONLY_TOKENS | GENERIC_FASHION_FILLERS:
        return "Platform or source name, not a fashion trend"
    if not (
        tokens & FASHION_PRODUCT_TOKENS
        or tokens & FASHION_STYLE_TOKENS
        or tokens & FASHION_DOMAIN_TOKENS
    ):
        return "No clear fashion product, material, silhouette or style signal"
    return ""


def generic_term_catalogue() -> list[str]:
    """Return the permanent single-term blocklist for transparent UI display."""

    return sorted(BROAD_SINGLE_TOKENS | VAGUE_SINGLE_TOKENS | PLATFORM_ONLY_TOKENS)


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
    audit = list((snapshot.get("meta") or {}).get("filtered_terms") or [])
    kept: list[dict[str, Any]] = []
    removed_ids: set[str] = set()
    remapped_ids: dict[str, str] = {}
    for trend in trends:
        name = str(trend.get("name") or "")
        reason = generic_trend_reason(name)
        if reason:
            removed_ids.add(str(trend.get("id") or ""))
            _audit_filtered(audit, name, "Stored snapshot", reason)
        else:
            canonical = CANONICAL_PHRASES.get(_clean_phrase(name), name)
            if canonical != name:
                normalised = dict(trend)
                old_id = str(trend.get("id") or "")
                new_id = slugify(canonical)
                normalised["name"] = canonical
                normalised["id"] = new_id
                if old_id:
                    remapped_ids[old_id] = new_id
                kept.append(normalised)
            else:
                kept.append(trend)
    if not removed_ids and not remapped_ids and len(kept) == len(trends):
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
    meta["quality_filter_version"] = "2.0"
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


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            parsed = datetime.now(tz=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
    declared = str(post.get("listening_window") or "").lower()
    if declared in {"current", "previous"}:
        return declared
    created = _parse_datetime(post.get("created_at"))
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


def _growth(current: int, previous: int) -> float:
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

        current = buckets["current_open"]
        previous = buckets["previous_open"]
        current_expert = buckets["current_expert"]
        previous_expert = buckets["previous_expert"]
        if not current and not previous and not current_expert and not previous_expert:
            continue

        current_authors = {_author_key(post) for post in current}
        previous_authors = {_author_key(post) for post in previous}
        expert_authors = {_author_key(post) for post in current_expert}
        engagement = sum(int(post.get("engagement") or 0) for post in current)
        views = sum(int(post.get("views") or 0) for post in current)
        expert_engagement = sum(int(post.get("engagement") or 0) for post in current_expert)
        expert_views = sum(int(post.get("views") or 0) for post in current_expert)
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
            if group and not str(group).startswith("expert")
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
    expert_author_rank = _rank_scores([math.log1p(row["expert_authors"]) for row in rows])
    expert_growth_rank = _rank_scores([row["expert_mention_growth"] for row in rows])
    expert_engagement_rank = _rank_scores(
        [math.log1p(row["expert_engagement_per_1000_views"]) for row in rows]
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
            raw_expert = (
                0.55 * expert_author_rank[index]
                + 0.25 * expert_growth_rank[index]
                + 0.20 * expert_engagement_rank[index]
            )
            row["expert_score"] = round(raw_expert * quality_multiplier, 1)
        else:
            row["expert_score"] = None
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
        values = [float(point.get("value") or 0) for point in points]
        if len(values) < 3:
            continue
        recent_window = max(2, min(7, len(values) // 6 or 2))
        baseline_window = max(recent_window * 3, 6)
        current_values = values[-recent_window:]
        baseline_values = values[-(recent_window + baseline_window) : -recent_window]
        if not baseline_values:
            baseline_values = values[:-recent_window]
        current = statistics.mean(current_values)
        baseline = statistics.mean(baseline_values) if baseline_values else 0
        momentum = 100 * (current - baseline) / max(baseline, 5)
        slope_values = values[-min(10, len(values)) :]
        slope = float(np.polyfit(np.arange(len(slope_values)), slope_values, 1)[0])
        name = canonical_name(term)
        rows.append(
            {
                "id": slugify(name),
                "name": name,
                "query": term,
                "search_interest": round(current, 1),
                "search_baseline": round(baseline, 1),
                "search_momentum": round(momentum, 1),
                "search_slope": round(slope, 2),
                "series": points,
                "aliases": [term],
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
    if row.get("expert_score") is not None:
        clauses.append(
            f"the expert panel contributed {int(row.get('expert_mentions') or 0)} current mentions"
        )
    if not clauses:
        return "The available evidence is directional and should be validated before use."
    return "; ".join(clauses).capitalize() + "."


def _content_angles(name: str, category: str) -> list[str]:
    return [
        f"The HULA edit: pre-owned pieces that tap into {name.lower()}",
        f"Three ways to style the {name.lower()} signal without buying new",
        f"Then vs now: how designer archives anticipated {name.lower()}",
    ]


def merge_trend_signals(
    google_rows: list[dict[str, Any]],
    x_rows: list[dict[str, Any]],
    *,
    limit: int = 15,
    audit: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(dict)
    for source_name, rows in (("google", google_rows), ("x", x_rows)):
        for row in rows:
            canonical = canonical_name(str(row.get("name", "")))
            reason = generic_trend_reason(canonical)
            if reason:
                _audit_filtered(audit, canonical, f"{source_name.title()} trend", reason)
                continue
            key = slugify(canonical)
            current = grouped[key].get(source_name)
            score_key = "google_score" if source_name == "google" else "open_x_score"
            if current is None or float(row.get(score_key) or 0) > float(current.get(score_key) or 0):
                grouped[key][source_name] = row

    merged: list[dict[str, Any]] = []
    for key, evidence in grouped.items():
        google = evidence.get("google") or {}
        social = evidence.get("x") or {}
        name = google.get("name") or social.get("name") or key
        components = {
            "google": google.get("google_score") if google else None,
            "open_x": (
                social.get("open_x_score")
                if social.get("open_x_score") is not None
                else social.get("x_score")
            )
            if social
            else None,
            "expert": social.get("expert_score") if social else None,
            "visual": social.get("visual_score") if social else None,
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
        has_expert = "expert" in available
        has_visual = "visual" in available
        if has_google and has_open_x and (has_expert or has_visual):
            confidence = "High"
        elif has_google and has_open_x:
            confidence = "High"
        elif len(available) >= 2:
            confidence = "Medium"
        else:
            confidence = "Exploratory"
        sources = [
            source
            for source, present in (
                ("Google Trends", has_google),
                ("Open X topics", has_open_x),
                ("Expert fashion panel", has_expert),
                ("Visual validation", has_visual),
            )
            if present
        ]
        aliases = list(
            dict.fromkeys(
                [
                    *google.get("aliases", []),
                    *social.get("aliases", []),
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
            "expert_score": round(float(components["expert"]), 1) if components["expert"] is not None else None,
            "visual_score": round(float(components["visual"]), 1) if components["visual"] is not None else None,
            "search_interest": google.get("search_interest"),
            "search_baseline": google.get("search_baseline"),
            "search_momentum": float(google.get("search_momentum") or 0),
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
            "duplicate_rate": float(social.get("duplicate_rate") or 0),
            "spam_rate": float(social.get("spam_rate") or 0),
            "evidence_quality": float(social.get("evidence_quality") or 0),
            "novelty_score": float(social.get("novelty_score") or 0),
            "confidence": confidence,
            "sources": sources,
            "aliases": aliases,
            "series": google.get("series", []),
            "component_weights": {
                component: round(SOURCE_WEIGHTS[component] / denominator, 4)
                for component in available
            },
        }
        row["category"] = infer_category(str(name))
        row["stage"] = infer_stage(row["search_momentum"], row["author_growth"] or row["mention_growth"])
        row["why_now"] = _why_now(row)
        row["content_angles"] = _content_angles(str(name), row["category"])
        merged.append(row)
    return sorted(merged, key=lambda row: row["score"], reverse=True)[:limit]
