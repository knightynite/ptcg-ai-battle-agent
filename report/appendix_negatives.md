# Appendix A — Negative results, withdrawn claims, and instrument failures

*Attachment to the Strategy Writeup: the complete negatives ledger behind the body's §7
summary — the body carries the summary and the lessons. References to `intel/…`,
`scripts/…`, and `agent/…` paths are internal campaign artifacts, cited by name for
audit-trail honesty; the released code repository accompanying this writeup ships the
agent, scripts, and report sources, and the key cited artifacts are summarized here and
in Appendix B.*

Every entry is a claim we tested and did not get to keep, or a measurement we found we
could not trust. Each links to the committed artifact that establishes it. We keep this
list because it is the honest denominator behind the results we do report: the same
method that produced +21.4pp also produced the entries below.

## A.1 Rejected patches (measured, not shipped)

| # | Claim | Measured | Disposition |
|---|---|---|---|
| 1 | Multi-turn turn-line search beats the single-turn exact oracle | **−2.5pp** | OFF (`PTCG_SEARCH=0`) |
| 2 | Opponent rollout / belief-informed determinization improves play | **−3.6pp** rollout ablation (R3 full stack: −2.1pp) | OFF |
| 3 | Fixing the 45.9% mulligan rate by adding basics | **−5.5pp** | Rejected; off-plan basics are prize-race liabilities |
| 4 | Tracker hooks clear a **+3.0pp** ship gate | **+1.37 ± 2.3pp** (pre-CRN, 6 seeds) | v4 not shipped *as v4*; hooks T2–T5 became defaults and **are live in v11**. Only T1 (Judge-EV) stays off — it ignored Judge's cost to our own hand. **The gate, not the patch, was the error** — see A.9 |
| 5 | v9 bench-floor + energy-denial | missed both gate legs | **HELD, unshipped** |
| 6 | Seat-gap recipes (four distinct attempts) | all non-positive | Gap halved by the deck switch, never solved |
| 7 | Starmie-blitz counter (SBL) | wrong sign | Shipped OFF |
| 8 | Manabase: −4 Spiky / +4 Basic Grass (see A.7) | **−8.00pp**, p=0.0032, 3/3 seeds | Rejected; deck unchanged |

Two patches (ED, O1) were confirmed **genuinely harmful** under CRN (p=0.013, p=0.0035)
and remain off. Two others (B2F, B3) had been **falsely convicted** by the pre-CRN
instrument and were recovered into v10 — see A.3.

## A.2 Claims we withdrew after they were already published internally

**The P-MIR attribution.** v11's mirror deck-out fix measured **+16.7pp (p≈2e-7)** on the
Great-Tusk-mill row and we credited it with v11's live jump to ~848. A per-`deck_key`
re-audit withdrew that: the entire local gain sits in the one row that **overshoots our
live result against the same list by ~35pp**, while the rows that do reconcile with live
(the real bleeder: 29.0% local vs 20–31% live; and the true mirror) measure P-MIR at **~0**. The live loss
class it targets did not fall distinguishably — while-ahead deck-outs went v10=1,
**v11=0**, v12=2, non-monotonic at n=6–12/version.

We did not revert it: the fix is mechanically plausible and harmless, and a mill fix
*should* only show on the mill row. What we cannot do is claim its size.
**v11 is our best-rated agent and we cannot say why** — v10 was evicted approximately flat
at 53 games (final 705.5; per-game trajectory 697→706→710→705.5 across games 30–53, per
the adversarial audit), so v10 and v11 were never cleanly compared live.
Artifacts: `intel/mirror_alakazam_instrument_2026-07-15.md`, `intel/chassis_bias_2026-07-15.md`.

