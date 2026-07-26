# FLAGS — the exact v12 submitted configuration

The code in `agent/` reads its feature flags from the environment at import time
(`scoring.py _flag()`, `pilot.py`, `search.py`). The tree's code defaults are the
v11-era defaults; the submitted v12 build bakes the full 46-flag ledger below into
`main.py` via `os.environ.setdefault(...)` (source of truth:
`submit/build_submission_v12.sh`), so an explicitly set env var still wins for local
ablations.

**Deck note:** the submitted build installs `agent/deck_crustle.csv` as `deck.csv`
(the crustle-wall list). The `deck.csv` committed in `agent/` is the earlier default
list, not the shipped one.

## v12 baked ledger (46 flags)

| flag | code default | v12 shipped | meaning |
|---|---|---|---|
| PTCG_SEARCH | 0 | 0 | turn-plan search master switch; ships OFF (the exact one-turn attack oracle remains active regardless) |
| PTCG_BELIEF | 1 | 1 | belief-informed opponent determinization (consumed only when search runs) |
| PTCG_OPP_ROLLOUT | 1 | 1 | opponent-turn rollout inside search (consumed only when search runs) |
| PTCG_P0 | 1 | 1 | hygiene: opponent-stadium no-op veto + discard inversion |
| PTCG_P1 | 1 | 1 | Wally's Compassion un-veto (gated heal) |
| PTCG_P2 | 1 | 1 | snipe targeting rewrite + oracle/live target consistency |
| PTCG_P3 | 1 | 1 | supporter timing: Carmine gate / Judge timing / Hilda / Lillie |
| PTCG_P4 | 1 | 1 | Ignition/Nebula plan |
| PTCG_P5 | 1 | 1 | Duskull -> Dusclops -> Dusknoir engine (gated) |
| PTCG_P6 | 0 | 0 | tempo: bench cap + decline bench (A/B: negative) |
| PTCG_P6B | 0 | 0 | hold development items when developed (A/B: no gain) |
| PTCG_P7 | 1 | 1 | Duskull pivot retreat |
| PTCG_P8 | 0 | 0 | seat-conditional play (A/B: hurt the Crustle pillar) |
| PTCG_T1 | 0 | 0 | Judge timing via judge_ev (measured -9pp on the ryota row) |
| PTCG_T2 | 1 | 1 | Lillie draw-EV from exact remaining-deck composition |
| PTCG_T3 | 1 | 1 | KO-over-chip when the opponent is KNOWN to hold switch/heal/scoop |
| PTCG_T4 | 1 | 1 | prize-aware energy scarcity (are our key energies prized?) |
| PTCG_T5 | 1 | 1 | stall-guard: no self-KO gifts / big draws on a deck clock |
| PTCG_T5N | 0 | 0 | v5 narrowing of T5 (re-measured negative) |
| PTCG_R1 | 1 | 1 | race-state evaluator: AHEAD / EVEN / BEHIND(+margin) |
| PTCG_R2 | 0 | 0 | behind-race policy consuming R1 (gated off, negative) |
| PTCG_R3 | 1 | 1 | tank-race math: turns-to-KO tie-break + Nebula plan |
| PTCG_R4 | 0 | 0 | mirror/attacker-line snipe denial (gated off) |
| PTCG_DK | 1 | 1 | deck-hook family: crustle_wall deck profile hooks (auto-profile fallback when 0) |
| PTCG_B1 | 1 | 1 | deck-life economy + stall-lock END band (library = HP) |
| PTCG_B2 | 1 | 1 | gust-lock: Boss's Orders strands a can't-attack body + don't-break-the-lock |
| PTCG_B3 | 1 | 1 | Kang bench cap / hand economy (spare Kangs stay in hand) |
| PTCG_B4 | 1 | 1 | promote-sac order (wall > Kang > Shaymin > Dwebble last) + Switch held |
| PTCG_B5 | 1 | 1 | energy role-map + Hero's Cape to the tank + Mist-first fetches |
| PTCG_B6 | 1 | 1 | supporter engine: Xerosic priority, Lillie 6-prize window, Hilda refetch |
| PTCG_B2F | 1 | 1 | v7.1 lock-threat fix: self-KO-rider disqualifies zero-threat; never veto an oracle-verified OHKO |
| PTCG_L1 | 1 | 1 | lucario/fighting-threat plan: Kang quarantine, Boss line-snipe, wall {G} payability |
| PTCG_S1 | 0 | 0 | second-seat wall rush (A/B: negative on its own target rows) |
| PTCG_D1 | 1 | 1 | Battle-Cage-aware bench-menace read + Cage stadium economy |
| PTCG_ST1 | 1 | 1 | starmie canned-list counter: deny the engine; Caped, fueled Kang tank |
| PTCG_O1 | 0 | 0 | stall-tail standoff branch (A/B: bellibolt -9.5pp) |
| PTCG_BF | 0 | **1** | bench floor: L1 Kang quarantine yields to survival under KO pressure (rev3) |
| PTCG_ED | 0 | 0 | energy-denial (hammer) resilience (measured net negative; ships toggleable) |
| PTCG_MIR | 0 | **1** | mirror deck-life + prize-race closure vs an observed crustle-family board |
| PTCG_SBL | 0 | 0 | starmie-blitz defense: denial yields to development (gated off) |
| PTCG_L2 | 0 | **1** | v12 Lucario-matchup master switch (all consumers gated `L2 and subflag`) |
| PTCG_L2_KANG | 0 | **1** | L2 #1: hard one-Kang prize-exposure budget |
| PTCG_L2_WALL | 0 | **1** | L2 #2: active-specific wall state + Kang evacuation |
| PTCG_L2_FLOOR | 0 | **1** | L2 #3: predictive non-Kang board floor |
| PTCG_L2_BOSS | 0 | **1** | L2 #4: Lucario-specific Boss target ordering |
| PTCG_L2_CLOCK | 0 | 0 | L2 #5: wall/deck clock replacing zero-threat — CRN-measured regression, ships OFF |

