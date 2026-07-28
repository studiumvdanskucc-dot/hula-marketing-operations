from __future__ import annotations

from typing import Any


ALLOWED_CLAIM_STATUSES = {
    "confirmed",
    "similar_design_only",
    "uncertain",
    "not_found",
}


def normalise_blog_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalise model output and prevent unsupported certainty labels."""

    result = dict(payload)
    sources = [
        {
            "index": int(source.get("index") or index),
            "title": str(source.get("title") or f"Source {index}"),
            "url": str(source.get("url") or ""),
        }
        for index, source in enumerate(result.get("sources") or [], 1)
        if str(source.get("url") or "").startswith(("https://", "http://"))
    ]
    claims: list[dict[str, Any]] = []
    for raw in result.get("claims") or []:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "uncertain").strip().casefold()
        if status not in ALLOWED_CLAIM_STATUSES:
            status = "uncertain"
        source_indices = [
            int(index)
            for index in raw.get("source_indices") or []
            if str(index).isdigit()
            and int(index) in {source["index"] for source in sources}
        ]
        note = str(raw.get("evidence_note") or "").strip()
        if status == "confirmed" and not source_indices:
            status = "uncertain"
            note = (
                note + " "
                if note
                else ""
            ) + "No claim-level grounding source was returned."
        claims.append(
            {
                "claim": str(raw.get("claim") or "").strip(),
                "status": status,
                "product_id": str(raw.get("product_id") or "").strip(),
                "source_indices": list(dict.fromkeys(source_indices)),
                "evidence_note": note,
            }
        )
    result["sources"] = sources
    result["claims"] = [claim for claim in claims if claim["claim"]]
    result["confirmed_claims"] = sum(
        claim["status"] == "confirmed" for claim in result["claims"]
    )
    result["needs_review_claims"] = sum(
        claim["status"] != "confirmed" for claim in result["claims"]
    )
    body = str(result.get("body_markdown") or "").strip()
    removed_claims = 0
    for claim in result["claims"]:
        if claim["status"] == "confirmed":
            continue
        exact = claim["claim"]
        if exact and exact in body:
            body = body.replace(exact, "").strip()
            removed_claims += 1
    result["body_markdown"] = body
    result["title"] = str(result.get("title") or "HULA weekly edit").strip()
    result["dek"] = str(result.get("dek") or "").strip()
    result["editorial_notes"] = [
        str(note).strip()
        for note in result.get("editorial_notes") or []
        if str(note).strip()
    ]
    if removed_claims:
        result["editorial_notes"].append(
            f"{removed_claims} unsupported claim(s) were removed from the "
            "publishable body automatically."
        )
    return result