**Re-tested 2026-07-26, after the engine changed under us — and the withdrawal stands.**
The competition engine shipped a fix for "a bug that occurred when discarding energy," and
a later baseline run found this exact mill row had moved **+11.00pp** across that
transition while 24 of 25 other rows reproduced within ±2.7pp. A mill matchup is precisely
where energy-discard resolution would bite, so the whole P-MIR measurement was suspect. We
re-ran the toggle CRN-paired at n=300/row **on both binaries** from one verified codebase:
**+17.00pp pre-fix, +17.33pp post-fix** (p=8.4e-07 / 5.7e-07). Holding the configuration
fixed and swapping only the binary changes **1 of 300 games on that row (0 of 300 in the
control arm; 17 of 3,600 across every row and arm)**, against an A/A null of 2 discordant
games in 1,800. The sharpest version of that test is the one that settles it: the shipped
v12 configuration run on both binaries reads 72.33% on each, **0 of 300 games changed**.
The effect is real and engine-independent; the engine hypothesis is refuted.

The same run **overturned a hypothesis of our own, and found a worse bug than the one we
went looking for**: the +11.00pp was not the engine. The archived pre-fix arm had been run
from a build whose `main.py` baked no flag defaults, so `PTCG_MIR` fell back to `"0"` and
**P-MIR was silently off in an arm we had recorded as having it on** — the same
unrecorded-build-state failure as A.3 #5, one directory over, caught only because an
unrelated result looked strange. (Stated as inference, not reading: that runner script is
not on disk and the logs carry no environment dump, so the flag state is reconstructed
from artifacts. Two loose ends we are not papering over — the same "nothing baked, nothing
exported" logic would put `PTCG_BF` and the `PTCG_L2` group off in that arm too, which we
did not test; and the archived arm still differs from our flag-matched replication in 18
of 300 games on a row whose A/A floor is 0 of 300, so something beyond that one flag
differed and we cannot say what. The engine hypothesis is refuted independently of all
this, by the 0-of-300 config-fixed binary swap above.)

**None of this restores the attribution, and we are not restoring it.** Verifying a
measurement is not validating a claim. The effect is still confined to the single row that
fails live reconciliation by ~35pp; the two rows that do reconcile still read +1.00pp
(p=0.74) and +0.67pp (p=0.84); and the size is configuration-sensitive — the same toggle
reads **+17.33pp in the v11 configuration the attribution was actually made about and
+9.67pp in v12**, both of which shipped. Those two are not formally distinguishable at
n=300 (difference 7.7pp, 95% CI [−1.5, +16.8], p≈0.10), so we state it as a caution
against quoting one number as *the* size, not as a demonstrated version effect. Our
earlier reporting did not say even that much. Artifact:
`intel/pmir_engine_recheck_2026-07-26.md` (16,200 games, engine binding proven from
`/proc/self/maps`, old-binary run reproduces the archived 2026-07-15 logs seed-for-seed).

**"Alakazam is our biggest leak."** v11's 46.4% against Alakazam (52% of the top slice)
read as a deficit until rating adjustment: opponents averaged **876**, and the fitted
MLE over those 28 games puts our skill at **854 [746, 962]** — **consistent with par: the
data give no evidence of a leak, and 28 games cannot distinguish par from a modest
deficit** (the CI spans 746–962). We withdrew the leak claim and stopped treating this as
a lever — not because a lever was proven absent, but because nothing here licenses
building one. Artifacts: `intel/mirror_alakazam_research_2026-07-15.md` (expectation-based
par check) and `intel/majkel_deepdive_2026-07-16.md` (the fitted MLE).

**"Self-built opponents flatter us on unfamiliar archetypes."** Our leading explanation
for the P-MIR reconciliation failure — that our Crustle-tuned chassis pilots foreign
lists badly and hands us strawmen — was **tested and refuted**: same-archetype rows show
a +17.6pp local-vs-live gap versus +16.6pp for foreign ones, and the best-powered foreign
row (`starmie_blitz`, n=29 live) *undershoots* live by 12.8pp — the opposite sign. The
surviving rule is narrower and still useful: **a newly built opponent row is untrusted —
and usually inflated (mean local-vs-live gap ≈ +17pp), though not uniformly:
starmie_blitz undershoots — until reconciled, whatever its archetype.** Artifact: `intel/chassis_bias_2026-07-15.md`.

