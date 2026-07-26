#!/bin/bash
# v5 gauntlet gate: v5 (race-state levers, final flag set via V5ENV below) vs
# same-batch v4b (R levers off), 15 opponents x N x 3 seeds per config PLUS the
# starmie-mirror row (mirror_ab vs frozen ~/mirror_b v4b copy) for the band metric.
# Usage: run_full_v5.sh [N=100] ["seeds..."] [V5ENV override]
cd "$HOME/ptcg-work" || exit 1
D="$HOME/ptcg-work/v5_full"
mkdir -p "$D"
N=${1:-100}
SEEDS=${2:-"12345 23456 34567"}
PY="$HOME/ptcg-venv/bin/python"
export PYTHONPATH="$HOME/ptcg-work"

# v4b baseline: R levers off AND T5N off (T5N=1 is a v5-candidate change; the
# baseline must reproduce the shipped v4b exactly)
V4B="PTCG_R1=0 PTCG_R2=0 PTCG_R3=0 PTCG_R4=0 PTCG_T5N=0"
V5=${3:-"PTCG_R1=1 PTCG_R2=1 PTCG_R3=1 PTCG_R4=1 PTCG_T5N=1"}

for s in $SEEDS; do
  env $V5  "$PY" bakeoff.py v5  "$N" "$s" > "$D/v5_$s.log"  2>&1 &
  env $V4B "$PY" bakeoff.py v4b "$N" "$s" > "$D/v4b_$s.log" 2>&1 &
  env $V5  "$PY" mirror_ab.py v5  "$N" "$s" > "$D/mir_v5_$s.log"  2>&1 &
  env $V4B "$PY" mirror_ab.py v4b "$N" "$s" > "$D/mir_v4b_$s.log" 2>&1 &
done
wait
echo "===================== STANDARD META-WEIGHTED READ ====================="
"$PY" combine_v3.py "$D"/v5_*.log "$D"/v4b_*.log
echo
echo "===================== BAND-WEIGHTED READ (climb metric) ====================="
"$PY" band_combine.py "$D"/v5_*.log "$D"/v4b_*.log "$D"/mir_v5_*.log "$D"/mir_v4b_*.log
