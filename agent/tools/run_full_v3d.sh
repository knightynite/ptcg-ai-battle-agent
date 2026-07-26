#!/bin/bash
# Full-gauntlet round 2: v3d (P2 on / P6 off) and v3c+P6B.
cd ~/ptcg-work || exit 1
D=~/ptcg-work/v3_full
mkdir -p "$D"
N=${1:-100}
SEEDS="12345 23456 34567"
V3D="PTCG_P0=1 PTCG_P1=1 PTCG_P2=1 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=0 PTCG_P6B=0 PTCG_P7=1 PTCG_P8=0"
V3CB="PTCG_P0=1 PTCG_P1=1 PTCG_P2=0 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=0 PTCG_P6B=1 PTCG_P7=1 PTCG_P8=0"
for s in $SEEDS; do
  env $V3D PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" bakeoff.py v3d "$N" "$s" > "$D/v3d_$s.log" 2>&1 &
  env $V3CB PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" bakeoff.py v3cb "$N" "$s" > "$D/v3cb_$s.log" 2>&1 &
done
wait
PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" combine_v3.py "$D"/v3d_*.log "$D"/v3cb_*.log
