"""Per-lever sentinel A/B screen for agent v5 (race-state levers PTCG_R1..R4).

Runs the v5-relevant opponents: the two Alakazam regression guards, the tuned-Crustle
guard, the Grimmsnarl attrition guard (320-HP tank -> the R3 Nebula window fires there
too and must not regress the 87% row), and the two live-band bleeders the levers target
(kiyotah_lucario, masami_archaludon). Flags are read from the environment at import, so
run ONE PROCESS PER CONFIG:

  PYTHONPATH=$HOME/ptcg-work PTCG_R1=0 PTCG_R2=0 PTCG_R3=0 PTCG_R4=0 \
      ~/ptcg-venv/bin/python ~/ptcg-work/ab_v5.py <label> [N=150] [seed=12345]
"""
import sys

import gauntlet as G

OPPS = ["ryota_alakazam", "wmh_alakazam", "souta_crustle", "wmh_grimmsnarl",
        "kiyotah_lucario", "masami_archaludon"]


def main():
    label = sys.argv[1]
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 12345
    out = []
    tc = ti = tt = 0
    p99 = 0.0
    for name in OPPS:
        r = G.play(name, N, seed)
        tc += r["crashes"]; ti += r["illegal"]; tt += r["timeouts"]
        p99 = max(p99, r.get("p99", 0))
        out.append("%s %d/%d (%.1f%%)" % (name, r["us"], r["tot"], 100 * r["wr"]))
        print("ABROW,%s,%s,%d,%d,%d,%d,%d,%d,%.2f,%d,%d,%d,%d" % (
            label, name, seed, r["us"], r["tot"], r["crashes"], r["illegal"],
            r["timeouts"], r.get("p99", 0), r.get("wf", 0), r.get("nf", 0),
            r.get("ws", 0), r.get("ns", 0)), flush=True)
    print("AB[%s] seed=%d N=%d :: %s :: safety c/i/t=%d/%d/%d p99max=%.1fms"
          % (label, seed, N, " | ".join(out), tc, ti, tt, p99), flush=True)


if __name__ == "__main__":
    main()
