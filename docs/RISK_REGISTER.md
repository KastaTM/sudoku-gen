# Sudoku Gen — Risk register

Last updated: 2026-11-14. Probability and impact are initial qualitative
ratings (H/M/L), not calibrated estimates. Owners review this file at the
close of every milestone.

| ID | Risk | P | I | Owner | Evidence (2026-11-14) | Mitigation / next action | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R01 | Trace-based difficulty does not match readers' perceived difficulty | H | H | Product | Policy is an explicit weight table, not calibrated (`difficulty.py`) | Reader panel of 5–10 people on the pilot; version the policy; never re-rate published editions | Open |
| R02 | Duplicate puzzles across volumes or languages | H | H | Technology | Deduplication is in-memory per job only | Registry (`catalog/editions.jsonl`) and cross-edition check in `run_publication` done in H3/WP1c (seed reuse rejected, conflicting sections regenerated). Residual: the check applies only when a job carries the registry, and nothing is registered until the first edition is approved | Mitigated |
| R03 | Local preflight passes but KDP previewer or print fails | M | H | Editorial | Preflight is local; KDP tools never run | Gate: Print Previewer + Cover Calculator + author copy before H5 | Open |
| R04 | Hard/Expert generation consumes too many attempts | M | M | Technology | Hard ≈ 31 attempts/puzzle (4.4 s), Expert ≈ 19 attempts (6.6 s, 26 clues) with RANDOM_RETRY; GUIDED_CARVING 8–18× slower in wall time | Formal benchmark per level/clue target before fixing the pilot composition; never relax controls | Open |
| R05 | Fonts, glyphs or layout fail in French or German | H | H | Expansion | Only Spanish tested with Bitstream Vera; text hard-coded | Foundational i18n in H3; FR/DE test books with glyph suite in H4 | Open |
| R06 | Insufficient demand / undifferentiated catalogue | H | H | Product + Growth | No market research exists | Product brief with niche and value proposition; pilot run as an experiment | Open |
| R07 | Margins eroded by printing, taxes, price | H | H | Revenue/Finance | No economic model exists | Unit economics with dated official sources before any price | Open |
| R08 | KDP requirement or rights non-compliance | M | H | Operations | 6×9 profile implemented from known rules; currency not re-checked; Vera license bundled | Re-read current KDP rules in H3; imprint legal checklist | Open |
| R09 | Dependence on a single channel | M | M | Revenue | Only KDP considered | Accepted for the pilot; revisit in H6 | Accepted |
| R10 | Agents working on divergent baselines or criteria | H | H | Orchestrator | No CI, no branches, `AGENTS.md` obsolete at baseline | H2b: CI + updated `AGENTS.md` + task contracts with SHA | Mitigating (H2b) |
| R11 | Documentation misguides agents | H | H | Technology | Five contradictions between docs and code at baseline | H2b documentation repair pull request | Mitigating (H2b) |
| R12 | Unit tests mistaken for real-world validation | M | H | Orchestrator | — | Mandatory evidence labels; edition DoD requires previewer and printed copy | Mitigating |
| R13 | Automation without return | M | M | Orchestrator + Finance | No budget defined beyond D-005 | Per-phase budget; pilot limits | Open |
| R14 | Published edition cannot be reproduced exactly | H | H | Technology | Manifest v1 lacks engine version, commit, dependencies, font, fingerprints | Manifest v2 done in H3/WP1b (engine version, git SHA, dependencies, font hash, fingerprints, locale); reference hashes in `DECISIONS.md`; residual: puzzles not yet covered by the cross-edition registry (WP1c) | Mitigated |
| R15 | Mixed-language text in a book (`Easy` label in a Spanish book) | H (occurs now) | H | Editorial + Technology | `page_render.py` uses `Difficulty.value.title()` | Resolved in H3/WP1a by `BookLocale`; guarded by `tests/test_book_locale.py` and `tests/test_editorial_literals.py` | Closed |
| R16 | Front matter and cover below commercial visual standard | H | M | Editorial | Visual inspection of the development book | Editorial design for the pilot; compare with 5 competitors of the niche | Open |
| R17 | Agent execution environment lacks PyPI / KDP access | H | M | Orchestrator | `uv sync --locked` blocked in both cloud and device shells on 2026-11-14 | CI (GitHub Actions) is the quality-gate environment; KDP steps are operated by the promoter | Mitigating (H2b) |
| R18 | Push access from the agent session to GitHub refused | M | M | Promoter + Orchestrator | GitHub App for Claude was not installed on 2026-11-14 13:58; installed by the promoter the same day, push and PR #1 succeeded | Keep the app installed; if pushes fail again, prepare branches locally and ask the promoter | Closed |
