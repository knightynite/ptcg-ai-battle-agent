# Appendix B — Agent-generation and gate ledger

*Attachment to the Strategy Writeup: the full release chronology summarized in the
body's §3.5 ("Later iteration") — the per-generation gate results, the CRN-recovered
patch verdicts, and the withdrawn v11 attribution in full.
Appendix A is the negatives ledger (`appendix_negatives.md`); sections B.1–B.3 below
extend its A.2, A.3, and A.5 threads. References to `intel/…`, `scripts/…`, and `agent/…` paths are internal campaign
artifacts, cited by name for audit-trail honesty; the released code repository
accompanying this writeup ships the agent, scripts, and report sources, and the key
cited artifacts are summarized here and in Appendix A.*

## B.1 Patch chronology, v7–v12 (extends Appendix A.2)

v7 (Budew behavior-diff #2): **+5.8pp meta-weighted but +0.61pp live-band**, missing the
+3.0pp gate — shipped meta leg only; its local 66.8% → live 65.5% is the one
reconciliation checkpoint that held (body §6.3). v8 (matchup hooks): +1.75pp live-band, short of +3pp but shipped clean. v9 (bench-floor +
energy-denial): read −0.29pp on the old noisy instrument, **HELD, unshipped**. Once CRN
existed (§6.2 of the body), two rejected patches (B2F, B3) were **falsely convicted** (true
effect ≈0, one real gain p=0.019) and shipped in v10; two others (ED, O1) were **confirmed
genuinely harmful** (p=0.013, p=0.0035), stay off.

## B.2 v10/v11 attribution history (extends Appendix A.3)

v10 reached 71.75% against a 72.0% bar — the closest miss yet on the pre-rebase instrument.
v11 rebuilt the *opponent pool* with full-agent tuned mirrors and found v10's number carried
~11pp of phantom equity — a **rebased-pool estimate of 60.82%**, not a "true baseline." A
mirror deck-out fix measured +4.04pp on the six mirror-family rows (p=0.00018; pool-wide
weighted effect +0.58pp, p=2e-4 — the number in the table below) and shipped. **We later
withdrew the claim that it caused v11's live jump** — a per-list re-audit showed its entire
local gain sat in the one mirror row that fails reconciliation against live, while the two
rows that match live measure it at ~0 (§7 of the body, Appendix A.2). v11 is our best observed
leaderboard draw, not a proven best policy; near-clone v12 landed ~127 points lower on the
live ladder, a direct sign of ladder-path variance rather than an L2-cost estimate.

## B.3 The Lucario post-mortem (extends Appendix A.5)

v12 implements five patches from an independent Codex/GPT-5 root-cause of 34 live
Crustle-vs-Lucario losses (Kangaskhan's Fighting weakness feeds Boss gust locks, not attacks
into the wall — Crustle blocked 95/95 direct Lucario attacks). Generic-pilot rows can't
measure a strong-pilot gust-sequencing fix, so v12 shipped as the honest live test rather than
a fabricated verdict (§7 of the body, Appendix A.5). Lucario is 0.4% of the field and 0% of
the top slice in the campaign's stopping-rule analysis (Appendix A.5); the patch was not
pursued further once that was established.

## Full generation-by-generation table

| Gen | Config | Local result | Verdict |
|---|---|---|---|
| v7 | Budew diff #2 (meta leg) | +5.8pp meta; +0.61pp band (missed +3.0 gate) | shipped, meta leg only |
| v8 | live-band matchup hooks | +1.75pp band | shipped, no regression |
| v9 | floor + energy-denial | −0.29pp (noisy) → +0.11pp CRN | HELD, unshipped |
| v10 | CRN-recovered patches (B2F, B3) | +0.13pp CRN vs v9 (71.62→71.75; 72.0 bar missed by 0.25) | shipped, closest miss |
| v11 | pool re-audit + mirror fix | rebased-pool estimate 60.82% (not "71.75"); +0.58pp (p=2e-4) | shipped — best observed draw; gain later unattributed |
| v12 | Codex-derived Lucario patches | +0.29pp (p=0.20, n.s.) | shipped as live test, then stopped — matchup 0.4% of field |

Sources: `intel/agent_v8_results.md`, `intel/agent_v9_results.md`, `intel/agent_v10_results.md`,
`intel/agent_v11_results.md`, `intel/agent_v12_results.md`, `intel/crn_reaudit_2026-07-13.md`,
`intel/mirror_alakazam_instrument_2026-07-15.md`, `intel/chassis_bias_2026-07-15.md`,
`intel/codex-lucario-research-2026-07-14.md`, `intel/lever_redirect_2026-07-15.md`.

## B.4 Frozen shipped configuration, baseline head-to-heads, fallback activity, and provenance

**B.4.1 Frozen shipped configuration (v11/v12).** Both builds bake an explicit env-flag
ledger into `main.py` and install `agent/deck_crustle.csv` as `deck.csv`
(`submit/build_submission_v11.sh`, `submit/build_submission_v12.sh`; v12 pins 46 flags).
Scoring keeps the inherited kiyotah/ichigoe priority bands (30000 ability / 20000
play-Pokémon), bugs fixed (`intel/agent_v0_results.md`).

| flag / constant | code default | v11 | v12 | role |
|---|---|---|---|---|
| `PTCG_SEARCH` (`agent/pilot.py:36`) | 0 | 0 | 0 | turn-plan search off (−2.5pp R2; tuning 46.0 vs 44.6, CIs overlap) |
| `SEARCH_RESERVE_SEC` / `PER_DECISION_BUDGET` / `SEARCH_K` (`pilot.py:55–57`) | 480 s / 2.5 s / 10 | = | = | clock reserve; search deadline; determinizations per crux |
| playbook (P0–P5, P7, T2–T5, R1, R3, DK, B1–B6, B2F, L1, D1, ST1) | 1 (`scoring.py` `_flag`) | 1 | 1 | shipped heuristic playbook |
| measured-negative (P6, P6B, P8, T1, T5N, R2, R4, S1, O1, ED, SBL) | 0 | 0 | 0 | stay off |
| `PTCG_BF`, `PTCG_MIR` | 0 | 1 | 1 | bench floor; mirror deck-life/closure |
| `PTCG_L2` + `_KANG/_WALL/_FLOOR/_BOSS` (`_CLOCK`) | 0 | — (pre-L2 code) | 1 (CLOCK 0) | Lucario patches; CLOCK off, measured regression |
| `PTCG_EXACT_DET` (`search.py`), `SUPPLY_RULE`, `DISCIPLINE_RULE` | 1 in today's tree (written 2026-07-16, after both tarballs) | **absent** | **absent** | tree-only; never fielded — see note |

*Note on the last row, corrected 2026-07-26.* It previously read "pinned 0 / unpinned → 1",
i.e. that the fielded v12 ran tracker-exact own-zone determinization and two mechanism
rules by default. **It did not.** Both tarballs were built 2026-07-13; those flags were
written 2026-07-16 and appear **zero times** in either submitted artifact (verified against
`submission_v11.tar.gz` and `submission_v12.tar.gz`). `build_submission_v11.sh` does pin
them to 0, but that pin postdates the shipped v11 artifact and has never been built. The
practical warning is the useful part: **a rebuild from HEAD would enable them by default
and would not be the agent that was fielded** — which is exactly why the baseline
experiment below used md5-verified tarball modules rather than the current tree.

**B.4.2 Final agent vs the provided baseline, deck held constant (measured 2026-07-26).**
The one comparison §6.1's ladder rows cannot support — a controlled contrast against the
organizer's provided sample agent — was run directly. Both arms pilot the identical
60-card `deck_crustle` list on the same 25-row live-band pool, the same three seeds, the
same engine binary (post-#1324, `e40e365b`), CRN-paired, n=300 per row; arm A's modules
are md5-identical to the shipped `submission_v12.tar.gz` and its 46-flag ledger was
mechanically diffed against the tarball's baked header (46/46 identical). The shipped
configuration wins by a live-band-weighted **+38.36pp (95% CI [+36.63, +40.10] for this fixed 25-row
pool at these weights — between-row spread is far larger, τ ≈ 25pp, so the interval bounds
sampling error, not pool composition or anything about the ladder; 71.9% vs 28.5%
unweighted mean of rows)**, all 25 rows favouring it, 0 crashes / 0 illegal / 0 timeouts
across 15,000 games. The pooled McNemar (3442/188) returns p < 1e-300, which we quote only
to note that it is a useless number — it tests a null nobody holds; **the load-bearing
statistic is that all 25 rows point the same way** (sign test p = 6e-8).

Three things bound that number. **The baseline is a random-legal-move agent**, so +38pp
sizes the distance from the provided starting point, not competitive strength — against
*tuned* opponents the same shipped agent reads 30.0% (`mirror_wall`), 19.7%
(`starmie_blitz`), 53.0% (`self_mirror`). **Roughly a fifth of the pool's weight sits on
rows this appendix already records as not reconciling to live** (A.3 #3/#4, plus a
cap-adjudicated row); dropping every flagged row moves the headline only to **+35.64pp**,
which is why we report it rather than quietly keeping them in. And **the CRN pairing
bought almost nothing here** (realized variance reduction 1.0–1.3×, against 8–147× on
near-clone gates) — correct but nearly inert when the arms are this dissimilar.

One-component ablations on the same instrument (Δ = ablated − full final, n=300/row,
52,500 further games) locate the value bluntly, against an **A/A null control that read
−0.04pp with 13/20 discordants** in the same batch:

Δ is *ablated minus full*, so a negative number is what removing that piece costs.

| ablated | Δpp | b / c | p |
|---|---:|---|---:|
| deck-hook family (`PTCG_DK`) | **−21.84** | 386 / 2340 | <1e-300 |
| Budew playbook (B1/B2/B4/B5/B6) | **−3.45** | 699 / 1083 | 8.4e-20 |
| tracker hooks (T2–T5) | −0.59 | 262 / 280 | 0.465 |
| mirror deck-clock (`PTCG_MIR`) | −0.30 | 98 / 133 | 0.025* |
| bench floor (`PTCG_BF`) | −0.08 | 32 / 36 | 0.716 |
| Lucario group (`PTCG_L2`) | **+0.03** | 147 / 154 | 0.730 |

\*fails Bonferroni correction (α=0.0083 across six tests).

Two results here are unflattering and we state them as results. **Removing the entire v12
Lucario group reads +0.03pp — so the group's own contribution is −0.03pp, indistinguishable
from zero**, though with a 95% CI of roughly ±0.9pp "changes nothing" is a bound, not a
proof of exact zero. On the row it was built for the two eras agree in direction and
disagree in size: re-oriented so both mean *with-L2 minus without-L2*, the v12 gate read
**+2.00pp (6 discordant games, p=0.418)** and this ablation reads **+0.67pp (2 discordant
games, p=0.87)**. Null then, null now; the effect did not reverse, it shrank toward
nothing.

We spell the orientation out because we got it wrong first. `crn_pool.py` prints its b/c
columns in opposite senses in those two tables, and an earlier draft of this very section
subtracted them unconverted and reported "the sign flipped" — manufacturing a reversal
that does not exist, in a report whose subject is exactly that error. It was caught by an
independent recomputation, not by us. **The four toggles below are also not equally
"null."** Only the Lucario group is a *measured* zero (301 discordant games, ~9× the noise
floor, excluding any effect above ~1pp). And **`PTCG_BF` is not measured as negative, it is
unmeasurable here**: it fires in only 68 discordant games against a 33-game floor, silent
on 17 of 25 rows — nothing is known about its effect where it does fire.

**B.4.2a The two unresolved toggles, re-run at 4× power (2026-07-26).** Rather than leave
them "not established at this n", we re-ran both against the full configuration at
n=1,200/row — 30,000 games per arm, same pool, weights, seeds, engine and orientation
(Δ = ablated − full, so negative means removing it costs):

| toggle | n=300/row (first run) | n=1,200/row | verdict |
|---|---|---|---|
| tracker hooks T2–T5 | −0.59pp, p=0.465, could not exclude −1.35pp | **−0.50pp, 95% CI [−0.94, −0.05]** | resolved: worth ~0.5pp; **harm now excluded** |
| `PTCG_MIR` | −0.30pp, p=0.025 (failed Bonferroni) | **−0.38pp, 95% CI [−0.55, −0.20], p=3.7e-08** | resolved: real, small, survives any correction |
| *A/A null control* | *−0.04pp, 33 discordants* | *+0.09pp, 95% CI [−0.01, +0.19]* | *the yardstick: two identical configs, still zero at 4× power* |

The null is what licenses the other two rows. It re-ran at the same n against a
byte-identical configuration and stayed indistinguishable from zero, and the engagement
counts separate signal from noise plainly: **141 discordant games for the null against 915
for `MIR` and 2,026 for the tracker hooks.** Identical builds replay almost identically
under paired randomness; these toggles genuinely change play.

Both hold across all three seeds independently (tracker −0.26/−0.36/−0.86; MIR
−0.57/−0.13/−0.42), so neither is one seed's luck. Two honest riders. The tracker-hook
interval is *nominal* — z≈2.2 — and would not survive Bonferroni across the two toggles
tested; what it does buy is the exclusion of harm, which the earlier bound could not. And
the MIR result, though overwhelming pool-wide, is **carried entirely by one row**:
`mirror_tusk_ee52c8d3` at −13.00pp (p=3.5e-15), with **no other row in the pool moving as
much as a point**. That is the same structure that made us withdraw the P-MIR attribution
in the first place (A.2) — the whole effect lives in the row that fails live reconciliation
by ~35pp, and the rows that *do* reconcile read zero. Four times the power did not change
the structure; it only measured it precisely. The patch is real and worth about half a
point locally. It is still not evidence for the live claim we retracted.

A note on what this run did *not* do: the tracker hooks originally missed their +3.0pp ship
gate (reading +1.37 ± 2.3pp) and shipped anyway as a disclosed non-regressing default
(A.1 #4, A.9). This measurement says that call was right — but it says so four generations
and 60,000 games later, which is not a vindication of the decision as made. Full protocol,
per-row tables, and build proofs: `intel/frozen_final_baseline_2026-07-26.md`.

**B.4.2b Earlier head-to-heads (superseded in scope by B.4.2).** Local gauntlet rows vs
the public reference agents — not ladder measurements. v12 vs v11, CRN-paired (3 seeds × 100/row):
kiyotah_lucario 46.3→48.3% (+2.00pp, b=16/c=22, p=0.418),
kojimar_baseline 27.3→26.0% (−1.33pp, p=0.618); flags-off v12 replays byte-identical to
v11, 30/30 transcript hashes (`intel/agent_v12_results.md`). v10→v11 paired (n=300):
kiyotah 46.7→46.7 (0.00, b=0/c=0) (`intel/agent_v11_results.md`). Pre-CRN v0 era (n=60):
our pilot on kiyotah's own Mega Lucario deck won 21.7% vs kiyotah's pilot —
statistically the same as our Starmie's 21.3%; vs generalist romanrozen ~61%
(`intel/agent_v0_results.md`).

**B.4.3 Fallback-ladder activity.** Per-tier activation counts for the crash ladder
(smart policy → first-N-legal → raw index) were not instrumented. What is measured
bounds it: **0 crashes / 0 illegal actions / 0 timeouts across 700,000+ local games and
642/642 live games** (body §3.1); the harnesses count agent exceptions directly (0 in
the 15,000-game v12 band), so the exception tiers had nothing to catch. The nearest thing
to an instrumented fallback counter is oracle-internal rather than the action ladder —
`EXACT_DET_DIAG`, ~5–7% fail-open in bring-up
(`intel/exact_det_patch_2026-07-16.md`) — and it is **tree-only: it appears in neither
submitted tarball and never ran in a fielded build** (same 2026-07-16 addition as the last
row of B.4.1). So for the shipped agent the honest statement is that per-tier fallback
activity was not instrumented at all.

**B.4.4 Provenance matrix.** Cells phrased to the body's own attributions.

| component | source | borrowed | ours | measured |
|---|---|---|---|---|
| exact-oracle determinization | documented Kiyotah recipe | determinization search | exact-resolve integration + failure boundary | §3.2/§3.3 |
| behavior-diff instrument | public episode dumps (WinDecks #7, Budew #2) | top agents' played decisions | counterfactual replay decomposition + gate discipline | §3.4 |
| CRN shuffle interposition | PokeForge described the idea | native-shuffle interposition concept | RDRAND/libstdc++ implementation, audit, four changed verdicts; dev-only | §6.2 |
| deck list | Budew's #2-ranked Crustle / Mega Kangaskhan ex list | 60-card list, unmodified (card-id multiset identical to the observed list) | the re-decision; the one change measured against *this* list — the −4 Spiky / +4 Basic Grass manabase A/B — was rejected at −8.00pp (p=0.0032). The 11-Basic mulligan fix (−5.5pp) was measured on the *previous* Starmie list, before the switch | §5 / A.7 |
| Lucario patches | independent Codex/GPT-5 root-cause | five-patch spec | CRN gating → best subset; +0.29pp n.s.; 0.4% of field, stopped | B.3 |
| rating backend + unit audit | our *fit* of the organizer's published rating system | the Evaluation page's qualitative spec | the fitted constants: settle model T = 1075 + 324·log₁₀(p/(1−p)) over 20,192 submission-sides; and five aggregate-vs-unit readings reversed or dissolved | §6.3/§6 |

*(The body credits Masamikobayashi's public approach for the tracker's own-zone/prize
inference, §4(b); the behavior-diff method itself is in-house.)*
