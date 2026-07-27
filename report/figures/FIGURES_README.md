# Strategy Writeup — figure gallery (rebuilt 2026-07-21)

Publication-quality figures for the Kaggle Strategy-track Writeup of the **Pokémon TCG
AI Battle Challenge**. These attachments carry the report's detailed evidence; the body
carries the argument.

**How they are made.** Every figure is regenerated from committed data + inlined
verbatim results by `reproducibility.py` (jupytext
"percent" format, the single source of truth). `build_notebook.py`
emits and executes `reproducibility.ipynb` top-to-bottom —
the notebook **prints every number each figure encodes** (busyaprime pattern) and
re-saves every PNG.

- Regenerate PNGs: `python reproducibility.py` — run from wherever the file sits; the
  script auto-discovers the repo layout and falls back to inlined data, so from the flat
  attachment download it regenerates every figure (F7 uses the inlined snapshot subset).
- Rebuild + execute the notebook (released code repository only): `python report/build_notebook.py`

**Conventions.**
- Each figure ships in **light and dark** variants (`*_light.png` / `*_dark.png`), colours
  from the `dataviz` reference palette (categorical hues validated for CVD + contrast in
  both modes). Pick the variant matching the gallery/theme.
- **No Pokémon card artwork or scans** anywhere — text/schematic only (license rule:
  artwork = disqualification).
- Numbers trace to `intel/` results docs, `report/numbers.json`, and the committed LB
  history CSVs — internal campaign artifacts, cited for audit-trail honesty. The released
  code repository ships the report sources and `numbers.json`; every number a figure
  encodes is also printed inline by the notebook, so the figures audit without them.

## Current gallery (2026-07-21 rebuild — executes the judge review's verdicts)

| ID | File(s) | Headline it carries (standalone) | Report section |
|----|---------|----------------------------------|----------------|
| **F1** | `F1_architecture_*` | One exact core, gated layers across twelve generations (v1–v12); safety 0/0/0 over 700k+ local + 642/642 live; p99 ≤ 13.5 ms, think ≤ 3.6 s of 600 s. | §3.1 |
| **F3** | `F3_classification_*` | Belief ~66% (T1–2) → ~90% by T3; tracker 99.981% / 100% / 100% on 57,589 replayed decisions. | §4 |
| **F4** | `F4_deck_roles_*` | The shipped deck by role — ONE Crustle list, two agent generations (v11+v12) on the ladder. | §5.4 |
| **F5** | `F5_*` | Deck consistency for the CURRENT Crustle list (mirrors the Starmie-era method; `intel/deck_consistency_crustle_2026-07-21.md`). | §5.3 |
| **F6** | `F6_unit_audit_*` | **CENTERPIECE.** Five aggregates that would have driven the wrong decision → re-keyed → decision changed; era-separated results strip with NO cross-era line. | §6 |
| **F7** | `F7_rating_trajectory_*` | Committed team-score series (07-11 through the latest committed read) vs the bars, with the v11 MLE band [794,906] — the score is a draw wandering around true skill. Pre-settle preview. | §6.4 |
| **F10** | `F10_behavior_diff_*` | The behavior diff applied twice: WinDecks (+21.4 local meta) and Budew (+5.8 meta / +0.61 band → gate MISSED, meta leg only). | §3.4 |
| **F11** | `F11_rating_model_*` | Fitted rating backend (K=9.0, s=324); honest checkpoint record (v7 held, v10 below projection, v11 MLE 850) — conditions comparisons, certifies nothing. | §6.3 |
| **F12** | `F12_crn_measurement_*` | The CRN fix: 6.0pp phantom → 0.0pp exact null; VRF 2.2–67× on the 2026-07-13 gates; the 2026-07-26 near-clone gates read 8–147× (B.4.2) and the body quotes the typical band, 16–44× — same statistic, different batches, reported here together so the three numbers reconcile. Four verdicts changed with McNemar p-values. Development-only. | §6.2 |

## Deleted from the gallery (judge review verdicts — do NOT re-add)

- **F2 latency histogram** — the distribution shape was a lognormal *reconstruction*
  pinned to two measured percentiles, not observed data. Latency is one body sentence now.
- **BONUS meta-positioning + BONUS matchup heatmap** — archetype (`opp_class`)
  aggregates: the exact wrong-unit mistake §6 documents.
- **Old F6 ablation ladder** — chained deltas across incomparable instrument eras;
  replaced by the unit-audit centerpiece + the era strip (no cross-era line).
- **Old F5 Starmie consistency** — sized the deck we no longer ship (replaced by the
  current-Crustle F5).
- **F8/F9 stubs** — awaiting-data placeholders earn no space in a judged attachment.
  Builders retained behind `RENDER_POST_SETTLE_STUBS = False`; F8 will key by exact
  deck list (not `opp_class`) when settled data lands post-settle (~Aug 31).

## Post-settle additions (planned; final data only)

- F7: final trajectory + placement.
- F8/F9: flip `RENDER_POST_SETTLE_STUBS`, populate from settled per-episode logs,
  re-verify the no-card-artwork rule on any new asset.
