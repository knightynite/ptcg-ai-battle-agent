# Crustle deck consistency analysis (2026-07-21) — the current-list §5.3 sizing, mirror of the Starmie doc

Computed on the shipped `agent/deck_crustle.csv` (Budew Crustle / Mega Kangaskhan ex, deck_key
656c2d64bc4711ef). Exact numbers are hypergeometric; the setup curve is a **1,000,000-trial-per-arm Monte
Carlo, fixed seed 20260721** (mulligan-to-basic, greedy Poffin/Pokégear dig + one draw-supporter/turn;
evolve requires turn ≥ 2). This fills the hole the report draft names in §5.3: consistency sizing existed
only for the OLD Starmie list (`intel/deck_consistency_starmie.md`); this doc is the same analysis for the
CURRENT list, in the same format, so the two are directly comparable. Script:
`scripts/deck_consistency_crustle.py` (deterministic, stdlib-only; every number below is its verbatim output).

## Method — mirror ledger vs `deck_consistency_starmie.md`

**Byte-mirrored definitions** (validated: the script re-derives all four of the old doc's exact rows to the
digit — 45.9% / 39.9% / 35.4% / 83.7%):

- 60-card deck, **7-card opening hand**; **mulligan = no Basic Pokémon in the opening 7**, resolved by
  redraw-to-basic (opponent may draw per our mulligan — irrelevant to these solitaire metrics);
- **"first 8" = opening 7 + the turn-1 draw**; all exact rows are unconditional hypergeometric;
- MC setup curve: mulligan-to-basic, then per our turn: draw 1, greedy item dig, **one draw/search
  supporter per turn**, **evolve requires player-turn ≥ 2** (and not the turn the Dwebble arrived), one
  energy attach per turn; "by end of turn N" = end of OUR turn N, reported going 2nd / going 1st;
- seat asymmetry as in the competition engine (`intel/engine_src/official/`): both players draw at every
  turn start including the going-first player's turn 1 (GameProc.h:994), but the going-first player cannot
  play a Supporter (GameProc.h:824) or attack (GameProc.h:915) on turn 1. FIRST_HAND=7, PRIZE_SIZE=6,
  DECK_SIZE=60, bench 5 (Core.h) — consistent with everything the old doc assumed.

**Where an exact mirror was impossible (each deliberate, none silent):**

1. **Trials/seed:** old doc = 40k trials, seed unstated (its script is not in the repo); this doc = 1,000,000
   trials per arm, fixed seed 20260721. Same procedure, tighter noise (±0.1pp at 1M vs ±0.5pp at 40k).
2. **Starmie's MC rows are quoted, not re-derived** (no script to rerun). Its exact rows ARE re-derived and
   byte-match, which is the strongest available check that the definitions here are the same ones.
3. **Dig items:** the old policy line is "greedy Poffin/Ultra-Ball dig"; this list has no Ultra Ball, so the
   greedy dig uses THIS deck's dig items — Buddy-Buddy Poffin (up to 2 Dwebble to bench; the only ≤70-HP
   Basic here) and Pokégear 3.0 (top 7 for a Supporter: Hilda, else Lillie). Supporter priority Hilda
   (search Evolution + Energy) then Lillie's Determination — the two setup supporters both lists share.
4. **The setup-defining event differs by deck role.** Starmie's curve metric was "Mega Starmie ex attacking"
   (a 1-energy attacker). This deck's attackers cost 3 energy (Rapid-Fire Combo {C}{C}{C}; Superb Scissors
   {G}{C}{C}), so *attacking by end of turn 2 is structurally impossible* (one attach/turn, no
   acceleration). The mirrored rows are therefore **wall online** (Crustle evolved — its role card,
   Mysterious Rock Inn, needs 0 energy) by T2/T3, plus **attacker online** (Kang with 3 energy, or Crustle
   with 3 incl. ≥1 {G}) by T3/T4. Both are reported; neither is swapped in silently as "attacking by T2".
5. **Prizes not modeled** — the old doc's method makes no mention of the 6-card prize set-aside, and the
   omission is kept so the decks stay comparable. Two effects cancel partially: no prize-pruning of key
   copies (optimistic) and Lillie draws 6 rather than the 8 she gives at exactly 6 prizes remaining
   (pessimistic).
