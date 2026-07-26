# Starmie deck consistency analysis (2026-07-11) — and a mulligan finding worth fixing

Computed on the shipped `agent/deck.csv` (Mega Starmie ex). Exact numbers are hypergeometric; the setup curve is
a 40k-trial Monte Carlo (mulligan-to-basic, greedy Poffin/Ultra-Ball dig + one draw-supporter/turn; evolve
requires turn ≥ 2). This is report §5.3 (consistency) + §5.4 (iteration) evidence — and flags a real weakness.

## Composition (60)
- **Basic Pokémon (6):** 4× Staryu, 2× Duskull. Line: **Staryu → Mega Starmie ex** (direct; no Rare Candy).
  Secondary tech: Duskull → Dusclops → **Dusknoir** (2/2/2 — the Cursed-Blast bench-snipe engine, dormant in the
  current pilot).
- **Energy (13):** 9× Basic {W}, 4× Ignition (special).
- **Draw/search (33):** 4× Buddy-Buddy Poffin, 4× Ultra Ball, 4× Poké Pad, 3× Pokégear 3.0, 4× Hilda,
  4× Lillie's Determination, 4× Wally's Compassion, 3× Carmine, 3× Judge. **1× Deluxe Bomb** (ACE SPEC tool).

## Numbers

| Metric | Value |
|---|---:|
| **Mulligan rate** — P(no Basic in opening 7) | **45.9%** |
| P(≥1 Staryu in opening 7) | 39.9% |
| P(≥1 Mega Starmie ex in first 8) | 35.4% |
| P(≥1 energy in opening 7) | 83.7% |
| P(Mega Starmie ex attacking by end of **turn 2**) — going 2nd / 1st | **72% / 67%** |
| P(attacking by end of **turn 3**) — going 2nd / 1st | **87% / 84%** |

## Finding: the mulligan rate is a real weakness

**6 basics in 60 → a 45.9% mulligan.** Nearly half of games open with a reshuffle (and the opponent draws a card
per our mulligan). Healthy decks run 8–12 basics for a <20% mulligan. The setup engine is strong *once it starts*
(≈70% attacking by turn 2), so the mulligan — not the combo speed — is the consistency bottleneck. This likely
costs real ladder equity, especially in the Alakazam prize race where a slow start is fatal.

**Hypothesis to test (queued — do NOT edit the deck while R3 owns `agent/`):** add 2–4 Basic Pokémon and trim
draw redundancy, targeting mulligan <25% without slowing the combo. Candidates from the pool (`card_db_full.csv`):
a Basic draw-support Pokémon (e.g. Fan Rotom / Squawkabilly-class ability-basic to also smooth draws), or +2 Staryu
(cheap, directly reduces mulligan and thickens the line). Measure: mulligan rate ↓ and meta-weighted gauntlet WR
(especially the Alakazam pillar) — a clean hypothesis→measure→decision iteration for report §5.4.

> Caveat: this analyzes OUR shipped list (WinDecks base + a Dusknoir tech line we added). The original WinDecks
> #7 list (55.6%/646g) may run a different basic count; the mulligan liability is a property of the *shipped* deck.
> Verify the mulligan/ reshuffle rule in the engine before over-weighting the penalty, but 6 basics is thin under
> any standard rule.

## Report tie-in
§5.3 consistency table (mulligan + setup curve = figure F5) and §5.4 iteration (the mulligan fix as a measured
hypothesis). The setup curve also supports the deck-concept claim that Starmie is *legible to the agent* — a fast,
linear 1-energy attacker — while honestly reporting its mulligan cost.
