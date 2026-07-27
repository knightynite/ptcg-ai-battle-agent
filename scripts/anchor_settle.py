#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
anchor_settle.py -- ANCHOR-SETTLE pre-registration estimator (Proposal 1,
`intel/novel_lever_hunt_2026-07-17.md` SS4.1; spec detail in
`intel/endgame_policy_2026-07-16.md` SS6.3).

Computes `base_settle`: the opponent-rating-adjusted MLE settle rating of our CURRENT
active submission, over a trailing 14-day window, from COMMITTED data only. This is not
a new estimator -- it re-runs, verbatim, the profile-likelihood MLE machinery that
already produced the "MLE settle 850 [794,906]" figure quoted throughout the campaign
(`intel/nightly_2026-07-15.md`, `intel/bronze_reframe_2026-07-15.md`,
`report/numbers.json` entry `v11_mle_settle`). That machinery lives at:

    intel/episodes_raw/al_najafi_all/calibrate.py   (mle(), lines 13-40 -- first version)
    intel/episodes_raw/al_najafi_all/nightly_0715.py (mle(), lines 30-52 -- the exact run
                                                        that produced 850 [794,906] for v11)

`mle()` below is a byte-for-byte port of nightly_0715.py's function (same scan range
200-1400 step 2, same profile-likelihood-drop-of-1.92 CI, same logistic-324 link). It is
reused, not reinvented, per the pre-registration brief's explicit instruction.

Logistic-324 link (`intel/rating_system_model.md` SS2, "Scale s = 324 MLE"):
    E(win | T, opp) = 1 / (1 + 10 ** (-(T - opp) / 324))
which is the same model underlying the closed-form shortcut quoted elsewhere in the repo
(`intel/rating_system_model.md` SS5, `intel/bronze_reframe_2026-07-15.md` footnote):
    settle = anchor + 324 * log10(p / (1 - p))
That closed-form is the special case of this same MLE when every opponent's rating is
collapsed to one fixed "anchor" point; the per-game MLE below does NOT make that
simplification -- it fits T directly against each game's actual (recorded) opponent
rating, which is the "opponent-rating-adjusted" part of the brief's definition. When the
opponent pool is roughly homogeneous, the two are checked against each other below
(`--verbose`) purely as a sanity cross-check, never as the estimator itself.

