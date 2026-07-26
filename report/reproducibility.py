# %% [markdown]
# # Reproducibility notebook — Strategy Writeup figures (2026-07-21 gallery rebuild)
#
# **Pokémon TCG AI Battle Challenge — Strategy track.** Agent lineage: exact-engine
# oracle (R1/v1) → **behavior-diff playbook (v3, +21.4 pp local meta)** → hidden-state
# tracker (v4) → race evaluator (v5) → **deck re-decision (v6 Budew Crustle)** →
# behavior-diff #2 (v7 Budew) → **CRN paired-world gates (v8–v10)** → pool re-audit +
# mirror fix (v11) → Codex L2 lucario patches (v12). Search layers (R2/R3) built,
# A/B-tested, shipped **gated off** after two clean negatives.
#
# This notebook regenerates **every figure** in the Writeup's media gallery from
# committed data + inlined verbatim results. It follows the *busyaprime* discipline:
# **every number a figure encodes is printed by a cell first**, so the charts are
# auditable, not decorative.
#
# Gallery (rebuilt 2026-07-21 per the adversarial judge review,
# `intel/codex_report_review_2026-07-15.md`):
# * **F1** architecture (v1–v12 layer stack, safety ledger)
# * **F3** belief classification + tracker precision (unchanged — still accurate)
# * **F4** current Crustle role table (single deck — the portfolio is generations now)
# * **F5** deck consistency — CURRENT Crustle list (mirrors the Starmie-era method)
# * **F6** THE UNIT AUDIT (centerpiece): wrong aggregate → right unit → changed
#   decision, ×5; era-separated results strip with **no cross-era connecting line**
# * **F7** live rating trajectory (committed snapshot series, pre-settle preview)
# * **F10** behavior-diff decomposition ×2 (WinDecks/Starmie + Budew/Crustle)
# * **F11** fitted rating backend (measured fits + honest checkpoints only)
# * **F12** the CRN measurement fix (null, VRF spectrum, four changed verdicts)
#
# **Dropped from the gallery** (judge review, do not re-add): F2 synthetic-latency
# histogram (shape was reconstructed, not observed); both BONUS archetype-aggregate
# charts (the exact wrong-unit mistake §6 documents); F8/F9 awaiting-data stubs
# (post-settle builders retained behind RENDER_POST_SETTLE_STUBS).
#
# Sources (all committed): `intel/agent_v3..v12_results.md`, `windecks_behavior_diff.md`,
# `budew_behavior_diff.md`, `measurement_harness_2026-07-13.md`, `crn_reaudit_2026-07-13.md`,
# `rating_system_model.md`, `deck_rebakeoff_2026-07-12.md`, `nightly_2026-07-13/14/15.md`,
# `deck_consistency_starmie.md`, `deck_consistency_crustle_2026-07-21.md`,
# `lb_history/{cutoffs_history,our_rating_history}.csv`, `agent/deck_crustle.csv`,
# `report/numbers.json`.
#
# Design system: the `dataviz` skill's validated reference palette (categorical hues
# pass the CVD/contrast validator in light **and** dark; ordering is the CVD-safety
# mechanism). Each figure is rendered on a **light and a dark** surface. **No Pokémon
# card artwork/scans** anywhere — text/schematic only (license rule).

# %%
# --- Setup: imports, palette, theming, IO ------------------------------------
import os
import sys
import math
import textwrap
import datetime as dt
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.colors import LinearSegmentedColormap

# Use a non-interactive backend when running as a plain script; keep the inline
# backend when running inside a Jupyter kernel (so previews embed in the notebook).
try:
    get_ipython()  # noqa: F821
    _IN_NOTEBOOK = True
except NameError:
    _IN_NOTEBOOK = False
    matplotlib.use("Agg")

print("matplotlib", matplotlib.__version__, "| numpy", np.__version__,
      "| notebook-kernel:", _IN_NOTEBOOK)


def find_repo_root():
    """Walk up from CWD to locate the repo (folder holding intel/meta_current_2026-07-10.csv)."""
    here = os.path.abspath(os.getcwd())
    anchor = os.path.join("intel", "meta_current_2026-07-10.csv")
    for _ in range(8):
        if os.path.exists(os.path.join(here, anchor)):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    # Kaggle / detached fallbacks
    for cand in ("/kaggle/input", os.getcwd()):
        if os.path.exists(os.path.join(cand, anchor)):
            return cand
    return os.getcwd()


REPO = find_repo_root()
INTEL = os.path.join(REPO, "intel")
FIGDIR = os.path.join(REPO, "report", "figures")
os.makedirs(FIGDIR, exist_ok=True)
print("repo root :", REPO)
print("intel dir :", INTEL, "(exists:", os.path.isdir(INTEL), ")")
print("fig out   :", FIGDIR)

# ---- dataviz reference palette (validated light + dark) ----------------------
PAL = {
    "light": dict(
        surface="#fcfcfb", page="#f9f9f7", ink="#0b0b0b", ink2="#52514e", muted="#898781",
        grid="#e1e0d9", axis="#c3c2b7", border=(0, 0, 0, 0.10),
        s1="#2a78d6", s2="#1baf7a", s3="#eda100", s4="#008300", s5="#4a3aa7",
        s6="#e34948", s7="#e87ba4", s8="#eb6834",
        good="#0ca30c", warn="#fab219", serious="#ec835a", critical="#d03b3b",
        div_lo="#2a78d6", div_mid="#f0efec", div_hi="#e34948",
    ),
    "dark": dict(
        surface="#1a1a19", page="#0d0d0d", ink="#ffffff", ink2="#c3c2b7", muted="#898781",
        grid="#2c2c2a", axis="#383835", border=(1, 1, 1, 0.10),
        s1="#3987e5", s2="#199e70", s3="#c98500", s4="#008300", s5="#9085e9",
        s6="#e66767", s7="#d55181", s8="#d95926",
        good="#0ca30c", warn="#fab219", serious="#ec835a", critical="#d03b3b",
        div_lo="#3987e5", div_mid="#383835", div_hi="#e66767",
    ),
}
MODES = ("light", "dark")


def theme(mode):
    """Apply rcParams for the given surface; return the palette dict."""
    p = PAL[mode]
    matplotlib.rcParams.update({
        "figure.facecolor": p["surface"], "axes.facecolor": p["surface"],
        "savefig.facecolor": p["surface"], "savefig.edgecolor": p["surface"],
        "text.color": p["ink"], "axes.labelcolor": p["ink2"], "axes.edgecolor": p["axis"],
        "xtick.color": p["muted"], "ytick.color": p["muted"],
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.titlesize": 14, "axes.titleweight": "bold",
        "axes.grid": False, "axes.spines.top": False, "axes.spines.right": False,
        "figure.dpi": 120,
    })
    return p


def diverging_cmap(mode):
    p = PAL[mode]
    return LinearSegmentedColormap.from_list("winrate", [p["div_hi"], p["div_mid"], p["div_lo"]])


def footnote(fig, text, mode):
    fig.text(0.008, 0.008, text, ha="left", va="bottom", fontsize=7.4,
             color=PAL[mode]["muted"])


def render(builder, name):
    """Build the figure in light + dark, save both PNGs; return the light fig for inline preview."""
    light_fig = None
    for mode in MODES:
        fig = builder(mode)
        out = os.path.join(FIGDIR, f"{name}_{mode}.png")
        fig.savefig(out, dpi=200, bbox_inches="tight",
                    facecolor=PAL[mode]["surface"])
        print(f"  saved {os.path.relpath(out, REPO)}")
        if mode == "light":
            light_fig = fig
        else:
            plt.close(fig)
    return light_fig


# %% [markdown]
# ## Data load — all figure inputs, printed (busyaprime pattern)
#
# Small numeric inputs are inlined verbatim from the committed intel `.md` results so
# the notebook is self-contained on Kaggle; CSVs (meta, matchups, cutoffs, rating
# history, decklists) are read from the repo when present, with inline fallbacks.
# Every value below is echoed before any figure uses it.

# %%
# ---- F6: THE UNIT AUDIT (report §6 table) + era-separated results strip ---------
# Five readings mistook an aggregate for the causal unit; each produced a false
# narrative until re-keyed to the unit the decision actually depends on.
UNIT_AUDIT = [  # (wrong unit, what the aggregate said, right unit, what it says, changed decision)
    ("Independent\nbatches",
     "v8 vs v8 (same build)\nread +6.0pp apart",
     "same stochastic world\n(CRN-paired arms)",
     "0.0pp — exact null\n(300/300 identical games)",
     "every later gate runs CRN"),
    ("Generic-pilot\nopponent pool",
     "v10 local read 71.75%",
     "pilot x deck pool,\nlive-reconciled",
     "60.82% re-based\n(~11pp phantom equity)",
     "eras never compared again"),
    ("Archetype key\n(opp_class), then\ndeck_key alone",
     "\"our own deck beats us\";\nthen a \"healthy 53% mirror\"",
     "BOTH sides keyed by the\nexact 60-card list",
     "true exact-list\nhistory: 2/7",
     "mirror fix re-targeted\nat the real list"),
    ("Raw matchup\nwin rate",
     "Alakazam 46.4%\n= \"a leak\"",
     "rating-conditioned\nexpectation",
     "13 obs vs 14.14\nexpected — par-consistent",
     "no patch (none needed)"),
    ("Nightly aggregate\nsides",
     "Crustle 47.0 -> 45.7 -> 45.0\n-> 42.3: pivot trigger FIRED",
     "same (team x deck) panel,\nteam-clustered",
     "45.2 -> 45.8, p=0.868\n(96.1% from 3 teams)",
     "deck HELD; the trigger\nitself was retired"),
]
print("UNIT AUDIT (F6): wrong unit -> right unit -> changed decision")
for wu, agg, ru, rd, dec in UNIT_AUDIT:
    print(f"  {wu.replace(chr(10),' '):42s} | {agg.replace(chr(10),' '):48s} -> "
          f"{rd.replace(chr(10),' '):38s} | {dec.replace(chr(10),' ')}")

# Era strip: results grouped by measurement instrument. LEVELS ARE NOT COMPARABLE
# ACROSS ERAS (the instrument changed) — the strip draws NO cross-era connecting line.
ERAS = [  # (era title, subtitle, rows: (label, value text))
    ("Era 1 · pre-CRN meta gauntlet", "unseeded RNG; same-batch multi-seed deltas only",
     [("R1 exact oracle", "43.8%  (anchor)"),
      ("R2/R3 search layers", "-2.5 / -2.1pp -> gated OFF"),
      ("v3 behavior-diff playbook", "65.1%  (+21.4pp, 3/3 seeds)"),
      ("v6 deck -> Crustle", "68.0% meta / 57.9% band  (+3.2 / +7.0)")]),
    ("Era 2 · CRN paired worlds", "identical shuffles/coins/prizes per arm; exact per-row stats",
     [("v7 behavior-diff #2 (Budew)", "+5.8pp meta; +0.61pp band — meta leg only"),
      ("v8/v9 patch gates", "four verdicts changed by CRN (see F12)"),
      ("v10 = v9 + recovered patches", "+0.13pp paired (71.62 -> 71.75, old pool)")]),
    ("Era 3 · re-based honest pool", "generic-pilot rows replaced; ~11pp phantom removed",
     [("v10 true baseline", "60.82%"),
      ("v11 + mirror deck-clock fix", "61.40%  (+0.58pp, 3/3 seed-pairs, p=2e-4)"),
      ("v12 + Codex L2 lucario", "band +0.29pp (under +2 bar); 2 sig row wins")]),
]
print("\nERA STRIP (F6 bottom): levels not comparable across eras — no connecting line")
for ttl, sub, rows in ERAS:
    print(f"  {ttl} — {sub}")
    for lab, val in rows:
        print(f"     {lab:34s} {val}")

