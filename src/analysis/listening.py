from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable


DEFAULT_TOPIC_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "id": "products",
        "label": "Products",
        "terms": (
            '"bag trend"',
            '"handbag trend"',
            '"shoe trend"',
            '"dress trend"',
            '"jewellery trend"',
            '"jewelry trend"',
            '"accessory trend"',
            '"it bag"',
            '"must-have shoes"',
        ),
    },
    {
        "id": "colour-material",
        "label": "Colours & materials",
        "terms": (
            '"colour trend"',
            '"color trend"',
            '"fabric trend"',
            '"material trend"',
            '"print trend"',
            '"pattern trend"',
            '"texture trend"',
            '"fashion colour forecast"',
        ),
    },
    {
        "id": "silhouette",
        "label": "Shapes & silhouettes",
        "terms": (
            '"silhouette trend"',
            '"bag shape trend"',
            '"shoe silhouette trend"',
            '"dress silhouette trend"',
            '"skirt silhouette trend"',
            '"trouser silhouette trend"',
            '"denim silhouette trend"',
            '"runway silhouette"',
        ),
    },
    {
        "id": "aesthetic",
        "label": "Aesthetics",
        "terms": (
            '"emerging fashion aesthetic"',
            '"new style aesthetic"',
            '"runway aesthetic"',
            '"street style trend"',
            '"vintage fashion trend"',
            '"maximalist fashion trend"',
            '"minimalist fashion trend"',
        ),
    },
    {
        "id": "behaviour-resale",
        "label": "Styling & resale behaviour",
        "terms": (
            '"how to wear"',
            '"how to style"',
            '"outfit ideas"',
            '"everywhere right now"',
            '"must-have fashion"',
            '"designer archive"',
            '"preowned fashion"',
            '"pre-loved fashion"',
            '"resale fashion"',
            '"vintage designer"',
        ),
    },
)


DEFAULT_EXPERT_ACCOUNTS: tuple[str, ...] = (
    "VogueRunway",
    "VogueBusiness",
    "BoF",
    "WGSN",
    "HYPEBEAST",
    "Highsnobiety",
    "Fashionista_com",
    "Dazed",
    "i_D",
    "BritishVogue",
    "VogueHongKong",
    "TatlerAsia",
    "VestiaireCo",
    "therealreal",
)

# These are the priority sources from the commercial-fashion panel that have
# stable X accounts and can therefore be collected by the existing governed X
# connector. Data But Make It Fashion and Tagwalk are collected by the
# governed Instagram connector rather than impersonated as X handles.
DEFAULT_PRIORITY_COMMERCIAL_ACCOUNTS: tuple[str, ...] = (
    "WhoWhatWear",
    "WhoWhatWearUK",
    "Lyst",
)

DEFAULT_INSTAGRAM_PRIORITY_ACCOUNTS: tuple[str, ...] = (
    "databutmakeitfashion",
    "tagwalk",
    "whowhatwear",
    "whowhatwear.uk",
    "lyst",
)

DEFAULT_INSTAGRAM_SPECIALIST_ACCOUNTS: tuple[str, ...] = (
    "voguerunway",
    "wgsn",
    "trendalytics",
    "edited_hq",
    "heuritech",
)

INSTAGRAM_ACCOUNT_WEIGHTS: dict[str, float] = {
    **{account: 3.0 for account in DEFAULT_INSTAGRAM_PRIORITY_ACCOUNTS},
    **{account: 2.0 for account in DEFAULT_INSTAGRAM_SPECIALIST_ACCOUNTS},
}

PRIORITY_COMMERCIAL_SOURCES: tuple[dict[str, str], ...] = (
    {
        "name": "Data But Make It Fashion",
        "handle": "@databutmakeitfashion",
        "role": "Quantified popularity and trend comparison",
        "route": "Automated public Instagram panel + official website review",
    },
    {
        "name": "Who What Wear",
        "handle": "@whowhatwear",
        "role": "Commercial what-to-buy and what-to-wear interpretation",
        "route": "Automated Instagram + X source",
    },
    {
        "name": "Who What Wear UK",
        "handle": "@whowhatwear.uk",
        "role": "European and London-led commercial interpretation",
        "route": "Automated Instagram + X source",
    },
    {
        "name": "Lyst",
        "handle": "@lyst",
        "role": "Product and brand shopping demand",
        "route": "Automated Instagram + X source + quarterly Lyst Index review",
    },
    {
        "name": "Tagwalk",
        "handle": "@tagwalk",
        "role": "Runway frequency, colours, silhouettes and accessories",
        "route": "Automated public Instagram panel + Tagwalk Trends review",
    },
)