## A.3 Instrument failures (found by us, before they decided a shipment)

1. **Pre-CRN noise, ±5–7pp/row.** The unseeded engine RNG produced **6pp phantom deltas
   on byte-identical builds**. It falsely convicted two good patches and let two harmful
   ones look neutral. Fixed by common-random-numbers via `random_device` interposition
   (16–44× variance reduction). `intel/measurement_harness_2026-07-13.md`,
   `intel/crn_reaudit_2026-07-13.md`.
2. **~11pp phantom pool equity.** The band pool's opponents were weak enough that v10's
   headline 71.75% was really **60.82%**. Re-based honestly. `intel/agent_v11_results.md` §1.
3. **The generic-pilot mirror row: 96.7% local vs 27% live.** An untuned opponent
   averaged away the very tuning that decided the matchup.
4. **The alakazam full-agent row: 92.0% local vs 46.4% live**, non-overlapping CIs — and
   this one was *not* a generic pilot (tuned build, 0 crash, 0 illegal, normal decision
   timing). Same useless result by a different route. **We currently cannot gate our
   largest matchup (52% of the top slice) offline at all.** We report this rather than
   quoting the 92%.
5. **A stale build.** The directory our v11 gate had been pointing at was **byte-identical
   to the v10 build** and contained none of the patch under test. Toggling the patch
   against it is a **silent no-op**: both arms emit identical outcomes and the ablation
   reports zero, with no error. Now guarded by a hard assertion that fails loudly.
   **Extended 2026-07-26 — the guard was the wrong shape.** It greps the build for a
   string from the patch under test, which catches a tree that is *behind* the version
   being gated but is blind to one that has drifted *ahead*: the same directory now
   carries **five** post-v11 flags present in no shipped v11 artifact, and the guard still
   passes. Two recorded failures share this root, and the guard was written for neither: a
   build silently *older* than claimed (this entry), and A.2's re-test — where the arm ran
   code **byte-identical** to its comparator but its `main.py` baked no defaults, so the
   flag fell back to 0. That second one is a *configuration* mismatch, not a version one;
   an earlier draft of this paragraph called it "a build silently newer", which our own
   md5 record contradicts. Forward drift is a third case, caught before it decided
   anything only because we went looking. A string check sees none of the three. The rule
   we should have written: **assert
   build *identity* — hash the tree against a named artifact — and archive an environment
   dump beside every gate log**, so the arm's flag state is read rather than reconstructed.
6. **A hazard we recorded as a defect, and then measured the distance to.** The pilot
   gates its exact-attack oracle on accumulated wall-clock: `allow_search = (not
   _search_disabled) and (_game_elapsed < SEARCH_RESERVE_SEC)` (`agent/pilot.py`), where
   `_game_elapsed` accumulates `time.monotonic()` deltas across our own decisions in a
   game and the reserve is 480s against the 600s live player clock. The gate is live in
   the shipped configuration — `PTCG_SEARCH=0` disables the multi-turn plan search only,
   never the oracle — so we first wrote this up as a load-dependent instrument failure:
   run two arms at once, slow the machine, and the agent under test quietly loses its
   oracle mid-game. **We checked the magnitude afterwards, and the claim does not survive
   it.** With search off our decisions cost p50 0.12–0.17ms and p99 0.8–2.8ms; a gauntlet
   game averages ~36ms of wall-clock for *both* players; the harness caps a game at 3,000
   decisions across both sides. Even in an impossible worst case — every capped decision
   ours, each at the slowest we have ever recorded — our per-game clock reaches **8.4s,
   1.7% of the reserve.** Tripping the gate needs a 57× slowdown there and ~10⁴× at
   observed game lengths, while oversubscribing processes buys single digits. The
   harness's own 520s per-game timer has counted **zero across every run on record**, and
   the worst live game used 0.7% of its 600s clock. The mechanism is real; the distance to
   it is four orders of magnitude; **no result of ours is affected.**

   We also withdraw the protocol claim we made while we believed otherwise. Our gates were
   **not** uniformly sequential: the v3, v4, v5 and deck-bakeoff batches launched 6–24
   concurrent processes (`agent/tools/run_full_v4.sh` and siblings), and that includes the
   run behind the +1.37pp tracker-hook reading in A.1 #4 — the very gate A.9 is a
   post-mortem about. Strictly sequential execution is documented from v8 onward. What
   protects those older numbers is the arithmetic above, not a protocol we turned out not
   to have had.

   The general lesson survives, and it has a live instance we walked past while writing
   the wrong one: with the plan search enabled, `PER_DECISION_BUDGET = 2.5s` truncates the
   determinization loop on the same monotonic clock (`agent/search.py`), so load changes
   *how many* determinizations complete — degrading continuously rather than at a cliff,
   with ~25–80× headroom at measured search-on p99. **If any behaviour is gated on
   wall-clock, throughput is an experimental variable and must be held fixed like any
   other — and measure the distance to a threshold before recording it as a defect.**
   This entry is the ledger catching its own author: an unfired mechanism was written up
   as a discovered failure, and an independent check found it within the hour.

