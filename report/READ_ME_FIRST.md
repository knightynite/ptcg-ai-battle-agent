# Read me first — a five-minute orientation

*Attachment to the Strategy Writeup "Measure the Right Unit". This page exists so a reader
can decide, quickly, what this submission claims and where each claim is evidenced. Nothing
here is new evidence: every figure below is stated and sourced in the writeup body or in one
of the four appendices, and this page points at those.*

---

## What we built, in one paragraph

A rule-based Pokémon TCG Pocket agent that plays a wall-and-clock deck: it makes the prize
race unplayable and wins on the opponent's library. There is no learned policy and no runtime
network call. Every legal attack is resolved exactly through the organizer's own search API
rather than estimated, a hidden-state tracker supplies what the rules legally allow us to
know, and everything above that is explicit heuristics. It has played **642 live ladder games
with 0 crashes, 0 illegal actions and 0 timeouts**, and over 700,000 local games across twelve
generations.

## What the report is actually about

Not the agent. **The measurement.** Our most dangerous numbers were arithmetically correct and
decision-wrong, because the aggregate was not the unit the decision acted on. The headline
case: a deck-pivot rule fired at 42.3% over 539 "top-slice sides", which looked like a broad
population but was eight teams, 96.1% of it from three of them. Re-keyed to a same-`(team,
deck list)` panel the "slide" was 45.2%→45.8% (p=0.868). We changed the decision rule instead
of the deck, and held the deck to the end. Two other narratives — an Alakazam pivot and a
Rocket-Spidops "collapse" — dissolved the same way.

## The deck, in plain language

Crustle's ability blanks **all attack damage from the entire ex / mega-ex class**, which is
what the top of this format is built from. Put it in the Active Spot against an ex board and
those attacks cannot remove it. Behind that wall the deck denies prizes, strands the
opponent's board with Boss's Orders and then *declines* to knock the target out (a knockout
would free the board and restart the clock), and spends none of its own library — in a game
decided by whose deck empties first, cards in hand are hit points. **62% of this deck's wins
are the opponent decking out (444 of 713).** Median win: 20 turns.

**Stated plainly because it bounds the Deck claim:** the 60-card list is **adopted, not
designed** — it is the card-id multiset of the #2-ranked ladder team's list, unmodified. What
is ours is the *re-decision* (a bakeoff that reversed our own published conclusion), the
utilization, and two edits we measured against it and rejected. Appendix D is the full
treatment.

## Where each grading criterion is answered

| Criterion | Where |
|---|---|
| **Model 1 — clarity of approach** | Body §2 (design principles), §3 (architecture) · figure F1 |
| **Model 2 — originality & soundness** | §3.2 exact attack oracle · §3.4 counterfactual behaviour diff · §6.2 paired-worlds harness · F10, F12 · Appendix B |
| **Model 3 — behavioural consistency** | §3.1 fallback ladder · the 0-incident record · F1 |
| **Model 4 — avoids over-reliance on states / matchups** | §6 (the unit audit — the spine of the report) · §6.4 seat diagnosis · §7 limitations · **Appendix A** · F6 |
| **Model 5 — simulation performance** | §6.4 · F7 |
| **Deck — concept & alignment with strategy** | §5.1–5.2 · **Appendix D.1–D.2** · F4 |
| **Deck — key-card selection & utilization** | §5.3 · **Appendix D.3–D.4** · F5 |
| **Report — clarity** | this page · FIGURES_README.md · Appendices A–D |

## The three results we would defend

1. **The unit audit.** Five readings mistook an aggregate for the causal unit; re-keying each
   reversed or dissolved it. Catching our own decision rule firing on the wrong population is
   the strongest single result we own. (§6, F6)
2. **The paired-worlds harness.** Interposing the engine's random-device symbols makes two
   arms replay identical shuffles, coins and prizes: 100% transcript-identical replay,
   typically 16–44× variance reduction. It recovered two patches we had falsely convicted and
   confirmed two as genuinely harmful. (§6.2, F12)
3. **The counterfactual behaviour diff.** Replaying top pilots decision-by-decision and
   diffing against our own choice at the same state. It is a strong *hypothesis* instrument —
   and we say so, because its third, pre-registered application returned a null under the
   paired gate. The gate certifies causality; the diff does not. (§3.4, F10)

## The three things we got wrong, kept in the package

- A deck-out attribution we **withdrew** after it failed to reconcile with live play (A.2).
- A ship gate that was **wrong by construction** — it demanded an effect its own instrument
  could not resolve, and judged five heterogeneous hooks as one bundle (A.9).
- Offline rows that **do not reconcile to live results**, including our largest matchup, which
  we cannot gate offline at all (§7, A.3).

Appendix A is the full ledger of rejected patches, withdrawn claims and failed instruments. It
is not an afterthought; under Model criterion 4 it is the evidence.

## Glossary

| Term | Meaning |
|---|---|
| **pp** | percentage points (a change from 43% to 65% is +22pp) |
| **CRN** | *common random numbers* — running two variants against identical randomness so the difference between them is signal, not shuffle luck |
| **MLE** | *maximum-likelihood estimate* — here, the skill rating that best explains our observed results |
| **side** | one deck's half of one game (a single game supplies two sides) |
| **top slice** | the organizer's daily dump of top-rated games |
| **META / BAND** | our two offline opponent weightings: META = frozen top-quartile field; BAND = a mix drawn from the live 700–1000 rating range |
| **gate** | a ship threshold fixed *before* a measurement, so the verdict cannot be chosen after seeing the result |
| **determinization** | filling unknown hidden zones with one concrete hypothesis so a simulator can play the position out |
| **behaviour diff** | replaying another pilot's real games and recording, at each decision, what we would have done instead |
| **entropy-pinned** | both arms draw from the same pinned randomness source, so identical builds replay identically |
| **submission-order attrition** | each team holds only two active ladder slots, so a new submission evicts the oldest — older agents rotate out by age rather than by choice |
| **ISMCTS / PPO** | two standard learned/search baselines from the literature (information-set Monte-Carlo tree search; a reinforcement-learning algorithm) |
| **ex / mega-ex** | high-HP multi-prize Pokémon cards; the class this deck's wall is immune to |

## Suggested reading order

**Body** (the 2,000-word writeup) → **Appendix D** if you grade the deck → **Appendix A** if
you grade rigour → **Appendix B** for the generation-by-generation ledger and provenance →
**Appendix C** for outside corroboration. `FIGURES_README.md` says what each figure encodes,
and `reproducibility.py` regenerates all of them from the shipped numbers.

## Standing, stated as a range because that is what it is

The submitted pair has been **unchanged since 14 July**. Across the five consecutive nightly
reads 07-23 → 07-27 it scored **866.9–918.8**, ranking **278–460** of 5,546–5,774 teams
(top 4.9–8.2%); the latest is 416 of 5,774. That spread on a frozen agent is the report's own
thesis applied to its own headline number: a single day's rank would be a draw quoted as a
skill. The estimate of record is the pre-committed settle MLE **850 [794, 906]**.
