"""Search-API exact-resolution oracle (the R1 differentiator).

For each legal attack this turn we determinize the hidden zones (kiyotah recipe
from intel/kiyotah_rl_mcts_extracted_source.py mcts_agent()), step the attack via
the engine's own resolver, follow any forced sub-selections that are still ours
(e.g. Jetting Blow's bench-snipe target), and read the EXACT result: did it win,
did it KO the defender, how many prizes it took, and the damage dealt.

Per intel/engine_bringup_2026-07-11.md: immediate outcomes are exact regardless
of hidden-zone filler, so this-turn damage/lethal needs no belief model. Every
search call is guarded and search_end() always runs.
"""

import os
import random
import time

from cg.api import search_begin, search_step, search_end, OptionType, SelectContext
import obs as O
import scoring as SC
import belief as BEL

# Junk determinization fillers (kiyotah recipe / bring-up benchmark).
JUNK_POKEMON = 1072   # Snorlax (a Basic Pokemon) - verified basic in card DB
JUNK_ENERGY = 1       # Basic {G} Energy - verified BASIC_ENERGY in card DB

# R3 diagnostics: how often the belief-informed opponent filler was used vs junk.
BELIEF_DIAG = {"belief_fill": 0, "junk_fill": 0}

# Tracker-exact own-zone determinization gate (default ON; PTCG_EXACT_DET=0 restores
# byte-identical old behavior for CRN A/B). See intel/exact_det_patch_2026-07-16.md.
EXACT_DET_ENABLED = os.environ.get("PTCG_EXACT_DET", "1") != "0"
EXACT_DET_DIAG = {"exact": 0, "fallback": 0}


def _expand_counter(counter):
    """Counter -> shuffled flat list of card ids (one entry per copy)."""
    out = []
    for cid, cnt in counter.items():
        out.extend([cid] * int(cnt))
    random.shuffle(out)
    return out


def _exact_own_zones(me, tracker):
    """Try to build (your_deck, your_prize) from opp_tracker's exact own-side knowledge.
    Returns (your_deck, your_prize) sized exactly to me.deckCount/len(me.prize), or None
    if the tracker can't supply consistent exact knowledge (caller fails open to the
    random.sample path). Any mismatch or exception -> None; never guesses."""
    if tracker is None:
        return None
    try:
        prize_ms = tracker.our_prize_known()
        deck_ms = tracker.our_deck_ms()
        if prize_ms is None or deck_ms is None:
            return None
        dc = me.deckCount
        pc = len(me.prize)
        if sum(deck_ms.values()) != dc:
            return None
        if sum(prize_ms.values()) != pc:
            return None
        your_deck = _expand_counter(deck_ms)
        your_prize = _expand_counter(prize_ms)
        if len(your_deck) != dc or len(your_prize) != pc:
            return None
        return your_deck, your_prize
    except Exception:
        return None


def _belief_opponent_zones(op, rep_counts, revealed_ids):
    """Complete the opponent's hidden zones (deck / hand / prize) from a representative
    archetype decklist minus the cards already revealed (R3 belief determinization).

    Returns (opponent_deck, opponent_hand, opponent_prize) sized to the observation.
    Pads with junk energy if the revealed cards exceed the representative multiset."""
    pool = {}
    for cid, cnt in rep_counts.items():
        pool[cid] = pool.get(cid, 0) + cnt
    for cid in revealed_ids:
        if pool.get(cid, 0) > 0:
            pool[cid] -= 1
    remaining = []
    for cid, cnt in pool.items():
        remaining.extend([cid] * cnt)
    random.shuffle(remaining)
    need = op.deckCount + op.handCount + len(op.prize)
    if len(remaining) < need:
        remaining.extend([JUNK_ENERGY] * (need - len(remaining)))
    dc, hc = op.deckCount, op.handCount
    return remaining[:dc], remaining[dc:dc + hc], remaining[dc + hc:need]


