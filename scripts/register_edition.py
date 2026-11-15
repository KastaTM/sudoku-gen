"""Register an approved edition (schema-v2 manifest + the submitted interior PDF)."""

import argparse
import json
from pathlib import Path

from sudoku_gen.publication import register_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("edition_id")
    parser.add_argument(
        "--interior",
        type=Path,
        help="uploaded interior PDF (default: interior.pdf beside the manifest)",
    )
    parser.add_argument("--registry", type=Path, default=Path("catalog/editions.jsonl"))
    args = parser.parse_args()
    interior = args.interior or args.manifest.with_name("interior.pdf")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    registry = register_manifest(
        args.registry, manifest, args.edition_id, interior.read_bytes()
    )
    print(f"Registered {args.edition_id}; registry has {len(registry.editions)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
