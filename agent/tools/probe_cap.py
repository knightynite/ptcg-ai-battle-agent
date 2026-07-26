"""Who consumes the steps in a capped game? Plays one game vs a band-pool opponent,
counts decisions per side, and prints the trailing decision pattern.
Usage: probe_cap.py <opponent> <gameseed> (gameseed = seed0+g from diag_v8)."""
import random
import sys
from collections import Counter

import gauntlet as G
from cg.game import battle_start, battle_select, battle_finish

G.GDIR = G.HOME + "/gauntlet_band"
name, gameseed = sys.argv[1], int(sys.argv[2])
g = gameseed % 2  # us_seat parity follows diag_v8: us_seat = g % 2 with seed0+g
# reproduce exactly: diag used random.seed(seed0+g), us_seat=g%2. We only know
# seed0+g; parity of g: diag seed0=12345 odd; us_seat = (gameseed - 12345) % 2.
us_seat = (gameseed - 12345) % 2
deck_o = G.opp_deck(name)
random.seed(gameseed)
opp = G.load_opp_fresh(name)
G.reset_our()
decks = (G.our.DECK, deck_o) if us_seat == 0 else (deck_o, G.our.DECK)
obs, sd = battle_start(decks[0], decks[1])
steps = 0
by_side = Counter()
trail = []
while obs["current"]["result"] < 0 and steps < 3000:
    yi = obs["current"]["yourIndex"]
    side = "US" if yi == us_seat else "OPP"
    ctx = obs["select"].get("context")
    opts = obs["select"]["option"]
    if yi == us_seat:
        sel = G.our.agent(obs)
    else:
        sel = opp.agent(obs)
    desc = []
    for si in (sel or [])[:2]:
        try:
            o = opts[si]
            desc.append("%s" % (o.get("type"),))
        except Exception:
            desc.append("?")
    by_side[side] += 1
    trail.append((side, ctx, ",".join(str(d) for d in desc), len(opts)))
    if len(trail) > 60:
        trail.pop(0)
    obs = battle_select(sel)
    steps += 1
cur = obs["current"]
print("steps=%d turn=%s result=%s  decisions US=%d OPP=%d" % (
    steps, cur["turn"], cur["result"], by_side["US"], by_side["OPP"]))
print("last 60 decisions (side, context, picked-type, n_opts):")
c = Counter(trail)
for k, n in c.most_common(10):
    print("  %dx %s" % (n, k))
battle_finish()
