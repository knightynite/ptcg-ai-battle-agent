"""One gauntlet row as a standalone job: emits the exact bakeoff.py CSVROW line so
combine_v3.py / band_combine.py aggregate row-sharded runs unchanged. Sharding exists
because the 2026-07-12 WSL service kept crashing mid-batch (Wsl/Service/E_UNEXPECTED):
a whole-batch bakeoff.py loses ~100 min of work per crash, a row job loses ~6.

Usage: PTCG_* flags in env; rowjob.py <label> <opponent> <N> <seed>
"""
import sys

import gauntlet as G


def main():
    label, name = sys.argv[1], sys.argv[2]
    n, seed = int(sys.argv[3]), int(sys.argv[4])
    r = G.play(name, n, seed)
    if r.get("tot", 0) == 0:
        print("ROWJOB ERROR: %s" % r.get("err"))
        sys.exit(1)
    print("CSVROW,%s,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%.2f,%.1f,%.1f" % (
        label, name, seed, r["us"], r["tot"], r["draw"], r["crashes"],
        r["illegal"], r["timeouts"], r.get("wf", 0), r.get("nf", 0),
        r.get("ws", 0), r.get("ns", 0), r.get("p99", 0),
        r.get("medw", 0), r.get("medl", 0)), flush=True)


if __name__ == "__main__":
    main()
