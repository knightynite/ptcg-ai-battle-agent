"""Per-patch sentinel A/B screen (agent v3 protocol, intel/agent_v3_playbook.md sec.3).

Runs the 4 pillar opponents (2x Alakazam regression guards + tuned Crustle target +
Grimmsnarl attrition check) for one config. The patch flags PTCG_P0..P8 are read from
the environment by the agent at import time, so run ONE PROCESS PER CONFIG:

  PYTHONPATH=$HOME/ptcg-work PTCG_P0=0 ... PTCG_P8=0 \
      ~/ptcg-venv/bin/python ~/ptcg-work/ab_v3.py <label> [N=60] [seed=12345]
"""
import sys

import gauntlet as G

OPPS = ["ryota_alakazam", "wmh_alakazam", "souta_crustle", "wmh_grimmsnarl"]


def main():
    label = sys.argv[1]
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 12345
    out = []
    tc = ti = tt = 0
    p99 = 0.0
    for name in OPPS:
        r = G.play(name, N, seed)
        tc += r["crashes"]; ti += r["illegal"]; tt += r["timeouts"]
        p99 = max(p99, r.get("p99", 0))
        out.append("%s %d/%d (%.1f%%)" % (name, r["us"], r["tot"], 100 * r["wr"]))
        print("ABROW,%s,%s,%d,%d,%d,%d,%d,%d,%.2f" % (
            label, name, seed, r["us"], r["tot"], r["crashes"], r["illegal"],
            r["timeouts"], r.get("p99", 0)), flush=True)
    print("AB[%s] seed=%d N=%d :: %s :: safety c/i/t=%d/%d/%d p99max=%.1fms"
          % (label, seed, N, " | ".join(out), tc, ti, tt, p99), flush=True)


if __name__ == "__main__":
    main()
