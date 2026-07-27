#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
endgame_simulator.py — committed, seeded, reproducible endgame submission-portfolio simulator.

Synthesis Lever 1 (`intel/fable_synthesis_2026-07-16.md` SS2.1) AND the adversarial audit's
outstanding demand (`intel/codex_adversarial_audit_2026-07-15.md`: "a saved, reproducible joint
simulation of (a) current true-skill uncertainty, (b) correlation between our two submissions,
(c) opponent/threshold drift, (d) the post-deadline run-out"). Ground truth and mechanics are
documented in `intel/endgame_policy_2026-07-16.md` SS1-2; read that first.

This script is Windows-Python-only (no WSL), makes no Kaggle calls, and never touches agent/ or
report/. It is a pure offline analysis of documented submission mechanics available to every team.

MODEL (see intel/endgame_policy_2026-07-16.md SS3 for the full derivation):
  A submission's observed rating at time t (days) is modeled as
      rating(t) = base_settle + shared_meta(t) + idio(t) + noise(t)
  where:
    - shared_meta(t): ONE stationary Ornstein-Uhlenbeck process per Monte-Carlo replicate, shared
      identically by every submission we make (it represents the state of the whole competitive
      field/meta at time t) -- timescale `tau` days, stationary sd `sigma_shared`.
    - idio(t): a PER-SUBMISSION-INSTANCE stationary OU process, independent across different
      submission instances (even of the identical tarball -- a resubmission draws a fresh
      realization, fresh opponent-luck path), same timescale `tau`, stationary sd `sigma_idio`.
    - noise(t): iid N(0, sigma_noise^2) fast reading noise, independent per (submission, time).
  sigma_shared^2 + sigma_idio^2 = sigma_wander^2 (the OU "slow wander" total).
  rho := sigma_shared^2 / sigma_wander^2 is the swept inter-submission correlation of the slow
  component (0 = all wander is submission-specific / escapable by resubmitting; 0.8 = mostly a
  shared-field effect / NOT escapable by resubmitting the same tarball).

  Approximation (documented, see SS7 assumptions): both OU components are treated as already at
  their stationary distribution from ~1 day after a submission's lock time onward, consistent with
  the doc's "new-sub convergence <1 day" claim about how fast the RATING ESTIMATE tracks its
  (wandering) target. This means a fresh submission's idio(t) draw at any t>lock+1day is an
  independent N(0, sigma_idio^2) draw uncorrelated with any prior submission's idio path -- exactly
  what makes a "reroll" (resubmitting the same tarball) valuable when the OLD reading's badness was
  idiosyncratic (rho small / recent) and worthless when it was shared-meta (rho large) or already
  decorrelated by a long remaining runout.

CALIBRATION TARGETS (synthesis spec, SS3 of the policy doc):
  - identical-agent p5-p95 spread ~ 240 over 36 days -> pins sigma_wander^2 + sigma_noise^2 (=: sigma_total^2)
  - 2-day net drift sd ~ 60 for a converged sub -> pins the split between "slow" and "fast" variance,
    GIVEN a choice of tau (tau itself is swept as an unknown, per the brief).
  - new-sub convergence < 1 day -> encoded structurally (see approximation above), not fit.
  - same-team divergence (v11 vs near-clone v12 ~127 pts; Yushin's two subs 190pts/2days) -> sanity
    check only (n=1 anecdotes are not fit targets), reported in the calibration section.

Run:  python scripts/endgame_simulator.py [--n 40000] [--out DIR]
Outputs JSON + CSV under intel/ (or --out) plus a console summary.
"""
import sys
import os
import json
import math
import argparse
import datetime as dt

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# --------------------------------------------------------------------------------------
# Fixed seed. Every run of this script with the same --n and CLI flags reproduces
# bit-identical results (numpy Generator with a fixed integer seed).
# --------------------------------------------------------------------------------------
MASTER_SEED = 20260716

EPOCH = dt.date(2026, 8, 1)


def day(date_str):
    y, m, d = map(int, date_str.split('-'))
    return (dt.date(y, m, d) - EPOCH).days


DEADLINE = day('2026-08-16')
CLOSE = day('2026-08-31')          # run-out end / final evaluation anchor (assumption, see SS7)

# --------------------------------------------------------------------------------------
# Calibration targets (see docstring). Pulled from intel/rating_system_model.md SS5c/5d
# since the raw per-team longitudinal series needed to re-derive them from scratch is not
# present in this repo (only a 5-day lb_history window) -- flagged, not silently trusted.
# --------------------------------------------------------------------------------------
TARGET_P5_P95_SPREAD_36D = 240.0
TARGET_2DAY_DRIFT_SD = 60.0
Z_P5_P95 = 2 * 1.6448536269514722  # two-sided 5%/95% normal spread multiple


def calibrate_wander_noise(tau):
    """Given a wander timescale tau (days), solve for (sigma_wander, sigma_noise) that jointly
    reproduce the two hardest empirical targets: total spread (p5-p95=240 over a horizon >> tau,
    i.e. total variance at stationarity) and 2-day net drift sd = 60 for an already-converged sub.
    Returns (sigma_wander, sigma_noise, sigma_total) in rating points. Raises if infeasible."""
    sigma_total = TARGET_P5_P95_SPREAD_36D / Z_P5_P95
    a = 2.0 * (1.0 - math.exp(-2.0 / tau))  # coefficient of sigma_wander^2 in Var(2-day drift)
    # a*sw2 + 2*(sigma_total^2 - sw2) = target^2  =>  sw2*(a-2) = target^2 - 2*sigma_total^2
    numerator = TARGET_2DAY_DRIFT_SD ** 2 - 2.0 * sigma_total ** 2
    denom = a - 2.0
    sw2 = numerator / denom
    if sw2 < 0 or sw2 > sigma_total ** 2:
        raise ValueError(f"tau={tau}: infeasible split (sw2={sw2:.1f}, total2={sigma_total**2:.1f})")
    sn2 = sigma_total ** 2 - sw2
    return math.sqrt(sw2), math.sqrt(sn2), sigma_total


# --------------------------------------------------------------------------------------
# Portfolio mechanics (verified, see intel/endgame_policy_2026-07-16.md SS1)
# --------------------------------------------------------------------------------------
# rating(t) for a given submission instance, given its lock time and the shared draws.
# We only ever need values at a small, fixed set of query times per scenario, so we sample
# the required OU marginals/joints in closed form (stationary covariance = sigma^2 * exp(-|dt|/tau))
# rather than simulating a full daily path -- exact, fast, and avoids discretization error.

def ou_cov(times, sigma, tau):
    times = np.asarray(times, dtype=float)
    dmat = np.abs(times[:, None] - times[None, :])
    return (sigma ** 2) * np.exp(-dmat / tau)


def sample_stationary_process(times, sigma, tau, n, rng):
    """Return array shape (len(times), n): jointly-stationary-OU draws at `times`."""
    if sigma <= 0:
        return np.zeros((len(times), n))
    cov = ou_cov(times, sigma, tau)
    cov = cov + 1e-10 * np.eye(len(times))
    L = np.linalg.cholesky(cov)
    z = rng.standard_normal((len(times), n))
    return L @ z


class Params:
    def __init__(self, tau, rho, base_settle):
        self.tau = tau
        self.rho = rho
        self.sigma_wander, self.sigma_noise, self.sigma_total = calibrate_wander_noise(tau)
        self.sigma_shared = self.sigma_wander * math.sqrt(rho)
        self.sigma_idio = self.sigma_wander * math.sqrt(1.0 - rho)
        self.base_settle = base_settle


# --------------------------------------------------------------------------------------
# Policies
# --------------------------------------------------------------------------------------
# A "policy" is a function(params, rng, n) -> dict with at least 'final' (n,) array = the
# competition-day final score (max of the 2 active subs at CLOSE), used for both the
# expected-rating and P(>=bar) reporting.

def _final_reading(base, shared_close, idio_close, noise_close):
    return base + shared_close + idio_close + noise_close


def policy_static(params, rng, n, tA, tB):
    """Lock A at tA, B at tB, no further action. Under this model (see policy doc SS3
    'gap has no effect' finding) the joint distribution of (A,B) at CLOSE does not depend on
    tA/tB individually as long as both clear the <1-day convergence floor before CLOSE --
    only the number of active, non-evicted subs at close matters, which for a 2-slot static
    lock with no later submissions is trivially both."""
    p = params
    times = [CLOSE]
    shared = sample_stationary_process(times, p.sigma_shared, p.tau, n, rng)[0]
    idioA = sample_stationary_process(times, p.sigma_idio, p.tau, n, rng)[0]
    idioB = sample_stationary_process(times, p.sigma_idio, p.tau, n, rng)[0]
    noiseA = rng.normal(0, p.sigma_noise, n)
    noiseB = rng.normal(0, p.sigma_noise, n)
    A = _final_reading(p.base_settle, shared, idioA, noiseA)
    B = _final_reading(p.base_settle, shared, idioB, noiseB)
    final = np.maximum(A, B)
    return {"final": final, "n_submissions_used": 2}


def policy_single(params, rng, n):
    """Baseline-of-baselines: only one active copy (no duplicate lock at all). Used to
    price the pair-lock's own value honestly (SS6 falsifier context)."""
    p = params
    shared = sample_stationary_process([CLOSE], p.sigma_shared, p.tau, n, rng)[0]
    idio = sample_stationary_process([CLOSE], p.sigma_idio, p.tau, n, rng)[0]
    noise = rng.normal(0, p.sigma_noise, n)
    final = _final_reading(p.base_settle, shared, idio, noise)
    return {"final": final, "n_submissions_used": 1}


def _observe_and_reroll(params, rng, n, tA, tB, t_obs, margin, mode):
    """Shared machinery for adaptive policies. mode in:
       'older_only'   -- reroll a slot only if it is BOTH bad AND the older-by-time slot
                          (the only self-consistent choice, since FIFO evicts the older slot).
       'worse_reading' -- reroll whichever slot reads worse, WITHOUT checking which is older
                          (negative control: demonstrates the FIFO trap -- may evict the good slot).
       'both'          -- unconditionally reroll both slots at t_obs (re-lock the pair late).
    Returns dict with 'final' and diagnostics.
    """
    p = params
    # Joint shared-meta draw at (t_obs, CLOSE).
    shared_ot = sample_stationary_process([t_obs, CLOSE], p.sigma_shared, p.tau, n, rng)
    shared_obs, shared_close = shared_ot[0], shared_ot[1]

    # A and B each have their own idio process observed at (t_obs, CLOSE) -- correlated across
    # time for the SAME submission instance (exp(-|CLOSE-t_obs|/tau)).
    idioA_ot = sample_stationary_process([t_obs, CLOSE], p.sigma_idio, p.tau, n, rng)
    idioB_ot = sample_stationary_process([t_obs, CLOSE], p.sigma_idio, p.tau, n, rng)
    noiseA_obs = rng.normal(0, p.sigma_noise, n)
    noiseB_obs = rng.normal(0, p.sigma_noise, n)
    noiseA_close = rng.normal(0, p.sigma_noise, n)
    noiseB_close = rng.normal(0, p.sigma_noise, n)

    readA_obs = _final_reading(p.base_settle, shared_obs, idioA_ot[0], noiseA_obs)
    readB_obs = _final_reading(p.base_settle, shared_obs, idioB_ot[0], noiseB_obs)

    threshold = p.base_settle - margin
    A_older = tA < tB  # who FIFO would evict if either is rerolled

    bad_A = readA_obs < threshold
    bad_B = readB_obs < threshold

    if mode == 'older_only':
        # Only reroll a slot if it is bad AND it is the older slot (self-consistent: the reroll
        # then correctly evicts the bad slot). If the NEWER slot is bad, do nothing -- rerolling
        # would evict the good OLDER slot instead (the FIFO trap), which is strictly worse, so a
        # rational policy withholds action rather than walk into it.
        reroll_A = bad_A & A_older
        reroll_B = bad_B & (~A_older)
    elif mode == 'worse_reading':
        # Naive: fire a single reroll whenever either slot reads bad, INTENDING to replace
        # whichever reads worse -- but FIFO does not care about intent. A single new submission
        # always evicts the OLDER of the current 2 actives, full stop (verified mechanic, SS1).
        # So the actual replaced slot is A_older, regardless of which one triggered the reroll or
        # which one the submitter "meant" to fix. This is the FIFO trap: when the worse reader is
        # the NEWER slot, firing a reroll silently destroys the GOOD older slot and leaves the bad
        # slot in place.
        reroll_fire = bad_A | bad_B
        reroll_A = reroll_fire & A_older
        reroll_B = reroll_fire & (~A_older)
    elif mode == 'both':
        reroll_A = np.ones(n, dtype=bool)
        reroll_B = np.ones(n, dtype=bool)
    else:
        raise ValueError(mode)

    # Fresh idio/noise draws for rerolled slots at CLOSE (new submission instance -> independent
    # of the pre-reroll idio path; only the shared-meta component still applies, since it's a
    # field-wide state, not a submission-specific one).
    freshA = sample_stationary_process([CLOSE], p.sigma_idio, p.tau, n, rng)[0]
    freshB = sample_stationary_process([CLOSE], p.sigma_idio, p.tau, n, rng)[0]
    fresh_noiseA = rng.normal(0, p.sigma_noise, n)
    fresh_noiseB = rng.normal(0, p.sigma_noise, n)

    idioA_close_final = np.where(reroll_A, freshA, idioA_ot[1])
    noiseA_close_final = np.where(reroll_A, fresh_noiseA, noiseA_close)
    idioB_close_final = np.where(reroll_B, freshB, idioB_ot[1])
    noiseB_close_final = np.where(reroll_B, fresh_noiseB, noiseB_close)

    # FIFO reality check: if BOTH would-be reroll flags fire from the SAME event on the SAME day
    # under 'worse_reading'/'older_only' they are for different slots by construction above, so no
    # double-eviction ambiguity arises within a single observation day.
    A_final = _final_reading(p.base_settle, shared_close, idioA_close_final, noiseA_close_final)
    B_final = _final_reading(p.base_settle, shared_close, idioB_close_final, noiseB_close_final)
    final = np.maximum(A_final, B_final)

    n_subs = 2 + reroll_A.astype(int) + reroll_B.astype(int)
    return {
        "final": final,
        "reroll_rate": float(np.mean(reroll_A | reroll_B)),
        "mean_n_submissions_used": float(np.mean(n_subs)),
    }


def policy_adaptive(params, rng, n, tA, tB, t_obs, margin, mode='older_only'):
    return _observe_and_reroll(params, rng, n, tA, tB, t_obs, margin, mode)


# --------------------------------------------------------------------------------------
# Sweep driver
# --------------------------------------------------------------------------------------

def summarize(final, bar_grid):
    out = {
        "mean": float(np.mean(final)),
        "p10": float(np.percentile(final, 10)),
        "p50": float(np.percentile(final, 50)),
        "p90": float(np.percentile(final, 90)),
        "sd": float(np.std(final)),
    }
    for bar in bar_grid:
        out[f"p_ge_{bar}"] = float(np.mean(final >= bar))
    return out


def run_sweep(n_reps, out_dir):
    rng_master = np.random.default_rng(MASTER_SEED)

    tau_grid = [5.0, 10.0, 20.0]
    rho_grid = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    base_settle_grid = [838.0, 847.5, 858.0]
    bar_grid = [860, 865, 870, 875, 880]
    margin_grid = [0, 20, 40, 60]

    tA_static, tB_static = day('2026-08-13'), day('2026-08-14')          # ~24h gap
    tA_static_g12, tB_static_g12 = day('2026-08-13'), day('2026-08-13') + 0.5  # ~12h gap
    t_obs_15 = day('2026-08-15')
    t_obs_16 = day('2026-08-16')

    calibration = {}
    for tau in tau_grid:
        sw, sn, st = calibrate_wander_noise(tau)
        # 2-day drift sd reproduction check (closed form)
        a = 2.0 * (1.0 - math.exp(-2.0 / tau))
        drift_sd = math.sqrt(a * sw ** 2 + 2 * sn ** 2)
        spread = Z_P5_P95 * math.sqrt(sw ** 2 + sn ** 2)
        calibration[tau] = {
            "sigma_wander": sw, "sigma_noise": sn, "sigma_total": st,
            "reproduced_2day_drift_sd": drift_sd,
            "reproduced_p5_p95_spread_36d": spread,
        }

    rows = []
    for tau in tau_grid:
        for rho in rho_grid:
            for base_settle in base_settle_grid:
                params = Params(tau, rho, base_settle)
                seed = MASTER_SEED + int(tau * 1000) + int(rho * 100) + int(base_settle)
                rng = np.random.default_rng(seed)

                single = summarize(policy_single(params, rng, n_reps)["final"], bar_grid)
                rows.append(dict(policy="single_submission", tau=tau, rho=rho,
                                  base_settle=base_settle, margin=None, gap_hours=None,
                                  reroll_rate=None, **single))

                static = summarize(policy_static(params, rng, n_reps, tA_static, tB_static)["final"], bar_grid)
                rows.append(dict(policy="static_pair_lock_24h_gap", tau=tau, rho=rho,
                                  base_settle=base_settle, margin=None, gap_hours=24,
                                  reroll_rate=None, **static))

                static12 = summarize(policy_static(params, rng, n_reps, tA_static_g12, tB_static_g12)["final"], bar_grid)
                rows.append(dict(policy="static_pair_lock_12h_gap", tau=tau, rho=rho,
                                  base_settle=base_settle, margin=None, gap_hours=12,
                                  reroll_rate=None, **static12))

                for t_obs, obs_label in [(t_obs_15, "aug15"), (t_obs_16, "aug16")]:
                    for margin in margin_grid:
                        res = policy_adaptive(params, rng, n_reps, tA_static, tB_static,
                                               t_obs, margin, mode='older_only')
                        s = summarize(res["final"], bar_grid)
                        rows.append(dict(policy=f"adaptive_reroll_older_only_{obs_label}", tau=tau,
                                          rho=rho, base_settle=base_settle, margin=margin,
                                          gap_hours=24, reroll_rate=res["reroll_rate"], **s))

                # negative control: FIFO trap, reroll whichever reads worse regardless of age
                res_trap = policy_adaptive(params, rng, n_reps, tA_static, tB_static,
                                            t_obs_15, 40, mode='worse_reading')
                s = summarize(res_trap["final"], bar_grid)
                rows.append(dict(policy="adaptive_reroll_worse_reading_TRAP_aug15", tau=tau,
                                  rho=rho, base_settle=base_settle, margin=40, gap_hours=24,
                                  reroll_rate=res_trap["reroll_rate"], **s))

                res_both = policy_adaptive(params, rng, n_reps, tA_static, tB_static,
                                            t_obs_15, 0, mode='both')
                s = summarize(res_both["final"], bar_grid)
                rows.append(dict(policy="adaptive_reroll_both_unconditional_aug15", tau=tau,
                                  rho=rho, base_settle=base_settle, margin=None, gap_hours=24,
                                  reroll_rate=res_both["reroll_rate"], **s))

    return calibration, rows, dict(tau_grid=tau_grid, rho_grid=rho_grid,
                                    base_settle_grid=base_settle_grid, bar_grid=bar_grid,
                                    margin_grid=margin_grid)


def write_outputs(calibration, rows, grids, out_dir, n_reps):
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "endgame_sim_results.csv")
    json_path = os.path.join(out_dir, "endgame_sim_results.json")

    fieldnames = ["policy", "tau", "rho", "base_settle", "margin", "gap_hours", "reroll_rate",
                  "mean", "sd", "p10", "p50", "p90"] + [f"p_ge_{b}" for b in grids["bar_grid"]]
    import csv
    with open(csv_path, "w", newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})

    with open(json_path, "w", encoding='utf-8') as f:
        json.dump({
            "master_seed": MASTER_SEED,
            "n_reps": n_reps,
            "calibration_targets": {
                "p5_p95_spread_36d": TARGET_P5_P95_SPREAD_36D,
                "2day_drift_sd": TARGET_2DAY_DRIFT_SD,
            },
            "calibration": {str(k): v for k, v in calibration.items()},
            "grids": grids,
            "rows": rows,
        }, f, indent=2)

    return csv_path, json_path


