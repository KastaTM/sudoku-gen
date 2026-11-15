# Edition catalogue

`editions.jsonl` is the append-only registry of editions approved for sale
(decision D-006: puzzles are exclusive per SKU across editions and languages).
One JSON object per line: edition id, title, locale, seed, fingerprint mode,
puzzle fingerprints and interior SHA-256.

- It is empty until the first edition is approved.
- Register an edition only when the promoter approves it for publication,
  from its schema-v2 `manifest.json` and the interior PDF that is uploaded:
  `uv run python scripts/register_edition.py <manifest.json> <edition-id> --interior <interior.pdf>`.
  Registration refuses a manifest with blocking preflight issues, without a
  clean 40-hex git SHA, with a different interior hash, or built against a
  registry other than the current one. Commit the change in a pull request.
- A job that sets `PublicationJob.registry` (see `load_registry`) rejects a
  reused seed and regenerates any section containing a registered puzzle.
- The development example (`scripts/create_phase_2_11_publication.py`) is not
  for sale and is never registered.
- Never edit or delete lines by hand: the loader rejects inconsistent files.
