from __future__ import annotations

from typing import Any
from urllib.parse import quote

import requests


ACTIVE_RUN_STATUSES = {"READY", "RUNNING", "TIMING-OUT", "ABORTING"}
TERMINAL_RUN_STATUSES = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


class ApifyCapacityError(RuntimeError):
    """Raised when Apify cannot allocate another Actor container."""


def apify_error_detail(response: requests.Response) -> tuple[str, str]:
    try:
        error = response.json().get("error") or {}
        return str(error.get("type") or ""), str(error.get("message") or "")
    except Exception:
        return "", ""


def is_capacity_failure(status_code: int, error_type: str, detail: str) -> bool:
    lowered = f"{error_type} {detail}".lower()
    return status_code == 402 and (
        "memory limit" in lowered
        or "actor-memory-limit-exceeded" in lowered
        or "concurrent-runs-limit-exceeded" in lowered
    )


def capacity_message(detail: str = "") -> str:
    suffix = f" Apify said: {detail[:220]}" if detail else ""
    return (
        "Apify's concurrent-memory allowance is full, so no new run can start. "
        "Stop active HULA runs in Data & Setup → Apify X run capacity, or wait for "
        "them to finish; adding fewer search terms will not free memory that is "
        "already reserved."
        + suffix
    )


def actor_memory_mb(value: Any, default: int) -> int:
    """Return an Apify-compatible power-of-two memory allocation."""

    try:
        memory = int(value)
    except (TypeError, ValueError):
        memory = int(default)
    if memory < 128 or memory & (memory - 1):
        return int(default)
    return memory


def abort_run(
    session: requests.Session,
    base_url: str,
    headers: dict[str, str],
    run_id: str,
) -> bool:
    """Force-stop one known run so its reserved memory is released promptly."""

    if not run_id:
        return False
    try:
        response = session.post(
            f"{base_url}/actor-runs/{quote(str(run_id), safe='')}/abort",
            headers=headers,
            params={"gracefully": "false"},
            timeout=30,
        )
        return bool(response.ok)
    except Exception:
        return False


def list_active_target_runs(
    session: requests.Session,
    base_url: str,
    headers: dict[str, str],
    target_path: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List active runs for one task or Actor without touching unrelated jobs."""

    response = session.get(
        f"{base_url}/{target_path}/runs",
        headers=headers,
        params={
            "status": ",".join(sorted(ACTIVE_RUN_STATUSES)),
            "desc": "1",
            "limit": max(1, min(1000, int(limit))),
        },
        timeout=30,
    )
    if not response.ok:
        _, detail = apify_error_detail(response)
        raise RuntimeError(
            f"Apify active-run check failed ({response.status_code})"
            + (f": {detail[:220]}" if detail else ".")
        )
    data = response.json().get("data") or {}
    return [
        row
        for row in (data.get("items") or [])
        if isinstance(row, dict) and str(row.get("status") or "") in ACTIVE_RUN_STATUSES
    ]


def run_memory_mb(
    session: requests.Session,
    base_url: str,
    headers: dict[str, str],
    run: dict[str, Any],
) -> int | None:
    options = run.get("options") or {}
    if isinstance(options, dict) and options.get("memoryMbytes") is not None:
        try:
            return int(options["memoryMbytes"])
        except (TypeError, ValueError):
            return None
    run_id = str(run.get("id") or "")
    if not run_id:
        return None
    try:
        response = session.get(
            f"{base_url}/actor-runs/{quote(run_id, safe='')}",
            headers=headers,
            timeout=30,
        )
        if not response.ok:
            return None
        detail = response.json().get("data") or {}
        value = (detail.get("options") or {}).get("memoryMbytes")
        return int(value) if value is not None else None
    except Exception:
        return None


def target_run_report(
    session: requests.Session,
    base_url: str,
    headers: dict[str, str],
    target_path: str,
) -> dict[str, Any]:
    runs = list_active_target_runs(session, base_url, headers, target_path)
    rows: list[dict[str, Any]] = []
    for run in runs:
        rows.append(
            {
                "id": str(run.get("id") or ""),
                "status": str(run.get("status") or ""),
                "started_at": str(run.get("startedAt") or ""),
                "memory_mb": run_memory_mb(session, base_url, headers, run),
            }
        )
    known_memory = [int(row["memory_mb"]) for row in rows if row.get("memory_mb")]
    return {
        "runs": rows,
        "count": len(rows),
        "known_memory_mb": sum(known_memory),
        "memory_complete": len(known_memory) == len(rows),
    }


def abort_target_runs(
    session: requests.Session,
    base_url: str,
    headers: dict[str, str],
    target_path: str,
) -> dict[str, int]:
    runs = list_active_target_runs(session, base_url, headers, target_path)
    stopped = sum(
        abort_run(session, base_url, headers, str(run.get("id") or ""))
        for run in runs
    )
    return {"found": len(runs), "stopped": stopped, "failed": len(runs) - stopped}