## A.4 The recurring failure mode, stated once

Four of the entries above are the same mistake wearing different clothes: **an aggregate
was mistaken for the causal unit.**

- A *generic pilot* stood in for the tuned pilots that actually decide matchups (96.7% vs 27%).
- An *archetype label* (`opp_class`) stood in for the deck (`deck_key`). Aggregated, it said
  **"our own deck beats us at 14%"** — a vivid, wrong, and immediately actionable story. Split
  by list, our own list was not the problem at all; three *other* lists of the same archetype were.
- We then made the identical error **on our own side of the same table**: a "healthy 53%
  true mirror" pooled games played with our *previous* deck. On the current list the true
  mirror is 2/7 = 28.6% — the control we thought we had did not exist.
- And the rating pool itself: a raw 46.4% is a leak or par depending entirely on who we played.

The rule we now apply before believing any number: **check that the key you grouped by is
the key that causes the outcome.** It cost us two days across two occurrences; it was
caught both times by splitting the group and re-asking.

## A.5 A stopping rule, recorded as a result

We spent two days measuring v12's Lucario patches on the live ladder. The A/B never
resolved — a second full day of laddering added **two** encounters. The reason is the
result: **Lucario is 0.4% of the field and 0.0% of the top slice.** The recommendation on
the table was to build a tuned Lucario instrument; we rejected it. It would have
perfectly optimized a matchup we meet roughly once a day, against opponents outside the
slice we were trying to climb into. *We could not measure it because we do not play it.*

We reallocated to the 78% of top-slice games (Alakazam + Crustle-class) — and that
redirect was itself **half-wrong**, which we record rather than quietly fix: Alakazam
turned out to be par, not a leak (A.2), and the Crustle bleeder that replaced Lucario has
**zero** top-slice share of its own. We had swapped a 0.4%-of-field target for a
0%-of-top-slice one. The single candidate it produced — a shared-axis manabase change —
was then **falsified too** (A.7).

So the stopping rule is the durable output here, not the redirect it justified: **a
matchup you cannot sample is a matchup that cannot pay.** Field share is a *prerequisite*
for a lever, not a tiebreaker between levers — and we now check it before, not after,
committing a build cycle. Artifact: `intel/lever_redirect_2026-07-15.md`.

## A.6 Limitations we could not remove

- **Unseeded engine RNG** — mitigated by CRN (16–44×), not eliminated; the Search API's
  own mt19937 still flips ~3% of games on the worst identical-build null row (9/300),
  unbiased.
- **Opponent-model fidelity** — our local opponents are proxies whose piloting quality we
  can only validate where live *n* permits. Where it does not (Alakazam), we say so.
- **Meta half-life ≈ 3 days** — any matchup conclusion older than a few nights is a
  hypothesis again.
- **Small live n per list** — the per-`deck_key` records that drive our current reads are
  n=5–13. They are directional, not established; we mark them as such rather than
  rounding them into confidence.

