#!/bin/bash
# Config-selection batch: v6 vs v7(all) vs v7nb3 (B3 off), N=150 x 2 seeds + mirror.
cd "$HOME/ptcg-work" || exit 1
D=$HOME/ptcg-work/v7_batch5
mkdir -p "$D"
PY=$HOME/ptcg-venv/bin/python
export PYTHONPATH=$HOME/ptcg-work
export PTCG_OUR_DIR=$HOME/v7agent
for seed in 12345 23456; do
  PTCG_B1=0 PTCG_B2=0 PTCG_B3=0 PTCG_B4=0 PTCG_B5=0 PTCG_B6=0 "$PY" bakeoff.py v6 150 "$seed" > "$D/v6_${seed}.log" 2>&1 &
  PTCG_B1=1 PTCG_B2=1 PTCG_B3=1 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 "$PY" bakeoff.py v7 150 "$seed" > "$D/v7_${seed}.log" 2>&1 &
  PTCG_B1=1 PTCG_B2=1 PTCG_B3=0 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 "$PY" bakeoff.py v7nb3 150 "$seed" > "$D/v7nb3_${seed}.log" 2>&1 &
  PTCG_B1=0 PTCG_B2=0 PTCG_B3=0 PTCG_B4=0 PTCG_B5=0 PTCG_B6=0 "$PY" mirror_ab.py v6 150 "$seed" > "$D/mir_v6_${seed}.log" 2>&1 &
  PTCG_B1=1 PTCG_B2=1 PTCG_B3=1 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 "$PY" mirror_ab.py v7 150 "$seed" > "$D/mir_v7_${seed}.log" 2>&1 &
  PTCG_B1=1 PTCG_B2=1 PTCG_B3=0 PTCG_B4=1 PTCG_B5=1 PTCG_B6=1 "$PY" mirror_ab.py v7nb3 150 "$seed" > "$D/mir_v7nb3_${seed}.log" 2>&1 &
done
wait
echo "BATCH5 DONE"
