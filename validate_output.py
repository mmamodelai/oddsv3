#!/usr/bin/env python3
import csv
import json
from collections import defaultdict

CSV_PATH = 'OddsMarketCombo.csv'
JSON_PATH = 'OddsMarketCombo.json'

def main():
    rows = list(csv.reader(open(CSV_PATH, encoding='utf-8')))
    if not rows:
        print('CSV empty')
        return
    hdr = rows[0]
    data = [dict(zip(hdr, r)) for r in rows[1:]]

    # columns
    try:
        col_source = hdr.index('Source')
    except ValueError:
        print('Missing Source column')
        return
    book_idx = list(range(col_source + 1, len(hdr)))

    # Duplicates by (Event, Fighter)
    seen_pairs = set()
    dups = 0
    for d in data:
        k = (d.get('Event',''), d.get('Fighter',''))
        if k in seen_pairs:
            dups += 1
        else:
            seen_pairs.add(k)
    print('dups_by_event_fighter =', dups)

    # Cross-event bleed
    fighter_to_event = {}
    cross = []
    for d in data:
        f = d.get('Fighter','')
        e = d.get('Event','')
        if f in fighter_to_event and fighter_to_event[f] != e:
            cross.append((f, fighter_to_event[f], e))
        else:
            fighter_to_event[f] = e
    print('cross_event_bleed =', len(cross))

    # Per-event counts and odds coverage
    event_to_rows = defaultdict(list)
    for d in data:
        event_to_rows[d.get('Event','')].append(d)
    events = sorted(event_to_rows.keys())
    print('events_total =', len(events))
    for e in events:
        erows = event_to_rows[e]
        with_odds = 0
        for d in erows:
            if any(d.get(hdr[i], '').strip() for i in book_idx):
                with_odds += 1
        print(f'event: {e} | fighters: {len(erows)} | with_odds: {with_odds}')

    # JSON sanity
    try:
        j = json.load(open(JSON_PATH, encoding='utf-8'))
        print('json_total_events =', j.get('total_events'))
        print('json_total_fighters =', j.get('total_fighters'))
    except Exception as e:
        print('json read error:', e)

if __name__ == '__main__':
    main()


