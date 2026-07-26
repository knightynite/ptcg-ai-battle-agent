"""BAND-WEIGHTED aggregation for the v5 gate: pool bakeoff CSVROW logs + mirror_ab
MIRRORROW logs and weight each archetype by OUR LIVE opponent mix in the 700-1000
climb band (intel/live_autopsy_2026-07-11.md, v3's 101 ladder games):

    lucario .21  alakazam .24  starmie(mirror) .12  dragapult .11  archaludon .07
    crustle .06  cynthia .04   -- and the remaining .15 spread to match the live tail:
    grimmsnarl .02  kangaskhan .01  generalist .06  other .06

This is the CLIMB metric (what the ladder actually serves us at 750-1000), computed
next to the standard top-quartile META metric (combine_v3.py). Also prints the pooled
seat split (mirror included) and per-seed band numbers.

Usage: python band_combine.py <bakeoff/mirror log> [...]
"""
import sys
from collections import defaultdict

import gauntlet as G

ARCH = dict(G.ROSTER)

BAND_WEIGHT = {
    "lucario": 0.21, "alakazam": 0.24, "starmie": 0.12, "dragapult": 0.11,
    "archaludon": 0.07, "crustle": 0.06, "cynthia": 0.04,
    "grimmsnarl": 0.02, "kangaskhan": 0.01, "generalist": 0.06, "other": 0.06,
}


def main():
    pool = defaultdict(lambda: defaultdict(lambda: [0] * 10))  # label -> name -> sums
    seeds = defaultdict(lambda: defaultdict(dict))
    for path in sys.argv[1:]:
        for line in open(path):
            if line.startswith("CSVROW,"):
                f = line.strip().split(",")
                label, name, seed = f[1], f[2], int(f[3])
                us, tot, draw = int(f[4]), int(f[5]), int(f[6])
                crs, ill, to = int(f[7]), int(f[8]), int(f[9])
                wf, nf, ws, ns = int(f[10]), int(f[11]), int(f[12]), int(f[13])
            elif line.startswith("MIRRORROW,"):
                f = line.strip().split(",")
                label, seed = f[1], int(f[2])
                us, tot, draw = int(f[3]), int(f[4]), int(f[5])
                crs, ill = int(f[6]) + int(f[8]), int(f[7]) + int(f[9])
                to = 0
                wf, nf, ws, ns = int(f[10]), int(f[11]), int(f[12]), int(f[13])
                name = "mirror_starmie"
            else:
                continue
            p = pool[label][name]
            for i, v in enumerate([us, tot, draw, crs, ill, to, wf, nf, ws, ns]):
                p[i] += v
            pu, pt = seeds[label][seed].get(name, (0, 0))
            seeds[label][seed][name] = (pu + us, pt + tot)

    def arch_of(name):
        return "starmie" if name == "mirror_starmie" else ARCH.get(name, "other")

    for label in sorted(pool):
        P = pool[label]
        by_arch = defaultdict(list)
        for name in P:
            by_arch[arch_of(name)].append(name)

        def band_wr(rows):
            num = den = 0.0
            for name, (us, tot) in rows.items():
                if tot == 0:
                    continue
                a = arch_of(name)
                w = BAND_WEIGHT.get(a, 0.0) / len(by_arch[a])
                num += w * us / tot
                den += w
            return num / den if den else 0.0

        pooled_rows = {n: (P[n][0], P[n][1]) for n in P}
        band = band_wr(pooled_rows)
        per_seed = []
        for seed in sorted(seeds[label]):
            per_seed.append((seed, band_wr(seeds[label][seed])))

        print("=" * 100)
        print("CONFIG: %s  -- BAND-WEIGHTED (live 700-1000 mix)" % label)
        for name, arch in list(G.ROSTER) + [("mirror_starmie", "starmie")]:
            if name not in P:
                continue
            us, tot = P[name][0], P[name][1]
            a = arch_of(name)
            w = BAND_WEIGHT.get(a, 0.0) / len(by_arch[a])
            print("  %-20s arch=%-11s w=%.4f  %4d/%4d  WR=%5.1f%%  LB=%5.1f%%"
                  % (name, a, w, us, tot, 100 * us / tot if tot else 0,
                     100 * G.wilson_lb(us, tot)))
        WF = sum(P[n][6] for n in P); NF = sum(P[n][7] for n in P)
        WS = sum(P[n][8] for n in P); NS = sum(P[n][9] for n in P)
        crs = sum(P[n][3] for n in P); ill = sum(P[n][4] for n in P)
        to = sum(P[n][5] for n in P)
        print("-" * 100)
        print("BAND-WEIGHTED WR = %.2f%%   per-seed: %s"
              % (100 * band, "  ".join("%d:%.1f%%" % (s, 100 * b) for s, b in per_seed)))
        print("SEAT (mirror incl.): first %.1f%% (n=%d, LB %.1f%%)  second %.1f%% (n=%d, LB %.1f%%)"
              % (100.0 * WF / NF if NF else 0, NF, 100 * G.wilson_lb(WF, NF),
                 100.0 * WS / NS if NS else 0, NS, 100 * G.wilson_lb(WS, NS)))
        print("SAFETY: crashes=%d illegal=%d timeouts=%d over %d games"
              % (crs, ill, to, sum(P[n][1] for n in P)))


if __name__ == "__main__":
    main()
