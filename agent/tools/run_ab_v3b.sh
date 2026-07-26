#!/bin/bash
# Wave-2 sentinel screens: stack-minus-one ablations + P6B isolated + seed stability.
cd ~/ptcg-work || exit 1
D=~/ptcg-work/v3_ab
mkdir -p "$D"
N=${1:-300}
ALLF="PTCG_P0=1 PTCG_P1=1 PTCG_P2=1 PTCG_P3=1 PTCG_P4=1 PTCG_P5=1 PTCG_P6=1 PTCG_P6B=0 PTCG_P7=1 PTCG_P8=1"
run() {
  local label=$1 seed=$2
  shift 2
  env $ALLF "$@" PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" ab_v3.py "$label" "$N" "$seed" > "$D/$label.log" 2>&1 &
}
run all_no_p2 12345 PTCG_P2=0
run all_no_p8 12345 PTCG_P8=0
run all_no_p6 12345 PTCG_P6=0
run all_no_p5 12345 PTCG_P5=0 PTCG_P7=0
run all_p6b 12345 PTCG_P6B=1
run all_s2 23456
run all_no_p2_s2 23456 PTCG_P2=0
run all_no_p8_s2 23456 PTCG_P8=0
env PTCG_P0=0 PTCG_P1=0 PTCG_P2=0 PTCG_P3=0 PTCG_P4=0 PTCG_P5=0 PTCG_P6=0 PTCG_P6B=0 PTCG_P7=0 PTCG_P8=0 \
  PYTHONPATH="$HOME/ptcg-work" "$HOME/ptcg-venv/bin/python" ab_v3.py base_s2 "$N" 23456 > "$D/base_s2.log" 2>&1 &
wait
grep -h "^AB\[" "$D"/*_no_*.log "$D"/all_p6b.log "$D"/all_s2.log "$D"/base_s2.log 2>/dev/null
