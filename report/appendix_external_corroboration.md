# Appendix C — External corroboration survey

*Attachment to the Strategy Writeup. Backs the single sentence in body §2: "Outside evidence
agrees: tuned rule-based agents beat ISMCTS/PPO in card games, recent Kaggle sim winners
abandoned pure RL, and simple consistent decks out-ladder combo under bot piloting."
References to `intel/…`, `scripts/…`, and `agent/…` paths are internal campaign
artifacts: they ship in the released code repository accompanying this writeup, not as
separate attachments.*

**Timing disclosure (stated first because it bounds the claim):** this evidence was gathered
2026-07-17, *after* our architecture and deck decisions were made and measured. It is
corroboration of a posture we had already validated internally — not the motivation for it,
and we do not present it as such.

**Provenance.** A structured web research sweep (5 angles → 22 sources → 69 extracted claims),
with the 25 decision-relevant claims each adversarially verified by three independent
reviewers: 23 confirmed, 2 refuted. The three claims below are confirmed ones with primary
identifiers; the refuted ones are listed at the end because excluding them silently would be
the same over-claiming this campaign exists to avoid.

## C.1 Tuned rule-based agents beat ISMCTS/PPO in card games

**Source:** Malla, S. R., *AI Agents for the Dhumbal Card Game: A Comparative Study*,
arXiv:2510.11736 (open code: github.com/sahajrajmalla/dhumbal-ai).

Across 1,024 simulated rounds of Dhumbal (multiplayer, imperfect information), the rule-based
"Aggressive" agent won **88.3%** (95% CI [86.3, 90.3]) versus **ISMCTS 9.0%** and **PPO 1.5%**.
The paper's own conclusion is the efficacy of simple heuristics under moderate information
asymmetry. Confidence: high (published comparative study, exact numbers, open code) — but it
is one game; we treat it as supporting the *plausibility* of our choice, and our own R2/R3
negatives (search measured −2.5/−2.1pp on our gauntlet, body §3.3) as the evidence that
decided it.

## C.2 Recent Kaggle simulation winners moved away from pure RL

**Sources:** public post-competition writeups from Kaggle simulation competitions —
Lux AI Season 2, 1st of 646: a stateful rules-based bot with forward planning, not RL
(kaggle.com/competitions/lux-ai-season-2/writeups/ry-andy-1st-place-solution; code at
github.com/ryandy/Lux-S2-public), alongside the 4th-place FLG deep-RL methods report
(kaggle.com/competitions/lux-ai-season-2/discussion/406702); and Kore 2022, 4th place,
titled "rule based" by its author after abandoning RL mid-campaign
(kaggle.com/c/kore-2022/discussion/340157).

Confidence: high for the factual method descriptions (self-reported by the winners in public
writeups); medium for any generalization beyond those two ladders. What we take from it is
narrow: heuristic/planning agents holding top placements in modern Kaggle sim competitions is
normal, not an anomaly requiring apology.

## C.3 Simple consistent decks out-ladder combo under bot piloting

**Source:** this competition's own public data — a public agent repository
(github.com/wmh/ptcg-abc) whose simple Bellibolt consistency deck rated **~836 Elo** while a
Typhlosion combo build of the same agent class sat at **~532** (our record of the comparison:
`intel/deck_ceiling_analysis.md`).

Confidence: **medium — this is n=1 and we label it so.** It corroborates, from someone else's
agent, the same mechanism our own re-bakeoff measured directly (body §5.1): a bot pilots a
simple gameplan cleanly and a combo gameplan clunkily, so deck EV under bot piloting diverges
from deck EV under human piloting. Our deck decision rests on our measured +3.2pp/+7.0pp
(3/3 and 6/6 seeds), not on this anecdote.

## C.4 Background reference

Kowalski & Miernik's Strategy Card Game AI competition retrospective (arXiv:2305.11814)
documents the broader pattern in card-game AI competitions that motivated the sweep's search
angle in the first place. Cited by identifier; the paper is third-party and is not
redistributed with this writeup.

## What the sweep did NOT support (kept for honesty)

- Two claims were **refuted in verification** and excluded: the "prioritized task-list"
  structural framing attributed to the Kore writeup, and a "queue-filling as
  imperfect-information planning" mechanism attributed to the Lux S2 FLG report. Neither is
  used anywhere in our writeup.
- The sweep also surfaced ISMCTS/OOS as the one search class we never built. We declined it
  for measured reasons (it targets misplay under uncertainty; our diagnosed losses are
  structural/tempo — body §7, Appendix A), not because the literature dismisses it. The
  ISMCTS literature itself reports it roughly tying determinized UCT on average while winning
  the hardest hidden-information deals — consistent with our decision, not proof of it.