# ---- F12: the CRN measurement fix (measurement_harness + crn_reaudit 07-13) ----
CRN_NULL = dict(unpaired=6.0, paired=0.0, n_pairs=300)   # v8-vs-v8 same-build null
CRN_VRF = [  # (gate row, realized VRF, regime note)
    ("B2F mutual-KO lock fix", 67.1, "near-clone"),
    ("ED energy-denial nudge", 51.8, "near-clone"),
    ("S1 Dwebble wall rush", 22.7, "near-clone"),
    ("B3 Kang bench cap", 17.3, "near-clone"),
    ("v10 assembly gate", 15.0, "near-clone"),
    ("O1 standoff branch", 2.2, "DISSIMILAR-POLICY regime"),
]
CRN_VERDICTS = [  # (patch, paired delta pp, McNemar p, verdict, disposition)
    ("B2F mutual-KO\nlock fix", -0.05, 0.47, "falsely convicted", "recovered -> IN v10"),
    ("B3 Kang\nbench cap", +0.17, 0.71, "falsely convicted", "recovered -> IN v10"),
    ("ED energy-denial\nnudge", -0.37, 0.013, "genuinely harmful", "confirmed OFF"),
    ("O1 standoff\nbranch", -1.43, 0.0035, "genuinely harmful", "confirmed OFF (moot)"),
]
print("\nCRN (F12): unpaired v8-vs-v8 null read "
      f"{CRN_NULL['unpaired']}pp; CRN-paired {CRN_NULL['paired']}pp "
      f"({CRN_NULL['n_pairs']}/{CRN_NULL['n_pairs']} identical games)")
for lab, v, reg in CRN_VRF:
    print(f"  VRF {lab:26s} {v:6.1f}x  ({reg})")
for lab, d, pv, verd, disp in CRN_VERDICTS:
    print(f"  verdict {lab.replace(chr(10),' '):26s} {d:+.2f}pp  p={pv:<7g} {verd:18s} {disp}")

# ---- F10: WinDecks behavior diff (windecks_behavior_diff.md + v3 results §5) --
WD_TOT = dict(decisions=26378, nontrivial=24664, raw=56.6, substantive=49.4,
              after_v3_raw=51.4, after_v3_sub=41.5)
WD_CATS = [  # (category, n, substantive disagreement %)
    ("SETUP bench", 192, 100), ("RETREAT", 56, 100), ("END turn", 707, 99),
    ("DISCARD", 707, 82), ("TO_BENCH", 659, 77), ("ATTACH", 2992, 72),
    ("ABILITY", 600, 68), ("ATTACK", 2594, 63), ("EVOLVE", 2075, 57),
    ("PLAY", 5459, 52), ("counter place", 553, 37), ("snipe target", 1624, 33),
    ("TO_HAND", 5318, 22),
]
WD_PAIRS = [  # (behavior, WD count, our counterfactual count, note)
    ("Cursed Blast (Dusknoir line)", 574, 0, "ability counters pierce attack-shields"),
    ("Wally's Compassion heal", 341, 0, "median heal 180, p75 240"),
    ("END holding playables", 707, 51, "resource conservation"),
    ("Hilda (setup supporter)", 842, 437, "guarantees the T3-4 Mega"),
    ("Carmine (discard hand)", 137, 737, "we over-burn curated hands"),
]
WD_SNIPE = [("Abra", 373), ("Kadabra", 139), ("Dwebble", 127), ("Impidimp", 124)]
WD_SNIPE_OURS = "ours: 50-chips into 210-320 HP tanks (Fezandipiti ex / M-Kangaskhan / Grimmsnarl)"
print("\nWD BEHAVIOR DIFF: 651 episodes,", WD_TOT["decisions"], "decisions,",
      WD_TOT["nontrivial"], "non-trivial; substantive disagreement",
      f"{WD_TOT['substantive']}% -> {WD_TOT['after_v3_sub']}% after v3 (-7.9pp)")
for c, n, r in WD_CATS:
    print(f"  {c:14s} n={n:5d}  substantive {r:3d}%")
for b, w, o, note in WD_PAIRS:
    print(f"  {b:30s} WD {w:4d} vs ours {o:4d}  ({note})")
print("  WD top snipe targets:", ", ".join(f"{k} x{v}" for k, v in WD_SNIPE),
      "|", WD_SNIPE_OURS)

# ---- F10 panel 2: Budew behavior diff (budew_behavior_diff.md + agent_v7_results) --
BU_TOT = dict(decisions=63038, nontrivial=59508, raw=59.1, substantive=44.3)
BU_CATS = [  # (category, n, substantive disagreement %)
    ("END turn", 5666, 99.9), ("DISCARD", 1456, 94), ("RETREAT", 52, 83),
    ("ATTACK", 4804, 75), ("ATTACH", 8763, 57), ("EVOLVE", 1930, 41),
    ("PLAY", 17744, 39), ("SWITCH/ACTIVE", 3320, 34), ("TO_HAND", 7532, 22),
    ("ABILITY", 4558, 1.6),
]
BU_FIVE = [  # (difference family, headline evidence)
    ("Deck-life economy", "5,666 ENDs at 99.9% disagreement; Run Errand SKIPPED 1,466x at median deck 16"),
    ("The gust-lock", "692 ENDs holding a legal attack (621 vs an ex) — strand it, mill it"),
    ("Wall maintenance", "active occupancy swings Kang-tank early -> Crustle-wall 52% of T9+ turns"),
    ("Energy role-map", "5,032 ATTACH flips (57%) — Mist-first fetch, active-loading discipline"),
    ("Supporter engine", "Xerosic over Hilda from Pokegear; they pitch dupes, protect Jumbo/Switch/Boss"),
]
BU_OUT = dict(meta=+5.8, band=+0.61, gate=+3.0)
print("\nBUDEW BEHAVIOR DIFF: 1,251 episodes,", BU_TOT["decisions"], "decisions,",
      BU_TOT["nontrivial"], "non-trivial; substantive disagreement",
      f"{BU_TOT['substantive']}% (WD/Starmie was {WD_TOT['substantive']}%)")
for c, n, r in BU_CATS:
    print(f"  {c:14s} n={n:6,d}  substantive {r:5.1f}%")
for fam, ev in BU_FIVE:
    print(f"  {fam:20s} {ev}")
print(f"  outcome: {BU_OUT['meta']:+.1f}pp meta-weighted BUT {BU_OUT['band']:+.2f}pp "
      f"live-band -> MISSED the {BU_OUT['gate']:+.1f}pp gate; shipped meta leg only (v7)")

# ---- F11: fitted rating backend (rating_system_model.md) ----------------------
RS = dict(K=9.0, K_iqr=(8.86, 9.23), s=324.0, anchor=1075.0, sides=19569,
          var_p5p95=240.0, seat=0.077, mu0=600.0)
RS_CAL = [(+118, 0.695, 0.698), (-184, 0.209, 0.213)]  # (rating diff, observed WR, model WR)
OUR_PLACE = dict(v3_band_p=0.530, v3_band_anchor=750.0, v3_obs=(752.4, 761.3),
                 v6_meta_p=0.680, v5_conservative_p=0.60)


def settle(p, anchor):
    return anchor + RS["s"] * math.log10(p / (1 - p))


print("\nRATING BACKEND: dmu = K*(S-E), K =", RS["K"], "IQR", RS["K_iqr"],
      "| E = logistic, scale s =", RS["s"], f"(fit on {RS['sides']:,} sides)")
for d, obs, mod in RS_CAL:
    print(f"  calibration bin: diff {d:+d} -> observed {obs:.3f} vs model {mod:.3f}")
print(f"  settle law: T = {RS['anchor']:.0f} + {RS['s']:.0f}*log10(p/(1-p))  "
      f"(anchor = visible 1050+ farm pool; shifts 1:1 with pool)")
print(f"  v3 placed with ITS OWN pool anchor ~{OUR_PLACE['v3_band_anchor']:.0f} "
      f"(median live opp 715-787): p={OUR_PLACE['v3_band_p']} -> "
      f"{settle(OUR_PLACE['v3_band_p'], OUR_PLACE['v3_band_anchor']):.0f}  "
      f"vs observed {OUR_PLACE['v3_obs']}")
print("  checkpoint record: v7 local 66.8% -> live 65.5% HELD; v10 settled 30-50 pts "
      "below projection; v11 settle MLE 850 [794,906] (n=101) — condition, don't certify")
print(f"  identical-agent 36-day spread: p5-p95 ~ {RS['var_p5p95']:.0f} "
      f"(community reports 150-400); first seat ~ +{RS['seat']} win-prob")

# ---- F3: classification by turn (agent_R3_results.md) + tracker (agent_v4) ----
CLS = [  # (bucket_label, x, acc_lo, acc_hi, conf_lo, conf_hi)
    ("1-2", 1.5, 59, 72, 71, 75),
    ("3-4", 3.5, 86, 91, 83, 84),
    ("5-6", 5.5, 87, 90, 90, 91),
    ("7-8", 7.5, 88, 90, 92, 93),
    ("9+",  9.5, 88, 91, 92, 93),
]
CLS_PILLARS = dict(alakazam=100.0, crustle=95.0)
TRACKER = [  # (headline, sub1, sub2)
    ("99.981%", "zone reconciliation", "57,589 replayed decisions · 11 divergences, all rebased gracefully"),
    ("100%", "own-prize identity", "2,208/2,208 checks · exact multiset by turn ~2.1 (792/800 streams)"),
    ("100%", "opp-hand-known precision", "6,517/6,517 checks — every claimed known was really there"),
]
print("\nCLASSIFICATION accuracy by turn bucket (acc% range, conf range):")
for lab, x, alo, ahi, clo, chi in CLS:
    print(f"  turns {lab:>3}: acc {alo}-{ahi}%  conf {clo/100:.2f}-{chi/100:.2f}")
print("  pillars once revealed: Alakazam ~100% (1558/1558), Crustle ~95%")
print("TRACKER precision (400 public episodes replayed):")
for h, s1_, s2_ in TRACKER:
    print(f"  {h:8s} {s1_:26s} {s2_}")

# ---- F5: deck consistency — CURRENT Crustle list (deck_consistency_crustle_2026-07-21) --
# Method byte-mirrors the Starmie-era doc (exact hypergeometric + MC, seed 20260721,
# 1M trials/arm); the script re-derives the old doc's four exact rows as validation.
CR_CONS = dict(
    mull_starmie=45.9, mull_fix=22.2, fix_meta_delta=-5.5, mull_crustle=30.0,
    basics=dict(starmie=6, fix=11, crustle=9),
    openers=[  # (label, %)
        (">=1 energy in opening 7", 83.7),
        ("Crustle line in first 8", 44.5),
        ("Dwebble in opening 7", 39.9),
        ("Mega Kangaskhan ex in 7", 39.9),
        ("Shaymin in opening 7", 11.7),
    ],
    # setup curve, MC baseline: (going 2nd, going 1st) %
    setup=[("wall\nby T2", 70.1, 65.5), ("wall\nby T3", 76.4, 75.6),
           ("attacker\nby T3", 62.7, 57.5), ("attacker\nby T4", 76.5, 76.1)],
    runerrand_note="Run Errand variant: wall T2 78.3/75.0, attacker T3 72.2/67.6 — the strict mirror understates the live deck by ~8-10pp",
)
print("\nDECK CONSISTENCY (current Crustle list, method mirrors deck_consistency_starmie):")
print(f"  mulligan: Starmie shipped {CR_CONS['mull_starmie']}% (6 Basics) | Starmie fix "
      f"{CR_CONS['mull_fix']}% (11 Basics) -> {CR_CONS['fix_meta_delta']}pp REJECTED | "
      f"Crustle current {CR_CONS['mull_crustle']}% (9 Basics)")
for lab, v in CR_CONS["openers"]:
    print(f"  opener {lab:28s} {v:5.1f}%")
for lab, s2_, s1_ in CR_CONS["setup"]:
    print(f"  setup  {lab.replace(chr(10),' '):28s} {s2_:5.1f}% going-2nd / {s1_:5.1f}% going-1st")
print("  " + CR_CONS["runerrand_note"])
print("  attack-by-T2 is structurally 0% (3-energy attackers) — stated openly")

