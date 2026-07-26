"""R3 diagnostics: opponent-archetype classification accuracy by turn + belief/rollout usage.

Plays the meta gauntlet (reusing gauntlet.py's loaders/loop) and, after each of OUR
decisions, snapshots the belief model's top_archetype() and confidence keyed by the engine
turn counter. Aggregates classification accuracy by turn bucket against each opponent's KNOWN
archetype (the gauntlet roster label). Also dumps belief-fill vs junk-fill counts, plan-search
override stats, and our decision timing -- the report's F3 figure ammunition.

Run in WSL (toggle env to taste, e.g. PTCG_SEARCH=1 PTCG_BELIEF=1 PTCG_OPP_ROLLOUT=1):
  PYTHONPATH=$HOME/ptcg-work PTCG_SEARCH=1 ~/ptcg-venv/bin/python diag_r3.py [games] [seed0]
"""
import sys
import time
import random
import statistics

import gauntlet as G
import pilot as PILOT
import belief as BEL
import search as SE
import obs as O
from cg.game import battle_start, battle_select, battle_finish

# roster arch -> belief arch (only these are scored for classification accuracy)
SCOREABLE = {
    "alakazam": "alakazam", "crustle": "crustle", "grimmsnarl": "grimmsnarl",
    "cynthia": "cynthia", "lucario": "lucario", "dragapult": "dragapult",
    "archaludon": "archaludon", "kangaskhan": "kangaskhan",
}
BUCKETS = [(1, 2), (3, 4), (5, 6), (7, 8), (9, 999)]


def play_diag(name, truth_arch, N, seed0, records, confusion):
    deck_o = G.opp_deck(name)
    for g in range(N):
        random.seed(seed0 + g)
        us_seat = g % 2
        try:
            opp = G.load_opp_fresh(name)
        except Exception:
            continue
        G.reset_our()
        decks = (G.our.DECK, deck_o) if us_seat == 0 else (deck_o, G.our.DECK)
        ob, sd = battle_start(decks[0], decks[1])
        if sd.errorPlayer >= 0:
            return
        steps = 0
        while ob["current"]["result"] < 0 and steps < 3000:
            yi = ob["current"]["yourIndex"]
            try:
                if yi == us_seat:
                    sel = G.our.agent(ob)
                    # snapshot belief AFTER our agent updated it this decision
                    turn = ob["current"].get("turn", 0) or 0
                    pred, conf = PILOT._belief.top_archetype()
                    records.append((turn, pred == truth_arch, conf))
                    confusion[(truth_arch, pred)] = confusion.get((truth_arch, pred), 0) + 1
                else:
                    sel = opp.agent(ob)
                ob = battle_select(sel)
            except Exception:
                break
            steps += 1
        battle_finish()


def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    seed0 = int(sys.argv[2]) if len(sys.argv) > 2 else 12345
    SE.BELIEF_DIAG.update({"belief_fill": 0, "junk_fill": 0})
    records = []            # (turn, correct_bool, conf)
    confusion = {}
    t0 = time.perf_counter()
    for name, arch in G.ROSTER:
        truth = SCOREABLE.get(arch)
        if truth is None:
            continue
        play_diag(name, truth, N, seed0, records, confusion)
    dt = time.perf_counter() - t0

    print("### R3 classification accuracy by turn (N=%d/opp, seed0=%d) ###" % (N, seed0))
    print("belief config: SEARCH=%s BELIEF=%s OPP_ROLLOUT=%s"
          % (PILOT._SEARCH_ENABLED, PILOT._BELIEF_ENABLED, PILOT._OPP_ROLLOUT))
    print("%-10s %8s %10s %10s" % ("turnbkt", "n", "acc", "meanConf"))
    for lo, hi in BUCKETS:
        sub = [(c, cf) for (t, c, cf) in records if lo <= t <= hi]
        if not sub:
            continue
        acc = sum(1 for c, _ in sub if c) / len(sub)
        mc = statistics.mean([cf for _, cf in sub])
        label = "%d-%d" % (lo, hi) if hi < 999 else "%d+" % lo
        print("%-10s %8d %9.1f%% %9.2f" % (label, len(sub), 100 * acc, mc))
    tot = len(records)
    if tot:
        overall = sum(1 for _, c, _ in records if c) / tot
        print("OVERALL   %8d %9.1f%%" % (tot, 100 * overall))
    print("\nbelief fills=%d  junk fills=%d  (belief share=%.1f%%)"
          % (SE.BELIEF_DIAG["belief_fill"], SE.BELIEF_DIAG["junk_fill"],
             100 * SE.BELIEF_DIAG["belief_fill"]
             / max(1, SE.BELIEF_DIAG["belief_fill"] + SE.BELIEF_DIAG["junk_fill"])))
    print("pilot STATS:", PILOT.STATS)
    print("plan diag:", SE.PLAN_DIAG)
    print("elapsed %.0fs" % dt)

    # confusion: what each true archetype was most often called
    print("\nconfusion (true -> predicted : count), top mispredictions:")
    by_true = {}
    for (tr, pr), c in confusion.items():
        by_true.setdefault(tr, []).append((c, pr))
    for tr in sorted(by_true):
        row = sorted(by_true[tr], reverse=True)[:4]
        print("  %-11s -> %s" % (tr, ", ".join("%s:%d" % (pr, c) for c, pr in row)))


if __name__ == "__main__":
    main()
