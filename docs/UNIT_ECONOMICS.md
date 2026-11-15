# Unit economics — pilot edition (Amazon.es, KDP paperback)

Status: PROPOSED (WP2). Prices here are a model, not a decision: public prices
need promoter approval. Date of figures: 2026-11-15.

## Verified inputs (CONFIRMED, KDP official es_ES help pages)

| Item | Value |
| --- | --- |
| Print cost, 24-110 pages, black and white, standard size | 2.05 EUR fixed |
| Print cost, 110-828 pages | 0.75 EUR + 0.012 EUR per page |
| Royalty rate, list price up to 9.98 EUR | 50% |
| Royalty rate, list price 9.99 EUR or more | 60% |
| Expanded distribution | 40% |
| Royalty formula | rate x list price (excluding VAT) - print cost |
| Maximum list price | 250 EUR |
| Minimum list price | print cost / rate |

## Assumptions (explicit, change them to rerun the model)

- A1: 120-page interior, black and white, standard trim: print cost 2.19 EUR
  (0.75 + 0.012 x 120). Page count of the pilot is not fixed.
- A2: Amazon.es only, no expanded distribution.
- A3: The prices below are tested values, not a recommendation. VAT is added
  by KDP on top of the list price (CONFIRMED in the help pages); the rate that
  applies to the book is NOT VERIFIED and does not change the royalty formula.
- A4: No advertising spend in the base case; no ISBN purchase (KDP free ISBN).
- A5: Royalty is before income tax and self-employment charges; the promoter's
  tax status is unknown (NOT VERIFIED).

## Royalty per copy (EUR, computed from the formula above)

| Pages | List price | Print cost | Rate | Royalty |
| --- | --- | --- | --- | --- |
| 100 | 7.99 | 2.05 | 50% | 1.95 |
| 100 | 9.99 | 2.05 | 60% | 3.94 |
| 100 | 11.99 | 2.05 | 60% | 5.14 |
| 120 | 7.99 | 2.19 | 50% | 1.81 |
| 120 | 9.99 | 2.19 | 60% | 3.80 |
| 120 | 11.99 | 2.19 | 60% | 5.00 |
| 120 | 12.99 | 2.19 | 60% | 5.60 |
| 150 | 9.99 | 2.55 | 60% | 3.44 |
| 150 | 11.99 | 2.55 | 60% | 4.64 |

Observations (arithmetic, not forecasts):

- 9.99 EUR is the first price at the 60% rate; 7.99 EUR earns about half as
  much per copy as 9.99 EUR at 120 pages.
- Minimum list price at 120 pages and 60%: 3.65 EUR.
- Copies to earn 100 EUR at 120 pages: about 27 at 9.99 EUR, 20 at 11.99 EUR.
- Each extra page costs 0.012 EUR (0.72 EUR per 60 pages), so page count
  matters less than the 50%/60% threshold.

## Fixed costs of the pilot (to confirm with the promoter)

Time of the promoter (cover review, KDP upload), a native Spanish review of
the editorial text, optional advertising. No software licence cost is known.
Amounts: NOT VERIFIED.

## Not modelled (NOT VERIFIED, needs sales data or a promoter decision)

Units sold, advertising cost per sale, returns, price of competing books (see
`docs/PILOT_BRIEF.md`). Do not read the table as a revenue forecast.

## Sources

KDP help pages for Amazon.es print pricing and royalties, consulted 2026-11-15.
