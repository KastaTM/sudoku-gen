# Sudoku Gen — Decision log

Decisions are appended, never rewritten. Superseding a decision adds a
new entry that references the old one. Each entry states who decided,
the status, and what it changes.

| ID | Date | Decision | Decided by | Status |
| --- | --- | --- | --- | --- |
| ADR-0001 | 2026-11-14 | Baseline of record is tag `v0.2.0` = `c05ce0c858ac36e3d2dd35762856301c25cca856`; all task contracts reference it until `main` moves | Orchestrator, confirmed by promoter | Accepted |
| ADR-0002 | 2026-11-14 | Agentic governance: evidence labels, task contracts, branch + PR workflow, CI as the only accepted quality-gate environment, mandatory human approval for irreversible or external actions (see `AGENTS.md` § Governance) | Promoter (intent), Orchestrator (design) | Accepted |
| D-001 | 2026-11-14 | Pilot edition language and market: `es-ES` | Promoter | Accepted |
| D-002 | 2026-11-14 | Pilot audience and promise: one progression volume (Easy → Hard) for adult puzzle fans; revisable after niche research | Promoter (default recommendation accepted tacitly) | Accepted |
| D-003 | 2026-11-14 | Channel and format: Amazon KDP paperback, 6 × 9 in, black and white, white paper, no bleed (the only implemented print profile) | Promoter (default recommendation accepted tacitly) | Accepted |
| D-004 | 2026-11-14 | Agent permissions on the repository: branches + pull requests; **autonomous merge allowed when CI is green**. Publishing, spending, public pricing, advertising, account creation and policy changes still require explicit promoter approval | Promoter | Accepted |
| D-005 | 2026-11-14 | Budget for H3: minimal spend (one author copy; native review by the promoter); no spend without prior notice | Promoter (default recommendation accepted tacitly) | Accepted |
| D-006 | 2026-11-14 | Puzzle reuse policy: puzzles are **exclusive per SKU** across all editions and languages; enforced by the edition registry (H3/WP1) | Promoter | Accepted |
| D-007 | 2026-11-14 | Imprint / author name for cover, copyright and metadata | Promoter | **Pending** — must be resolved before the pilot cover (WP2) |
| ADR-0003 | 2026-11-14 | Delegation model: the Orchestrator publishes a short step brief before each work package and proceeds unless the promoter objects; explicit approval only for the actions listed in D-004; every repeated manual step becomes an automation candidate | Promoter (intent), Orchestrator (design) | Accepted |
| ADR-0004 | 2026-11-14 | Workflow automation: deterministic checks live in CI, tests and hooks, not in agent turns; delegated work is tiered by model (small for mechanical checks, mid-tier by default, top-tier for architecture and independent review); agents load `docs/CONTEXT_CORE.md` instead of the full context document; decision and risk logs live in the repository | Orchestrator, proposed to promoter | Accepted (no objection) |
| ADR-0005 | 2026-11-14 | Editorial text lives in `BookLocale` (`publication/locale.py`); `es-ES` complete, `en-US` test-only; no fallback; the Spanish interior reference hash changes because the difficulty label is now Spanish | Orchestrator (design), promoter (D-001) | Accepted |
| ADR-0006 | 2026-11-15 | Manifest schema v2: reproduction inputs and output hashes are deterministic; build facts live in a separate informational `environment` block that may differ per machine | Orchestrator (design) | Accepted |
| ADR-0007 | 2026-11-15 | Edition registry: append-only JSON Lines file `catalog/editions.jsonl`; a job given a registry rejects a reused seed and regenerates sections with registered puzzles; the development example is never registered | Orchestrator (design), promoter (D-006) | Accepted |

## ADR-0001 — Baseline of record

**Context.** The knowledge-transfer document dated 2026-11-11 named
commit `c05ce0c` as the verified baseline. On 2026-11-14 `main` on GitHub
and the promoter's local clone were both at that commit with no other
branches, stashes or local commits. An annotated tag `v0.2.0` points to
it, while `pyproject.toml` still declared `0.1.0`.

**Decision.** `v0.2.0` / `c05ce0c` is the baseline. The version in
`pyproject.toml` and `uv.lock` is raised to `0.2.0` in H2b with no
functional change.

**Consequences.** Task contracts cite this SHA. Reference PDF hashes of
the phase 2.11 development book at this baseline are
`interior.pdf = 68f65e4a4982e27386c5ca592a3ad3ac27b7273a75a57dba48e3658527a4b1e1`
and
`cover.pdf = d626109e451250d26151405a0d1d2e58e02c8eca197260ee14b189bf03e785f5`
(identical on Windows/Python 3.12 and Linux/Python 3.13).

## ADR-0002 — Agentic governance

**Context.** `AGENTS.md` described a single coding agent working on
phase 1 and forbade PDF/KDP work that the code already implements. The
project moves to an orchestrator plus departmental agents, with the
promoter keeping strategic decisions.

**Decision.** Governance rules live in `AGENTS.md` § Governance for
agents and are binding for every agent. CI is the only environment whose
quality-gate results count as evidence; a gate that did not run is
NOT VERIFIED.

