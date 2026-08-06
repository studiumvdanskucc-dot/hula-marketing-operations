from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class OpenAIResponsesError(RuntimeError):
    pass


MODEL_PRICES_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (5.00, 30.00),
}


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        status=2,
        backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"POST"}),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _output_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct
    parts: list[str] = []
    for item in payload.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content") or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(str(content["text"]))
            if content.get("type") == "refusal" and content.get("refusal"):
                raise OpenAIResponsesError(str(content["refusal"]))
    text = "\n".join(parts).strip()
    if not text:
        raise OpenAIResponsesError("OpenAI returned no usable output text.")
    return text


def _strict_object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


CLUSTER_SCHEMA = _strict_object(
    {
        "clusters": {
            "type": "array",
            "items": _strict_object(
                {
                    "name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                },
                ["name", "aliases"],
            ),
        }
    },
    ["clusters"],
)

ENRICH_SCHEMA = _strict_object(
    {
        "trends": {
            "type": "array",
            "items": _strict_object(
                {
                    "id": {"type": "string"},
                    "category": {"type": "string"},
                    "why_now": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "content_angles": {"type": "array", "items": {"type": "string"}},
                },
                ["id", "category", "why_now", "aliases", "content_angles"],
            ),
        }
    },
    ["trends"],
)

RELEVANCE_SCHEMA = _strict_object(
    {
        "reviews": {
            "type": "array",
            "items": _strict_object(
                {
                    "trend_id": {"type": "string"},
                    "evidence_index": {"type": "integer"},
                    "relevant": {"type": "boolean"},
                    "relevance_score": {"type": "number"},
                    "reason": {"type": "string"},
                },
                ["trend_id", "evidence_index", "relevant", "relevance_score", "reason"],
            ),
        }
    },
    ["reviews"],
)

BLOG_SCHEMA = _strict_object(
    {
        "title": {"type": "string"},
        "dek": {"type": "string"},
        "body_markdown": {"type": "string"},
        "shopify_excerpt": {"type": "string"},
        "seo_title": {"type": "string"},
        "seo_description": {"type": "string"},
        "claims": {
            "type": "array",
            "items": _strict_object(
                {
                    "claim": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": [
                            "confirmed",
                            "similar_design_only",
                            "uncertain",
                            "not_found",
                        ],
                    },
                    "product_id": {"type": "string"},
                    "source_indices": {"type": "array", "items": {"type": "integer"}},
                    "evidence_note": {"type": "string"},
                },
                ["claim", "status", "product_id", "source_indices", "evidence_note"],
            ),
        },
        "editorial_notes": {"type": "array", "items": {"type": "string"}},
    },
    [
        "title",
        "dek",
        "body_markdown",
        "shopify_excerpt",
        "seo_title",
        "seo_description",
        "claims",
        "editorial_notes",
    ],
)


