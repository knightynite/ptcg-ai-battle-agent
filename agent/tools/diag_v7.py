"""Diagnose v7 losses: play N games vs one opponent, log end-state census +
lock-engagement stats per game."""
import os, sys, random
import gauntlet as G
import pilot as _pilot
import scoring as SC
from cg.game import battle_start, battle_select, battle_finish

name = sys.argv[1]; N = int(sys.argv[2]); seed0 = int(sys.argv[3])
deck_o = G.opp_deck(name)
LOCK = {"n": 0}
_orig = SC._lock_clock
def probed(tc):
    r = _orig(tc)
    if r: LOCK["n"] += 1
    return r
SC._lock_clock = probed

census = {"win": 0, "loss": 0}
rows = []
for g in range(N):
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
    r = cur["result"]
    me = cur["players"][us_seat]; op = cur["players"][1 - us_seat]
    won = (r == us_seat)
    # loss/win mode guess
    mode = "?"
    if me["deckCount"] == 0 and not won: mode = "OUR_DECKOUT"
    elif op["deckCount"] == 0 and won: mode = "OPP_DECKOUT"
    elif won and len(op["prize"]) - 6 == 0: mode = "?"
    if won and any(len(me["prize"]) == 0 for _ in [0]): mode = "PRIZES_US" if me["prize"] is not None and len([p for p in me["prize"]]) == 0 else mode
    my_pr = len(me["prize"] or []); op_pr = len(op["prize"] or [])
    if mode == "?":
        if won: mode = "PRIZE_WIN" if my_pr == 0 else "OPP_NOBENCH?"
        else:   mode = "PRIZE_LOSS" if op_pr == 0 else "OUR_NOBENCH?"
    census["win" if won else "loss"] += 1
    rows.append((won, mode, steps, cur["turn"], me["deckCount"], op["deckCount"],
                 my_pr, op_pr, LOCK["n"]))
    battle_finish()
print("%-5s %-13s %5s %5s %6s %6s %5s %5s %6s" % ("won","mode","steps","turn","mydk","opdk","myPr","opPr","lockN"))
for r in rows:
    print("%-5s %-13s %5d %5d %6d %6d %5d %5d %6d" % r)
print(census)
