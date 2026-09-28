# Public price maintenance

`public-prices.json` is the single approved public price catalog. Generate the search/lot calculator index, part-page price cards, ranges, calculator constants, price-bearing descriptions, and the price tables from it:

```sh
python3 scripts/sync-public-prices.py --write
python3 scripts/sync-public-prices.py
python3 scripts/test-public-prices.py
```

Without `--write`, the command is read-only and exits unsuccessfully if any generated output has drifted. Run it before publishing and during weekly audits. It does not retrieve new prices, advance dates, modify the database, or deploy the site.

## Refresh workflow

1. Read the current authorized Supabase `public_offer` records and supporting dates from `part_market_price`. Use `price_ready`, not merely the presence of a number: the view can return a numeric fallback for a deliberately quote-only override. Never copy buyer identities, bids, credentials or private notes into the public catalog.
2. Compare the proposed public offers with the approved catalog. Preserve approved DDR5 overrides unless new comparison evidence supports changing them. The owner selected the midpoint of SellUsedRAM's main payout index as the DDR5 comparison policy, excluding Memory.net. Use `https://www.sellusedram.com/prices/`, checking the individual row date rather than the whole-page date or older brand pages. Match capacity, generation, speed and module type; do not substitute RDIMM for UDIMM, kits for single modules, or MRDIMM for RDIMM. Do not introduce competitor brand discounts without an owner decision.
3. Update approved `lo`/`hi` and source dates in the catalog. Preserve explicit existing amounts such as $1,251 (approximately the $1,251.50 midpoint) and the $97 UDIMM adjustment rather than silently recalculating or rounding them. Parts without adequate evidence remain `price_ready: false` with null prices. A newly unpriced formerly priced page must be converted to quote-only; the generator refuses to leave a stale number on that page.
4. Set `checked_at` only after checking that part's source. It is distinct from `source_updated_at`: for database offers this is the newest supporting bid record date, not a claim that every bid in the 45-day range has that date; for competitor overrides it is the comparable row's update date. `offer_effective_from` records when the approved override took effect. The catalog-level check date is the latest review date, with per-part dates retained.
5. Generate, inspect the changes, and run the consistency check and tests. Publish only through the separately authorized deployment workflow, including the catalog, generated index and updated HTML together.

## September 28, 2026 review

Read 50 published RAM offers: 41 priced and nine quote-only. Existing approved amounts for all 13 priced DDR5 parts were preserved. The source database returned $91 for M393A4K40CB2-CTD7Y (previous public index: $88) and $66 for HMA82GR7CJR8N-XN (previous part page: $57; index already $66). Supporting price ranges were also synchronized.

SellUsedRAM was checked September 28. Its comparable 16GB DDR5-4800 row is dated August 27; its 16GB DDR5-5600 UDIMM row is dated August 15; the other matched DDR5 override rows are dated September 10. The main index's September 19 date does not mean each row changed on that day.

The public site remains a static, reviewed price publication. It is not a live feed, and the weekly audit does not automatically approve changed buying prices. Database formula/override expiry changes are outside this synchronization change.

## Price list structured data

The generator also writes the price list's structured data (WebPage, Dataset, ItemList of priced parts, and FAQPage) between the `<!-- PRICE-LD:START -->` and `<!-- PRICE-LD:END -->` markers in `ram-price-list.html`, and updates the "last checked" date in its "How current are these prices?" answer. The FAQ structured data is copied from the page's visible FAQ, so edit the visible questions and answers, then regenerate. Don't edit the generated block by hand. A test fails if the block is removed or goes out of step with the catalog.
