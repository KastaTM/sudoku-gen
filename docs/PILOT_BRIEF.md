# Pilot edition brief — Sudoku Gen, Spanish market (WP2)

Status: PROPOSED. Decisions marked **Promoter** are open.

## Product

A black-and-white paperback of Sudoku puzzles in Spanish for Amazon.es,
produced by the deterministic pipeline (reproducible PDFs, manifest v2,
registered in `catalog/editions.jsonl` once approved).

| Field | Proposal | Basis |
| --- | --- | --- |
| Locale | `es-ES` (Fácil, Medio, Difícil, Experto) | `ES_ES` in code |
| Interior | Puzzles then solutions, contents page, instructions | existing pipeline |
| Length | About 120 pages | assumption A1 in `UNIT_ECONOMICS.md` |
| Trim | Standard KDP size, to confirm (6x9 vs 8.5x11 for large print) | **Promoter** |
| List price | Test 9.99 EUR (first 60% rate) | model only, **Promoter** |
| Imprint and author name | Not defined | **Promoter** (D-007) |
| Uniqueness | No puzzle shared with another edition (D-006), up to digit relabeling | D-008 pending |

## Market evidence

- CONFIRMED: KDP economics (see `UNIT_ECONOMICS.md`).
- NOT VERIFIED: competitor titles, prices, rankings, reviews and keywords on
  Amazon.es. The research agent was blocked on a self-built URL and the
  searches done returned insufficient evidence. No claim about demand or
  competition is made here.
- Needed: a manual look at Amazon.es results for "sudoku" (promoter or an
  approved browser session) to record 10 comparable titles: price, pages,
  size, review count.

## Risks to settle before publishing

1. KDP AI-content disclosure: puzzles are algorithmic, but cover and text
   are authored with AI assistance; the exact disclosure wording is
   **Promoter**.
2. ISBN: free KDP ISBN vs own ISBN. **Promoter**.
3. Tax status and VAT handling for royalties. **Promoter**.
4. Cover: needs KDP Cover Calculator and Print Previewer, run by the promoter
   (account action).
5. Native-language review of all editorial text before release.
6. Hash of the new interior on Windows is NOT VERIFIED (CI is Linux).

## Next steps

1. Promoter answers the **Promoter** items above.
2. Record competitor table (see Market evidence).
3. Build the pilot with the registry loaded; publication-qa runs the release
   checklist; promoter uploads and approves price and publication.
