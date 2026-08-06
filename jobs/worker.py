from __future__ import annotations

import argparse
import json
import os
import socket
import sqlite3
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.marketing_ops.config import load_marketing_settings, resolve_database_path
from src.marketing_ops.connectors.base import SyncWindow
from src.marketing_ops.connectors.registry import build_connector_registry
from src.marketing_ops.demo_data import demo_dataset
from src.marketing_ops.reporting import monthly_report_pdf
from src.marketing_ops.security import safe_exception
from src.marketing_ops.signals import detect_business_signals
from src.marketing_ops.store import OperationalStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def claim_next(path: Path, worker_id: str, lease_seconds: int) -> dict[str, Any] | None:
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("begin immediate")
        now = utc_now()
        row = connection.execute(
            """select * from job_queue
               where status in ('Queued','Retry')
                 and (lease_expires_at is null or lease_expires_at < ?)
                 and attempt_count < max_retries
               order by requested_at limit 1""",
            (now,),
        ).fetchone()
        if not row:
            connection.commit()
            return None
        lease = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
        changed = connection.execute(
            """update job_queue set status='Running',started_at=coalesce(started_at,?),
               attempt_count=attempt_count+1,lease_owner=?,lease_expires_at=?
               where id=? and status in ('Queued','Retry')""",
            (now, worker_id, lease, row["id"]),
        ).rowcount
        connection.commit()
        if changed != 1:
            return None
        payload = dict(row)
        payload["payload"] = json.loads(payload.pop("payload_json"))
        return payload
    finally:
        connection.close()


def finish(path: Path, job_id: str, *, result: dict[str, Any] | None = None, error: str = "", retry: bool = False) -> None:
    status = "Retry" if retry else ("Failed" if error else "Completed")
    progress = 0 if retry else (0 if error else 100)
    with sqlite3.connect(path, timeout=15) as connection:
        connection.execute(
            """update job_queue set status=?,completed_at=?,progress_pct=?,error=?,
               result_json=?,lease_owner=null,lease_expires_at=null where id=?""",
            (status, utc_now(), progress, error, json.dumps(result or {}, default=str), job_id),
        )


def handle_job(job: dict[str, Any], root: Path) -> dict[str, Any]:
    job_type = str(job["job_type"])
    payload = job.get("payload") or {}
    if job_type == "detect_fixture_signals":
        signals = detect_business_signals(demo_dataset())
        return {"data_mode": "fixture", "signals_detected": len(signals), "deduplication_keys": [signal.deduplication_key for signal in signals]}
    if job_type == "generate_fixture_report":
        output = root / "data" / "generated" / "HULA_Marketing_Operations_fixture.pdf"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(monthly_report_pdf(demo_dataset(), approved=False, version="Worker fixture"))
        return {"data_mode": "fixture", "output": str(output.relative_to(root)), "approved": False}
    if job_type == "site_crawl":
        raise NotImplementedError("The production crawler worker is not implemented in the first release. The queue request was retained without crawling.")
    if job_type.startswith("sync_"):
        settings = load_marketing_settings()
        registry = build_connector_registry(settings)
        provider = str(payload.get("provider") or "")
        connector = registry.get(provider)
        if connector is None:
            raise ValueError(f"Unknown provider for sync probe: {provider}")
        validation = connector.validate_config()
        if not validation.valid:
            raise RuntimeError(validation.message)
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=6)
        sync = connector.sync(SyncWindow(start, end))
        if not sync.success:
            raise RuntimeError(sync.error or "Read-only provider probe failed.")
        return {
            "provider": provider,
            "mode": "read_only_probe",
            "records_read": len(sync.records),
            "persisted_to_mart": False,
            "warning": "This first-release worker verifies and normalizes reads but does not claim a completed production mart sync.",
            "schema_version": sync.schema_version,
        }
    raise ValueError(f"Unsupported job type: {job_type}")


def run_once(root: Path = ROOT) -> bool:
    settings = load_marketing_settings()
    path = resolve_database_path(settings, root)
    OperationalStore(path)
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    job = claim_next(path, worker_id, lease_seconds=900)
    if job is None:
        return False
    try:
        result = handle_job(job, root)
        finish(path, job["id"], result=result)
    except Exception as exc:
        retry = int(job.get("attempt_count") or 0) + 1 < int(job.get("max_retries") or 5) and not isinstance(exc, NotImplementedError)
        finish(path, job["id"], error=safe_exception(exc), retry=retry)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Process one HULA Marketing Operations local/demo job.")
    parser.add_argument("--once", action="store_true", help="Process at most one job (the only supported first-release mode).")
    parser.parse_args()
    processed = run_once()
    print("processed" if processed else "idle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
