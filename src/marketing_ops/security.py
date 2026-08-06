from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any


_SENSITIVE_KEY = re.compile(
    r"(access[_-]?token|refresh[_-]?token|api[_-]?key|client[_-]?secret|"
    r"password|authorization|cookie|private[_-]?key|service[_-]?role)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{8,}")
_URL_SECRET = re.compile(
    r"(?i)([?&](?:key|token|access_token|api_key|client_secret)=)[^&\s]+"
)
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")


def redact_text(value: Any, known_secrets: Iterable[str] = ()) -> str:
    text = str(value or "")
    for secret in known_secrets:
        secret_text = str(secret or "")
        if secret_text:
            text = text.replace(secret_text, "[redacted]")
    text = _BEARER.sub("Bearer [redacted]", text)
    text = _URL_SECRET.sub(r"\1[redacted]", text)
    return text[:1200]


def safe_exception(exc: BaseException, known_secrets: Iterable[str] = ()) -> str:
    detail = redact_text(str(exc).strip(), known_secrets)
    if not detail:
        detail = "No additional detail was returned."
    return f"{type(exc).__name__}: {detail}"[:1200]


def redact_mapping(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[redacted]"
            if _SENSITIVE_KEY.search(str(key))
            else redact_mapping(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_mapping(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_mapping(item) for item in value)
    if isinstance(value, str):
        return redact_text(value)
    return value


def redact_customer_text(value: str) -> tuple[str, bool]:
    redacted = _EMAIL.sub("[email redacted]", value or "")
    redacted = _PHONE.sub("[phone redacted]", redacted)
    return redacted, redacted != (value or "")