# ---- F1: safety ledger (F2 latency figure DROPPED per judge review — the histogram
# shape was a lognormal reconstruction, not observed data; latency lives in one body
# sentence: measured p99 <= 13.5ms vs the 7.5s budget, live think <= 3.6s of 600s) ----
SAFETY = dict(local_games="700,000+", generations="twelve", live_games="642/642",
              p99_ms=13.5, think_max_s=3.6, think_budget_s=600)
print("\nSAFETY: 0 crashes / 0 illegal / 0 timeouts over", SAFETY["local_games"],
      "local games (", SAFETY["generations"], "generations) and",
      SAFETY["live_games"], "live ladder games; p99 <=", SAFETY["p99_ms"],
      "ms; live think max", SAFETY["think_max_s"], "s of", SAFETY["think_budget_s"], "s")


# %%
# ---- CSV loads: meta (Jul-10 + Jul-11), matchups, cutoffs, rating history ------
def _read_csv_dicts(path):
    import csv
    if not os.path.exists(path):
        return None
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def load_meta(fname, fallback):
    rows = _read_csv_dicts(os.path.join(INTEL, fname))
    if rows is not None:
        out = [(r["archetype"], int(r["games"]), float(r["score_rate"]),
                float(r["wilson_low"]), float(r["wilson_high"]), float(r["usage_share"]))
               for r in rows]
        print(f"{fname}: read {len(out)} rows from committed CSV")
        return out
    print(f"{fname}: using inline fallback ({len(fallback)} rows)")
    return fallback


META10_FB = [("alakazam", 8081, .510333, .499431, .521225, .400645),
             ("crustle", 3797, .521728, .505825, .537587, .188250),
             ("grimmsnarl", 2659, .464648, .445756, .483643, .131829),
             ("cynthia_garchomp", 1310, .514504, .487436, .541487, .064948),
             ("starmie", 928, .531250, .499080, .563162, .046009),
             ("lucario", 613, .438825, .400043, .478370, .030392),
             ("archaludon", 553, .464738, .423554, .506408, .027417),
             ("dragapult", 449, .531180, .484952, .576879, .022261),
             ("rocket_spidops", 316, .547468, .492346, .601451, .015667),
             ("kangaskhan", 274, .459854, .401803, .519015, .013585)]
META11_FB = [("alakazam", 3713, .492055, .475991, .508136, .370337),
             ("crustle", 2483, .545711, .526071, .565210, .247656),
             ("grimmsnarl", 957, .443051, .411868, .474689, .095452),
             ("cynthia_garchomp", 653, .486983, .448834, .525284, .065131),
             ("dragapult", 560, .555357, .513961, .595999, .055855),
             ("rocket_spidops", 348, .580460, .528009, .631154, .034710),
             ("lucario", 342, .374269, .324643, .426689, .034111),
             ("other:Dangerous Laser|Bramblin", 322, .496894, .442642, .551220, .032116),
             ("starmie", 220, .486364, .421119, .552076, .021943),
             ("archaludon", 84, .392857, .295302, .499784, .008378)]
META10 = load_meta("meta_current_2026-07-10.csv", META10_FB)
META11 = load_meta("meta_current_2026-07-11.csv", META11_FB)


def load_meta_matchups():
    rows = _read_csv_dicts(os.path.join(INTEL, "meta_matchups_2026-07-10.csv"))
    if rows is not None:
        pairs = {(r["archetype_a"], r["archetype_b"]): float(r["a_score_rate"]) for r in rows}
        print("meta_matchups: read", len(pairs), "pairs from committed CSV")
        return pairs
    pairs = {("alakazam", "starmie"): .5238, ("crustle", "starmie"): .1856,
             ("grimmsnarl", "starmie"): .63, ("starmie", "lucario"): .4634,
             ("starmie", "archaludon"): .6111, ("starmie", "dragapult"): .525}
    print("meta_matchups: using inline fallback (", len(pairs), "pairs )")
    return pairs


META_MU = load_meta_matchups()

SHORT = {"alakazam": "Alakazam", "crustle": "Crustle", "grimmsnarl": "Grimmsnarl",
         "cynthia_garchomp": "Cynthia", "starmie": "Starmie", "lucario": "Lucario",
         "archaludon": "Archaludon", "dragapult": "Dragapult", "rocket_spidops": "Rocket",
         "kangaskhan": "Kangaskhan", "other:Dangerous Laser|Bramblin": "Bramblin"}

# Ladder cutoffs — latest committed snapshot
CUT_FB = dict(snapshot="2026-07-12T05:13", teams=4844, top10=1120.9, top25=1064.3,
              top50=1022.6, top100=984.0)
_cut = _read_csv_dicts(os.path.join(INTEL, "lb_history", "cutoffs_history.csv"))
if _cut:
    r = _cut[-1]
    CUTOFFS = dict(snapshot=r["snapshot_utc"][:16], teams=int(r["teams"]),
                   top10=float(r["top10"]), top25=float(r["top25"]),
                   top50=float(r["top50"]), top100=float(r["top100"]),
                   bronze=(float(r["bronze_score"]) if r.get("bronze_score") else None))
    print("cutoffs_history: latest committed snapshot used")
else:
    CUTOFFS = dict(CUT_FB, bronze=None)
    print("cutoffs_history: inline fallback")
print("  cutoffs @", CUTOFFS["snapshot"], "(", CUTOFFS["teams"], "teams): top-10",
      CUTOFFS["top10"], "top-50", CUTOFFS["top50"], "top-100", CUTOFFS["top100"],
      "bronze(top-10%)", CUTOFFS["bronze"])

# Our team rating history (best-of-2 active) + per-submission trajectory (autopsy §1)
OUR_HIST_FB = [("2026-07-11T17:49", 600.0), ("2026-07-12T01:25", 756.3),
               ("2026-07-12T05:13", 739.0)]
_oh = _read_csv_dicts(os.path.join(INTEL, "lb_history", "our_rating_history.csv"))
OUR_HIST = ([(r["snapshot_utc"][:16], float(r["score"])) for r in _oh]
            if _oh else OUR_HIST_FB)
SUB_MARKS = [  # (label, submit dt) — only sourced timestamps (submit/SUBMISSIONS.md)
    ("v3", "2026-07-11T20:22"),
    ("v6", "2026-07-12T03:17"),
    ("v11", "2026-07-14T01:50"),
    ("v12", "2026-07-14T03:40"),
]
V11_MLE = dict(mle=850, lo=794, hi=906, n=101)   # numbers.json v11_mle_settle
print("our_rating_history (team best-of-2):", len(OUR_HIST), "committed snapshots,",
      OUR_HIST[0], "->", OUR_HIST[-1])
for lab, t0 in SUB_MARKS:
    print(f"  submit mark {lab:4s} {t0}")
print(f"  v11 skill MLE {V11_MLE['mle']} [{V11_MLE['lo']},{V11_MLE['hi']}] (n={V11_MLE['n']})")

# Crustle decklist composition (agent/deck_crustle.csv; names curated from card_db)
CRUSTLE_IDS_FB = {1: 1, 11: 4, 14: 4, 18: 4, 343: 1, 344: 4, 345: 4, 756: 4,
                  1086: 4, 1087: 1, 1122: 4, 1123: 4, 1147: 4, 1159: 1, 1182: 2,
                  1197: 4, 1225: 4, 1227: 4, 1264: 2}
_dc = os.path.join(REPO, "agent", "deck_crustle.csv")
if os.path.exists(_dc):
    import collections
    with open(_dc, encoding="utf-8") as fh:
        _ids = [int(l.strip()) for l in fh if l.strip()]
    CRUSTLE_IDS = dict(collections.Counter(_ids))
    print(f"deck_crustle.csv: {sum(CRUSTLE_IDS.values())} cards, "
          f"{len(CRUSTLE_IDS)} distinct ids (committed file)")
else:
    CRUSTLE_IDS = CRUSTLE_IDS_FB
    print("deck_crustle.csv: inline fallback")
CARD_NAMES = {1: "Basic {G} Energy", 11: "Mist Energy", 14: "Spiky Energy",
              18: "Grow Grass Energy", 343: "Shaymin", 344: "Dwebble", 345: "Crustle",
              756: "Mega Kangaskhan ex", 1086: "Buddy-Buddy Poffin", 1087: "Hand Trimmer",
              1122: "Pokegear 3.0", 1123: "Switch", 1147: "Jumbo Ice Cream",
              1159: "Hero's Cape", 1182: "Boss's Orders", 1197: "Xerosic's Machinations",
              1225: "Hilda", 1227: "Lillie's Determination", 1264: "Battle Cage"}
assert sum(CRUSTLE_IDS.values()) == 60, "Crustle list must be 60 cards"
print("  Budew Crustle list (deck_key 656c2d64bc4711ef):",
      ", ".join(f"{CARD_NAMES.get(k, k)} x{v}" for k, v in sorted(CRUSTLE_IDS.items())))


# %% [markdown]
# ## F1 — Agent architecture / pipeline (v6 state)
#
# The layered pilot as shipped: exact-oracle core (v1) + behavior-diff playbook (v3) +
# hidden-state tracker (v4) + race evaluator (v5) + deck-general hooks (v6 portfolio).
# The two search layers stay **gated off** after two clean negatives. Schematic only.
# **Message:** additive, individually-gated layers over one ground-truth core, wrapped
# in a fallback ladder that has never crashed — locally or live.

