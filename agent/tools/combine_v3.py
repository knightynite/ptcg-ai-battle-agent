"""Pool CSVROW lines from (parallel, single-seed) bakeoff logs into the v3 report:
per-opponent pooled WR/LB, per-seed + pooled meta-weighted WR, pillars, seat split,
safety totals. Usage:  python combine_v3.py <log> [<log> ...]
"""
import sys
from collections import defaultdict

import gauntlet as G

ARCH = dict(G.ROSTER)


def main():
    pool = defaultdict(lambda: defaultdict(lambda: [0] * 10))  # label -> name -> sums
    seeds = defaultdict(lambda: defaultdict(dict))             # label -> seed -> name -> (us,tot)
    p99 = defaultdict(float)
    for path in sys.argv[1:]:
        for line in open(path):
            if not line.startswith("CSVROW,"):
                continue
            f = line.strip().split(",")
            label, name, seed = f[1], f[2], int(f[3])
            us, tot, draw = int(f[4]), int(f[5]), int(f[6])
            crs, ill, to = int(f[7]), int(f[8]), int(f[9])
            wf, nf, ws, ns = int(f[10]), int(f[11]), int(f[12]), int(f[13])
            p = pool[label][name]
            for i, v in enumerate([us, tot, draw, crs, ill, to, wf, nf, ws, ns]):
                p[i] += v
            seeds[label][seed][name] = (us, tot)
            p99[label] = max(p99[label], float(f[14]))

    for label in sorted(pool):
        P = pool[label]
        print("=" * 100)
        print("CONFIG: %s   (max p99 %.1f ms)" % (label, p99[label]))
        print("%-20s %-11s %5s %7s %8s %4s %4s %4s   %s" %
              ("opponent", "arch", "n", "WR", "WilsonLB", "crs", "ill", "to",
               "1st% / 2nd%"))
        tc = ti = tt = 0
        for name, arch in G.ROSTER:
            if name not in P:
                continue
            us, tot, draw, crs, ill, to, wf, nf, ws, ns = P[name]
            wr = us / tot if tot else 0.0
            tc += crs; ti += ill; tt += to
            f1 = 100.0 * wf / nf if nf else 0.0
            s2 = 100.0 * ws / ns if ns else 0.0
            print("%-20s %-11s %5d %6.1f%% %7.1f%% %4d %4d %4d   %4.0f%%(%d) / %4.0f%%(%d)"
                  % (name, arch, tot, 100 * wr, 100 * G.wilson_lb(us, tot),
                     crs, ill, to, f1, nf, s2, ns))

        by_arch = defaultdict(list)
        for name, arch in G.ROSTER:
            if name in P:
                by_arch[arch].append(name)
        num = den = 0.0
        for name, arch in G.ROSTER:
            if name not in P:
                continue
            us, tot = P[name][0], P[name][1]
            w = G.ARCH_WEIGHT.get(arch, 0.0) / len(by_arch[arch])
            num += w * (us / tot if tot else 0.0)
            den += w
        meta = num / den if den else 0.0

        per_seed = []
        for seed in sorted(seeds[label]):
            sm = seeds[label][seed]
            n2 = d2 = 0.0
            for name, arch in G.ROSTER:
                if name not in sm:
                    continue
                us, tot = sm[name]
                w = G.ARCH_WEIGHT.get(arch, 0.0) / len(by_arch[arch])
                n2 += w * (us / tot if tot else 0.0)
                d2 += w
            per_seed.append((seed, n2 / d2 if d2 else 0.0))

        def pillar(names):
            us = tot = 0
            for nm in names:
                if nm in P:
                    us += P[nm][0]
                    tot += P[nm][1]
            return (us / tot if tot else 0.0), G.wilson_lb(us, tot), tot

        alz = pillar(["ryota_alakazam", "wmh_alakazam"])
        crt = pillar(["souta_crustle"])
        cra = pillar(["souta_crustle", "budew_crustle"])
        WF = sum(P[n][6] for n in P); NF = sum(P[n][7] for n in P)
        WS = sum(P[n][8] for n in P); NS = sum(P[n][9] for n in P)
        print("-" * 100)
        print("META-WEIGHTED (pooled) = %.2f%%   per-seed: %s" %
              (100 * meta, "  ".join("%d:%.1f%%" % (s, 100 * m) for s, m in per_seed)))
        print("PILLAR Alakazam(x2)  = %.1f%%  LB=%.1f%% (n=%d)" % (100 * alz[0], 100 * alz[1], alz[2]))
        print("PILLAR Crustle tuned = %.1f%%  LB=%.1f%% (n=%d)" % (100 * crt[0], 100 * crt[1], crt[2]))
        print("PILLAR Crustle all   = %.1f%%  LB=%.1f%% (n=%d)" % (100 * cra[0], 100 * cra[1], cra[2]))
        print("SEAT: first %.1f%% (n=%d)   second %.1f%% (n=%d)" %
              (100.0 * WF / NF if NF else 0, NF, 100.0 * WS / NS if NS else 0, NS))
        print("SAFETY: crashes=%d illegal=%d timeouts=%d over %d games" %
              (tc, ti, tt, sum(P[n][1] for n in P)))


if __name__ == "__main__":
    main()
