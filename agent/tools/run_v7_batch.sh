#!/bin/bash
# v7 gate + per-patch A/B, ONE batch (unseeded engine RNG -> same-batch deltas only).
# Arms: v6 (B1..B6=0, exact shipped config), b1..b6 (single patch on), v7 (all on).
# Rows: 15-opp gauntlet x100 x3 seeds per arm; mirror_ab + majkel_hammer_alakazam
# informational rows for v6/v7 only.
cd "$HOME/ptcg-work" || exit 1
D=$HOME/ptcg-work/v7_batch3
mkdir -p "$D"
PY=$HOME/ptcg-venv/bin/python
export PYTHONPATH=$HOME/ptcg-work
export PTCG_OUR_DIR=$HOME/v7agent

flags() {
  case $1 in
    v6) echo "0 0 0 0 0 0";;
    b1) echo "1 0 0 0 0 0";;
    b2) echo "0 1 0 0 0 0";;
    b3) echo "0 0 1 0 0 0";;
    b4) echo "0 0 0 1 0 0";;
    b5) echo "0 0 0 0 1 0";;
    b6) echo "0 0 0 0 0 1";;
    v7) echo "1 1 1 1 1 1";;
  esac
}

for seed in 12345 23456 34567; do
  for arm in v6 b1 b2 b3 b4 b5 b6 v7; do
    read a b c d e f <<< "$(flags $arm)"
    PTCG_B1=$a PTCG_B2=$b PTCG_B3=$c PTCG_B4=$d PTCG_B5=$e PTCG_B6=$f \
      "$PY" bakeoff.py "$arm" 100 "$seed" > "$D/${arm}_${seed}.log" 2>&1 &
  done
  for arm in v6 v7; do
    read a b c d e f <<< "$(flags $arm)"
    PTCG_B1=$a PTCG_B2=$b PTCG_B3=$c PTCG_B4=$d PTCG_B5=$e PTCG_B6=$f \
      "$PY" mirror_ab.py "$arm" 100 "$seed" > "$D/mir_${arm}_${seed}.log" 2>&1 &
    PTCG_B1=$a PTCG_B2=$b PTCG_B3=$c PTCG_B4=$d PTCG_B5=$e PTCG_B6=$f \
      "$PY" gauntlet.py one majkel_hammer_alakazam 100 "$seed" > "$D/majkel_${arm}_${seed}.log" 2>&1 &
  done
done
wait
echo "BATCH DONE"