# %%
def build_F1(mode):
    p = theme(mode)
    fig, ax = plt.subplots(figsize=(12.8, 8.8))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    def box(x, y, w, h, title, body, ec, tc, fs=10.0, wrapw=62, alpha=1.0,
            accent=None, ls="-"):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2.0",
                     fc=p["surface"], ec=ec, lw=1.6, alpha=alpha, zorder=2, ls=ls))
        if accent:
            ax.add_patch(Rectangle((x, y), 1.2, h, fc=accent, ec="none", zorder=3))
        ax.text(x + 2.2, y + h - 1.1, title, ha="left", va="top", fontsize=fs + 0.8,
                fontweight="bold", color=tc, zorder=4)
        if body:
            lines = []
            for para in body.split("\n"):
                lines += (textwrap.wrap(para, wrapw) or [""])
            yy = y + h - 1.1 - 4.1
            for ln in lines:
                ax.text(x + 2.2, yy, ln, ha="left", va="top", fontsize=fs - 1.5,
                        color=p["ink2"], zorder=4)
                yy -= 2.9

    def arrow(x1, y1, x2, y2, color, lw=1.8, ls="-", zorder=5):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                     mutation_scale=13, lw=lw, color=color, ls=ls, zorder=zorder,
                     shrinkA=1, shrinkB=1))

    ax.text(0, 99.6, "F1 · Agent architecture — one exact core, gated layers across twelve generations, zero crashes",
            ha="left", va="top", fontsize=14.5, fontweight="bold", color=p["ink"])

    # Crash-safe wrapper
    ax.add_patch(FancyBboxPatch((0.5, 2.5), 66.5, 92, boxstyle="round,pad=0.5,rounding_size=2.4",
                 fc="none", ec=p["muted"], lw=1.2, ls=(0, (5, 4)), zorder=0))
    ax.text(2.5, 93.2, "crash-safe wrapper · monotonic clock reserve · final legality gate",
            ha="left", va="top", fontsize=8.4, color=p["muted"], style="italic")

    # Layer stack (decision flows top -> bottom through the scoring layers)
    box(2, 84, 30, 5.2, "Decision request", "", p["axis"], p["ink2"], fs=9.6)
    L = [
        ("1 · Exact-oracle core   (R1 = v1)", p["s1"],
         "Every legal attack resolved via the organizer's search_begin/step sandbox — exact damage / KO / prizes."),
        ("2 · Behavior-diff playbook   (v3, +21.4 pp local meta)", p["s1"],
         "7 rule families mined from the #7 pilot's 651 episodes on our identical list; matchup-gated by belief."),
        ("3 · Hidden-state tracker   (v4, +1.37 ± 2.3 — kept)", p["s2"],
         "Exact own zones + opp-hand knowns (99.981% / 100% / 100% replay-verified); below gate, ships as default."),
        ("4 · Race evaluator + tank math   (v5, +0.11 — kept)", p["s2"],
         "AHEAD / EVEN / BEHIND prize-race read; turns-to-KO pacing picks tank windows."),
        ("5 · Deck-general profile + Crustle kit   (v6, +3.2 meta)", p["s1"],
         "Auto-derived roles for any list; wall / breaker modes, Xerosic timing. Deck -> Budew Crustle."),
        ("6 · Behavior-diff #2   (v7, Budew)", p["s2"],
         "+5.8 pp meta / +0.61 band -> meta leg only; the gate, not the diff, certifies (report §3.4)."),
        ("7 · CRN paired-world gates   (v8–v10)", p["s5"],
         "Paired random worlds for every A/B; four verdicts changed (F12). Development-only — never ships."),
        ("8 · Pool re-audit + mirror fix (v11) · L2 lucario (v12)", p["s1"],
         "~11 pp phantom pool equity removed; mirror deck-clock fix +0.58 pp (p=2e-4) on the honest pool."),
    ]
    hs = [7.0] * len(L)
    ys = [80.0 - 8.0 * (i + 1) + 1.0 for i in range(len(L))]  # 73, 65, ... 17
    arrow(33.5, 80.0, 33.5, ys[-1] - 0.6, p["muted"], lw=1.4, zorder=1)  # flow line, visible in the gaps
    for (ttl, col, body), y, h in zip(L, ys, hs):
        box(2, y, 63, h, ttl, body, col, p["ink"], fs=9.6, wrapw=104, accent=col)
    arrow(17, 84, 17, ys[0] + hs[0] + 0.4, p["muted"])

    # Fallback ladder strip
    box(2, 4.5, 63, 9.5, "Safety fallback ladder", "", p["axis"], p["ink2"], fs=9.6)
    ax.text(4.2, 8.4, "smart policy  ->  first-N-legal (exact minCount/maxCount)  ->  raw index"
            "   ·   circuit breaker + watchdog", ha="left", va="center", fontsize=9.0,
            color=p["ink2"])

    # Right column: gated-off search, output, safety badge
    box(70, 71, 29, 17, "Gated OFF — two clean negatives",
        "R2 turn-line search: -2.5pp.\nR3 reply rollout: -3.6pp\n(belief-search +1.4, not confident).\nPTCG_SEARCH unset -> pure pilot.",
        p["muted"], p["ink2"], fs=9.2, wrapw=44, ls=(0, (4, 3)))
    arrow(70, 76, 65.6, 73.5, p["muted"], lw=1.2, ls=(0, (4, 3)))

    box(70, 52, 29, 9, "Legal action", "returned to the engine on every decision",
        p["s4"], p["ink"], fs=9.8, wrapw=40)
    arrow(65, 23, 70, 55.5, p["s1"], lw=2.0)

    ax.add_patch(FancyBboxPatch((70, 14), 29, 30, boxstyle="round,pad=0.6,rounding_size=2.0",
                 fc=p["surface"], ec=p["good"], lw=1.9))
    ax.text(84.5, 37.5, "0 / 0 / 0", ha="center", va="center", fontsize=22,
            fontweight="bold", color=p["good"])
    ax.text(84.5, 27.5, "crashes / illegal / timeouts\n\n700,000+ local games (12 gens)\n"
            "642/642 live ladder games\np99 <= 13.5 ms per decision\nlive think <= 3.6 s of 600 s",
            ha="center", va="center", fontsize=9.0, color=p["ink2"], linespacing=1.4)

    footnote(fig, "F1 · schematic (no card artwork). Layer deltas = gated A/B results in their own era's instrument "
                  "(F6 era strip; levels not comparable across eras). Sources: agent_v3..v12_results.md, "
                  "deck_rebakeoff_2026-07-12.md, measurement_harness_2026-07-13.md.", mode)
    fig.tight_layout()
    return fig


print("F1 — architecture diagram")
_f1 = render(build_F1, "F1_architecture")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## F3 — Belief: archetype classifier + exact hidden-state tracker
#
# **Message (two panels):** (left) the archetype belief is prior-dominated (~60–72%)
# until a signature reveals, then jumps to **~90% by turn 3** and holds. (right) the v4
# tracker is *exact where it claims exactness* — replay-verified on 400 public episodes:
# 99.981% zone reconciliation, 100% own-prize identity (exact by ~turn 2), 100%
# opponent-hand-known precision.

# %%
def build_F3(mode):
    p = theme(mode)
    fig = plt.figure(figsize=(12.8, 6.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.45, 1], wspace=0.18)
    ax = fig.add_subplot(gs[0, 0])

    xs = [c[1] for c in CLS]
    acc_lo = np.array([c[2] for c in CLS]); acc_hi = np.array([c[3] for c in CLS])
    acc_mid = (acc_lo + acc_hi) / 2
    conf_mid = np.array([(c[4] + c[5]) / 2 for c in CLS])

    ax.fill_between(xs, acc_lo, acc_hi, color=p["s1"], alpha=0.16, zorder=1,
                    label="accuracy range (2 runs)")
    ax.plot(xs, acc_mid, "-o", color=p["s1"], lw=2.4, ms=8, zorder=3, label="classification accuracy")
    ax.plot(xs, conf_mid, "--s", color=p["s2"], lw=2.0, ms=6, zorder=3, label="mean posterior confidence")
    for x, y in zip(xs, acc_mid):
        ax.annotate(f"{y:.0f}%", (x, y), textcoords="offset points", xytext=(0, 11),
                    ha="center", fontsize=9.4, fontweight="bold", color=p["ink"])
    ax.axhline(CLS_PILLARS["alakazam"], color=p["muted"], lw=1.1, ls=":")
    ax.text(9.7, CLS_PILLARS["alakazam"] - 0.4, "Alakazam ~100% (1558/1558)", ha="right",
            va="top", fontsize=8.6, color=p["ink2"])
    ax.axhline(CLS_PILLARS["crustle"], color=p["muted"], lw=1.1, ls=":")
    ax.text(9.7, CLS_PILLARS["crustle"] - 0.4, "Crustle ~95%", ha="right", va="top",
            fontsize=8.6, color=p["ink2"])
    ax.axvspan(0.6, 2.6, color=p["s3"], alpha=0.07, zorder=0)
    ax.text(1.5, 55.5, "prior-dominated\n(turns 1-2)", ha="center", va="top",
            fontsize=8.6, color=p["muted"], style="italic")
    ax.text(6.5, 63.5, "signature revealed -> holds ~90%", ha="center", va="top",
            fontsize=8.6, color=p["muted"], style="italic")
    ax.set_xticks(xs); ax.set_xticklabels([c[0] for c in CLS])
    ax.set_xlabel("turn bucket"); ax.set_ylabel("percent")
    ax.set_ylim(50, 104); ax.set_xlim(0.6, 10.1)
    ax.grid(axis="y", color=p["grid"], lw=0.7); ax.set_axisbelow(True)
    ax.set_title("Archetype classifier: ~90% by turn 3", loc="left", color=p["ink"],
                 fontsize=12)
    ax.legend(loc="lower right", frameon=False, fontsize=9.0, labelcolor=p["ink2"])

    # right: tracker precision stat tiles
    axR = fig.add_subplot(gs[0, 1]); axR.axis("off")
    axR.set_xlim(0, 100); axR.set_ylim(0, 100)
    axR.set_title("Hidden-state tracker (v4): replay-verified", loc="left",
                  color=p["ink"], fontsize=12)
    for i, (h, sub, note) in enumerate(TRACKER):
        y0 = 69 - i * 33
        axR.add_patch(FancyBboxPatch((2, y0), 96, 28, boxstyle="round,pad=0.8,rounding_size=2.2",
                      fc=p["surface"], ec=p["axis"], lw=1.4))
        axR.add_patch(Rectangle((2, y0), 1.6, 28, fc=p["good"], ec="none"))
        axR.text(7, y0 + 21.5, h, fontsize=17, fontweight="bold", color=p["good"],
                 va="center")
        axR.text(7, y0 + 12.5, sub, fontsize=10.2, fontweight="bold", color=p["ink"],
                 va="center")
        for j, ln in enumerate(textwrap.wrap(note, 60)):
            axR.text(7, y0 + 6.5 - j * 4.2, ln, fontsize=8.3, color=p["ink2"], va="center")

    fig.suptitle("F3 · Belief state — probabilistic where it must be, exact where it can be",
                 x=0.01, ha="left", fontsize=14, fontweight="bold", color=p["ink"])
    footnote(fig, "F3 · left: belief config vs 8 archetype-labeled gauntlet opponents (agent_R3_results.md, Ablation D; "
                  "two runs, N=8 & N=20/opp; early misses default to the Alakazam prior — pillar accuracies, no confusion matrix). "
                  "right: 400 public episodes / 57,589 decisions replayed through the tracker (agent_v4_results.md §2).", mode)
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    return fig


print("F3 — classification + tracker precision")
_f3 = render(build_F3, "F3_classification")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## F4 — Current deck role table (Crustle / Mega Kangaskhan ex — single deck)
#
# **Message:** the shipped deck, by role. Both active submissions pilot this one 60-card
# Crustle list (the earlier Crustle+Starmie portfolio consolidated to two Crustle
# *generations*, v11+v12, through ordinary submission-order attrition — report §5.2).
# Picked by a current-pilot re-bakeoff (+3.2 meta / +7.0 band, 2nd-seat tax halved).
# Styled table-figure, no card art.

# %%
def _role_table(ax, p, title, rows, footer):
    ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.text(0, 99, title, ha="left", va="top", fontsize=12.6, fontweight="bold",
            color=p["ink"])
    x_role, x_cards, x_fn = 2, 20, 56
    ax.text(x_role, 88, "ROLE", fontsize=9, fontweight="bold", color=p["muted"])
    ax.text(x_cards, 88, "CARDS", fontsize=9, fontweight="bold", color=p["muted"])
    ax.text(x_fn, 88, "FUNCTION", fontsize=9, fontweight="bold", color=p["muted"])
    ax.plot([x_role, 99], [85, 85], color=p["axis"], lw=1.1)
    top = 83
    rh = (top - 10) / len(rows)
    for i, (role, cards, fn, c) in enumerate(rows):
        y = top - i * rh
        if i % 2 == 0:
            ax.add_patch(Rectangle((x_role - 1, y - rh + 0.8), 100 - x_role, rh - 0.4,
                                   fc=p["grid"], ec="none", alpha=0.5, zorder=0))
        ax.add_patch(Rectangle((x_role - 1, y - rh + 0.8), 0.9, rh - 0.4, fc=c, ec="none", zorder=1))
        ax.text(x_role + 1.3, y - rh / 2 + 0.6, role, fontsize=9.6, fontweight="bold",
                color=p["ink"], va="center")
        ax.text(x_cards, y - rh / 2 + 0.6, cards, fontsize=8.6, color=p["ink2"], va="center")
        ax.text(x_fn, y - rh / 2 + 0.6, fn, fontsize=8.3, color=p["ink2"], va="center")
    ax.plot([x_role, 99], [top - len(rows) * rh + 0.8, top - len(rows) * rh + 0.8],
            color=p["axis"], lw=1.1)
    ax.text(x_role, 3.5, footer, fontsize=8.4, color=p["muted"], va="center")


