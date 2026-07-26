"""Per-turn summary trace of one band-pool game: actives, HP, energy, prizes, decks.
Usage: probe_trace.py <opponent> <gameseed> (diag_v8 convention: us_seat=(gameseed-12345)%2)."""
import random
import sys

import gauntlet as G
import obs as O
from cg.game import battle_start, battle_select, battle_finish

G.GDIR = G.HOME + "/gauntlet_band"
name, gameseed = sys.argv[1], int(sys.argv[2])
us_seat = (gameseed - 12345) % 2
deck_o = G.opp_deck(name)
random.seed(gameseed)
opp = G.load_opp_fresh(name)
G.reset_our()
decks = (G.our.DECK, deck_o) if us_seat == 0 else (deck_o, G.our.DECK)
obs, sd = battle_start(decks[0], decks[1])
steps = 0
last_turn = -1


def nm(cid):
    d = O.card_data(cid)
    return (getattr(d, "name", None) or str(cid))[:18]


def brd(p):
    out = []
    for c in ([p["active"][0]] if p["active"] and p["active"][0] else []) + [
            b for b in (p["bench"] or []) if b]:
        out.append("%s %d/%dhp e%d" % (nm(c["id"]), c["hp"],
                                       c.get("maxHp", c["hp"]), len(c["energies"] or [])))
    return " | ".join(out)


while obs["current"]["result"] < 0 and steps < 3000:
    cur = obs["current"]
    if cur["turn"] != last_turn:
        last_turn = cur["turn"]
        me = cur["players"][us_seat]
        op = cur["players"][1 - us_seat]
        print("T%-3d pr %d-%d dk %d-%d | US: %s || OPP: %s" % (
            cur["turn"], len(me["prize"] or []), len(op["prize"] or []),
            me["deckCount"], op["deckCount"], brd(me), brd(op)))
    yi = cur["yourIndex"]
    sel = G.our.agent(obs) if yi == us_seat else opp.agent(obs)
    obs = battle_select(sel)
    steps += 1
cur = obs["current"]
me = cur["players"][us_seat]
op = cur["players"][1 - us_seat]
print("END r=%s T%s steps=%d pr %d-%d dk %d-%d" % (
    cur["result"], cur["turn"], steps, len(me["prize"] or []),
    len(op["prize"] or []), me["deckCount"], op["deckCount"]))
print("US: %s" % brd(me))
print("OPP: %s" % brd(op))
battle_finish()
