from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis.evidence_scoring import upgrade_snapshot_to_v2  # noqa: E402
from src.storage import load_snapshot, save_snapshot  # noqa: E402


def main() -> int:
    path = ROOT / "data" / "latest_snapshot.json"
    snapshot = load_snapshot(path)
    if not snapshot:
        raise SystemExit(f"No readable snapshot at {path}")
    upgraded = upgrade_snapshot_to_v2(snapshot)
    save_snapshot(upgraded, path, archive=False)
    print(
        f"Migrated {len(upgraded.get('trends') or [])} trends to "
        f"methodology {upgraded.get('methodology_version')}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
