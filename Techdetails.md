## LulSec UFC Odds Extraction – Technical Details

This document is the internal handbook for agents working on `OddsMarketCombo`. It captures the architecture, deterministic algorithm, safeguards, debugging workflow, CI, and future enhancements to restore fully live odds across all upcoming UFC events without cross‑event bleed.

### Repository map
- `OddsMarketCombo.py`: Single-file extractor that generates `OddsMarketCombo.csv` and `OddsMarketCombo.json`.
- `MMAFightScraper.py`: Standalone fights indexer; generates `MMAFights.csv` and `MMAFights.json`.
- `MMAFights.csv`: Canonical source of truth for upcoming fight rosters per event. We import this as an authoritative roster + fight order.
- `.github/workflows/odds-extraction.yml`: CI job (Windows runner) that runs extractor and uploads CSV/JSON artifacts.
- `requirements.txt`: Dependencies (requests, bs4, selenium/undetected-chromedriver, lxml, webdriver-manager).

### Data sources (fightodds.io)
- Discover events: `https://fightodds.io/upcoming-mma-events/ufc` (+ generic `/upcoming-mma-events` fallback).
- Per-event pages: `{event_url}` (for JSON-LD and metadata date fallback).
- Event fights (roster + ordering): `{event_url}/fights`.
- Event odds: `{event_url}/odds`.

### Deterministic algorithm
1) Event discovery
   - Parse anchors to `/mma-events/{id}/{slug}/`; store canonical `event_url`, `odds_url`, `event_id`.
   - `event_date`: row-adjacent date → JSON-LD/meta/title fallback → `normalize_event_date_string()` to `YYYY-MM-DD`.
2) Roster authority (from `MMAFights.csv`)
   - `load_fights_index_from_csv()` builds an index by `event_id`:
     - `roster`: list of fighter names found in `MMAFights.csv` for that event.
     - `order_map`: per-fighter `FightOrder` (1 = main, 2 = co-main, etc.), derived from row order per event.
     - `event_date`: propagated date if present.
3) Odds extraction per event
   - Open `{event_url}/odds` in undetected Chrome; validate header token contains event token (e.g., “UFC 319” or event name). If mismatch → skip.
   - Locate an odds table near the event header. If scoped table not found, we do NOT use a global “largest table” fallback (prevents cross-event bleed).
   - Extract sportsbook headers; parse fighter rows.
   - Fuzzy-name match odds rows to roster (`match_name_to_roster()` token overlap with Jaccard ≥ 0.6, subset boost). Only keep matches.
   - Merge odds into base roster entries (every roster fighter appears in CSV even if odds are blank yet). Attach `FightOrder` from `order_map`.
4) Validation & de-duplication
   - Remove duplicates by `(Event, Fighter)`.
   - Cross-event bleed guard: a fighter appears under only one event; conflicting rows are dropped with a log.
   - Output `CSV` and `JSON` with union of sportsbooks as columns.

### CSV schema
`Fighter, Event, EventDate, FightOrder, Source, <sportsbooks…>`
- `EventDate`: `YYYY-MM-DD` when known; else empty.
- `FightOrder`: 1 = main, 2 = co-main, …; 0 for cancelled (if detectable).
- `Source`: always `fightodds.io` for odds; rows still listed even with empty odds (roster authority).

### JSON schema (high-level)
```
{
  extraction_timestamp,
  extraction_run_id,
  total_fighters,
  total_events,
  sportsbooks: [..],
  events: {
    "<EventName>": { event_url, odds_url, event_id, event_date }
  },
  fighters: [
    { fighter, event, event_date, fight_order, source, odds: { <book>: "+155" | "" } }
  ]
}
```

### Current behavior (as of latest run)
- UFC 319 exposes an event-scoped odds table → odds populated for that card.
- Other upcoming event odds pages currently render a global table dominated by UFC 319 names. We do not attach those to other events, preserving correctness.
- CSV therefore contains:
  - UFC 319: roster rows with odds and `FightOrder`.
  - Other events: roster rows with `FightOrder` and blank odds (until event-scoped odds appear).

