#!/usr/bin/env python3
"""Drift guard for report/numbers.json.

Loads report/numbers.json, re-derives every entry that is mechanically
computable from the newest intel/lb_history/*.csv snapshot (our_rank,
our_rating, n_teams, bronze_bar, silver_bar, top100_cutoff, majkel_rating),
and prints PASS/DRIFT per entry (old value from numbers.json vs newly
computed value from the latest snapshot).

Hand-curated entries (v11_mle_settle, v11_g100_rating, anchor_of_record,
read_schedule_endgame, p_bronze_static, band_v11, crn_vrf_range,
seat_gap_corrected, field_median_think_time, our_latest_snapshot_rating) are
NOT re-derivable from the leaderboard CSV alone -- they are reported as
INFO (not re-checked) with a reminder of their source doc.

Usage:
    python scripts/check_numbers.py                # PASS/DRIFT report only
    python scripts/check_numbers.py --refresh       # also updates numbers.json
                                                      # in place for derivable
                                                      # entries + snapshot stamps
"""
import csv
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NUMBERS_PATH = os.path.join(REPO, 'report', 'numbers.json')
LB_DIR = os.path.join(REPO, 'intel', 'lb_history')

# Entries this script can mechanically re-derive from the latest lb_history
# snapshot, and are therefore subject to drift-checking / --refresh.
DERIVABLE = {
    'our_rank', 'our_rating', 'n_teams', 'bronze_bar', 'silver_bar',
    'top100_cutoff', 'majkel_rating', 'our_latest_snapshot_rating',
}

HAND_CURATED_NOTE = {
    'v11_mle_settle': 'intel/nightly_2026-07-15.md (MLE fit, n=101) -- not re-derivable from lb_history alone',
    'v11_g100_rating': 'intel/nightly_2026-07-15.md (in-game trajectory anchor)',
    'anchor_of_record': 'pre-committed per fable_synthesis_2026-07-16.md §4 item 5 -- re-set only at pre-scheduled reads, never by this script',
    'read_schedule_endgame': 'intel/endgame_policy_2026-07-16.md §6.1 -- static plan text',
    'p_bronze_static': 'intel/endgame_policy_2026-07-16.md §6.3 -- Monte-Carlo simulator output',
    'band_v11': 'intel/agent_v11_results.md -- frozen-roster regression index',
    'crn_vrf_range': 'intel/crn_reaudit_2026-07-13.md -- CRN re-audit VRF figures',
    'seat_gap_corrected': 'intel/fable_synthesis_2026-07-16.md §5 item 4 -- composition-corrected seat gap',
    'field_median_think_time': 'intel/execution_forensics_2026-07-16.md -- replay-forensics measurement',
}


def _parse_snapshot_ts(ts):
    """Parse a snapshot timestamp like 2026-07-25T01:52:02 (time separators may
    be ':' or a substitute glyph) into a naive-UTC datetime, or None."""
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2})\D?(\d{2})(?:\D?(\d{2}))?)?', ts)
    if not m:
        return None
    y, mo, d, hh, mm, ss = m.groups()
    return datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0))


def latest_snapshot():
    files = sorted(glob.glob(os.path.join(LB_DIR, 'pokemon-tcg-ai-battle-publicleaderboard-*.csv')))
    if not files:
        raise SystemExit(f"No leaderboard snapshots found in {LB_DIR}")
    f = files[-1]
    rows = list(csv.DictReader(open(f, encoding='utf-8-sig')))
    scores = sorted((float(r['Score']) for r in rows if r.get('Score')), reverse=True)
    n = len(scores)
    ts = os.path.basename(f).split('publicleaderboard-')[-1].replace('.csv', '')
    # Freshness guard: --refresh restamps numbers.json, so refuse to do it from
    # a stale snapshot (>48h) unless --allow-stale is passed explicitly.
    if '--refresh' in sys.argv and '--allow-stale' not in sys.argv:
        snap_dt = _parse_snapshot_ts(ts)
        if snap_dt is None:
            # Fall back to file mtime if the filename timestamp is unparseable.
            snap_dt = datetime.utcfromtimestamp(os.path.getmtime(f))
        age_h = (datetime.now(timezone.utc).replace(tzinfo=None) - snap_dt).total_seconds() / 3600.0
        if age_h > 48:
            raise SystemExit(
                f"REFUSING --refresh: newest snapshot {ts} is {age_h:.0f}h old (>48h). "
                "Re-run daily_monitor.sh or pass --allow-stale.")
    snapshot_utc = ts.replace(':', '-')  # for display; filenames may carry literal ':' or a substitute glyph
    ranked = sorted(rows, key=lambda r: -float(r.get('Score') or 0))
    ours = [(i + 1, float(r['Score'])) for i, r in enumerate(ranked)
            if 'najafi' in (r.get('TeamName') or '').lower()]
    our_rank, our_rating = ours[0] if ours else (float('nan'), float('nan'))
    bronze_rk = round(0.10 * n)
    silver_rk = round(0.05 * n)
    top1 = ranked[0]
    return {
        'file': f,
        'snapshot_utc': ts,
        'n_teams': n,
        'our_rank': our_rank,
        'our_rating': round(our_rating, 1),
        'our_latest_snapshot_rating': round(our_rating, 1),
        'bronze_bar': round(scores[bronze_rk - 1], 1),
        'silver_bar': round(scores[silver_rk - 1], 1),
        'top100_cutoff': round(scores[99], 1) if n >= 100 else float('nan'),
        'majkel_rating': round(float(top1.get('Score') or 0), 1),
    }


def main():
    refresh = '--refresh' in sys.argv

    with open(NUMBERS_PATH, encoding='utf-8') as fh:
        data = json.load(fh)
    entries = data['entries']

    live = latest_snapshot()
    print(f"Latest snapshot: {live['file']}")
    print(f"  n_teams={live['n_teams']}  our_rank={live['our_rank']}  our_rating={live['our_rating']}")
    print()

    any_drift = False
    for name in sorted(entries):
        entry = entries[name]
        if name not in DERIVABLE:
            src = HAND_CURATED_NOTE.get(name, entry.get('source_file', '?'))
            print(f"INFO  {name}: hand-curated, not re-checked (source: {src})")
            continue

        old_val = entry.get('value')
        new_val = live.get(name)
        if new_val is None:
            print(f"SKIP  {name}: no re-derivation rule")
            continue

        if isinstance(old_val, (int, float)) and abs(float(old_val) - float(new_val)) < 1e-9:
            print(f"PASS  {name}: {old_val} (unchanged, snapshot {live['snapshot_utc']})")
        else:
            any_drift = True
            print(f"DRIFT {name}: {old_val} -> {new_val}  (old snapshot {entry.get('snapshot_utc')}, "
                  f"new snapshot {live['snapshot_utc']})")
            if refresh:
                entry['value'] = new_val
                entry['snapshot_utc'] = live['snapshot_utc'].replace('-', ':', 2) if 'T' in live['snapshot_utc'] else live['snapshot_utc']
                entry['source_file'] = os.path.relpath(live['file'], REPO).replace(os.sep, '/')

    if refresh:
        data['generated_utc'] = live['snapshot_utc']
        with open(NUMBERS_PATH, 'w', encoding='utf-8') as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write('\n')
        print()
        print("Refreshed report/numbers.json in place.")

    print()
    if any_drift and not refresh:
        print("Drift detected. Re-run with --refresh to update numbers.json, or update hand-curated entries manually.")
        sys.exit(1)
    else:
        print("No unresolved drift." if not any_drift else "Drift resolved via --refresh.")


if __name__ == '__main__':
    main()
