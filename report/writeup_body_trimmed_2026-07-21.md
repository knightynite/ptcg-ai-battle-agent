<!-- Trimmed writeup body 2026-07-21: naive/Kaggle counts re-verified after each edit batch — recount below-comment text after ANY change (Kaggle counter calibrated ~= naive whitespace split -1.1%: it read 2,498 where local naive read 2,518 on the untrimmed body; keep under the 1,900 goal, 2,000 hard cap).
     Cuts: §6 wrong-unit table -> prose + [F6]; header word-count labels; TL;DR para-2 compression (it summarized §3-§6); §3.5 de-dup vs §6.2; §5.4/§7 de-dup vs §1/§6; "safety fallback never optional" principle line (§3.0/§3.1 carry the ladder); "Information != value" aphorism; long figure tags -> short; phrase-level compression throughout. Subtitle's compliance disclosures folded into §2 principle 1 and §6.2.
     Source: report/strategy_report_draft.md §1-§8 at commit 24425a6. Paste everything BELOW this comment into the Kaggle editor. -->

## 1. TL;DR

Our most dangerous numbers were arithmetically correct but decision-wrong: the aggregate did not match the
unit of intervention. Our Crustle pivot trigger fired at 42.3% over 539 top-slice sides (a *side* = one
deck's half of one game, from the daily top-rated-games dump) — but eight teams supplied them, the top three 518/539 (96.1%). Re-keyed to a same-`(team, deck list)` panel, the "slide" was 45.2%→45.8%
(p=0.868), so we held the deck four weeks before lock. The same failure mode had already manufactured an
Alakazam-pivot narrative and a Rocket-Spidops "collapse" (both dissolved, §6). Catching our own decision
rule firing on the wrong population, and changing the decision instead of the deck, is the strongest
single result we own.

We rebuilt measurement at the decision-relevant unit: exact attack resolution via the engine's API; a
per-decision diff of top pilots (+21.4pp local meta — yet its third, pre-registered application returned a
CRN null: the gate, not the diff, certifies causality); a development-only paired-RNG harness; a rating backend conditioning on opponent strength; the re-bakeoff that reversed Starmie for Crustle. Live, on a
submission frozen since 14 July: five nightly reads span 866.9–918.8 — a draw
around the skill MLE 850, not new skill — with 0 crash/illegal/timeout losses in 642 games.

## 2. Problem framing & design principles

An agent sees its own hand but not the opponent's, either deck's order, or any prizes; coins, draws, and
shuffles are chance; a turn branches into thousands of legal multi-select sequences. Four principles:

1. **Never approximate the rules where the engine will do it for us.** Every legal *attack* resolves
   through the organizer's `search_*` API — exact by construction; non-attack planning stays heuristic;
   multi-turn search ships off (§7). Submitted agents use only documented Search APIs and per-perspective
   observations.
2. **When a layer fails, measure *why* before building the next** — our biggest gains are measurement
   instruments, not search algorithms.
3. **Every change clears its same-batch multi-seed gate, ships gated off, or ships as a non-regressing
   default with its below-gate reading disclosed** — disclosed cases: the tracker hooks (§4), the
   Budew meta leg (§3.4), and the v8/v10/v12 ledger rows (attached).
4. **Audit the measurement itself.** Unseeded RNG and generic-pilot pools produced phantom deltas (6pp, ~11pp) a naive gate would have banked (§6.2).

Outside evidence agrees (attachment; small-n): a rule-based agent beat ISMCTS/PPO in one card-game study, recent Kaggle sim leaders shipped rules-based bots, and one simple consistent deck out-laddered combo under bot piloting.

## 3. Agent architecture — the 70% core

**3.0 One decision.** Masked observation → tracker update (exact own zones, §4) → belief refresh →
enumerate legal actions → resolve every legal *attack* exactly via the engine's API (§3.2) → score
everything else heuristically (playbook, race math, overrides) → best legal action, inside the fallback ladder (§3.1); component deltas in §6.1. **[F1; nine figures, light/dark, F1–F12 with gaps; READ_ME_FIRST is the glossary.]**

**3.1 Crash-safe pilot.** Fallback ladder: smart policy → first-N-legal (exact `minCount`/`maxCount`) →
raw index; monotonic wall-clock reserve. Measured: **0 crashes / 0 illegal actions / 0 timeouts across
700,000+ local games (twelve generations) and 642/642 live ladder games**; p99 ≤ 13.5ms; live think ≤3.6s
of 600s. Per-tier activation was never instrumented: the honest claim is the lower rungs were never
*needed*, not that they work.

**3.2 The exact oracle.** The `search_begin/step` API is a caller-supplied determinization simulator: fill
hidden zones with a hypothesis and the engine advances a full game, resolving damage, weakness, KO, and
playability *exactly* for each legal attack regardless of filler. Determinization search here is the
documented Kiyotah recipe; ours is the exact-resolve integration and its failure boundary (§3.3).

**3.3 Where search stopped paying.** Depth-1–2 determinization-ensemble search measured **−2.5pp** (R2);
an opponent-reply rollout **−3.6pp** (R3; belief-search alone +1.4pp, not confident). Both ship gated off.

**3.4 The counterfactual behavior diff — our best hypothesis instrument, not over-credited.** WinDecks (#7) piloted our byte-identical Starmie list; replaying its 651 episodes (24,664 decisions)
decomposed 49.4% substantive disagreement into five rule families. Seven shipped patches (v3) scored
**+21.4pp on our *local* meta-weighted gauntlet (43.79→65.14%, 3/3 seeds)** and the agent climbed live
(≈590→≈750). That is a pre-CRN gauntlet magnitude, 77% weighted on two matchups whose rows later proved
unreliable (§6.2) — evidence of a climb, not a certified causal gain. Against Budew (#2, v7, 59,508
decisions) the method is sharper: **+5.8pp meta-weighted but +0.61pp live-band, missing its +3.0pp gate.**
A third, pre-registered application reproduced across two pilots at 20–500× its noise floor, then returned a **mechanism-confirmed CRN null** (0.0pp, p=1.0). The diff generates mechanically-grounded
hypotheses; the **gate** certifies which are causal. **[F10.]**

**3.5 Later iteration.** The v7–v12 generation ledger is attached; §6.2 carries the verdicts CRN changed.

## 4. Belief state

**(a) Archetype belief:** a top-quartile-share prior plus a signature-card classifier reads
~86–91% accurate by turn 3 (Alakazam ~100%); belief-completed determinizations beat junk fillers +0.8pp and gate the matchup playbook live.

**(b) The hidden-state tracker: exact-by-construction own-zone tracking plus exact public opponent-known constraints** —
opponent hidden state stays approximate. It never reads opponent-private zones: own prizes are inferred via legal own-deck search (792/800 streams); opponent identities enter only when the masked observation
reveals them (Masamikobayashi's public approach; integration and validation are ours). It consumes only the engine's
per-perspective-masked event log — card-counting, legal by construction. On 400 replayed episodes (57,589
decisions): **zone reconciliation 99.981%**; **own-prize identity 100%** (2,208 checks); **opponent-hand-known precision 100%** (6,517 checks); every failure path degrades to the
tracker-less pilot.

Honest result: five tracker hooks measured **+1.37 ± 2.3pp** over six seeds — short of our gate, so the
infrastructure shipped and the claim didn't. At 4× power they resolve: **−0.50pp ablated, CI
[−0.94, −0.05]** — worth ~half a point, harm excluded (B.4.2a). **[F3.]**

## 5. Deck design — re-decided twice (Deck Score 20%)

**5.1 The switch, against our own prior conclusion.** The R1-era bakeoff concluded nothing beat Mega
Starmie ex; re-run on the *current*, deck-general pilot, Budew's #2-ranked Crustle / Mega Kangaskhan ex
list beat our Starmie **+3.2pp meta-weighted (3/3 seeds) and +7.0pp on the offline live-band mix (6/6 seeds, two
batches)**, halving the second-seat tax (−20.0→−9.8pp). Alakazam and Rocket measured −22/−9pp for our
pilot: deck EV ≠ our-bot EV, twice.

**5.2 Final submission.** Both active submissions run this list; generation diversity (v7–v12) replaced
the Starmie hedge through submission-order attrition — an explicit limitation (§7).

**5.3 Consistency and roles.** The *current* list is Budew's, adopted unmodified; we re-measured it with the Starmie-era instrument (exact
hypergeometric + seeded Monte-Carlo; deck_consistency attachments): mulligan **30.0%** — the deck *switch* cut the old
45.9%, where the 11-Basic fix (22.2%) had measured −5.5pp and been rejected; wall online by turn 2 in
66–70% of games; the 3-energy attacker never is — the wall buys that time. A manabase mechanism-vs-outcome A/B (A.7) is the outcome-level check. Roles: Crustle wall (Mysterious Rock Inn
blanks ex-attack damage) + Mega Kangaskhan ex closer + Dwebble/Shaymin feedstock. **[Appendix D: deck concept,
per-card utilization, rejected edits.] [F5.]**

**5.4 Known holes, carried openly.** The Kang-less single-prize grinder is a structural counter
(same-chassis local 29.7% ≈ live 30.8%): its non-ex attacker bypasses the wall and denies a three-prize target; eight live losses do not isolate its size. A mill-aware deck-out fix stays unattributed
(A.2); Starmie-blitz is unsolved, shipped off. The deck-pivot trigger's firing and dissolution are
§1's audit; the durable output was retiring a rule reading pilots as archetypes. **[F4.]**

## 6. Results: what survived the unit audit

Five readings mistook an aggregate for the causal unit — a build "differing from itself" by 6.0pp across batches; v10's 71.75% on a generic-pilot pool (re-based 60.82%, ~11pp phantom); archetype-keyed mirror reads (true exact-list history 2/7); Alakazam 46.4% read as a leak but par-consistent rating-conditioned (13 obs vs 14.14 expected); the §1 pivot trigger. Re-keying each to the decision unit reversed or
dissolved it. **[F6.]**

Separately, a controlled run against the provided baseline (same deck, CRN, n=300/row) reads **+38.4pp**, or **+35.6pp** dropping every row that fails live reconciliation — and that agent moves randomly, so it sizes the starting gap, not strength. Ablation puts 57% in one flag family that gates much of the rest (B.4.2).

**6.1 Surviving evidence ladder** (levels not comparable across instrument eras):

| Gen | Config | Result | Verdict |
|---|---|---|---|
| R1 | exact-oracle pilot | 43.8% meta | baseline |
| R2/R3 | search / belief+rollout | −2.5 / −2.1pp | OFF |
| v3 | diff #1 (WinDecks) | **+21.4pp local meta**; live ≈590→≈750 | shipped |
| v6 | deck → Crustle | 68.0 meta / 57.9 band | shipped |
| v7 | diff #2 (Budew) | **+5.8pp meta**; band +0.61 | meta leg only |
| v11 | pool re-audit + mirror fix | rebased 60.82%; **+0.58pp (p=2e-4)** | best observed draw (§7) |

**6.2 CRN.** Unseeded engine RNG gave v8-vs-v8 a **6.0pp phantom null**. Interposing the libstdc++
`random_device` symbols makes paired arms replay identical shuffles/coins/prizes: **100% transcript-identical replay of identical builds (entropy-pinned)**, **typically 16–44× variance reduction in near-clone gates** (2.2× low case, the dissimilar-policy regime). It recovered two falsely-convicted patches and
confirmed two harmful. PokeForge described native-shuffle interposition; ours is the
RDRAND/libstdc++ implementation, audit, and four changed verdicts. Development-only: excluded from every
submission, it changes no card rules and no agent-visible information. **[F12.]**

**6.3 Rating as conditioning instrument.** Fitted from 20,192 submission-sides: dμ = 9.0·(S−E), scale
324, settle **T = 1075 + 324·log₁₀(p/(1−p))**. One checkpoint held (v7 local 66.8% → live 65.5%); v10 settled below projection — we condition, never certify. A pre-registered forward check passed its rule but is weak — any centre from 835 to 939 fits its reads (A.10). **[F11.]**

**6.4 Live results.** Five consecutive nightly reads of the unchanged pair span **866.9–918.8** (rank **278–460**, latest **416/5,774**) — a **rating draw**, not new skill; the estimate of record stays v11
settle MLE **850 [794,906]**, ~150 points under the top-100 cutoff. The −19pp local second-seat gap replicated live (−17.8pp), halved with Crustle (local −9.8pp), and a 12,925-decision diagnosis read it as **opponent-strength-dependent tempo, not a policy-addressable seat advantage**: the best seat lever (+32.3pp) inverted across versions and nulled pooled — declined. **[F7.]**

## 7. Honest negatives & limitations

**[Appendix A: the full negatives ledger.]** Rejected patches include turn-line search −2.5pp, mulligan fix −5.5pp and four seat recipes; two confirmed *harmful* stay off; four tracker hooks read below gate yet ship as disclosed defaults (the gate, not
the patch, was the error). We withdrew three internal claims — including our headline: v11's mirror fix
(+16.7pp, p≈2e-7) was credited with the live climb, but its whole gain sits in the one row that overshoots
live by ~35pp; the reconciling rows read ~0. **v11 is our best observed leaderboard draw, not a proven
best policy** — v10 was evicted ~flat at 53 games before a clean comparison; near-clone v12 landed ~127
points lower. Five failures shared one mistake — **an aggregate mistaken for the decision-relevant unit**
(§6, F6); worst: a generic pilot standing in for a tuned one (96.7% local, 27% live). We now check that
the key we group by is the key the decision depends on. Limitations: unseeded RNG (CRN mitigates, not eliminates); against Alakazam, 52% of the top slice, our best offline row reads 92% versus a live 46.4%,
so we **cannot gate our largest matchup offline at all**; ~3-day meta half-life; per-list live n=5–13 is
directional, not established.

## 8. Conclusion

The campaign's durable result was learning **which measurements deserved decisions** — including
discounting our own headline. What earned its keep: a behavior-diff that generated two decks' playbooks
alongside a real climb, then taught us that off-policy agreement is not a causal win; a deck decided twice against our own conclusion; a paired-RNG harness
that caught our gate convicting good patches and clearing bad ones. What we could *not* establish, we say
so: v11 is our best observed draw, not a proven best policy; several offline opponent rows still fail live
reconciliation. Standing: **top 4.9–8.2% across five nightly reads**. Reproducibility: the attached code regenerates every figure; our agent, harness and diff code are MIT-licensed at **github.com/knightynite/ptcg-ai-battle-agent**
— original code only, no engine binaries, competition data, or third-party agents; every published file is hashed in its MANIFEST.