def build_F4(mode):
    p = theme(mode)
    fig, axT = plt.subplots(figsize=(13.0, 6.4))

    crustle_rows = [
        ("Wall", "Crustle x4  (150 HP)", "Mysterious Rock Inn: immune to ex/Mega attack damage; Scissors 120 pierces effects", p["s1"]),
        ("Main attacker", "Mega Kangaskhan ex x4  (300 HP)", "Rapid-Fire Combo CCC: 200 + 50/heads; Run Errand ability: draw 2 every turn", p["s2"]),
        ("Feeder", "Dwebble x4", "Ascension (0 cost): evolve straight from deck -> the wall lands by turn 2", p["s2"]),
        ("Bench shield", "Shaymin (Flower Curtain), Battle Cage x2", "blanks bench snipe + damage-counter placement", p["s5"]),
        ("Sustain", "Jumbo Ice Cream x4, Hero's Cape, Grow Grass x4", "heal 80 at >=3 energy; +100 / +20 HP on the wall", p["s3"]),
        ("Hand denial", "Xerosic's Machinations x4, Hand Trimmer, Boss's Orders x2", "strip big hands (Powerful-Hand denial); gust the win target", p["s6"]),
        ("Draw / mobility", "Hilda x4, Lillie x4, Pokegear x4, Poffin x4, Switch x4", "Switch serves the wall swap (wall in front of ex, breaker vs their wall)", p["s8"]),
    ]
    _role_table(axT, p, "Crustle / Mega Kangaskhan ex — wall + tank  ·  both active slots (v11 + v12 generations)",
                crustle_rows,
                "60 cards · deck_key 656c2d64bc4711ef (= #2 Budew's list) · engine-validated errorType=0 · "
                "13 energy (Mist blocks effects / Spiky punishes hits) · seat gap -9.8pp vs Starmie's -20.0pp · "
                "consistency sizing: F5 / intel/deck_consistency_crustle_2026-07-21.md")

    fig.suptitle("F4 · The shipped deck, by role — one 60-card Crustle list, two agent generations on the ladder",
                 x=0.01, ha="left", fontsize=14.5, fontweight="bold", color=p["ink"])
    footnote(fig, "F4 · Sources: deck_rebakeoff_2026-07-12.md §2-3 + agent/deck_crustle.csv + card_db_full.csv; "
                  "portfolio consolidation: submit/SUBMISSIONS.md (report §5.2). No card artwork (schematic role view).", mode)
    fig.tight_layout(rect=(0, 0.01, 1, 0.94))
    return fig


print("F4 — deck portfolio role tables")
_f4 = render(build_F4, "F4_deck_roles")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## F5 — Deck consistency, CURRENT Crustle list (sized, not asserted)
#
# **Message (three honest panels):** (left) the old list's named weakness — a 45.9%
# mulligan rate — was NOT fixed by resizing (the 11-Basic rebuild hit 22.2% but measured
# **−5.5 pp and was rejected**: consistency ≠ win rate, the A.7 pattern); the deck
# *switch* fixed it (current list: **30.0%**, 9 Basics). (middle) opener probabilities
# for the current list's key roles. (right) the setup curve: wall online by T2 in
# ~66–70% of games; the 3-energy attacker is structurally never online by T2 — stated
# openly, the wall exists to buy exactly that time.

# %%
def build_F5(mode):
    p = theme(mode)
    fig, (axL, axM, axR) = plt.subplots(1, 3, figsize=(14.0, 5.8),
                                        gridspec_kw={"width_ratios": [1, 1.08, 1.22]})

    # -- left: mulligan, three arms --
    labels = ["Starmie\nshipped\n6 Basics", "Starmie fix\n11 Basics\nREJECTED", "Crustle\ncurrent\n9 Basics"]
    vals = [CR_CONS["mull_starmie"], CR_CONS["mull_fix"], CR_CONS["mull_crustle"]]
    cols = [p["muted"], p["s6"], p["s1"]]
    bars = axL.bar(labels, vals, color=cols, width=0.62, edgecolor=p["surface"], linewidth=1.2)
    bars[1].set_hatch("///"); bars[1].set_alpha(0.8)
    for b, v in zip(bars, vals):
        axL.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.1f}%", ha="center",
                 fontsize=10.5, fontweight="bold", color=p["ink"])
    axL.annotate("22.2% mulligan\nBUT -5.5 pp meta\n-> consistency != win rate",
                 xy=(1, CR_CONS["mull_fix"]), xytext=(0.42, 38.5),
                 fontsize=8.2, color=p["s6"], ha="left", va="center", fontweight="bold",
                 arrowprops=dict(arrowstyle="-|>", color=p["s6"], lw=1.3))
    axL.annotate("the SWITCH fixed it:\n-15.9 pp mulligan", xy=(2, CR_CONS["mull_crustle"] + 4.0),
                 xytext=(1.42, 48.5), fontsize=8.2, color=p["s1"], ha="left",
                 va="center", fontweight="bold",
                 arrowprops=dict(arrowstyle="-|>", color=p["s1"], lw=1.3))
    axL.set_ylabel("mulligan rate (%)"); axL.set_ylim(0, 56)
    axL.grid(axis="y", color=p["grid"], lw=0.7); axL.set_axisbelow(True)
    axL.set_title("Mulligan: fixed by the deck switch,\nnot by the sizing fix that failed its gate",
                  loc="left", fontsize=11, color=p["ink"])

    # -- middle: opener probabilities (current list) --
    ol = CR_CONS["openers"]
    yo = np.arange(len(ol))[::-1]
    axM.barh(yo, [v for _, v in ol], height=0.6, color=p["s1"],
             edgecolor=p["surface"], linewidth=1.0)
    for y, (lab, v) in zip(yo, ol):
        axM.text(v + 1.5, y, f"{v:.1f}%", va="center", fontsize=9.2,
                 fontweight="bold", color=p["ink"])
    axM.set_yticks(yo); axM.set_yticklabels([lab for lab, _ in ol], fontsize=8.8)
    axM.set_xlim(0, 100); axM.set_xlabel("probability (%)")
    axM.grid(axis="x", color=p["grid"], lw=0.7); axM.set_axisbelow(True)
    axM.set_title("Current-list openers\n(exact hypergeometric)", loc="left",
                  fontsize=11, color=p["ink"])

    # -- right: setup curve (grouped bars, going 2nd / 1st) --
    groups = CR_CONS["setup"]
    x = np.arange(len(groups)); w = 0.36
    s2v = [g[1] for g in groups]; s1v = [g[2] for g in groups]
    b2 = axR.bar(x - w / 2, s2v, w, color=p["s2"], edgecolor=p["surface"],
                 linewidth=1.2, label="going 2nd")
    b1 = axR.bar(x + w / 2, s1v, w, color=p["s1"], edgecolor=p["surface"],
                 linewidth=1.2, label="going 1st")
    for bars_ in (b2, b1):
        for b in bars_:
            axR.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.2,
                     f"{b.get_height():.0f}", ha="center", fontsize=9.4,
                     fontweight="bold", color=p["ink"])
    axR.set_xticks(x); axR.set_xticklabels([g[0] for g in groups], fontsize=8.6)
    axR.set_ylabel("P(online) %  ·  MC 1M trials/arm"); axR.set_ylim(0, 100)
    axR.grid(axis="y", color=p["grid"], lw=0.7); axR.set_axisbelow(True)
    axR.legend(loc="upper left", frameon=False, fontsize=9.0, labelcolor=p["ink2"])
    axR.set_title("Setup curve: the wall buys the time\nthe 3-energy attacker needs",
                  loc="left", fontsize=11, color=p["ink"])
    axR.text(0.985, 0.975, "attack-by-T2 is structurally 0% (3-energy attackers);\n"
             "Run Errand variant adds ~8-10pp to these baselines",
             transform=axR.transAxes, ha="right", va="top", fontsize=7.8,
             color=p["muted"])

    fig.suptitle("F5 · Deck consistency — the CURRENT Crustle list, sized with the same instrument as the old one",
                 x=0.01, ha="left", fontsize=14, fontweight="bold", color=p["ink"])
    footnote(fig, "F5 · Source: deck_consistency_crustle_2026-07-21.md + scripts/deck_consistency_crustle.py (exact hypergeometric + "
                  "MC seed 20260721, 1M trials/arm; method byte-mirrors deck_consistency_starmie.md — its four exact rows re-derive "
                  "identically). Rejected-fix arm: final_tuning_2026-07-11.md (Test B).", mode)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    return fig


print("F5 — current-Crustle deck consistency")
_f5 = render(build_F5, "F5_deck_consistency")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## F6 — THE UNIT AUDIT (report centerpiece)
#
# **Message:** our most dangerous numbers were arithmetically correct but
# decision-wrong — the aggregate did not match the unit of intervention. Five times, a
# seductive aggregate reading would have driven a bad decision; re-keying the same data
# to the decision-relevant unit reversed or dissolved it. Bottom strip: the surviving
# results grouped by measurement-instrument era, with **no cross-era connecting line**
# (the instrument changed; absolute levels are not comparable across eras).

# %%
def build_F6(mode):
    p = theme(mode)
    fig = plt.figure(figsize=(13.6, 11.8))
    gs = fig.add_gridspec(2, 1, height_ratios=[2.55, 1.0], hspace=0.10)

    # ---------- top: the unit-audit table ----------
    ax = fig.add_subplot(gs[0, 0])
    ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 100)

    cA, cB, cC, cD, cE = 1, 16.5, 41.5, 62.5, 82.5   # column left edges
    ax.text(cA, 97.5, "WRONG UNIT", fontsize=8.5, fontweight="bold", color=p["muted"])
    ax.text(cB, 97.5, "THE AGGREGATE SAID", fontsize=8.5, fontweight="bold", color=p["critical"])
    ax.text(cC, 97.5, "RE-KEYED TO THE RIGHT UNIT", fontsize=8.5, fontweight="bold", color=p["muted"])
    ax.text(cD, 97.5, "IT ACTUALLY SAYS", fontsize=8.5, fontweight="bold", color=p["good"])
    ax.text(cE, 97.5, "DECISION CHANGED", fontsize=8.5, fontweight="bold", color=p["ink"])
    ax.plot([cA, 99.5], [95.2, 95.2], color=p["axis"], lw=1.1)

    top, bot = 94.0, 2.0
    rh = (top - bot) / len(UNIT_AUDIT)
    for i, (wu, agg, ru, rd, dec) in enumerate(UNIT_AUDIT):
        y1 = top - i * rh          # row top
        ym = y1 - rh / 2           # row centre
        if i % 2 == 0:
            ax.add_patch(Rectangle((cA - 0.6, y1 - rh + 0.35), 100.2 - cA, rh - 0.7,
                                   fc=p["grid"], ec="none", alpha=0.5, zorder=0))
        ax.text(cA, ym, wu, fontsize=9.2, fontweight="bold", color=p["ink"],
                va="center", linespacing=1.25)
        ax.text(cB, ym, agg, fontsize=8.8, color=p["critical"], va="center",
                linespacing=1.3)
        ax.annotate("", xy=(cC - 1.2, ym), xytext=(cC - 4.6, ym),
                    arrowprops=dict(arrowstyle="-|>", color=p["muted"], lw=1.5))
        ax.text(cC, ym, ru, fontsize=8.6, color=p["ink2"], va="center",
                style="italic", linespacing=1.3)
        ax.text(cD, ym, rd, fontsize=8.8, fontweight="bold", color=p["good"],
                va="center", linespacing=1.3)
        ax.add_patch(FancyBboxPatch((cE - 0.4, ym - 3.4), 17.6, 6.8,
                     boxstyle="round,pad=0.35,rounding_size=1.2",
                     fc=p["surface"], ec=p["s1"], lw=1.3, zorder=2))
        ax.text(cE + 8.4, ym, dec, fontsize=8.0, fontweight="bold", color=p["s1"],
                va="center", ha="center", linespacing=1.25, zorder=3)
    ax.plot([cA, 99.5], [bot + 0.3, bot + 0.3], color=p["axis"], lw=1.1)

    # ---------- bottom: era-separated results strip (NO cross-era line) ----------
    axE = fig.add_subplot(gs[1, 0])
    axE.axis("off"); axE.set_xlim(0, 100); axE.set_ylim(0, 100)
    axE.text(0, 99, "Results, by measurement instrument — levels are NOT comparable across eras "
             "(no line connects the boxes on purpose)", fontsize=10.5, fontweight="bold",
             color=p["ink"], va="top")

    ew, gap = 31.4, 2.9                      # era box width / inter-box gap
    for k, (ttl, sub, rows) in enumerate(ERAS):
        x0 = k * (ew + gap)
        axE.add_patch(FancyBboxPatch((x0 + 0.4, 4), ew, 84,
                      boxstyle="round,pad=0.7,rounding_size=1.8",
                      fc=p["surface"], ec=p["axis"], lw=1.5, zorder=1))
        axE.add_patch(Rectangle((x0 + 0.4, 4), 1.1, 84, fc=p["s1"], ec="none", zorder=2))
        axE.text(x0 + 2.6, 82.5, ttl, fontsize=9.6, fontweight="bold", color=p["ink"],
                 va="center", zorder=3)
        axE.text(x0 + 2.6, 74.5, sub, fontsize=7.4, color=p["muted"], va="center",
                 style="italic", zorder=3)
        yy = 62.0
        for lab, val in rows:
            axE.text(x0 + 2.6, yy, lab, fontsize=7.9, color=p["ink2"], va="center", zorder=3)
            axE.text(x0 + 2.6, yy - 6.8, val, fontsize=8.3, fontweight="bold",
                     color=p["ink"], va="center", zorder=3)
            yy -= 15.0
        if k < len(ERAS) - 1:                # explicit break glyph between eras
            axE.text(x0 + ew + gap / 2 + 0.4, 46, "//", fontsize=13, fontweight="bold",
                     color=p["muted"], ha="center", va="center")

    fig.suptitle("F6 · The unit audit — five aggregates that would have driven the wrong decision",
                 x=0.01, ha="left", fontsize=14.5, fontweight="bold", color=p["ink"])
    footnote(fig, "F6 · Rows: report §6 table. CRN null: measurement_harness_2026-07-13.md; pool re-base: agent_v11_results.md §1; exact-list mirror +\n"
                  "rating-conditioning (13 obs vs 14.14 exp): mirror_alakazam_research_2026-07-15.md; pivot-trigger panel: nightly_2026-07-15.md §1.\n"
                  "Era strip: agent_v3..v12_results.md — no cross-era comparison by construction.", mode)
    fig.tight_layout(rect=(0, 0.02, 1, 0.965))
    return fig


