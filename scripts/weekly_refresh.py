from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.config import load_settings  # noqa: E402
from src.pipeline import refresh_snapshot  # noqa: E402


def main() -> int:
    settings = load_settings()
    snapshot = refresh_snapshot(settings, use_llm=True, persist=True)
    meta = snapshot.get("meta", {})
    summary = {
        "generated_at": meta.get("generated_at"),
        "mode": meta.get("mode"),
        "source_status": meta.get("source_status"),
        "counts": meta.get("raw_counts"),
        "warnings": len(meta.get("warnings", [])),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
