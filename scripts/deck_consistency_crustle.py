#!/usr/bin/env python3
"""Deck-consistency analysis for the CURRENT Crustle list (agent/deck_crustle.csv).

Mirrors the method of intel/deck_consistency_starmie.md (2026-07-11) so the two
decks are directly comparable for report section 5.3:
  * exact hypergeometric for all opening-hand / first-N-card probabilities
    (same definitions: opening hand = 7, "first 8" = opening 7 + the turn-1
    draw, mulligan = no Basic Pokemon in the opening 7, unconditional draws);
  * Monte Carlo for the setup curve (mulligan-to-basic redraw, greedy item dig
    + one draw/search supporter per turn, evolve requires player-turn >= 2 and
    the evolving Pokemon must have been in play before the current turn).

Differences from the Starmie run (documented, not silent):
  * 1,000,000 trials per arm with FIXED seed 20260721 (old doc: 40k trials,
    seed unstated).
  * The greedy dig uses THIS deck's dig items (Buddy-Buddy Poffin + Pokegear
    3.0); the Starmie list used Poffin + Ultra Ball. Supporter priority is
    Hilda (search Evolution+Energy) then Lillie's Determination (shuffle-draw
    6) -- the same two setup supporters both lists share.
  * Seat asymmetry grounded in the official engine source
    (intel/engine_src/official/): both players draw at turn start including
    the going-first player's turn 1 (GameProc.h:994), but the going-first
    player cannot play a Supporter on turn 1 (GameProc.h:824) and cannot
    attack on turn 1 (GameProc.h:915). FIRST_HAND=7, PRIZE_SIZE=6,
    DECK_SIZE=60, BENCH_SIZE_DEFAULT=5 (Core.h).
  * Prizes are NOT modeled (the Starmie doc's method makes no mention of
    prize set-aside; the omission is kept so the two analyses stay
    comparable). Consequence: no prize pruning of key copies (optimistic) and
    Lillie draws 6, not the 8 she draws at exactly 6 prizes remaining
    (pessimistic).
  * Baseline arms do NOT model Mega Kangaskhan ex's Run Errand ability or
    Switch (the Starmie method modeled no abilities). A sensitivity variant
    with Run Errand + greedy Switch-to-Kang is reported separately.

Deterministic: stdlib only, single fixed seed, arms run in a fixed order off
one RNG stream. Runnable on Windows: python scripts/deck_consistency_crustle.py
Optional: --trials N (default 1_000_000) for smoke runs.
"""
import os
import sys
import time
import random
import argparse
from collections import Counter
from math import comb

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = 20260721
DECK_SIZE = 60
HAND = 7          # FIRST_HAND (engine Core.h)
BOARD_MAX = 6     # active + BENCH_SIZE_DEFAULT=5 (engine Core.h)
TMAX = 4

# ---- card ids (verified against intel/card_db_full.csv) ----------------------
G_BASIC, MIST, SPIKY, GROW = 1, 11, 14, 18
SHAYMIN, DWEBBLE, CRUSTLE, KANG = 343, 344, 345, 756
POFFIN, TRIMMER, POKEGEAR, SWITCH, ICECREAM, CAPE = 1086, 1087, 1122, 1123, 1147, 1159
BOSS, XEROSIC, HILDA, LILLIE, CAGE = 1182, 1197, 1225, 1227, 1264

ENERGY = {G_BASIC, MIST, SPIKY, GROW}
GRASS = {G_BASIC, GROW}              # sources that can pay Superb Scissors' {G}
BASICS = {SHAYMIN, DWEBBLE, KANG}    # Basic Pokemon in this list (card_db basic=True)

EXPECTED = {G_BASIC: 1, MIST: 4, SPIKY: 4, GROW: 4, SHAYMIN: 1, DWEBBLE: 4,
            CRUSTLE: 4, KANG: 4, POFFIN: 4, TRIMMER: 1, POKEGEAR: 4, SWITCH: 4,
            ICECREAM: 4, CAPE: 1, BOSS: 2, XEROSIC: 4, HILDA: 4, LILLIE: 4,
            CAGE: 2}


