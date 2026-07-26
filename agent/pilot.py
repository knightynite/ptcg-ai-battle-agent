"""_pilot: parse -> (lethal oracle | turn-plan search | greedy floor) -> legal selection.

R2 restructures the R1 greedy pilot into a searched pilot while keeping R1's greedy
pick as the guaranteed floor. Sequencing still follows the kiyotah/ichigoe greedy MAIN
pattern (the engine re-presents MAIN after each sub-action), but at a consequential MAIN
"crux" we run search.plan_decision -- a multi-turn determinization-ensemble over candidate
turn plans -- and override the greedy pick only when a plan is strictly better.

The six Codex v0.1 crash-safety fixes are folded in here:
  #1 monotonic per-decision deadline threaded into the search (this is R2's budget hook);
  #2 elapsed time charged in a `finally` so exceptions still bank the clock;
  #3 the oracle/search runs only when it can change the choice (crux gate);
  #4 legality of the smart result is gated before it is returned (main.py re-gates too);
  #6 a per-game search circuit breaker disables search after a Search-API anomaly.
"""

import os
import time

from cg.api import OptionType, SelectContext
import obs as O
import scoring as SC
import search as SE
import belief as BEL
import opp_tracker as OT

# Turn-plan search is OFF by default. A 2,160-game ablation (intel/agent_R2_results.md) showed the
# determinization-ensemble turn-plan search is net -2.5% meta-weighted vs R1's exact oracle on this
# deck (the oracle already captures the single-turn tactical value; the remaining gap is strategic).
# The full, validated search machinery ships intact and is opt-in via PTCG_SEARCH=1 for the ablation
# and R3 work. Default off = the WR-maximizing, strictly-non-regressing ladder config.
# FINAL LADDER TUNING (intel/final_tuning_2026-07-11.md; 18,000 games, N=600/opp x 3 seeds): the
# belief-search-no-rollout config (PTCG_SEARCH=1 PTCG_BELIEF=1 PTCG_OPP_ROLLOUT=0) scored 46.0% meta
# vs R1 44.6% -- +1.4pp directional but NOT a confident beat (95% CIs overlap; wins 2/3 seeds). Per
# the strictly-non-regressing rule, R1 (search OFF) remains the shipped default.
_SEARCH_ENABLED = os.environ.get("PTCG_SEARCH", "0") == "1"
# R3 knobs (only relevant when search is enabled): belief-informed opponent determinization and
# the opponent-turn rollout. Both default ON when search is on (the R3 config); each can be
# disabled independently for the belief-vs-junk and rollout-on/off ablations.
_BELIEF_ENABLED = os.environ.get("PTCG_BELIEF", "1") == "1"
_OPP_ROLLOUT = os.environ.get("PTCG_OPP_ROLLOUT", "1") == "1"

DECK = []  # injected by main.py after loading deck.csv

# --- clock / budget ---
_game_elapsed = 0.0
_last_turn = -1
_search_disabled = False          # circuit breaker (fix #6); reset per game
_belief = BEL.BeliefState()       # per-game opponent belief (R3); reset on new game
SC.BELIEF = _belief               # v3: expose the belief to scoring (P5/P3 gating);
                                  # same object, reset per game, updated every decision
_tracker = OT.Tracker()           # v4: hidden-state tracker (opp_tracker Phases 1+2);
SC.TRACKER = _tracker             # reset per game, fed every REAL obs; any failure
                                  # disables it for the game (consumers -> v3 behavior)
SEARCH_RESERVE_SEC = 480.0        # drop to pure heuristic once the game clock is high
PER_DECISION_BUDGET = 2.5         # hard per-decision search deadline (fix #1); << Kaggle 7.5s
SEARCH_K = 10                     # determinizations per crux (tuned on the gauntlet)

# Diagnostics (read by tools; zero cost otherwise).
STATS = {"main": 0, "crux": 0, "override": 0, "lethal": 0, "broke": 0}
OVR_LABELS = {}