Bold = shipped value differs from the code default in this tree.

## Flags in THIS TREE but NOT in the shipped build

**Corrected 2026-07-26.** An earlier version of this table listed these as "shipped value =
the code default", implying the fielded agent runs them. It does not: both submission
tarballs were built 2026-07-13, these flags were written 2026-07-16, and they appear **zero
times** in either artifact. They exist only in the current source tree.

| flag | default in this tree | in the shipped tarballs | meaning |
|---|---|---|---|
| PTCG_EXACT_DET | 1 | **not present** | tracker-exact own-zone determinization in `search.py` |
| PTCG_SUPPLY_RULE | 1 | **not present** | prize-multiset resource-supply consumer (fail-open on the tracker) |
| PTCG_DISCIPLINE_RULE | 1 | **not present** | narrow top-pilot discipline rule (fail-open; crustle_wall-gated) |
| PTCG_SUPPLY_DEBUG | 0 | **not present** | episode-end supply-rule debug dump |
| PTCG_DISCIPLINE_DEBUG | 0 | **not present** | episode-end discipline-rule debug dump |

Consequence worth stating plainly: **a rebuild from this tree is not the agent that was
fielded**, because these default ON. Reproducing the submitted behaviour means building
from the tarball ledger above, not from HEAD.

## Search reserve constants (not env flags)

`agent/pilot.py` hard-codes the search clock budget. These are constants, not flags, and
they differ in scope — an earlier version of this file wrongly said both "only matter when
`PTCG_SEARCH=1`", which contradicts line 18 above and the code:

- `SEARCH_RESERVE_SEC = 480.0` — applies **regardless of `PTCG_SEARCH`**. It gates
  `allow_search`, which controls the exact one-turn attack oracle; `PTCG_SEARCH` gates only
  the multi-turn plan search one line below it. Measured headroom is ~57× in an impossible
  worst case and ~10⁴× at observed game lengths, so it has never fired (see the negatives
  ledger, A.3 #6).
- `PER_DECISION_BUDGET = 2.5` — hard per-decision search deadline (well under Kaggle's
  7.5 s); this one does only bind when the plan search is enabled.