def _determinize(observation, my_deck, belief=None, tracker=None):
    """search_begin. Our hidden zones: if `tracker` (opp_tracker.Tracker) has exact
    own-side knowledge (our_prize_known()/our_deck_ms() both Counters sized exactly to
    this state) and PTCG_EXACT_DET is on, your_deck/your_prize are built from that exact
    multiset -- no double-counting of cards already in hand/board/discard, no ignoring
    known prizes. Otherwise (tracker off/None/inexact/mismatched) falls back byte-
    identically to the old random.sample-from-full-60 recipe. The opponent's hidden zones
    use kiyotah's junk filler UNLESS a confident belief supplies a representative
    archetype decklist (R3), in which case they are completed from that list minus
    revealed cards. May raise; caller guards."""
    state = observation.current
    yi = state.yourIndex
    me = state.players[yi]
    op = state.players[1 - yi]

    dc = me.deckCount
    pc = len(me.prize)
    exact = _exact_own_zones(me, tracker) if EXACT_DET_ENABLED else None
    if exact is not None:
        your_deck, your_prize = exact
        EXACT_DET_DIAG["exact"] += 1
    else:
        EXACT_DET_DIAG["fallback"] += 1
        # your_deck / your_prize sampled from our own 60-card list (kiyotah recipe;
        # bring-up pitfall #7 notes the engine accepts the possible double-count).
        if my_deck and dc <= len(my_deck):
            your_deck = random.sample(my_deck, dc)
        else:
            your_deck = [random.choice(my_deck) for _ in range(dc)] if my_deck else [JUNK_ENERGY] * dc
        if my_deck and pc <= len(my_deck):
            your_prize = random.sample(my_deck, pc)
        else:
            your_prize = [random.choice(my_deck) for _ in range(pc)] if my_deck else [JUNK_ENERGY] * pc

    op_active = op.active
    opponent_active = [JUNK_POKEMON] if (len(op_active) > 0 and op_active[0] is None) else []

    rep = belief.rep_deck() if belief is not None else None
    if rep:
        revealed = set(belief.revealed)
        opp_deck, opp_hand, opp_prize = _belief_opponent_zones(op, rep, revealed)
        BELIEF_DIAG["belief_fill"] += 1
    else:
        opp_deck = [JUNK_POKEMON] * op.deckCount
        opp_hand = [JUNK_ENERGY] * op.handCount
        opp_prize = [JUNK_ENERGY] * len(op.prize)
        BELIEF_DIAG["junk_fill"] += 1

    return search_begin(
        observation,
        your_deck=your_deck,
        your_prize=your_prize,
        opponent_deck=opp_deck,
        opponent_prize=opp_prize,
        opponent_hand=opp_hand,
        opponent_active=opponent_active,
    )


def _active_hp(state, pidx):
    ps = state.players[pidx]
    if ps.active and ps.active[0] is not None:
        return ps.active[0].hp, ps.active[0].serial
    return None, None


def _greedy_subchoice(observation, my_index):
    """Pick a reasonable selection for a forced sub-step during attack resolution.
    For opponent-Pokemon damage placement (e.g. bench snipe) prefer the target
    with the lowest remaining HP (most likely KO); otherwise first-N legal."""
    sel = observation.select
    n = len(sel.option)
    mn = sel.minCount or 0
    mx = sel.maxCount or 1
    yi = observation.current.yourIndex
    # damage-placement style contexts: options are CARD referencing a Pokemon.
    best = []
    scored = []
    tcl = None
    for i, o in enumerate(sel.option):
        card = None
        try:
            if o.playerIndex is not None and o.area is not None:
                card = O.get_card(observation, o.area, o.index, o.playerIndex)
        except Exception:
            card = None
        if card is not None and hasattr(card, "hp") and o.playerIndex is not None and o.playerIndex != yi:
            if SC.P2:
                # P2: same shared target score the LIVE pick uses, so the oracle's
                # simulated Jetting Blow line and the executed one aim at the same
                # Pokemon (design review sec.2: oracle/live target inconsistency).
                # v5/R4: the denial bonus needs board context -- build it once so the
                # simulated and executed snipes still agree.
                if SC.R4 and tcl is None:
                    try:
                        tcl = SC.TurnCtx(observation)
                    except Exception:
                        tcl = None
                scored.append((-SC.damage_target_score(card, 50, tc=tcl), i))
            else:
                # opponent Pokemon: prefer lowest hp (easiest KO)
                scored.append((card.hp, i))
    if scored:
        scored.sort()
        best = [i for _, i in scored]
        return O.clamp_selection(best, mn, mx, n)
    return O.clamp_selection(list(range(n)), mn, mx, n)