class OpenAIResponsesConnector:
    """Evidence-locked OpenAI Responses API client.

    The model may classify, merge and write, but this connector never asks it
    to calculate HULA's public scores. Those remain deterministic Python.
    """

    def __init__(
        self,
        api_key: str,
        *,
        api_url: str = "https://api.openai.com/v1/responses",
        luna_model: str = "gpt-5.6-luna",
        terra_model: str = "gpt-5.6-terra",
        sol_model: str = "gpt-5.6-sol",
        timeout_seconds: int = 180,
    ) -> None:
        self.api_key = str(api_key or "")
        self.api_url = str(api_url or "").rstrip("/")
        self.luna_model = str(luna_model or "gpt-5.6-luna")
        self.terra_model = str(terra_model or "gpt-5.6-terra")
        self.sol_model = str(sol_model or "gpt-5.6-sol")
        self.timeout_seconds = max(30, int(timeout_seconds))
        self.session = _session()
        self.usage_log: list[dict[str, Any]] = []

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _record_usage(self, payload: dict[str, Any], model: str, task: str) -> None:
        usage = payload.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        prices = MODEL_PRICES_PER_MILLION.get(model)
        cost = None
        if prices:
            cost = (input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000
        self.usage_log.append(
            {
                "task": task,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": round(cost, 6) if cost is not None else None,
            }
        )

    def call_json(
        self,
        *,
        model: str,
        task: str,
        instructions: str,
        input_text: str,
        schema: dict[str, Any],
        max_output_tokens: int,
        reasoning_effort: str = "low",
    ) -> dict[str, Any]:
        body = {
            "model": model,
            "instructions": instructions,
            "input": input_text,
            "reasoning": {"effort": reasoning_effort},
            "max_output_tokens": max_output_tokens,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": task.replace("-", "_")[:64],
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        try:
            response = self.session.post(
                self.api_url,
                headers=self.headers,
                json=body,
                timeout=self.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise OpenAIResponsesError(
                f"OpenAI timed out after {self.timeout_seconds} seconds."
            ) from exc
        except requests.RequestException as exc:
            raise OpenAIResponsesError(f"The app could not reach OpenAI: {exc}") from exc
        if not response.ok:
            try:
                detail = str(((response.json().get("error") or {}).get("message") or ""))
            except (TypeError, ValueError):
                detail = response.text[:260]
            request_id = response.headers.get("x-request-id")
            raise OpenAIResponsesError(
                f"OpenAI request failed ({response.status_code})"
                + (f": {detail[:260]}" if detail else "")
                + (f". Request ID: {request_id}" if request_id else "")
            )
        try:
            payload = response.json()
            result = json.loads(_output_text(payload))
        except (ValueError, TypeError) as exc:
            raise OpenAIResponsesError("OpenAI returned invalid structured JSON.") from exc
        if not isinstance(result, dict):
            raise OpenAIResponsesError("OpenAI returned an invalid structured result.")
        self._record_usage(payload, model, task)
        return result

    def test_connection(self) -> dict[str, Any]:
        schema = _strict_object({"ok": {"type": "boolean"}}, ["ok"])
        result = self.call_json(
            model=self.luna_model,
            task="connection_test",
            instructions="Return only the requested structured result.",
            input_text="Set ok to true.",
            schema=schema,
            max_output_tokens=100,
            reasoning_effort="low",
        )
        if result.get("ok") is not True:
            raise OpenAIResponsesError("OpenAI answered, but the diagnostic result was unexpected.")
        return {"ok": True, "model": self.luna_model}

    def cluster_topic_phrases(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact = [
            {
                "phrase": str(item.get("phrase") or item.get("name") or "")[:80],
                "frequency_index": int(item.get("count") or 0),
            }
            for item in candidates[:70]
            if str(item.get("phrase") or item.get("name") or "").strip()
        ]
        if not compact:
            return []
        result = self.call_json(
            model=self.terra_model,
            task="fashion_alias_clusters",
            instructions=(
                "You are a conservative fashion taxonomy analyst. Group only exact visual "
                "or product aliases. Do not merge items merely because they share an aesthetic. "
                "Every alias must be copied from the supplied phrases."
            ),
            input_text=json.dumps(compact, ensure_ascii=False),
            schema=CLUSTER_SCHEMA,
            max_output_tokens=2400,
            reasoning_effort="low",
        )
        return [row for row in result.get("clusters") or [] if isinstance(row, dict)]

    def review_evidence(self, trends: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Use Luna as a cheap specificity/relevance gate before Python scoring."""

        compact: list[dict[str, Any]] = []
        for trend in trends[:30]:
            trend_id = str(trend.get("id") or trend.get("canonical_slug") or "")
            trend_name = str(trend.get("name") or trend.get("trend_name") or "")
            for index, row in enumerate((trend.get("commercial_evidence") or [])[:15]):
                if not isinstance(row, dict):
                    continue
                compact.append(
                    {
                        "trend_id": trend_id,
                        "trend_name": trend_name,
                        "evidence_index": index,
                        "source": row.get("publisher") or row.get("source_name"),
                        "title": row.get("article_title") or row.get("title"),
                        "explicit_label": row.get("explicit_label"),
                        "summary": row.get("evidence_summary"),
                    }
                )
        if not compact:
            return trends
        compact = compact[:120]
        result = self.call_json(
            model=self.luna_model,
            task="evidence_relevance_review",
            instructions=(
                "You are a conservative fashion evidence filter. Judge only whether each "
                "supplied item specifically supports the named trend. Reject generic category, "
                "non-fashion, unrelated or merely aesthetic-neighbour evidence. Do not infer facts. "
                "Return every supplied trend_id and evidence_index exactly once."
            ),
            input_text=json.dumps(compact, ensure_ascii=False),
            schema=RELEVANCE_SCHEMA,
            max_output_tokens=6000,
            reasoning_effort="low",
        )
        reviews = {
            (str(row.get("trend_id") or ""), int(row.get("evidence_index") or 0)): row
            for row in result.get("reviews") or []
            if isinstance(row, dict)
        }
        reviewed: list[dict[str, Any]] = []
        for original in trends:
            trend = dict(original)
            trend_id = str(trend.get("id") or trend.get("canonical_slug") or "")
            retained: list[dict[str, Any]] = []
            excluded: list[dict[str, Any]] = []
            for index, original_row in enumerate(trend.get("commercial_evidence") or []):
                row = dict(original_row)
                review = reviews.get((trend_id, index))
                if review is None:
                    retained.append(row)
                    continue
                relevance = max(0.0, min(1.0, float(review.get("relevance_score") or 0)))
                row["model_relevance_score"] = relevance
                if review.get("relevant") is False or relevance < 0.5:
                    excluded.append(
                        {
                            "source": row.get("publisher") or row.get("source_name"),
                            "title": row.get("article_title") or row.get("title"),
                            "reason": str(review.get("reason") or "low relevance"),
                        }
                    )
                else:
                    retained.append(row)
            trend["commercial_evidence"] = retained
            if excluded:
                trend["model_excluded_evidence"] = excluded
            reviewed.append(trend)
        return reviewed

    def enrich_trends(self, trends: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact = [
            {
                "id": str(item.get("id") or item.get("canonical_slug") or ""),
                "name": item.get("name") or item.get("trend_name"),
                "aliases": list(item.get("aliases") or [])[:8],
                "evidence": [
                    {
                        "source": row.get("source_name"),
                        "type": row.get("evidence_type"),
                        "date": row.get("published_at"),
                        "summary": row.get("evidence_summary"),
                        "stance": row.get("supports_or_contradicts"),
                    }
                    for row in (item.get("evidence") or [])[:12]
                    if isinstance(row, dict)
                ],
            }
            for item in trends[:20]
        ]
        result = self.call_json(
            model=self.sol_model,
            task="weekly_trend_synthesis",
            instructions=(
                "You are HULA's final fashion trend analyst. Use only the supplied evidence. "
                "Never invent a source, metric, runway, celebrity, retailer or causal claim. "
                "Do not calculate or suggest scores. Be specific and commercially useful."
            ),
            input_text=json.dumps(compact, ensure_ascii=False),
            schema=ENRICH_SCHEMA,
            max_output_tokens=5000,
            reasoning_effort="medium",
        )
        by_id = {
            str(row.get("id") or ""): row
            for row in result.get("trends") or []
            if isinstance(row, dict)
        }
        enriched: list[dict[str, Any]] = []
        for trend in trends:
            merged = dict(trend)
            addition = by_id.get(str(trend.get("id") or trend.get("canonical_slug") or ""), {})
            for key in ("category", "why_now", "aliases", "content_angles"):
                if addition.get(key):
                    merged[key] = addition[key]
            enriched.append(merged)
        return enriched

    def evidence_locked_blog(
        self,
        trend: dict[str, Any],
        products: list[dict[str, Any]],
        *,
        reason: str,
        stores: list[str] | None = None,
    ) -> dict[str, Any]:
        sources: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for row in trend.get("evidence") or []:
            url = str(row.get("source_url") or "")
            if not url.startswith(("https://", "http://")) or url in seen_urls:
                continue
            seen_urls.add(url)
            sources.append(
                {
                    "index": len(sources) + 1,
                    "title": str(row.get("title") or row.get("source_name") or "Evidence source"),
                    "url": url,
                    "evidence_summary": str(row.get("evidence_summary") or ""),
                    "published_at": row.get("published_at"),
                }
            )
        product_context = []
        for product in products[:5]:
            product_context.append(
                {
                    "id": str(product.get("id") or ""),
                    "title": product.get("title"),
                    "brand": product.get("vendor"),
                    "product_type": product.get("product_type"),
                    "description": str(product.get("description") or "")[:700],
                    "tags": list(product.get("tags") or [])[:16],
                    "price": product.get("price"),
                    "currency": product.get("currency"),
                    "product_url": product.get("product_url"),
                }
            )
        result = self.call_json(
            model=self.sol_model,
            task="evidence_locked_blog",
            instructions=(
                "You are HULA Hong Kong's fashion journal editor. Write polished British "
                "English with an intelligent, playful circular-fashion voice. Every factual "
                "trend claim must be supported by the supplied numbered sources. Never invent "
                "celebrity wear, runway provenance, archive year, rarity, condition or stock. "
                "Use editorial interpretation only when clearly framed as interpretation."
            ),
            input_text=json.dumps(
                {
                    "editorial_reason": reason,
                    "stores": stores or ["Online", "HULA Soho", "The Hub"],
                    "trend": {
                        "name": trend.get("name") or trend.get("trend_name"),
                        "momentum": trend.get("momentum"),
                        "why_now": trend.get("why_now"),
                        "commercial_interpretation": trend.get("commercial_interpretation"),
                    },
                    "numbered_sources": sources,
                    "selected_products": product_context,
                    "rules": [
                        "Target 700 to 1000 words with short subheadings.",
                        "Cite each factual claim by returning its numbered source_indices.",
                        "A confirmed claim must have at least one valid source index.",
                        "Mention Soho and The Hub equally when both are selected.",
                        "Do not put a source list inside body_markdown.",
                    ],
                },
                ensure_ascii=False,
            ),
            schema=BLOG_SCHEMA,
            max_output_tokens=9000,
            reasoning_effort="medium",
        )
        result.update(
            {
                "sources": [
                    {"index": row["index"], "title": row["title"], "url": row["url"]}
                    for row in sources
                ],
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                "model": self.sol_model,
                "grounded": False,
                "evidence_locked": True,
                "usage": list(self.usage_log[-1:]),
            }
        )
        return result
