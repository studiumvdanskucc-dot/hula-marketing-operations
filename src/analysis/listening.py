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
            '"butter yellow"',
            '"suede bag"',
            '"raffia bag"',
            '"sheer dressing"',
            '"lace trend"',
            '"polka dot"',
            '"leopard print"',
            '"metallic fashion"',
        ),
    },
    {
        "id": "silhouette",
        "label": "Shapes & silhouettes",
        "terms": (
            '"silhouette trend"',
            '"east west bag"',
            '"drop waist"',
            '"capri pants"',
            '"maxi skirt"',
            '"barrel jeans"',
            '"fisherman sandals"',
            '"ballet flats"',
            '"mary jane shoes"',
            '"statement belt"',
        ),
    },
    {
        "id": "aesthetic",
        "label": "Aesthetics",
        "terms": (
            '"fashion aesthetic"',
            '"style aesthetic"',
            '"boho fashion"',
            '"minimalist fashion"',
            '"archive fashion"',
            '"quiet luxury"',
            '"maximalist fashion"',
            '"coastal style"',
            '"street style"',
            '"vintage fashion"',
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
    "Lyst",
    "WhoWhatWear",
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
    topic_groups: Iterable[dict[str, Any]] = DEFAULT_TOPIC_GROUPS,
    expert_chunk_size: int = 8,
) -> list[dict[str, Any]]:
    """Build balanced current/previous X searches for ScrapeBadger Advanced Search."""

    current_time = (now or datetime.now(tz=timezone.utc)).astimezone(timezone.utc)
    windows = _window_bounds(current_time)
    plan: list[dict[str, Any]] = []

    for window in windows:
        for group in topic_groups:
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

    accounts = clean_expert_accounts(expert_accounts)
    expert_chunk_size = max(1, int(expert_chunk_size))
    chunks = [accounts[index : index + expert_chunk_size] for index in range(0, len(accounts), expert_chunk_size)]
    for window in windows:
        for index, chunk in enumerate(chunks, 1):
            sources = " OR ".join(f"from:{account}" for account in chunk)
            body = (
                f"({sources}) "
                "(fashion OR style OR trend OR trends OR runway OR bag OR shoes OR vintage OR resale)"
            )
            plan.append(
                {
                    "id": f"expert-{index}:{window['id']}",
                    "group": f"expert-{index}",
                    "group_label": f"Expert panel {index}",
                    "window": window["id"],
                    "window_label": window["label"],
                    "is_expert": True,
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
        if int(post.get("engagement") or 0) > int(existing.get("engagement") or 0):
            for field in ("likes", "reshares", "replies", "views", "engagement"):
                existing[field] = post.get(field, existing.get(field))

    unique = list(by_id.values())
    return unique, {
        "collected": len(posts),
        "unique": len(unique),
        "duplicates_removed": max(0, len(posts) - len(unique)),
    }
