#!/bin/bash
# v7.1 gate batch (2026-07-12): v7.1 (ship B-flags + PTCG_B2F=1) vs v7 (B2F=0, the live
# sub 54600640 config), same-batch, N=200 x 3 seeds. Rows: 16-opp gauntlet (incl. the
# new weight-0 hops_box coverage row) + starmie mirror (BAND parity). Gate:
# (a) META and BAND non-regression >= -1pp; (c) hops_box row informational.
# NOTE: B2F defaults to 1 in scoring.py -- the v7 arm MUST pin PTCG_B2F=0.
# RESUMABLE + SELF-SUPERVISING: the 2026-07-12 WSL service crashed twice mid-batch
# (Wsl/Service/E_UNEXPECTED) killing all runs; each run is now skipped when its log
# already carries the completion marker, and the outer loop relaunches the missing
# ones until everything is complete. Writes $D/DONE when all 12 logs are complete.
cd "$HOME/ptcg-work" || exit 1
D=$HOME/ptcg-work/v71_gate
mkdir -p "$D"
PY=$HOME/ptcg-venv/bin/python
export PYTHONPATH=$HOME/ptcg-work
export PTCG_OUR_DIR=$HOME/v7agent

bake_done() { grep -q "SAFETY totals" "$1" 2>/dev/null; }
mir_done()  { grep -q "^MIRRORROW"    "$1" 2>/dev/null; }

flags_for() {  # $1 = arm
  if [ "$1" = v7 ]; then echo 0; else echo 1; fi
}

for round in 1 2 3 4 5 6; do
  launched=0
  for seed in 12345 23456 34567; do
    for arm in v7 v71; do
      b2f=$(flags_for "$arm")
      if ! bake_done "$D/${arm}_${seed}.log"; then
        PTCG_B1=1 PTCG_B2=1 PTCG_B3=0 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 PTCG_B2F=$b2f \
          "$PY" bakeoff.py "$arm" 200 "$seed" > "$D/${arm}_${seed}.log" 2>&1 &
        launched=$((launched+1))
      fi
      if ! mir_done "$D/mir_${arm}_${seed}.log"; then
        PTCG_B1=1 PTCG_B2=1 PTCG_B3=0 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 PTCG_B2F=$b2f \
          "$PY" mirror_ab.py "$arm" 200 "$seed" > "$D/mir_${arm}_${seed}.log" 2>&1 &
        launched=$((launched+1))
      fi
    done
  done
  [ "$launched" -eq 0 ] && break
  wait
done

ok=1
for seed in 12345 23456 34567; do
  for arm in v7 v71; do
    bake_done "$D/${arm}_${seed}.log" || ok=0
    mir_done "$D/mir_${arm}_${seed}.log" || ok=0
  done
done
if [ "$ok" = 1 ]; then
  echo "V71 GATE BATCH DONE" > "$D/DONE"
  echo "V71 GATE BATCH DONE"
else
  echo "V71 GATE BATCH INCOMPLETE AFTER 6 ROUNDS"
fi