def resolve_attack(observation, my_deck, attack_option_index, max_steps=16, tracker=None):
    """Resolve one attack option from the current state.

    Returns dict {ok, wins, ko_active, prizes_taken, def_dmg, resigns} or None.
    'resigns' True if resolution left us (our own active) knocked out / decked.
    """
    state = observation.current
    yi = state.yourIndex
    my_prizes_before = len(state.players[yi].prize)
    def_hp_before, _def_serial_before = _active_hp(state, 1 - yi)

    ss = None
    try:
        ss = _determinize(observation, my_deck, tracker=tracker)
    except Exception:
        try:
            search_end()
        except Exception:
            pass
        return None

    try:
        ss = search_step(ss.searchId, [attack_option_index])
        steps = 0
        while True:
            cur = ss.observation.current
            if cur is None or cur.result >= 0:
                break
            if cur.yourIndex != yi:
                break  # control passed to opponent -> our attack has resolved
            sel = ss.observation.select
            if sel is None or len(sel.option) == 0:
                break
            if steps >= max_steps:
                break
            choice = _greedy_subchoice(ss.observation, yi)
            ss = search_step(ss.searchId, choice)
            steps += 1

        cur = ss.observation.current
        if cur is None:
            return None
        result = cur.result
        if result >= 0:
            wins = (result == yi)
            return {"ok": True, "wins": wins, "ko_active": wins,
                    "prizes_taken": my_prizes_before, "def_dmg": (def_hp_before or 0),
                    "resigns": (not wins and result != 2)}

        my_prizes_after = len(cur.players[yi].prize)
        prizes_taken = my_prizes_before - my_prizes_after
        def_hp_after, def_serial_after = _active_hp(cur, 1 - yi)
        if SC.P2:
            # P2 KO-attribution fix (design review sec.2): the defender is KO'd iff
            # the active slot emptied or now holds a different (promoted) Pokemon.
            # Under the old `prizes_taken > 0` rule a Jetting Blow BENCH KO was
            # mislabeled as an active KO and skewed attack choice.
            ko_active = (def_hp_after is None
                         or (def_serial_after is not None
                             and _def_serial_before is not None
                             and def_serial_after != _def_serial_before))
            if ko_active:
                def_dmg = def_hp_before or 0
            else:
                def_dmg = max(0, (def_hp_before or 0) - (def_hp_after or 0))
        else:
            # KO of the defender: we took a prize, OR their active slot is now empty /
            # occupied by a freshly promoted (different) Pokemon.
            ko_active = prizes_taken > 0
            def_dmg = 0
            if def_hp_before is not None:
                if def_hp_after is None:
                    ko_active = True
                    def_dmg = def_hp_before
                else:
                    def_dmg = max(0, def_hp_before - def_hp_after)
        # our own active KO'd (bad trade signal)
        my_hp_after, _ = _active_hp(cur, yi)
        resigns = False
        return {"ok": True, "wins": False, "ko_active": ko_active,
                "prizes_taken": max(0, prizes_taken), "def_dmg": def_dmg,
                "resigns": resigns}
    except Exception:
        return None
    finally:
        try:
            search_end()
        except Exception:
            pass


# =====================================================================================
# R2: multi-turn determinization-ensemble turn-line search.
#
# At a MAIN "crux" we compare a small set of candidate turn PLANS (policies) instead of
# greedily taking the top-priority option. Each plan is a set of mode flags that reshape
# the R1 greedy scorer (scoring.score_main); we roll the plan to end-of-turn by threading
# search_step from the determinized root, evaluate the resulting position with the linear
# value function (scoring.position_value), average over K determinizations, and return the
# best plan's FIRST action. The R1 greedy pick (the 'default' plan) is always a candidate,
# so we never return worse than R1. Everything is gated on a monotonic deadline and every
# Search-API call is guarded (a fault trips the caller's circuit breaker).
# =====================================================================================

MAX_ROLLOUT_STEPS = 20        # our-turn line length cap (our turn is ~5-12 real steps)
OPP_ROLLOUT_STEPS = 18        # additional cap for rolling the opponent's reply (R3)
# Require a clear mean-value improvement to override the R1 floor. With K determinizations
# the per-plan mean is noisy; a small margin causes winner's-curse overrides, so we keep it
# well above the rollout noise floor (a fraction of one prize).
OVERRIDE_MARGIN = 150.0


def _distinct_attack_ids(sel):
    ids = []
    for o in sel.option:
        if O.opt_type(o) == OptionType.ATTACK and o.attackId is not None and o.attackId not in ids:
            ids.append(o.attackId)
    return ids