print("F6 — the unit audit (centerpiece)")
_f6 = render(build_F6, "F6_unit_audit")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## F10 — Behavior-diff decomposition ×2 (one method, applied twice)
#
# **Message:** the same instrument, applied twice, with two different honest outcomes.
# **Top (WinDecks/Starmie, v3):** 651 episodes of the #7 team piloting our
# byte-identical list, replayed through our pilot (24,664 non-trivial counterfactual
# decisions); five load-bearing gaps patched → +21.4 pp local meta and a real live
# climb. **Bottom (Budew/Crustle, v7):** 1,251 episodes of the #2 team on the list we
# now ship (59,508 non-trivial decisions); five sharper families found → **+5.8 pp
# meta but +0.61 pp live-band, MISSING the +3.0 gate** — shipped meta leg only. The
# diff generates hypotheses; the gate certifies them (a third, pre-registered
# application returned a CRN null — report §3.4).

# %%
def build_F10(mode):
    p = theme(mode)
    fig = plt.figure(figsize=(13.4, 13.6))
    gs = fig.add_gridspec(3, 2, width_ratios=[1.02, 1],
                          height_ratios=[3.4, 3.4, 0.78],
                          wspace=0.34, hspace=0.46)

    # --- left: per-category substantive disagreement ---
    axL = fig.add_subplot(gs[0, 0])
    cats = WD_CATS
    ys = np.arange(len(cats))[::-1]
    rates = [c[2] for c in cats]
    axL.barh(ys, rates, height=0.62, color=p["s1"], edgecolor=p["surface"], linewidth=1.0)
    for y, (cat, n, r) in zip(ys, cats):
        axL.text(r + 2, y, f"{r}%", va="center", fontsize=8.8, fontweight="bold",
                 color=p["ink"])
        axL.text(r + 16, y, f"n={n:,}", va="center", fontsize=7.4, color=p["muted"])
    axL.set_yticks(ys); axL.set_yticklabels([c[0] for c in cats], fontsize=9.2)
    axL.set_xlim(0, 140); axL.set_xticks([0, 25, 50, 75, 100])
    axL.set_xlabel("substantive disagreement (%)")
    axL.axvline(50, color=p["muted"], lw=1.0, ls=":")
    axL.grid(axis="x", color=p["grid"], lw=0.7); axL.set_axisbelow(True)
    axL.set_title("Application 1 · WinDecks (#7) on our identical Starmie list\n(disagreement by category, same states)",
                  loc="left", fontsize=11.5, color=p["ink"])

    # --- right: the five load-bearing differences (paired counts) ---
    axR = fig.add_subplot(gs[0, 1])
    m = len(WD_PAIRS)
    ys2 = np.arange(m)[::-1] * 1.0
    bh = 0.34
    wd_vals = [w for _, w, _, _ in WD_PAIRS]
    our_vals = [o for _, _, o, _ in WD_PAIRS]
    axR.barh(ys2 + bh / 2 + 0.02, wd_vals, height=bh, color=p["s1"],
             edgecolor=p["surface"], linewidth=0.8, label="WinDecks (#7)")
    axR.barh(ys2 - bh / 2 - 0.02, our_vals, height=bh, color=p["s3"],
             edgecolor=p["surface"], linewidth=0.8, label="our pilot (pre-v3), same states")
    for k, (y, w, o, (b, _, _, note)) in enumerate(zip(ys2, wd_vals, our_vals, WD_PAIRS)):
        wtxt = f"{w}" + (" — median heal 180" if "Wally" in b else "")
        otxt = f"{o}" + (" — over-burn" if "Carmine" in b else "")
        axR.text(w + 14, y + bh / 2 + 0.02, wtxt, va="center", fontsize=8.6,
                 fontweight="bold", color=p["ink"])
        axR.text(o + 14, y - bh / 2 - 0.02, otxt, va="center", fontsize=8.6,
                 color=p["ink"])
    axR.set_yticks(ys2)
    axR.set_yticklabels(["Cursed Blast\n(Dusknoir line)", "Wally's\nCompassion",
                         "END holding\nplayables", "Hilda\n(setup)",
                         "Carmine\n(hand-burn)"], fontsize=9.0)
    axR.set_ylim(-0.55, m - 0.45)
    axR.set_xlim(0, 1000)
    axR.set_xlabel("uses across the 651-episode corpus")
    axR.grid(axis="x", color=p["grid"], lw=0.7); axR.set_axisbelow(True)
    axR.legend(loc="upper center", bbox_to_anchor=(0.5, -0.155), ncol=2,
               frameon=False, fontsize=8.8, labelcolor=p["ink2"])
    axR.set_title("Five load-bearing differences (evidence counts)",
                  loc="left", fontsize=11.5, color=p["ink"])
    axR.text(985, 3.70, "snipe targets — WD kills enablers:\n"
             "Abra x373 · Kadabra x139 · Dwebble x127\n"
             "ours: 50-chips into 210-320 HP tanks",
             ha="right", va="center", fontsize=7.8, color=p["ink2"],
             bbox=dict(boxstyle="round,pad=0.45", fc=p["surface"], ec=p["axis"], lw=1.0))

    # --- middle-left: Budew disagreement by category ---
    axBL = fig.add_subplot(gs[1, 0])
    ys3 = np.arange(len(BU_CATS))[::-1]
    rates3 = [c[2] for c in BU_CATS]
    axBL.barh(ys3, rates3, height=0.62, color=p["s2"], edgecolor=p["surface"], linewidth=1.0)
    for y, (cat, n, r) in zip(ys3, BU_CATS):
        axBL.text(r + 2, y, f"{r:g}%", va="center", fontsize=8.8, fontweight="bold",
                  color=p["ink"])
        axBL.text(r + 18, y, f"n={n:,}", va="center", fontsize=7.4, color=p["muted"])
    axBL.set_yticks(ys3); axBL.set_yticklabels([c[0] for c in BU_CATS], fontsize=9.2)
    axBL.set_xlim(0, 140); axBL.set_xticks([0, 25, 50, 75, 100])
    axBL.set_xlabel("substantive disagreement (%)")
    axBL.axvline(50, color=p["muted"], lw=1.0, ls=":")
    axBL.grid(axis="x", color=p["grid"], lw=0.7); axBL.set_axisbelow(True)
    axBL.set_title("Application 2 · Budew (#2) on the Crustle list we now ship\n(disagreement by category, same states)",
                   loc="left", fontsize=11.5, color=p["ink"])

    # --- middle-right: the five Budew difference families (evidence tiles) ---
    axBR = fig.add_subplot(gs[1, 1]); axBR.axis("off")
    axBR.set_xlim(0, 100); axBR.set_ylim(0, 100)
    axBR.set_title("Five load-bearing families (evidence, not yet causal)",
                   loc="left", fontsize=11.5, color=p["ink"])
    th = 100 / len(BU_FIVE)
    for i, (fam, ev) in enumerate(BU_FIVE):
        y0 = 100 - (i + 1) * th + 1.2
        axBR.add_patch(FancyBboxPatch((1, y0), 97, th - 3.0,
                       boxstyle="round,pad=0.5,rounding_size=1.6",
                       fc=p["surface"], ec=p["axis"], lw=1.2))
        axBR.add_patch(Rectangle((1, y0), 1.0, th - 3.0, fc=p["s2"], ec="none"))
        axBR.text(3.4, y0 + th - 6.6, fam, fontsize=9.6, fontweight="bold",
                  color=p["ink"], va="center")
        for j, ln in enumerate(textwrap.wrap(ev, 66)):
            axBR.text(3.4, y0 + th - 11.4 - j * 3.9, ln, fontsize=7.9,
                      color=p["ink2"], va="center")

    # --- bottom: outcome strip, both applications ---
    axB = fig.add_subplot(gs[2, :]); axB.axis("off")
    axB.set_xlim(0, 100); axB.set_ylim(0, 10)
    axB.add_patch(FancyBboxPatch((0.5, 0.5), 48.5, 9.2, boxstyle="round,pad=0.4,rounding_size=1.6",
                  fc=p["surface"], ec=p["good"], lw=1.6))
    axB.text(2.0, 7.4, "APP 1 OUTCOME (v3)", fontsize=8.6, fontweight="bold", color=p["muted"])
    axB.text(2.0, 3.8, "9 patches gated -> 7 shipped · disagreement 49.4 -> 41.5%",
             fontsize=8.6, color=p["ink2"], va="center")
    axB.text(47.5, 5.0, "+21.4 pp\nlocal meta", fontsize=11, fontweight="bold",
             color=p["good"], ha="right", va="center")
    axB.add_patch(FancyBboxPatch((51.0, 0.5), 48.5, 9.2, boxstyle="round,pad=0.4,rounding_size=1.6",
                  fc=p["surface"], ec=p["warn"], lw=1.6))
    axB.text(52.5, 7.4, "APP 2 OUTCOME (v7)", fontsize=8.6, fontweight="bold", color=p["muted"])
    axB.text(52.5, 3.8, "+5.8 meta BUT +0.61 live-band -> MISSED the +3.0 gate\n"
             "shipped meta leg only — the gate, not the diff, certifies",
             fontsize=8.6, color=p["ink2"], va="center")
    axB.text(98.0, 5.0, "+0.61 pp\nlive-band", fontsize=11, fontweight="bold",
             color=p["warn"], ha="right", va="center")

    fig.suptitle("F10 · The counterfactual behavior diff, applied twice — a diagnostic that generates hypotheses; the gate certifies",
                 x=0.01, ha="left", fontsize=14, fontweight="bold", color=p["ink"])
    footnote(fig, "F10 · App 1: 651 WinDecks episodes, 24,664 non-trivial decisions (windecks_behavior_diff.md, agent_v3_results.md). "
                  "App 2: 1,251 Budew episodes, 59,508 non-trivial decisions (budew_behavior_diff.md, agent_v7_results.md). "
                  "Counterfactual = their observation -> our pilot; off-policy, hence gated before shipping. "
                  "Third application: pre-registered CRN null (discipline_rule_2026-07-16.md).", mode)
    fig.tight_layout(rect=(0, 0.01, 1, 0.955))
    return fig