6. **Run Errand sensitivity (addition, not headline):** the old method modeled no Abilities, so the baseline
   arms don't either. But Mega Kangaskhan ex's Run Errand (Active: draw 2/turn) is this deck's built-in draw
   engine; a flagged variant (greedy Switch-to-Kang + Run Errand) is reported separately as the
   deck-faithful upper read.

## Composition (60)

- **Basic Pokémon (9 of 13 Pokémon):** 4× Dwebble, 4× Mega Kangaskhan ex (a *Basic* — the MAIN attacker
  needs no evolution), 1× Shaymin. Line: **Dwebble → Crustle ×4** (the WALL; Stage 1, no Rare Candy). Roles per
  `deck_rebakeoff_2026-07-12.md` §3: **MAIN = {Mega Kangaskhan ex}, FEEDERS = {Dwebble}, WALL = {Crustle}**,
  Shaymin = bench shield (Flower Curtain).
- **Energy (13):** 4× Grow Grass ({G}), 4× Mist, 4× Spiky (both {C}), 1× Basic {G}. All four pay Kang's
  colorless costs; 5 cards pay Superb Scissors' {G}.
- **Trainers (34):** items 4× Buddy-Buddy Poffin, 4× Pokégear 3.0, 4× Switch, 4× Jumbo Ice Cream, 1× Hand
  Trimmer, 1× Hero's Cape (ACE SPEC tool); supporters 4× Hilda, 4× Xerosic's Machinations,
  4× Lillie's Determination, 2× Boss's Orders; stadium 2× Battle Cage.

## Numbers

Exact = hypergeometric; curve = Monte Carlo (1M trials/arm, seed 20260721), baseline arms (no Abilities,
mirror-comparable). MC mulligan cross-check: three arms reproduce the exact value at the reported precision
(30.0%); the fourth (first+RE) prints 29.9% — MC rounding at the 0.1pp edge, consistent with the exact 30.0.

| Metric | Value |
|---|---:|
| **Mulligan rate** — P(no Basic in opening 7), 9 Basics | **30.0%** |
| P(≥1 Dwebble in opening 7) [FEEDER / Crustle-line starter] | 39.9% |
| P(≥1 Mega Kangaskhan ex in opening 7) [MAIN — a Basic] | 39.9% |
| P(≥1 Shaymin in opening 7) [bench shield, 1 copy] | 11.7% |
| P(≥1 Crustle in first 8) [WALL evolution] | 44.5% |
| P(≥1 Dwebble-or-Poffin in opening 7) [wall access, 8 outs] | 65.4% |
| P(≥1 energy in opening 7) | 83.7% |
| P(≥1 energy in first 8 / 9 / 10) [seen by end T1/T2/T3, no dig] | 87.7% / 90.8% / 93.1% |
| P(≥1 energy **attached** by end T1) — going 2nd / 1st (MC) | 92.9% / 83.2% |
| P(≥1 energy attached by end T2 — T3) — 2nd / 1st (MC) | 96.6% / 96.4% — 97.8% / 97.8% |
| **P(Crustle wall online by end of turn 2)** — going 2nd / 1st (MC) | **70.1% / 65.5%** |
| P(wall online by end of turn 3 — 4) — 2nd / 1st (MC) | 76.4% / 75.6% — 81.6% / 81.2% |
| P(attacker online by end of turn 2) [structural: 3-energy attackers] | 0% |
| **P(attacker online by end of turn 3)** — going 2nd / 1st (MC) | **62.7% / 57.5%** |
| P(attacker online by end of turn 4) — 2nd / 1st (MC) | 76.5% / 76.1% |

**Run Errand sensitivity** (deck-faithful variant; Ability + greedy Switch-to-Kang; same seed stream):
wall online T2 **78.3% / 75.0%** (2nd/1st), T3 86.9% / 86.4%; attacker online T3 **72.2% / 67.6%**, T4
85.2% / 84.1%; energy attached T1 94.0% / 86.9%. Run Errand is worth ~+8pp on the T2 wall and ~+10pp on the
T3 attacker — the strict-mirror baseline *understates* the live deck's curve.

## Comparison — Crustle-current vs Starmie-old (every metric the old doc computed)

