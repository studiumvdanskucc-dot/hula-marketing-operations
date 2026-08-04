from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class GeminiResearchError(RuntimeError):
    pass


_TEST_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


_BLOG_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "dek": {"type": "string"},
        "body_markdown": {"type": "string"},
        "shopify_excerpt": {"type": "string"},
        "seo_title": {"type": "string"},
        "seo_description": {"type": "string"},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
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
                    "evidence_note": {"type": "string"},
                },
                "required": [
                    "claim",
                    "status",
                    "product_id",
                    "evidence_note",
                ],
                "additionalProperties": False,
            },
        },
        "editorial_notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": [
        "title",
        "dek",
        "body_markdown",
        "shopify_excerpt",
        "seo_title",
        "seo_description",
        "claims",
        "editorial_notes",
    ],
    "additionalProperties": False,
}


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"POST"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        str(text or "").strip(),
        flags=re.I | re.S,
    )
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        try:
            parsed, _ = decoder.raw_decode(cleaned[match.start() :])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise GeminiResearchError("Gemini did not return a valid JSON object.")


def _response_diagnostic(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
    prompt_feedback = payload.get("promptFeedback") or {}
    usage = payload.get("usageMetadata") or {}
    details: list[str] = []
    finish_reason = str(
        candidate.get("finishReason") or candidate.get("finish_reason") or ""
    ).strip()
    block_reason = str(
        prompt_feedback.get("blockReason")
        or prompt_feedback.get("block_reason")
        or ""
    ).strip()
    if finish_reason:
        details.append(f"finish reason: {finish_reason}")
    if block_reason:
        details.append(f"prompt block: {block_reason}")
    token_fields = (
        ("output tokens", "candidatesTokenCount"),
        ("thought tokens", "thoughtsTokenCount"),
        ("total tokens", "totalTokenCount"),
    )
    for label, key in token_fields:
        value = usage.get(key)
        if value is not None:
            details.append(f"{label}: {value}")
    return "; ".join(details)


def _response_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        diagnostic = _response_diagnostic(payload)
        raise GeminiResearchError(
            "Gemini returned no candidate"
            + (f" ({diagnostic})." if diagnostic else ".")
        )
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    text = "\n".join(
        str(part.get("text") or "")
        for part in parts
        if isinstance(part, dict) and part.get("text")
    ).strip()
    if not text:
        diagnostic = _response_diagnostic(payload)
        raise GeminiResearchError(
            "Gemini returned an empty response"
            + (f" ({diagnostic})." if diagnostic else ".")
        )
    return text


def _empty_response_can_retry(payload: dict[str, Any]) -> bool:
    candidates = payload.get("candidates") or []
    if not candidates or not isinstance(candidates[0], dict):
        return False
    candidate = candidates[0]
    parts = ((candidate.get("content") or {}).get("parts") or [])
    if any(
        isinstance(part, dict) and str(part.get("text") or "").strip()
        for part in parts
    ):
        return False
    finish_reason = str(
        candidate.get("finishReason") or candidate.get("finish_reason") or ""
    ).upper()
    return finish_reason not in {
        "SAFETY",
        "BLOCKLIST",
        "PROHIBITED_CONTENT",
        "SPII",
        "IMAGE_SAFETY",
        "RECITATION",
    }


def grounding_sources(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = payload.get("candidates") or []
    metadata = (
        (candidates[0].get("groundingMetadata") or {})
        if candidates and isinstance(candidates[0], dict)
        else {}
    )
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in metadata.get("groundingChunks") or []:
        web = (chunk or {}).get("web") or {}
        url = str(web.get("uri") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        index = len(output) + 1
        output.append(
            {
                "index": index,
                "title": str(web.get("title") or f"Source {index}"),
                "url": url,
            }
        )
    return output


def grounding_supports(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Map grounded response segments to the displayed source numbers."""

    candidates = payload.get("candidates") or []
    metadata = (
        (candidates[0].get("groundingMetadata") or {})
        if candidates and isinstance(candidates[0], dict)
        else {}
    )
    chunks = metadata.get("groundingChunks") or []
    source_number_by_chunk: dict[int, int] = {}
    source_number_by_url: dict[str, int] = {}
    next_number = 1
    for chunk_index, chunk in enumerate(chunks):
        web = (chunk or {}).get("web") or {}
        url = str(web.get("uri") or "").strip()
        if not url:
            continue
        if url not in source_number_by_url:
            source_number_by_url[url] = next_number
            next_number += 1
        source_number_by_chunk[chunk_index] = source_number_by_url[url]

    output: list[dict[str, Any]] = []
    for support in metadata.get("groundingSupports") or []:
        segment = (support or {}).get("segment") or {}
        text = str(segment.get("text") or "").strip()
        indices = [
            source_number_by_chunk[index]
            for index in (support or {}).get("groundingChunkIndices") or []
            if index in source_number_by_chunk
        ]
        if text and indices:
            output.append(
                {
                    "text": text,
                    "source_indices": list(dict.fromkeys(indices)),
                }
            )
    return output


def _evidence_tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) >= 4
    }


def attach_claim_sources(
    result: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Attach grounding sources to model claims or leave them unconfirmed."""

    output = dict(result)
    supports = grounding_supports(payload)
    claims: list[dict[str, Any]] = []
    for raw in output.get("claims") or []:
        if not isinstance(raw, dict):
            continue
        claim = dict(raw)
        claim_text = str(claim.get("claim") or "")
        claim_tokens = _evidence_tokens(claim_text)
        matched: list[int] = []
        for support in supports:
            support_text = str(support.get("text") or "")
            support_tokens = _evidence_tokens(support_text)
            overlap = len(claim_tokens & support_tokens)
            denominator = max(1, min(len(claim_tokens), len(support_tokens)))
            related = (
                len(support_text) >= 12
                and support_text.casefold() in claim_text.casefold()
            ) or (overlap / denominator >= 0.45)
            if related:
                matched.extend(support.get("source_indices") or [])
        claim["source_indices"] = list(dict.fromkeys(matched))
        claims.append(claim)
    output["claims"] = claims
    return output


class GeminiResearchConnector:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-3.6-flash",
        api_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: int = 180,
        grounding_enabled: bool = True,
    ) -> None:
        self.api_key = str(api_key or "")
        self.model = str(model or "gemini-3.6-flash")
        self.api_url = str(api_url or "").rstrip("/")
        self.timeout_seconds = max(30, int(timeout_seconds))
        self.grounding_enabled = bool(grounding_enabled)
        self.session = _session()

    @property
    def is_gemini_3(self) -> bool:
        return self.model.removeprefix("models/").startswith("gemini-3")

    @property
    def endpoint(self) -> str:
        return (
            f"{self.api_url}/models/{quote(self.model, safe='.-_')}:generateContent"
        )

    @property
    def headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _generate(
        self,
        prompt: str,
        *,
        grounded: bool,
        max_output_tokens: int,
        thinking_level: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        generation_config: dict[str, Any] = {
            "maxOutputTokens": max_output_tokens,
        }
        if thinking_level and self.is_gemini_3:
            generation_config["thinkingConfig"] = {
                "thinkingLevel": thinking_level,
            }
        if response_schema and self.is_gemini_3:
            generation_config["responseFormat"] = {
                "text": {
                    "mimeType": "application/json",
                    "schema": response_schema,
                }
            }
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        if grounded:
            body["tools"] = [{"google_search": {}}]
        try:
            response = self.session.post(
                self.endpoint,
                headers=self.headers,
                json=body,
                timeout=self.timeout_seconds,
            )
        except requests.Timeout as exc:
            raise GeminiResearchError(
                f"Gemini timed out after {self.timeout_seconds} seconds."
            ) from exc
        except requests.RequestException as exc:
            raise GeminiResearchError(
                f"The app could not reach Gemini: {exc}"
            ) from exc
        if not response.ok:
            detail = ""
            try:
                detail = str(
                    ((response.json().get("error") or {}).get("message") or "")
                )
            except (TypeError, ValueError):
                detail = response.text[:260]
            hints = {
                400: "The selected model or Search tool rejected the request.",
                401: "The Gemini API key was not accepted.",
                403: "The project is not allowed to use this model or tool.",
                429: "The free Gemini allowance is temporarily exhausted.",
            }
            raise GeminiResearchError(
                f"Gemini request failed ({response.status_code})"
                + (f": {detail[:260]}. " if detail else ". ")
                + hints.get(response.status_code, "Gemini returned an error.")
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise GeminiResearchError("Gemini returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise GeminiResearchError("Gemini returned an invalid response object.")
        return payload

    def _generate_text(
        self,
        prompt: str,
        *,
        grounded: bool,
        max_output_tokens: int,
        thinking_level: str | None,
        response_schema: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], str]:
        """Generate visible text, retrying one transient HTTP-200 blank response."""

        last_error: GeminiResearchError | None = None
        for attempt in range(2):
            payload = self._generate(
                prompt,
                grounded=grounded,
                max_output_tokens=max_output_tokens,
                thinking_level=thinking_level,
                response_schema=response_schema,
            )
            try:
                return payload, _response_text(payload)
            except GeminiResearchError as exc:
                last_error = exc
                if attempt == 0 and _empty_response_can_retry(payload):
                    continue
                raise
        raise last_error or GeminiResearchError("Gemini returned no usable text.")

    def test_connection(self) -> dict[str, Any]:
        payload, text = self._generate_text(
            'Return exactly this JSON object and nothing else: {"ok":true}',
            grounded=False,
            max_output_tokens=1024,
            thinking_level="minimal",
            response_schema=_TEST_RESPONSE_SCHEMA,
        )
        result = attach_claim_sources(
            extract_json_object(text),
            payload,
        )
        if result.get("ok") is not True:
            raise GeminiResearchError(
                "Gemini answered, but the diagnostic JSON was unexpected."
            )
        return {"ok": True, "model": self.model}

    def researched_blog(
        self,
        trend: dict[str, Any],
        products: list[dict[str, Any]],
        *,
        reason: str,
        stores: list[str] | None = None,
    ) -> dict[str, Any]:
        product_context = [
            {
                "id": product.get("id"),
                "sku": product.get("sku"),
                "title": product.get("title"),
                "brand": product.get("vendor"),
                "product_type": product.get("product_type"),
                "description": str(product.get("description") or "")[:900],
                "tags": list(product.get("tags") or [])[:18],
                "product_url": product.get("product_url"),
                "price": product.get("price"),
                "currency": product.get("currency"),
            }
            for product in products[:5]
        ]
        prompt = f"""
You are HULA Hong Kong's fashion journal editor and evidence researcher.
Write polished British English with HULA's intelligent, playful, circular-fashion
voice. Research the public web before writing.

Editorial reason: {reason}
Store context: {", ".join(stores or ["Online", "Soho", "The Hub"])}

Trend evidence:
{json.dumps(trend, ensure_ascii=False)}

Selected public product information:
{json.dumps(product_context, ensure_ascii=False)}

Critical evidence rules:
1. A claim that a named person wore a product may be "confirmed" only when a
credible source supports the exact design, collection or unmistakably identical
piece. A merely similar item must be "similar_design_only" and must not be
written as a factual celebrity association in body_markdown.
2. Never invent runway season, archive year, rarity, provenance, condition,
availability or event details.
3. body_markdown may contain only confirmed factual claims plus clearly framed
styling/editorial interpretation. Put uncertainty in editorial_notes.
4. Include a natural circular-fashion angle, 3–5 selected HULA products and a
final CTA that reflects the editorial reason. Mention Soho and The Hub equally
when both are relevant.
5. Target 700–1,000 words. Use short subheadings and no source list inside the
body; sources are returned separately by the API.

Return strict JSON and no markdown fence, with this exact shape:
{{
  "title": "",
  "dek": "",
  "body_markdown": "",
  "shopify_excerpt": "",
  "seo_title": "",
  "seo_description": "",
  "claims": [
    {{
      "claim": "",
      "status": "confirmed|similar_design_only|uncertain|not_found",
      "product_id": "",
      "evidence_note": ""
    }}
  ],
  "editorial_notes": [""]
}}
""".strip()
        grounded = self.grounding_enabled
        payload, text = self._generate_text(
            prompt,
            grounded=grounded,
            max_output_tokens=12000,
            thinking_level="low",
            response_schema=_BLOG_RESPONSE_SCHEMA,
        )
        result = attach_claim_sources(extract_json_object(text), payload)
        result.update(
            {
                "generated_at": datetime.now(tz=timezone.utc).isoformat(),
                "model": self.model,
                "grounded": grounded,
                "sources": grounding_sources(payload),
                "search_queries": list(
                    (
                        ((payload.get("candidates") or [{}])[0].get(
                            "groundingMetadata"
                        )
                        or {})
                    ).get("webSearchQueries")
                    or []
                ),
            }
        )
        return result
