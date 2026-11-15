# Sudoku Gen — Roadmap

Last updated: 2026-11-14. Baseline: tag `v0.2.0` = `c05ce0c858ac36e3d2dd35762856301c25cca856`.

Evidence labels: **CONFIRMED** (verified with reproducible evidence),
**PROMOTER INTENT**, **PROPOSAL**, **TO VERIFY**, **PENDING DECISION**,
**NOT VERIFIED** (a planned check that did not run).

## Milestones

| Milestone | Owner | Status | Exit criteria |
| --- | --- | --- | --- |
| **H0 — Sudoku engine** (historical phase 1) | Technology | CONFIRMED in code and tests | Unique-solution puzzles, logical solver, trace-based difficulty, seeded batches, fingerprints, audits |
| **H1 — Editorial pipeline** (historical phases 2.1–2.11) | Editorial / Technology | CONFIRMED in code; 28-page development book reproduces byte-for-byte across platforms | Interior + cover PDFs, manifest, quality report, local preflight |
| **H2 — Rebaseline and agentic governance** | Orchestrator | H2a (audit, inventory, risks, contracts) done 2026-11-14 outside the repo; **H2b (this documentation repair + CI) in progress** | CI green on `main`; `AGENTS.md`/`README.md` aligned with 2.11; version 0.2.0; governance docs present; full test suite incl. Hypothesis executed in CI |
| **H3 — Pilot edition with foundational i18n** | Orchestrator (Editorial, Technology, Product, Revenue/Finance) | APPROVED (decision D-004); WP0 and WP1 done, WP2 started | See `SGEN-H3` below |
| **H4 — Structural i18n and reproducible catalogue** | Expansion / Technology | Pending; reduced to what H3 does not cover | FR/DE test books pass preflight and native review; cross-book duplicate query available |
| **H5 — First validated launch** | Editorial / Revenue / Promoter | Pending | Edition published with promoter approval, KDP Print Previewer + Cover Calculator + author copy passed, exact file hashes recorded |
| **H6 — Measurement and learning** | Data / Finance / Growth | Pending | Report with units, net revenue, contribution margin and a signed `scale / iterate / stop` decision within an agreed horizon |
| **H7 — Gradual expansion ES/EN/FR/DE** | Expansion | Pending; conditional on H6 unless the promoter decides otherwise | One new language only with native QA and per-market economics |
| **H8 — Portfolio and channel scaling** | Orchestrator | Future | Only with an approved business case; no web/API/DB without it |

## SGEN-H3 — Pilot edition with foundational i18n

Status: APPROVED for WP0; WP1 and WP2 approved in scope and start
sequentially. Not a goal: publishing, selling, public pricing, ISBN
purchase, FR/DE, UI/API/DB.

### WP0 — Documentation repair and CI (Technology)

- Realign `AGENTS.md` and `README.md` with phase 2.11; bump version to 0.2.0.
- Add `docs/` governance files and `.github/workflows/ci.yml`.
- Acceptance: CI green on the pull request and on `main`; the 12
  Hypothesis property tests executed; coverage percentage recorded as a
  baseline (not a target).
- Evidence (CONFIRMED, CI run 43597837180 on PR #1, 2026-11-14): Ubuntu,
  CPython 3.12.15, uv 0.12.24, `uv sync --locked` OK; ruff format/check,
  mypy strict PASS; **1206 tests passed** (incl. the 12 Hypothesis property
  tests) in 164.65 s; **coverage baseline 87 %** (branch coverage, 2949
  statements, 276 missed); 2.11 reference PDF hashes identical to the
  Windows and Linux runs (third independent environment).

### WP1 — i18n and catalogue foundation (Technology)

Progress: **WP1a (BookLocale) done**; **WP1b (manifest v2) done**; **WP1c
(edition registry) done**. An independent review of WP1a-c (2026-11-15) led to
WP1d, a hardening change: the manifest records every job input and the
registry digest, registration enforces the release checks, and the registry
file is written under a lock. WP1 closes when WP1d is merged.

- Editorial text resource layer (working name `BookLocale`) covering the
  seven hard-coded strings and the difficulty labels; `es-ES` complete,
  `en-US` as a test locale only. Missing keys raise; no silent fallback.
- Manifest `schema_version: 2` with `generator_version`, `git_sha`,
  Python and dependency versions, font SHA-256, locale, and per-puzzle
  fingerprints.
- Persistent edition registry (versioned file) and a mandatory
  cross-edition duplicate check in `run_publication` (decision D-006:
  puzzles are exclusive per SKU, in every language).
- Acceptance: regenerated development book contains no English strings
  (automated test + inspection); two editions with different seeds share
  0 fingerprints and a third with a reused seed is rejected; manifest v2
  validated; hashes reproducible in CI.

### WP2 — Pilot edition and business case (Editorial, Product, Revenue/Finance, Operations)

- `PILOT_BOOK_BRIEF`: audience, promise, `es-ES`, puzzle count, level
  mix, working title, format (decisions D-001..D-003).
- Pilot edition: `interior.pdf`, `cover.pdf`, manifest v2, quality
  report, print-resolution visual inspection report.
- KDP Print Previewer and Cover Calculator passes (operator: promoter).
- `UNIT_ECONOMICS`: printing cost, royalty, proposed price, break-even
  units; conservative/base/optimistic scenarios with dated sources.
- KDP compliance and licensing checklist; formal generation benchmark
  for the chosen composition.
- Acceptance: edition meets the "Edition" Definition of Done in
  `docs/RELEASE_CHECKLIST.md` except the publication approval; native
  linguistic review documented; no unsourced figure in the business case.
- Pending decision D-007 (imprint/author name) must be resolved before
  the pilot cover is produced.

## Known debt carried into H3 (CONFIRMED 2026-11-14)

- Per-puzzle difficulty label prints the English enum value
  (`page_render.py`, `Difficulty.value.title()`) while headers are Spanish.
- Hard-coded editorial strings: `SUDOKUS`, `Sudoku #`, `SOLUCIONES`,
  `Solución #`, `Información`, `Instrucciones`, `Contenido`.
- Manifest v1 lacks engine version, commit, dependency versions, font
  identity, and per-puzzle fingerprints.
- Deduplication is per job only; no registry across editions.
- No barcode is generated on the cover (area reserved only).
- Front matter and cover are functional but visually minimal.

## Generation cost reference (CONFIRMED 2026-11-14, small sample, one machine)

5 puzzles, seed 777, 30 target clues, `max_attempts=300`:

| Difficulty | RANDOM_RETRY | GUIDED_CARVING |
| --- | --- | --- |
| Easy | 6 attempts, 1.0 s | 5 attempts, 17.7 s |
| Medium | 85 attempts, 12.4 s | 27 attempts, 96.8 s |
| Hard | 156 attempts, 22.0 s | not completed within the time box |
| Expert (2 puzzles, 26 clues, `max_attempts=1500`) | 38 attempts, 13.2 s | not measured |

A formal benchmark is part of WP2.

## WP2 progress (2026-11-15)

`docs/PILOT_BRIEF.md` and `docs/UNIT_ECONOMICS.md` drafted (PROPOSED). KDP
economics confirmed from official pages; competitor data NOT VERIFIED; promoter
decisions listed in the brief.