def _bench_has_attacker(tc):
    for p in (tc.me.bench or []):
        if p is not None and (p.id in SC.MAIN_ATTACKERS or p.id == SC.STARYU):
            return True
    return False


def candidate_policies(observation, tc):
    """Enumerate plausible turn plans for the current MAIN state (pre-pruned; we do NOT
    brute-force multi-select combos). Always includes the R1 greedy 'default' plan."""
    sel = observation.select
    types = [O.opt_type(o) for o in sel.option]
    plans = [("default", {})]

    atk_ids = _distinct_attack_ids(sel)
    has_attack = len(atk_ids) > 0
    has_retreat = OptionType.RETREAT in types
    has_energy_attach = any(
        O.opt_type(o) == OptionType.ATTACH for o in sel.option)
    bench_attacker = _bench_has_attacker(tc)
    active = tc.active
    active_is_attacker = active is not None and active.id in SC.MAIN_ATTACKERS

    # Attack SELECTION stays with R1's exact oracle (already strong); the search only fixes
    # R1's structural gaps. Banking (route the turn's energy onto the benched successor rather
    # than the active) only pays off when THIS active is about to die -- otherwise it just
    # costs active damage on a 330-HP wall that rarely gets KO'd. So we only offer the bank
    # plan when the active is damaged past 40% or is under a return-KO threat next turn; the
    # active still attacks this turn (rollout max-damage pick).
    active_dying = False
    if active is not None:
        opp_act = tc.op.active[0] if (tc.op.active and tc.op.active[0] is not None) else None
        hp = getattr(active, "hp", 0)
        mx = getattr(active, "maxHp", hp) or hp
        active_dying = (hp <= 0.6 * mx
                        or SC.opp_best_attack_damage(opp_act, active) >= hp)
    if ((has_attack or (has_energy_attach and active_is_attacker))
            and bench_attacker and active_dying):
        plans.append(("bank", {"energy_to_bench": True}))

    # Reposition: force_retreat is implemented and searchable, but on this energy-discard-
    # averse deck (Mega Starmie retreatCost=2) evaluated retreat lines consistently LOST in
    # A/B (the eval underweights the strategic tempo cost of dumping the attacker's energy).
    # R1 correctly never retreats; we keep retreat OUT of the candidate set. Honest negative;
    # see intel/agent_R2_results.md. (Left as `has_retreat` no-op for an R3 revisit.)
    _ = has_retreat

    # conditional self-KO (Cursed Blast) only when a KO target exists
    has_selfko_ability = False
    for o in sel.option:
        if O.opt_type(o) == OptionType.ABILITY:
            card = O.get_card(observation, o.area, o.index, tc.yi)
            if card is not None and card.id in SC.SELF_KO_ABILITY_DAMAGE:
                has_selfko_ability = True
    if has_selfko_ability:
        plans.append(("selfko", {"allow_selfko": True}))

    return plans


def _rollout(root_id, root_obs, me, policy, prizes_before, deadline, opp_rollout=False):
    """Execute one turn plan from a determinized root; return (value, first_selection).

    Phase 1 ('ours'): roll OUR candidate turn plan to end-of-turn (score_main + policy).
    Phase 2 ('opp', R3): if opp_rollout, continue rolling the OPPONENT's greedy reply
    (their max-damage attack line -- score_main with no policy naturally develops, attaches
    to the active and attacks for the biggest hit) until control returns to us. This yields
    the position we ACTUALLY face after their reply -- with return-KO / prize-race awareness
    baked into the evaluated state -- instead of a static opponent-threat estimate.

    first_selection is our plan's first action at the root (the only thing we may return)."""
    cur_id = root_id
    cur_obs = root_obs
    first_sel = None
    steps = 0
    phase = "ours"
    cap = MAX_ROLLOUT_STEPS + (OPP_ROLLOUT_STEPS if opp_rollout else 0)
    while steps < cap:
        cur = cur_obs.current
        if cur is None or cur.result >= 0:
            break
        yidx = cur.yourIndex
        if phase == "ours":
            if yidx != me:
                if not opp_rollout:
                    break               # R2 behaviour: stop at end of our turn
                phase = "opp"           # R3: roll the opponent's reply
                continue
            rollout_policy = policy
        else:  # phase == "opp"
            if yidx == me:
                break                   # opponent's reply is done -> evaluate here
            rollout_policy = None       # opponent plays a plain greedy max-damage turn
        sel = cur_obs.select
        if sel is None or len(sel.option) == 0:
            break
        n = len(sel.option)
        if int(sel.context) == SelectContext.MAIN:
            tcl = SC.TurnCtx(cur_obs)
            scores = SC.score_main(cur_obs, tcl, None, rollout_policy)
            choice = SC.select_by_scores(scores, sel, n)
        else:
            choice = _greedy_subchoice(cur_obs, yidx)
        if not choice and (sel.minCount or 0) > 0:
            choice = O.clamp_selection(list(range(n)), sel.minCount, sel.maxCount, n)
        if first_sel is None and phase == "ours":
            first_sel = list(choice)
        nxt = search_step(cur_id, choice)       # returns a SearchState
        cur_obs = nxt.observation
        cur_id = nxt.searchId
        steps += 1
        if deadline is not None and time.monotonic() > deadline:
            break
    val = SC.position_value(cur_obs.current, me, prizes_before)
    return val, first_sel


