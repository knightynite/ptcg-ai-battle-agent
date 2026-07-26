"""Discipline-rule mechanism instrument, 2026-07-16 (intel/discipline_rule_2026-07-16.md
step 3c). Runs one (opponent row, N, seed0) band-gauntlet unit exactly like
band_gauntlet.py's "one" mode (same BANDROW output line, so crn_pool.py works
unmodified), then ALSO reads agent/scoring.py's module-level discipline diag counters
(_DISCIPLINE_DIAG) directly off the loaded pilot module and prints a MECHROW line before
resetting them for the next unit -- same convention as the Lever-3 supply-rule gate used
(supply_rule_2026-07-16.md sec. mechanism instrument: gauntlet.py's reset_our() bypasses
pilot._update_clock's new-game-boundary stderr hook, but the module-level counters still
accumulate correctly across the whole row, so they're read directly here rather than
relying on the DISCIPLINEDIAG stderr line).

MECHROW,<row>,<seed0>,<n>,fires=<f>,evolves_promoted=<e>,attaches_promoted=<a>,
plays_demoted=<p>

Usage (WSL): PYTHONPATH=$HOME/ptcg-work PTCG_OUR_DIR=$HOME/v11agentB \
  <the 40-flag v11 ledger, PTCG_DISCIPLINE_RULE=0|1> \
  ~/ptcg-venv/bin/python discipline_instrument.py <row> <N> <seed0>
"""
import os
import sys

sys.path.insert(0, os.path.join(os.environ.get("HOME", os.path.expanduser("~")), "ptcg-work"))
import gauntlet as G  # noqa: E402 -- reuses OUR_DIR load, CRN shim, play()

G.GDIR = os.path.join(os.environ.get("HOME", os.path.expanduser("~")), "gauntlet_band")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    name = sys.argv[1]
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 12345

    SC = G._pilot.SC
    for k in SC._DISCIPLINE_DIAG:
        SC._DISCIPLINE_DIAG[k] = 0

    print(G.HEADER)
    r = G.play(name, N, seed0)
    print(G.fmt_row(name, "?", r))
    print("BANDROW,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s" % (
        name, seed0, r["us"], r["tot"], r["draw"], r["crashes"], r["illegal"],
        r["timeouts"], r["wf"], r["nf"], r["ws"], r["ns"],
        r.get("cap", 0), r.get("capw", 0), r.get("outcomes", "")), flush=True)

    d = SC.discipline_diag_summary()
    print("MECHROW,%s,%d,%d,fires=%d,evolves_promoted=%d,attaches_promoted=%d,"
          "plays_demoted=%d" % (
              name, seed0, r["tot"], d.get("fires", 0), d.get("evolves_promoted", 0),
              d.get("attaches_promoted", 0), d.get("plays_demoted", 0)), flush=True)
    for k in SC._DISCIPLINE_DIAG:
        SC._DISCIPLINE_DIAG[k] = 0

    if r.get("err"):
        print(r["err"])


if __name__ == "__main__":
    main()