def _update_clock(state):
    global _game_elapsed, _last_turn, _search_disabled
    turn = state.turn if state.turn is not None else 0
    if _last_turn < 0 or turn < _last_turn:  # new game (turn counter reset)
        if _last_turn >= 0 and SC.SUPPLY_DEBUG:
            # Lever 3 (intel/supply_rule_2026-07-16.md): per-game mechanism instrument
            # summary to stderr, best-effort, never blocks the new-game reset.
            try:
                import sys
                d = SC.supply_diag_summary()
                sys.stderr.write("SUPPLYDIAG %s\n" % d)
                sys.stderr.flush()
            except Exception:
                pass
            for k in SC._SUPPLY_DIAG:
                SC._SUPPLY_DIAG[k] = 0
        if _last_turn >= 0 and SC.DISCIPLINE_DEBUG:
            # discipline rule (intel/discipline_rule_2026-07-16.md): per-game mechanism
            # instrument summary to stderr, best-effort, never blocks the new-game reset.
            try:
                import sys
                d = SC.discipline_diag_summary()
                sys.stderr.write("DISCIPLINEDIAG %s\n" % d)
                sys.stderr.flush()
            except Exception:
                pass
            for k in SC._DISCIPLINE_DIAG:
                SC._DISCIPLINE_DIAG[k] = 0
        _game_elapsed = 0.0
        _search_disabled = False             # re-enable search for the new game
        _belief.reset()                      # fresh opponent belief per game (R3)
        try:
            _tracker.reset(DECK)             # fresh hidden-state tracker per game (v4)
        except Exception:
            try:
                _tracker.ok = False
            except Exception:
                pass
    _last_turn = turn


def _eval_attacks(obs, tc, obs_dict, allow_search):
    """Resolve every legal ATTACK option via the Search-API oracle (lethal detection)."""
    ev = {}
    best_dmg = 0
    attack_idxs = [i for i, o in enumerate(obs.select.option)
                   if O.opt_type(o) == OptionType.ATTACK]
    if not attack_idxs:
        ev["_best_dmg"] = 0
        return ev

    if getattr(obs, "search_begin_input", None) is None:
        try:
            obs.search_begin_input = obs_dict.get("search_begin_input")
        except Exception:
            pass

    can_search = bool(allow_search and getattr(obs, "search_begin_input", None) and DECK)
    for i in attack_idxs:
        r = SE.resolve_attack(obs, DECK, i, tracker=_tracker) if can_search else None
        ev[i] = r
        if r:
            if r.get("wins"):
                best_dmg = max(best_dmg, 99999)
            elif r.get("ko_active"):
                best_dmg = max(best_dmg, 400)
            else:
                best_dmg = max(best_dmg, r.get("def_dmg", 0))
        else:
            best_dmg = max(best_dmg, 1)  # unknown -> assume active can attack (veto retreat)
    ev["_best_dmg"] = best_dmg
    return ev


def _select(scores, sel, n):
    return SC.select_by_scores(scores, sel, n)


def _lethal_index(sel, attack_eval):
    """Option index of a this-turn winning attack, if the oracle found one."""
    for i, o in enumerate(sel.option):
        if O.opt_type(o) == OptionType.ATTACK:
            ev = attack_eval.get(i)
            if ev and ev.get("wins"):
                return i
    return None


def _legal(selection, sel, n):
    """Fix #4: validate a smart selection before returning it (unique in-range ints,
    count within [minCount, maxCount])."""
    if not isinstance(selection, list):
        return False
    if any((not isinstance(i, int)) or i < 0 or i >= n for i in selection):
        return False
    if len(set(selection)) != len(selection):
        return False
    mn = sel.minCount if sel.minCount is not None else 0
    mx = sel.maxCount if sel.maxCount is not None else 1
    mx = min(mx, n)
    return mn <= len(selection) <= mx


