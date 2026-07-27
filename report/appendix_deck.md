# Appendix D — Deck concept and card utilization

*Attachment to the Strategy Writeup: the full deck evidence behind the body's §5 — the
concept and its alignment with the agent, the 60-card list with per-card roles, the
measurement behind each key-card utilization claim, and the ledger of deck edits we tested
and rejected. References to `intel/…`, `scripts/…`, and `agent/…` paths are internal
campaign artifacts, cited by name for audit-trail honesty; the released code repository
accompanying this writeup ships the agent, scripts, deck list, and report sources, and the
key cited artifacts are summarized here and in Appendices A and B.*

**Disclosure, stated first because it bounds everything below.** The 60-card list is
**adopted, not designed**: it is the card-id multiset of the #2-ranked ladder team's
Crustle / Mega Kangaskhan ex deck (`deck_key 656c2d64bc4711ef`, shipped as
`agent/deck_crustle.csv`), unmodified. What is ours is the *re-decision* — the bakeoff that
adopted it over our own incumbent, against our own prior published conclusion — the
utilization, and the two measured edits we tried on it and rejected. The provenance matrix
in Appendix B.4.4 says the same thing in the same words. Nothing in this appendix claims
authorship of the list.

**Instrument note, applied throughout.** Every magnitude here is a **local gauntlet**
figure. Levels are not comparable across instrument eras (body §6.1), and the two eras that
appear below are different instruments: the 2026-07-12 bakeoff and v7 per-patch A/Bs are
**pre-CRN** (unseeded engine shuffle, same-batch deltas only, ±2–3pp batch band on the
weighted metrics and ±5–7pp per-row A/A noise — Appendix A.3 #1), while the 2026-07-26
ablations are CRN-paired on one engine binary at n=300/row. None of them is a ladder
measurement, and roughly a fifth of the 25-row pool's weight sits on rows this report
already records as not reconciling to live (A.3 #3/#4). Where a number below is a *usage
count* it is descriptive — an observation of another team's play alongside our pilot's
counterfactual pick at the same state — and is not causal on its own.

---

## D.1 The concept, and how a won game actually unfolds

**The concept in one paragraph.** This deck does not try to win the prize race; it tries to
make the prize race unplayable and then win on the opponent's library. Crustle's ability
**Mysterious Rock Inn** — *"Prevent all damage done to this Pokémon by attacks from your
opponent's Pokémon {ex}"* (`intel/card_db_full.csv` id 345) — makes a 150-HP Stage 1
**completely immune to attack damage from the entire ex/mega-ex class**, which is what the
top of this format is built out of. The shield is specific in two ways that bound every
claim below: it covers *damage to Crustle*, and only from that class. Put Crustle in the
Active Spot against an ex board and the opponent cannot remove it by attacking: they cannot
take a prize on it, and every turn they spend searching for an answer costs them a card off
the top of their deck. What still gets through — non-ex attackers, Fire weakness, and
effects that reach past the Active Spot — is stated below and is the reason the deck
carries counters at all. Behind that
wall the deck does three things. It **denies prizes** — the only 3-prize bodies it owns
(Mega Kangaskhan ex) stay in hand or behind the wall rather than on the bench where a gust
can take them. It **strands the opponent's board** — Boss's Orders drags a Pokémon that
*cannot attack* into the Active Spot and then the deck simply declines to knock it out,
because knocking it out would free the board and restart the clock. And it **spends none of
its own library**, because in a game decided by whose deck empties first, cards in the
library are hit points: every draw item is self-damage. The win arrives one of two ways —
the opponent draws to zero, or, when the board finally opens, a 300-HP Mega Kangaskhan ex
closes with Rapid-Fire Combo for 200 into a board that has been unable to develop.

**How a won game actually unfolds, turn by turn.** The measured shape of this deck's games
comes from the 1,251-episode counterfactual replay of the #2 team piloting this exact list
(`intel/budew_behavior_diff.md`) plus our own consistency simulation of the shipped list
(`intel/deck_consistency_crustle_2026-07-21.md`, 1,000,000 trials/arm, seed 20260721):

- **Turns 1–2 — set up the wall, attack with nothing.** Opening hand mulligans at **30.0%**
  (9 Basics of 60, exact hypergeometric). Dwebble-or-Poffin — the 8 outs to the wall line —
  appears in the opening 7 **65.4%** of the time; **the Crustle wall is online by the end of
  turn 2 in 70.1% of games going second and 65.5% going first** (Monte Carlo; **78.3% /
  75.0%** with Mega Kangaskhan ex's Run Errand counted, which the strict-mirror baseline
  excludes). Attacking in this window is **structurally impossible** — both attackers cost
  three energy, the format allows one attach per turn, and the deck runs no acceleration, so
  P(attacker online by end of turn 2) is exactly **0%**. That is not a weakness of the
  opening; it is the plan. The wall costs zero energy to switch on, so the deck's role card
  is live a full turn before its damage is, and the wall buys the turns the attacker needs.
  The #2 pilot's own attack profile matches: across turns 1–4 it attacks **essentially never
  (272 Ascension searches only)**, and its first Rapid-Fire Combo lands at **median turn 9**.
- **Turns 3–8 — the tank absorbs, the wall takes over, the hand war starts.** The attacker
  comes online end of turn 3 in **62.7% / 57.5%** of games (2nd/1st; **72.2% / 67.6%** with
  Run Errand), turn 4 in **76.5% / 76.1%**. Active occupancy shifts measurably from
  Kangaskhan-tank early (**57% of turns 1–4**) to **Crustle-wall late (52% of turns 9+)** —
  the 300-HP body eats the early damage that the wall is not yet there to blank, then hands
  the Active Spot to the wall for the long game. Meanwhile Xerosic's Machinations empties
  the opponent's hand (fired at **median opponent hand 8; 91.7% of uses at ≥5, 0% at ≤3**),
  which is what stops them assembling the non-ex answer the wall is vulnerable to.
- **Turns 9–20 — the lock, and the library as hit points.** This is where the deck's real
  game lives, and where our own pilot disagreed with the #2 pilot most: substantive decision
  disagreement rises from **33.6% on turns 1–4 to 61.1% on turns 17+**. Boss's Orders drags
  a body that cannot attack in front of the wall and the deck **passes**: across the replay
  there are **692 ENDs taken with a legal attack available, 621 of them with an ex Active**,
  the single commonest lock being *(my Crustle, opponent's Cynthia's Garchomp ex holding one
  energy)* **×424**. The worked example is game `85224267`: from turn 19 to turn 41+ the
  board is frozen at Crustle 170 HP versus Garchomp ex 400 HP with one energy, the
  opponent's deck runs 23 → 4 → 0, and the deck never attacks once. Simultaneously it stops
  spending its own library: across **7,135 chosen ENDs** it was holding Switch **2,437**
  times, a playable Mega Kangaskhan **1,908**, Poffin **1,430**, a legal Crustle evolution
  **1,130**, Pokégear **1,098**, Battle Cage **821**, an energy attach **741**, and **a
  legal attack 692**. Median hand at END: 6. It skips its own draw ability at **median own
  deck 16** — 1,466 skips, 1,067 of them at deck > 10.
- **The close.** **62% of this deck's wins are the opponent decking out (444 of 713)** —
  against Alakazam opponents, **75% (328/440)**. About 34% are prize finishes, typically a
  late 2–3 prize knockout chain once the board finally cracks; 4% are bench-outs. **Median
  win: 20 turns. Median loss: 12** — the deck's losses are the games where it never got the
  wall up, and its wins are long by construction. Its own deck-out loss rate is **3%** (38
  of 1,251 games). Where the plan is executed cleanly the result is extreme: versus Cynthia's
  Garchomp, **96.5% over 57 games, of which 53 of 55 wins are literal deck-outs**.

**What the deck loses to, stated as part of the concept.** Mysterious Rock Inn is a
class-specific shield, so the counters are exactly the things outside that class: a
**non-ex attacker** walks through the wall (the tuned Great-Tusk stall row read 19.7%
before the v7 playbook and 41.2% after; on the current rebased pool the Kang-less
single-prize grinder `mirror_wall_fdedde79` reads **30.0%** for the shipped agent, against
~30.8% live on the same chassis — body §5.4), **Fire weakness** one-shots
a Grass wall (Ethan's Typhlosion, 89.0% → 54.3% on the deck switch), and **effects that
reach the bench** go around it entirely (Dragapult's Phantom Dive, Shadow Bullet — which is
what the two Battle Cage slots exist for). These are structural, we carry them openly
(A.5, body §5.4), and they are why the pilot's lock logic is gated rather than
unconditional: the v7 build shipped four evidence-driven guards that *drop* the lock when
the opponent is ahead on prizes, when a bench-reaching or non-ex attacker is live, when the
race model says we are not actually winning it, and when the draw-throttle would starve a
matchup that is genuinely a race (`intel/agent_v7_results.md` §2).

## D.2 Alignment: why this deck fits *this* agent

The alignment argument is not "this is a strong deck." It is a measured claim about the
interaction between this list and *our* pilot, and the evidence for it is that we ran the
comparison twice and **reversed our own published conclusion the second time**.

**We re-ran the bakeoff on our own current pilot and overturned ourselves.** The
2026-07-11 bakeoff, run on the primitive R1-era pilot, concluded that *nothing beat* our
incumbent Mega Starmie ex list (`intel/pilotability_bakeoff_2026-07-11.md`). By 2026-07-12
the pilot had gained the WinDecks playbook, the hidden-state tracker, and race/tank math,
and `set_profile_from_deck` derived deck roles automatically — so the pilot was
deck-general enough that the *deck* ceilings, not the pilot floor, dominated. We re-ran the
identical decision frame (`intel/deck_rebakeoff_2026-07-12.md`; same-batch, 15 frozen
opponents × 100 games × 3 seeds per deck, ~38,400 games) and the prior verdict did not
survive:

| deck | META (frozen top-quartile) | BAND (live 700–1000 mix) | seat 1st / 2nd | safety |
|---|---|---|---|---|
| Starmie (incumbent control) | 64.80 | 50.91 | 65.2 / 45.3 (−20.0) | 0/0/0 |
| **Crustle (adopted)** | **68.01 (+3.21, 3/3 seeds)** | **57.93 (+7.02, 3/3 seeds)** | 65.2 / **55.4 (−9.8)** | 0/0/0 |
| Alakazam | 43.02 (−21.8) | 44.73 (−6.2) | 50.0 / 43.2 | 0/0/0 |
| Rocket / Spidops | 55.72 (−9.1) | 44.33 (−6.6) | 45.2 / 45.7 | 0/0/0 |

*(Pre-CRN instrument: same-batch deltas only, ±2–3pp batch band. The direction replicates
across two independent batches — Crustle wins the band read 6/6 seeds and the meta read
5/6 — which is what the decision rested on, not any single level.)*

Three things in that table are the alignment argument.

**1. Deck EV ≠ our-bot EV — measured twice, in the same batch.** Alakazam is the
top-quartile king of this format: its owner converts it at a **70.4% success rate** on the
ladder. *Our* pilot realizes **43.0%** with it — the worst deck-EV-to-bot-EV conversion we
have measured, because the list's value is hand-size finesse that does not port cheaply.
Rocket/Spidops is the highest structural-SR archetype on the board and lands at 55.7/44.3
for us, with a disruption toolbox that is precisely the piloting risk. Choosing a deck by
its standing in the meta would have picked one of those two. The bakeoff measured what our
agent could actually *convert*, and that is a different ordering.

**2. The gameplan is one a rule-based agent can execute.** Our architecture is a tuned
heuristic pilot with an exact single-turn attack oracle and no learned policy (body §3).
That architecture is bad at finesse and good at applying a fixed, legible rule to a
long game. This deck's plan — hold the wall, hold the hand, hold the lock, count two
libraries — is almost entirely *legible state*, and its hardest decision is a repeated
"do nothing" that a heuristic can be told to prefer. The strongest evidence that the
gameplan and the architecture fit is that the #2-ranked team on the ladder converts this
exact 60 at **~57% success rate at LB ~1264 with a simple rules bot** (59% over the 307
games in the selection-window sample), which is an existence proof for the class of agent
we are, on the list we hold, at a rating above ours. And it is the same 60: the card-id
multiset was verified identical on sampled games, across the 1,251 of their episodes we
replayed.

**3. It fixes the incumbent's specific structural defect.** Our Starmie list carried a
permanent **−18pp live second-seat tax**, and four separate seat recipes had all failed to
move it (A.1 #6). The deck switch halved it — **−20.0pp → −9.8pp locally**, the entire gain
sitting in the second seat — which is consistent with the mechanism: a deck whose turn-1
plan is "put a 0-energy wall down and pass" cares far less about the going-first supporter
lockout than a deck racing for prizes. The consistency mirror shows the same thing from the
other side: the going-first supporter lockout costs this list ~4.6pp on the turn-2 wall,
and Run Errand halves even that.

**And the mechanism reads per row explain themselves in terms of the concept**, which is
the coherence test that matters: the wall blanks ex attack damage, so **Archaludon ex
+55.0pp** and **Cynthia's Garchomp ex +29.0pp** simply cannot win; the Alakazam pillar
flips **+10.5pp** because Xerosic strips the Powerful-Hand hand while a 300-HP Kangaskhan
out-tanks a 140-HP Alakazam; the Lucario bleeder improves **+8.3pp** because we stop
handing over 3-prize Megas. The costs land exactly where the shield does not apply —
non-ex grinder **−46.3pp**, Fire **−34.7pp**, bench-reaching Phantom Dive **−6.3pp**. A
deck whose per-matchup results are predicted by one sentence of its own card text is the
definition of a coherent concept, and it is also why we can state the counters honestly
rather than discovering them.

**Finally, the whole agent is built around knowing it holds this deck.** The controlled
2026-07-26 measurement against the organizer's provided baseline, deck held constant,
CRN-paired at n=300/row (`intel/frozen_final_baseline_2026-07-26.md`), ablates the
deck-hook family `PTCG_DK` at **−21.84pp — about 56% of the entire +38.36pp gap**, with 24
of 25 rows regressing, 21 at p<1e-4, worst `crustle_live` −83.33pp. As that document puts
it: *the honest one-line story of this agent is "it knows what deck it is holding," and the
rest of the ledger is refinement on top of that.* The caveat is stated there and repeated
here — `PTCG_DK` is a *precondition* flag that gates much of the rest of the ledger, so
−21.84pp is a **floor on how much of this agent is deck-specific**, not a clean measurement
of one mechanism.

## D.3 The list: 60/60 with counts and roles

Card names and texts verified against `intel/card_db_full.csv`; counts verified against the
shipped `agent/deck_crustle.csv` and the live extraction in
`intel/novel_lever_hunt_2026-07-17.md` §3.1. Role labels are the pilot's own — the
`crustle_wall` profile pins `MAIN = {756}`, `FEEDERS = {756, 344}`, `WALL = {345}`,
`PRIMARY_ENERGIES = {G, Mist, Spiky, Grow Grass}` (`agent/scoring.py`, verified in-harness).

| # | id | card | type | role in the plan |
|---:|---:|---|---|---|
| 4 | 344 | Dwebble | Basic Pokémon, 70 HP | wall feedstock; *Ascension* searches its own evolution — the wall supply IS the game |
| 4 | 345 | **Crustle** | Stage 1, 150 HP | **THE WALL.** *Mysterious Rock Inn* blanks all attack damage from opponent's ex; *Superb Scissors* 120, damage unaffected by effects on their Active |
| 4 | 756 | **Mega Kangaskhan ex** | Basic mega-ex, 300 HP | tank, draw engine (*Run Errand*: draw 2), and closer (*Rapid-Fire Combo* 200). Fighting-weak; 3 prizes |
| 1 | 343 | Shaymin | Basic, 80 HP | bench shield (*Flower Curtain* prevents damage to our benched non-Rule-Box Pokémon); the designated sacrifice |
| 4 | 18 | Grow Grass Energy | Special energy | provides {G} **and +20 HP** to a {G} Pokémon — reserved for Crustle: its cost *and* its buff |
| 4 | 11 | Mist Energy | Special energy | {C}; **prevents all attack *effects*** on its holder — the protective resource, goes on the Active tank |
| 4 | 14 | Spiky Energy | Special energy | {C}; puts **2 damage counters on the attacker** when its Active holder is damaged by an attack |
| 1 | 1 | Basic {G} Energy | Basic energy | the only non-special {G}; emergency Superb Scissors fuel |
| 4 | 1086 | Buddy-Buddy Poffin | Item | search 2 Basics with ≤70 HP to bench — in this list, Dwebble only |
| 4 | 1122 | Pokégear 3.0 | Item | top-7 dig for a Supporter |
| 4 | 1123 | Switch | Item | the wall swap — wall in front of an ex, breaker in front of their wall, tank back when the wall is pointless |
| 4 | 1147 | Jumbo Ice Cream | Item | heal 80 from an Active with ≥3 Energy — the tank-longevity card |
| 1 | 1087 | Hand Trimmer | Item | both players discard to 5, opponent first — hand denial that costs no Supporter slot |
| 1 | 1159 | Hero's Cape | **ACE SPEC** Tool | +100 HP, one per deck by rule — goes on whichever body is tanking |
| 4 | 1225 | Hilda | Supporter | search an Evolution **and** an Energy — the wall/energy refetch after losses |
| 4 | 1227 | Lillie's Determination | Supporter | shuffle hand, draw 6 — **8 at exactly 6 Prizes**; near-neutral on the mill clock |
| 4 | 1197 | Xerosic's Machinations | Supporter | opponent discards to 3 — the hand-denial engine |
| 2 | 1182 | Boss's Orders | Supporter | the gust — creates the lock |
| 2 | 1264 | Battle Cage | Stadium | prevents damage counters being placed on **either player's** benched Pokémon by opponent attack/Ability *effects* (attack damage still lands) — the answer to bench-reaching attacks |

**Totals: 13 Pokémon (9 Basics) / 13 Energy (12 special) / 34 Trainers = 60.**

The sizing is consistency-first wherever the list has a choice: **4-of on every functional
slot** — Dwebble, Crustle, Kangaskhan, Poffin, Pokégear, Hilda, Lillie, Xerosic, Switch,
Ice Cream, and all three special energies. Only tech is off-max: Shaymin ×1, Boss ×2,
Cage ×2, Trimmer ×1, and the ACE SPEC Cape at its mandatory 1. Nine Basics give a **30.0%
mulligan rate** — the deck switch cut the incumbent's 45.9% by 15.9pp *and improved the
result*, where the direct 11-Basic rebuild of the old list had measured **−5.5pp** and been
rejected (A.1 #3). 30.0% is still above the "<20% healthy" bar the consistency doc uses,
and we report it rather than rounding it away; the mitigation is that 8 of the 9 Basics are
cards this deck actively wants on turn 1.

## D.4 Key cards: what the pilot does with each, and the number behind it

Each entry states the utilization rule the agent applies, then the measurement that backs
it. Where a rule ships inside a bundled flag we say so and quote the bundle, rather than
attributing the bundle's value to the card. The per-card-family A/B is
`intel/agent_v7_results.md` §3 (batch 3: 8 arms × 15 opponents × 100 games × 3 seeds,
pre-CRN, same-batch); the CRN ablation is `intel/frozen_final_baseline_2026-07-26.md`.

**The family-level scoreboard, since several cards below share a flag:**

| family (`PTCG_…`) | what it governs | META Δ, single arm | note |
|---|---|---:|---|
| B6 | supporter engine (Xerosic / Lillie / Hilda / Trimmer priority + timing) | **+4.49** | largest single arm |
| B5 | energy role-map + Hero's Cape routing + Jumbo enablement | **+4.26** | |
| B3 | Kangaskhan bench cap / spares stay in hand | +2.75 | **dropped from the v7 ship set — but shipped anyway; see D.5** |
| B1 | deck-life economy + stall-lock END band | +1.35 | pairs with B2 |
| B4 | promote/sacrifice order + Switch held by default | +1.09 | |
| B2 | gust-lock: Boss targeting + don't-break-the-lock | **−1.61** | **negative alone**; only pays paired with B1 |
| all on | — | **+8.28** | less than the +12.3 sum of singles — overlapping credit |

*(Pre-CRN, same-batch; per-row deltas inside these arms sit under the ±5–7pp A/A noise
floor and are not individually resolvable. The five shipped flags B1/B2/B4/B5/B6 were later
re-measured as a group on the CRN instrument: removing them costs **−3.45pp**, p=8.4e-20,
concentrated on exactly the rows they were ported for — `mirror_tusk` −31.33, `wmh_garchomp`
−15.00, `comfey_hammer_denial` −15.33, `budew_crustle` −12.67. Three fast-clock rows move
*positive* when the group is removed, which is honest evidence the playbook is not free.)*

**The gate this set actually faced, stated so the table is not over-read.** At its ship gate
the five-flag playbook **met the META leg (+5.83pp, 3/3 seeds) and MISSED the live-band leg
(+0.61pp against a +3.0pp bar)**, and it shipped on the meta leg only (B.1, body §3.5). The
structural reason is directly about deck concept: these patches move the crustle-family
grinds, stall endgames and the Alakazam hand-war, which carry 77% of the meta weight but
only ~36% of the band weight — Lucario, Dragapult and the Starmie mirror hold 44% of the
band weight and did not move. So the correct reading of the family table is *"where the
deck's plan applies, the utilization is worth a lot; across the whole live band it is worth
less than its headline"* — and the 2026-07-26 CRN group read of −3.45pp is the honest
band-wide number.

### Crustle ×4 — the wall
**Rule:** when the opponent's board threat is ex/mega-ex *attack* damage, promote and keep
Crustle Active (+260) and fuel the Active wall to 3 energy (+340); when *their* Active is a
Crustle-class shield our own ex deals 0 to, the non-ex Crustle becomes the win condition
and the same preferences flip to it (`_wall_mode` / `_opp_wall_active`). The hooks correctly
stay **off** against non-ex threats.
**Measured:** the family that contains this is the single largest measured component of the
agent — `PTCG_DK` ablates **−21.84pp**, ~56% of the whole gap to the provided baseline,
2,726 discordant games, p<1e-300. Uptime: **wall online by end of turn 2 in 70.1% / 65.5%**
of games (2nd/1st; 78.3% / 75.0% with Run Errand). Matchup mechanism, on the deck switch:
Archaludon ex **+55.0pp**, Cynthia's Garchomp ex **+29.0pp**. The wall-breaker branch alone
moved the non-ex grinder row 9.0% → 19.7% and the mirror 83.0% → 90.3%. Independently, in
the independent root-cause review of 34 live Lucario losses, **Crustle blocked 95 of 95 direct
Lucario attacks** — the losses came from gust-locks on our Kangaskhan, not from anything
getting through the wall (B.3).
**Caveat:** `PTCG_DK` is a precondition flag, so −21.84pp is a floor on "how deck-specific
this agent is", not a Crustle-card measurement.

### Mega Kangaskhan ex ×4 — tank, draw engine, closer
**Rule:** the deck's only draw engine is Run Errand on the Active Kangaskhan, and it is also
the deck's main *cost*, because every draw ticks our own library toward the loss condition.
B1 rewrote the veto from a flat `deck ≤ 6` to clock-aware: hard floor at ≤6, full stop once
the passive mill race is won, and a `deck ≤ 18 & hand ≥ 4` throttle **only while safely
behind the wall**.
**Measured:** the #2 pilot uses Run Errand **4,558×** at median own-deck 33 and **skips it
1,466×** at median own-deck 16 (1,067 skips at deck > 10); against our pre-v7 `deck ≤ 6`
veto we counterfactually Run-Errand **5,605×** where they decline, 2,040 of those at deck
5–19. Run Errand's own value is sized in the consistency MC: **+8pp on the turn-2 wall and
+10pp on the turn-3 attacker**. The tank role is measured as occupancy — Kangaskhan holds
the Active Spot in **57% of turns 1–4** and Hero's Cape goes to it 376 of 756 times.
**Cost, stated:** Kangaskhan is Fighting-weak and worth 3 prizes. The v8 diagnosis found our
Lucario losses were **6-0 prize losses in which their six prizes were exactly our Mega
Kangaskhans**, gusted off the bench on sight — which is what the L1 quarantine and the B3
bench cap exist for. See D.5 for the unresolved status of B3.

### The energy suite: Mist ×4 / Spiky ×4 / Grow Grass ×4 / Basic {G} ×1
**Rule (B5 role-map):** the three special energies are *not* interchangeable. Mist goes to
the current tank in the Active Spot — its "prevent all attack effects" only protects the
unit being hit. Spiky goes to Kangaskhan while Kangaskhan tanks. Grow Grass is reserved for
Crustle: it is simultaneously the {G} that pays Superb Scissors and a +20 HP buff on the
body that has to survive. The single Basic {G} is held as emergency Superb fuel. And the
Active is loaded to 3 energy **before** any bench banking, because 3 energy is Jumbo Ice
Cream's eligibility line. `_to_hand_value` was inverted to fetch Mist first.
**Measured:** **B5 = +4.26 META** as a single arm. The usage evidence: Mist→Kangaskhan@Active
**1,658**, Spiky→Kangaskhan 920 Active + 447 bench, Grow Grass→Crustle **627** Active,
Grow→Kangaskhan 667 as filler; **800 both-ATTACH flips** dominated by their-Mist-vs-our-
Grow/Spiky on the same target; deck-fetch flips are one-way — they take Mist where we take
Spiky/Grow/basic-{G} (**222 + 220 + 194** flips). Superb Scissors' {G} has exactly **5
payers in 60 cards**.
**The strongest evidence for Spiky specifically is a negative result.** We tested cutting
all four Spiky for four Basic {G} — holding 13 energy, raising Grass providers 5→9 and
shrinking Hammer-strippable special energy 12→8. It measured **−8.00pp on the primary gate
row (p=0.0032), negative on every row, consistent across 3/3 seeds**, while the *intended*
mechanism moved exactly as predicted (payable-Crustle turns +9.4%, attacks per game +8.6%).
The reason is card text read one matchup too narrowly: the non-ex grinder attacks with a
genuine damaging attack 12+ times per game, and Spiky had been retaliating all along
(A.7, `intel/manabase_ab_2026-07-15.md`). **Spiky is load-bearing, and we only know it
because we tried to cut it.**
**Honest limitation:** that same A/B is the *only* measurement we have touching the Basic
{G} count, and it says more Basic {G} is worse. The single copy is inherited and has no
independent support.

### Xerosic's Machinations ×4 — the hand-denial engine
**Rule (B6):** fire at opponent hand ≥6 (≥5 against a believed Alakazam), hold it dead at
≤4, and — the actual fix — give it priority over Hilda and Lillie both in hand and at
Pokégear picks.
**Measured:** at the same board states, **they cast Xerosic 2,739 times to our 1,468**.
Their timing: **median opponent hand 8, 91.7% of uses at ≥5, 0% at ≤3** — our gate's
*shape* was already right; it lost the priority fight, taking **Hilda over Xerosic ×261**
and Lillie over Xerosic ×145 at Pokégear looks (their Pokégear picks run Xerosic 724 >
Lillie 667 > Hilda 417 > Boss 204). **B6 = +4.49 META**, the largest single arm in the set,
with the Alakazam rows moving +10.4 and +6.7.

### Lillie's Determination ×4 — the draw the mill clock allows
**Rule (B6):** widen the cast window to hand ≤7 at exactly 6 Prizes remaining (the old
hand ≤5 gate blocked most real usage).
**Measured:** they cast at median hand 6 (p75 7), **69% of casts inside the exactly-6-prizes
8-draw window**; our gate produced **314 Lillie-vs-Hilda and 331 Lillie-vs-bench-Kangaskhan
flips**. The concept-level reason this card is a 4-of in a deck that refuses to draw:
Lillie shuffles the hand back in, so she is **nearly neutral on the mill clock** — the one
draw supporter this deck can spend freely.

### Hilda ×4 — the refetch, not the setup engine
**Rule (B6):** drop the crustle-path early-Hilda +700 bonus; Hilda is the wall/energy
refetch when the Crustle line or the energy is short, on any turn.
**Measured:** this is a card where the measurement said **our prior utilization was wrong
and we changed it**. We over-used Hilda — **ours 2,067 vs their 1,493** — firing it early on
undeveloped boards, while their **median Hilda turn is 9** (p25 5), i.e. after wall losses.
Same card, opposite timing; the search text (an Evolution **and** an Energy) is a repair
tool, not an opener.

### Boss's Orders ×2 — the gust that creates the lock
**Rule (B2):** target `argmin(attack capability)` — bodies ≥2 energy away from any attack,
preferring energyless ex support (a 2-prize hostage that cannot act), engine basics only
when we exact-KO them next turn — instead of the old "drag the biggest threat". Then, once
the lock is on, **hold Boss and veto our own attacks** while the opponent's Active deals 0
to ours and our library outlasts theirs.
**Measured:** their gust targets are hostages, not threats — Fezandipiti ex **×87**, Abra
×69, Kadabra ×38, Dunsparce ×22, opponent Dwebble ×26, Spiritomb ×13 — where we
counterfactually gusted the biggest threat (Kadabra→Alakazam ×19+13, Staryu→a 410-HP Mega
Froslass ex). Lock discipline: **692 declined attacks, 621 with an ex Active**; our pilot
had **no lock concept at all** and broke locks it accidentally acquired (85 direct
attack-at-their-END flips). The concept payoff at the top of the ladder is the Cynthia row:
**96.5%, 53 of 55 wins by literal deck-out**.
**Honest limitation, and it is the sharpest one in this appendix.** **B2 is the only single
arm in the v7 set that measured negative: −1.61 META / −1.93 BAND.** It pays only as a pair
with B1 — attack-refusal without the draw-throttle stalls into *our own* deck-out (the
grinder row reads 14.7% with B2 alone versus 42.3% with both). And the diff document's
headline "+28pp available on Cynthia" **did not transfer**: v7 moved that row only +2.7pp,
because our wall already farmed the local Cynthia bot at 66–70% — unlike whatever the
opponents at 1264 were doing. The lock is the concept's centrepiece and its single-card
evidence is the weakest in the set; we ship it inside a pair whose *group* measures −3.45pp
when removed, and we do not claim a number for the gust alone.

### Switch ×4 — held, not spent
**Rule (B4):** Switch is **held by default** and played only when the swap changes
this-turn damage — wall in front of an ex, breaker in front of their wall, tank reset, or a
lethal promote. This demoted our earlier proactive +250/+200 swap bands.
**Measured:** Switch is their **#1 held card at END — 2,437 of 7,135 ENDs**, and our
proactive hook generated **618 END-vs-Switch flips**. They pay a retreat cost **52 times in
1,251 games**; repositioning is Switch-only. Ships inside B4 (+1.09 single-arm) and the
−3.45pp shipped group; no isolated Switch measurement exists.

### Jumbo Ice Cream ×4 — enabled upstream, not by its own gate
**Rule:** heal only on an Active with ≥3 energy and ≥60 damage.
**Measured:** our gate was **already correctly shaped and still fired only 548 times against
their 1,337**, because we never loaded the Active to 3 energy in the first place — they heal
a median of 80 (p25 60) on a median-3-energy Active (Kangaskhan 872 / Crustle 464). The fix
was upstream in B5's attach ordering, not in the Jumbo gate. This is the cleanest example
in the deck of *utilization* being the binding constraint rather than card choice: same
card, same threshold, 2.4× the usage once the energy policy fed it.

### Hero's Cape ×1 (ACE SPEC) — +100 HP, on the body that is tanking
**Rule (B5):** route the Cape to the current tank (Kangaskhan or Crustle), never to Shaymin.
**Measured:** **756 uses → Kangaskhan Active 376 / Crustle Active 139** against **our 138**,
and our misrouting was specifically Cape-onto-Shaymin (8 flips). Carried by B5's +4.26;
no isolated measurement.

### Buddy-Buddy Poffin ×4 and Pokégear 3.0 ×4 — the dig, priced against the clock
**Rule (B1):** Poffin only while wall supply is unestablished (<2 Dwebble+Crustle in play or
hand); Pokégear only when the hand has no Supporter and one is wanted; both dead once
developed.
**Measured:** every Poffin is −2 library and every Pokégear −1 against a plan whose loss
condition is our own library. We would play Poffin **3,069 times to their 2,144**, and dump
Pokégear/Poffin on sight where they hold them (**609 + 272 END flips**). Consistency side:
the Dwebble-or-Poffin package gives **8 opening outs, 65.4%**, to the wall line — which is
why the count stays at 4 despite the clock cost.

### Dwebble ×4 and Shaymin ×1 — the sacrifice order
**Rule (B4):** after a knockout in wall-relevant matchups, promote **Crustle**; sacrifice in
the order Shaymin > spare Kangaskhan tank > **Dwebble last**, because Dwebble is Crustle
feedstock and the wall supply is the game.
**Measured:** they promote Crustle where we send Dwebble **×403** or Kangaskhan **×148**,
and they promote Shaymin where we send Dwebble **×134**. Ships in B4.
**Honest limitation:** Shaymin is the thinnest card in this write-up. Its evidence is 134
observational promote flips in another team's games plus a role assignment; the two pilot
rules that implement it are bundled (B4's sacrifice order, and a bench-discipline branch
behind the disputed B3), and **no measurement isolates Shaymin at all**. We keep the card
because it is in the adopted list and its Flower Curtain text is coherent with a plan that
wants a cheap non-Rule-Box body to throw away — but that is a reasoned assertion, not a
measurement, and it is listed as such in D.5.

### Battle Cage ×2 — the answer to the attacks that go around the wall
**Rule (D1b "Cage economy"):** hold the Cage unless it *replaces* their stadium or a live
counter-bench threat is on board; never burn the spare over our own Cage. The reasoning is
recorded in the code: Dragapult's Watchtower runs ×2 and turns Run Errand off, so leading
with an unprovoked Cage loses the stadium war 2-2.
**Measured:** the card answers a real, identified hole — the v7 board-aware guard lists
Shadow Bullet ("30 to 1 Benched") and Phantom Dive ("6 damage counters on Benched") as
attacks that **pierce Mysterious Rock Inn** and must disqualify the lock. They hold Cage at
END **821** times, consistent with the hold-by-default policy.
**Honest limitation:** **no measurement isolates Battle Cage**, and the one measured variant
on record is a *failure* — the hold-until-provoked band was scored at 400, which sat below
the attack band, so the Cage never reached the table and **the Dragapult row bled 5.7pp**.
The shipped band is the correction to that failure, not a validated optimum.

### Hand Trimmer ×1 — hand denial that costs no Supporter slot
**Rule (B6):** relax the own-hand gate to ≤7 when the opponent's hand is ≥6.
**Measured:** they fire it **568 times to our 160**, at opponent hand ≥6–7 even holding 7
themselves (accepting the symmetric discard).
**Honest limitation:** bundled in B6 with three larger cards; no isolated measurement, and
the single copy is inherited.

## D.5 Where the deck story is weaker than it reads — stated as results

The rubric asks how effectively key cards are selected and utilized. Four honest deductions
belong in the answer:

1. **Six of the 60 cards, across five slots, have no measurement behind their
   utilization.** Shaymin ×1, Battle Cage ×2, Hand Trimmer ×1, the single Basic {G}, and
   the single Hero's Cape are
   described above by role and by observational usage counts, and each is either bundled
   inside a multi-card flag or unmeasured entirely. For Battle Cage the only isolated
   experiment on record **failed** (the Dragapult row bled 5.7pp when the hold band was set
   too low). We are not able to say these five slots are correct; we can say what they are
   for and that we have not tested them.
2. **The gust-lock — the concept's centrepiece — measures negative in isolation.** B2 is
   −1.61 META alone and only positive as a pair with B1 (D.4). The most quotable number in
   the concept (Cynthia 96.5%, 53/55 deck-outs) is *their* result on this list, and the
   corresponding lift did not transfer to our gauntlet (+2.7pp, not the +28pp the diff
   suggested).
3. **A shipped flag contradicts its own gate, and we found it writing this appendix.** The
   v7 bakeoff **dropped B3 (the Kangaskhan bench cap / spares-stay-in-hand rule) from the
   ship set**: head-to-head, v7-without-B3 beat v7-all-on on *both* weightings (META 77.53
   vs 75.25; BAND 61.26 vs 59.92) with a consistent Lucario bleed (−7.3pp pooled over
   n=900). Yet `PTCG_B3=1` in **both** fielded build scripts
   (`submit/build_submission_v11.sh:53`, `submit/build_submission_v12.sh:53`), it is listed
   as on in the frozen configuration ledger (B.4.1), and the 2026-07-26 CRN ablation
   deliberately grouped only **B1/B2/B4/B5/B6** — so **B3's marginal value in the
   configuration we actually fielded has never been measured on the CRN instrument**. We
   record this as an unresolved discrepancy rather than quietly correcting the narrative in
   either direction: the pre-CRN head-to-head that dropped it (N=150×2, one batch) is
   exactly the class of reading the CRN work has repeatedly overturned in both directions
   (A.3 #1, B.1), so "the shipped build is wrong" is no better supported than "the drop was
   noise." What is certain is that a key-card discipline rule for the deck's 3-prize body is
   shipping in a state its own gate did not authorize.
4. **The concept census is measured on their games, not ours.** "62% of wins are opponent
   deck-out", "median win 20 turns", and the usage tables are all from the 1,251-episode
   replay of the **#2 team's** play on this list. We have never censused our own agent's
   win-condition mix at that granularity. The two narrower reads we do have on our own play
   point the same way and are small-n: v8's diagnosis found our wins against both Lucario
   lists are "almost all `OPP_DECKOUT`", and the seat diagnosis found our second-seat wins
   are **exclusively long grinds — 7 of 11 by deck-out, zero wins under 17 turns**. Neither
   is a census. And the clock cuts both ways for us more than for them: on the same
   denominator, our own deck-out *losses* run **23/192 = 12% of our losses** against
   **38/538 = 7% of theirs**. (The 3% quoted in D.1 is their share of *games*, 38/1,251;
   the like-for-like contrast is the one above.)

## D.6 Rejected modifications, and the decision to hold the list

The deck-change family is **0-for-2**, and both failures are informative rather than
inconclusive — though about different things: #1 about the card, #2 about our own pilot
(see the target-selection defect below). Both were pre-registered with falsifiers fixed before the run, both were
CRN-paired across 3 seeds (manabase n=300/row, Sacred Ash n=900/row/arm), both
instrumented the mechanism they claimed, and
**in both cases the mechanism fired exactly as predicted while the win rate moved the other
way.**

| # | change tested | primary row | Δ win rate | McNemar p | mechanism | verdict |
|---|---|---|---:|---:|---|---|
| 1 | −4 Spiky Energy / +4 Basic {G} (manabase; holds 13 energy) | `mirror_wall_fdedde79` | **−8.00pp** | **0.0032** | fired: payable-Crustle turns +9.4%, attacks/game +8.6% | rejected, 3/3 seeds, every row negative |
| 2 | −1 Pokégear 3.0 / +1 Sacred Ash (deck-out recovery) | `mirror_wall_fdedde79` | **−3.44pp** | **0.0424** | fired: Sacred Ash played in 65.8% of games; our deck-out rate 18.1% → 15.0% | NO-SHIP / CLOSE |

*(A third rejected change, the 11-Basic mulligan rebuild at −5.5pp, was measured on the
**previous** Starmie list before the switch and is therefore not an edit to this list —
Appendix B.4.4 draws the same line.)*

Two details are worth carrying, because they are what turn "we didn't change the deck" into
a decision.

**The manabase failure taught a rule we now apply everywhere: confirming your mechanism does
not confirm your change** (A.7). The candidate was chosen to be shared-axis rather than
matchup-specific, its rationale came from card text, and its predicted mechanism was
verified against the engine's own legality computation. It was still wrong — because the
resource being spent (Spiky's retaliation against a grinder that attacks 12+ times per game)
was never priced.

**The Sacred Ash failure surfaced a defect in our own item handling, not in the card.**
Across **all 1,074 firings**, `ash_targets == ash_fires` exactly — **every single Sacred Ash
play returned exactly ONE Pokémon**, never more, despite the card allowing up to 5 and the
pre-check census finding a median of 3 (up to 8) of our own Pokémon in the discard at the
moment of a real deck-out loss. The card engaged in two thirds of games and never delivered
a fifth of its per-play ceiling. So that A/B honestly tested *"Sacred Ash as played by this
pilot,"* not *"Sacred Ash"* — which we state because it bounds the conclusion, and because
the target-selection artifact is a pilot bug we did not have budget to fix inside a
deck-only pre-registration.

**The decision: hold the list. This is a deliberate, evidenced stop, and here is its rule.**

1. **Prior.** Two independent, mechanistically unrelated edits both landed negative on the
   same primary row at p<0.05, with pre-registered falsifiers and CRN pairing. A third
   deck A/B costs a full build cycle against a 0-for-2 prior.
2. **No diagnosis points at a third card.** Neither failure was a mechanism failure, which
   removes the usual "try a better version of the same idea" response. We do not have a
   card-level defect to fix; we have two confirmed mechanisms that did not convert.
3. **The list is externally validated above our own rating.** The #2 team converts this
   exact 60 — verified identical card-id multiset — at ~57% over 1,251 games at LB ~1264,
   with a rules bot. The gap between that result and ours is measured, and it is
   **behavior, not cards**: **26,376 substantive decision disagreements** out of 59,508
   non-trivial decisions, of which the categories the five load-bearing differences cover
   account for ~24.0k. Every point of that gap is implementable in the
   pilot, and the pilot is where our remaining budget goes.
4. **Coherence is the thing being scored, and every measured edit reduced it.** One cut the
   retaliation the grind depends on; the other spent a Pokégear slot — the deck's supporter
   access — on a recovery card this pilot demonstrably under-uses. Both made the list less
   aligned with the plan described in D.1, which is exactly what their results said.
5. **Reopen conditions, recorded so this is a stop and not a wall.** (a) The narrower
   single-variable Spiky test the manabase document itself names — **−2 Spiky / +2 Basic
   {G}** — which would isolate the retaliation channel rather than deleting it. (b) Fix the
   item target-selection artifact first, then re-run Sacred Ash, since that A/B never tested
   the card at full effect. Neither was run. That is a budget decision under a 0-for-2
   prior, not a judgement that they would fail.

## D.7 What this appendix does not establish

- **No number here is a ladder measurement.** All of it is local gauntlet, and levels are
  not comparable across instrument eras (body §6.1). The bakeoff and the v7 per-family A/Bs
  are pre-CRN, same-batch reads with a ±2–3pp batch band and a ±5–7pp per-row A/A noise
  floor; the 2026-07-26 ablations are CRN-paired but still local, and ~20% of that pool's
  weight sits on rows recorded as not reconciling to live (A.3 #3/#4).
- **The usage counts are observational.** They describe another team's decisions and our
  pilot's counterfactual pick at the same state. They locate disagreement; they do not
  establish that their pick was better. The A/Bs are what establish that, and only for the
  families that were A/B'd.
- **`PTCG_DK = −21.84pp` is a floor, not a component measurement.** It disables deck-kind
  profiling, which is a precondition for most of the rest of the ledger.
- **The list is adopted.** The 60 cards are not our design, we say so here, in body §5, and
  in the provenance matrix (B.4.4), and nothing in this appendix should be read as a claim
  of deck-building authorship. The claim is narrower and is the one the evidence supports:
  **we chose this list against our own prior conclusion, on our own measured pilot, we can
  say what every card in it is for, and we have named the six slots we never tested.**

**Artifacts.** `agent/deck_crustle.csv` (the shipped 60);
`intel/deck_rebakeoff_2026-07-12.md` (the selection); `intel/budew_behavior_diff.md` (the
59,508-decision counterfactual replay behind the concept and every usage count);
`intel/agent_v7_results.md` §3–§4 (the per-family A/Bs and the ship gate);
`intel/deck_consistency_crustle_2026-07-21.md` and `intel/deck_consistency_starmie.md` (the
consistency mirror); `intel/frozen_final_baseline_2026-07-26.md` (the CRN ablations);
`intel/manabase_ab_2026-07-15.md` and `intel/sacred_ash_gate_result_2026-07-17.md` (the
rejected-edit ledger, with `intel/sacred_ash_gate_prereg_2026-07-17.md` as the binding
pre-registration); `intel/novel_lever_hunt_2026-07-17.md` §3.1 (the live-extracted 60-card
list); `intel/card_db_full.csv` (every card text quoted above); `agent/scoring.py` (the
`crustle_wall` profile and every utilization rule cited, each flag-toggleable).
