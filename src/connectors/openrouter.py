from __future__ import annotations

import json
import re
from typing import Any

import requests


class OpenRouterError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I | re.S)
    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        try:
            value, _ = decoder.raw_decode(cleaned[match.start() :])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue
    raise OpenRouterError("The model response did not contain valid JSON.")


class OpenRouterConnector:
    def __init__(
        self,
        api_key: str,
        model: str,
        api_url: str = "https://openrouter.ai/api/v1/chat/completions",
        timeout: int = 180,
        site_url: str = "",
        app_name: str = "HULA Trend Intelligence",
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.timeout = timeout
        self.site_url = site_url
        self.app_name = app_name

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Title": self.app_name,
        }
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        return headers

    def call_json(
        self,
        system: str,
        user: str | list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1800,
    ) -> dict[str, Any]:
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                },
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise OpenRouterError(
                f"The request timed out after {self.timeout} seconds. Try the test again; "
                "if it repeats, check OpenRouter provider status."
            ) from exc
        except requests.ConnectionError as exc:
            raise OpenRouterError(
                "The app could not reach OpenRouter. Check the internet connection and API URL."
            ) from exc
        except requests.RequestException as exc:
            raise OpenRouterError(f"The OpenRouter request could not be sent: {exc}") from exc
        if not response.ok:
            detail = ""
            try:
                detail = str((response.json().get("error") or {}).get("message", ""))
            except Exception:
                pass
            hints = {
                400: "The request or model option was rejected.",
                401: "The API key was not accepted. Check that the complete key is loaded and restart Streamlit.",
                402: "The OpenRouter account needs sufficient credits.",
                403: "The key or account is not permitted to use this provider/model.",
                404: "Check the API URL and model slug.",
                429: "The account or provider is rate-limited; retry shortly.",
            }
            request_id = response.headers.get("x-request-id") or response.headers.get(
                "x-openrouter-request-id"
            )
            hint = hints.get(response.status_code, "OpenRouter or its provider returned an error.")
            raise OpenRouterError(
                f"OpenRouter request failed ({response.status_code})"
                + (f": {detail[:240]}. " if detail else ". ")
                + hint
                + (f" Request ID: {request_id}." if request_id else "")
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise OpenRouterError("OpenRouter returned a non-JSON API response.") from exc
        choices = payload.get("choices") or []
        if not choices:
            raise OpenRouterError("OpenRouter returned no choices.")
        content = ((choices[0].get("message") or {}).get("content") or "")
        if isinstance(content, list):
            content = "\n".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        return _extract_json(str(content))

    def extract_instagram_visual_terms(
        self,
        posts: list[dict[str, Any]],
        *,
        max_posts: int = 10,
    ) -> dict[str, list[str]]:
        """Read trend labels visible inside selected public Instagram graphics."""

        selected = [
            post
            for post in posts
            if post.get("media_urls") and post.get("post_hash")
        ][: max(1, int(max_posts))]
        if not selected:
            return {}

        parts: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": (
                    "Inspect each public Instagram image below. Extract only concrete "
                    "fashion trend names visibly supported by the image or caption. "
                    "Ignore generic labels such as fashion, outfit ideas, dress, trousers, "
                    "style and trend. Return JSON in the exact shape "
                    '{"posts":[{"post_hash":"...","visual_terms":["mini dress"]}]}. '
                    "Use the supplied post_hash exactly. Return an empty visual_terms list "
                    "when the visual does not support a specific fashion product, material, "
                    "silhouette, colour combination or named aesthetic."
                ),
            }
        ]
        for post in selected:
            parts.append(
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "post_hash": post.get("post_hash"),
                            "source": post.get("source_account"),
                            "caption": str(post.get("text") or "")[:700],
                        },
                        ensure_ascii=False,
                    ),
                }
            )
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": str(post["media_urls"][0])},
                }
            )
        result = self.call_json(
            (
                "You are a conservative fashion-visual taxonomy analyst. "
                "Do not infer a trend from a person, logo or setting alone. "
                "Return strict JSON and no markdown."
            ),
            parts,
            temperature=0,
            max_tokens=1800,
        )
        output: dict[str, list[str]] = {}
        allowed_ids = {str(post.get("post_hash")) for post in selected}
        for row in result.get("posts") or []:
            if not isinstance(row, dict):
                continue
            post_hash = str(row.get("post_hash") or "")
            if post_hash not in allowed_ids:
                continue
            terms = [
                str(term).strip()
                for term in row.get("visual_terms") or []
                if str(term).strip()
            ]
            output[post_hash] = list(dict.fromkeys(terms))[:8]
        return output

    def test_connection(self) -> dict[str, Any]:
        result = self.call_json(
            "Return valid JSON only.",
            'Return exactly {"ok":true}.',
            temperature=0,
            max_tokens=30,
        )
        if result.get("ok") is not True:
            raise OpenRouterError("The model answered, but the diagnostic JSON was unexpected.")
        return {"ok": True, "model": self.model}

    def cluster_topic_phrases(
        self, candidates: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Group aggregated candidate phrases without sending raw posts or authors."""

        compact = [
            {
                "phrase": str(item.get("phrase", ""))[:80],
                "frequency_index": int(item.get("count") or 0),
            }
            for item in candidates[:70]
            if str(item.get("phrase", "")).strip()
        ]
        if not compact:
            return []
        result = self.call_json(
            """You are a precise fashion taxonomy analyst. Group only phrases that
refer to the same concrete fashion concept. For example, ballet pumps and
ballet flats may be aliases, while flats and high heels are not. Do not group
merely because phrases share a broad word such as bag, fashion or style. Use
only supplied phrases as aliases. Return strict JSON and no markdown.""",
            """Return up to 35 clusters using this exact shape:
{"clusters":[{"name":"Ballet Flats","aliases":["ballet flats","ballet pumps"]}]}

Every alias must exactly match one supplied phrase. Leave ambiguous phrases
unclustered rather than forcing a match.

Aggregated candidate phrases:
""" + json.dumps(compact, ensure_ascii=False),
            temperature=0,
            max_tokens=2200,
        )
        clusters = result.get("clusters") or []
        return [cluster for cluster in clusters if isinstance(cluster, dict)]

    def enrich_trends(self, trends: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "aliases": item.get("aliases", []),
                "google_score": item.get("google_score"),
                "x_score": item.get("x_score"),
                "search_momentum": item.get("search_momentum"),
                "mention_growth": item.get("mention_growth"),
            }
            for item in trends[:12]
        ]
        result = self.call_json(
            """You are a fashion trend analyst for HULA, a Hong Kong pre-owned
designer fashion retailer. Work only from the aggregated evidence provided.
Do not claim a runway origin, celebrity association, or cultural cause unless
the evidence explicitly states it. Return strict JSON and no markdown.""",
            """For each trend, provide a concise category, lifecycle stage,
one evidence-led 'why now' sentence, 3 useful aliases for catalogue matching,
and 3 editorial content angles. Keep the exact id. Allowed stages: Emerging,
Rising, Peaking, Established, Cooling. Return:
{"trends":[{"id":"...","category":"...","stage":"Rising","why_now":"...","aliases":[],"content_angles":[]}]}

Aggregated signals:
""" + json.dumps(compact, ensure_ascii=False),
            temperature=0.15,
            max_tokens=2200,
        )
        by_id = {
            str(item.get("id")): item
            for item in result.get("trends", [])
            if isinstance(item, dict)
        }
        enriched: list[dict[str, Any]] = []
        for trend in trends:
            addition = by_id.get(str(trend.get("id")), {})
            merged = dict(trend)
            for key in ("category", "stage", "why_now", "aliases", "content_angles"):
                if addition.get(key):
                    merged[key] = addition[key]
            enriched.append(merged)
        return enriched

    def campaign_brief(
        self,
        trend: dict[str, Any],
        products: list[dict[str, Any]],
        channel: str,
        objective: str,
    ) -> dict[str, Any]:
        product_context = [
            {
                "title": product.get("title"),
                "brand": product.get("vendor"),
                "type": product.get("product_type"),
                "tags": product.get("tags", [])[:12],
                "price": product.get("price"),
                "currency": product.get("currency"),
            }
            for product in products[:6]
        ]
        return self.call_json(
            """You are HULA's sharp, playful editorial strategist. HULA is a
Hong Kong pre-owned designer-fashion destination. Write polished British
English. Be fashion-literate, concise and specific. Never invent product
history, rarity, runway provenance, condition, or availability. Return strict
JSON with no markdown.""",
            f"""Create one {channel} campaign for the objective '{objective}'.
Use only the supplied trend and products. Return this exact shape:
{{"campaign_name":"","insight":"","hook":"","caption":"","shot_list":[""],"story_frames":[""],"cta":"","proof_points":[""],"avoid":[""]}}

Trend: {json.dumps(trend, ensure_ascii=False)}
Products: {json.dumps(product_context, ensure_ascii=False)}""",
            temperature=0.45,
            max_tokens=1800,
        )
