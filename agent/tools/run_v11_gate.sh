#!/bin/bash
# v11 gate driver: one arm, all (seed,row) units SEQUENTIALLY via band_gauntlet "one"
# (rowjob pattern: per-unit logs, resumable, a WSL crash loses ~one row not a batch).
# Usage: v11_rows.sh <arm> [N] [extra env assignments...]
#   arm = log prefix (v10base | v11)
# Extra env (e.g. PTCG_MIR=1) exported after the fixed v10 ledger.
cd "$HOME/ptcg-work" || exit 1
ARM=${1:?arm}; shift
N=${1:-100}; shift || true
for kv in "$@"; do export "$kv"; done
export PYTHONPATH=$HOME/ptcg-work
# 2026-07-15: $HOME/v11agent went STALE -- byte-identical to the v10 build, no P-MIR.
# Toggling PTCG_MIR against it is a SILENT NO-OP: both arms emit identical outcomes and
# the ablation reports ~0 with no error. Use v11agentB (verified == submission_v11_build).
# Guard below fails loudly rather than measuring nothing. See
# intel/mirror_alakazam_instrument_2026-07-15.md sec.2.
export PTCG_OUR_DIR=$HOME/v11agentB
if ! grep -qs PTCG_MIR "$PTCG_OUR_DIR/scoring.py"; then
  echo "FATAL: $PTCG_OUR_DIR/scoring.py has no PTCG_MIR -- stale build, ablation would be a no-op." >&2
  exit 1
fi
export PTCG_SEARCH=0 PTCG_BELIEF=1 PTCG_OPP_ROLLOUT=1
export PTCG_P0=1 PTCG_P1=1 PTCG_P2=1 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=0 PTCG_P6B=0 PTCG_P7=1 PTCG_P8=0
export PTCG_T1=0 PTCG_T2=1 PTCG_T3=1 PTCG_T4=1 PTCG_T5=1 PTCG_T5N=0
export PTCG_R1=1 PTCG_R2=0 PTCG_R3=1 PTCG_R4=0
export PTCG_DK=1
export PTCG_B1=1 PTCG_B2=1 PTCG_B3=1 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 PTCG_B2F=1
export PTCG_L1=1 PTCG_S1=0 PTCG_D1=1 PTCG_ST1=1 PTCG_O1=0
export PTCG_BF=1 PTCG_ED=0
for kv in "$@"; do export "$kv"; done
D=$HOME/ptcg-work/crn3
mkdir -p "$D"
PY=$HOME/ptcg-venv/bin/python
ROWS="kiyotah_lucario kojimar_baseline alakazam_live wmh_alakazam ryota_alakazam \
budew_crustle crustle_live self_mirror mirror_wall_fdedde79 mirror_tusk_ee52c8d3 \
mirror_216305d7 kiyotah_dragapult starmie_live starmie_blitz archaludon_live \
masami_archaludon kyogre_live hops_snorlax wmh_grimmsnarl wmh_garchomp \
wmh_bellibolt ogerpon_live majkel_hammer_alakazam comfey_hammer_denial rocket_spidops"
rc=0
for seed in 12345 23456 34567; do
  for row in $ROWS; do
    log=$D/${ARM}_${seed}_${row}.log
    if grep -q "^BANDROW," "$log" 2>/dev/null; then continue; fi
    timeout 7200 $PY band_gauntlet.py one "$row" "$N" "$seed" > "$log" 2>&1
    if ! grep -q "^BANDROW," "$log"; then
      echo "MISSING ${ARM}_${seed}_${row}"; tail -3 "$log"; rc=1
      if grep -qi "catastrophic failure" "$log"; then echo "CATASTROPHIC-STOP"; exit 9; fi
    else
      grep -h "^BANDROW," "$log"
    fi
  done
done
# per-seed combined logs for crn_pool.py
for seed in 12345 23456 34567; do
  cat $D/${ARM}_${seed}_*.log 2>/dev/null | grep -h "^BANDROW," > $D/${ARM}_seed${seed}.log
done
echo "ARM-DONE $ARM rc=$rc"
exit $rc
