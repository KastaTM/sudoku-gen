# Sudoku Gen — Release checklist (Definition of Done for an edition)

An edition is **not** ready because `interior.pdf` and `cover.pdf` exist.
Every item below must be ticked with linked evidence before the promoter
is asked to approve publication. A check that was not run is
NOT VERIFIED, not passed.

## 1. Mathematical and generation quality

- [ ] `quality-report.json` shows `audit_passed: true` for every batch and
      no preflight or cover issue codes.
- [ ] Every puzzle has exactly one solution and clues consistent with it
      (covered by the batch audit; spot-check three puzzles manually).
- [ ] Requested difficulty matched for every section; no `UNRATED` puzzle.
- [ ] Zero duplicate fingerprints inside the edition **and** against the
      edition registry of all previous editions in every language (the
      job was built with `load_registry` and the manifest's `registry.sha256`
      matches the current `catalog/editions.jsonl`)
      (decision D-006). Registry entry prepared for this edition.
- [ ] Generation parameters (seed, strategy, clue target, symmetry,
      deduplication mode) recorded in the manifest.

## 2. Reproducibility and traceability

- [ ] Manifest `schema_version` ≥ 2 with generator version, git SHA,
      Python and dependency versions, font SHA-256, locale, per-puzzle
      fingerprints, and SHA-256 of both PDFs.
- [ ] Regenerating from the manifest parameters on CI yields identical
      PDF hashes.
- [ ] The exact files submitted are archived with their hashes.

## 3. Editorial text and language

- [ ] All visible text comes from the locale resources; no hard-coded
      literal and no string in another language (automated test).
- [ ] Title, subtitle, author/imprint, copyright, instructions, section
      titles and difficulty labels reviewed by a native speaker of the
      edition's language; reviewer and date recorded.
- [ ] Imprint / author name per decision D-007 (or its successor).

## 4. Visual inspection (human, at print resolution)

- [ ] Title page, copyright page, instructions page, contents page.
- [ ] First and last puzzle page; a page crossing a section boundary.
- [ ] First and last solution page; a partially filled final page.
- [ ] Digit legibility, line weights, margins (recto/verso), page numbers.
- [ ] Cover: front, spine (if ≥ 80 effective pages), back copy, barcode
      area kept clear; spine width matches the final page count.

## 5. Channel validation (Amazon KDP, current rules)

- [ ] Local preflight PASS (`preflight_pdf`) and `validate_cover_pdf` PASS.
- [ ] KDP Print Previewer PASS for the interior (screenshot attached).
- [ ] KDP Cover Calculator template matches the cover dimensions
      (screenshot attached).
- [ ] Author copy ordered and inspected, or an explicit, recorded
      decision by the promoter to skip it.
- [ ] Current KDP content, metadata and trim-size requirements re-read
      on the submission date; differences from the implemented profile
      recorded.

## 6. Commercial and legal

- [ ] Product brief approved (audience, promise, level mix, puzzle count).
- [ ] Unit economics approved: printing cost, royalty, price, break-even,
      with dated sources.
- [ ] Marketplace listing (title, subtitle, description, keywords,
      categories) truthful and in the edition's language.
- [ ] Font and content licenses verified (Bitstream Vera license
      bundled; all text original).
- [ ] Price, territories and ISBN/ASIN choice decided by the promoter.

## 7. Approval and record

- [ ] Promoter's written approval to publish, referencing the manifest
      hash.
- [ ] `docs/DECISIONS.md` entry for the launch; `docs/RISK_REGISTER.md`
      reviewed.
- [ ] Post-publication: live listing checked, published file hashes
      recorded, measurement plan (H6) started.
