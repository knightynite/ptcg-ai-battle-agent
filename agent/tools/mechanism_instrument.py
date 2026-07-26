"""Manabase A/B mechanism instrument: -4 Spiky/+4 Basic{G} candidate, 2026-07-15.

Runs one (opponent row, N, seed0) unit under whichever deck.csv is currently sitting
at PTCG_OUR_DIR (arm A/B is toggled OUTSIDE this script by swapping deck.csv before
invocation -- same convention as run_v11_gate.sh toggling env before each arm). Holds
pilot flags fixed at the v11 SHIP config (PTCG_MIR=1 PTCG_SBL=0, agent_v11_results.md
sec.4) -- this is a deck-only A/B, no pilot-logic change.

In addition to the standard BANDROW win/loss line (same schema as band_gauntlet.py,
so crn_pool.py works unmodified), prints a MECHROW line per unit with:
  - our_turns: number of our TurnStart events across all N games
  - crustle_attacks: number of Attack log events by us with cardId=345 (Crustle,
    attackId=479 "Superb Scissors")
  - payable_decisions: number of our MAIN-select decisions where an ATTACK option
    with attackId=479 was present in obs.select.option (engine-computed legality,
    not reimplemented energy math)
  - payable_games: number of games in which >=1 payable_decision occurred
  - attack_games: number of games in which we made >=1 Crustle attack

Usage (WSL): PYTHONPATH=$HOME/ptcg-work PTCG_OUR_DIR=... PTCG_MIR=1 PTCG_SBL=0 \
  <40-flag ledger from agent_v11_results.md sec.4 / run_v11_gate.sh> \
  ~/ptcg-venv/bin/python mechanism_instrument.py <row> <N> <seed0>

See intel/manabase_ab_2026-07-15.md for the run this tool produced and its verdict.
"""
import os
import sys
import random
import traceback

sys.path.insert(0, os.path.join(os.environ.get("HOME", os.path.expanduser("~")), "ptcg-work"))
import gauntlet as G  # reuses OUR_DIR load, CRN shim
G.GDIR = os.path.join(os.environ.get("HOME", os.path.expanduser("~")), "gauntlet_band")  # full-agent rows live here (band_gauntlet.py convention)

CRUSTLE_CARD_ID = 345
CRUSTLE_ATTACK_ID = 479
MAIN_SELECT_TYPE = 0
ATTACK_OPTION_TYPE = 13


def _opt_type(o):
    return o.get("type") if isinstance(o, dict) else getattr(o, "type", None)


def _opt_attack_id(o):
    return o.get("attackId") if isinstance(o, dict) else getattr(o, "attackId", None)


def play_instrumented(name, N, seed0):
    deck_o = G.opp_deck(name)
    us = lo = draw = 0
    outcomes = []
    our_turns = 0
    crustle_attacks = 0
    payable_decisions = 0
    payable_games = 0
    attack_games = 0
    err = None
    DECISION_CAP = 3000
    for g in range(N):
        random.seed(seed0 + g)
        us_seat = g % 2
        try:
            opp = G.load_opp_fresh(name)
        except Exception:
            if err is None:
                err = "LOAD: " + traceback.format_exc(limit=4)
            lo += 1
            outcomes.append("L")
            continue
        G.reset_our()
        decks = (G.our.DECK, deck_o) if us_seat == 0 else (deck_o, G.our.DECK)
        if G._crn:
            G._crn.PtcgCrnSetSeed(G._crn_game_seed(seed0, g))
            G._crn.PtcgCrnMode(1)
        try:
            obs, sd = G.battle_start(decks[0], decks[1])
        finally:
            if G._crn:
                G._crn.PtcgCrnMode(0)
        if G._crn and G._crn.PtcgCrnBattleDraws() == 0:
            sys.exit("CRN interposition inactive -- abort (see gauntlet.py note).")
        if sd.errorPlayer >= 0:
            print("DECK_ERROR player=%d type=%d" % (sd.errorPlayer, sd.errorType))
            sys.exit(1)
        steps = 0
        aborted = None
        game_payable = False
        game_attacked = False
        while obs["current"]["result"] < 0 and steps < DECISION_CAP:
            yi = obs["current"]["yourIndex"]
            logs = obs.get("logs") or []
            for lg in logs:
                lt = lg.get("type") if isinstance(lg, dict) else None
                if lt == 2 and lg.get("playerIndex") == us_seat:      # TurnStart
                    our_turns += 1
                if lt == 15 and lg.get("playerIndex") == us_seat:     # Attack
                    if lg.get("cardId") == CRUSTLE_CARD_ID and lg.get("attackId") == CRUSTLE_ATTACK_ID:
                        crustle_attacks += 1
                        game_attacked = True
            if yi == us_seat:
                sel_block = obs.get("select") or {}
                stype = sel_block.get("type")
                options = sel_block.get("option") or []
                if stype == MAIN_SELECT_TYPE:
                    has_payable = any(
                        _opt_type(o) == ATTACK_OPTION_TYPE and _opt_attack_id(o) == CRUSTLE_ATTACK_ID
                        for o in options
                    )
                    if has_payable:
                        payable_decisions += 1
                        game_payable = True
                try:
                    sel = G.our.agent(obs)
                    n = len(options)
                    ok = (isinstance(sel, list)
                          and all(isinstance(i, int) and 0 <= i < n for i in sel)
                          and len(set(sel)) == len(sel))
                    if not ok:
                        aborted = "illegal"
                        break
                except Exception:
                    aborted = "crash"
                    if err is None:
                        err = "RUN(our): " + traceback.format_exc(limit=4)
                    break
            else:
                try:
                    sel = opp.agent(obs)
                except Exception:
                    aborted = "crash"
                    if err is None:
                        err = "RUN(opp): " + traceback.format_exc(limit=4)
                    break
            if G._crn:
                G._crn.PtcgCrnMode(1)
            try:
                obs = G.battle_select(sel)
            finally:
                if G._crn:
                    G._crn.PtcgCrnMode(0)
            steps += 1
        r = obs["current"]["result"]
        G.battle_finish()
        won = False
        if aborted:
            lo += 1
        elif r < 0:
            lo += 1  # cap: conservative our loss (mechanism-instrument run, not the gate number)
        elif r == 2:
            draw += 1
        elif r == us_seat:
            us += 1
            won = True
        else:
            lo += 1
        outcomes.append("W" if won else ("D" if (r == 2 and not aborted) else "L"))
        if game_payable:
            payable_games += 1
        if game_attacked:
            attack_games += 1
    tot = us + lo + draw
    return {
        "us": us, "lo": lo, "draw": draw, "tot": tot,
        "outcomes": "".join(outcomes),
        "our_turns": our_turns, "crustle_attacks": crustle_attacks,
        "payable_decisions": payable_decisions,
        "payable_games": payable_games, "attack_games": attack_games,
        "err": err,
    }


def main():
    name = sys.argv[1]
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    seed0 = int(sys.argv[3]) if len(sys.argv) > 3 else 12345
    r = play_instrumented(name, N, seed0)
    print("BANDROW,%s,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s" % (
        name, seed0, r["us"], r["tot"], r["draw"], 0, 0,
        0, 0, 0, 0, 0, 0, 0, r["outcomes"]))
    print("MECHROW,%s,%d,%d,%d,%d,%d,%d,%d" % (
        name, seed0, r["tot"], r["our_turns"], r["crustle_attacks"],
        r["payable_decisions"], r["payable_games"], r["attack_games"]))
    if r["err"]:
        print("ERR: " + r["err"])


if __name__ == "__main__":
    main()
