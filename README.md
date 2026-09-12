# Bronco Deal Tracker

Tracks new-Bronco inventory deals against your buying criteria, until your
target purchase window closes.

**Your criteria** (see `bronco_tracker/config.py` to change any of it):
- New 2024-2026 Ford Bronco, 4-door hardtop
- Trim: Big Bend or Outer Banks preferred; a higher trim (Black Diamond,
  Badlands, etc.) is fine if it's still $40k-$48k
- Colors: black, Marsh Gray, or another dark gray
- Search area: Orange County / LA County / Inland Empire, around zip 92706
- Target buy date: **December 31, 2026** (no purchase before then)
- Trade-in: paid off, $21,000 baseline value, tracked toward the target date
  with a depreciation estimate

## What it does

1. **Tracks listings** in `data/listings.json` — price, trim, color, dealer,
   first/last seen date, and full price history per listing.
2. **Scores deals** (`bronco_tracker/deals.py`) by price vs. same-trim peer
   average, days on market, and any observed price drop. Listings sitting
   21+ days are flagged as stale/negotiable.
3. **Projects your trade-in's value** (`bronco_tracker/trade_in.py`) from
   today to the target date using a simple compounding monthly depreciation
   estimate — a planning number, not an appraisal.
4. **Generates `data/report.md`** — the current best deals, market trends,
   and trade-in projection, regenerated on every update.

## Adding a listing

Whenever you (or the automated sweep, see below) spot a listing:

```bash
python3 -m bronco_tracker.cli add \
  --id "dealer-slug-stocknumber" \
  --dealer "Dealer Name" \
  --location "City, CA" \
  --trim "Big Bend" \
  --doors 4 \
  --color "Marsh Gray" \
  --price 44169 \
  --stock "FB261461" \
  --url "https://..."
```

Running `add` again with the same `--id` updates the existing listing and
appends to its price history if the price changed. Mark a listing gone with:

```bash
python3 -m bronco_tracker.cli remove --id "dealer-slug-stocknumber" --status sold
```

Regenerate the report any time with:

```bash
python3 -m bronco_tracker.cli report
```

## Automated tracking

A scheduled Claude Code Routine runs a periodic sweep: it searches for new
listings matching the criteria above, logs them here, recomputes deal
scores and trends, commits and pushes the update, and sends a push
notification when a standout deal shows up. It checks in again as the
target date approaches and winds itself down shortly after.

**Known limitation:** this environment's network sandbox blocks direct
scraping of dealer and marketplace sites (Cars.com, CarGurus, Ford.com,
individual dealer sites all return `EGRESS_BLOCKED`). The automated sweep
works around this by using web search instead of fetching pages directly,
then parsing whatever structured info search results surface (dealer
listing titles are often already structured, e.g. "New 2026 Ford Bronco
Big Bend 4 Door in Buena Park #FB261461 | Dealer Name"). This is
best-effort — it will miss listings that don't surface well in search, so
keep feeding it anything you personally come across.

## Running tests

```bash
python3 -m unittest discover -s tests
```

No external dependencies — everything is Python standard library.
