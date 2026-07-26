"""Live-engine tracker drift test (v4). Plays N local games (cg.game) with the full
v4 agent and asserts after EVERY one of our decisions that the hidden-state tracker:
  * stayed ok (never internally disabled),
  * accumulated zero divergences (div == 0 -> every event batch reconciled exactly
    against the state counts, no rebases needed),
  * agrees with the observation on the opponent hand partition
    (len(known) + unknown == handCount) and our hidden-pool size.
Also reports tracker exact-prize coverage and our decision p50/p99 (tracker overhead).

Run in WSL:
  PYTHONPATH=$HOME/ptcg-work:$HOME/agent_v0 ~/ptcg-venv/bin/python tracker_live_test.py 20
"""
import os
import sys
import time
import importlib.util
import statistics

HOME = os.path.expanduser("~")
OUR_DIR = HOME + "/agent_v0"
GDIR = HOME + "/gauntlet"
OPPS = ["romanrozen", "souta_crustle", "ryota_alakazam", "wmh_grimmsnarl"]


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


our = _load("our_main", OUR_DIR + "/main.py", OUR_DIR)
our.DECK = [int(x) for x in open(OUR_DIR + "/deck.csv") if x.strip()]
import pilot as _pilot
_pilot.DECK = our.DECK

from cg.game import battle_start, battle_select, battle_finish


def main():
    n_games = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    viol = 0
    games = 0
    exact_games = 0
    not_ok_games = 0
    div_games = 0
    dtimes = []
    for g in range(n_games):
        opp_name = OPPS[g % len(OPPS)]
        opp = _load("opp_" + opp_name, GDIR + "/" + opp_name + "/main.py",
                    GDIR + "/" + opp_name)
        opp_deck = [int(x) for x in open(GDIR + "/" + opp_name + "/deck.csv")
                    if x.strip()]
        us_seat = g % 2
        _pilot._last_turn = -1
        _pilot._game_elapsed = 0.0
        decks = (our.DECK, opp_deck) if us_seat == 0 else (opp_deck, our.DECK)
        obs, sd = battle_start(decks[0], decks[1])
        assert sd.errorPlayer < 0, "deck error"
        steps = 0
        had_exact = False
        while obs["current"]["result"] < 0 and steps < 3000:
            yi = obs["current"]["yourIndex"]
            if yi == us_seat:
                t0 = time.perf_counter()
                sel = our.agent(obs)
                dtimes.append(time.perf_counter() - t0)
                t = _pilot._tracker
                # strict per-decision invariants
                if not t.ok:
                    viol += 1
                    print("game %d (%s): tracker NOT ok at step %d" % (g, opp_name, steps))
                    break
                if t.div != 0:
                    viol += 1
                    print("game %d (%s): div=%d at step %d (tags need debug run)"
                          % (g, opp_name, t.div, steps))
                    break
                opp_ps = obs["current"]["players"][1 - us_seat]
                if len(t.opp_known_hand) + t.opp_unknown_n != (opp_ps["handCount"] or 0):
                    viol += 1
                    print("game %d: hand partition mismatch at step %d" % (g, steps))
                    break
                if t.our_prize_ms is not None:
                    had_exact = True
                    n_fd = sum(1 for c in obs["current"]["players"][us_seat]["prize"]
                               if c is None)
                    if sum(t.our_prize_ms.values()) != n_fd:
                        viol += 1
                        print("game %d: prize ms size mismatch at step %d" % (g, steps))
                        break
            else:
                sel = opp.agent(obs)
            obs = battle_select(sel)
            steps += 1
        battle_finish()
        games += 1
        t = _pilot._tracker
        if had_exact:
            exact_games += 1
        if not t.ok:
            not_ok_games += 1
        if t.div:
            div_games += 1

    ds = sorted(dtimes)
    print("=" * 70)
    print("games=%d violations=%d  exact-prize games=%d  not_ok=%d  div>0=%d" % (
        games, viol, exact_games, not_ok_games, div_games))
    if ds:
        print("our decisions=%d p50=%.2fms p99=%.2fms max=%.1fms" % (
            len(ds), 1000 * statistics.median(ds),
            1000 * ds[min(len(ds) - 1, int(len(ds) * 0.99))], 1000 * ds[-1]))
    print("VERDICT:", "PASS" if viol == 0 and not_ok_games == 0 and div_games == 0
          else "FAIL")


if __name__ == "__main__":
    main()