LAST_MEANS = {}                                 # diagnostics: means of the last searched crux
PLAN_DIAG = {"searched": 0, "best": {}, "beat_but_margin": 0, "gap_sum": 0.0}


def plan_decision(observation, my_deck, tc, deadline, K, belief=None, opp_rollout=False, tracker=None):
    """Search the turn plans and return (override_selection or None, broke, best_label).
    override_selection is None when the R1 greedy floor is not beaten. `broke` True
    signals the caller to trip the search circuit breaker for the rest of the game.

    R3: `belief` (a belief.BeliefState) supplies the opponent's hidden zones for a
    belief-informed determinization; `opp_rollout` rolls the opponent's greedy reply after
    our line so the evaluated position reflects the actual return-KO / prize race.
    `tracker` (opp_tracker.Tracker) supplies exact own-zone determinization when possible
    (see _determinize / _exact_own_zones); fails open when not exact."""
    plans = candidate_policies(observation, tc)
    if len(plans) <= 1:
        return None, False, "default"           # no real choice -> greedy floor

    me = observation.current.yourIndex
    prizes_before = len(observation.current.players[me].prize)
    sums = {label: 0.0 for label, _ in plans}
    firsts = {label: None for label, _ in plans}
    counts = {label: 0 for label, _ in plans}

    dets = 0
    for _k in range(K):
        if time.monotonic() > deadline:
            break
        ss = None
        try:
            ss = _determinize(observation, my_deck, belief, tracker=tracker)
        except Exception:
            try:
                search_end()
            except Exception:
                pass
            continue                            # a determinization sample failed -> skip it
        try:
            root_id = ss.searchId
            root_obs = ss.observation
            for label, policy in plans:
                if time.monotonic() > deadline:
                    break
                try:
                    val, first_sel = _rollout(root_id, root_obs, me, policy,
                                              prizes_before, deadline, opp_rollout)
                except Exception:
                    continue                    # a rollout sample failed -> skip it
                if first_sel is None:
                    continue
                sums[label] += val
                counts[label] += 1
                if firsts[label] is None:
                    firsts[label] = first_sel
            dets += 1
        except Exception:
            return None, True, None             # anomaly mid-tree -> circuit break
        finally:
            try:
                search_end()
            except Exception:
                return None, True, None

    if dets == 0:
        return None, False, "default"

    means = {label: (sums[label] / counts[label]) for label in sums if counts[label] > 0}
    globals()["LAST_MEANS"] = means
    PLAN_DIAG["searched"] += 1
    if "default" not in means:
        return None, False, "default"
    best_label = max(means, key=lambda l: means[l])
    PLAN_DIAG["best"][best_label] = PLAN_DIAG["best"].get(best_label, 0) + 1
    if best_label == "default":
        return None, False, "default"
    if firsts.get(best_label) is None:
        return None, False, "default"
    gap = means[best_label] - means["default"]
    if gap <= OVERRIDE_MARGIN:
        PLAN_DIAG["beat_but_margin"] += 1
        return None, False, "default"
    # Scope: only override with a STRUCTURAL first action (retreat / bench-attach / self-KO
    # ability). If the winning plan's first action is an ATTACK, defer to R1's oracle, which
    # selects the attack exactly -- the rollout's static attack pick must not override it.
    first_sel = firsts[best_label]
    opts = observation.select.option
    if any(0 <= i < len(opts) and O.opt_type(opts[i]) == OptionType.ATTACK for i in first_sel):
        return None, False, "default"
    PLAN_DIAG["gap_sum"] += gap
    return first_sel, False, best_label
