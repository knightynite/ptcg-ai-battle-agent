"""Pool BANDROW lines from v9 row-sharded logs into the LIVE-BAND-WEIGHTED WR.

Reads any number of log files, collects BANDROW,<name>,<seed>,us,tot,draw,crash,
illegal,timeouts,wf,nf,ws,ns[,cap,capw] lines (the 2026-07-13 cap-adjudicated
instrument appends cap/capw), de-duplicates on (name,seed) keeping the FIRST
occurrence (resumable-runner semantics), and prints per-row pooled WR + the
weighted aggregate per band_gauntlet.ROSTER weights + safety counts.

Usage: python band_pool_v9.py <log> [log...]
"""
import sys

from band_gauntlet import ROSTER, WEIGHT

rows = {}
for path in sys.argv[1:]:
    for ln in open(path, encoding="utf-8", errors="replace"):
        if not ln.startswith("BANDROW,"):
            continue
        f = ln.strip().split(",")
        name, seed = f[1], int(f[2])
        if (name, seed) in rows:
            continue
        v = [int(x) for x in f[3:]]
        v += [0] * (12 - len(v))
        rows[(name, seed)] = v

pool = {}
for (name, seed), v in sorted(rows.items()):
    p = pool.setdefault(name, [0] * 12)
    for i, x in enumerate(v):
        p[i] += x

print("%-24s %5s %5s %6s  %s" % ("row", "us", "tot", "WR%", "crash/ill/to  cap(w)  seeds"))
num = den = 0.0
crash = ill = to = 0
for name, arch, w, _k, _n, _wl in ROSTER:
    if name not in pool:
        print("%-24s  MISSING" % name)
        continue
    us, tot, draw, cr, il, t, wf, nf, ws, ns, cap, capw = pool[name]
    seeds = sorted(s for (n2, s) in rows if n2 == name)
    wr = us / tot if tot else 0.0
    num += w * wr
    den += w
    crash += cr; ill += il; to += t
    print("%-24s %5d %5d %6.1f  %d/%d/%d  %d(%d)  %s" % (
        name, us, tot, 100 * wr, cr, il, t, cap, capw,
        ",".join(str(s) for s in seeds)))
if den:
    print("-" * 78)
    print("LIVE-BAND-WEIGHTED WR (coverage %.3f) = %.2f%%" % (den, 100 * num / den))
    print("safety: crashes=%d illegal=%d timeouts=%d" % (crash, ill, to))
    # per-seed weighted (only seeds present for ALL rows count)
    seeds_all = sorted({s for (_n, s) in rows})
    for s in seeds_all:
        n2 = d2 = 0.0
        ok = True
        for name, arch, w, _k, _nn, _wl in ROSTER:
            v = rows.get((name, s))
            if v is None or v[1] == 0:
                ok = False
                break
            n2 += w * v[0] / v[1]
            d2 += w
        if ok:
            print("  seed %d weighted = %.2f%%" % (s, 100 * n2 / d2))