## A.7 The most instructive negative: a confirmed mechanism that still lost

Our last deck candidate was chosen to be *shared-axis* rather than matchup-specific:
**−4 Spiky Energy / +4 Basic Grass**, holding 13 Energy. It raises Grass providers 5→9
(testing whether payable-Crustle uptime is the bottleneck against the grinder that has 23
to our 5), and cuts special Energy 12→8 (shrinking what Enhanced Hammer can strip in the
52%-share Alakazam pool). The reasoning for cutting *Spiky* specifically was card text:
Alakazam's Powerful Hand places damage **counters** as an effect, and Spiky only triggers
when its holder is **damaged by an attack** — so Spiky looked inert where it mattered.

We pre-registered the falsifiers, including one that turned out to decide the result:
*a win-rate move with no mechanism move is not evidence.* So we instrumented the
mechanism, reading the **engine's own legality computation** rather than reimplementing
energy math (`agent/tools/mechanism_instrument.py`).

**The mechanism moved exactly as predicted. The win rate moved the other way.**

| row | A | B | Δpp | McNemar p |
|---|---:|---:|---:|---:|
| **`fdedde79` grinder (primary gate)** | 29.7 | 21.7 | **−8.00** | **0.0032** |
| self-mirror (control) | 53.3 | 48.3 | −5.00 | 0.180 |
| Typhlosion hybrid | 57.3 | 54.7 | −2.67 | 0.484 |
| Alakazam (regression-only) | 92.0 | 88.7 | −3.33 | 0.087 |
| Majkel 4-Hammer Alakazam | 93.0 | 91.0 | −2.00 | 0.263 |

Payable-Crustle turns **+9.4%**, attacks/game **+8.6%** — the bottleneck hypothesis was
*correct* — while the primary gate fell 8pp, consistently across all three seeds
(31/29/29 → 25/19/21). Every row moved negative. 3,000 games, 0 crashes, 0 illegal
actions.

The explanation is the same card text, read one matchup too narrowly. Spiky is inert
against Alakazam's counter-placing *ability* — but the grinder attacks with **Superb
Scissors**, a genuine damaging attack, 12+ times per game. Spiky was retaliating all
along. We cut it, and lost more to the missing retaliation than we gained in fuel —
**worst on the very row the change was designed to fix.**

The lesson we keep: *confirming your mechanism does not confirm your change.* A correct
causal story about the bottleneck told us nothing about the cost of the resource we spent
to relieve it. Only the paired outcome did. Artifact: `intel/manabase_ab_2026-07-15.md`.

## A.8 The known-value control — and the version of it we got wrong first

Everything in A.3 is a variant of one problem: we cannot tell whether a local opponent is
a fair proxy for a live one, because we do not know the true value the row should report.
Live reconciliation is the only external check and it needs live *n* we often lack
(Alakazam — 52% of the top slice — gives us 28 games; per-list we have 5–13).

