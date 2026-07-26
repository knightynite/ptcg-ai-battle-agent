#!/bin/bash
# Full-gauntlet A/B: finalist v3 stacks vs same-batch R1. One process per
# (config x seed); pooled afterwards with combine_v3.py. Usage: run_full_v3.sh [N=100]
cd ~/ptcg-work || exit 1
D=~/ptcg-work/v3_full
mkdir -p "$D"
N=${1:-100}
SEEDS="12345 23456 34567"
ZERO="PTCG_P0=0 PTCG_P1=0 PTCG_P2=0 PTCG_P3=0 PTCG_P4=0 PTCG_P5=0 PTCG_P6=0 PTCG_P6B=0 PTCG_P7=0 PTCG_P8=0"
V3A="PTCG_P0=1 PTCG_P1=1 PTCG_P2=1 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=1 PTCG_P6B=0 PTCG_P7=1 PTCG_P8=0"
V3B="PTCG_P0=1 PTCG_P1=1 PTCG_P2=0 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=1 PTCG_P6B=0 PTCG_P7=1 PTCG_P8=0"
V3C="PTCG_P0=1 PTCG_P1=1 PTCG_P2=0 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=0 PTCG_P6B=0 PTCG_P7=1 PTCG_P8=0"
for s in $SEEDS; do
  env $ZERO PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" bakeoff.py R1 "$N" "$s" > "$D/R1_$s.log" 2>&1 &
  env $V3A PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" bakeoff.py v3a "$N" "$s" > "$D/v3a_$s.log" 2>&1 &
  env $V3B PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" bakeoff.py v3b "$N" "$s" > "$D/v3b_$s.log" 2>&1 &
  env $V3C PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" bakeoff.py v3c "$N" "$s" > "$D/v3c_$s.log" 2>&1 &
done
wait
PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" combine_v3.py "$D"/*.log