PRIORITY_EXPERT_MULTIPLIER = 3.0
SUPPORTING_EXPERT_MULTIPLIER = 1.0


def clean_expert_accounts(accounts: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for account in accounts:
        value = re.sub(r"[^A-Za-z0-9_]", "", str(account).lstrip("@").strip())
        if value and value.lower() not in {item.lower() for item in cleaned}:
            cleaned.append(value)
    return cleaned


def _window_bounds(now: datetime) -> tuple[dict[str, Any], dict[str, Any]]:
    current_end = now.date() + timedelta(days=1)
    current_start = now.date() - timedelta(days=7)
    previous_start = now.date() - timedelta(days=14)
    return (
        {
            "id": "current",
            "label": "Current 7 days",
            "since": current_start.isoformat(),
            "until": current_end.isoformat(),
        },
        {
            "id": "previous",
            "label": "Previous 7 days",
            "since": previous_start.isoformat(),
            "until": current_start.isoformat(),
        },
    )


def _query(
    body: str,
    *,
    since: str,
    until: str,
    language: str,
) -> str:
    filters = [f"lang:{language}"] if language else []
    filters.extend(("-filter:replies", "-filter:nativeretweets"))
    return " ".join(
        [f"({body})", *filters, f"since:{since}", f"until:{until}"]
    )


def build_listening_plan(
    *,
    now: datetime | None = None,
    language: str = "en",
    results_per_query: int = 50,
    expert_results_per_query: int = 35,
    expert_accounts: Iterable[str] = DEFAULT_EXPERT_ACCOUNTS,
    priority_accounts: Iterable[str] = DEFAULT_PRIORITY_COMMERCIAL_ACCOUNTS,
    topic_groups: Iterable[dict[str, Any]] = DEFAULT_TOPIC_GROUPS,
    validation_terms: Iterable[str] = (),
    expert_chunk_size: int = 8,
) -> list[dict[str, Any]]:
    """Build balanced current/previous X searches for ScrapeBadger Advanced Search."""

    current_time = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    windows = _window_bounds(current_time)
    plan: list[dict[str, Any]] = []

    groups = list(topic_groups)
    cleaned_validation_terms: list[str] = []
    for raw in validation_terms:
        value = re.sub(r"[^A-Za-z0-9&' /-]+", " ", str(raw or ""))
        value = re.sub(r"\s+", " ", value).strip(" -/")[:80]
        if value and value.casefold() not in {
            term.casefold() for term in cleaned_validation_terms
        }:
            cleaned_validation_terms.append(value)
        if len(cleaned_validation_terms) >= 12:
            break
    if cleaned_validation_terms:
        validation_group = {
            "id": "publisher-validation",
            "label": "Fresh publisher validation",
            "terms": tuple(f'"{term}"' for term in cleaned_validation_terms),
            "is_dynamic_validation": True,
        }
        # Keep the governed run count unchanged: on a live refresh the
        # dynamic validation family replaces the generic behaviour/resale
        # family instead of creating two additional paid Actor runs.
        if groups:
            groups[-1] = validation_group
        else:
            groups.append(validation_group)

    for window in windows:
        for group in groups:
            terms = [str(term).strip() for term in group.get("terms", ()) if str(term).strip()]
            if not terms:
                continue
            plan.append(
                {
                    "id": f"{group.get('id', 'topic')}:{window['id']}",
                    "group": str(group.get("id", "topic")),
                    "group_label": str(group.get("label", group.get("id", "Topic"))),
                    "window": window["id"],
                    "window_label": window["label"],
                    "is_expert": False,
                    "is_dynamic_validation": bool(
                        group.get("is_dynamic_validation")
                    ),
                    "input": {
                        "mode": "Advanced Search",
                        "query": _query(
                            " OR ".join(terms),
                            since=window["since"],
                            until=window["until"],
                            language=language,
                        ),
                        "query_type": "Latest",
                        "max_results": max(10, int(results_per_query)),
                    },
                }
            )

    priority = clean_expert_accounts(priority_accounts)
    priority_keys = {account.lower() for account in priority}
    accounts = [
        account
        for account in clean_expert_accounts(expert_accounts)
        if account.lower() not in priority_keys
    ]
    expert_chunk_size = max(1, int(expert_chunk_size))
    priority_chunks = [
        priority[index : index + expert_chunk_size]
        for index in range(0, len(priority), expert_chunk_size)
    ]
    supporting_chunks = [
        accounts[index : index + expert_chunk_size]
        for index in range(0, len(accounts), expert_chunk_size)
    ]
    for window in windows:
        tier_chunks = (
            (
                "commercial-priority",
                "Commercial priority",
                PRIORITY_EXPERT_MULTIPLIER,
                priority_chunks,
            ),
            (
                "expert-support",
                "Supporting expert panel",
                SUPPORTING_EXPERT_MULTIPLIER,
                supporting_chunks,
            ),
        )
        for tier_id, tier_label, multiplier, chunks in tier_chunks:
            for index, chunk in enumerate(chunks, 1):
                sources = " OR ".join(f"from:{account}" for account in chunk)
                body = (
                    f"({sources}) "
                    "(fashion OR style OR trend OR trends OR runway OR bag OR shoes OR vintage OR resale)"
                )
                plan.append(
                    {
                        "id": f"{tier_id}-{index}:{window['id']}",
                        "group": f"{tier_id}-{index}",
                        "group_label": f"{tier_label} {index}",
                        "window": window["id"],
                        "window_label": window["label"],
                        "is_expert": True,
                        "expert_tier": tier_id,
                        "expert_weight": multiplier,
                        "accounts": list(chunk),
                        "input": {
                            "mode": "Advanced Search",
                            "query": _query(
                                body,
                                since=window["since"],
                                until=window["until"],
                                language=language,
                            ),
                            "query_type": "Latest",
                            "max_results": max(10, int(expert_results_per_query)),
                        },
                    }
                )
    return plan


def _fallback_post_hash(post: dict[str, Any]) -> str:
    basis = "|".join(
        (
            str(post.get("text", "")).strip().lower(),
            str(post.get("created_at", "")),
            str(post.get("author_hash", "")),
        )
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


def deduplicate_posts(posts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Collapse the same X post returned by several searches while retaining provenance."""

    by_id: dict[str, dict[str, Any]] = {}
    for post in posts:
        key = str(post.get("post_hash") or _fallback_post_hash(post))
        existing = by_id.get(key)
        if existing is None:
            row = dict(post)
            row["post_hash"] = key
            row["listening_groups"] = sorted(
                set(post.get("listening_groups") or [str(post.get("listening_group", "topic"))])
            )
            row["evidence_channels"] = sorted(
                set(post.get("evidence_channels") or (["expert"] if post.get("is_expert") else ["open"]))
            )
            row["expert_weight"] = float(post.get("expert_weight") or 1.0)
            row["expert_tiers"] = sorted(
                set(
                    post.get("expert_tiers")
                    or ([str(post.get("expert_tier"))] if post.get("expert_tier") else [])
                )
            )
            row["duplicate_count"] = max(1, int(post.get("duplicate_count") or 1))
            by_id[key] = row
            continue

        existing["duplicate_count"] = int(existing.get("duplicate_count") or 1) + max(
            1, int(post.get("duplicate_count") or 1)
        )
        existing["listening_groups"] = sorted(
            set(existing.get("listening_groups") or [])
            | set(post.get("listening_groups") or [str(post.get("listening_group", "topic"))])
        )
        existing["evidence_channels"] = sorted(
            set(existing.get("evidence_channels") or [])
            | set(post.get("evidence_channels") or (["expert"] if post.get("is_expert") else ["open"]))
        )
        existing["is_expert"] = "expert" in existing["evidence_channels"]
        existing["expert_weight"] = max(
            float(existing.get("expert_weight") or 1.0),
            float(post.get("expert_weight") or 1.0),
        )
        existing["expert_tiers"] = sorted(
            set(existing.get("expert_tiers") or [])
            | set(
                post.get("expert_tiers")
                or ([str(post.get("expert_tier"))] if post.get("expert_tier") else [])
            )
        )
        if int(post.get("engagement") or 0) > int(existing.get("engagement") or 0):
            for field in ("likes", "reshares", "replies", "views", "engagement"):
                existing[field] = post.get(field, existing.get(field))

    unique = list(by_id.values())
    return unique, {
        "collected": len(posts),
        "unique": len(unique),
        "duplicates_removed": max(0, len(posts) - len(unique)),
    }
