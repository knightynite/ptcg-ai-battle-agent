"""Pilotability-bakeoff aggregation for ONE deck (already swapped into ~/agent_v0/deck.csv).

Runs the 15-opponent meta gauntlet (see gauntlet.py) over >=3 seeds, pools games per
opponent (N = games*seeds), and reports pooled WR + Wilson LB, per-seed + averaged
meta-weighted WR, the Alakazam/Crustle pillars, and 0/0/0 safety totals. Used by the
pilotability bakeoff (intel/pilotability_bakeoff_2026-07-11.md) to measure OUR pilot's
meta-weighted winrate on each candidate deck under an identical harness.

Run in WSL (deck.csv must be swapped BEFORE launch so main.py derives the right profile):
  PYTHONPATH=$HOME/ptcg-work ~/ptcg-venv/bin/python bakeoff.py <label> 120 12345 23456 34567
"""
import sys
import statistics
import gauntlet as G


def main():
    label = sys.argv[1]
    N = int(sys.argv[2])
    seeds = [int(s) for s in sys.argv[3:]] or [12345]

    pool = {}          # name -> [us, tot, draw, crashes, illegal, timeouts, arch]
    per_seed_meta = []
    for s in seeds:
        by_arch = {}
        res = {}
        for name, arch in G.ROSTER:
            r = G.play(name, N, s)
            res[name] = r
            by_arch.setdefault(arch, []).append(name)
            p = pool.setdefault(name, [0, 0, 0, 0, 0, 0, arch])
            p[0] += r["us"]; p[1] += r["tot"]; p[2] += r["draw"]
            p[3] += r["crashes"]; p[4] += r["illegal"]; p[5] += r["timeouts"]
            # machine-readable row (combined across parallel single-seed runs)
            print("CSVROW,%s,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%.2f,%.1f,%.1f" % (
                label, name, s, r["us"], r["tot"], r["draw"], r["crashes"],
                r["illegal"], r["timeouts"], r.get("wf", 0), r.get("nf", 0),
                r.get("ws", 0), r.get("ns", 0), r.get("p99", 0),
                r.get("medw", 0), r.get("medl", 0)), flush=True)
        num = den = 0.0
        for name, arch in G.ROSTER:
            w = G.ARCH_WEIGHT.get(arch, 0.0) / len(by_arch[arch])
            num += w * res[name]["wr"]; den += w
        per_seed_meta.append(num / den if den else 0.0)

    print("############ DECK: %s   (N=%d/opp/seed x %d seeds = %d/opp) ############"
          % (label, N, len(seeds), N * len(seeds)))
    print("%-20s %-11s %5s %7s %8s %4s %4s %4s"
          % ("opponent", "arch", "n", "WR", "WilsonLB", "crs", "ill", "to"))
    tc = ti = tt = 0
    for name, arch in G.ROSTER:
        us, tot, draw, crs, ill, to, a = pool[name]
        wr = us / tot if tot else 0.0
        lb = G.wilson_lb(us, tot)
        tc += crs; ti += ill; tt += to
        print("%-20s %-11s %5d %6.1f%% %7.1f%% %4d %4d %4d"
              % (name, arch, tot, 100 * wr, 100 * lb, crs, ill, to))

    by_arch = {}
    for name, arch in G.ROSTER:
        by_arch.setdefault(arch, []).append(name)
    num = den = 0.0
    for name, arch in G.ROSTER:
        us, tot, draw, crs, ill, to, a = pool[name]
        wr = us / tot if tot else 0.0
        w = G.ARCH_WEIGHT.get(arch, 0.0) / len(by_arch[arch])
        num += w * wr; den += w
    meta_pooled = num / den if den else 0.0

    def pillar(names):
        us = tot = 0
        for nm in names:
            us += pool[nm][0]; tot += pool[nm][1]
        return (us / tot if tot else 0.0), G.wilson_lb(us, tot), tot

    alz = pillar(["ryota_alakazam", "wmh_alakazam"])
    cru_t = pillar(["souta_crustle"])
    cru_all = pillar(["souta_crustle", "budew_crustle"])

    print("-" * 72)
    print("META-WEIGHTED (pooled) = %.1f%%   per-seed: %s   avg=%.1f%%  spread=%.1f"
          % (100 * meta_pooled, ", ".join("%.1f" % (100 * m) for m in per_seed_meta),
             100 * statistics.mean(per_seed_meta),
             100 * (max(per_seed_meta) - min(per_seed_meta))))
    print("PILLAR Alakazam(x2)   = %.1f%%  WilsonLB=%.1f%%  (n=%d)" % (100*alz[0], 100*alz[1], alz[2]))
    print("PILLAR Crustle tuned  = %.1f%%  WilsonLB=%.1f%%  (souta n=%d)" % (100*cru_t[0], 100*cru_t[1], cru_t[2]))
    print("PILLAR Crustle all    = %.1f%%  WilsonLB=%.1f%%  (souta+budew n=%d)" % (100*cru_all[0], 100*cru_all[1], cru_all[2]))
    print("SAFETY totals: crashes=%d illegal=%d timeouts=%d  (over %d games)"
          % (tc, ti, tt, sum(pool[n][1] for n, _ in G.ROSTER)))


if __name__ == "__main__":
    main()