**Consequences.** Pull requests carry evidence in their description.
Documentation, decisions and risks are updated in the same pull request
as the change they describe.

## ADR-0003 — Delegation model

**Context.** The promoter wants to be informed of every step and its
rationale, to be able to object, and otherwise to delegate and automate
as much as possible.

**Decision.** Before each work package the Orchestrator publishes a
step brief (what, why, evidence to be delivered, risk). Absent an
objection, work proceeds. Explicit approval is required only for the
actions listed in D-004. Cover and text proposals are presented once,
with alternatives, before publication.

**Consequences.** Fewer approval round-trips; a complete audit trail in
this file and in pull requests.

## ADR-0004 — Workflow automation and model tiers

**Context.** Quality gates, reference hashes and deduplication are already
deterministic, but running them through agent turns spends tokens and time.
The 14-11-2026 audit found 8 hard-coded editorial literals and no automated
guard against adding more.

**Decision.** (1) Checks that code can perform run in CI, tests or hooks:
`tests/test_editorial_literals.py` (ratchet over renderer literals),
sample-page PNG artifacts in CI, Dependabot for `uv` and GitHub Actions, and
a Claude Code hook that formats edited Python files. (2) Delegated work is
tiered by model: small model for mechanical checks, mid-tier by default, top
tier for architecture and independent review of critical pull requests.
(3) Agents start from `docs/CONTEXT_CORE.md`; the knowledge-transfer document
is historical. (4) Logs of decisions and risks stay in `docs/`, not in the
claude.ai project, to avoid invalidating the prompt cache of every chat.

**Consequences.** `KNOWN_DEBT` in the ratchet test must shrink to empty in
WP1. Skills and agent definitions (`.claude/agents/`) are the next step and
will be proposed separately. Dependabot pull requests follow D-004 (merge on
green CI) except for major version bumps, which the Orchestrator reviews.

**Update (agent definitions).** `.claude/agents/` defines `gates-runner`
(small model), `engineer` and `publication-qa` and `market-researcher`
(mid-tier) and `reviewer` (top tier, read-only). Finance, data, revenue and
growth stay as templates until there are sales data (H5/H6).

## ADR-0005 — BookLocale and new reference hash

**Context.** Eight editorial literals lived in the renderers and the
difficulty label was English in a Spanish book (R15).

**Decision.** All renderer-visible text comes from `BookLocale`. A locale
that lacks any key cannot be built and an unknown code raises; there is no
fallback. `PublicationJob.locale` defaults to `ES_ES` (D-001). `en-US` exists
only to prove the layer works and is not reviewed by a native speaker.

**Consequences.** Behavior change, intentional: the label `Easy` becomes
`Fácil` (and Medium, Hard, Expert become Medio, Difícil, Experto). The
reference hash of the phase 2.11 development book changes:
`interior.pdf = 3f6ae31e6e7b1433d28ef584af77f2a05d6aa1bb1d49c769303cfbd9230c8b64`
(previous: `68f65e4a…27b1`, see ADR-0001). `cover.pdf` is unchanged
(`d626109e…85f5`). The cross-platform check of the new hash is the CI job.

## ADR-0006 — Manifest schema v2

**Context.** Manifest v1 could not identify the engine, commit, dependencies,
font or puzzles of an edition (R14).

**Decision.** `schema_version: 2` adds locale, deduplication mode, print
profile, font identity, per-puzzle fingerprints and an `environment` block.
Everything outside `environment` is an input of reproduction or an output
hash and is deterministic. `environment` is informational and best-effort:
unavailable facts are `null`, never an error. The git SHA comes from
`SUDOKU_GEN_GIT_SHA` when set (then the dirty flag is unknown), otherwise from
`git`; a dirty tree is recorded as `git_dirty: true`.

**Consequences.** `publication_manifest(result, environment=None)` collects the
environment when omitted; tests inject one to stay deterministic. A release
manifest with `git_dirty: true` or `git_sha: null` must not be accepted for
sale. WP1c reuses the fingerprints for the edition registry.

## ADR-0007 — Edition registry

**Context.** D-006 makes puzzles exclusive per SKU across editions and
languages, but deduplication was per job only (R02).

**Decision.** `catalog/editions.jsonl` is an append-only JSON Lines file, one
edition per line: id, title, locale, seed, fingerprint mode, puzzle
fingerprints, interior SHA-256. It is validated on load (duplicate id, seed,
fingerprint or mixed modes are errors). `PublicationJob.registry` defaults to
an empty registry so development runs work; a real edition loads the file with
`load_registry`. Two rules apply: (1) a job whose base seed equals a
registered seed is rejected before generation; (2) a section containing a
registered puzzle is regenerated within the existing budget, and the job fails
when the budget is exhausted. Fingerprints are compared only in one mode; a
registry in another mode than the job is an error.

**Consequences.** Registration is a release step taken from the schema-v2
manifest (`scripts/register_edition.py`) in a pull request, only after the
promoter approves publication. Reusing a seed with a different configuration
is also rejected: pick a new seed. Open: how the pipeline obliges real
editions to pass the registry (a release script) is part of WP2.
