"""Paired A/B pooling for CRN band-gauntlet logs: per-row paired deltas + McNemar.

Usage:
  python crn_pool.py <armA.log> <armB.log> [more A,B pairs...]
  (each log = band_gauntlet.py output containing BANDROW lines WITH the trailing
   per-game outcome string, i.e. produced by the 2026-07-13 CRN harness; arm A and
   arm B must have been run with the SAME seed0 and --crn so game index g shares
   the same battle world in both arms.)

Per row it reports:
  nA/nB wins, delta pp, discordant pair counts b (A won, B didn't) / c (B won,
  A didn't), exact two-sided McNemar p (binomial b vs b+c), and the empirical
  variance-reduction factor VRF = Var_unpaired(delta_hat)/Var_paired(delta_hat)
    unpaired: (pA qA + pB qB)/n     paired: [ (b+c)/n - ((b-c)/n)^2 ] / n
Aggregate: live-band-weighted delta, pooled b/c + pooled McNemar, weighted VRF.

Multiple (A,B) pairs (e.g. 3 seeds) are pooled per row before the stats.
"""
import sys
import math

# live-band weights -- keep in sync with band_gauntlet.py ROSTER (duplicated here so
# this reporting tool never imports the harness, which would load agents/engine).
WEIGHT = {
    # 2026-07-14 v11 re-based pool (Jul-13 active-pair faced mix; see band_gauntlet.py)
    # 2026-07-14 v12: kiyotah/kojimar corrected 0.180/0.090 -> 0.171/0.099 (the 2:1
    # split matched nothing on record; corrected to the live 31:18 faced ratio at
    # the same 0.270 family total -- see band_gauntlet.py ROSTER comment). Keep
    # this dict in sync with ROSTER (duplicated by design; see module docstring).
    "kiyotah_lucario": 0.171, "kojimar_baseline": 0.099, "alakazam_live": 0.045,
    "wmh_alakazam": 0.025, "ryota_alakazam": 0.020, "budew_crustle": 0.015,
    "crustle_live": 0.010, "self_mirror": 0.035, "mirror_wall_fdedde79": 0.030,
    "mirror_tusk_ee52c8d3": 0.030, "mirror_216305d7": 0.015,
    "kiyotah_dragapult": 0.090, "starmie_live": 0.053, "starmie_blitz": 0.055,
    "archaludon_live": 0.040, "masami_archaludon": 0.014, "kyogre_live": 0.018,
    "hops_snorlax": 0.045, "wmh_grimmsnarl": 0.063, "wmh_garchomp": 0.009,
    "wmh_bellibolt": 0.009, "ogerpon_live": 0.005, "majkel_hammer_alakazam": 0.045,
    "comfey_hammer_denial": 0.012, "rocket_spidops": 0.010,
}


def parse(path):
    rows = {}
    for line in open(path):
        if not line.startswith("BANDROW,"):
            continue
        f = line.strip().split(",")
        name, seed = f[1], int(f[2])
        outc = f[15] if len(f) > 15 else ""
        if not outc:
            sys.exit("%s: BANDROW for %s has no outcome string -- re-run with the"
                     " CRN harness (2026-07-13+)" % (path, name))
        rows[(name, seed)] = outc
    if not rows:
        sys.exit("%s: no BANDROW lines" % path)
    return rows


def mcnemar_p(b, c):
    """Exact two-sided binomial test of b successes in b+c at p=0.5."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2.0 ** n
    return min(1.0, 2.0 * tail)


def main(argv):
    if len(argv) < 2 or len(argv) % 2:
        sys.exit(__doc__)
    logsA, logsB = argv[0::2], argv[1::2]
    A, B = {}, {}
    for pa, pb in zip(logsA, logsB):
        ra, rb = parse(pa), parse(pb)
        for k, v in ra.items():
            A.setdefault(k[0], []).append((k[1], v))
        for k, v in rb.items():
            B.setdefault(k[0], []).append((k[1], v))

    print("%-24s %5s %6s %6s %7s  %4s %4s  %-9s %6s" %
          ("row", "n", "A%", "B%", "dpp", "b", "c", "McNemar_p", "VRF"))
    print("-" * 84)
    tb = tc = 0
    wnum = wden = 0.0
    wvrf_num = wvrf_den = 0.0
    for name in A:
        if name not in B:
            print("%-24s  (missing in arm B -- skipped)" % name)
            continue
        sa = dict(A[name])
        sb = dict(B[name])
        seeds = sorted(set(sa) & set(sb))
        oa = "".join(sa[s] for s in seeds)
        ob = "".join(sb[s] for s in seeds)
        if len(oa) != len(ob):
            print("%-24s  (unequal game counts %d vs %d -- skipped)"
                  % (name, len(oa), len(ob)))
            continue
        n = len(oa)
        wa = oa.count("W")
        wb = ob.count("W")
        b = sum(1 for x, y in zip(oa, ob) if x == "W" and y != "W")
        c = sum(1 for x, y in zip(oa, ob) if x != "W" and y == "W")
        pA, pB = wa / n, wb / n
        var_un = (pA * (1 - pA) + pB * (1 - pB)) / n
        var_pa = ((b + c) / n - ((b - c) / n) ** 2) / n
        vrf = (var_un / var_pa) if var_pa > 0 else float("inf")
        p = mcnemar_p(b, c)
        print("%-24s %5d %6.1f %6.1f %+7.2f  %4d %4d  %9.4f %6s" %
              (name, n, 100 * pA, 100 * pB, 100 * (pB - pA), b, c, p,
               ("%.1fx" % vrf) if vrf != float("inf") else "inf"))
        tb += b
        tc += c
        w = WEIGHT.get(name, 0.0)
        wnum += w * (pB - pA)
        wden += w
        if var_pa > 0:
            wvrf_num += w * vrf
            wvrf_den += w
    print("-" * 84)
    if wden > 0:
        print("live-band-WEIGHTED paired delta = %+.2fpp (coverage %.1f%%)"
              % (100 * wnum / wden, 100 * wden))
    print("pooled discordants b=%d c=%d  pooled McNemar p=%.4f" %
          (tb, tc, mcnemar_p(tb, tc)))
    if wvrf_den > 0:
        print("weighted mean per-row VRF (paired vs unpaired) = %.1fx"
              % (wvrf_num / wvrf_den))


if __name__ == "__main__":
    main(sys.argv[1:])