def _worth_searching(obs, tc, greedy_pick, sel):
    """Fix #3: only search when it can change the choice. The consequential MAIN cruxes
    are: the greedy would attack or end now; a benched second-attacker banking decision;
    a reposition; or a Cursed Blast that could secure a KO. Everything else is greedy."""
    if not greedy_pick:
        return False
    top = greedy_pick[0]
    tt = O.opt_type(sel.option[top])
    if tt in (OptionType.ATTACK, OptionType.END):
        return True
    bench_attacker = any(p is not None and (p.id in SC.MAIN_ATTACKERS or p.id in SC.FEEDER_BASICS)
                         for p in (tc.me.bench or []))
    active_is_attacker = tc.active is not None and tc.active.id in SC.MAIN_ATTACKERS
    if tt == OptionType.ATTACH and bench_attacker and active_is_attacker:
        return True
    for op in sel.option:
        ot = O.opt_type(op)
        if ot == OptionType.RETREAT and bench_attacker:
            return True
        if ot == OptionType.ABILITY:
            c = O.get_card(obs, op.area, op.index, tc.yi)
            if (c is not None and c.id in SC.SELF_KO_ABILITY_DAMAGE
                    and SC._opponent_can_be_ko_by_ability(
                        tc, SC.SELF_KO_ABILITY_DAMAGE[c.id]) is not None):
                return True
    return False


def _pilot(obs_dict):
    global _game_elapsed, _search_disabled
    t0 = time.monotonic()
    try:
        obs = O.to_observation_class(obs_dict)
        state = obs.current
        sel = obs.select
        if state is None or sel is None:
            return []
        n = len(sel.option)
        if n == 0:
            return []

        _update_clock(state)
        # R3: fold newly-revealed opponent cards into the archetype belief (cheap, guarded).
        try:
            _belief.update(obs)
        except Exception:
            pass
        # v4: feed the hidden-state tracker the raw obs (REAL battle obs only -- never
        # search-sim obs). update() is exception-proof; belt-and-braces guard anyway.
        try:
            _tracker.update(obs_dict)
        except Exception:
            try:
                _tracker.ok = False
            except Exception:
                pass
        # allow_search gates the Search-API (oracle + plan); allow_plan additionally requires
        # the opt-in turn-plan search flag (default off -- see _SEARCH_ENABLED note above).
        allow_search = (not _search_disabled) and (_game_elapsed < SEARCH_RESERVE_SEC)
        allow_plan = allow_search and _SEARCH_ENABLED
        deadline = t0 + PER_DECISION_BUDGET

        ctx = int(sel.context) if sel.context is not None else -1
        tc = SC.TurnCtx(obs)

        if ctx != SelectContext.MAIN:
            return _select(SC.score_generic(obs, tc, ctx), sel, n)

        # --- MAIN ---
        STATS["main"] += 1
        attack_eval = _eval_attacks(obs, tc, obs_dict, allow_search)
        greedy_pick = _select(SC.score_main(obs, tc, attack_eval), sel, n)  # R1 floor

        # 1) lethal shortcut (keep R1's win): a this-turn winning attack -> take it now
        lethal = _lethal_index(sel, attack_eval)
        if lethal is not None:
            STATS["lethal"] += 1
            return [lethal]

        # 2) turn-plan search, only at a crux and only within budget
        if allow_plan and time.monotonic() < deadline and _worth_searching(
                obs, tc, greedy_pick, sel):
            STATS["crux"] += 1
            try:
                belief = _belief if _BELIEF_ENABLED else None
                override, broke, label = SE.plan_decision(
                    obs, DECK, tc, deadline, SEARCH_K, belief, _OPP_ROLLOUT, tracker=_tracker)
            except Exception:
                override, broke, label = None, True, None
            if broke:
                STATS["broke"] += 1
                _search_disabled = True
            if override is not None and _legal(override, sel, n):
                STATS["override"] += 1
                OVR_LABELS[label] = OVR_LABELS.get(label, 0) + 1
                return override

        return greedy_pick
    finally:
        # fix #2: exceptions still bank elapsed time (else search stays enabled while the
        # clock actually drains).
        _game_elapsed += (time.monotonic() - t0)
