"""Starmie-mirror A/B: OUR live build (~/agent_v0, env-configured, e.g. v5 flags) vs a
FROZEN v4b opponent (~/mirror_b: repo-HEAD agent modules renamed *_b so both stacks can
coexist in one process). Both sides play the identical Mega Starmie ex 60.

Purpose: the live 700-1000 band serves ~12% Starmie mirrors (live autopsy 2026-07-11,
4-8 with all losses second/slow) and the local roster has no mirror bot. This harness
supplies the mirror row for the v5 band-weighted gate and the seat-split read.

  PYTHONPATH=$HOME/ptcg-work [PTCG_R1=0 ...] \
      ~/ptcg-venv/bin/python ~/ptcg-work/mirror_ab.py <label> [N=100] [seed=12345]

NOTE: the frozen *_b side reads the same PTCG_P*/T* env (it has no R flags), so leave
P/T unset (defaults = v4b) and vary only PTCG_R1..R4 between arms.
"""
import importlib.util
import math
import os
import random
import statistics
import sys
import time

HOME = os.path.expanduser("~")
OUR_DIR = HOME + "/agent_v0"
B_DIR = HOME + "/mirror_b"


def _load(modname, path, wd):
    old = os.getcwd()
    os.chdir(wd)
    if wd not in sys.path:
        sys.path.insert(0, wd)
    try:
        sys.modules.pop(modname, None)
        spec = importlib.util.spec_from_file_location(modname, path)
        m = importlib.util.module_from_spec(spec)
        sys.modules[modname] = m
        spec.loader.exec_module(m)
    finally:
        os.chdir(old)
    return m


def wilson_lb(w, n, z=1.96):
    if n == 0:
        return 0.0
    p = w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - m) / d


our = _load("our_main", OUR_DIR + "/main.py", OUR_DIR)
DECK = [int(x) for x in open(OUR_DIR + "/deck.csv") if x.strip()]
our.DECK = DECK
import pilot as _pilot  # noqa: E402  (loaded by our main)
_pilot.DECK = DECK

# The frozen B side plays ITS OWN deck (~/mirror_b/deck.csv = the WD Starmie list) so
# a non-Starmie candidate in OUR_DIR still faces the live-band Starmie opponent
# (deck re-bakeoff 2026-07-12). With OUR_DIR = the Starmie agent this is byte-identical
# to the old both-play-OUR-deck behavior (the two lists are the same file content).
bmain = _load("b_main", B_DIR + "/main_b.py", B_DIR)
try:
    BDECK = [int(x) for x in open(B_DIR + "/deck.csv") if x.strip()]
    if len(BDECK) != 60:
        BDECK = list(DECK)
except Exception:
    BDECK = list(DECK)
bmain.DECK = BDECK
import pilot_b as _pilot_b  # noqa: E402  (loaded by the frozen copy)
_pilot_b.DECK = list(BDECK)

from cg.game import battle_start, battle_select, battle_finish  # noqa: E402


def reset_both():
    for p in (_pilot, _pilot_b):
        if hasattr(p, "_last_turn"):
            p._last_turn = -1
        if hasattr(p, "_game_elapsed"):
            p._game_elapsed = 0.0


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "mirror"
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 12345
    us = lo = draw = 0
    cr_us = cr_b = il_us = il_b = 0
    wf = nf = ws = ns = 0
    dtimes = []
    for g in range(N):
        random.seed(seed0 + g)
        us_seat = g % 2
        reset_both()
        decks = (DECK, BDECK) if us_seat == 0 else (BDECK, DECK)
        obs, sd = battle_start(decks[0], decks[1])
        if sd.errorPlayer >= 0:
            print("DECK_ERROR", sd.errorPlayer, sd.errorType)
            return
        steps = 0
        aborted = None
        while obs["current"]["result"] < 0 and steps < 3000:
            yi = obs["current"]["yourIndex"]
            try:
                if yi == us_seat:
                    t0 = time.perf_counter()
                    sel = our.agent(obs)
                    dtimes.append(time.perf_counter() - t0)
                else:
                    sel = bmain.agent(obs)
                n = len(obs["select"]["option"])
                ok = (isinstance(sel, list)
                      and all(isinstance(i, int) and 0 <= i < n for i in sel)
                      and len(set(sel)) == len(sel))
                if not ok:
                    if yi == us_seat:
                        il_us += 1
                    else:
                        il_b += 1
                    aborted = "illegal"
                    break
                obs = battle_select(sel)
            except Exception:
                if yi == us_seat:
                    cr_us += 1
                else:
                    cr_b += 1
                aborted = "crash"
                break
            steps += 1
        r = obs["current"]["result"]
        try:
            fp = obs["current"].get("firstPlayer", -1)
        except Exception:
            fp = -1
        battle_finish()
        won = False
        if aborted:
            lo += 1          # any abort scored as OUR loss (conservative)
        elif r == 2:
            draw += 1
        elif r == us_seat:
            us += 1
            won = True
        else:
            lo += 1
        if fp is not None and fp >= 0:
            if fp == us_seat:
                nf += 1
                wf += 1 if won else 0
            else:
                ns += 1
                ws += 1 if won else 0
    tot = us + lo + draw
    ds = sorted(dtimes)
    p99 = ds[min(len(ds) - 1, int(len(ds) * 0.99))] * 1000 if ds else 0
    print("MIRRORROW,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%.2f" % (
        label, seed0, us, tot, draw, cr_us, il_us, cr_b, il_b,
        wf, nf, ws, ns, p99), flush=True)
    print("MIRROR[%s] seed=%d: us=%d lo=%d draw=%d tot=%d  WR=%.1f%% LB=%.1f%%  "
          "1st %.0f%%(%d) 2nd %.0f%%(%d)  crash us/b=%d/%d illegal us/b=%d/%d p99=%.1fms"
          % (label, seed0, us, lo, draw, tot, 100 * us / tot if tot else 0,
             100 * wilson_lb(us, tot),
             100.0 * wf / nf if nf else 0, nf, 100.0 * ws / ns if ns else 0, ns,
             cr_us, cr_b, il_us, il_b, p99), flush=True)


if __name__ == "__main__":
    main()