DATA SOURCES (committed only):
  - intel/episodes_raw/al_najafi_all/our_games_all.csv
        Per-game log: version, create timestamp, result, opp_rating (recorded at fetch
        time from the leaderboard/episode metadata), status flags. This file lives under
        intel/episodes_raw/, which carries a blanket `*` .gitignore; it is force-added to
        git alongside this script and the pre-registration doc (the same "episodes_raw
        precedent" already used for `intel/episodes_raw/clock_precheck_0717.py`,
        `intel/novel_lever_hunt_2026-07-17.md` SS3.2) so the estimator is reproducible
        from `git log` alone, not from an ambient local file.
  - intel/lb_history/our_rating_history.csv
        Committed team-level snapshot history (rank/score/submission_count per read).
        Used for the "latest snapshot" legacy anchor (847.5) and to auto-detect the
        estimator's data-cutoff timestamp (`--asof`, default = its last row).
  - intel/lb_history/cutoffs_history.csv
        Committed field-cutoff history (top1/10/25/50/100). NOT used as an MLE input
        (no per-game join needed -- opp_rating already lives in our_games_all.csv); kept
        as an optional field-context cross-check only (`--verbose`).
  - intel/lb_history/*publicleaderboard*.csv (raw per-snapshot dumps) are DELIBERATELY
        NOT used. Repo .gitignore explicitly excludes them ("large per-snapshot
        leaderboard CSVs (keep only cutoffs_history.csv)") -- they are local-only,
        non-committed, and would break "committed data only" reproducibility. The
        per-game opponent rating this script needs is already embedded in
        our_games_all.csv at fetch time, which is exactly the source the original
        nightly_0715.py MLE run used -- no separate leaderboard join exists in the
        method being reused, so none is invented here.

Windows-side only. No WSL. No Kaggle calls. Does not touch agent/ or submit/. Writes only
under intel/ (JSON + CSV, never binaries).

Run:
    python scripts/anchor_settle.py
    python scripts/anchor_settle.py --version v11 --window-days 14 --reads 5 --verbose
"""
import sys
import os
import csv
import json
import math
import argparse
import datetime as dt

sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GAMES_CSV = os.path.join(REPO_ROOT, "intel", "episodes_raw", "al_najafi_all", "our_games_all.csv")
DEFAULT_RATING_HISTORY_CSV = os.path.join(REPO_ROOT, "intel", "lb_history", "our_rating_history.csv")
DEFAULT_CUTOFFS_CSV = os.path.join(REPO_ROOT, "intel", "lb_history", "cutoffs_history.csv")
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "intel")

SCALE = 324.0          # rating_system_model.md SS2, fitted MLE scale (Elo would be 400)
CALIB_2DAY_DRIFT_SD = 60.0   # endgame_policy_2026-07-16.md SS3, calibration target (all tau)
FINAL_PRELOCK_READ_UTC = "2026-08-13T01:52:00Z"   # pre-registered terminal read of the schedule

# CURRENT active submission for base_settle-of-record purposes. Per submit/SUBMISSIONS.md
# (log entry #12, "Active pair from 03:40: v12 (54670983) + v11 (54668059, 930 climbing).")
# BOTH v11 and v12 are technically active (2-slot FIFO), but v11 is the campaign's
# documented "active best submission" (report/numbers.json `anchor_of_record`.method:
# "anchor = MLE settle of the active best submission"; v12 is a held lucario-experiment
# copy under live A/B, "v11 star untouched" per submit/SUBMISSIONS.md). base_settle uses
# v11 by default; v12 is always also computed and printed for transparency. When a new
# version becomes the documented "active best" (a future v13+), re-point this default and
# note the change in the next scheduled read's commit message.
CURRENT_BEST_VERSION = "v11"


def parse_ts(s):
    """Parse an ISO-ish timestamp (with or without trailing Z, with or without
    fractional seconds) as a naive UTC datetime."""
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1]
    return dt.datetime.fromisoformat(s)


def fmt_ts(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_games(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["opp_rating"] = float(r["opp_rating"])
        r["our_before"] = float(r["our_before"])
        r["our_after"] = float(r["our_after"])
        r["_create_dt"] = parse_ts(r["create"])
    return rows


def load_rating_history(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["score"] = float(r["score"])
        r["rank"] = int(r["rank"])
        r["total_teams"] = int(r["total_teams"])
        r["submission_count"] = int(r["submission_count"])
        r["_snapshot_dt"] = parse_ts(r["snapshot_utc"])
    rows.sort(key=lambda r: r["_snapshot_dt"])
    return rows


# ----------------------------------------------------------------------------------------
# MLE machinery -- verbatim port of intel/episodes_raw/al_najafi_all/nightly_0715.py
# mle() (lines 30-52), itself descended from calibrate.py's mle() (lines 13-40). Do not
# "improve" this function under this task's explicit instruction not to invent a new
# estimator; any change to the method belongs in a new pre-registration, not a silent
# edit here.
# ----------------------------------------------------------------------------------------
def mle(games):
    """games: list of (opp_rating: float, win: bool). Returns (T, lo, hi) -- point MLE and
    95% profile-likelihood CI (log-likelihood drop of 1.92), or (None, None, None) if empty."""
    if not games:
        return None, None, None

    def ll(T):
        s = 0.0
        for opp, win in games:
            e = 1.0 / (1.0 + 10 ** (-(T - opp) / SCALE))
            e = min(max(e, 1e-6), 1 - 1e-6)
            s += math.log(e) if win else math.log(1 - e)
        return s

    best_T, best_L = None, -1e18
    for T in range(200, 1400, 2):
        L = ll(T)
        if L > best_L:
            best_T, best_L = T, L
    lo = hi = best_T
    T = best_T
    while T > 200 and ll(T) > best_L - 1.92:
        lo = T
        T -= 2
    T = best_T
    while T < 1400 and ll(T) > best_L - 1.92:
        hi = T
        T += 2
    return best_T, lo, hi


def logit10(p):
    return math.log10(p / (1 - p))


# ----------------------------------------------------------------------------------------
# base_settle: opponent-rating-adjusted MLE over the CURRENT active submission's games in
# a trailing `window_days` window ending at `asof`.
# ----------------------------------------------------------------------------------------
def compute_base_settle(games, version, asof, window_days):
    window_start = asof - dt.timedelta(days=window_days)
    rows = [r for r in games
            if r["ver"] == version and r["result"] in ("W", "L")
            and window_start <= r["_create_dt"] <= asof]
    pair = [(r["opp_rating"], r["result"] == "W") for r in rows]
    T, lo, hi = mle(pair)
    n = len(pair)
    w = sum(1 for _, win in pair if win)
    opp_mean = (sum(o for o, _ in pair) / n) if n else None
    return {
        "version": version,
        "asof": fmt_ts(asof),
        "window_days": window_days,
        "window_start": fmt_ts(window_start),
        "n_games": n,
        "w": w,
        "l": n - w,
        "opp_mean_rating": round(opp_mean, 1) if opp_mean is not None else None,
        "mle_settle": T,
        "ci95": [lo, hi],
    }


# ----------------------------------------------------------------------------------------
# Legacy anchor reproduction (frozen, historical check -- always v11, always the exact
# historical cut each anchor was originally quoted from; independent of --version).
# ----------------------------------------------------------------------------------------
def reproduce_legacy_anchors(games, rating_history):
    out = {}

    # --- g100 = 838: v11's in-game trajectory rating at game 100 (nightly_2026-07-15.md
    # "rating @g" row: g80=862 g90=852 g100=838). Sort v11 games by create time, take the
    # our_after value at the 100th game.
    v11 = sorted([r for r in games if r["ver"] == "v11"], key=lambda r: r["_create_dt"])
    g100 = v11[99]["our_after"] if len(v11) >= 100 else None
    out["g100_838"] = {
        "claimed": 838,
        "recomputed": round(g100, 1) if g100 is not None else None,
        "n_v11_games": len(v11),
        "reproduces": (g100 is not None and round(g100) == 838),
        "note": "our_after of the 100th v11 game (create-time sorted); nightly doc rounds 837.9 -> 838.",
    }

    # --- 847.5 = latest snapshot (as of the 2026-07-16T01:52:48Z read, our_rating_history.csv)
    target_snap = None
    for r in rating_history:
        if r["snapshot_utc"] == "2026-07-16T01:52:48":
            target_snap = r
            break
    out["snapshot_847_5"] = {
        "claimed": 847.5,
        "recomputed": target_snap["score"] if target_snap else None,
        "reproduces": (target_snap is not None and target_snap["score"] == 847.5),
        "note": "our_rating_history.csv row for snapshot_utc=2026-07-16T01:52:48 (rank 687, 5082 teams, 2 active subs).",
    }

    # --- 850 = MLE settle, v11, full valid record (both the 101-game all-valid set and
    # the 100-game set excluding the one default-win-against-INVALID-opponent row, per
    # adversarial_audit_2026-07-15.md's "one v11 default win against an invalid
    # opponent is excluded above").
    v11_all_pairs = [(r["opp_rating"], r["result"] == "W") for r in v11 if r["result"] in ("W", "L")]
    T_101, lo_101, hi_101 = mle(v11_all_pairs)

    v11_excl_invalid = [r for r in v11 if not (r["status_us"] == "DONE" and r["status_opp"] == "INVALID")]
    v11_100_pairs = [(r["opp_rating"], r["result"] == "W") for r in v11_excl_invalid if r["result"] in ("W", "L")]
    T_100, lo_100, hi_100 = mle(v11_100_pairs)
    opp_mean_100 = sum(o for o, _ in v11_100_pairs) / len(v11_100_pairs) if v11_100_pairs else None

    out["mle_850"] = {
        "claimed": 850,
        "claimed_ci": [794, 906],
        "recomputed_n101": {"T": T_101, "ci95": [lo_101, hi_101], "n": len(v11_all_pairs)},
        "recomputed_n100_excl_invalid_opp": {"T": T_100, "ci95": [lo_100, hi_100], "n": len(v11_100_pairs)},
        "reproduces": (T_101 == 850 and [lo_101, hi_101] == [794, 906]),
        "note": "Exact match on the 101-game set (T=850 [794,906]); the 100-game excl.-invalid set gives the same T/CI (one extra near-anchor win barely moves the fit).",
    }

    # --- 858: endgame_policy_2026-07-16.md SS2.2/SS4 labels this "858 (mild-optimism
    # MLE-ish)" / "modest-optimism MLE-ish upper case", i.e. treats it as a THIRD,
    # independent MLE point estimate alongside 838 and 850. It does not reproduce as an
    # MLE settle value under any subset tested above (both give T=850). It DOES
    # reproduce exactly as the OPPONENT MEAN rating of v11's 100-game
    # excl.-invalid-opponent set (adversarial_audit_2026-07-15.md's table column
    # "opponent mean rating" = 858 on the same 48-52 W-L row) -- a different quantity
    # entirely, conflated with a settle estimate downstream. FLAGGED.
    out["anchor_858"] = {
        "claimed_as": "858 (mild-optimism MLE) -- endgame_policy_2026-07-16.md SS2.2/SS4",
        "reproduces_as_mle": False,
        "mle_recomputed_on_same_subset": T_100,
        "reproduces_as_opponent_mean": (opp_mean_100 is not None and round(opp_mean_100, 1) == 858.1),
        "opponent_mean_recomputed": round(opp_mean_100, 1) if opp_mean_100 is not None else None,
        "verdict": "PROVENANCE FAILS as claimed. 858 is v11's OPPONENT MEAN rating over the "
                   "100-game excl.-invalid subset (adversarial_audit_2026-07-15.md table, "
                   "column 'opponent mean rating'), not a second MLE settle point estimate. "
                   "endgame_policy_2026-07-16.md mislabels/conflates it as 'mild-optimism MLE'. "
                   "The actual MLE on that identical subset is 850 [794,906] -- same as the "
                   "101-game set, not 858. This is exactly the class of provenance failure "
                   "SS5 of the pre-registration brief asked this pre-check to catch.",
    }
    return out


# ----------------------------------------------------------------------------------------
# Predicted band for the next N scheduled 01:52 UTC snapshot reads.
#
# Reads are pinned to the REAL calendar 01:52 UTC cadence (`intel/endgame_policy_2026-07-16.md`
# "the existing 01:52 UTC daily snapshot cadence"), not to "asof + i*24h" -- those only
# coincide if the estimator happens to be committed exactly at asof. Any cadence point that
# falls between `asof` (the last actually-observed data point) and `now` (when this
# pre-registration is committed) has already occurred but was never captured (a real
# data-collection gap, e.g. no WSL access that day) -- it is reported as MISSED, not folded
# into the 5-read validation set, and NOT silently treated as a hit or a miss.
# ----------------------------------------------------------------------------------------
CADENCE_TIME_UTC = dt.time(1, 52, 0)


def next_cadence_read(after_dt, cadence_time=CADENCE_TIME_UTC):
    candidate = dt.datetime.combine(after_dt.date(), cadence_time)
    if candidate <= after_dt:
        candidate += dt.timedelta(days=1)
    return candidate


def predicted_band(center, asof, now, n_reads):
    """sd(gap_days) = CALIB_2DAY_DRIFT_SD * sqrt(gap_days / 2) -- diffusive (Brownian-at-
    short-lag) scaling of the single calibrated 2-day net-drift sd target
    (endgame_policy_2026-07-16.md SS3; same OU-short-lag approximation used throughout
    scripts/endgame_simulator.py). gap_days is measured from `asof` (the estimator's data
    cutoff), which is the honest "how stale is our estimate" measure -- NOT from `now`.
    Band = center +/- sd(gap) (a +/-1sd band, per the pre-registration brief's literal
    'estimator +/- ... drift sd' spec -- NOT a wider +/-1.96sd interval; see the pre-reg
    doc for the caveat this implies)."""
    missed = []
    probe = next_cadence_read(asof)
    first_future = next_cadence_read(now)
    while probe < first_future:
        missed.append(fmt_ts(probe))
        probe += dt.timedelta(days=1)

    reads = []
    for i in range(n_reads):
        read_dt = first_future + dt.timedelta(days=i)
        gap_days = (read_dt - asof).total_seconds() / 86400.0
        sd = CALIB_2DAY_DRIFT_SD * math.sqrt(gap_days / 2.0)
        reads.append({
            "read_n": i + 1,
            "read_utc": fmt_ts(read_dt),
            "gap_days": round(gap_days, 3),
            "sd": round(sd, 1),
            "band_lo": round(center - sd, 1),
            "band_hi": round(center + sd, 1),
        })
    return reads, missed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games-csv", default=DEFAULT_GAMES_CSV)
    ap.add_argument("--rating-history-csv", default=DEFAULT_RATING_HISTORY_CSV)
    ap.add_argument("--cutoffs-csv", default=DEFAULT_CUTOFFS_CSV)
    ap.add_argument("--version", default=CURRENT_BEST_VERSION, help="current active submission for base_settle (default: v11)")
    ap.add_argument("--window-days", type=int, default=14)
    ap.add_argument("--asof", default=None, help="ISO8601 UTC timestamp; default = last row of rating-history-csv")
    ap.add_argument("--now", default=None, help="ISO8601 UTC timestamp for 'when is this being committed'; default = actual current UTC time")
    ap.add_argument("--reads", type=int, default=5)
    ap.add_argument("--out", default=DEFAULT_OUT_DIR)
    ap.add_argument("--tag", default=None, help="filename tag for output artifacts (default: today's date)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    games = load_games(args.games_csv)
    rating_history = load_rating_history(args.rating_history_csv)

    if args.asof:
        asof = parse_ts(args.asof)
    else:
        asof = rating_history[-1]["_snapshot_dt"]

    now = parse_ts(args.now) if args.now else dt.datetime.utcnow()

    print("=" * 100)
    print("ANCHOR-SETTLE base_settle estimator")
    print("games_csv:", args.games_csv)
    print("rating_history_csv:", args.rating_history_csv)
    print("asof (data cutoff):", fmt_ts(asof))
    print("now (pre-registration commit time):", fmt_ts(now))
    print("window_days:", args.window_days)
    print()

    result_best = compute_base_settle(games, args.version, asof, args.window_days)
    print("base_settle (%s, current active best submission):" % args.version)
    print("  n=%(n_games)d  W-L %(w)d-%(l)d  opp_mean=%(opp_mean_rating)s" % result_best)
    print("  MLE settle T=%s  95%% CI %s" % (result_best["mle_settle"], result_best["ci95"]))

    other_versions = sorted(set(r["ver"] for r in games
                                 if r["ver"] != args.version and r["_create_dt"] >= asof - dt.timedelta(days=args.window_days)))
    cross_checks = {}
    for v in other_versions:
        cross_checks[v] = compute_base_settle(games, v, asof, args.window_days)
        if args.verbose:
            print("  [cross-check other active sub %s] n=%d MLE=%s CI=%s" % (
                v, cross_checks[v]["n_games"], cross_checks[v]["mle_settle"], cross_checks[v]["ci95"]))

    print()
    print("=" * 100)
    print("Legacy anchor reproduction (offline pre-check, SS5 of the pre-reg brief)")
    legacy = reproduce_legacy_anchors(games, rating_history)
    for key, v in legacy.items():
        print("  %-16s reproduces=%s" % (key, v.get("reproduces", v.get("reproduces_as_mle"))))
        if args.verbose:
            print("    ", json.dumps(v, indent=2))

    print()
    print("=" * 100)
    center = result_best["mle_settle"]
    band, missed = predicted_band(center, asof, now, args.reads)
    if missed:
        print("MISSED cadence read(s) between asof and now (data-collection gap, not fetched -- excluded from the 5-read validation set):")
        for m in missed:
            print("  MISSED:", m)
    print("Predicted band for the next %d scheduled 01:52 UTC reads (center=%s):" % (args.reads, center))
    for b in band:
        print("  read#%d  %s  gap=%.2fd  sd=%.1f  band=[%.1f, %.1f]" % (
            b["read_n"], b["read_utc"], b["gap_days"], b["sd"], b["band_lo"], b["band_hi"]))
    print()
    print("Final pre-lock read (schedule terminus, not part of the 5-read validation band): %s" % FINAL_PRELOCK_READ_UTC)

    tag = args.tag or dt.datetime.utcnow().strftime("%Y-%m-%d")
    out_json_path = os.path.join(args.out, "anchor_settle_result_%s.json" % tag)
    out_csv_path = os.path.join(args.out, "anchor_settle_band_%s.csv" % tag)

    payload = {
        "generated_utc": fmt_ts(dt.datetime.utcnow()),
        "asof": fmt_ts(asof),
        "now": fmt_ts(now),
        "window_days": args.window_days,
        "current_best_version": args.version,
        "base_settle": result_best,
        "cross_check_other_active_subs": cross_checks,
        "legacy_anchor_reproduction": legacy,
        "missed_reads": missed,
        "predicted_band": band,
        "final_prelock_read_utc": FINAL_PRELOCK_READ_UTC,
        "calibration_2day_drift_sd": CALIB_2DAY_DRIFT_SD,
        "method_citation": {
            "mle_source": "intel/episodes_raw/al_najafi_all/nightly_0715.py (mle(), lines 30-52); "
                           "originally intel/episodes_raw/al_najafi_all/calibrate.py (mle(), lines 13-40)",
            "closed_form_source": "intel/rating_system_model.md SS5 (settle = anchor + 324*log10(p/(1-p)))",
            "drift_sd_source": "intel/endgame_policy_2026-07-16.md SS3 (2-day net drift sd calibration target = 60)",
        },
    }
    os.makedirs(args.out, exist_ok=True)
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    with open(out_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["read_n", "read_utc", "gap_days", "sd", "band_lo", "band_hi"])
        w.writeheader()
        for b in band:
            w.writerow(b)

    print()
    print("Wrote:", out_json_path)
    print("Wrote:", out_csv_path)


if __name__ == "__main__":
    main()