### Key safeguards (non‑negotiables satisfied)
- Event header token validation: we only trust an odds page if its title/H1 includes the event token.
- Roster filter: only fighters in the event’s roster from `MMAFights.csv` are emitted.
- Fuzzy name matching avoids formatting differences while remaining strict to roster membership.
- Cross-event bleed guard + `(Event, Fighter)` de-dup.
- No “largest table fallback” – prevents accidental attachment from a global odds table.

### Environment/feature flags (planned)
- `REQUIRE_EVENT_TABLE` (default: 1): require a scoped odds table near the event heading.
- `SCAN_GLOBAL_TABLE_WITH_ROSTER` (default: 0): if no scoped table, scan all tables on the event page but attach odds only if fighter matches roster AND event token matches. Accuracy-first; still scoped to the event page.
- `USE_ALT_BOOK_APIS` (default: 0): optional book API fill (DK/FD/MGM) when site tables lag; only attach when pair exactly matches roster and date is plausible. Off by default for safety.

### Logging & debug artifacts
- Per event: `Roster size`, `Fighters kept` (from odds), `Skipped`, and whether a roster was sourced from `MMAFights.csv`.
- Debug prints: page title snippet, sample of odds-table fighters, and sample roster.
- Proposed: when an event has blank odds, dump HTML to `debug_html/{event_id}_{kind}.html` for later inspection (`kind` ∈ {odds,fights}).

### Local run
- Python 3.10+
- Run: `python OddsMarketCombo.py`
- Outputs: `OddsMarketCombo.csv`, `OddsMarketCombo.json`

### Validation snippets (Python one-liners)
- Count duplicate `(Event, Fighter)`:
```python
import csv
rows=list(csv.DictReader(open('OddsMarketCombo.csv',encoding='utf-8')))
seen=set(); dups=0
for r in rows:
    k=(r['Event'], r['Fighter'])
    dups+=1 if k in seen else 0
    seen.add(k)
print('dups:', dups)
```
- Check a specific event’s roster vs odds coverage:
```python
import csv
ev='UFC 319: Du Plessis vs. Chimaev'
rows=[r for r in csv.DictReader(open('OddsMarketCombo.csv',encoding='utf-8')) if r['Event']==ev]
books=[h for h in rows[0].keys() if h not in ['Fighter','Event','EventDate','FightOrder','Source']]
with_odds=[r for r in rows if any(r[b].strip() for b in books)]
print(ev, 'fighters:', len(rows), 'with_odds:', len(with_odds))
```

### Troubleshooting playbook
- Blank odds for an event:
  - Verify event page title/H1 includes event token; if not, site may redirect/mislabel.
  - Confirm `{event_url}/fights` parsed roster names and `order_map`.
  - Inspect saved `odds` HTML (planned) for a scoped table near the heading.
  - If the page shows a global table (UFC 319), leave odds blank by design.
- Name mismatches:
  - Review fuzzy matcher threshold; update MMAFights.csv names if official hyphenation/casing changes.
- Cross-event conflicts:
  - We keep the first event that claims the fighter; later duplicates log and drop. Inspect `MMAFights.csv` for overlaps or scheduling shifts.

### Evasion & reliability
- Undetected Chrome with stealth args, headless in CI.
- Scroll + click expanders; retry/backoff on loads.
- Session headers for HTTP fallback where used.

### CI
- Windows runner, Python 3.11.
- Steps: checkout → pip install → run `OddsMarketCombo.py` → upload artifacts.
- Schedule + manual dispatch supported.

### Roadmap to restore broader live odds (safe)
1) Implement event‑section DOM scoping: anchor at the event heading and search within section siblings for the closest table.
2) Add debug HTML dumps when no scoped table is detected.
3) Optional `SCAN_GLOBAL_TABLE_WITH_ROSTER=1`: if enabled, scan all tables on the event page; attach odds only when the page token matches and names match roster (still accuracy‑first).
4) Optional `USE_ALT_BOOK_APIS=1`: fill from book APIs when the site lags, with strict pair/date checks.
5) Maintain roster base rows so downstream analytics retain full upcoming coverage even before odds publish.

### Contact points in code
- `extract_ufc_events_from_page()` – discovery, date inference.
- `load_fights_index_from_csv()` – MMAFights roster/order index.
- `extract_event_fighters_from_odds()` – header validation, roster merge, odds parsing, fight order attach.
- `match_name_to_roster()` – fuzzy matching guardrail.

For the lulz.


