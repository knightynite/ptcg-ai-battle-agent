"""v8 diagnostics on the LIVE-BAND pool (~/gauntlet_band): per-game end-state census.

Like diag_v7.py but: band-pool roster, per-game seat + first-player, explicit CAPPED
mode (the local 3000-step cap) with the at-cap deck-race read (who would deck out
first if both sides went fully passive -- the live adjudication proxy, since the real
engine has episodeSteps=10M and the Jun-30 rule makes loopers lose by TIMEOUT, not
step cap), lock engagement, and optional seat filter.

Usage: PTCG_OUR_DIR=... PTCG_B1=1 ... diag_v8.py <opponent> <N> <seed0> [first|second]
"""
import random
import sys

import gauntlet as G
import scoring as SC
from cg.game import battle_start, battle_select, battle_finish

G.GDIR = G.HOME + "/gauntlet_band"

name = sys.argv[1]
N = int(sys.argv[2])
seed0 = int(sys.argv[3])
seat_filter = sys.argv[4] if len(sys.argv) > 4 else None

deck_o = G.opp_deck(name)
LOCK = {"n": 0}
_orig = SC._lock_clock


def probed(tc):
    r = _orig(tc)
    if r:
        LOCK["n"] += 1
    return r


SC._lock_clock = probed

census = {}
rows = []
played = 0
g = -1
while played < N:
    g += 1
    random.seed(seed0 + g)
    us_seat = g % 2
    opp = G.load_opp_fresh(name)
    G.reset_our()
    LOCK["n"] = 0
    decks = (G.our.DECK, deck_o) if us_seat == 0 else (deck_o, G.our.DECK)
    obs, sd = battle_start(decks[0], decks[1])
    steps = 0
    while obs["current"]["result"] < 0 and steps < 3000:
        yi = obs["current"]["yourIndex"]
        sel = G.our.agent(obs) if yi == us_seat else opp.agent(obs)
        obs = battle_select(sel)
        steps += 1
    cur = obs["current"]
    fp = cur.get("firstPlayer", -1)
    we_first = (fp == us_seat)
    if seat_filter == "first" and not we_first:
        battle_finish()
        continue
    if seat_filter == "second" and we_first:
        battle_finish()
        continue
    played += 1
    r = cur["result"]
    me = cur["players"][us_seat]
    op = cur["players"][1 - us_seat]
    won = (r == us_seat)
    my_pr = len(me["prize"] or [])
    op_pr = len(op["prize"] or [])
    mydk, opdk = me["deckCount"], op["deckCount"]
    if r < 0:
        # CAPPED: local harness scores this as OUR LOSS. Live (episodeSteps=10M)
        # the game would continue; if both go passive 1 draw/turn the smaller deck
        # decks out first -> report who wins THAT race (we move next-ish; ties ~ even).
        mode = "CAPPED(%s)" % ("WEwin" if mydk > opdk else
                               ("WElose" if mydk < opdk else "even"))
    elif r == 2:
        mode = "DRAW"
    elif won:
        mode = ("OPP_DECKOUT" if opdk == 0 else
                ("PRIZE_WIN" if my_pr == 0 else "OPP_NOBENCH?"))
    else:
        mode = ("OUR_DECKOUT" if mydk == 0 else
                ("PRIZE_LOSS" if op_pr == 0 else "OUR_NOBENCH?"))
    census[mode] = census.get(mode, 0) + 1
    rows.append((("W" if won else ("D" if r == 2 else "L")),
                 ("1st" if we_first else "2nd"), mode, steps, cur["turn"],
                 mydk, opdk, my_pr, op_pr, LOCK["n"], seed0 + g))
    battle_finish()

print("%-2s %-4s %-15s %5s %5s %5s %5s %5s %5s %6s %8s" %
      ("wl", "seat", "mode", "steps", "turn", "mydk", "opdk", "myPr", "opPr",
       "lockN", "gameseed"))
for r in rows:
    print("%-2s %-4s %-15s %5d %5d %5d %5d %5d %5d %6d %8d" % r)
wins = sum(1 for r in rows if r[0] == "W")
print("WR %d/%d = %.1f%%   modes: %s" % (wins, len(rows), 100.0 * wins / max(1, len(rows)),
                                          sorted(census.items(), key=lambda kv: -kv[1])))
