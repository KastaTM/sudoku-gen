# Sudoku Gen — Core context for agents

Minimal briefing for any agent or sub-agent. Load this file first; open the
linked documents only when the task needs them. Authority order: promoter's
current instructions, then repository facts, then `docs/DECISIONS.md`, then
everything else.

## What this is
A deterministic Sudoku engine plus an editorial pipeline that produces a
print-ready book: `interior.pdf`, `cover.pdf`, `manifest.json`,
`quality-report.json`. The business hypothesis is selling printed Sudoku
books on Amazon KDP, first in `es-ES`. Nothing has been published or sold.

## Baseline and state
- Baseline of record: tag `v0.2.0` (ADR-0001). `main` has moved with H2b/WP0
  (docs, governance, CI).
- Current milestone: SGEN-H3 (pilot edition with foundational i18n). Detail
  and work packages: `docs/ROADMAP.md`.
- Python 3.12+, `uv`, runtime deps ReportLab and pypdf only.

## Non-negotiable rules
- Never weaken uniqueness, difficulty matching or deduplication to reach a
  target. A bounded generation failure is a valid outcome.
- Randomness only through an explicit seeded `random.Random`.
- A change in the reference PDF hashes (`docs/DECISIONS.md`, ADR-0001) is a
  behavior change and must be explained in the pull request.
- Do not add hard-coded editorial text to renderers
  (`tests/test_editorial_literals.py` enforces it).
- Local preflight does not certify KDP acceptance.
- A gate that did not run is NOT VERIFIED, never PASS. CI is the only
  environment whose results count.

## Decisions in force (details: `docs/DECISIONS.md`)
Pilot is `es-ES`, one progression volume, KDP paperback 6 × 9 in B/W without
bleed. Puzzles are exclusive per SKU. Imprint/author is pending (D-007).
Agents work on branches with pull requests and may merge when CI is green.

## Needs explicit promoter approval
Publishing, spending, public prices, advertising, creating accounts,
production deployments, and any change to difficulty or uniqueness policy
that affects existing editions.

## Quality gates (run in CI)
```sh
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov --cov-report=term-missing
```

## Where things are
| Need | Location |
| --- | --- |
| Full engineering contract | `AGENTS.md` |
| Roadmap and work packages | `docs/ROADMAP.md` |
| Decisions and risks | `docs/DECISIONS.md`, `docs/RISK_REGISTER.md` |
| Pre-sale checklist | `docs/RELEASE_CHECKLIST.md` |
| Pipeline entry point | `src/sudoku_gen/publication/pipeline.py` |
| Reference example | `scripts/create_phase_2_11_publication.py` |

## Model tiers for delegated work (ADR-0004)
Mechanical checks (gates, grep, log summaries, formatting): small model.
Scoped implementation, tests, drafts: mid-tier model (default).
Architecture decisions and independent review of critical pull requests:
top-tier model, in a fresh context that did not write the change.