def load_deck():
    path = os.path.join(REPO, "agent", "deck_crustle.csv")
    ids = [int(line.strip()) for line in open(path) if line.strip()]
    counts = Counter(ids)
    assert sum(counts.values()) == DECK_SIZE, f"deck size {sum(counts.values())} != 60"
    assert counts == Counter(EXPECTED), f"deck drifted from expected list: {counts}"
    return ids


# ---- exact hypergeometric -----------------------------------------------------
def p_none(k, draw, deck=DECK_SIZE):
    """P(zero of the k copies among the first `draw` cards)."""
    if draw > deck - k:
        return 0.0
    return comb(deck - k, draw) / comb(deck, draw)


def p_any(k, draw, deck=DECK_SIZE):
    return 1.0 - p_none(k, draw, deck)


# ---- Monte Carlo setup-curve model --------------------------------------------
def simulate_arm(rng, going_first, run_errand, trials):
    """One arm. Returns dict of cumulative-by-turn probabilities.

    Turn model (mirrors deck_consistency_starmie.md's stated method):
      setup: draw 7, mulligan-to-basic (redraw 7 until >=1 Basic); play ALL
        Basics (active + bench, board cap 6).
      each of our turns t=1..TMAX:
        - draw 1 (both seats -- engine draws at every turn start);
        - [variant only] Switch to Mega Kangaskhan ex if benched, then Run
          Errand: draw 2 while Kang is active;
        - development pass: bench Basics from hand, play every Buddy-Buddy
          Poffin (fetch up to 2 Dwebble to bench), evolve Dwebble->Crustle if
          t>=2 and the Dwebble was in play before this turn;
        - play every Pokegear 3.0 (top 7; take Hilda, else Lillie);
        - ONE supporter (blocked on our turn 1 when going first, per engine):
          Hilda if she can fetch a missing Crustle or missing Energy, else
          Lillie's Determination if a need remains (shuffle hand, draw 6);
        - second development pass (bench/Poffin/evolve with fetched cards);
        - attach ONE energy from hand: to Kang if in play (any energy), else
          to the most-fueled Crustle/Dwebble ({G} first while it has none).
      recorded per turn (cumulative): wall online (>=1 evolved Crustle),
      attacker online (Kang with >=3 energy, or Crustle with >=3 energy incl.
      >=1 {G}), >=1 energy attached anywhere.
    """
    base = load_deck.__cache__
    wall_by = [0] * (TMAX + 1)
    atk_by = [0] * (TMAX + 1)
    energy_by = [0] * (TMAX + 1)
    mull_games = 0

    for _ in range(trials):
        deck = list(base)
        rng.shuffle(deck)
        hand = [deck.pop() for _ in range(HAND)]
        mulls = 0
        while not any(c in BASICS for c in hand):
            mulls += 1
            deck = list(base)
            rng.shuffle(deck)
            hand = [deck.pop() for _ in range(HAND)]
        if mulls:
            mull_games += 1

        # setup: play all basics, board cap 6; active preference Kang > Dwebble > Shaymin
        board = []  # slots: [card_id, n_energy, n_grass, placed_turn]
        for pref in (KANG, DWEBBLE, SHAYMIN):
            while pref in hand and len(board) < BOARD_MAX:
                hand.remove(pref)
                board.append([pref, 0, 0, 0])
        active = 0  # index of active slot (only matters for the Run Errand variant)

        wall = atk = has_energy = False
        for t in range(1, TMAX + 1):
            if deck:
                hand.append(deck.pop())

            if run_errand:
                if board[active][0] != KANG and SWITCH in hand:
                    for i, s in enumerate(board):
                        if s[0] == KANG:
                            hand.remove(SWITCH)
                            active = i
                            break
                if board[active][0] == KANG:
                    for _ in range(2):
                        if deck:
                            hand.append(deck.pop())

            def dev_pass():
                # bench basics from hand
                for pref in (KANG, DWEBBLE, SHAYMIN):
                    while pref in hand and len(board) < BOARD_MAX:
                        hand.remove(pref)
                        board.append([pref, 0, 0, t])
                # greedy Poffin dig (Dwebble is the only <=70 HP Basic here)
                while POFFIN in hand and len(board) < BOARD_MAX and DWEBBLE in deck:
                    hand.remove(POFFIN)
                    for _ in range(2):
                        if len(board) < BOARD_MAX and DWEBBLE in deck:
                            deck.remove(DWEBBLE)
                            board.append([DWEBBLE, 0, 0, t])
                # evolve (player-turn >= 2; not the turn the Dwebble arrived)
                if t >= 2:
                    for s in board:
                        if s[0] == DWEBBLE and s[3] < t and CRUSTLE in hand:
                            hand.remove(CRUSTLE)
                            s[0] = CRUSTLE

            dev_pass()

            # Pokegear 3.0: top 7, take Hilda else Lillie, shuffle rest back
            while POKEGEAR in hand:
                hand.remove(POKEGEAR)
                top = [deck.pop() for _ in range(min(7, len(deck)))]
                take = HILDA if HILDA in top else (LILLIE if LILLIE in top else None)
                if take is not None:
                    top.remove(take)
                    hand.append(take)
                deck.extend(top)
                rng.shuffle(deck)

            # one supporter per turn; engine blocks supporters on P1's turn 1
            if not (going_first and t == 1):
                need_evo = CRUSTLE in deck and CRUSTLE not in hand
                need_energy = (not any(c in ENERGY for c in hand)
                               and any(c in ENERGY for c in deck))
                if HILDA in hand and (need_evo or need_energy):
                    hand.remove(HILDA)
                    if CRUSTLE in deck:
                        deck.remove(CRUSTLE)
                        hand.append(CRUSTLE)
                    kang_on_board = any(s[0] == KANG for s in board)
                    pref_order = (MIST, SPIKY, GROW, G_BASIC) if kang_on_board \
                        else (GROW, G_BASIC, MIST, SPIKY)
                    for e in pref_order:
                        if e in deck:
                            deck.remove(e)
                            hand.append(e)
                            break
                elif LILLIE in hand and (need_evo or need_energy):
                    hand.remove(LILLIE)
                    deck.extend(hand)
                    hand.clear()
                    rng.shuffle(deck)
                    hand.extend(deck.pop() for _ in range(min(6, len(deck))))

            dev_pass()

            # attach one energy: Kang first (colorless costs), else Crustle line
            target = None
            for s in board:
                if s[0] == KANG and (target is None or s[1] > target[1]):
                    target = s
            if target is None:
                for wanted in (CRUSTLE, DWEBBLE):
                    for s in board:
                        if s[0] == wanted and (target is None or s[1] > target[1]):
                            target = s
                    if target is not None:
                        break
            if target is not None:
                if target[0] == KANG:
                    pref_order = (MIST, SPIKY, GROW, G_BASIC)
                elif target[2] == 0:
                    pref_order = (GROW, G_BASIC, MIST, SPIKY)
                else:
                    pref_order = (MIST, SPIKY, GROW, G_BASIC)
                for e in pref_order:
                    if e in hand:
                        hand.remove(e)
                        target[1] += 1
                        target[2] += 1 if e in GRASS else 0
                        break

            # end-of-turn records (cumulative)
            wall = wall or any(s[0] == CRUSTLE for s in board)
            atk = atk or any(
                (s[0] == KANG and s[1] >= 3)
                or (s[0] == CRUSTLE and s[1] >= 3 and s[2] >= 1)
                for s in board)
            has_energy = has_energy or any(s[1] > 0 for s in board)
            wall_by[t] += wall
            atk_by[t] += atk
            energy_by[t] += has_energy

    n = float(trials)
    return {
        "mulligan": mull_games / n,
        "wall_by": [x / n for x in wall_by],
        "atk_by": [x / n for x in atk_by],
        "energy_by": [x / n for x in energy_by],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1_000_000)
    args = ap.parse_args()

    deck = load_deck()
    load_deck.__cache__ = tuple(deck)
    pct = lambda x: f"{100 * x:.1f}%"

    print(f"deck: agent/deck_crustle.csv  (60 cards, verified vs expected list)")
    print(f"seed: {SEED}   MC trials/arm: {args.trials}\n")

    # ---- validation: re-derive the Starmie doc's exact hypergeometric rows ----
    print("== validation: exact hypergeometric re-derivation of the OLD Starmie rows ==")
    print("   (agent/deck.csv: 6 Basics, 4 Staryu, 3 Mega Starmie ex, 13 energy)")
    rows = [
        ("mulligan P(no Basic in 7)      doc 45.9%", p_none(6, 7)),
        ("P(>=1 Staryu in opening 7)     doc 39.9%", p_any(4, 7)),
        ("P(>=1 Mega Starmie in first 8) doc 35.4%", p_any(3, 8)),
        ("P(>=1 energy in opening 7)     doc 83.7%", p_any(13, 7)),
    ]
    for label, v in rows:
        print(f"   {label}  ->  {pct(v)}")

    # ---- Crustle exact hypergeometric ----
    print("\n== Crustle-current: exact hypergeometric ==")
    exact = {
        "mulligan": p_none(9, 7),
        "dwebble7": p_any(4, 7),
        "kang7": p_any(4, 7),
        "shaymin7": p_any(1, 7),
        "crustle8": p_any(4, 8),
        "energy7": p_any(13, 7),
        "energy8": p_any(13, 8),
        "energy9": p_any(13, 9),
        "energy10": p_any(13, 10),
        "poffin_or_dwebble7": 1 - p_none(8, 7),  # any Dwebble access card in 7
    }
    print(f"   mulligan P(no Basic in opening 7), 9 Basics : {pct(exact['mulligan'])}")
    print(f"   P(>=1 Dwebble in opening 7)   [FEEDER]      : {pct(exact['dwebble7'])}")
    print(f"   P(>=1 Mega Kangaskhan ex in 7) [MAIN, Basic] : {pct(exact['kang7'])}")
    print(f"   P(>=1 Shaymin in opening 7)   [bench shield] : {pct(exact['shaymin7'])}")
    print(f"   P(>=1 Crustle in first 8)     [WALL evo]     : {pct(exact['crustle8'])}")
    print(f"   P(>=1 Dwebble-or-Poffin in 7) [wall access]  : {pct(exact['poffin_or_dwebble7'])}")
    print(f"   P(>=1 energy in opening 7)                   : {pct(exact['energy7'])}")
    print(f"   P(>=1 energy in first 8/9/10) [end T1/T2/T3, "
          f"no dig] : {pct(exact['energy8'])} / {pct(exact['energy9'])} / {pct(exact['energy10'])}")

    # ---- Monte Carlo arms (fixed order off one seeded stream) ----
    rng = random.Random(SEED)
    arms = {}
    for name, first, errand in (
        ("second", False, False),
        ("first", True, False),
        ("second+RE", False, True),
        ("first+RE", True, True),
    ):
        t0 = time.time()
        arms[name] = simulate_arm(rng, first, errand, args.trials)
        print(f"\n-- MC arm {name:10s} ({time.time() - t0:.0f}s) --")
        a = arms[name]
        print(f"   mulligan (MC cross-check)          : {pct(a['mulligan'])}"
              f"   (exact {pct(exact['mulligan'])})")
        print(f"   P(wall online by end T2/T3/T4)     : "
              f"{pct(a['wall_by'][2])} / {pct(a['wall_by'][3])} / {pct(a['wall_by'][4])}")
        print(f"   P(attacker online by end T3/T4)    : "
              f"{pct(a['atk_by'][3])} / {pct(a['atk_by'][4])}")
        print(f"   P(>=1 energy attached by T1/T2/T3) : "
              f"{pct(a['energy_by'][1])} / {pct(a['energy_by'][2])} / {pct(a['energy_by'][3])}")

    # ---- headline block for the intel doc ----
    s, f = arms["second"], arms["first"]
    print("\n== headline (baseline arms, mirror-comparable to the Starmie doc) ==")
    print(f"   mulligan {pct(exact['mulligan'])} | wall T2 {pct(s['wall_by'][2])}/{pct(f['wall_by'][2])} "
          f"(2nd/1st) | wall T3 {pct(s['wall_by'][3])}/{pct(f['wall_by'][3])} | "
          f"attacker T3 {pct(s['atk_by'][3])}/{pct(f['atk_by'][3])} | "
          f"attacker T4 {pct(s['atk_by'][4])}/{pct(f['atk_by'][4])}")


if __name__ == "__main__":
    main()