| Metric (old doc's definition) | Starmie-old (2026-07-11) | Crustle-current (2026-07-21) |
|---|---:|---:|
| Mulligan rate — P(no Basic in opening 7) | **45.9%** (6 Basics) | **30.0%** (9 Basics) |
| P(≥1 line starter in opening 7) | 39.9% (Staryu ×4) | 39.9% (Dwebble ×4) |
| P(≥1 evolution attacker in first 8) | 35.4% (Mega Starmie ex ×3) | 44.5% (Crustle ×4) |
| P(≥1 energy in opening 7) | 83.7% (13 energy) | 83.7% (13 energy) |
| P(setup by end of **turn 2**) — 2nd / 1st | 72% / 67% *(Mega Starmie attacking — 1-energy role)* | 70.1% / 65.5% *(Crustle wall online — 0-energy role)* |
| P(setup by end of **turn 3**) — 2nd / 1st | 87% / 84% *(attacking)* | 76.4% / 75.6% *(wall online)*; **attacking** 62.7% / 57.5% (T4: 76.5% / 76.1%) |

Reading the last two rows honestly: each deck's *setup-defining event* (Starmie attacking; the Crustle wall
standing) lands on essentially the same curve — ~70% by turn 2 going second. What differs is structural:
Starmie converts setup into damage immediately (1-energy attacker), while this deck's 3-energy attackers
start a turn later by construction — and its game plan (wall + 300-HP tank) is built around exactly that.
With Run Errand counted, the current list's curve dominates the old one's on every shared row.

## Finding: the old doc's mulligan weakness is fixed by construction — and the sizing is coherent

- The Starmie doc's headline finding was the **45.9% mulligan (6 Basics)** and it proposed "add Basics" as
  the fix (the +Basics rebuild was later measured at −5.5pp meta and rejected — `reproducibility.py` F5).
  The deck *switch* delivered what the rebuild couldn't: **9 Basics → 30.0% mulligan**, a −15.9pp cut, with
  the meta result improving (+3.2pp META / +7.0pp BAND, `deck_rebakeoff_2026-07-12.md`) instead of paying
  for it. Still above the old doc's "<20% healthy" bar — but 8 of the 9 Basics are cards the deck actively
  wants turn 1 (4 Dwebble feed the wall, 4 Kang are the closer *and* the draw engine).
- Sizing is consistency-first everywhere the list has a choice: **4-of on every functional slot** (Dwebble,
  Crustle, Kang, Poffin, Pokégear, Hilda, Lillie, Xerosic, Switch, Ice Cream, all three special energies) —
  only tech (Shaymin, Boss ×2, Cage ×2, Trimmer, Cape/ACE-SPEC) is off-max. The wall line is reachable via
  8 opening outs (65.4%) plus Hilda/Pokégear chains; the evolution itself is 44.5% in the first 8 raw, and
  the MC shows the chains lift wall-by-T2 to 70.1% going second.
- Energy: same 13-count as Starmie (83.7% opener) — but all-special (12/13), which the pilot must not pitch
  (the rebakeoff's PRIMARY_ENERGIES role-pin exists for exactly this).
- Seat asymmetry: the going-first supporter lockout costs ~4.6pp on the T2 wall (70.1→65.5) and ~5.2pp on
  the T3 attacker — same direction and similar size as Starmie's 72→67. Run Errand halves the gap
  (78.3→75.0), which rhymes with the live finding that this deck halved our second-seat tax.

## Report tie-in (what this supports in §5.3)

§5.3's claim — *consistency-first sizing of the current list* — previously leaned on the manabase A/B plus
a Starmie-only attachment. This doc supplies the missing current-list evidence in the old doc's own units:
**mulligan 30.0% vs 45.9%** (the old doc's named weakness, fixed by the switch, not by the rejected
rebuild), **identical energy opener (83.7%)**, **thicker evolution access (44.5% vs 35.4% in the first 8)**,
and a **setup curve on par with Starmie's (wall ~70% by T2 going 2nd; +8pp with Run Errand)** with the
one honest structural caveat stated (damage starts T3+, by role design). Comparison table above is the
F5-style pairing; figure work is owned by the report workstream (this doc deliberately touches neither
`report/` nor `reproducibility.py`).

> Caveats: (1) the Starmie MC rows are quoted from the 2026-07-11 doc, not re-run (script absent); the
> byte-matched exact rows are the mirror proof. (2) No prizes modeled, both decks alike (see ledger #5).
> (3) The greedy pilot here is a floor for the live pilot (no Ascension attack-search, no Xerosic/Boss
> lines, baseline ignores Run Errand); it is the same *kind* of floor the Starmie MC was.