The escape is a row whose true value is known **by construction**: run the **byte-identical
build against itself** (A/A), where the true effect is exactly **0.00pp** — not by
assumption, but because both arms are the same program. Any non-zero reading is pure
instrument. This is the control that exposed our worst measurement failure: the pre-CRN
harness returned **6pp deltas between byte-identical builds** (A.3 #1). Under CRN the same
null collapses to ~0, which is what licensed us to act on sub-1pp effects at all.

**We first wrote this section around the wrong control, and the error is worth keeping.**
We claimed the *self-mirror* row (our list on both sides, reading 53.3%) was self-validating:
"symmetry forces 50%, so any deviation measures the instrument." That is invalid twice over.
**A shared 60-card list does not force 50% — identical *policies* do**, and our self-mirror
row runs a v10-chassis opponent against a v11 agent, so the arms are not symmetric at all.
And under balanced seat alternation first-seat advantage **cancels**, so 53.3% cannot be
read as "50% plus seat"; it is simply *consistent with* 50% at this n. The row is a weak
sanity check, not a calibration reference — worse, a symmetric matchup returns ~50%
whether or not the simulator is faithful, so the very symmetry that makes the answer
knowable also strips the test of power to detect infidelity.

The corrected rule: **a known-value control must fix the whole causal chain (build, flags,
policy, seat schedule), not just one visible attribute of it.** Matching the decks and
calling it symmetry is the same error as matching the archetype and calling it the deck
(A.4) — an aggregate mistaken for the causal unit, this time committed by us against our
own instrument, one day after we wrote the rule against it.

(The self-mirror row does still earn its place for one narrow purpose: the live exact-mirror
record is v11+v12 **0/3**, and P(0 wins in 3 | p=0.533) = **0.102** — noise, not a finding.
A colleague model argued from the same data that the mirror must be *pilotable*, since
identical lists cannot create a one-sided **deck** disadvantage. That is logically sound but
establishes only *where* a gap would originate, never *that* one exists. At n=3, it does not.)

## A.9 The gate that was wrong: a post-mortem on the tracker-hook bar

A.1 #4 records the verdict; this is the mechanism. The +3.0pp ship gate failed three ways
at once, and each is the A.4 unit error applied to our own gating:

1. **Resolution mismatch.** The reading was **+1.37 ± 2.3pp over six seeds** on the
   pre-CRN instrument, whose own A/A noise floor was ±5–7pp/row (A.3 #1). The bar
   demanded an effect the instrument could not resolve at the n we could afford — the
   verdict was noise-shaped regardless of the hooks' true value.
2. **Unit mismatch.** One bundle-level bar judged five heterogeneous hooks jointly. T1
   (Judge-EV) was wrong by design — it ignored Judge's cost to our own hand — while
   T2–T5 went on to ship as defaults; the bundle reading mixed the known-bad hook with
   the four that shipped. The decision-relevant unit was the hook, not the bundle.
3. **Class mismatch.** A causal-win-rate bar was applied to infrastructure whose value
   case was non-regression plus enabling downstream consumers (body §4: "the
   infrastructure ships, the claim doesn't"). A gate certifies only the claim it was
   designed for.

Disposition, unchanged since: T2–T5 ship as non-regressing defaults with the below-gate
reading disclosed (body §2, principle 3); T1 stays off. The rule we keep: a gate needs a
pre-registered effect-size floor matched to its instrument's demonstrated resolution —
otherwise "missed the gate" is a statement about the gate.

## A.10 The prospective test we pre-registered — including the attempt that died

The rating model of §6.3 is fitted, so every number in it is in-sample. We wanted one
**forward** check on it, with its rule fixed before the outcomes it would judge, and we
recorded both attempts honestly — including, below, why passing it proves much less than
the word "validated" suggests.

**Attempt 1 (VOID, operational).** A five-read nightly series was pre-registered on
2026-07-17: five 01:52 UTC leaderboard reads, each checked against a band centred on the
fitted MLE settle (850) with half-width 60·√(gap/2) points, widening with the forecast
horizon. Only the centre comes from the current fit; the 60-point coefficient is an
**inherited two-day-drift calibration**, and it is one drift-SD — not a 95% interval —
and the raw longitudinal series behind that coefficient is not reproducible from this
repository. The verdict rule was fixed in advance: **VALIDATED at ≥4/5 in-band,
FALSIFIED at ≥2/5 outside**. Four of the five reads were
never taken: the campaign had assumed a nightly automation that **had never been
instantiated** — no scheduled task, no cron entry for it, only a manually-invoked script. Under
the series' own cadence rule a late fetch reads a different night's state, so the reads
were unrecoverable. Verdict: **VOID — neither validated nor falsified.** The lesson is
the same null-ratchet class as A.9, one level up: *a scheduled process does not exist
until you have listed the scheduler entry and seen the first artifact it produced.*

**Attempt 2 (passed its rule — and here is why that is weak evidence).** The series was
re-registered on 2026-07-21 — same estimator, same rule, same script, plus a
capture-tolerance clause (±30 min) written *before* any read landed — and this time the
scheduler entry was registered and test-fired first. Per this repository's local Git
history the bands, rule, and tolerance were committed 21 hours before read #1 and never
edited afterwards (later commits to that file only append the read ledger); the commits
are unsigned, so that ordering is local evidence, not a third-party timestamp. Attempt 2
was prospective but **not blind**: an off-cadence reading of 907.5 was already known and
supplied the series' as-of timestamp. Reads and outcomes:

| read | UTC | band | team score | verdict |
|---|---|---|---|---|
| 1 | 07-22 01:52 | [810.0, 890.0] | — | MISSED-operational (host crash) |
| 2 | 07-23 01:52 | [791.7, 908.3] | 884.3 | in-band |
| 3 | 07-24 01:52 | [777.9, 922.1] | 866.9 | in-band |
| 4 | 07-25 01:52 | [766.3, 933.7] | 918.8 | in-band |
| 5 | 07-26 01:52 | [756.2, 943.8] | 904.7 | in-band |

**Four scheduled reads were captured and all four fell in-band; one was missed
operationally. That passes the pre-registered ≥4/5 rule — the protocol's label for which
is "VALIDATED" — but it is not statistical validation, and we will not present it as
one.** Four things bound what it bought:

1. **The check cannot locate the centre.** A score frozen at the already-known **907.5
   would itself pass 4/5**; so would any constant in [791.7, 908.3]. Re-centring the same
   captured widths, **every centre from 835 to 939 fits all four observations** — our
   850-centred fit is indistinguishable here from one centred near 900, and a materially
   wider model passes too.
2. **The tightest band is the one we lost.** Read #1's ±40-point window was the series'
   real falsification risk, and nights 4 and 5 (918.8, 904.7) would both have missed it.
   The crash cost us the sharpest test, not a convenient one. The crash night's own
   continuity read (891.0 at 05:55Z, off-cadence, counting for nothing under the ±30-min
   rule) also sat outside [810.0, 890.0]. Even so, a captured miss there would have left
   4/5 standing, because falsification required two.
3. **The surviving bands are wide relative to the movement they had to catch.** The three
   observed night-to-night moves were −17.4, +51.9, −14.1 (mean absolute 27.8); the
   half-widths that judged them were 58.3 to 93.8 — roughly two to three times the
   typical move. Read #4 came within 14.9 points of failing; the rest had room.
4. **The reads are correlated, not independent** — sequential snapshots of one
   slowly-wandering process, a caveat the pre-registration itself carried. A naive
   iid reading of "4/5" overstates what four nights buy.

So the honest statement is narrow: **on four correlated nights the ladder never moved far
enough to break a one-drift-SD band, which is weak evidence against gross
mis-specification and no evidence about the centre.** The estimate of record stays the
MLE with its interval (body §6.3, §6.4). We kept the section because the discipline — rule
first, outcomes second, both attempts published — is the point; the result it produced is
mostly a lesson in how easy it is to pass a test you wrote yourself.

Artifacts: `intel/anchor_settle_prereg_2026-07-17.md` (attempt 1),
`intel/anchor_settle_replacement_2026-07-21.md` (the VOID verdict, the re-registration,
and the §5b read ledger), `scripts/anchor_settle.py` (the band formula, unchanged since
the 07-17 commit).

**Errata in those artifacts, corrected here rather than rewritten there** (a
pre-registration you edit after the fact is worth nothing, so the originals stand and the
corrections are additive): (a) the 07-17 header calls that day's snapshot "read #1 of 5"
while its own locked table correctly begins 07-18 — the header is wrong, the table
governs; (b) the replacement doc states that persistence near 907.5 would produce two
band misses and *falsify* the estimator — that is arithmetically wrong, as §1 above shows
it would pass 4/5, and the error made our disclosed foreknowledge sound more adverse than
it was; (c) the replacement's printed regeneration command omits `--asof`, so re-running
it verbatim picks up a later CSV row and reproduces three bands shifted by ±0.1 (no
verdict changes).