print("F10 — behavior-diff decomposition")
_f10 = render(build_F10, "F10_behavior_diff")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## F11 — The fitted rating backend (a conditioning instrument, not a certifier)
#
# **Message:** from 20,192 public submission-sides we reconstructed the ladder's update
# rule — plain Elo above the σ-floor: **dμ = 9.0·(S−E)**, logistic scale **s = 324**
# (scale calibration on 19,569 sides, binned fit within ±0.004). That yields a settle
# law **T = anchor + 324·log₁₀(p/(1−p))**. Honest checkpoint record, stated on the
# figure: v3's 752–761 plateau priced from its own 53.0% band rate; **v7 held (local
# 66.8% → live 65.5%); v10 settled 30–50 pts BELOW projection** — one clean prospective
# checkpoint, not a universal local→live transfer. We use the fit to *condition
# comparisons on opponent strength*, never to certify local rates as live ones.
# Identical agents spread p5–p95 ≈ 240 over 36 days — driving the submission policy
# (duplicate finals; static pair-lock Aug 13–14).

# %%
def build_F11(mode):
    p = theme(mode)
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13.0, 5.9),
                                   gridspec_kw={"width_ratios": [1.2, 1]})

    # --- left: settle curve ---
    ps = np.linspace(0.30, 0.85, 300)
    T = np.array([settle(x, RS["anchor"]) for x in ps])
    axL.fill_between(ps * 100, T - RS["var_p5p95"] / 2, T + RS["var_p5p95"] / 2,
                     color=p["s1"], alpha=0.13, zorder=1,
                     label="identical-agent p5-p95 (~240 over 36 d)")
    axL.plot(ps * 100, T, color=p["s1"], lw=2.6, zorder=3,
             label="settle T = 1075 + 324*log10(p/(1-p))")
    Tv3 = np.array([settle(x, OUR_PLACE["v3_band_anchor"]) for x in ps])
    axL.plot(ps * 100, Tv3, color=p["s2"], lw=1.8, ls="--", zorder=2,
             label="same law, v3's own pool (anchor ~750)")

    # cutoffs
    for y, lab in [(CUTOFFS["top10"], "top-10"), (CUTOFFS["top50"], "top-50"),
                   (CUTOFFS["top100"], "top-100")]:
        axL.axhline(y, color=p["muted"], lw=1.0, ls=":")
        axL.text(84.5, y + 5, f"{lab} ~ {y:.0f}", fontsize=7.8, color=p["muted"],
                 ha="right", va="bottom",
                 bbox=dict(boxstyle="round,pad=0.15", fc=p["surface"], ec="none", alpha=0.9))

    # v3 placement + observed
    pv3 = OUR_PLACE["v3_band_p"] * 100
    tv3 = settle(OUR_PLACE["v3_band_p"], OUR_PLACE["v3_band_anchor"])
    axL.plot([pv3], [tv3], "o", ms=9, color=p["s2"], mec=p["surface"], mew=1.2, zorder=5)
    for obs in OUR_PLACE["v3_obs"]:
        axL.plot([pv3 + 1.1], [obs], "x", ms=7, color=p["ink2"], mew=2, zorder=5)
    axL.annotate(f"v3 live: p=0.530 on its band ->\nlaw says ~{tv3:.0f}; observed 752 / 761",
                 xy=(pv3, tv3), xytext=(56, 690), fontsize=8.6, color=p["ink2"],
                 fontweight="bold",
                 arrowprops=dict(arrowstyle="-|>", color=p["s2"], lw=1.3))

    # honest checkpoint record (no projected-target stars — judge review)
    axL.text(31.5, 1330,
             "checkpoint record (prospective):\n"
             "v7  local band 66.8% -> live 65.5%   HELD\n"
             "v10 settled 30-50 pts BELOW projection\n"
             "v11 settle MLE 850 [794, 906] (n=101,\n"
             "  per-game opponent-conditioned fit)\n"
             "-> one clean checkpoint, not a universal\n"
             "   local->live transfer; we condition, not certify",
             fontsize=8.2, color=p["ink2"], va="top",
             bbox=dict(boxstyle="round,pad=0.5", fc=p["surface"], ec=p["axis"], lw=1.0))

    axL.set_xlabel("true win probability vs the pool it farms (%)")
    axL.set_ylabel("settle rating")
    axL.set_xlim(30, 86); axL.set_ylim(620, 1420)
    axL.grid(color=p["grid"], lw=0.6); axL.set_axisbelow(True)
    axL.legend(loc="upper left", frameon=False, fontsize=8.2, labelcolor=p["ink2"])
    axL.set_title("Settle law prices our climb (anchor shifts 1:1 with farm pool)",
                  loc="left", fontsize=11.5, color=p["ink"])

    # --- right: update-rule fit ---
    d = np.linspace(-420, 420, 300)
    E324 = 1 / (1 + 10 ** (-d / RS["s"]))
    E400 = 1 / (1 + 10 ** (-d / 400.0))
    axR.plot(d, E324 * 100, color=p["s1"], lw=2.6, zorder=3,
             label="fitted logistic, s = 324 (MLE)")
    axR.plot(d, E400 * 100, color=p["muted"], lw=1.6, ls="--", zorder=2,
             label="classic Elo s = 400 (rejected)")
    cal_txt = [((155, 50), "left"), ((-400, 36), "left")]
    for (dd, obs, modv), ((tx, ty), ha) in zip(RS_CAL, cal_txt):
        axR.plot([dd], [obs * 100], "o", ms=9, color=p["s6"], mec=p["surface"],
                 mew=1.2, zorder=5)
        axR.annotate(f"binned obs {obs:.3f}\n(model {modv:.3f})", xy=(dd, obs * 100),
                     xytext=(tx, ty), ha=ha, fontsize=8.2, color=p["ink2"],
                     arrowprops=dict(arrowstyle="-|>", color=p["s6"], lw=1.1,
                                     shrinkB=6))
    axR.axhline(50, color=p["muted"], lw=1.0, ls=":")
    axR.axvline(0, color=p["muted"], lw=1.0, ls=":")
    axR.set_xlabel("rating difference (mu_self - mu_opp)")
    axR.set_ylabel("expected score E (%)")
    axR.set_ylim(0, 104); axR.set_xlim(-420, 420)
    axR.grid(color=p["grid"], lw=0.6); axR.set_axisbelow(True)
    axR.legend(loc="upper left", frameon=False, fontsize=8.4, labelcolor=p["ink2"])
    axR.set_title("Update rule: dmu = K*(S - E), K = 9.0 at the floor",
                  loc="left", fontsize=11.5, color=p["ink"])
    axR.text(0.97, 0.225, "K floor 9.0 (IQR 8.86-9.23), flat vs rating\n"
             "1000-1400 and vs games played\n"
             "new sub: sigma-burst 600 -> 1050+ in < 1 h\n"
             "first seat ~ +0.077 win-prob (~ +25 pts)\n"
             f"fit on {RS['sides']:,} submission-sides",
             transform=axR.transAxes, ha="right", va="center", fontsize=8.0,
             color=p["ink2"],
             bbox=dict(boxstyle="round,pad=0.5", fc=p["surface"], ec=p["axis"], lw=1.0))

    fig.suptitle("F11 · The rating backend, reverse-engineered from 20,192 public submission-sides — used to condition, not certify",
                 x=0.01, ha="left", fontsize=14, fontweight="bold", color=p["ink"])
    footnote(fig, "F11 · Source: rating_system_model.md (Jul 9-10 episode dumps + 12 daily manifests + LB snapshots; scale "
                  "calibration on 19,569 sides). Cutoff lines: lb_history/cutoffs_history.csv @ " + CUTOFFS["snapshot"] +
                  ". Checkpoints: nightly_2026-07-13.md (v7 held, v10 mis-predicted); v11 MLE: nightly_2026-07-15.md / "
                  "anchor_settle_prereg_2026-07-17.md.", mode)
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    return fig


print("F11 — fitted rating backend")
_f11 = render(build_F11, "F11_rating_model")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## F12 — The CRN measurement fix (null / VRF spectrum / four changed verdicts)
#
# **Message:** the gate itself was broken, so we fixed the gate before trusting any
# more deltas. (left) Unseeded engine RNG made a build differ from ITSELF by 6.0 pp;
# interposing the libstdc++ `random_device` symbols makes paired arms replay identical
# shuffles/coins/prizes — the same null reads exactly 0.0 pp (300/300 identical games).
# (middle) Realized variance-reduction factors span 2.2×–67× — the 2.2× is O1, the
# predicted dissimilar-policy regime (CRN pairs the random stream, not the trajectory
# once policies diverge). (right) Re-auditing old verdicts under CRN changed four of
# them: two patches recovered (falsely convicted by noise), two confirmed harmful with
# p-values. Development-only; excluded from every submission.
#
# (The two archetype-aggregate BONUS charts that previously lived here were deleted —
# they aggregate by `opp_class`, the exact wrong-unit mistake §6 documents.)

# %%
def build_F12(mode):
    p = theme(mode)
    fig = plt.figure(figsize=(13.6, 6.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.72, 1.12, 1.28], wspace=0.36)

    # --- left: the null test ---
    axA = fig.add_subplot(gs[0, 0])
    bars = axA.bar(["independent\nbatches", "CRN-paired\nworlds"],
                   [CRN_NULL["unpaired"], CRN_NULL["paired"]],
                   color=[p["critical"], p["s1"]], width=0.62,
                   edgecolor=p["surface"], linewidth=1.2)
    axA.text(0, CRN_NULL["unpaired"] + 0.18, f"{CRN_NULL['unpaired']:.1f} pp",
             ha="center", fontsize=11, fontweight="bold", color=p["critical"])
    axA.text(1, 0.18, "0.0 pp", ha="center", fontsize=11, fontweight="bold", color=p["s1"])
    axA.text(1, 2.6, f"{CRN_NULL['n_pairs']}/{CRN_NULL['n_pairs']}\nidentical games",
             ha="center", va="bottom", fontsize=8.2, color=p["ink2"],
             bbox=dict(boxstyle="round,pad=0.3", fc=p["surface"], ec=p["axis"], lw=0.9))
    axA.set_ylabel("apparent |delta|, v8 vs v8 (pp)")
    axA.set_ylim(0, 7.2)
    axA.grid(axis="y", color=p["grid"], lw=0.7); axA.set_axisbelow(True)
    axA.set_title("A build vs ITSELF:\nthe 6 pp phantom", loc="left",
                  fontsize=11.5, color=p["ink"])

    # --- middle: realized VRF spectrum (log x) ---
    axB = fig.add_subplot(gs[0, 1])
    vrf_sorted = sorted(CRN_VRF, key=lambda r: r[1])
    yv = np.arange(len(vrf_sorted))
    axB.axvspan(16, 44, color=p["s1"], alpha=0.10, zorder=0)
    axB.set_ylim(-1.05, len(vrf_sorted) - 0.45)
    axB.text(26.5, -0.72, "16-44x typical\nnear-clone", ha="center",
             va="center", fontsize=7.8, color=p["s1"], fontweight="bold")
    for y, (lab, v, reg) in zip(yv, vrf_sorted):
        dissim = reg.startswith("DISSIMILAR")
        c = p["s8"] if dissim else p["s1"]
        axB.hlines(y, 1, v, color=c, lw=2.0, zorder=2)
        axB.plot([v], [y], "o", ms=9, color=c, mec=p["surface"], mew=1.2, zorder=3)
        axB.text(v * 1.18, y, f"{v:g}x", va="center", fontsize=8.8,
                 fontweight="bold", color=p["ink"])
    axB.set_yticks(yv)
    axB.set_yticklabels([r[0] for r in vrf_sorted], fontsize=8.6)
    axB.set_xscale("log"); axB.set_xlim(1, 260)
    axB.set_xticks([1, 2, 5, 10, 20, 50, 100])
    axB.set_xticklabels(["1", "2", "5", "10", "20", "50", "100"])
    axB.set_xlabel("realized variance-reduction factor (log)")
    axB.grid(axis="x", color=p["grid"], lw=0.7); axB.set_axisbelow(True)
    axB.set_title("Variance reduction, per gate row\n(O1 = dissimilar-policy regime)",
                  loc="left", fontsize=11.5, color=p["ink"])

    # --- right: four changed verdicts ---
    axC = fig.add_subplot(gs[0, 2])
    yc = np.arange(len(CRN_VERDICTS))[::-1]
    for y, (lab, d, pv, verd, disp) in zip(yc, CRN_VERDICTS):
        harmful = verd == "genuinely harmful"
        c = p["critical"] if harmful else p["s1"]
        axC.barh(y, d, height=0.56, color=c, edgecolor=p["surface"], linewidth=1.0)
        if abs(d) > 0.8:   # label fits inside the bar
            axC.text(d / 2, y + 0.02, f"{d:+.2f} pp  (p={pv:g})", va="center",
                     ha="center", fontsize=8.6, fontweight="bold", color=p["surface"])
        else:
            tx = d - 0.05 if d < 0 else d + 0.05
            axC.text(tx, y + 0.02, f"{d:+.2f} pp  (p={pv:g})",
                     va="center", ha="right" if d < 0 else "left",
                     fontsize=8.6, fontweight="bold", color=p["ink"])
        axC.text(0.38, y - 0.34, f"{verd} -> {disp}", va="center", ha="left",
                 fontsize=7.8, color=(p["critical"] if harmful else p["s1"]),
                 fontweight="bold")
    axC.axvline(0, color=p["muted"], lw=1.2)
    axC.set_yticks(yc)
    axC.set_yticklabels([v[0] for v in CRN_VERDICTS], fontsize=8.8)
    axC.set_xlim(-1.75, 1.15)
    axC.set_xlabel("CRN-paired delta (pp) · exact McNemar p")
    axC.grid(axis="x", color=p["grid"], lw=0.7); axC.set_axisbelow(True)
    axC.set_title("Four verdicts CHANGED by the paired re-audit",
                  loc="left", fontsize=11.5, color=p["ink"])

    fig.suptitle("F12 · Fix the instrument first — the paired-random-world (CRN) measurement harness (development-only, never ships)",
                 x=0.01, ha="left", fontsize=14, fontweight="bold", color=p["ink"])
    footnote(fig, "F12 · Sources: measurement_harness_2026-07-13.md (null, interposition, 100% transcript-identical replay); "
                  "crn_reaudit_2026-07-13.md (VRFs 67.1/51.8/22.7/17.3/15.0/2.2x; B2F p=0.47, B3 p=0.71, ED p=0.013, O1 p=0.0035). "
                  "CRN excluded from every submission; changes no card rules and no agent-visible information.", mode)
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    return fig


