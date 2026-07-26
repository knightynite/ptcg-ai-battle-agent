#!/bin/bash
# Gate confirm batch: v6 vs v7 only, N=200 x 3 seeds (double power on every row).
cd "$HOME/ptcg-work" || exit 1
D=$HOME/ptcg-work/v7_batch6
mkdir -p "$D"
PY=$HOME/ptcg-venv/bin/python
export PYTHONPATH=$HOME/ptcg-work
export PTCG_OUR_DIR=$HOME/v7agent
for seed in 12345 23456 34567; do
  PTCG_B1=0 PTCG_B2=0 PTCG_B3=0 PTCG_B4=0 PTCG_B5=0 PTCG_B6=0 "$PY" bakeoff.py v6 200 "$seed" > "$D/v6_${seed}.log" 2>&1 &
  PTCG_B1=1 PTCG_B2=1 PTCG_B3=0 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 "$PY" bakeoff.py v7 200 "$seed" > "$D/v7_${seed}.log" 2>&1 &
  PTCG_B1=0 PTCG_B2=0 PTCG_B3=0 PTCG_B4=0 PTCG_B5=0 PTCG_B6=0 "$PY" mirror_ab.py v6 200 "$seed" > "$D/mir_v6_${seed}.log" 2>&1 &
  PTCG_B1=1 PTCG_B2=1 PTCG_B3=0 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 "$PY" mirror_ab.py v7 200 "$seed" > "$D/mir_v7_${seed}.log" 2>&1 &
  PTCG_B1=0 PTCG_B2=0 PTCG_B3=0 PTCG_B4=0 PTCG_B5=0 PTCG_B6=0 "$PY" gauntlet.py one majkel_hammer_alakazam 200 "$seed" > "$D/majkel_v6_${seed}.log" 2>&1 &
  PTCG_B1=1 PTCG_B2=1 PTCG_B3=0 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 "$PY" gauntlet.py one majkel_hammer_alakazam 200 "$seed" > "$D/majkel_v7_${seed}.log" 2>&1 &
done
wait
echo "BATCH4 DONE"
