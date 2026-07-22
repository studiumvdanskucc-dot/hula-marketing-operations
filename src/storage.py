from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def load_snapshot(path: str | Path) -> dict[str, Any] | None:
    snapshot_path = Path(path)
    if not snapshot_path.exists():
        return None
    try:
        with snapshot_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, path)


def save_snapshot(
    payload: dict[str, Any],
    latest_path: str | Path,
    *,
    archive: bool = True,
) -> tuple[Path, Path | None]:
    latest = Path(latest_path)
    _atomic_json_write(latest, payload)
    archived: Path | None = None
    if archive:
        generated = str((payload.get("meta") or {}).get("generated_at", ""))
        try:
            stamp = datetime.fromisoformat(generated.replace("Z", "+00:00"))
        except ValueError:
            stamp = datetime.now(tz=timezone.utc)
        archived = latest.parent / "archive" / f"{stamp.date().isoformat()}.json"
        _atomic_json_write(archived, payload)
    return latest, archived


def load_trend_presence(
    latest_path: str | Path,
    *,
    weeks: int = 4,
) -> dict[str, int]:
    """Count how many recent weekly snapshots already contained each trend."""

    latest = Path(latest_path)
    candidates = [latest]
    archive_dir = latest.parent / "archive"
    if archive_dir.exists():
        candidates.extend(sorted(archive_dir.glob("*.json"), reverse=True))
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=max(1, weeks) * 7 + 2)
    seen_snapshots: set[str] = set()
    presence: Counter[str] = Counter()
    for candidate in candidates:
        snapshot = load_snapshot(candidate)
        if not snapshot:
            continue
        generated = str((snapshot.get("meta") or {}).get("generated_at") or candidate.name)
        if generated in seen_snapshots:
            continue
        try:
            generated_at = datetime.fromisoformat(generated.replace("Z", "+00:00"))
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=timezone.utc)
            if generated_at.astimezone(timezone.utc) < cutoff:
                continue
        except ValueError:
            pass
        seen_snapshots.add(generated)
        for trend in snapshot.get("trends") or []:
            trend_id = str(trend.get("id") or "").strip()
            if trend_id:
                presence[trend_id] += 1
    return dict(presence)
