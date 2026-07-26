"""LIVE-BAND gauntlet: our agent vs the ACTUAL 600-900 ladder population (2026-07-12 census).

Built from ALL 327 of our own ladder games across 7 submissions (intel/
live_band_census_2026-07-12.md; raw mining in intel/episodes_raw/al_najafi_all/).
Every roster row is an EXACT 60-card list we faced live (hash-verified); weights are the
live faced shares (within-class split by chosen-list faced counts, renormalized over the
loaded roster — the pool covers ~96% of faced games). Rows marked "existing" reuse the
~/gauntlet opponents whose decklists hash-match live lists (their pilots ARE the public
notebooks the band actually submits — e.g. kojimar_baseline == the 646d954b Lucario list
faced 18x); "new" rows are generic-pilot builds under ~/gauntlet_band/ (errorType=0).

This replaces band_combine.py's BAND_WEIGHT proxy (which put 0 weight on kyogre/hops/
ionos/ogerpon = ~11% of the real band, over-weighted the mirror, and used the wrong
archaludon/crustle lists).

Run in WSL (Ubuntu-24.04):
  PYTHONPATH=$HOME/ptcg-work ~/ptcg-venv/bin/python ~/ptcg-work/band_gauntlet.py <mode>
Modes:
  probe [games]              quick smoke over the whole roster (default 4)
  run   [games] [seed0]      full run + LIVE-BAND-WEIGHTED WR (default 80 / 12345)
  one   <name> [games] [seed0]
Env: PTCG_OUR_DIR (agent under test), PTCG_B1..B6 (patch flags) as usual.
Flags: --crn / --no-crn (see gauntlet.py; DEFAULT ON = paired engine RNG via
crn_shim.so, --no-crn/PTCG_CRN=0 reproduces the old unpaired instrument). Two arms
run with the same seed0 share battle worlds game-for-game; pool the two logs with
agent/tools/crn_pool.py for per-row paired deltas + McNemar p-values.
Prints BANDROW,<name>,<seed0>,<us>,<tot>,...,<outcomes> CSV lines for pooling
across seeds (trailing field = per-game W/L/D string, the CRN pairing key).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gauntlet as G

HOME = os.path.expanduser("~")
G.GDIR = HOME + "/gauntlet_band"

# (dir under ~/gauntlet_band, class, live weight, deck_key, live faced n, live our W-L)
# 2026-07-14 v11 POOL RE-BASELINE (intel/nightly_2026-07-13.md THE-calibration-bug):
# weights re-based on the Jul-13 ACTIVE-PAIR faced mix (v7r+v10, n=111: lucario 27.0%,
# crustle 13.5% at 4-11, alakazam 13.5%, starmie 10.8% at 4-8, dragapult 9.0%, grimm
# 6.3%, archaludon 5.4%, hops 4.5%). Five FULL-AGENT rows added (frozen v10 submission
# build as the pilot, built by make_fullagent_opp.py -- the generic pilot was the
# instrument lie: crustle_live read 96.7% local vs 26.7% live for the class):
#   self_mirror          our own list under our own frozen v10 build (strongest tuned
#                        mirror available; live 656c2d64 vs the active pair went 1-2)
#   mirror_wall_fdedde79 the 19-basic-Grass pure-wall grinder (0-3 Jul-13; 3-7 all-time;
#                        Crustle attacks every turn, wins the prize race vs our passivity)
#   mirror_tusk_ee52c8d3 Crustle + Great Tusk Land-Collapse MILL (1-2 Jul-13; both
#                        while-AHEAD-on-prizes deckouts ep-85701444/85760550 are this list)
#   mirror_216305d7      Waitress/Cook wall variant (0-1, ep-85761039)
#   starmie_blitz        5fd8867e under the v10 build (same list as starmie_live's
#                        generic pilot -> direct pilot-strength contrast; live starmie
#                        blitz kills t4-13 before the wall sets)
# majkel/comfey keep their FORWARD weights (hammer-tech = 22.2% of top player-games
# and spreading down). Coverage sums to .963 (renormalized at aggregation).
ROSTER = [
    # 2026-07-14 v12 weight fix (intel/agent_v12_results.md sec.0): the Jul-13
    # re-baseline rescaled the lucario FAMILY total to 27.0% but the internal
    # kiyotah:kojimar SPLIT was set to a clean 2:1 (0.180/0.090) that matches
    # nothing on record. The only measured internal ratio is the live faced count
    # in this same row (n=31 vs n=18, i.e. 31:18 = 1.722:1, live_band_census_
    # 2026-07-12.md:102). Corrected: 0.270 * 31/49 = 0.171, 0.270 * 18/49 = 0.099
    # (sum unchanged at 0.270 -> total band coverage 0.963 is unaffected; every
    # other row's weight is unchanged). Applied identically to BOTH A/B arms.
    ("kiyotah_lucario",   "lucario",    0.171, "1d6b56d28084e9f2", 31, "12-19"),
    ("kojimar_baseline",  "lucario",    0.099, "646d954bc4d15376", 18, "2-16"),
    ("alakazam_live",     "alakazam",   0.045, "2e3679ef01161534", 14, "8-6"),
    ("wmh_alakazam",      "alakazam",   0.025, "7314e005fdd76cb4", 10, "4-6"),
    ("ryota_alakazam",    "alakazam",   0.020, "381d496636f709db",  8, "5-3"),
    ("budew_crustle",     "crustle",    0.015, "656c2d64bc4711ef",  9, "7-2"),
    ("crustle_live",      "crustle",    0.010, "fdedde790abf667e",  7, "3-4"),
    ("self_mirror",          "crustle", 0.035, "656c2d64bc4711ef",  3, "1-2"),
    ("mirror_wall_fdedde79", "crustle", 0.030, "fdedde790abf667e", 10, "3-7"),
    ("mirror_tusk_ee52c8d3", "crustle", 0.030, "ee52c8d39f149632",  5, "2-3"),
    ("mirror_216305d7",      "crustle", 0.015, "216305d7b2cf4dea",  1, "0-1"),
    ("kiyotah_dragapult", "dragapult",  0.090, "daefc773f03a8f08", 16, "7-9"),
    ("starmie_live",      "starmie",    0.053, "5fd8867e6fdffae1", 17, "8-9"),
    ("starmie_blitz",     "starmie",    0.055, "5fd8867e6fdffae1",  6, "1-5"),
    ("archaludon_live",   "archaludon", 0.040, "e4a8fd85629f5487", 10, "2-8"),
    ("masami_archaludon", "archaludon", 0.014, "b2777e9097ea4f91",  3, "2-1"),
    ("kyogre_live",       "kyogre_box", 0.018, "27518b3dbceb9314",  9, "7-2"),
    ("hops_snorlax",      "hops",       0.045, "8e7dd94a09adae7b",  8, "5-3"),
    ("wmh_grimmsnarl",    "grimmsnarl", 0.063, "da68e3242c16b2d1",  6, "2-4"),
    ("wmh_garchomp",      "cynthia",    0.009, "19c78850973d0711",  6, "2-4"),
    ("wmh_bellibolt",     "ionos_box",  0.009, "e2b81366589b54e1",  6, "1-5"),
    ("ogerpon_live",      "ogerpon",    0.005, "91092d119d94ab5d",  1, "0-1"),
    ("majkel_hammer_alakazam", "alakazam",       0.045, "cdf6763b7d7eff2a", 3, "3-0"),
    ("comfey_hammer_denial",   "denial_brew",    0.012, "c5051a0bbd69c1ce", 1, "0-1"),
    ("rocket_spidops",         "rocket_spidops", 0.010, "a002a5db532f0de5", 0, "0-0"),
]
WEIGHT = {name: w for name, _a, w, _k, _n, _wl in ROSTER}
NAMES = [(name, arch) for name, arch, _w, _k, _n, _wl in ROSTER]


def run(N, seed0):
    print(G.HEADER)
    print("-" * 96)
    results = {}
    import time
    for name, arch in NAMES:
        d = G.GDIR + "/" + name
        if not os.path.isdir(d) or not os.path.exists(d + "/deck.csv"):
            print("%-20s %-11s  (missing dir/deck -> skipped)" % (name, arch))
            continue
        t0 = time.perf_counter()
        r = G.play(name, N, seed0)
        r["arch"] = arch
        results[name] = r
        print(G.fmt_row(name, arch, r), " [%.0fs]" % (time.perf_counter() - t0), flush=True)
        if r.get("err") and r.get("tot", 0) == 0:
            print("    -> " + str(r["err"]).replace("\n", "\n       ")[:400])
        # trailing field = per-game outcome string (CRN pairing; crn_pool.py McNemar)
        print("BANDROW,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s" % (
            name, seed0, r["us"], r["tot"], r["draw"], r["crashes"], r["illegal"],
            r["timeouts"], r["wf"], r["nf"], r["ws"], r["ns"],
            r.get("cap", 0), r.get("capw", 0), r.get("outcomes", "")), flush=True)

    num = den = 0.0
    swf = snf = sws = sns = 0
    print("-" * 96)
    print("live-band weight contributions:")
    for name, arch in NAMES:
        r = results.get(name)
        if not r or r.get("tot", 0) == 0:
            continue
        w = WEIGHT[name]
        num += w * r["wr"]
        den += w
        swf += r["wf"]; snf += r["nf"]; sws += r["ws"]; sns += r["ns"]
        print("  %-20s cls=%-11s w=%.3f  wr=%.1f%%" % (name, arch, w, 100 * r["wr"]))
    if den > 0:
        print("-" * 96)
        print("LIVE-BAND-WEIGHTED WR (renormalized, coverage %.1f%%) = %.2f%%"
              % (100 * den, 100 * num / den))
        if snf and sns:
            print("pooled seat split: 1st %.1f%% (%d)  2nd %.1f%% (%d)"
                  % (100.0 * swf / snf, snf, 100.0 * sws / sns, sns))
    return results


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "probe":
        g = int(sys.argv[2]) if len(sys.argv) > 2 else 4
        run(g, 12345)
    elif mode == "run":
        g = int(sys.argv[2]) if len(sys.argv) > 2 else 80
        s = int(sys.argv[3]) if len(sys.argv) > 3 else 12345
        run(g, s)
    elif mode == "one":
        name = sys.argv[2]
        g = int(sys.argv[3]) if len(sys.argv) > 3 else 80
        s = int(sys.argv[4]) if len(sys.argv) > 4 else 12345
        print(G.HEADER)
        r = G.play(name, g, s)
        print(G.fmt_row(name, dict(NAMES).get(name, "?"), r))
        print("BANDROW,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s" % (
            name, s, r["us"], r["tot"], r["draw"], r["crashes"], r["illegal"],
            r["timeouts"], r["wf"], r["nf"], r["ws"], r["ns"],
            r.get("cap", 0), r.get("capw", 0), r.get("outcomes", "")))
        if G.CRN_HASH:
            for i, h in enumerate(r.get("ghashes", [])):
                print("GAMEHASH,%s,%d,%d,%s" % (name, s, i, h))
        if r.get("err"):
            print(r["err"])