def print_summary(calibration, rows, grids):
    print("=== CALIBRATION (per swept tau) ===")
    for tau, c in calibration.items():
        print(f"tau={tau:>5.1f}d  sigma_wander={c['sigma_wander']:6.2f}  "
              f"sigma_noise={c['sigma_noise']:6.2f}  sigma_total={c['sigma_total']:6.2f}  "
              f"| reproduces 2-day-drift-sd={c['reproduced_2day_drift_sd']:6.2f} (target 60.0)  "
              f"p5-p95(36d)={c['reproduced_p5_p95_spread_36d']:6.1f} (target 240.0)")

    print("\n=== PAIR-LOCK RE-DERIVED VALUE (single vs static_pair_lock_24h_gap), mean over rho grid ===")
    for tau in grids["tau_grid"]:
        for base_settle in grids["base_settle_grid"]:
            singles = [r["mean"] for r in rows if r["policy"] == "single_submission"
                       and r["tau"] == tau and r["base_settle"] == base_settle]
            pairs = [r["mean"] for r in rows if r["policy"] == "static_pair_lock_24h_gap"
                     and r["tau"] == tau and r["base_settle"] == base_settle]
            gain = np.mean(pairs) - np.mean(singles)
            print(f"tau={tau:>5.1f}  base={base_settle:>6.1f}  pair-lock gain = {gain:6.2f} pts "
                  f"(single mean {np.mean(singles):7.2f} -> pair mean {np.mean(pairs):7.2f})")

    print("\n=== ADAPTIVE GAIN OVER STATIC (older_only, aug15, margin=40) by tau x rho, base=847.5 ===")
    for tau in grids["tau_grid"]:
        for rho in grids["rho_grid"]:
            stat = [r["mean"] for r in rows if r["policy"] == "static_pair_lock_24h_gap"
                    and r["tau"] == tau and r["rho"] == rho and r["base_settle"] == 847.5]
            adap_rows = [r for r in rows if r["policy"] == "adaptive_reroll_older_only_aug15"
                         and r["tau"] == tau and r["rho"] == rho and r["base_settle"] == 847.5
                         and r["margin"] == 40]
            if stat and adap_rows:
                adap = [r["mean"] for r in adap_rows]
                gain = np.mean(adap) - np.mean(stat)
                print(f"tau={tau:>5.1f}  rho={rho:.1f}  adaptive gain = {gain:6.2f} pts "
                      f"(reroll_rate={adap_rows[0]['reroll_rate']:.3f})")

    print("\n=== FIFO TRAP COST (worse_reading trap vs static), base=847.5, margin=40 ===")
    for tau in grids["tau_grid"]:
        for rho in grids["rho_grid"]:
            stat = [r["mean"] for r in rows if r["policy"] == "static_pair_lock_24h_gap"
                    and r["tau"] == tau and r["rho"] == rho and r["base_settle"] == 847.5]
            trap = [r["mean"] for r in rows if r["policy"] == "adaptive_reroll_worse_reading_TRAP_aug15"
                    and r["tau"] == tau and r["rho"] == rho and r["base_settle"] == 847.5]
            if stat and trap:
                cost = np.mean(trap) - np.mean(stat)
                print(f"tau={tau:>5.1f}  rho={rho:.1f}  trap effect = {cost:6.2f} pts vs static")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40000, help="Monte Carlo replicates per cell")
    ap.add_argument("--out", type=str, default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "intel"))
    args = ap.parse_args()

    calibration, rows, grids = run_sweep(args.n, args.out)
    csv_path, json_path = write_outputs(calibration, rows, grids, args.out, args.n)
    print_summary(calibration, rows, grids)
    print(f"\nWrote {csv_path}\nWrote {json_path}")


if __name__ == "__main__":
    main()
