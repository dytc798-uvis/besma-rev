from __future__ import annotations

import argparse
from collections import Counter
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.document_explorer.routes import _scan_document_file_entries  # noqa: E402
from app.modules.document_explorer.search_index import refresh_document_index  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    entries = _scan_document_file_entries()
    result = refresh_document_index(
        ((item.relative_path, path) for item, path in entries),
        force=args.force,
    )
    status_counts = Counter(
        str(item.get("status") or "unknown")
        for item in result["items"].values()
    )
    extension_counts = Counter(
        Path(relative_path).suffix.lower() or "(none)"
        for relative_path in result["items"]
    )
    print(
        json.dumps(
            {
                **{
                    key: value
                    for key, value in result.items()
                    if key != "items"
                },
                "status_counts": dict(sorted(status_counts.items())),
                "extension_counts": dict(sorted(extension_counts.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