print("F12 — the CRN measurement fix")
_f12 = render(build_F12, "F12_crn_measurement")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## (deleted) BONUS archetype charts — builders removed 2026-07-21
#
# The meta-positioning and observational-matchup charts aggregated by `opp_class` —
# the exact wrong-unit mistake the report's §6 documents. Deleted per the judge
# review's gallery verdict; the committed CSV loaders above remain for provenance.

# %%
# (builders deleted; see note above)


# %% [markdown]
# ## F7 — Team score trajectory (committed snapshot series) — pre-settle preview
#
# **Message:** the whole committed best-of-2 team-score series, v1 → v12, against the
# moving bars — plus the v11 skill-MLE band [794, 906] to make the report's own point
# visible: **the team score is a leaderboard DRAW that wanders around true skill**
# (±20-30 pts on an unchanged pair inside this window), which is why we anchor policy
# to the MLE, not to the latest snapshot. Final trajectory populates post-settle.

# %%
def _pdt(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M")


def build_F7(mode):
    p = theme(mode)
    fig, ax = plt.subplots(figsize=(12.6, 6.4))
    ax.set_title("F7 · Team score, 2026-07-11 -> 07-21 (pre-settle) — a draw wandering around true skill",
                 loc="left", color=p["ink"], fontsize=13)

    # v11 skill-MLE band (the anchor of record)
    t0, t1 = _pdt(OUR_HIST[0][0]), _pdt(OUR_HIST[-1][0])
    ax.axhspan(V11_MLE["lo"], V11_MLE["hi"], color=p["s2"], alpha=0.10, zorder=0)
    ax.axhline(V11_MLE["mle"], color=p["s2"], lw=1.4, ls="--", zorder=1)
    ax.text(1.002, (V11_MLE["lo"] + V11_MLE["mle"]) / 2 - 6,
            f"v11 skill MLE {V11_MLE['mle']}\n[{V11_MLE['lo']}, {V11_MLE['hi']}] (n={V11_MLE['n']})",
            transform=ax.get_yaxis_transform(), fontsize=7.8, color=p["s2"],
            va="center", fontweight="bold")

    # bars (latest committed snapshot)
    bars = [(CUTOFFS["top100"], f"top-100 ~ {CUTOFFS['top100']:.0f}")]
    if CUTOFFS.get("bronze"):
        bars.append((CUTOFFS["bronze"], f"bronze bar (top-10%) ~ {CUTOFFS['bronze']:.0f}"))
    for y, lab in bars:
        ax.axhline(y, color=p["muted"], lw=1.0, ls=":")
        ax.text(1.002, y, lab, transform=ax.get_yaxis_transform(), fontsize=7.8,
                color=p["muted"], va="center")

    # the committed team series
    ts = [_pdt(t) for t, _ in OUR_HIST]
    vs = [v for _, v in OUR_HIST]
    ax.plot(ts, vs, "-o", color=p["s1"], lw=2.2, ms=6, mec=p["surface"], mew=1.0,
            zorder=4, label="team score (best of 2 active subs, committed snapshots)")
    for k in (0, len(ts) - 1):
        ax.annotate(f"{vs[k]:.0f}", (ts[k], vs[k]), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=9.2, fontweight="bold",
                    color=p["ink"])
    # the unchanged-pair wander, called out honestly
    ax.annotate("unchanged v11+v12 pair:\n847.5 -> 869.8 -> 907.5\n(rating-path variance, not new skill)",
                xy=(ts[-1], vs[-1]), xytext=(-150, -58), textcoords="offset points",
                fontsize=8.2, color=p["ink2"], ha="left",
                arrowprops=dict(arrowstyle="-|>", color=p["muted"], lw=1.1))

    # version submit marks (sourced timestamps only)
    for lab, tsub in SUB_MARKS:
        td = _pdt(tsub)
        ax.axvline(td, color=p["s8"], lw=1.0, ls=(0, (2, 2)), alpha=0.6)
        ax.text(td, ax.get_ylim()[0] + 8 if False else 585, lab, rotation=90,
                fontsize=7.8, color=p["s8"], ha="right", va="bottom")
    ax.text(_pdt("2026-07-12T20:00"), 585, "v7-v10 iterations\nJul-12 -> 13",
            fontsize=7.6, color=p["muted"], ha="center", va="bottom", style="italic")

    ax.set_ylim(560, 1000)
    ax.set_ylabel("ladder rating (team score)")
    ax.set_xlabel("UTC")
    import matplotlib.dates as mdates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.grid(axis="y", color=p["grid"], lw=0.7); ax.set_axisbelow(True)
    ax.legend(loc="lower right", frameon=False, fontsize=8.8, labelcolor=p["ink2"])
    ax.text(0.985, 0.965, "PRE-SETTLE PREVIEW — games run to ~Aug 31; final placement populates post-settle",
            transform=ax.transAxes, ha="right", va="top", fontsize=8.4, color=p["warn"],
            fontweight="bold")

    footnote(fig, "F7 · Series: lb_history/our_rating_history.csv (every committed snapshot; 01:52 UTC cadence where "
                  "captured). Bars: cutoffs_history.csv @ " + CUTOFFS["snapshot"] + ". MLE band: numbers.json "
                  "v11_mle_settle / anchor_settle_prereg_2026-07-17.md. Submit marks: submit/SUBMISSIONS.md. NOT final data.", mode)
    fig.tight_layout()
    return fig


print("F7 — team score trajectory (committed series)")
_f7 = render(build_F7, "F7_rating_trajectory")
if _IN_NOTEBOOK:
    plt.show()


# %% [markdown]
# ## F8 / F9 — post-settle builders, NOT rendered (judge review: no stubs in the gallery)
#
# These need the settled ladder sample. The builders are retained for the post-settle
# pass but `RENDER_POST_SETTLE_STUBS = False` keeps stub PNGs out of the gallery —
# an awaiting-data placeholder earns no space in a judged attachment. F8 will be keyed
# by exact deck list (NOT `opp_class` — the §6 wrong-unit lesson) when real data lands.

# %%
RENDER_POST_SETTLE_STUBS = False  # flip post-settle, then re-run



def _stub(mode, fnum, title, will_show, refs=None):
    p = theme(mode)
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    ax.add_patch(FancyBboxPatch((1, 1), 98, 98, boxstyle="round,pad=0.4,rounding_size=2",
                 fc=p["surface"], ec=p["axis"], lw=1.4, ls=(0, (6, 4))))
    ax.text(5, 90, f"{fnum} · {title}", fontsize=15, fontweight="bold", color=p["ink"])
    ax.text(5, 80, "AWAITING SETTLED LIVE DATA  (post-settle)", fontsize=11.5,
            fontweight="bold", color=p["warn"])
    ax.text(5, 71, "Will show:", fontsize=10.5, fontweight="bold", color=p["ink2"])
    ax.text(6, 65, will_show, fontsize=9.8, color=p["ink2"], va="top", linespacing=1.45)
    if refs:
        ax.text(5, 36, "Real partial context (already committed):", fontsize=10,
                fontweight="bold", color=p["ink2"])
        ax.text(6, 30.5, refs, fontsize=9.2, color=p["muted"], va="top", linespacing=1.4)
    ax.text(5, 6, "Not fabricated — this panel is a placeholder pending settled ratings.",
            fontsize=8.4, color=p["muted"], style="italic")
    footnote(fig, f"{fnum} · post-settle stub. Source will be per-episode live logs (ListEpisodes API workflow, "
                  "live_autopsy method §0).", mode)
    fig.tight_layout()
    return fig


def build_F8(mode):
    return _stub(mode, "F8", "Live matchup heatmap (our agents)",
                 "- our portfolio's measured live win rate vs each meta archetype\n"
                 "- diverging blue/red around 50%, Wilson-bounded per cell\n"
                 "- the settled analogue of the bonus observational matrix",
                 "v3 live rows (n=101, autopsy §2): Alakazam 70.8% (17-7) · Dragapult 72.7% · "
                 "Lucario 42.9% ·\nStarmie mirror 33.3% · Archaludon 14.3% — the 600-900 band "
                 "over-samples our worst rows.")


def build_F9(mode):
    return _stub(mode, "F9", "First/second + bad-opening splits",
                 "- win rate going 1st vs 2nd for the settled portfolio\n"
                 "- performance from mulligan / thin-basic openings\n"
                 "- shows no reliance on any single initial state",
                 "Already measured: local v3 seat gap -19 pp -> live -17.8 pp (59.0/41.2, REPLICATED); "
                 "Crustle local\nseat gap -9.8 pp (tax halved); live mulligan pricing 61% clean vs 42% "
                 "(F5). Sources: live_autopsy §2/§4,\ndeck_rebakeoff §5.3.")


if RENDER_POST_SETTLE_STUBS:
    for nm, fn in [("F8_live_matchup_heatmap", build_F8), ("F9_firstsecond_openings", build_F9)]:
        print(f"{nm} — post-settle stub")
        _s = render(fn, nm)
        if _IN_NOTEBOOK:
            plt.show()
else:
    print("F8/F9 — post-settle builders retained; stub PNGs NOT rendered (gallery rule)")


# %% [markdown]
# ## Manifest — every generated PNG
#
# Confirms all figures (F1–F11 + bonus) were regenerated from committed data.

# %%
pngs = sorted(f for f in os.listdir(FIGDIR) if f.endswith(".png"))
print(f"{len(pngs)} PNGs in {os.path.relpath(FIGDIR, REPO)}:")
for f in pngs:
    sz = os.path.getsize(os.path.join(FIGDIR, f)) // 1024
    print(f"  {f:42s} {sz:5d} KB")
print("\nDone — every figure regenerated; every encoded number printed above.")
