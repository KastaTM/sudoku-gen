"""Register an approved edition (from its schema-v2 manifest) in the catalogue."""

import argparse
import json
from pathlib import Path

from sudoku_gen.publication import append_edition, record_from_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("edition_id")
    parser.add_argument("--registry", type=Path, default=Path("catalog/editions.jsonl"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    record = record_from_manifest(manifest, args.edition_id)
    registry = append_edition(args.registry, record)
    print(f"Registered {record.edition_id}; registry has {len(registry.editions)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
